# Implementation Plan: Restauración y Coloreado de Imágenes con IA

**Branch**: `001-image-restore-colorize` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-image-restore-colorize/spec.md`

## Summary

Aplicación web Django que permite a usuarios anónimos subir fotografías
viejas, aplicar coloreado (DeOldify), restauración (CodeFormer) o ambos
mediante la API Serverless de Hugging Face, y ver/descargar un panel
comparativo Antes/Después. El MVP soporta 10 usuarios concurrentes,
sin autenticación, con limpieza automática de archivos a las 24 horas.

## Technical Context

**Language/Version**: Python 3.10+ / Django 5.x

**Primary Dependencies**: Django (Forms, File Handling), Pillow
(imagen), requests (HTTP síncrono a Hugging Face)

**Storage**: Archivos en disco (`media/subidas/`, `media/resultados/`);
base de datos SQLite para registro de sesiones de procesamiento

**Testing**: Django test client + pytest (unitarias de forms/services)

**Target Platform**: Linux server, navegadores de escritorio
(Chrome, Firefox, Safari)

**Project Type**: Web application (monolithic Django)

**Performance Goals**: <60s por imagen incluyendo cold start,
10 usuarios concurrentes sin degradación

**Constraints**: Sin frameworks JS complejos, Tailwind CSS vía CDN,
FBVs exclusivamente, cero credenciales hardcoded

**Scale/Scope**: 10 usuarios concurrentes, imágenes hasta 10 MB,
3 presets (Colorear, Restaurar, Ambos)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How Addressed |
|-----------|--------|---------------|
| I. Arquitectura Django (FBV) | ✅ Compliant | Todas las rutas son FBVs, Django Forms en forms.py, enrutamiento app-level |
| II. Manejo de Archivos | ✅ Compliant | MEDIA_ROOT/MEDIA_URL explícitos, media/subidas/ + media/resultados/, UUID naming |
| III. Integración con IA | ✅ Compliant | requests síncrono, headers Bearer + octet-stream, payload binario puro |
| IV. Seguridad y Config | ✅ Compliant | Token por os.getenv(), manejo 503/401/timeout, .gitignore |
| V. Frontend y UX | ✅ Compliant | Tailwind CDN, inicio.html única plantilla, 3 estados visuales |

## Project Structure

```text
app-restaurador-ia/
├── manage.py
├── requirements.txt                  # ya existe
├── .env                              # HUGGINGFACE_API_TOKEN (no versionado)
├── .gitignore
│
├── config/                           # Proyecto Django core
│   ├── __init__.py
│   ├── settings.py                   # MEDIA_ROOT, MEDIA_URL, configuración
│   ├── urls.py                       # Incluye urls de la app
│   └── wsgi.py
│
├── procesador/                       # App principal
│   ├── __init__.py
│   ├── urls.py                       # Rutas: /, /procesar/, /resultado/<id>/
│   ├── forms.py                      # ImageUploadForm (imagen + preset)
│   ├── views.py                      # FBVs: inicio, procesar, resultado
│   ├── services.py                   # Lógica de IA: llamar_api_hf(), cold_start_handler()
│   └── models.py                     # Registro de sesiones de procesamiento
│
├── templates/
│   └── procesador/
│       └── inicio.html               # SPA simulada con Tailwind CDN
│
├── media/                            # Directorio raíz de archivos
│   ├── subidas/                      # Imágenes originales del usuario
│   └── resultados/                   # Imágenes procesadas por IA
│
└── tests/
    ├── __init__.py
    ├── test_forms.py                  # Validación de ImageUploadForm
    ├── test_views.py                  # Tests de las FBVs
    └── test_services.py              # Tests de la capa de servicios IA
