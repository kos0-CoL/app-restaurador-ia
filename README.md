<h1 align="center">Restaurador IA</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/Tailwind_CSS-3-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/Hugging_Face-Spaces-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="Hugging Face">
  <img src="https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  <strong>Aplicacion web para colorear y restaurar fotos antiguas usando modelos de IA gratuitos</strong>
</p>

<p align="center">
  <a href="#-demo">Demo</a> &bull;
  <a href="#-caracteristicas">Caracteristicas</a> &bull;
  <a href="#-instalacion">Instalacion</a> &bull;
  <a href="#-api-y-modelos">API y Modelos</a> &bull;
  <a href="#-deploy">Deploy</a> &bull;
  <a href="#-tests">Tests</a> &bull;
  <a href="#-licencia">Licencia</a>
</p>

---

## Demo

### Antes y Despues

<p align="center">
  <img src="docs/28756141_20260706_040321.jpg" alt="Resultado procesado" width="45%">
  &nbsp;&nbsp;
  <img src="docs/screenshot-resultado.jpg" alt="Panel comparativo" width="45%">
</p>

> Sube una foto vieja, elige el tipo de mejora y obtiene el resultado en segundos.

---

## Caracteristicas

| Feature | Descripcion |
|---------|-------------|
| **Colorear** | Agrega color a fotos blanco y negro usando [DeOldify](https://github.com/jantic/DeOldify) |
| **Restaurar** | Corrige raspanos, ruido y desenfoque usando [CodeFormer](https://github.com/sczhou/CodeFormer) |
| **Ambos** | Encadena restauracion + coloreado en una sola operacion |
| **Panel comparativo** | Muestra original vs resultado lado a lado |
| **Descarga directa** | Descarga el resultado procesado con un clic |
| **Reintentos automaticos** | Maneja cold starts de los Spaces de Hugging Face |
| **Sin autenticacion** | Acceso publico, sin registro requerido |
| **UI moderna** | Interfaz oscura con Tailwind CSS |

---

## Stack Tecnologico

| Componente | Tecnologia | Version |
|-----------|-----------|---------|
| Backend | Python + Django | 3.10+ / 6.0.6 |
| Frontend | Tailwind CSS (CDN) | 3.x |
| Variables de entorno | python-dotenv | 1.1.0 |
| HTTP Client | requests | 2.34.2 |
| Procesamiento de imagen | Pillow | 12.3.0 |
| Base de datos | SQLite (dev) / PostgreSQL (prod) | - |
| IA | Hugging Face Spaces (Gradio REST) | Gratuito |

---

## Instalacion

### Prerequisitos

- Python 3.10 o superior
- Cuenta de Hugging Face (gratuita)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/app-restaurador-ia.git
cd app-restaurador-ia

# 2. Crear y activar el entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu token de Hugging Face

# 5. Ejecutar migraciones
python manage.py migrate

# 6. Crear directorios de media
mkdir -p media/subidas media/resultados

# 7. Iniciar el servidor
python manage.py runserver
```

Abrir **http://127.0.0.1:8000** en el navegador.

---

## Variables de Entorno

Crea un archivo `.env` en la raiz del proyecto (esta en `.gitignore`):

```env
# Token de Hugging Face (obtener en https://huggingface.co/settings/tokens)
HUGGINGFACE_API_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxx

# Configuracion de la API
HF_API_TIMEOUT=60
HF_MAX_RETRIES=3
HF_RETRY_BASE_WAIT=5

# URLs de los Spaces de Gradio
GRADIO_SPACE_COLOREAR=https://leonelhs-deoldify.hf.space
GRADIO_SPACE_RESTAURAR=https://sczhou-codeformer.hf.space
```

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `HUGGINGFACE_API_TOKEN` | User Access Token de HF | **requerido** |
| `HF_API_TIMEOUT` | Timeout de peticiones (seg) | `60` |
| `HF_MAX_RETRIES` | Maximo de reintentos | `3` |
| `HF_RETRY_BASE_WAIT` | Espera entre reintentos (seg) | `5` |
| `GRADIO_SPACE_COLOREAR` | URL Space DeOldify | `leonelhs-deoldify.hf.space` |
| `GRADIO_SPACE_RESTAURAR` | URL Space CodeFormer | `sczhou-codeformer.hf.space` |

---

## API y Modelos

### Arquitectura

La aplicacion se conecta a **Spaces publicos de Hugging Face** mediante la API REST de Gradio (reemplaza la API Serverless Inference deprecada).

**Flujo de 3 pasos:**

```
1. UPLOAD  → POST /gradio_api/upload         → path remoto
2. PREDICT → POST /gradio_api/call/{api}     → event_id
3. DOWNLOAD→ GET  /gradio_api/call/{api}/{id} → bytes imagen
```

### Spaces Configurados

| Preset | Space | Endpoint | Modelo |
|--------|-------|----------|--------|
| `colorear` | [leonelhs/deoldify](https://huggingface.co/spaces/leonelhs/deoldify) | `/predict` | DeOldify |
| `restaurar` | [sczhou/CodeFormer](https://huggingface.co/spaces/sczhou/CodeFormer) | `/inference` | CodeFormer |

### Parametros de CodeFormer

```python
face_align=True          # Alineacion facial
background_enhance=True  # Mejora de fondo
face_upsample=True       # Upsampling facial
upscale=2                # Factor de escala
codeformer_fidelity=0.5  # Fidelidad al modelo (0-1)
```

### Logica de Reintentos

```
Space responde 503 (cold start)?
  ├─ Si → Espera 5 segundos → reintenta
  │       ├─ 2do fallo → espera 5 segundos → reintenta
  │       └─ 3er fallo → muestra error amigable
  └─ No → Retorna resultado o error
```

---

## Estructura del Proyecto

```
app-restaurador-ia/
├── config/                         # Configuracion Django
│   ├── settings.py                 # Settings: tokens, URLs, rutas
│   └── urls.py                     # Enrutamiento raiz
├── procesador/                     # Aplicacion principal
│   ├── models.py                   # SesionProcesamiento
│   ├── forms.py                    # ImageUploadForm
│   ├── views.py                    # FBVs: inicio, procesar, resultado
│   ├── services.py                 # Integracion API Gradio
│   ├── urls.py                     # Rutas de la app
│   ├── templates/procesador/
│   │   └── inicio.html             # UI de una pagina (Tailwind)
│   └── management/commands/
│       └── limpiar_archivos.py     # Limpieza de archivos antiguos
├── tests/                          # Suite de pruebas (25 tests)
│   ├── test_forms.py               # Tests de formularios
│   ├── test_services.py            # Tests de servicios API (mockeados)
│   └── test_views.py               # Tests de vistas
├── media/                          # Archivos de usuario
│   ├── subidas/                    # Imagenes subidas
│   └── resultados/                 # Resultados procesados
├── test_ia.py                      # Script de diagnostico
├── .env                            # Variables de entorno (no subir)
├── .env.example                    # Plantilla de variables
├── requirements.txt                # Dependencias
└── README.md                       # Esta documentacion
```

---

## Flujo de Datos

```
Navegador                    Backend Django                 Hugging Face Space
  │                              │                              │
  │  POST /procesar/             │                              │
  │  (imagen + preset)           │                              │
  │ ────────────────────────────>│                              │
  │                              │  Validate form               │
  │                              │  Save image → media/subidas/ │
  │                              │  Create SesionProcesamiento  │
  │                              │                              │
  │                              │  POST /gradio_api/upload     │
  │                              │ ────────────────────────────>│
  │                              │  ← file_path                 │
  │                              │                              │
  │                              │  POST /gradio_api/call/      │
  │                              │ ────────────────────────────>│
  │                              │  ← event_id                  │
  │                              │                              │
  │                              │  GET /gradio_api/call/       │
  │                              │ ────────────────────────────>│
  │                              │  ← bytes imagen resultado    │
  │                              │                              │
  │                              │  Save result → media/        │
  │                              │  Update SesionProcesamiento  │
  │                              │                              │
  │  Redirect /resultado/<id>    │                              │
  │ <────────────────────────────│                              │
  │                              │                              │
  │  Panel Antes/Despues         │                              │
  │  (original + resultado)      │                              │
```

---

## Comandos Utiles

```bash
# Ejecutar todas las pruebas
python manage.py test tests/ -v2

# Script de diagnostico (prueba conexion real con API)
python test_ia.py

# Limpiar archivos mayores a 1 dia
python manage.py limpiar_archivos

# Vista previa de limpieza (dry-run)
python manage.py limpiar_archivos --days 2 --dry-run

# Crear superusuario (opcional, para admin Django)
python manage.py createsuperuser
```

---

## Tests

```bash
# Ejecutar suite completa
python manage.py test tests/ -v2

# Ejecutar tests especificos
python manage.py test tests.test_forms -v2
python manage.py test tests.test_services -v2
python manage.py test tests.test_views -v2
```

**Cobertura:**
- Validacion de formularios (5 tests)
- Servicios API con mocks (12 tests)
- Vistas y respuestas HTTP (8 tests)

---

## Deploy en Produccion

### Checklist

- [ ] `DEBUG = False` en `config/settings.py`
- [ ] Nuevo `SECRET_KEY` (generar con `django.core.management.utils.get_random_secret_key()`)
- [ ] `ALLOWED_HOSTS` configurado con tu dominio
- [ ] PostgreSQL como base de datos
- [ ] `python manage.py collectstatic` ejecutado
- [ ] Gunicorn como servidor WSGI
- [ ] HTTPS habilitado
- [ ] Variables de entorno en la plataforma (no en `.env`)

### Hosting Recomendado

| Opcion | Por que | Costo |
|--------|---------|-------|
| **Railway** | Deploys de Django con un clic, tier gratis | Gratis / $5/mes |
| **Render** | Deploys via Git, PostgreSQL gestionado | Gratis / $7/mes |
| **DigitalOcean App** | Soporte Docker, escalabilidad | $5+/mes |
| **Fly.io** | Edge global, cuota gratuita | Gratis / $5+/mes |
| **PythonAnywhere** | Hosting Python simple, sin Docker | Gratis / $5/mes |

### Variables en Produccion

```env
HUGGINGFACE_API_TOKEN=hf_xxxxxxxx
DJANGO_SETTINGS_MODULE=config.settings
GRADIO_SPACE_COLOREAR=https://leonelhs-deoldify.hf.space
GRADIO_SPACE_RESTAURAR=https://sczhou-codeformer.hf.space
```

---

## Limitaciones

- Sin autenticacion de usuarios (acceso publico)
- Procesamiento secuencial (una imagen a la vez)
- Tamano maximo de subida: 10 MB (solo JPEG/PNG)
- Cold starts de 10-30 seg en la primera llamada al Space
- La calidad depende de la disponibilidad de GPU del Space

---

## Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Haz commit de tus cambios (`git commit -m 'Add nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

---

## Reconocimientos

- [DeOldify](https://github.com/jantic/DeOldify) - Modelo de coloreado de imagenes
- [CodeFormer](https://github.com/sczhou/CodeFormer) - Modelo de restauracion facial
- [Hugging Face](https://huggingface.co/) - Plataforma de modelos de IA
- [Django](https://www.djangoproject.com/) - Framework web
- [Tailwind CSS](https://tailwindcss.com/) - Framework de estilos CSS

---

## Licencia

Este proyecto esta bajo la licencia MIT. Ver [LICENSE](LICENSE) para mas detalles.

---

<p align="center">
  Hecho con Python y Hugging Face
</p>
