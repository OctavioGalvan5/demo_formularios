import os
import json
import uuid
from io import BytesIO
from datetime import datetime

from sqlalchemy import text
from pypdf import PdfReader, PdfWriter
from docxtpl import DocxTemplate
from werkzeug.utils import secure_filename

from models.database import engine
from services import almacenamiento

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Carpeta local de origen para la importación masiva única (datos/formularios/
# con las plantillas que ya venían con el proyecto). Los formularios subidos
# desde la app viven en MinIO (services/almacenamiento.py), no acá.
FORMULARIOS_DIR = os.path.join(BASE_DIR, 'datos', 'formularios')
os.makedirs(FORMULARIOS_DIR, exist_ok=True)

EXTENSIONES_PERMITIDAS = {'.pdf': 'pdf', '.docx': 'docx'}
CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

# Vocabulario fijo de variables del sistema. El admin del estudio mapea los
# campos detectados en cada PDF/DOCX que sube contra estas claves; el
# generador arma este mismo diccionario para cada cliente al momento de
# generar los documentos.
VARIABLES_SISTEMA = {
    "nombre": "Nombre",
    "apellido": "Apellido",
    "nombre_completo": "Nombre completo (Apellido Nombre)",
    "nombre_completo_2": "Nombre completo (Nombre Apellido)",
    "numero_dni": "Número de DNI",
    "numero_cuil": "Número de CUIL",
    "cuil_inicio": "CUIL — primeros 2 dígitos",
    "cuil_fin": "CUIL — dígito verificador",
    "numero_celular": "Celular",
    "sexo": "Sexo (texto)",
    "sexo_femenino": "Marca 'X' si es femenino",
    "sexo_masculino": "Marca 'X' si es masculino",
    "fecha_de_nacimiento_formato": "Fecha de nacimiento (DD/MM/AAAA)",
    "fecha_de_nacimiento": "Fecha de nacimiento (DDMMAAAA)",
    "fecha_de_nacimiento_dia": "Día de nacimiento",
    "fecha_de_nacimiento_mes": "Mes de nacimiento",
    "fecha_de_nacimiento_año": "Año de nacimiento",
    "fecha_de_ingreso": "Fecha de ingreso al país (DDMMAA)",
    "nacionalidad": "Nacionalidad",
    "direccion": "Domicilio (calle)",
    "numero_direccion": "Domicilio (número)",
    "provincia": "Provincia",
    "departamento": "Departamento",
    "ciudad": "Ciudad",
    "donde_firmar": "Marca de firma ('X')",
}


def build_datos_cliente(row):
    """row: mapping (RowMapping/dict) de demo_clientes. Arma el diccionario
    de variables del sistema usado para rellenar cualquier formulario."""
    nombre = row.get("nombre", "") or ""
    apellido = row.get("apellido", "") or ""

    def fmt(d, f):
        if not d:
            return ""
        if hasattr(d, 'strftime'):
            return d.strftime(f)
        try:
            return datetime.strptime(str(d)[:10], '%Y-%m-%d').strftime(f)
        except (ValueError, TypeError):
            return str(d)

    return {
        "nombre": nombre,
        "apellido": apellido,
        "numero_celular": row.get("numero_celular", "") or "",
        "nombre_completo": f"{apellido} {nombre}".strip(),
        "nombre_completo_2": f"{nombre} {apellido}".strip(),
        "sexo": row.get("sexo", "") or "",
        "sexo_femenino": row.get("sexo_femenino", "") or "",
        "sexo_masculino": row.get("sexo_masculino", "") or "",
        "numero_dni": row.get("numero_dni", "") or "",
        "fecha_de_nacimiento_formato": fmt(row.get("fecha_de_nacimiento"), '%d/%m/%Y'),
        "fecha_de_nacimiento": fmt(row.get("fecha_de_nacimiento"), '%d%m%Y'),
        "fecha_de_nacimiento_dia": fmt(row.get("fecha_de_nacimiento"), '%d'),
        "fecha_de_nacimiento_mes": fmt(row.get("fecha_de_nacimiento"), '%m'),
        "fecha_de_nacimiento_año": fmt(row.get("fecha_de_nacimiento"), '%Y'),
        "fecha_de_ingreso": fmt(row.get("fecha_de_ingreso"), '%d%m%y'),
        "numero_cuil": row.get("numero_cuil", "") or "",
        "cuil_inicio": (row.get("numero_cuil", "") or "")[:2],
        "cuil_fin": (row.get("numero_cuil", "") or "")[-1:],
        "nacionalidad": row.get("nacionalidad", "") or "",
        "direccion": row.get("direccion", "") or "",
        "numero_direccion": row.get("numero_direccion", "") or "",
        "provincia": row.get("provincia", "") or "",
        "departamento": row.get("departamento", "") or "",
        "ciudad": row.get("ciudad", "") or "",
        "donde_firmar": "X",
    }


# ---------------------------------------------------------------------------
# Detección de campos (a partir de los bytes del archivo, sin depender de
# dónde esté guardado: sirve tanto para un upload recién llegado como para
# algo ya leído de MinIO)
# ---------------------------------------------------------------------------

def detectar_campos_pdf(datos_bytes):
    reader = PdfReader(BytesIO(datos_bytes))
    fields = reader.get_fields()
    if not fields:
        return []
    return list(fields.keys())


def detectar_campos_docx(datos_bytes):
    doc = DocxTemplate(BytesIO(datos_bytes))
    variables = doc.get_undeclared_template_variables()
    return sorted(variables)


def detectar_campos(datos_bytes, tipo):
    if tipo == 'pdf':
        return detectar_campos_pdf(datos_bytes)
    return detectar_campos_docx(datos_bytes)


def detectar_campos_de_formulario(formulario):
    """Vuelve a detectar los campos del archivo ya guardado en MinIO (para
    refrescar la pantalla de mapeo). Devuelve [] si el objeto no está."""
    datos_bytes = almacenamiento.leer(formulario["archivo"])
    if datos_bytes is None:
        return []
    return detectar_campos(datos_bytes, formulario["tipo"])


# ---------------------------------------------------------------------------
# Catálogo (CRUD)
# ---------------------------------------------------------------------------

def _row_to_dict(row):
    d = dict(row)
    try:
        d['mapeo'] = json.loads(d.get('mapeo') or '{}')
    except (json.JSONDecodeError, TypeError):
        d['mapeo'] = {}
    d['activo'] = bool(d.get('activo'))
    return d


def listar_formularios(solo_activos=False):
    query = "SELECT * FROM demo_formularios"
    params = {}
    if solo_activos:
        query += " WHERE activo = :activo"
        params["activo"] = True
    query += " ORDER BY categoria, nombre"
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def listar_formularios_agrupados(solo_activos=True):
    """Devuelve un dict ordenado {categoria: [formularios]} para armar la UI del cliente."""
    formularios = listar_formularios(solo_activos=solo_activos)
    agrupados = {}
    for f in formularios:
        categoria = f.get('categoria') or 'General'
        agrupados.setdefault(categoria, []).append(f)
    return agrupados


def obtener_formulario(formulario_id):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM demo_formularios WHERE id = :id"), {"id": formulario_id}
        ).mappings().first()
    return _row_to_dict(row) if row else None


