import openai
import base64
import os
import json
from datetime import datetime
from sqlalchemy import text
from models.database import engine
from io import BytesIO
import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORMULARIOS_DIR = os.path.join(BASE_DIR, 'datos', 'formularios')

CHECKBOX_MAPPING = {
    "formularios_Reconocimiento_de_Servicios": "formularios_reconocimiento_servicios",
    "formularios_Jubilación": "formularios_jubilacion",
    "formularios_Jubilación_con_24.476": "formularios_jubilacion_con_24_476",
    "formularios_Jubilación_con_27.705": "formularios_jubilacion_con_27_705",
    "formularios_Jubilación_docente": "formularios_jubilacion_docente",
    "formularios_Jubilación_serv_diferenciales": "formularios_jubilacion_serv_diferenciales",
    "formularios_Jubilación_Servicio_Doméstico": "formularios_jubilacion_servicio_domestico",
    "formularios_Jubilación_HIV": "formularios_jubilacion_hiv",
    "formularios_Jubilación_trabajadores_minusvalidos_ceguera": "formularios_jubilacion_minusvalidos_ceguera",
    "formularios_Pension_Directa_casados": "formularios_pension_directa_casados",
    "formularios_Pension_Directa_convivientes": "formularios_pension_directa_convivientes",
    "formularios_Pension_Deriva_casados": "formularios_pension_derivada_casados",
    "formularios_Pension_Deriva_convivientes": "formularios_pension_derivada_convivientes",
    "formularios_Pension_Directa_Derivada_hijo_discapacitada": "formularios_pension_directa_derivada_hijo_discapacitada",
    "formularios_Retiro_Transitorio_por_invalidez": "formularios_retiro_transitorio_por_invalidez",
    "formularios_Retiro_Transitorio_por_invalidez_SDM": "formularios_retiro_transitorio_por_invalidez_sdm",
    "formularios_PUAM": "formularios_puam",
    "formularios_UCAP": "formularios_ucap",
    "formularios_Reajuste_de_Haberes": "formularios_reajuste_de_haberes",
    "formularios_asignacion_fliar_hijo_discapacitado": "formularios_asignacion_fliar_hijo_discapacitado",
    "(Beneficios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado": "beneficios_nuevo_convenio_de_honorarios_numerado",
    "(Juicios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado": "juicios_nuevo_convenio_de_honorarios_numerado",
    "CONVENIO_MAGISTRADOS": "convenio_magistrados",
    "CONVENIO_DE_GASTOS_ADMINISTRATIVOS_JUDICIALES": "convenio_de_gastos_administrativos_judiciales",
    "2.91_Guarda_Documental": "_2_91_guarda_documental",
    "6.18_Solicitud_Prestaciones_Previsionales": "_6_18_solicitud_prestaciones_previsionales",
    "6.18_Solicitud_Prestaciones_Previsionales_pension": "_6_18_solicitud_prestaciones_previsionales_pension",
    "Acta_Poder": "acta_poder",
    "Anexo_Baja_Puam": "anexo_baja_puam",
    "Anexo_I_Ley_27.625": "anexo_i_ley_27625",
    "Anexo_II_DEC_894_01": "anexo_ii_dec_894_01",
    "Anexo_II_980_05": "anexo_ii_980_05",
    "Anexo_II_Socioeconómico_24.476": "anexo_ii_socioeconomico_24_476",
    "Baja_PNC": "baja_pnc",
    "Carta_Poder_SRT": "carta_poder_srt",
    "DDJJ_de_salud_resol_300": "ddjj_de_salud_resol_300",
    "DDJJ_Ley_17562_6.9": "ddjj_ley_17562_6_9",
    "F_3283_Autorización_ARCA": "f_3283_autorizacion_arca",
    "Formulario_Carta_Poder_(CSS)": "formulario_carta_poder_css",
    "Formulario_encuesta_RTI": "formulario_encuesta_rti",
    "PS_1.75_Carta_Poder_Cap_III_27.705": "ps_1_75_carta_poder_cap_iii_27705",
    "PS_5.7_Derivacion_aportes_Obra_Social": "ps_5_7_derivacion_aportes_obra_social",
    "PS_5.11_Aceptacion_de_la_Obra_Social": "ps_5_11_aceptacion_de_la_obra_social",
    "PS_6.292_DDJJ_solicitante_SDM": "ps_6_292_ddjj_solicitante_sdm",
    "PS_6.293_DDJJ_Dador_de_trabajo_SDM": "ps_6_293_ddjj_dador_de_trabajo_sdm",
    "PS_6.294_DDJJ_renuncia_SDM": "ps_6_294_ddjj_renuncia_sdm",
    "PS_6.2_Certific_de_Servicios": "ps_6_2_certific_de_servicios",
    "PS_6.3_Nivel_de_estudios_RTI": "ps_6_3_nivel_de_estudios_rti",
    "PS_6.4_Carta_Poder": "ps_6_4_carta_poder",
    "PS_6.8_DDJJ_TESTIMONIAL_ACRED_SERVICIOS": "ps_6_8_ddjj_testimonial_acred_servicios",
    "PS_6.13_DDJJ_Testimonial_dependencia_economica": "ps_6_13_ddjj_testimonial_dependencia_economica",
    "PS_6.268_Certific_de_Servicios_(Ampliatoria)": "ps_6_268_certific_de_servicios_ampliatoria",
    "PS_6.273_Certific_complementaria_investigadores": "ps_6_273_certific_complementaria_investigadores",
    "PS_6.278_Dto_de_cuotas_jubilación": "ps_6_278_dto_de_cuotas_jubilacion",
    "PS_6.279_Dto_de_cuotas_pensión": "ps_6_279_dto_de_cuotas_pension",
    "PS_6.284_DDJJ_Fzas_Armadas": "ps_6_284_ddjj_fzas_armadas",
    "PS_6.305_Carta_Poder": "ps_6_305_carta_poder",
    "Renuncia_condicionada": "renuncia_condicionada",
    "Telegrama_revocando_poder": "telegrama_revocando_poder",
    "poder_AR_La_plata": "poder_ar_la_plata",
    "poder_AR_punta_alta": "poder_ar_punta_alta",
    "PS_5.8_Obra_Social": "ps_5_8_obra_social",
    "PS_6.304_Carta_Poder": "ps_6_304_carta_poder",
    "formularios_Jubilacion_nueva": "formularios_jubilacion_nueva",
    "formularios_Jubilacion_PC_nueva": "formularios_jubilacion_pc_nueva",
    "formularios_Jubilacion_Moratoria_nueva": "formularios_jubilacion_moratoria_nueva",
    "formularios_Pension_nueva": "formularios_pension_nueva",
}


