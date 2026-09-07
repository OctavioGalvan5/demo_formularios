import os
import zipfile
from io import BytesIO
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, send_file, make_response)
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text
from pypdf import PdfReader, PdfWriter
from xhtml2pdf import pisa

from models.database import engine, init_db
from services.consultas.consultas import (
    openai_api_extract_data, update_cliente_in_db,
    process_file, FORMULARIOS_MAPPING
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'legalforms-demo-secret-key')

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Iniciá sesión para continuar.'
login_manager.login_message_category = 'warning'


@app.template_filter('fecha')
def filtro_fecha(val, fmt='%d/%m/%Y'):
    if not val:
        return '—'
    if hasattr(val, 'strftime'):
        return val.strftime(fmt)
    try:
        return datetime.strptime(str(val)[:10], '%Y-%m-%d').strftime(fmt)
    except (ValueError, TypeError):
        return str(val)


class User(UserMixin):
    def __init__(self, id, username, fullname='', is_admin=False):
        self.id = id
        self.username = username
        self.fullname = fullname
        self.is_admin = bool(is_admin)


@login_manager.user_loader
def load_user(user_id):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, username, fullname, is_admin FROM demo_users WHERE id = :id"),
            {"id": int(user_id)}
        ).fetchone()
    if row:
        return User(row[0], row[1], row[2] or '', row[3])
    return None


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not getattr(current_user, 'is_admin', False):
            flash('No tenés permiso para acceder a esa sección.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_is_admin():
    return {'is_admin': bool(getattr(current_user, 'is_admin', False))
            if current_user.is_authenticated else False}


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def index():
    return redirect(url_for('home'))


@app.route('/home')
@login_required
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, username, password, fullname, is_admin FROM demo_users WHERE username = :u"),
                {"u": username}
            ).fetchone()
        if row and check_password_hash(row[2], password):
            login_user(User(row[0], row[1], row[3] or '', row[4]))
            return redirect(url_for('home'))
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# USUARIOS (solo admin)
# ---------------------------------------------------------------------------

@app.route('/usuarios')
@admin_required
def usuarios():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, username, fullname, is_admin FROM demo_users ORDER BY id")
        ).fetchall()
    usuarios_list = [
        {'id': r[0], 'username': r[1], 'fullname': r[2] or '', 'is_admin': bool(r[3])}
        for r in rows
    ]
    return render_template('usuarios/usuarios.html', usuarios=usuarios_list)


@app.route('/usuarios/crear', methods=['POST'])
@admin_required
def usuarios_crear():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    fullname = (request.form.get('fullname') or '').strip()
    is_admin_new = bool(request.form.get('is_admin'))

    if not username or not password:
        flash('Usuario y contraseña son obligatorios.', 'danger')
        return redirect(url_for('usuarios'))

    if len(password) < 6:
        flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
        return redirect(url_for('usuarios'))

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM demo_users WHERE username = :u"), {"u": username}
            ).fetchone()
            if existing:
                flash(f'El usuario "{username}" ya existe.', 'danger')
                return redirect(url_for('usuarios'))

            conn.execute(
                text("INSERT INTO demo_users (username, password, fullname, is_admin) "
                     "VALUES (:u, :p, :f, :a)"),
                {"u": username, "p": generate_password_hash(password),
                 "f": fullname, "a": is_admin_new}
            )
        flash(f'Usuario "{username}" creado correctamente.', 'success')
    except Exception as e:
        flash(f'Error al crear el usuario: {e}', 'danger')

    return redirect(url_for('usuarios'))


@app.route('/usuarios/eliminar/<int:id>', methods=['POST'])
@admin_required
def usuarios_eliminar(id):
    if id == current_user.id:
        flash('No podés eliminar tu propio usuario.', 'danger')
        return redirect(url_for('usuarios'))

    try:
        with engine.begin() as conn:
            admins = conn.execute(
                text("SELECT COUNT(*) FROM demo_users WHERE is_admin = :v"), {"v": True}
            ).scalar() or 0
            target = conn.execute(
                text("SELECT is_admin FROM demo_users WHERE id = :id"), {"id": id}
            ).fetchone()
            if target and target[0] and admins <= 1:
                flash('No podés eliminar al único administrador.', 'danger')
                return redirect(url_for('usuarios'))

            conn.execute(text("DELETE FROM demo_users WHERE id = :id"), {"id": id})
        flash('Usuario eliminado.', 'success')
    except Exception as e:
        flash(f'Error al eliminar el usuario: {e}', 'danger')

    return redirect(url_for('usuarios'))


@app.route('/usuarios/reset_password/<int:id>', methods=['POST'])
@admin_required
def usuarios_reset_password(id):
    new_password = request.form.get('password') or ''
    if len(new_password) < 6:
        flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
        return redirect(url_for('usuarios'))

    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE demo_users SET password = :p WHERE id = :id"),
                {"p": generate_password_hash(new_password), "id": id}
            )
        flash('Contraseña actualizada.', 'success')
    except Exception as e:
        flash(f'Error al actualizar la contraseña: {e}', 'danger')

    return redirect(url_for('usuarios'))


