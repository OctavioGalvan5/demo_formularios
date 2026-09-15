import re
import unicodedata

from sqlalchemy import text

from models.database import engine
from services.formularios.formularios import VARIABLES_SISTEMA


def _slugify(etiqueta):
    texto = unicodedata.normalize('NFKD', etiqueta or '').encode('ascii', 'ignore').decode('ascii')
    texto = texto.strip().lower()
    texto = re.sub(r'[^a-z0-9]+', '_', texto).strip('_')
    return texto or 'campo'


def listar_campos_personalizados():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, clave, etiqueta FROM demo_variables_personalizadas ORDER BY etiqueta"
        )).mappings().all()
    return [dict(r) for r in rows]


def crear_campo_personalizado(etiqueta, creado_por):
    etiqueta = (etiqueta or '').strip()
    if not etiqueta:
        return None, "El nombre del campo no puede estar vacío."

    base = _slugify(etiqueta)
    with engine.connect() as conn:
        existentes = {
            r[0] for r in conn.execute(text("SELECT clave FROM demo_variables_personalizadas")).fetchall()
        }

    reservadas = set(VARIABLES_SISTEMA.keys()) | existentes
    clave = base
    sufijo = 2
    while clave in reservadas:
        clave = f"{base}_{sufijo}"
        sufijo += 1

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO demo_variables_personalizadas (clave, etiqueta, creado_por)
            VALUES (:clave, :etiqueta, :creado_por)
            RETURNING id
        """), {"clave": clave, "etiqueta": etiqueta, "creado_por": creado_por})
        new_id = result.scalar()

    return new_id, None


def eliminar_campo_personalizado(campo_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_cliente_variables WHERE variable_id = :id"), {"id": campo_id})
        conn.execute(text("DELETE FROM demo_variables_personalizadas WHERE id = :id"), {"id": campo_id})


def obtener_valores_cliente(cliente_id):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT v.clave, cv.valor
            FROM demo_cliente_variables cv
            JOIN demo_variables_personalizadas v ON v.id = cv.variable_id
            WHERE cv.cliente_id = :cid
        """), {"cid": cliente_id}).fetchall()
    return {r[0]: (r[1] or '') for r in rows}


def guardar_valores_cliente(cliente_id, valores_por_clave):
    """valores_por_clave: {clave: valor}. Upsert por cada campo personalizado existente."""
    if not valores_por_clave:
        return
    with engine.begin() as conn:
        for clave, valor in valores_por_clave.items():
            campo = conn.execute(text(
                "SELECT id FROM demo_variables_personalizadas WHERE clave = :clave"
            ), {"clave": clave}).fetchone()
            if not campo:
                continue
            campo_id = campo[0]
            existente = conn.execute(text(
                "SELECT id FROM demo_cliente_variables WHERE cliente_id = :cid AND variable_id = :vid"
            ), {"cid": cliente_id, "vid": campo_id}).fetchone()
            if existente:
                conn.execute(text(
                    "UPDATE demo_cliente_variables SET valor = :valor WHERE id = :id"
                ), {"valor": valor, "id": existente[0]})
            else:
                conn.execute(text(
                    "INSERT INTO demo_cliente_variables (cliente_id, variable_id, valor) VALUES (:cid, :vid, :valor)"
                ), {"cid": cliente_id, "vid": campo_id, "valor": valor})


def vocabulario_completo():
    """VARIABLES_SISTEMA fijo + los campos personalizados, para el desplegable de mapeo."""
    vocabulario = dict(VARIABLES_SISTEMA)
    claves_personalizadas = set()
    for campo in listar_campos_personalizados():
        vocabulario[campo['clave']] = campo['etiqueta']
        claves_personalizadas.add(campo['clave'])
    return vocabulario, claves_personalizadas
