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
    else:
        _id   = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        _bool = "BOOLEAN DEFAULT 0"

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
                created_by TEXT,
                formularios_reconocimiento_servicios {_bool},
                formularios_jubilacion {_bool},
                formularios_jubilacion_con_24_476 {_bool},
                formularios_jubilacion_con_27_705 {_bool},
                formularios_jubilacion_docente {_bool},
                formularios_jubilacion_serv_diferenciales {_bool},
                formularios_jubilacion_servicio_domestico {_bool},
                formularios_jubilacion_hiv {_bool},
                formularios_jubilacion_minusvalidos_ceguera {_bool},
                formularios_pension_directa_casados {_bool},
                formularios_pension_directa_convivientes {_bool},
                formularios_pension_derivada_casados {_bool},
                formularios_pension_derivada_convivientes {_bool},
                formularios_pension_directa_derivada_hijo_discapacitada {_bool},
                formularios_retiro_transitorio_por_invalidez {_bool},
                formularios_retiro_transitorio_por_invalidez_sdm {_bool},
                formularios_puam {_bool},
                formularios_ucap {_bool},
                formularios_reajuste_de_haberes {_bool},
                formularios_asignacion_fliar_hijo_discapacitado {_bool},
                beneficios_nuevo_convenio_de_honorarios_numerado {_bool},
                juicios_nuevo_convenio_de_honorarios_numerado {_bool},
                convenio_magistrados {_bool},
                convenio_de_gastos_administrativos_judiciales {_bool},
                _2_91_guarda_documental {_bool},
                _6_18_solicitud_prestaciones_previsionales {_bool},
                _6_18_solicitud_prestaciones_previsionales_pension {_bool},
                acta_poder {_bool},
                anexo_baja_puam {_bool},
                anexo_i_ley_27625 {_bool},
                anexo_ii_dec_894_01 {_bool},
                anexo_ii_980_05 {_bool},
                anexo_ii_socioeconomico_24_476 {_bool},
                baja_pnc {_bool},
                carta_poder_srt {_bool},
                ddjj_de_salud_resol_300 {_bool},
                ddjj_ley_17562_6_9 {_bool},
                f_3283_autorizacion_arca {_bool},
                formulario_carta_poder_css {_bool},
                formulario_encuesta_rti {_bool},
                ps_1_75_carta_poder_cap_iii_27705 {_bool},
                ps_5_7_derivacion_aportes_obra_social {_bool},
                ps_5_11_aceptacion_de_la_obra_social {_bool},
                ps_6_292_ddjj_solicitante_sdm {_bool},
                ps_6_293_ddjj_dador_de_trabajo_sdm {_bool},
                ps_6_294_ddjj_renuncia_sdm {_bool},
                ps_6_2_certific_de_servicios {_bool},
                ps_6_3_nivel_de_estudios_rti {_bool},
                ps_6_4_carta_poder {_bool},
                ps_6_8_ddjj_testimonial_acred_servicios {_bool},
                ps_6_13_ddjj_testimonial_dependencia_economica {_bool},
                ps_6_268_certific_de_servicios_ampliatoria {_bool},
                ps_6_273_certific_complementaria_investigadores {_bool},
                ps_6_278_dto_de_cuotas_jubilacion {_bool},
                ps_6_279_dto_de_cuotas_pension {_bool},
                ps_6_284_ddjj_fzas_armadas {_bool},
                ps_6_305_carta_poder {_bool},
                renuncia_condicionada {_bool},
                telegrama_revocando_poder {_bool},
                poder_ar_la_plata {_bool},
                poder_ar_punta_alta {_bool},
                formularios_jubilacion_nueva {_bool},
                formularios_jubilacion_pc_nueva {_bool},
                formularios_jubilacion_moratoria_nueva {_bool},
                formularios_pension_nueva {_bool},
                ps_5_8_obra_social {_bool},
                ps_6_304_carta_poder {_bool}
            )
        """))


def drop_demo_tables():
    """Utilidad para limpiar las tablas demo cuando termine la demo."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_clientes"))
        conn.execute(text("DROP TABLE IF EXISTS demo_users"))