```

**Structure Decision**: Estructura monolítica Django con una app
(`procesador`) que encapsula toda la lógica de negocio. El directorio
`config/` maneja la configuración del proyecto Django. Separación
clara entre vistas (orquestadores), forms (validación), services
(lógica de IA) y models (persistencia).

## Data Flow Completo

### Flujo 1: Carga y Procesamiento de Imagen

```
USUARIO                    DJANGO                       HUGGING FACE
  │                           │                              │
  │  1. POST /procesar/       │                              │
  │  (imagen + preset)        │                              │
  │──────────────────────────>│                              │
  │                           │                              │
  │  2. ImageUploadForm        │                              │
  │     validates:             │                              │
  │     - formato (JPEG/PNG)   │                              │
  │     - tamaño (<=10MB)      │                              │
  │                           │                              │
  │  3. Guarda en media/       │                              │
  │     subidas/ con UUID      │                              │
  │     nombre: abc123.jpg     │                              │
  │                           │                              │
  │  4. Lee bytes en memoria   │                              │
  │     imagen_bytes =          │                              │
  │     archivo.read()          │                              │
  │                           │                              │
  │  5. POST request           │                              │
  │     Authorization: Bearer  │                              │
  │     Content-Type: app/     │                              │
  │     octet-stream           │──────────────────────────────>│
  │     body: imagen_bytes     │                              │
  │                           │                              │
  │  6. Respuesta              │                              │
  │     200 → bytes resultado  │<─────────────────────────────│
  │     503 → cold start       │                              │
  │     401 → token inválido   │                              │
  │     timeout → abortar      │                              │
  │                           │                              │
  │  7. Guarda resultado       │                              │
  │     media/resultados/      │                              │
  │     def456_20260705.jpg    │                              │
  │                           │                              │
  │  8. Registro en DB          │                              │
  │     SesiónProcesamiento:   │                              │
  │     estado="completado"    │                              │
  │                           │                              │
  │  9. Redirect a              │                              │
  │     /resultado/<id>/       │                              │
  │<──────────────────────────│                              │
  │                           │                              │
  │ 10. Renderiza panel         │                              │
  │     comparativo A/D        │                              │
  │     con URLs de archivos   │                              │
  │<──────────────────────────│                              │
```

### Flujo 2: Manejo de Error 503 (Cold Start) — Estrategia Detallada

```
USUARIO                    DJANGO                       HUGGING FACE
  │                           │                              │
  │  1. POST /procesar/       │                              │
  │──────────────────────────>│                              │
  │                           │                              │
  │  2. Primer intento         │   POST request              │
  │     imagen_bytes           │──────────────────────────────>│
  │                           │                              │
  │  3. Respuesta 503          │   503 Service Unavailable   │
  │     (Model Loading)        │<─────────────────────────────│
  │                           │                              │
  │  4. Actualiza DB:          │                              │
  │     estado="cargando"      │                              │
  │                           │                              │
  │  5. Muestra al usuario:    │                              │
  │     "El modelo está        │                              │
  │      cargando...           │                              │
  │      Intento 1/3"          │                              │
  │<──────────────────────────│                              │
  │                           │                              │
  │  6. Espera 5 segundos      │                              │
  │     (backoff exponencial)  │                              │
  │                           │                              │
  │  7. Segundo intento        │   POST request              │
  │                           │──────────────────────────────>│
  │                           │                              │
  │  8. Respuesta 200          │   Imagen procesada           │
  │     (éxito)                │<─────────────────────────────│
  │                           │                              │
  │  9. Guarda resultado,      │                              │
  │     actualiza DB:          │                              │
  │     estado="completado"    │                              │
  │                           │                              │
  │ 10. Redirect a resultado   │                              │
  │<──────────────────────────│                              │
```

### Flujo 3: Timeout — Estrategia de Abort

```
DJANGO                          HUGGING FACE
  │                                  │
  │  POST request                    │
  │  (timeout=60 segundos)           │
  │─────────────────────────────────>│
  │                                  │
  │  ... 60 segundos transcurren ... │
  │                                  │
  │  requests.exceptions.            │
  │  ReadTimeout                     │
  │<─────────────────────────────────│
  │                                  │
  │  1. Actualiza DB:                │
  │     estado="error"               │
  │     error_msg="Timeout..."       │
  │                                  │
  │  2. Elimina archivos temporales  │
  │                                  │
  │  3. Renderiza mensaje de error   │
  │     con botón de reintentar      │
  │<──── (usuario ve pantalla) ──────│