def _f(nombre):
    return os.path.join(FORMULARIOS_DIR, nombre)


FORMULARIOS_MAPPING = {
    "2.91_Guarda_Documental":                               {"path": _f("2.91_Guarda_Documental.pdf"),                              "label": "2.91 Guarda Documental"},
    "6.18_Solicitud_Prestaciones_Previsionales":            {"path": _f("6.18_Solicitud_Prestaciones_Previsionales.pdf"),           "label": "6.18 Solicitud Prestaciones Previsionales"},
    "6.18_Solicitud_Prestaciones_Previsionales_pension":    {"path": _f("6.18_Solicitud_Prestaciones_Previsionales_pension.pdf"),   "label": "6.18 Solicitud Prestaciones Previsionales pension"},
    "Anexo_Baja_Puam":                                      {"path": _f("Anexo_Baja_Puam.pdf"),                                     "label": "Anexo Baja Puam"},
    "Anexo_I_Ley_27.625":                                   {"path": _f("Anexo_I_Ley_27.625.pdf"),                                  "label": "Anexo I Ley 27.625"},
    "Anexo_II_DEC_894_01":                                  {"path": _f("Decreto 894.pdf"),                                        "label": "Anexo II DEC 894 01"},
    "Anexo_II_980_05":                                      {"path": _f("Anexo_II_980_05.pdf"),                                     "label": "Anexo II 980 05"},
    "Anexo_II_Socioeconómico_24.476":                       {"path": _f("Anexo_II_Socioeconómico_24.476.pdf"),                      "label": "Anexo II Socioeconómico 24.476"},
    "Baja_PNC":                                             {"path": _f("Baja_PNC.pdf"),                                           "label": "Baja PNC"},
    "Carta_Poder_SRT":                                      {"path": _f("Carta_Poder_SRT.pdf"),                                     "label": "Carta Poder SRT"},
    "DDJJ_de_salud_resol_300":                              {"path": _f("DDJJ_de_salud_resol_300.pdf"),                             "label": "DDJJ de salud resol 300"},
    "DDJJ_Ley_17562_6.9":                                   {"path": _f("DDJJ_Ley_17562_6.9.pdf"),                                  "label": "DDJJ Ley 17562 6.9"},
    "F_3283_Autorización_ARCA":                             {"path": _f("F_3283_Autorización_ARCA.pdf"),                            "label": "F 3283 Autorización ARCA"},
    "Formulario_Carta_Poder_(CSS)":                         {"path": _f("Formulario_Carta_Poder_(CSS).pdf"),                        "label": "Formulario Carta Poder (CSS)"},
    "Formulario_encuesta_RTI":                              {"path": _f("Formulario_encuesta_RTI.pdf"),                             "label": "Formulario encuesta RTI"},
    "PS_1.75_Carta_Poder_Cap_III_27.705":                   {"path": _f("PS_1.75_Carta_Poder_Cap_III_27.705.pdf"),                  "label": "PS 1.75 Carta Poder Cap III 27.705"},
    "PS_5.7_Derivacion_aportes_Obra_Social":                {"path": _f("PS_5.7_Derivacion_aportes_Obra_Social.pdf"),              "label": "PS 5.7 Derivacion aportes Obra Social"},
    "PS_5.11_Aceptacion_de_la_Obra_Social":                 {"path": _f("PS_5.11_Aceptacion_de_la_Obra_Social.pdf"),               "label": "PS 5.11 Aceptacion de la Obra Social"},
    "PS_6.2_Certific_de_Servicios":                         {"path": _f("PS_6.2_Certific_de_Servicios.pdf"),                       "label": "PS 6.2 Certific de Servicios"},
    "PS_6.3_Nivel_de_estudios_RTI":                         {"path": _f("PS_6.3_Nivel_de_estudios_RTI.pdf"),                       "label": "PS 6.3 Nivel de estudios RTI"},
    "PS_6.4_Carta_Poder":                                   {"path": _f("PS_6.4_Carta_Poder.pdf"),                                  "label": "PS 6.4 Carta Poder"},
    "PS_6.8_DDJJ_TESTIMONIAL_ACRED_SERVICIOS":              {"path": _f("PS_6.8_DDJJ_TESTIMONIAL_ACRED_SERVICIOS.pdf"),             "label": "PS 6.8 DDJJ TESTIMONIAL ACRED SERVICIOS"},
    "PS_6.13_DDJJ_Testimonial_dependencia_economica":       {"path": _f("PS_6.13_DDJJ_Testimonial_dependencia_económica.pdf"),      "label": "PS 6.13 DDJJ Testimonial dependencia economica"},
    "PS_6.268_Certific_de_Servicios_(Ampliatoria)":         {"path": _f("PS_6.268_Certific_de_Servicios_(Ampliatoria).pdf"),        "label": "PS 6.268 Certific de Servicios (Ampliatoria)"},
    "PS_6.273_Certific_complementaria_investigadores":      {"path": _f("PS_6.273_Certific_complementaria_investigadores.pdf"),     "label": "PS 6.273 Certific complementaria investigadores"},
    "PS_6.278_Dto_de_cuotas_jubilación":                    {"path": _f("PS_6.278_Dto_de_cuotas_jubilación.pdf"),                   "label": "PS 6.278 Dto de cuotas jubilación"},
    "PS_6.279_Dto_de_cuotas_pensión":                       {"path": _f("PS_6.279_Dto_de_cuotas_pensión.pdf"),                      "label": "PS 6.279 Dto de cuotas pensión"},
    "PS_6.284_DDJJ_Fzas_Armadas":                           {"path": _f("PS_6.284_DDJJ_Fzas_Armadas.pdf"),                         "label": "PS 6.284 DDJJ Fzas Armadas"},
    "PS_6.292_DDJJ_solicitante_SDM":                        {"path": _f("PS_6.292_DDJJ_solicitante_SDM.pdf"),                      "label": "PS 6.292 DDJJ solicitante SDM"},
    "PS_6.293_DDJJ_Dador_de_trabajo_SDM":                   {"path": _f("PS_6.293_DDJJ_Dador_de_trabajo_SDM.pdf"),                  "label": "PS 6.293 DDJJ Dador de trabajo SDM"},
    "PS_6.294_DDJJ_renuncia_SDM":                           {"path": _f("PS_6.294_DDJJ_renuncia_SDM.pdf"),                         "label": "PS 6.294 DDJJ renuncia SDM"},
    "PS_6.305_Carta_Poder":                                 {"path": _f("PS_6.305_Carta_Poder.pdf"),                               "label": "PS 6.305 Carta Poder"},
    "Renuncia_condicionada":                                {"path": _f("Renuncia_condicionada.pdf"),                               "label": "Renuncia condicionada"},
    "Telegrama_revocando_poder":                            {"path": _f("Telegrama_revocando_poder.pdf"),                           "label": "Telegrama revocando poder"},
    "poder_AR_La_plata":                                    {"path": _f("poder la plata.pdf"),                                     "label": "Poder AR La Plata"},
    "poder_AR_punta_alta":                                  {"path": _f("poder Punta alta.pdf"),                                   "label": "Poder AR Punta Alta"},
    "PS_5.8_Obra_Social":                                   {"path": _f("Obra social 5.8.pdf"),                                    "label": "PS 5.8 Obra Social"},
    "PS_6.304_Carta_Poder":                                 {"path": _f("Carta Poder 6.304.pdf"),                                   "label": "PS 6.304 Carta Poder"},
    "Acta_Poder":                                           {"path": _f("Acta_Poder.docx"),                                        "label": "Acta Poder"},
    "(Beneficios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado":  {"path": _f("(Beneficios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado.docx"), "label": "(Beneficios) NUEVO CONVENIO DE HONORARIOS Numerado"},
    "(Juicios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado":     {"path": _f("(Juicios)_NUEVO_CONVENIO_DE_HONORARIOS_Numerado.docx"),    "label": "(Juicios) NUEVO CONVENIO DE HONORARIOS Numerado"},
    "CONVENIO_MAGISTRADOS":                                 {"path": _f("CONVENIO_MAGISTRADOS.docx"),                              "label": "CONVENIO MAGISTRADOS"},
    "CONVENIO_DE_GASTOS_ADMINISTRATIVOS_JUDICIALES":        {"path": _f("CONVENIO_DE_GASTOS_ADMINISTRATIVOS_JUDICIALES.docx"),     "label": "CONVENIO DE GASTOS ADMINISTRATIVOS JUDICIALES"},
}


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

    for html_name, db_column_name in CHECKBOX_MAPPING.items():
        cliente_data[db_column_name] = (data.get(html_name) == 'on')

    columns_to_update = [
        "nombre", "apellido", "numero_celular", "nombre_completo",
        "nombre_completo_2", "sexo", "sexo_femenino", "sexo_masculino",
        "numero_dni", "fecha_de_nacimiento", "fecha_de_ingreso",
        "numero_cuil", "nacionalidad", "direccion", "numero_direccion",
        "provincia", "departamento", "ciudad"
    ]
    columns_to_update.extend(CHECKBOX_MAPPING.values())

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
