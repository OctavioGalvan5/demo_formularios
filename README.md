# LegalForms — Demo funcional

Demo del módulo de generación automática de formularios legales con IA (OCR de DNI vía GPT-4o + relleno de PDFs/DOCX).

El catálogo de formularios es autogestionable: el admin del estudio sube sus propios PDFs/DOCX desde la app (sin tocar código ni base de datos), mapea los campos detectados contra los datos del cliente, y puede darlos de baja o reemplazarlos en cualquier momento. Ver "Gestión de formularios (admin)" más abajo.

## Stack
- Flask + flask-login
- PostgreSQL (mismo servidor que producción, tablas con prefijo `demo_`)
- MinIO para el almacenamiento de los PDF/DOCX del catálogo
- OpenAI GPT-4o para OCR
- pypdf / docxtpl / xhtml2pdf para generación de documentos

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

El archivo `.env` (ver `.env.example`) necesita:
- `DB_CONNECTION_STRING` — PostgreSQL
- `OPENAI_API_KEY` — para el OCR del DNI
- `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` / `MINIO_SECURE` — dónde se guardan los PDF/DOCX subidos al catálogo. El bucket se crea solo la primera vez que hace falta si no existe.
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
4. En la ficha del cliente, tab **Formularios** — marcar los formularios que aplican (catálogo cargado por el admin).
5. Botón **Guardar y Generar Formularios** → descarga ZIP con PDFs/DOCX rellenados.

## Gestión de formularios (admin)

El menú **Formularios** (solo visible para admins) permite administrar el catálogo sin tocar código:

1. **Subir**: PDF (con campos de formulario/AcroForm) o DOCX (con marcadores `{{variable}}`, vía `docxtpl`).
2. **Mapear**: el sistema detecta automáticamente los campos del archivo (`pypdf` para PDF, `docxtpl` para DOCX) y el admin elige, por cada campo, a qué dato del cliente corresponde (nombre, DNI, CUIL, domicilio, etc. — vocabulario fijo definido en `services/formularios/formularios.py`).
3. **Dar de baja / reactivar**: oculta el formulario de la ficha de clientes sin borrar el historial de documentos ya generados con él.
4. **Eliminar**: borra el registro y el archivo en MinIO definitivamente.

Requisito: el PDF tiene que ser un formulario interactivo (no un escaneo plano) para poder autocompletarse.

## Limpieza

Cuando termine la demo, para eliminar todas las tablas `demo_*` del Postgres:

```bash
python limpiar_demo.py
```

## Estructura

```
DEMO formularios/
├── app.py                    # rutas Flask (auth, home, consultas, usuarios, formularios)
├── crear_usuario.py          # bootstrap del admin
├── limpiar_demo.py           # DROP de las tablas demo
├── requirements.txt
├── .env                      # credenciales (Postgres + OpenAI)
├── models/database.py        # engine SQLAlchemy + init_db (demo_users, demo_clientes, demo_formularios, demo_cliente_formularios)
├── services/consultas/       # OCR GPT-4o del DNI
├── services/formularios/     # catálogo de formularios: detección de campos, mapeo, generación
├── services/almacenamiento.py # guardar/leer/eliminar archivos en MinIO
├── templates/                # base, nav, footer, home, auth, consultas, usuarios, formularios
├── datos/formularios/        # solo plantillas de ejemplo para importar la primera vez (ver importar_formularios.py) — los formularios subidos desde la app viven en MinIO, no acá
└── static/uploads/
```

## Notas

- Las tablas usan el prefijo `demo_` para no chocar con las tablas reales del proyecto original (`users`, `data_clientes`).
- El puerto por defecto es `5002` (el original usa `5001`), por si querés correr ambos en paralelo.