```

## Error Strategy: 503 Cold Start

### Algoritmo de Reintentos

```python
MAX_INTENTOS = 3
BASE_ESPERA = 5  # segundos

def llamar_api_hf(imagen_bytes, preset):
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            respuesta = requests.post(
                url=OBTENER_URL_MODEL(preset),
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/octet-stream",
                },
                data=imagen_bytes,
                timeout=60,
            )

            if respuesta.status_code == 200:
                return Exito(respuesta.content)

            if respuesta.status_code == 503:
                if intento < MAX_INTENTOS:
                    espera = BASE_ESPERA * (2 ** (intento - 1))  # 5s, 10s, 20s
                    return Reintentando(intento, MAX_INTENTOS, espera)
                else:
                    return Error("El modelo no pudo cargar tras 3 intentos")

            if respuesta.status_code == 401:
                return Error("Token de Hugging Face inválido. "
                             "Verificar la configuración del servidor.")

            return Error(f"Error inesperado: {respuesta.status_code}")

        except requests.exceptions.ReadTimeout:
            return Error("El procesamiento excedió el tiempo límite. "
                         "Intente con una imagen más pequeña.")
        except requests.exceptions.ConnectionError:
            return Error("No se pudo conectar con el servicio de IA. "
                         "Verifique su conexión a internet.")

    return Error("Máximo de reintentos alcanzado")
```

### Estados de la Sesión de Procesamiento

| Estado | Descripción | Transiciones |
|--------|------------|--------------|
| `pendiente` | Imagen subida, procesamiento no iniciado | → `procesando` |
| `procesando` | Llamada a API en curso | → `completado`, `error`, `cargando` |
| `cargando` | 503 recibido, esperando reintento | → `procesando` (reintento), `error` (max reintentos) |
| `completado` | Imagen procesada y guardada | → (estado final) |
| `error` | Fallo irrecuperable | → (estado final) |

### Mensajes de Error al Usuario

| Error | Mensaje Visible | Acción Sugerida |
|-------|----------------|-----------------|
| 503 (1er intento) | "El modelo de IA está cargando. Espere unos segundos..." | Espera automática |
| 503 (max reintentos) | "El servicio de IA no está disponible temporalmente." | Botón Reintentar |
| 401 | "Error de configuración del servicio." | Contactar administrador |
| Timeout | "El procesamiento tardó demasiado. Imagen muy grande o servicio lento." | Reintentar o imagen más pequeña |
| Conexión | "No se pudo conectar con el servicio de IA." | Verificar conexión a internet |
| Formato inválido | "Formato de imagen no soportado. Use JPEG o PNG." | Subir otro archivo |
| Tamaño excesivo | "La imagen supera los 10 MB. Comprima o recorte la imagen." | Subir imagen más pequeña |

## Flask/WSGI Configuration (settings.py)

### Variables Críticas

```python
# settings.py — Configuración mínima relevante

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Archivos multimedia — EXPLÍCITO (Constitución II)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Subdirectorios de trabajo
UPLOAD_DIR = MEDIA_ROOT / 'subidas'
RESULT_DIR = MEDIA_ROOT / 'resultados'

# Token de IA — NUNCA hardcodeado (Constitución IV)
HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')

# Timeouts de la API de IA (configurables vía env)
HF_API_TIMEOUT = int(os.getenv('HF_API_TIMEOUT', '60'))
HF_MAX_RETRIES = int(os.getenv('HF_MAX_RETRIES', '3'))
HF_RETRY_BASE_WAIT = int(os.getenv('HF_RETRY_BASE_WAIT', '5'))

# Límites de carga
MAX_UPLOAD_SIZE_MB = 10
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png']
```

### URLs

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('procesador.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# procesador/urls.py
from django.urls import path
from . import views

app_name = 'procesador'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('procesar/', views.procesar, name='procesar'),
    path('resultado/<int:sesion_id>/', views.resultado, name='resultado'),
]
```

