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
from sqlalchemy import text
from xhtml2pdf import pisa

from models.database import engine, init_db
from services.consultas.consultas import (
    openai_api_extract_data, update_cliente_in_db, process_file
)
from services.formularios import formularios as formularios_service
from services import campos_personalizados as campos_service
from services import tramites as tramites_service

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

        valores_personalizados = {
            campo['clave']: request.form.get(f"campo_personalizado__{campo['clave']}", '')
            for campo in campos_service.listar_campos_personalizados()
        }
        campos_service.guardar_valores_cliente(id, valores_personalizados)

        formulario_ids = [int(v) for v in request.form.getlist('formularios') if v.isdigit()]
        formularios_service.set_formularios_seleccionados(id, formulario_ids)

        if accion == 'hacer_formulario':
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM demo_clientes WHERE id = :id"), {"id": id}
                ).mappings().first()

            nombre = row.get("nombre", "") or ""
            apellido = row.get("apellido", "") or ""
            datos = formularios_service.build_datos_cliente(row)
            datos.update(campos_service.obtener_valores_cliente(id))

            catalogo_activo = {f["id"]: f for f in formularios_service.listar_formularios(solo_activos=True)}
            seleccionados = [catalogo_activo[fid] for fid in formulario_ids if fid in catalogo_activo]

            archivos_generados = {}
            lista_formularios = []

            for formulario in seleccionados:
                resultado = formularios_service.generar_archivo(formulario, datos)
                if not resultado:
                    continue
                nombre_archivo, contenido = resultado
                archivos_generados[nombre_archivo] = contenido
                lista_formularios.append(formulario["nombre"])

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

    formularios_agrupados = formularios_service.listar_formularios_agrupados(solo_activos=True)
    formularios_seleccionados = formularios_service.obtener_formularios_seleccionados(id)
    campos_personalizados = campos_service.listar_campos_personalizados()
    valores_personalizados = campos_service.obtener_valores_cliente(id)

    return render_template(
        'consultas/ver_cliente.html',
        data_cliente=data,
        formularios_agrupados=formularios_agrupados,
        formularios_seleccionados=formularios_seleccionados,
        campos_personalizados=campos_personalizados,
        valores_personalizados=valores_personalizados,
    )


# ---------------------------------------------------------------------------
# FORMULARIOS (catálogo gestionable por el admin del estudio)
# ---------------------------------------------------------------------------

@app.route('/formularios')
@admin_required
def formularios():
    lista = formularios_service.listar_formularios()
    tramites = tramites_service.listar_tramites()
    return render_template('formularios/formularios.html', formularios=lista, tramites=tramites)


@app.route('/formularios/subir', methods=['POST'])
@admin_required
def formularios_subir():
    archivo = request.files.get('archivo')
    nombre = (request.form.get('nombre') or '').strip()
    categoria = (request.form.get('categoria') or '').strip()

    if not archivo or not archivo.filename:
        flash('Tenés que seleccionar un archivo PDF o DOCX.', 'danger')
        return redirect(url_for('formularios'))

    new_id, campos, error = formularios_service.guardar_nuevo_formulario(
        archivo, nombre, categoria, current_user.username
    )
    if error:
        flash(error, 'danger')
        return redirect(url_for('formularios'))

    if not campos:
        flash(
            'El formulario se subió, pero no se detectaron campos rellenables. '
            'Revisá que el PDF tenga un formulario (AcroForm) o que el DOCX use marcadores {{variable}}.',
            'warning'
        )
    else:
        flash(f'Formulario subido. Se detectaron {len(campos)} campo(s) — ahora mapealos.', 'success')

    return redirect(url_for('formularios_mapear', id=new_id))


