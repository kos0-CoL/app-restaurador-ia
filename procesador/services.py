import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# --- Gradio Space API configuration ---
# El Serverless Inference API (api-inference.huggingface.co) fue deprecado.
# Ahora usamos la API REST de Gradio directamente sobre Spaces publicos.
#
# Flujo: upload → predict → download
# Cada Space tiene su propio endpoint y parametros.


@dataclass
class ResultadoAPI:
    exito: bool
    datos: bytes = b''
    error: str = ''
    es_reintento: bool = False
    intento_actual: int = 0
    max_intentos: int = 0
    espera_segs: int = 0


def _obtener_token():
    token = settings.HUGGINGFACE_API_TOKEN
    if not token:
        raise ValueError(
            'HUGGINGFACE_API_TOKEN no configurado. '
            'Defina la variable de entorno en .env'
        )
    return token


def _gradio_upload(space_url: str, imagen_bytes: bytes, token: str) -> str:
    """
    Sube una imagen a un Space de Gradio via /gradio_api/upload.
    Retorna el path remoto del archivo en el Space.
    """
    headers = {'Authorization': f'Bearer {token}'}
    upload_url = f'{space_url}/gradio_api/upload'

    respuesta = requests.post(
        url=upload_url,
        headers=headers,
        files={'files': ('imagen.jpg', imagen_bytes, 'image/jpeg')},
        timeout=settings.HF_API_TIMEOUT,
    )

    if respuesta.status_code != 200:
        raise RuntimeError(
            f'Error subiendo imagen al Space: {respuesta.status_code} - '
            f'{respuesta.text[:200]}'
        )

    file_paths = respuesta.json()
    return file_paths[0] if isinstance(file_paths, list) else file_paths


def _gradio_predict(
    space_url: str,
    api_name: str,
    file_path: str,
    token: str,
    extra_params: list | None = None,
) -> dict:
    """
    Llama al endpoint /gradio_api/call/{api_name} de un Space de Gradio.
    Retorna el dict con la info del resultado (url, path, etc).
    """
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    predict_url = f'{space_url}/gradio_api/call/{api_name}'

    data = [{'path': file_path, 'meta': {}}]
    if extra_params:
        data.extend(extra_params)

    payload = {'data': data, 'fn_index': 0}

    respuesta = requests.post(
        url=predict_url,
        headers=headers,
        json=payload,
        timeout=settings.HF_API_TIMEOUT,
    )

    if respuesta.status_code == 503:
        raise ConnectionError('Space en modo cold start (503)')
    if respuesta.status_code != 200:
        raise RuntimeError(
            f'Error en predict ({api_name}): {respuesta.status_code} - '
            f'{respuesta.text[:300]}'
        )

    event_id = respuesta.json().get('event_id')
    if not event_id:
        raise RuntimeError('No se recibio event_id del Space')

    # Obtener resultado via SSE
    result_url = f'{space_url}/gradio_api/call/{api_name}/{event_id}'
    resultado = requests.get(
        url=result_url,
        headers={'Authorization': f'Bearer {token}'},
        timeout=settings.HF_API_TIMEOUT,
    )

    if resultado.status_code != 200:
        raise RuntimeError(
            f'Error obteniendo resultado: {resultado.status_code}'
        )

    # Parsear respuesta SSE: buscar la linea "data: {...}" con el resultado
    for linea in resultado.text.split('\n'):
        if linea.startswith('data:'):
            data_str = linea[5:].strip()
            if data_str and data_str != 'null':
                data_parsed = json.loads(data_str)
                if isinstance(data_parsed, list) and len(data_parsed) >= 1:
                    return data_parsed[0]

    raise RuntimeError('No se encontro resultado en la respuesta del Space')


def _gradio_download(result_info: dict, token: str) -> bytes:
    """
    Descarga el resultado de un Space de Gradio.
    result_info puede tener 'url' o 'path'.
    """
    # Intentar descargar via URL primero
    url = result_info.get('url')
    if url:
        headers = {'Authorization': f'Bearer {token}'}
        respuesta = requests.get(url, headers=headers, timeout=settings.HF_API_TIMEOUT)
        if respuesta.status_code == 200:
            return respuesta.content
        raise RuntimeError(
            f'Error descargando resultado: {respuesta.status_code}'
        )

    raise RuntimeError('No se pudo descargar el resultado del Space')


