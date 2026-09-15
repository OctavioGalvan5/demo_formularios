from sqlalchemy import text

from models.database import engine


def listar_tramites():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, nombre FROM demo_tipos_tramite ORDER BY nombre"
        )).mappings().all()
    return [dict(r) for r in rows]


def crear_tramite(nombre, creado_por):
    nombre = (nombre or '').strip()
    if not nombre:
        return None, "El nombre del trámite no puede estar vacío."

    with engine.connect() as conn:
        existente = conn.execute(text(
            "SELECT id FROM demo_tipos_tramite WHERE LOWER(nombre) = LOWER(:nombre)"
        ), {"nombre": nombre}).fetchone()
    if existente:
        return None, f'Ya existe un tipo de trámite "{nombre}".'

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO demo_tipos_tramite (nombre, creado_por)
            VALUES (:nombre, :creado_por)
            RETURNING id
        """), {"nombre": nombre, "creado_por": creado_por})
        new_id = result.scalar()

    return new_id, None


def eliminar_tramite(tramite_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_tipos_tramite WHERE id = :id"), {"id": tramite_id})