@app.route('/formularios/<int:id>/mapear', methods=['GET', 'POST'])
@admin_required
def formularios_mapear(id):
    formulario = formularios_service.obtener_formulario(id)
    if not formulario:
        flash('Formulario no encontrado.', 'danger')
        return redirect(url_for('formularios'))

    if request.method == 'POST':
        nombre = (request.form.get('nombre') or '').strip() or formulario['nombre']
        categoria = (request.form.get('categoria') or '').strip()
        formularios_service.actualizar_datos_formulario(id, nombre, categoria)

        nuevo_mapeo = {}
        for campo in formulario['mapeo'].keys():
            variable = request.form.get(f'campo__{campo}', '')
            if variable:
                nuevo_mapeo[campo] = variable
        formularios_service.actualizar_mapeo(id, nuevo_mapeo)

        flash('Mapeo guardado correctamente.', 'success')
        return redirect(url_for('formularios'))

    try:
        campos_detectados = formularios_service.detectar_campos_de_formulario(formulario)
        if not campos_detectados:
            campos_detectados = list(formulario['mapeo'].keys())
    except Exception:
        campos_detectados = list(formulario['mapeo'].keys())

    mapeo_actual = formulario['mapeo']
    campos = [(c, mapeo_actual.get(c, '')) for c in campos_detectados]
    vocabulario, claves_personalizadas = campos_service.vocabulario_completo()
    tramites = tramites_service.listar_tramites()

    return render_template(
        'formularios/mapear.html',
        formulario=formulario,
        campos=campos,
        variables_sistema=vocabulario,
        variables_personalizadas=claves_personalizadas,
        tramites=tramites,
    )


@app.route('/formularios/<int:id>/toggle_activo', methods=['POST'])
@admin_required
def formularios_toggle_activo(id):
    formulario = formularios_service.obtener_formulario(id)
    if not formulario:
        flash('Formulario no encontrado.', 'danger')
        return redirect(url_for('formularios'))
    formularios_service.set_activo(id, not formulario['activo'])
    flash('Formulario reactivado.' if not formulario['activo'] else 'Formulario dado de baja.', 'success')
    return redirect(url_for('formularios'))


@app.route('/formularios/<int:id>/eliminar', methods=['POST'])
@admin_required
def formularios_eliminar(id):
    formularios_service.eliminar_formulario(id)
    flash('Formulario eliminado.', 'success')
    return redirect(url_for('formularios'))


# ---------------------------------------------------------------------------
# CAMPOS PERSONALIZADOS (vocabulario extra para el mapeo, solo admin)
# ---------------------------------------------------------------------------

@app.route('/campos')
@admin_required
def campos():
    lista = campos_service.listar_campos_personalizados()
    return render_template(
        'campos/campos.html',
        campos=lista,
        variables_sistema=formularios_service.VARIABLES_SISTEMA,
    )


@app.route('/campos/crear', methods=['POST'])
@admin_required
def campos_crear():
    etiqueta = request.form.get('etiqueta', '')
    new_id, error = campos_service.crear_campo_personalizado(etiqueta, current_user.username)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Campo "{etiqueta}" creado. Ya está disponible en Datos Personales y en el mapeo de formularios.', 'success')
    return redirect(url_for('campos'))


@app.route('/campos/<int:id>/eliminar', methods=['POST'])
@admin_required
def campos_eliminar(id):
    campos_service.eliminar_campo_personalizado(id)
    flash('Campo eliminado.', 'success')
    return redirect(url_for('campos'))


# ---------------------------------------------------------------------------
# TIPOS DE TRÁMITE (lista controlada para categorizar formularios, solo admin)
# ---------------------------------------------------------------------------

@app.route('/tramites')
@admin_required
def tramites():
    lista = tramites_service.listar_tramites()
    return render_template('tramites/tramites.html', tramites=lista)


@app.route('/tramites/crear', methods=['POST'])
@admin_required
def tramites_crear():
    nombre = request.form.get('nombre', '')
    new_id, error = tramites_service.crear_tramite(nombre, current_user.username)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Tipo de trámite "{nombre}" creado.', 'success')
    return redirect(url_for('tramites'))


@app.route('/tramites/<int:id>/eliminar', methods=['POST'])
@admin_required
def tramites_eliminar(id):
    tramites_service.eliminar_tramite(id)
    flash('Tipo de trámite eliminado.', 'success')
    return redirect(url_for('tramites'))


# ---------------------------------------------------------------------------
# INICIO
# ---------------------------------------------------------------------------

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5002)
