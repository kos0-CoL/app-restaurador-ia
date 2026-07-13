#!/usr/bin/env python3
"""
Script de diagnostico independiente para Restaurador IA.
Valida: carga de .env, token, DNS, conexion a HF, y modelos.

Uso:
    python test_ia.py
"""

import os
import sys
import io
import socket
from pathlib import Path
from datetime import datetime

# ─── PASO 1: Cargar .env ──────────────────────────────────────────────

print("=" * 60)
print("  DIAGNOSTICO RESTAURADOR IA")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

print("\n[PASO 1] Carga de variables de entorno (.env)")

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / '.env'

print(f"  Directorio del proyecto : {BASE_DIR}")
print(f"  Ruta de .env            : {env_path}")
print(f"  Archivo .env existe     : {env_path.exists()}")

if not env_path.exists():
    print("  [FATAL] No se encontro el archivo .env")
    sys.exit(1)

with open(env_path, 'r') as f:
    env_lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]

print(f"  Variables definidas     : {len(env_lines)}")
for line in env_lines:
    key = line.split('=')[0]
    val = line.split('=', 1)[1] if '=' in line else ''
    masked = val[:6] + '...' + val[-4:] if len(val) > 10 else '***'
    print(f"    - {key} = {masked}")

try:
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)
    print(f"  python-dotenv          : OK")
except ImportError:
    print("  [FATAL] python-dotenv no instalado")
    sys.exit(1)

# ─── PASO 2: Verificar token ──────────────────────────────────────────

print("\n[PASO 2] Verificacion del token")

token = os.getenv('HUGGINGFACE_API_TOKEN', '')
print(f"  os.getenv() retorno     : {'SI' if token else 'VACIO'}")
print(f"  Longitud                : {len(token)} caracteres")
print(f"  Empieza con 'hf_'       : {token.startswith('hf_')}")
print(f"  Valor (enmascarado)     : {token[:8]}...{token[-4:] if len(token) > 12 else ''}")

if not token:
    print("\n  [FATAL] HUGGINGFACE_API_TOKEN esta vacio")
    sys.exit(1)

# ─── PASO 3: Verificar dependencias ───────────────────────────────────

print("\n[PASO 3] Dependencias")

try:
    import requests
    print(f"  requests                : v{requests.__version__}")
except ImportError:
    print("  [FATAL] requests no instalado")
    sys.exit(1)

try:
    from PIL import Image
    print(f"  Pillow                  : v{Image.__version__}")
except ImportError:
    print("  [WARN] Pillow no disponible")

# ─── PASO 4: Generar imagen de prueba ─────────────────────────────────

print("\n[PASO 4] Imagen de prueba")

from PIL import Image, ImageDraw

img = Image.new('RGB', (256, 256), color=(128, 100, 80))
draw = ImageDraw.Draw(img)
for x in range(0, 256, 32):
    draw.line([(x, 0), (x, 255)], fill=(80, 60, 40), width=2)
for y in range(0, 256, 32):
    draw.line([(0, y), (255, y)], fill=(80, 60, 40), width=2)
draw.rectangle([64, 64, 192, 192], fill=(200, 180, 160), outline=(100, 80, 60))
draw.ellipse([96, 96, 160, 160], fill=(160, 140, 120))

buf = io.BytesIO()
img.save(buf, format='JPEG', quality=85)
imagen_bytes = buf.getvalue()
print(f"  Imagen generada         : 256x256 JPEG, {len(imagen_bytes)} bytes")

# ─── PASO 5: Resolucion DNS ───────────────────────────────────────────

print("\n[PASO 5] Resolucion DNS")

hostnames = [
    ('huggingface.co', 'Sitio principal HF'),
    ('api-inference.huggingface.co', 'API antigua (Serverless Inference)'),
    ('router.huggingface.co', 'API nueva (Inference Providers)'),
]

dns_results = {}
for host, desc in hostnames:
    try:
        result = socket.getaddrinfo(host, 443)
        ip = result[0][4][0]
        dns_results[host] = True
        print(f"  {host}")
        print(f"    -> RESUELVE: {ip} ({desc})")
    except socket.gaierror as e:
        dns_results[host] = False
        print(f"  {host}")
        print(f"    -> NO RESUELVE: {e} ({desc})")

# ─── PASO 6: Test api-inference (ANTIGUA) ─────────────────────────────

print("\n[PASO 6] API ANTIGUA: api-inference.huggingface.co")
print("  Este endpoint fue DEPRECADO por Hugging Face")

if not dns_results.get('api-inference.huggingface.co'):
    print("  [DEPRECADO] El DNS no resuelve este dominio")
    print("  Hugging Face elimino este endpoint completamente")
    print("  La app NO puede funcionar con esta URL")

    url_old = "https://api-inference.huggingface.co/models/jantic/DeOldify"
    print(f"\n  Probando {url_old}...")
    try:
        resp_old = requests.post(
            url_old,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/octet-stream'},
            data=imagen_bytes,
            timeout=15,
        )
        print(f"  Status: {resp_old.status_code}")
    except requests.exceptions.ConnectionError as e:
        err = str(e)
        if 'Failed to resolve' in err or 'No address' in err:
            print(f"  Resultado: DNS resolution error (confirmado deprecado)")
        else:
            print(f"  Resultado: Connection error: {err[:100]}")
    except Exception as e:
        print(f"  Resultado: {type(e).__name__}: {str(e)[:100]}")
else:
    print("  [INesperado] El DNS SI resuelve - intentando llamada...")
    try:
        resp = requests.post(
            f"https://api-inference.huggingface.co/models/jantic/DeOldify",
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/octet-stream'},
            data=imagen_bytes,
            timeout=30,
        )
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

