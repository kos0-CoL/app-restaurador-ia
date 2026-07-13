# Tasks: Restauración y Coloreado de Imágenes con IA

**Input**: Design documents from `/specs/001-image-restore-colorize/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Proyecto Django**: `config/` (core), `procesador/` (app principal)
- **Templates**: `templates/procesador/`
- **Media**: `media/subidas/`, `media/resultados/`
- **Tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto Django y estructura base

- [X] T001 Crear estructura del proyecto Django (`manage.py`, `config/`, `procesador/`) ejecutando `django-admin startproject config .` y `python manage.py startapp procesador`
- [X] T002 [P] Configurar `config/settings.py`: MEDIA_ROOT, MEDIA_URL, ALLOWED_HOSTS, INSTALLED_APPS (agregar `procesador`), variables de entorno con `os.getenv()` para HUGGINGFACE_API_TOKEN
- [X] T003 [P] Crear directorios de media: `media/subidas/` y `media/resultados/` con archivos `.gitkeep`
- [X] T004 [P] Crear `.env.example` con variables `HUGGINGFACE_API_TOKEN=`, `HF_API_TIMEOUT=60`, `HF_MAX_RETRIES=3`, `HF_RETRY_BASE_WAIT=5` y `.gitignore` excluyendo `.env`, `media/`, `__pycache__/`, `venv/`
- [X] T005 Instalar dependencias ejecutando `pip install -r requirements.txt` en el virtualenv

**Checkpoint**: Proyecto Django inicializado, media directories listos, variables de entorno documentadas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modelos, forms y capa de servicios compartidos que TODOS los user stories necesitan

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Crear modelo `SesionProcesamiento` en `procesador/models.py` con campos: imagen_original, imagen_resultado, preset, estado, error_mensaje, intentos_api, creado, actualizado
- [X] T007 Ejecutar `python manage.py makemigrations` y `python manage.py migrate` para crear la tabla en SQLite
- [X] T008 Crear `ImageUploadForm` en `procesador/forms.py` con campo `imagen` (ImageField), campo `preset` (ChoiceField con opciones Colorear/Restaurar/Ambos), y método `clean_imagen()` que valide formato (JPEG/PNG) y tamaño (<=10MB)
- [X] T009 Crear `procesador/services.py` con función base `llamar_api_hf(imagen_bytes, modelo_id, token)` que realice POST síncrono con headers Authorization Bearer + Content-Type application/octet-stream y payload binario puro
- [X] T010 Implementar en `procesador/services.py` el manejo de respuestas HTTP: 200→éxito, 503→reintentar con backoff exponencial (5s, 10s, 20s, máx 3 intentos), 401→error token, timeout→abortar
- [X] T011 Implementar en `procesador/services.py` función `guardar_imagen(directorio, archivo)` que genere nombre único con UUID corto + timestamp (ej. `abc123_20260705_143022.jpg`) y guarde el archivo en el directorio especificado
- [X] T012 Crear `config/urls.py` incluyendo `procesador.urls` y configurando `static(MEDIA_URL, document_root= MEDIA_ROOT)` para servir archivos media en desarrollo
- [X] T013 Crear `procesador/urls.py` con rutas: `''` → `views.inicio`, `'procesar/'` → `views.procesar`, `'resultado/<int:sesion_id>/'` → `views.resultado`
- [X] T014 Crear `templates/procesador/inicio.html` con Tailwind CSS vía CDN, estructura base HTML5, y marcadores para los 3 estados visuales (vacío, procesando, éxito)
- [X] T015 [P] Crear `tests/__init__.py`, `tests/test_forms.py` (validación de ImageUploadForm: formato, tamaño, preset válido)
- [X] T016 [P] Crear `tests/test_services.py` (mock de requests.post para validar flujo 200, 503, 401, timeout)
- [X] T017 Ejecutar `python manage.py test` para verificar que la infraestructura base funciona correctamente

**Checkpoint**: Foundation ready — modelo, forms, servicios base, URLs, template base y tests de infraestructura funcionando

---

## Phase 3: User Story 1 — Cargar y Colorear una Imagen (Priority: P1) 🎯 MVP

**Goal**: Un usuario sube una imagen B&W, selecciona "Colorear", y recibe un panel comparativo con la versión colorizada descargable.

**Independent Test**: Cargar imagen B&W → seleccionar "Colorear" → ver panel A/D → descargar resultado

### Implementation for User Story 1

- [X] T018 [US1] Implementar en `procesador/services.py` función `colorear_imagen(imagen_bytes, token)` que llame a `jantic/DeOldify` via `llamar_api_hf()` y retorne los bytes del resultado o error
- [X] T019 [US1] Implementar en `procesador/views.py` función `inicio(request)` que renderice `inicio.html` con `ImageUploadForm` vacío (GET)
- [X] T020 [US1] Implementar en `procesador/views.py` función `procesar(request)` que valide con `ImageUploadForm`, guarde imagen original en `media/subidas/`, llame a `colorear_imagen()`, guarde resultado en `media/resultados/`, registre sesión en DB y redirija a `/resultado/<id>/`
- [X] T021 [US1] Implementar en `procesador/views.py` función `resultado(request, sesion_id)` que cargue la sesión de la DB, renderice `inicio.html` en estado "éxito" con URLs de imagen original y resultado para el panel comparativo
- [X] T022 [US1] Implementar en `procesador/views.py` manejo de errores en `procesar()`: catches para 503 (reintentos), 401, timeout, formato inválido — actualizando estado de sesión y mostrando mensaje al usuario
- [X] T023 [US1] Completar `templates/procesador/inicio.html` con los 3 estados: estado vacío (form con dropzone + radio buttons para preset), estado procesando (spinner con mensaje "Procesando tu imagen..."), estado éxito (panel comparativo lado a lado con botones de descarga y "Nueva imagen")
- [X] T024 [US1] Agregar JavaScript vanilla en `inicio.html` para: validación client-side de archivo antes de submit, mostrar spinner al enviar, manejo de respuestas AJAX si se usa fetch en lugar de form submit

**Checkpoint**: User Story 1 funcional — Upload → Colorear → Panel A/D → Descargar

---

## Phase 4: User Story 2 — Restaurar una Imagen (Priority: P2)

**Goal**: Un usuario sube una imagen deteriorada, selecciona "Restaurar", y recibe un panel comparativo con la versión restaurada.

**Independent Test**: Subir imagen dañada → seleccionar "Restaurar" → ver mejoras en nitidez → descargar

### Implementation for User Story 2

- [X] T025 [P] [US2] Implementar en `procesador/services.py` función `restaurar_imagen(imagen_bytes, token)` que llame a `sczhou/CodeFormer` via `llamar_api_hf()` y retorne los bytes del resultado o error
- [X] T026 [US2] Actualizar en `procesador/views.py` la función `procesar()` para soportar el preset "restaurar" usando `restaurar_imagen()` en lugar de `colorear_imagen()`
- [X] T027 [US2] Verificar que `inicio.html` muestra correctamente el panel comparativo para el preset "Restaurar" (sin cambios en template si el template ya es genérico)

**Checkpoint**: User Story 1 y 2 funcionando independientemente — cada preset llama al modelo correcto

---

## Phase 5: User Story 3 — Colorear y Restaurar Simultáneamente (Priority: P3)

**Goal**: Un usuario sube una imagen vieja deteriorada en B&W, selecciona "Ambos", y recibe un resultado que combina coloreado + restauración.

**Independent Test**: Subir imagen B&W deteriorada → seleccionar "Ambos" → ver resultado colorizado Y restaurado → descargar

### Implementation for User Story 3

- [X] T028 [US3] Implementar en `procesador/services.py` función `procesar_ambos(imagen_bytes, token)` que encadene `restaurar_imagen()` → `colorear_imagen()` (primero restaurar nitidez, luego aplicar color) y retorne los bytes finales
- [X] T029 [US3] Actualizar en `procesador/views.py` la función `procesar()` para soportar el preset "ambos" usando `procesar_ambos()`
- [X] T030 [US3] Verificar que `inicio.html` muestra un indicador de carga apropiado para "Ambos" (puede mostrar "Restaurando y colorizando..." o similar)

**Checkpoint**: Los 3 presets funcionan independientemente — Colorear, Restaurar, y Ambos

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras transversales, limpieza y documentación

- [X] T031 [P] Implementar limpieza automática de archivos: crear management command `python manage.py limpiar_archivos` que elimine archivos en `media/subidas/` y `media/resultados/` con más de 24 horas de antigüedad
- [X] T032 [P] Agregar manejo de abort en `procesador/views.py`: si el usuario cierra la pestaña, detectar desconexión y eliminar imagen temporal + actualizar sesión a estado "abortado"
- [X] T033 [P] Crear `tests/test_views.py` con tests para las 3 FBVs: inicio (GET retorna form), procesar (POST válido → redirect a resultado, POST inválido → errores en form), resultado (GET con sesion_id válida e inválida)
- [X] T034 Ejecutar `python manage.py test` completo y verificar que todos los tests pasan
- [X] T035 [P] Documentar en `README.md`: instrucciones de instalación, variables de entorno requeridas, cómo ejecutar el servidor, modelos de IA utilizados, y limitaciones del MVP
- [X] T036 Revisar compliance con la Constitución: verificar que todas las vistas son FBVs, que no hay credenciales hardcoded, que MEDIA_ROOT/MEDIA_URL son explícitos, que se usa requests síncrono sin async

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP, highest priority
- **US2 (Phase 4)**: Depends on Foundational — Can start in parallel with US1
- **US3 (Phase 5)**: Depends on US1 + US2 (necesita ambas funciones de services.py)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — Can start after Phase 2
- **US2 (P2)**: No dependencies on US1 — Can start after Phase 2 (in parallel with US1)
- **US3 (P3)**: Depends on US1 + US2 — Both must be functional before starting

### Within Each User Story

- Models/Services before Views
- Views before Template (or in parallel if template is generic)
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004, T015, T016 can run in parallel (Phase 1-2)
- T025 can run in parallel with US1 tasks (different file, no dependencies)
- T031, T032, T033, T035 can run in parallel (Phase 6, different files)

---

## Parallel Example: Phase 1-2 Setup

```bash
# Launch foundational setup tasks in parallel:
Task T002: "Configurar config/settings.py"
Task T003: "Crear directorios media/"
Task T004: "Crear .env.example y .gitignore"

