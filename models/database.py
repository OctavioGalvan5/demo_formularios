import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'demo.db')

_conn_str = os.environ.get('DB_CONNECTION_STRING', '')
_use_postgres = _conn_str.startswith('postgresql')

if _use_postgres:
    engine = create_engine(_conn_str, pool_pre_ping=True)
else:
    engine = create_engine(
        f'sqlite:///{os.path.abspath(DB_PATH)}',
        pool_pre_ping=True,
        connect_args={"check_same_thread": False}
    )


def init_db():
    if _use_postgres:
        _id   = "id BIGSERIAL PRIMARY KEY"
        _bool = "BOOLEAN DEFAULT FALSE"
        _ts   = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        _fk   = "BIGINT"
    else:
        _id   = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        _bool = "BOOLEAN DEFAULT 0"
        _ts   = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        _fk   = "INTEGER"

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_users (
                {_id},
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                fullname TEXT DEFAULT '',
                is_admin {_bool}
            )
        """))

        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_clientes (
                {_id},
                numero_dni TEXT,
                numero_cuil TEXT,
                numero_celular TEXT,
                nombre TEXT,
                apellido TEXT,
                nombre_completo TEXT,
                nombre_completo_2 TEXT,
                sexo TEXT,
                sexo_femenino TEXT,
                sexo_masculino TEXT,
                fecha_de_nacimiento DATE,
                fecha_de_ingreso DATE,
                nacionalidad TEXT,
                direccion TEXT,
                numero_direccion TEXT,
                provincia TEXT,
                departamento TEXT,
                ciudad TEXT,
                created_by TEXT
            )
        """))

        # Catálogo de formularios (PDF/DOCX) gestionable por el admin del estudio.
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_formularios (
                {_id},
                nombre TEXT NOT NULL,
                categoria TEXT DEFAULT '',
                tipo TEXT NOT NULL,
                archivo TEXT NOT NULL,
                nombre_original TEXT DEFAULT '',
                mapeo TEXT DEFAULT '{{}}',
                activo {_bool.replace('FALSE', 'TRUE').replace('0', '1')},
                creado_por TEXT,
                fecha_alta {_ts}
            )
        """))

        # Selección de formularios por cliente (reemplaza las columnas booleanas fijas).
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_cliente_formularios (
                {_id},
                cliente_id {_fk} NOT NULL,
                formulario_id {_fk} NOT NULL,
                UNIQUE(cliente_id, formulario_id)
            )
        """))

        # Variables personalizadas: el admin puede sumar campos propios al
        # vocabulario fijo (VARIABLES_SISTEMA) sin tocar código.
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_variables_personalizadas (
                {_id},
                clave TEXT NOT NULL UNIQUE,
                etiqueta TEXT NOT NULL,
                creado_por TEXT,
                fecha_alta {_ts}
            )
        """))

        # Valor de cada variable personalizada por cliente.
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_cliente_variables (
                {_id},
                cliente_id {_fk} NOT NULL,
                variable_id {_fk} NOT NULL,
                valor TEXT DEFAULT '',
                UNIQUE(cliente_id, variable_id)
            )
        """))

        # Lista controlada de tipos de trámite (Jubilación, Pensión, etc.)
        # que el admin gestiona, en vez de escribir la categoría a mano.
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS demo_tipos_tramite (
                {_id},
                nombre TEXT NOT NULL UNIQUE,
                creado_por TEXT,
                fecha_alta {_ts}
            )
        """))

def drop_demo_tables():
    """Utilidad para limpiar las tablas demo cuando termine la demo."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_cliente_variables"))
        conn.execute(text("DROP TABLE IF EXISTS demo_variables_personalizadas"))
        conn.execute(text("DROP TABLE IF EXISTS demo_tipos_tramite"))
        conn.execute(text("DROP TABLE IF EXISTS demo_cliente_formularios"))
        conn.execute(text("DROP TABLE IF EXISTS demo_formularios"))
        conn.execute(text("DROP TABLE IF EXISTS demo_clientes"))
        conn.execute(text("DROP TABLE IF EXISTS demo_users"))
