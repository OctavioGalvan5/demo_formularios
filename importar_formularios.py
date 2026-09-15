"""
Da de alta en el catálogo (tabla demo_formularios) todos los PDFs/DOCX que
ya estén sueltos en datos/formularios/ — por ejemplo, las plantillas
originales que venían con la demo — sin tener que subirlos uno por uno
desde la pantalla de admin.

Los campos detectados cuyo nombre coincide exactamente con una variable
del sistema (numero_dni, nombre_completo, etc.) se mapean automáticamente;
el resto queda sin mapear para completarlo desde /formularios.

Es seguro correrlo más de una vez: los archivos ya importados se detectan
por nombre original y se saltean.

    python importar_formularios.py
"""
import os
import re

from sqlalchemy import text
from models.database import engine, init_db
from services.formularios import formularios as formularios_service

UUID_BASENAME = re.compile(r'^[0-9a-f]{32}$')

init_db()

with engine.connect() as conn:
    ya_importados = {
        r[0] for r in conn.execute(text("SELECT nombre_original FROM demo_formularios")).fetchall()
    }

candidatos = []
for nombre_archivo in sorted(os.listdir(formularios_service.FORMULARIOS_DIR)):
    base, ext = os.path.splitext(nombre_archivo)
    if ext.lower() not in formularios_service.EXTENSIONES_PERMITIDAS:
        continue
    if UUID_BASENAME.match(base):
        continue  # ya es una copia interna de un formulario subido/importado antes
    if nombre_archivo in ya_importados:
        continue
    candidatos.append(nombre_archivo)

if not candidatos:
    print("No hay formularios nuevos para importar. El catálogo ya está al día.")
else:
    print(f"Importando {len(candidatos)} formulario(s)...\n")
    nuevos = 0
    for nombre_archivo in candidatos:
        ruta = os.path.join(formularios_service.FORMULARIOS_DIR, nombre_archivo)
        new_id, campos, error = formularios_service.importar_formulario_desde_disco(
            ruta, categoria='Importados', creado_por='importar_formularios.py'
        )
        if error:
            print(f"  ERROR con {nombre_archivo}: {error}")
            continue
        formulario = formularios_service.obtener_formulario(new_id)
        mapeados = sum(1 for v in (formulario['mapeo'] or {}).values() if v)
        print(f"  + {nombre_archivo} -> id {new_id} ({mapeados}/{len(campos)} campos auto-mapeados)")
        nuevos += 1

    print(f"\nListo: {nuevos} formulario(s) nuevo(s) en el catálogo.")
    print("Revisá los que quedaron con campos sin mapear desde /formularios en la app.")
