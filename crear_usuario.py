"""
Ejecutar una sola vez para crear el primer usuario administrador:
    python crear_usuario.py
"""
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from models.database import engine, init_db

init_db()

username = input("Usuario: ").strip()
password = input("Contraseña: ").strip()
fullname = input("Nombre completo: ").strip()

with engine.begin() as conn:
    existing = conn.execute(
        text("SELECT id FROM demo_users WHERE username = :u"), {"u": username}
    ).fetchone()
    if existing:
        print(f"El usuario '{username}' ya existe.")
    else:
        conn.execute(
            text("INSERT INTO demo_users (username, password, fullname, is_admin) "
                 "VALUES (:u, :p, :f, :a)"),
            {"u": username, "p": generate_password_hash(password), "f": fullname, "a": True}
        )
        print(f"Usuario admin '{username}' creado correctamente.")