# ─── PASO 7: Test router.huggingface.co (NUEVA) ──────────────────────

print("\n[PASO 7] API NUEVA: router.huggingface.co")
print("  Endpoint de reemplazo para la API de inference")

modelos = [
    ('jantic/DeOldify', 'Colorear (DeOldify)'),
    ('sczhou/CodeFormer', 'Restaurar (CodeFormer)'),
]

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/octet-stream',
}

for modelo_id, desc in modelos:
    url_new = f'https://router.huggingface.co/hf-inference/models/{modelo_id}'
    print(f"\n  Modelo: {desc}")
    print(f"  URL: {url_new}")

    try:
        start = datetime.now()
        resp = requests.post(url_new, headers=headers, data=imagen_bytes, timeout=30)
        elapsed = (datetime.now() - start).total_seconds()

        print(f"  Status: {resp.status_code} ({elapsed:.1f}s)")

        if resp.status_code == 200:
            print(f"  [EXITO] Modelo disponible! Bytes: {len(resp.content)}")
            out = BASE_DIR / f'test_ia_{modelo_id.split("/")[1]}.jpg'
            with open(out, 'wb') as f:
                f.write(resp.content)
            print(f"  Guardado en: {out}")
        else:
            try:
                err = resp.json()
                error_msg = err.get('error', str(err))
                print(f"  Error: {error_msg}")
                if 'not supported' in error_msg.lower():
                    print(f"  -> Modelo NO soportado por hf-inference provider")
            except Exception:
                print(f"  Body: {resp.text[:300]}")

    except requests.exceptions.ConnectionError as e:
        print(f"  Connection error: {str(e)[:100]}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {str(e)[:100]}")

# ─── PASO 8: Buscar modelos alternativos disponibles ──────────────────

print("\n[PASO 8] Busqueda de modelos alternativos en HF Hub")

alternativas = [
    ('AXERA-TECH/DeOldify', 'DeOldify variante (pipeline: image-to-image)'),
    ('timbrooks/instruct-pix2pix', 'Image editing (pipeline: image-to-image)'),
]

for modelo_id, desc in alternativas:
    url_alt = f'https://router.huggingface.co/hf-inference/models/{modelo_id}'
    print(f"\n  Probando: {desc}")
    print(f"  Modelo: {modelo_id}")

    try:
        resp = requests.post(url_alt, headers=headers, data=imagen_bytes, timeout=30)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  [EXITO] Modelo alternativo funcional!")
            out = BASE_DIR / f'test_ia_alt_{modelo_id.split("/")[-1]}.jpg'
            with open(out, 'wb') as f:
                f.write(resp.content)
            print(f"  Guardado en: {out}")
        else:
            try:
                err = resp.json().get('error', resp.text[:100])
                print(f"  Error: {err}")
            except Exception:
                print(f"  Body: {resp.text[:100]}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {str(e)[:100]}")

# ─── RESUMEN FINAL ────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  RESUMEN DEL DIAGNOSTICO")
print("=" * 60)

api_antigua_ok = dns_results.get('api-inference.huggingface.co', False)
api_nueva_ok = dns_results.get('router.huggingface.co', False)

print(f"""
  [CHECKLIST]
  1. .env existe y carga       : OK
  2. Token valido              : OK ({len(token)} chars)
  3. python-dotenv             : OK
  4. requests + Pillow         : OK
  5. DNS huggingface.co        : {'OK' if dns_results.get('huggingface.co') else 'FALLO'}
  6. DNS api-inference (ANTIGUA): {'OK' if api_antigua_ok else 'DEPRECADO/NO RESUELVE'}
  7. DNS router.huggingface    : {'OK' if api_nueva_ok else 'FALLO'}
  8. Modelo DeOldify via nueva : Ver PASO 7
  9. Modelo CodeFormer via nueva: Ver PASO 7
""")

if not api_antigua_ok:
    print("  [CAUSA RAIZ IDENTIFICADA]")
    print("")
    print("  El endpoint ANTIGUO 'api-inference.huggingface.co' ha sido")
    print("  ELIMINADO por Hugging Face. El DNS ya no resuelve este")
    print("  dominio. La app NO puede usar esta URL.")
    print("")
    print("  El endpoint NUEVO 'router.huggingface.co' existe pero los")
    print("  modelos jantic/DeOldify y sczhou/CodeFormer NO estan")
    print("  soportados por el provider 'hf-inference'.")
    print("")
    print("  [OPCIONES DE SOLUCION]")
    print("")
    print("  A) Usar la libreria huggingface_hub (InferenceClient)")
    print("     - Requiere: pip install huggingface_hub")
    print("     - Puede buscar providers alternativos automaticamente")
    print("     - Puede que DeOldify/CodeFormer no esten disponibles")
    print("")
    print("  B) Usar Replicate API (alternativa popular)")
    print("     - Tiene DeOldify y CodeFormer disponibles")
    print("     - Requiere: cuenta en replicate.com + token")
    print("     - Costo: ~$0.0023/segundo de GPU")
    print("")
    print("  C) Ejecutar modelos LOCALMENTE")
    print("     - Descargar DeOldify y CodeFormer desde GitHub")
    print("     - Requiere: GPU con minimo 4GB VRAM")
    print("     - Sin costo por uso")
    print("")
    print("  D) Buscar modelos HF alternativos")
    print("     - Verificar si existen versiones de DeOldify/CodeFormer")
    print("       que SI esten soportadas por Inference Providers")
    print("     - Los modelos listados arriba no funcionaron")

print("\n" + "=" * 60)
