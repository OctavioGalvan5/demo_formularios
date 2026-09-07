"""
Elimina las tablas demo_users y demo_clientes de la base de datos.
Ejecutar cuando termine la demo para dejar la DB limpia.

    python limpiar_demo.py
"""
from models.database import drop_demo_tables

confirm = input("¿Seguro que querés borrar las tablas demo_users y demo_clientes? (s/N): ").strip().lower()
if confirm == 's':
    drop_demo_tables()
    print("Tablas demo_users y demo_clientes eliminadas.")
else:
    print("Cancelado.")
