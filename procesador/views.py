import logging
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponseRedirect

from .forms import ImageUploadForm
from .models import SesionProcesamiento
from .services import (
    guardar_imagen,
    colorear_imagen,
    restaurar_imagen,
    procesar_ambos,
)

logger = logging.getLogger(__name__)

SERVICIOS = {
    'colorear': colorear_imagen,
    'restaurar': restaurar_imagen,
    'ambos': procesar_ambos,
}


def inicio(request):
    """Muestra el formulario de carga de imagen."""
    form = ImageUploadForm()
    return render(request, 'procesador/inicio.html', {
        'form': form,
        'estado': 'vacio',
    })


def procesar(request):
    """Procesa la imagen subida segun el preset seleccionado."""
    if request.method != 'POST':
        return redirect('procesador:inicio')

    form = ImageUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, 'procesador/inicio.html', {
            'form': form,
            'estado': 'vacio',
        })

    imagen = form.cleaned_data['imagen']
    preset = form.cleaned_data['preset']

    # 1. Guardar imagen original
    try:
        nombre_original = guardar_imagen(settings.MEDIA_ROOT / 'subidas', imagen)
    except Exception as e:
        logger.error('Error guardando imagen: %s', e)
        form.add_error('imagen', 'Error al guardar la imagen. Intente de nuevo.')
        return render(request, 'procesador/inicio.html', {
            'form': form,
            'estado': 'vacio',
        })

    # 2. Crear sesion de procesamiento
    sesion = SesionProcesamiento.objects.create(
        imagen_original=nombre_original,
        preset=preset,
        estado='procesando',
    )

    # 3. Leer bytes y procesar
    imagen.seek(0)
    imagen_bytes = imagen.read()

    servicio = SERVICIOS.get(preset)
    if not servicio:
        sesion.estado = 'error'
        sesion.error_mensaje = f'Preset desconocido: {preset}'
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)

    resultado = servicio(imagen_bytes)
    sesion.intentos_api += 1

    # 4. Manejar resultado
    if resultado.exito:
        nombre_resultado = guardar_imagen(
            settings.MEDIA_ROOT / 'resultados',
            type('Archivo', (), {
                'name': f'resultado_{sesion.id}.jpg',
                'content_type': 'image/jpeg',
                'read': lambda: resultado.datos,
                'seek': lambda *a: None,
                'chunks': lambda chunk_size=None: [resultado.datos],
            })()
        )
        sesion.imagen_resultado = nombre_resultado
        sesion.estado = 'completado'
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)

    elif resultado.es_reintento:
        sesion.estado = 'cargando'
        sesion.save()
        # Reintentar despues de espera
        import time
        time.sleep(resultado.espera_segs)
        return procesar_con_reintento(request, sesion, imagen_bytes)

    else:
        sesion.estado = 'error'
        sesion.error_mensaje = resultado.error
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)


def procesar_con_reintento(request, sesion, imagen_bytes):
    """Reintenta el procesamiento despues de un cold start."""
    servicio = SERVICIOS.get(sesion.preset)
    if not servicio:
        sesion.estado = 'error'
        sesion.error_mensaje = f'Preset desconocido: {sesion.preset}'
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)

    resultado = servicio(imagen_bytes)
    sesion.intentos_api += 1

    if resultado.exito:
        nombre_resultado = guardar_imagen(
            settings.MEDIA_ROOT / 'resultados',
            type('Archivo', (), {
                'name': f'resultado_{sesion.id}.jpg',
                'content_type': 'image/jpeg',
                'read': lambda: resultado.datos,
                'seek': lambda *a: None,
                'chunks': lambda chunk_size=None: [resultado.datos],
            })()
        )
        sesion.imagen_resultado = nombre_resultado
        sesion.estado = 'completado'
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)

    elif resultado.es_reintento and sesion.intentos_api < settings.HF_MAX_RETRIES:
        import time
        time.sleep(resultado.espera_segs)
        return procesar_con_reintento(request, sesion, imagen_bytes)

    else:
        sesion.estado = 'error'
        sesion.error_mensaje = resultado.error or 'Maximo de reintentos alcanzado'
        sesion.save()
        return redirect('procesador:resultado', sesion_id=sesion.id)


def resultado(request, sesion_id):
    """Muestra el panel comparativo Antes/Despues."""
    sesion = get_object_or_404(SesionProcesamiento, id=sesion_id)

    if sesion.estado == 'error':
        return render(request, 'procesador/inicio.html', {
            'estado': 'error',
            'error_mensaje': sesion.error_mensaje or 'Error desconocido.',
        })

    if sesion.estado != 'completado':
        return render(request, 'procesador/inicio.html', {
            'estado': 'procesando',
            'preset': sesion.preset,
        })

    imagen_original_url = f'{settings.MEDIA_URL}subidas/{sesion.imagen_original}'
    imagen_resultado_url = f'{settings.MEDIA_URL}resultados/{sesion.imagen_resultado}'

    return render(request, 'procesador/inicio.html', {
        'estado': 'exito',
        'imagen_original_url': imagen_original_url,
        'imagen_resultado_url': imagen_resultado_url,
        'sesion': sesion,
    })
