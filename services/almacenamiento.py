import os
from io import BytesIO

from minio import Minio
from minio.error import S3Error

MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', '')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', '')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', '')
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'legalforms-formularios')
MINIO_SECURE = os.environ.get('MINIO_SECURE', 'false').strip().lower() == 'true'

_client = None


def _get_client():
    """Cliente MinIO perezoso: se crea (y se asegura el bucket) recién al
    primer uso, no al importar el módulo — así el resto de la app no se cae
    si todavía no se configuraron las variables de entorno de MinIO."""
    global _client
    if _client is None:
        if not MINIO_ENDPOINT:
            raise RuntimeError(
                "MINIO_ENDPOINT no está configurado. Definí MINIO_ENDPOINT, "
                "MINIO_ACCESS_KEY, MINIO_SECRET_KEY y MINIO_BUCKET en el .env."
            )
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
        _client = client
    return _client


def guardar(nombre_objeto, datos_bytes, content_type='application/octet-stream'):
    """Sube (o sobrescribe) un objeto en el bucket."""
    client = _get_client()
    client.put_object(
        MINIO_BUCKET, nombre_objeto, BytesIO(datos_bytes),
        length=len(datos_bytes), content_type=content_type,
    )


def leer(nombre_objeto):
    """Devuelve los bytes del objeto, o None si no existe."""
    client = _get_client()
    response = None
    try:
        response = client.get_object(MINIO_BUCKET, nombre_objeto)
        return response.read()
    except S3Error as e:
        if e.code in ('NoSuchKey', 'NoSuchObject'):
            return None
        raise
    finally:
        if response is not None:
            response.close()
            response.release_conn()


def eliminar(nombre_objeto):
    client = _get_client()
    try:
        client.remove_object(MINIO_BUCKET, nombre_objeto)
    except S3Error:
        pass


def existe(nombre_objeto):
    client = _get_client()
    try:
        client.stat_object(MINIO_BUCKET, nombre_objeto)
        return True
    except S3Error:
        return False