# Then foundational tasks:
Task T006: "Crear modelo SesionProcesamiento"
Task T008: "Crear ImageUploadForm"
Task T009: "Crear función base llamar_api_hf()"
```

## Parallel Example: User Stories 1 & 2

```bash
# Once Phase 2 is complete, US1 and US2 can run simultaneously:
# US1 Developer:
Task T018: "Implementar colorear_imagen()"
Task T019-T024: Views + Template for colorear

# US2 Developer (in parallel):
Task T025: "Implementar restaurar_imagen()"
Task T026-T027: Views update for restaurar
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T017)
3. Complete Phase 3: User Story 1 (T018-T024)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready — MVP is functional

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Colorear) → Test → Deploy/Demo (MVP!)
3. Add US2 (Restaurar) → Test → Deploy/Demo
4. Add US3 (Ambos) → Test → Deploy/Demo
5. Polish → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Colorear) — T018-T024
   - Developer B: US2 (Restaurar) — T025-T027
3. After US1 + US2 complete:
   - Developer A or B: US3 (Ambos) — T028-T030
4. Team: Polish — T031-T036

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US3 depends on US1 + US2 because it chains both services
- 24-hour cleanup is a cross-cutting concern (Phase 6), not per-story
- Abort-on-disconnect (FR-015) requires JavaScript + server-side detection
