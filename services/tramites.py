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
        conn.execute(text("DELETE FROM demo_tramite_formularios WHERE tramite_id = :id"), {"id": tramite_id})


def obtener_bundle_de_formulario(formulario_id):
    """IDs de los tipos de trámite en cuyo bundle está este formulario."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT tramite_id FROM demo_tramite_formularios WHERE formulario_id = :fid"
        ), {"fid": formulario_id}).fetchall()
    return [r[0] for r in rows]


def set_bundle_de_formulario(formulario_id, tramite_ids):
    """Reemplaza el conjunto de bundles a los que pertenece un formulario."""
    tramite_ids = [int(t) for t in tramite_ids if str(t).isdigit()]
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM demo_tramite_formularios WHERE formulario_id = :fid"
        ), {"fid": formulario_id})
        for tid in tramite_ids:
            conn.execute(text("""
                INSERT INTO demo_tramite_formularios (tramite_id, formulario_id)
                VALUES (:tid, :fid)
            """), {"tid": tid, "fid": formulario_id})


def obtener_formularios_por_tramite():
    """Dict {tramite_id: [formulario_id, ...]} con todos los bundles armados."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT tramite_id, formulario_id FROM demo_tramite_formularios"
        )).fetchall()
    bundles = {}
    for tramite_id, formulario_id in rows:
        bundles.setdefault(tramite_id, []).append(formulario_id)
    return bundles