@app.route('/usuarios/toggle_admin/<int:id>', methods=['POST'])
@admin_required
def usuarios_toggle_admin(id):
    if id == current_user.id:
        flash('No podés cambiar tu propio rol.', 'danger')
        return redirect(url_for('usuarios'))

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT is_admin FROM demo_users WHERE id = :id"), {"id": id}
            ).fetchone()
            if not row:
                flash('Usuario no encontrado.', 'danger')
                return redirect(url_for('usuarios'))

            if row[0]:
                admins = conn.execute(
                    text("SELECT COUNT(*) FROM demo_users WHERE is_admin = :v"), {"v": True}
                ).scalar() or 0
                if admins <= 1:
                    flash('Debe quedar al menos un administrador.', 'danger')
                    return redirect(url_for('usuarios'))

            nuevo = not bool(row[0])
            conn.execute(
                text("UPDATE demo_users SET is_admin = :a WHERE id = :id"),
                {"a": nuevo, "id": id}
            )
        flash('Rol actualizado.', 'success')
    except Exception as e:
        flash(f'Error al actualizar el rol: {e}', 'danger')

    return redirect(url_for('usuarios'))


# ---------------------------------------------------------------------------
# CONSULTAS (Clientes + generación de formularios con IA)
# ---------------------------------------------------------------------------

@app.route('/consultas')
@login_required
def consultas():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM demo_clientes ORDER BY id DESC"))
        data_clientes = [dict(row._mapping) for row in result]
    return render_template('consultas/consultas.html', data_clientes=data_clientes)


@app.route('/upload_dni', methods=['POST'])
@login_required
def upload_dni():
    documentos = request.files.getlist('documentos')
    if len(documentos) < 1:
        flash("Debe enviar al menos un archivo del DNI.", "danger")
        return redirect(url_for('consultas'))

    processed_files = []
    for file in documentos:
        pages = process_file(file)
        if not pages:
            flash("Error al procesar alguno de los archivos.", "danger")
            return redirect(url_for('consultas'))
        processed_files.extend(pages)

    extracted_data, error = openai_api_extract_data(processed_files)
    if error or not extracted_data:
        flash(f"Error al extraer datos del DNI: {error}", "danger")
        return redirect(url_for('consultas'))

    if not extracted_data.get('date_of_birth'):
        extracted_data['date_of_birth'] = None
    if not extracted_data.get('entry_date'):
        extracted_data['entry_date'] = None

    try:
        with engine.begin() as conn:
            extracted_data['created_by'] = current_user.username
            result = conn.execute(text("""
                INSERT INTO demo_clientes (
                    numero_dni, numero_cuil, numero_celular, nombre, apellido,
                    nombre_completo, nombre_completo_2, sexo, sexo_femenino,
                    sexo_masculino, fecha_de_nacimiento, fecha_de_ingreso,
                    nacionalidad, direccion, numero_direccion, provincia,
                    departamento, ciudad, created_by
                ) VALUES (
                    :dni_number, :cuil_number, :phone_number, :name, :surname,
                    :full_name, :full_name_2, :sexo, :sexo_femenino,
                    :sexo_masculino, :date_of_birth, :entry_date,
                    :nationality, :address, :adress_number, :province,
                    :department, :city, :created_by
                ) RETURNING id
            """), extracted_data)
            new_id = result.scalar()
    except Exception as e:
        flash(f"Error al guardar los datos: {e}", "danger")
        return redirect(url_for('consultas'))

    return redirect(url_for('ver_cliente', id=new_id))