def _mapeo_inicial(campos):
    """Auto-mapea los campos cuyo nombre coincide exactamente con una
    variable del sistema o con un campo personalizado (comodidad para
    PDFs/DOCX que ya usan esa convención); el resto queda en '' para que
    el admin lo mapee a mano."""
    from services import campos_personalizados  # import perezoso: evita ciclo de imports
    vocabulario = set(VARIABLES_SISTEMA.keys())
    vocabulario.update(c['clave'] for c in campos_personalizados.listar_campos_personalizados())
    return {campo: (campo if campo in vocabulario else "") for campo in campos}


def _humanizar_nombre(filename):
    base = os.path.splitext(filename)[0]
    base = base.replace('_', ' ').replace('.', ' ')
    return ' '.join(base.split()) or filename


def _insertar_catalogo(nombre, categoria, tipo, stored_name, nombre_original, mapeo, creado_por):
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO demo_formularios
                (nombre, categoria, tipo, archivo, nombre_original, mapeo, activo, creado_por)
            VALUES
                (:nombre, :categoria, :tipo, :archivo, :nombre_original, :mapeo, :activo, :creado_por)
            RETURNING id
        """), {
            "nombre": nombre,
            "categoria": categoria or "",
            "tipo": tipo,
            "archivo": stored_name,
            "nombre_original": nombre_original,
            "mapeo": json.dumps(mapeo),
            "activo": True,
            "creado_por": creado_por,
        })
        return result.scalar()


def guardar_nuevo_formulario(file_storage, nombre, categoria, creado_por):
    """Sube a MinIO el archivo recibido desde la web y crea el registro en
    el catálogo. Devuelve (id_nuevo, campos_detectados, error)."""
    filename = file_storage.filename or ''
    ext = os.path.splitext(filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return None, [], "Solo se aceptan archivos PDF o DOCX."

    tipo = EXTENSIONES_PERMITIDAS[ext]
    datos_bytes = file_storage.read()

    try:
        campos = detectar_campos(datos_bytes, tipo)
    except Exception as e:
        return None, [], f"No se pudo leer el archivo: {e}"

    stored_name = f"{uuid.uuid4().hex}{ext}"
    try:
        almacenamiento.guardar(stored_name, datos_bytes, content_type=CONTENT_TYPES[tipo])
    except Exception as e:
        return None, [], f"No se pudo guardar el archivo en el almacenamiento: {e}"

    new_id = _insertar_catalogo(
        nombre or os.path.splitext(filename)[0], categoria, tipo,
        stored_name, filename, _mapeo_inicial(campos), creado_por
    )
    return new_id, campos, None


def importar_formulario_desde_disco(path, nombre=None, categoria='', creado_por='import'):
    """Sube a MinIO un PDF/DOCX que está en el disco local (por ejemplo, una
    plantilla que ya venía con el proyecto en datos/formularios/) y lo da de
    alta en el catálogo. Devuelve (id_nuevo, campos, error)."""
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return None, [], f"Extensión no soportada: {ext}"

    tipo = EXTENSIONES_PERMITIDAS[ext]
    with open(path, 'rb') as f:
        datos_bytes = f.read()

    try:
        campos = detectar_campos(datos_bytes, tipo)
    except Exception as e:
        return None, [], str(e)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    almacenamiento.guardar(stored_name, datos_bytes, content_type=CONTENT_TYPES[tipo])

    new_id = _insertar_catalogo(
        nombre or _humanizar_nombre(filename), categoria, tipo,
        stored_name, filename, _mapeo_inicial(campos), creado_por
    )
    return new_id, campos, None


def actualizar_mapeo(formulario_id, mapeo):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE demo_formularios SET mapeo = :mapeo WHERE id = :id"),
            {"mapeo": json.dumps(mapeo), "id": formulario_id}
        )


def actualizar_datos_formulario(formulario_id, nombre, categoria):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE demo_formularios SET nombre = :nombre, categoria = :categoria WHERE id = :id"),
            {"nombre": nombre, "categoria": categoria or "", "id": formulario_id}
        )


def set_activo(formulario_id, activo):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE demo_formularios SET activo = :activo WHERE id = :id"),
            {"activo": activo, "id": formulario_id}
        )


def eliminar_formulario(formulario_id):
    formulario = obtener_formulario(formulario_id)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM demo_cliente_formularios WHERE formulario_id = :id"), {"id": formulario_id}
        )
        conn.execute(
            text("DELETE FROM demo_tramite_formularios WHERE formulario_id = :id"), {"id": formulario_id}
        )
        conn.execute(text("DELETE FROM demo_formularios WHERE id = :id"), {"id": formulario_id})
    if formulario:
        almacenamiento.eliminar(formulario["archivo"])


# ---------------------------------------------------------------------------
# Selección de formularios por cliente
# ---------------------------------------------------------------------------

def obtener_formularios_seleccionados(cliente_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT formulario_id FROM demo_cliente_formularios WHERE cliente_id = :cid"),
            {"cid": cliente_id}
        ).fetchall()
    return {r[0] for r in rows}


def set_formularios_seleccionados(cliente_id, formulario_ids):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM demo_cliente_formularios WHERE cliente_id = :cid"), {"cid": cliente_id}
        )
        for fid in formulario_ids:
            conn.execute(
                text("INSERT INTO demo_cliente_formularios (cliente_id, formulario_id) VALUES (:cid, :fid)"),
                {"cid": cliente_id, "fid": fid}
            )


# ---------------------------------------------------------------------------
# Generación de documentos
# ---------------------------------------------------------------------------

def generar_archivo(formulario, datos_sistema):
    """formulario: dict del catálogo (con 'mapeo' ya parseado a dict).
    Devuelve (nombre_archivo, BytesIO) o None si el archivo no está en MinIO."""
    datos_bytes = almacenamiento.leer(formulario["archivo"])
    if datos_bytes is None:
        return None

    datos_mapeados = {
        campo_detectado: datos_sistema.get(variable, "")
        for campo_detectado, variable in (formulario.get("mapeo") or {}).items()
        if variable
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_nombre = secure_filename(formulario["nombre"]) or f"formulario_{formulario['id']}"

    if formulario["tipo"] == "pdf":
        reader = PdfReader(BytesIO(datos_bytes))
        writer = PdfWriter()
        writer.clone_reader_document_root(reader)
        try:
            writer.set_need_appearances_writer(True)
        except Exception:
            pass
        for page in writer.pages:
            try:
                writer.update_page_form_field_values(page, datos_mapeados)
            except Exception:
                pass
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return f"{base_nombre}_{timestamp}.pdf", output

    doc = DocxTemplate(BytesIO(datos_bytes))
    doc.render(datos_mapeados)
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return f"{base_nombre}_{timestamp}.docx", output
