"""
Elimina las tablas demo_users, demo_clientes, demo_formularios y
demo_cliente_formularios de la base de datos.
Ejecutar cuando termine la demo para dejar la DB limpia.

    python limpiar_demo.py
"""
from models.database import drop_demo_tables

confirm = input("¿Seguro que querés borrar todas las tablas demo_*? (s/N): ").strip().lower()
if confirm == 's':
    drop_demo_tables()
    print("Tablas demo_* eliminadas.")
else:
    print("Cancelado.")
