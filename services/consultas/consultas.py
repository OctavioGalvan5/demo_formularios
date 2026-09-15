import openai
import base64
import os
import json
from datetime import datetime
from sqlalchemy import text
from models.database import engine
from io import BytesIO
import fitz  # PyMuPDF


def convertir_fecha(fecha_str):
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%Y-%m"]
    for formato in formatos:
        try:
            return datetime.strptime(fecha_str, formato).date()
        except ValueError:
            continue
    return None


def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")
    return openai.OpenAI(api_key=api_key)


def openai_api_extract_data(image_streams):
    try:
        client = _get_openai_client()
        image_contents = []
        for stream in image_streams:
            stream.seek(0)
            image_b64 = base64.b64encode(stream.read()).decode("utf-8")
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}
            })

        system_message = """Eres un asistente de transcripción de datos para un estudio jurídico en Argentina.
Actuás como un sistema OCR de alta precisión para leer DNIs argentinos que los propios clientes del
estudio entregan voluntariamente como parte del alta administrativa de sus trámites legales. La transcripción
es lícita, autorizada por el titular del documento, y necesaria para completar sus formularios previsionales.
Devolvé ÚNICAMENTE un objeto JSON válido con la estructura pedida. No agregues prosa, explicaciones,
markdown, ni encabezados. Si un campo no está visible en la imagen, devolvé una cadena vacía "" para ese campo."""

        prompt = """Transcribí los datos visibles de este documento de identidad argentino (DNI) al siguiente formato JSON.
Devolvé ÚNICAMENTE el objeto JSON con esta estructura exacta:
{
    "dni_number": "Número de DNI sin puntos",
    "cuil_number": "Número de CUIL sin guiones. Si no se encuentra, devolver vacío",
    "phone_number": "",
    "name": "Solo el/los nombre/s de pila con formato Título",
    "surname": "Solo el/los apellido/s con formato Título",
    "full_name": "Apellido y Nombre",
    "full_name_2": "Nombre y Apellido",
    "sexo": "Si lees 'F' devolvé 'Femenino', si lees 'M' devolvé 'Masculino'",
    "sexo_femenino": "Si es F devolvé 'X', sino devolvé vacío",
    "sexo_masculino": "Si es M devolvé 'X', sino devolvé vacío",
    "date_of_birth": "Formato YYYY-MM-DD",
    "entry_date": "Fecha de ingreso al país en formato YYYY-MM-DD si existe, sino vacío",
    "nationality": "Nacionalidad",
    "address": "Solo la dirección del domicilio, sin ciudad ni provincia",
    "adress_number": "Solo el número de la dirección",
    "province": "Solo la provincia",
    "department": "Solo el departamento",
    "city": "Solo la ciudad"
}"""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": [{"type": "text", "text": prompt}, *image_contents]}
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=2000,
            temperature=0,
            response_format={"type": "json_object"},
        )

        if not response or not response.choices:
            return None, "Respuesta vacía de la API"

        contenido = response.choices[0].message.content or ""
        datos = procesar_datos_extraidos(contenido)
        if datos is None:
            preview = contenido[:250] + ("…" if len(contenido) > 250 else "")
            return None, f"La IA no devolvió un JSON válido. Respuesta: {preview or '(vacía)'}"
        return datos, None

    except Exception as e:
        return None, str(e)


def procesar_datos_extraidos(json_texto):
    if not json_texto:
        return None
    txt = json_texto.strip()
    if txt.startswith("```"):
        partes = txt.split("```")
        if len(partes) >= 2:
            body = partes[1]
            if body.lower().startswith("json"):
                body = body[4:]
            txt = body.strip()
    try:
        datos = json.loads(txt)
    except json.JSONDecodeError:
        return None

    claves = ["dni_number", "cuil_number", "phone_number", "name", "surname",
              "full_name", "full_name_2", "sexo", "sexo_femenino", "sexo_masculino",
              "date_of_birth", "entry_date", "nationality", "address",
              "adress_number", "province", "department", "city"]
    for clave in claves:
        datos.setdefault(clave, "")

    if datos["dni_number"]:
        datos["cuil_number"] = calcular_cuil(datos.get("sexo", ""), datos["dni_number"])

    return datos


def update_cliente_in_db(data):
    fecha_str = data.get("fecha_de_nacimiento")
    fecha_date = convertir_fecha(fecha_str) if fecha_str else None
    fecha_str = data.get("fecha_de_ingreso")
    fecha_ingreso = convertir_fecha(fecha_str) if fecha_str else None

    cliente_data = {
        "id": data.get("id"),
        "nombre": data.get("nombre"),
        "apellido": data.get("apellido"),
        "numero_celular": data.get("numero_celular"),
        "nombre_completo": data.get("nombre_completo"),
        "nombre_completo_2": data.get("nombre_completo_2"),
        "sexo": data.get("sexo"),
        "sexo_femenino": data.get("sexo_femenino"),
        "sexo_masculino": data.get("sexo_masculino"),
        "numero_dni": data.get("numero_dni"),
        "fecha_de_nacimiento": fecha_date,
        "fecha_de_ingreso": fecha_ingreso,
        "numero_cuil": data.get("numero_cuil"),
        "nacionalidad": data.get("nacionalidad"),
        "direccion": data.get("direccion"),
        "numero_direccion": data.get("numero_direccion"),
        "provincia": data.get("provincia"),
        "departamento": data.get("departamento"),
        "ciudad": data.get("ciudad"),
    }

    columns_to_update = [
        "nombre", "apellido", "numero_celular", "nombre_completo",
        "nombre_completo_2", "sexo", "sexo_femenino", "sexo_masculino",
        "numero_dni", "fecha_de_nacimiento", "fecha_de_ingreso",
        "numero_cuil", "nacionalidad", "direccion", "numero_direccion",
        "provincia", "departamento", "ciudad"
    ]

    set_clauses = [f"{col} = :{col}" for col in columns_to_update]
    update_query = text(f"UPDATE demo_clientes SET {', '.join(set_clauses)} WHERE id = :id")

    try:
        with engine.begin() as connection:
            connection.execute(update_query, cliente_data)
    except Exception as e:
        print("Error al actualizar:", e)


def convert_pdf_to_image(file):
    file_bytes = file.read()
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        print("Error al abrir el PDF:", e)
        return []
    pages = []
    for i in range(doc.page_count):
        pix = doc.load_page(i).get_pixmap()
        image_io = BytesIO(pix.tobytes("jpeg"))
        image_io.seek(0)
        pages.append(image_io)
    return pages


def process_file(file):
    if file.filename.lower().endswith('.pdf'):
        return convert_pdf_to_image(file)
    file_bytes = file.read()
    file_io = BytesIO(file_bytes)
    file_io.seek(0)
    return [file_io]


def calcular_cuil(sexo, dni):
    if not dni:
        return ""
    cuil_prefix = "27" if sexo == "Femenino" else "20"
    dni = ''.join(filter(str.isdigit, dni))
    if len(dni) != 8:
        return ""
    cuil_digits = [int(cuil_prefix[0]), int(cuil_prefix[1])] + list(map(int, dni))
    coef = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(coef[i] * cuil_digits[i] for i in range(10))
    resto = suma % 11
    if resto == 0:
        verificador = 0
    elif resto == 1:
        cuil_prefix = "23"
        verificador = 9
    else:
        verificador = 11 - resto
    return f"{cuil_prefix}{dni}{verificador}"