### Models

```python
# procesador/models.py
from django.db import models

class SesionProcesamiento(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('cargando', 'Cargando modelo'),
        ('completado', 'Completado'),
        ('error', 'Error'),
    ]

    imagen_original = models.CharField(max_length=255)  # ruta relativa
    imagen_resultado = models.CharField(max_length=255, blank=True)
    preset = models.CharField(max_length=20)  # colorear/restaurar/ambos
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    error_mensaje = models.TextField(blank=True)
    intentos_api = models.IntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
```

### Forms

```python
# procesador/forms.py
from django import forms

PRESET_CHOICES = [
    ('colorear', 'Colorear'),
    ('restaurar', 'Restaurar'),
    ('ambos', 'Ambos'),
]

class ImageUploadForm(forms.Form):
    imagen = forms.ImageField(
        label='Selecciona una imagen',
        help_text='Formatos aceptados: JPEG, PNG. Máximo 10 MB.',
    )
    preset = forms.ChoiceField(
        choices=PRESET_CHOICES,
        label='Tipo de mejora',
        widget=forms.RadioSelect,
    )

    def clean_imagen(self):
        imagen = self.cleaned_data['imagen']
        # Validar tamaño (10 MB)
        if imagen.size > 10 * 1024 * 1024:
            raise forms.ValidationError('La imagen supera los 10 MB.')
        # Validar tipo MIME
        if imagen.content_type not in ['image/jpeg', 'image/png']:
            raise forms.ValidationError('Formato no soportado. Use JPEG o PNG.')
        return imagen
```

## Constitution Compliance Checklist

| # | Requisito Constitucional | Verificación |
|---|------------------------|-------------|
| I-1 | FBVs exclusivamente | ✅ `views.py` contiene solo funciones |
| I-2 | Django Forms obligatorios | ✅ `forms.py` con `ImageUploadForm` |
| I-3 | Enrutamiento app-level | ✅ `procesador/urls.py` + `config/urls.py` |
| I-4 | Separación vista→servicio | ✅ `views.py` orquesta, `services.py` ejecuta |
| II-1 | MEDIA_ROOT/MEDIA_URL explícitos | ✅ En `settings.py` |
| II-2 | Imágenes en `media/subidas/` | ✅ Upload guardado ahí |
| II-3 | Resultados en `media/resultados/` | ✅ Con UUID naming |
| II-4 | Pillow para validación | ✅ En `ImageUploadForm.clean_imagen` |
| III-1 | requests síncrono | ✅ No async, no aiohttp |
| III-2 | Headers Bearer + octet-stream | ✅ En `services.py` |
| III-3 | Payload binario puro | ✅ `data=imagen_bytes` |
| IV-1 | Token vía os.getenv() | ✅ En `settings.py` |
| IV-2 | Manejo 503/401/timeout | ✅ Estrategia de reintentos definida |
| IV-3 | .gitignore para .env | ✅ Archivo incluido |
| V-1 | Tailwind CSS vía CDN | ✅ En `inicio.html` |
| V-2 | Única plantilla `inicio.html` | ✅ SPA simulada |
| V-3 | 3 estados visuales | ✅ Vacío, Procesando, Éxito |

## Complexity Tracking

> No constitution violations detected. All principles fully compliant.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none) | — | — |

## Files to Create (Ordered by Dependency)

1. `config/` — Proyecto Django core (settings, urls, wsgi)
2. `procesador/models.py` — Modelo de datos
3. `procesador/forms.py` — Formulario de validación
4. `procesador/services.py` — Lógica de integración con HF
5. `procesador/views.py` — FBVs (inicio, procesar, resultado)
6. `procesador/urls.py` — Enrutamiento de la app
7. `templates/procesador/inicio.html` — Interfaz de usuario
8. `tests/` — Suite de tests
9. `.env` — Variables de entorno (no versionado)
10. `.gitignore` — Excluir .env, media/, __pycache__