def llamar_api_hf(imagen_bytes: bytes, modelo_id: str) -> ResultadoAPI:
    """
    Envía una imagen a un Space de Gradio para procesamiento con IA.

    Flujo: upload → predict → download
    Reintenta automaticamente en caso de cold start (503) o errores de conexion.
    """
    token = _obtener_token()
    space_url = settings.GRADIO_SPACES.get(modelo_id)

    if not space_url:
        return ResultadoAPI(
            exito=False,
            error=f'Modelo desconocido: {modelo_id}',
        )

    max_intentos = settings.HF_MAX_RETRIES
    base_espera = settings.HF_RETRY_BASE_WAIT

    # Configuracion de la llamada por modelo
    api_configs = {
        'colorear': {
            'api_name': 'predict',
            'extra_params': None,
        },
        'restaurar': {
            'api_name': 'inference',
            'extra_params': [True, True, True, 2, 0.5],
        },
    }

    config = api_configs.get(modelo_id)
    if not config:
        return ResultadoAPI(
            exito=False,
            error=f'Configuracion no encontrada para modelo: {modelo_id}',
        )

    for intento in range(1, max_intentos + 1):
        try:
            logger.info(
                'Gradio Space call: modelo=%s space=%s intento=%d/%d',
                modelo_id, space_url, intento, max_intentos,
            )

            # Paso 1: Subir imagen al Space
            logger.info('Upload: modelo=%s bytes=%d', modelo_id, len(imagen_bytes))
            file_path = _gradio_upload(space_url, imagen_bytes, token)
            logger.info('Upload OK: path=%s', file_path)

            # Paso 2: Llamar a predict
            logger.info('Predict: modelo=%s api=%s', modelo_id, config['api_name'])
            result_info = _gradio_predict(
                space_url=space_url,
                api_name=config['api_name'],
                file_path=file_path,
                token=token,
                extra_params=config['extra_params'],
            )
            logger.info('Predict OK: resultado=%s', str(result_info)[:100])

            # Paso 3: Descargar resultado
            logger.info('Download: modelo=%s', modelo_id)
            resultado_bytes = _gradio_download(result_info, token)
            logger.info(
                'Download OK: modelo=%s bytes=%d',
                modelo_id, len(resultado_bytes),
            )

            return ResultadoAPI(exito=True, datos=resultado_bytes)

        except ConnectionError:
            if intento < max_intentos:
                logger.warning(
                    'Space cold start (503): modelo=%s reintento=%d/%d espera=%ds',
                    modelo_id, intento, max_intentos, base_espera,
                )
                time.sleep(base_espera)
                continue
            return ResultadoAPI(
                exito=False,
                error=(
                    'La IA se esta encendiendo en los '
                    'servidores gratuitos. Por favor, '
                    'reintenta en un momento.'
                ),
            )

        except requests.exceptions.ReadTimeout:
            return ResultadoAPI(
                exito=False,
                error=(
                    'El procesamiento excedio el tiempo limite. '
                    'Intente con una imagen mas pequena.'
                ),
            )

        except requests.exceptions.ConnectionError as e:
            if intento < max_intentos:
                logger.warning(
                    'Connection error: modelo=%s reintento=%d/%d: %s',
                    modelo_id, intento, max_intentos, str(e)[:100],
                )
                time.sleep(base_espera)
                continue
            return ResultadoAPI(
                exito=False,
                error=(
                    'No se pudo conectar con el servicio de IA. '
                    'Verifique su conexion a internet.'
                ),
            )

        except RuntimeError as e:
            error_msg = str(e)
            logger.error('Runtime error: modelo=%s error=%s', modelo_id, error_msg)
            if '503' in error_msg or 'cold start' in error_msg.lower():
                if intento < max_intentos:
                    logger.warning(
                        'Space cold start: modelo=%s reintento=%d/%d',
                        modelo_id, intento, max_intentos,
                    )
                    time.sleep(base_espera)
                    continue
                return ResultadoAPI(
                    exito=False,
                    error=(
                        'La IA se esta encendiendo en los '
                        'servidores gratuitos. Por favor, '
                        'reintenta en un momento.'
                    ),
                )
            return ResultadoAPI(exito=False, error=error_msg)

        except Exception as e:
            logger.error(
                'Error inesperado: modelo=%s tipo=%s error=%s',
                modelo_id, type(e).__name__, str(e)[:200],
            )
            return ResultadoAPI(
                exito=False,
                error=f'Error inesperado: {type(e).__name__}: {str(e)[:200]}',
            )

    return ResultadoAPI(
        exito=False,
        error='Maximo de reintentos alcanzado',
    )


def guardar_imagen(directorio: Path, archivo) -> str:
    """
    Guarda un archivo UploadedFile en el directorio indicado.
    Genera un nombre unico con UUID corto + timestamp.
    Retorna el nombre de archivo generado.
    """
    extension = Path(archivo.name).suffix or '.jpg'
    uuid_corto = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f'{uuid_corto}_{timestamp}{extension}'
    ruta = directorio / nombre

    directorio.mkdir(parents=True, exist_ok=True)

    with open(ruta, 'wb') as f:
        for chunk in archivo.chunks():
            f.write(chunk)

    logger.info('Imagen guardada: %s (%s)', ruta, archivo.content_type)
    return nombre


def colorear_imagen(imagen_bytes: bytes) -> ResultadoAPI:
    """Envia imagen para colorear via DeOldify Space."""
    return llamar_api_hf(imagen_bytes, 'colorear')


def restaurar_imagen(imagen_bytes: bytes) -> ResultadoAPI:
    """Envia imagen para restaurar via CodeFormer Space."""
    return llamar_api_hf(imagen_bytes, 'restaurar')


def procesar_ambos(imagen_bytes: bytes) -> ResultadoAPI:
    """Cadena restaurar -> colorear en una sola operacion."""
    resultado_restauracion = restaurar_imagen(imagen_bytes)
    if not resultado_restauracion.exito:
        return resultado_restauracion
    return llamar_api_hf(resultado_restauracion.datos, 'colorear')
