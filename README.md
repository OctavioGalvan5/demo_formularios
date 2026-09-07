# LegalForms — Demo funcional

Demo del módulo de generación automática de formularios legales con IA (OCR de DNI vía GPT-4o + relleno de PDFs/DOCX).

## Stack
- Flask + flask-login
- PostgreSQL (mismo servidor que producción, tablas con prefijo `demo_`)
- OpenAI GPT-4o para OCR
- pypdf / docxtpl / xhtml2pdf para generación de documentos

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

El archivo `.env` ya está copiado del proyecto original con:
- `DB_CONNECTION_STRING` — PostgreSQL de producción
- `OPENAI_API_KEY` — para el OCR del DNI
- `SECRET_KEY` — sesión Flask

## Primer arranque

1. Crear el usuario admin (crea también las tablas `demo_users` y `demo_clientes`):
   ```bash
   python crear_usuario.py
   ```

2. Levantar el servidor:
   ```bash
   python app.py
   ```
   Abre en `http://localhost:5002`

## Flujo de la demo

1. Login con el usuario admin creado.
2. Menú **Clientes** → **Cargar por DNI** → subir foto/PDF (frente y dorso).
3. La IA extrae automáticamente nombre, DNI, CUIL, domicilio, etc.
4. En la ficha del cliente, tab **Opciones de trámite** — marcar el trámite; se auto-seleccionan los documentos.
5. Botón **Guardar y Generar Formularios** → descarga ZIP con PDFs/DOCX rellenados.

## Limpieza

Cuando termine la demo, para eliminar las tablas `demo_users` y `demo_clientes` del Postgres:

```bash
python limpiar_demo.py
```

## Estructura

```
DEMO formularios/
├── app.py                 # rutas Flask (auth, home, consultas, usuarios)
├── crear_usuario.py       # bootstrap del admin
├── limpiar_demo.py        # DROP de las tablas demo
├── requirements.txt
├── .env                   # credenciales (Postgres + OpenAI)
├── models/database.py     # engine SQLAlchemy + init_db (demo_users, demo_clientes)
├── services/consultas/    # OCR GPT-4o + mapping formularios
├── templates/             # base, nav, footer, home, auth, consultas, usuarios
├── datos/formularios/     # 40 PDFs + 5 DOCX plantilla (fillables)
└── static/uploads/
```

## Notas

- Las tablas usan el prefijo `demo_` para no chocar con las tablas reales del proyecto original (`users`, `data_clientes`).
- El puerto por defecto es `5002` (el original usa `5001`), por si querés correr ambos en paralelo.