@app.route('/agregar_cliente', methods=['POST'])
@login_required
def agregar_cliente():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO demo_clientes (created_by) VALUES (:created_by) RETURNING id
            """), {"created_by": current_user.username})
            new_id = result.scalar()
    except Exception:
        return redirect(url_for('consultas'))
    return redirect(url_for('ver_cliente', id=new_id))


@app.route('/eliminar_cliente/<int:id>', methods=['POST'])
@login_required
def eliminar_cliente(id):
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM demo_clientes WHERE id = :id"), {"id": id})
    except Exception as e:
        print(f"Error al eliminar: {e}")
    return redirect(url_for('consultas'))


@app.route('/ver_cliente/<int:id>', methods=['GET', 'POST'])
@login_required
def ver_cliente(id):
    if request.method == 'POST':
        accion = request.form.get('accion')
        data = request.form.to_dict()
        update_cliente_in_db(data)

        if accion == 'hacer_formulario':
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM demo_clientes WHERE id = :id"), {"id": id}
                ).mappings().first()

            nombre = row.get("nombre", "") or ""
            apellido = row.get("apellido", "") or ""

            def fmt(d, f):
                if not d:
                    return ""
                if hasattr(d, 'strftime'):
                    return d.strftime(f)
                try:
                    return datetime.strptime(str(d)[:10], '%Y-%m-%d').strftime(f)
                except (ValueError, TypeError):
                    return str(d)

            datos = {
                "nombre": nombre,
                "apellido": apellido,
                "numero_celular": row.get("numero_celular", "") or "",
                "nombre_completo": f"{apellido} {nombre}",
                "nombre_completo_2": f"{nombre} {apellido}",
                "sexo": row.get("sexo", "") or "",
                "sexo_femenino": row.get("sexo_femenino", "") or "",
                "sexo_masculino": row.get("sexo_masculino", "") or "",
                "numero_dni": row.get("numero_dni", "") or "",
                "fecha_de_nacimiento_formato": fmt(row.get("fecha_de_nacimiento"), '%d/%m/%Y'),
                "fecha_de_nacimiento": fmt(row.get("fecha_de_nacimiento"), '%d%m%Y'),
                "fecha_de_nacimiento_dia": fmt(row.get("fecha_de_nacimiento"), '%d'),
                "fecha_de_nacimiento_mes": fmt(row.get("fecha_de_nacimiento"), '%m'),
                "fecha_de_nacimiento_año": fmt(row.get("fecha_de_nacimiento"), '%Y'),
                "fecha_de_ingreso": fmt(row.get("fecha_de_ingreso"), '%d%m%y'),
                "numero_cuil": row.get("numero_cuil", "") or "",
                "cuil_inicio": (row.get("numero_cuil", "") or "")[:2],
                "cuil_fin": (row.get("numero_cuil", "") or "")[-1:],
                "nacionalidad": row.get("nacionalidad", "") or "",
                "direccion": row.get("direccion", "") or "",
                "numero_direccion": row.get("numero_direccion", "") or "",
                "provincia": row.get("provincia", "") or "",
                "departamento": row.get("departamento", "") or "",
                "ciudad": row.get("ciudad", "") or "",
                "donde_firmar": "X",
            }

            archivos_generados = {}
            lista_formularios = []
            formularios_pdf = []
            formularios_docx = []

            for checkbox_name, info in FORMULARIOS_MAPPING.items():
                if request.form.get(checkbox_name):
                    lista_formularios.append(info["label"])
                    if info["path"].endswith(".docx"):
                        formularios_docx.append(info["path"])
                    else:
                        formularios_pdf.append(info["path"])

            for formulario in formularios_pdf:
                if not os.path.exists(formulario):
                    continue
                reader = PdfReader(formulario)
                writer = PdfWriter()
                writer.clone_reader_document_root(reader)
                if len(writer.pages) == 0:
                    continue
                try:
                    writer.update_page_form_field_values(writer.pages[0], datos)
                except Exception:
                    pass
                nombre_formulario = secure_filename(os.path.splitext(os.path.basename(formulario))[0])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = BytesIO()
                writer.write(output)
                output.seek(0)
                archivos_generados[f"{nombre_formulario}_{timestamp}.pdf"] = output

            if formularios_docx:
                from docxtpl import DocxTemplate
                for template_path in formularios_docx:
                    if not os.path.exists(template_path):
                        continue
                    doc = DocxTemplate(template_path)
                    doc.render(datos)
                    output_word = BytesIO()
                    doc.save(output_word)
                    output_word.seek(0)
                    nombre_base = os.path.splitext(os.path.basename(template_path))[0]
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archivos_generados[f"{nombre_base}_{timestamp}.docx"] = output_word

            rendered = render_template('consultas/formularios_impresos.html', filas=lista_formularios)
            pdf_lista_buffer = BytesIO()
            pisa.CreatePDF(rendered, dest=pdf_lista_buffer)
            pdf_lista_buffer.seek(0)
            archivos_generados["lista_formularios.pdf"] = pdf_lista_buffer

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for nombre_archivo, contenido in archivos_generados.items():
                    contenido.seek(0)
                    zf.writestr(nombre_archivo, contenido.read())
            zip_buffer.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_zip = f"formularios_{apellido}_{nombre}_{timestamp}.zip".replace(" ", "_")

            response = make_response(send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=nombre_zip
            ))
            response.set_cookie('fileDownloadReady', '1')
            return response

        flash("Cambios guardados correctamente.", "success")
        return redirect(url_for('ver_cliente', id=id))

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM demo_clientes WHERE id = :id"), {"id": id}
        ).mappings().first()

    if not row:
        flash("Cliente no encontrado.", "danger")
        return redirect(url_for('consultas'))

    data = dict(row)
    for campo in ('fecha_de_nacimiento', 'fecha_de_ingreso'):
        val = data.get(campo)
        if val is None:
            data[campo] = ''
        elif hasattr(val, 'strftime'):
            data[campo] = val.strftime('%Y-%m-%d')
        else:
            data[campo] = str(val)[:10]

    return render_template('consultas/ver_cliente.html', data_cliente=data)


# ---------------------------------------------------------------------------
# INICIO
# ---------------------------------------------------------------------------

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5002)
