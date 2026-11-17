# Etapa 2 · Diseño de Talent Match V6

## 1. Arquitectura final

Se mantiene el **monolito modular de V5** (FastAPI + SQLModel). No hay microservicios ni un segundo backend: el frontend React compilado lo sirve el mismo proceso.

```
┌────────────────────────── Navegador ──────────────────────────┐
│ SPA React (Vite) · token de acceso solo en memoria            │
│ /app (empleado)   /rrhh (RR. HH.)   /admin (administración)   │
└───────────────┬───────────────────────────────────────────────┘
                │ HTTPS · Bearer JWT + cookie HttpOnly (refresh)
┌───────────────▼──────────────── FastAPI (app/main.py) ────────┐
│ Middlewares V5: TrustedHost · CORS · RateLimit · SecurityHeaders (CSP sin unsafe-inline)
│ core/   config · security · crypto · database · middleware · text · time
│ modules/
│   auth (usuarios, sesiones, invitaciones)   consent   profiles (+ talent)
│   extraction (lectores, sensibles, parser, providers/)   catalog
│   projects   matching (engine)   development (recommender)
│   analytics   dashboard   privacy   admin   audit   governance
└───────────────┬───────────────────────────────────────────────┘
                │ SQLModel / SQLAlchemy
        SQLite (por defecto) · PostgreSQL (DATABASE_URL)
        data/: JobsDatasetProcessed.csv · Coursera.csv · Udemy_Courses.xlsx (solo lectura)
```

Regla de dependencias (heredada de V5): `modules/*` usa `core/`; un módulo usa de otro su `service` o `deps`, no sus routers. Separación: routers (presentación) → `service.py` (negocio) → modelos SQLModel (persistencia).

## 2. Modelo de datos

| Tabla | Propósito | Notas de privacidad |
|---|---|---|
| `user` | Identidad y rol (`employee`, `hr`, `admin`) | `email_enc`, `full_name_enc` (Fernet); `email_index` (HMAC, único) |
| `authsession` | Sesión con refresh rotativo | Solo la huella SHA-256 del refresh |
| `invitation` | Alta por invitación | Token de un uso; solo su huella; correo cifrado |
| `consent` | Historial de autorizaciones del titular | `processing` y `external_ai` separados; versión de política |
| `profile` | Perfil propiedad del empleado (1:1 con `user`) | Estado `draft`/`published`, visibilidad por sección |
| `profileskill` | Competencias técnicas y power skills | `origin` (extracted, inferred, ai_external, manual) + `status` (pending, confirmed, rejected) + evidencia + confianza |
| `profileentry` | Experiencia, formación, certificaciones, idiomas | Igual que las competencias |
| `extractionrun` | Trazabilidad de cada análisis | Sin archivo ni texto: huella, proveedor, categorías sensibles descartadas |
| `project`, `position`, `positionrequirement` | Proyectos, cargos y requisitos | Requisitos `mandatory`/`desirable` con peso; ponderación por cargo |
| `matchrun`, `matchresult` | Ejecuciones y resultados persistidos | Componentes, coincidencias, brechas, evidencias, explicación |
| `hrdecision` | Decisión humana justificada | Justificación ≥ 20 caracteres; visible para el titular |
| `learningpath`, `learningitem` | Rutas de aprendizaje y progreso | Cada ítem nace de una brecha |
| `privacyrequest` | Solicitudes del titular | Detalle y respuesta cifrados |
| `systemsetting` | Parámetros editables por el administrador | |
| `auditlog` | Bitácora con cadena de hashes | Sin datos personales; IP seudonimizada |

Las claves foráneas usan `ON DELETE CASCADE` (en SQLite se activa `PRAGMA foreign_keys=ON`) para que la supresión sea completa.

## 3. Roles y permisos (verificados en el servidor)

| Capacidad | Empleado | RR. HH. | Admin |
|---|:-:|:-:|:-:|
| Perfil propio, CV, confirmación, publicación | ✔ | | |
| Consentimiento y solicitudes de privacidad propias | ✔ | | |
| Oportunidades y compatibilidad propias | ✔ | | |
| Rutas propias y progreso | ✔ | | |
| Directorio de talento (solo publicado + autorización vigente) | | ✔ | |
| Proyectos, cargos, requisitos, ponderaciones | | ✔ | |
| Matching, comparación, decisiones, asignar rutas | | ✔ | |
| Analítica organizacional | | ✔ | |
| Invitar empleados | | ✔ | ✔ |
| Invitar RR. HH. / administradores | | | ✔ |
| Usuarios, roles, sesiones, desbloqueo | | | ✔ |
| Configuración del sistema | | | ✔ |
| Auditoría y verificación de la cadena | | | ✔ |
| Gestionar solicitudes de privacidad (ejecuta supresión sin ver contenido) | | | ✔ |
| Tarjeta ética | ✔ | ✔ | ✔ |
| Indicadores de gobernanza y evaluación | | ✔ | ✔ |

Implementación: `require_role()` en `modules/auth/deps.py` (cada 403 se audita como evento de seguridad). La **propiedad** se garantiza por diseño: las rutas del empleado (`/profiles/me`, `/development/items/{id}`…) toman al dueño del token y verifican que el recurso le pertenezca; no aceptan un identificador de perfil.

## 4. Contratos API (prefijo `/api/v1`)

| Módulo | Endpoints principales |
|---|---|
| auth | `POST /auth/token` · `POST /auth/refresh` (cabecera `X-TM-Refresh: 1`) · `POST /auth/logout` · `GET /auth/me` · `POST /auth/password` |
| invitaciones | `POST/GET /invitations` · `DELETE /invitations/{id}` · `GET /invitations/token/{token}` · `POST /invitations/token/{token}/accept` |
| consentimiento | `GET /consent/policy` (público) · `GET/POST /consent/me` · `GET /consent/me/history` |
| perfil | `GET/PATCH /profiles/me` · `POST /profiles/me/cv` · `GET /profiles/me/extractions` · `POST/PATCH/DELETE /profiles/me/skills[/{id}]` · `POST/PATCH/DELETE /profiles/me/entries[/{id}]` · `POST /profiles/me/confirm-all` · `POST /profiles/me/publish` · `POST /profiles/me/unpublish` · `GET /profiles/me/export` · `DELETE /profiles/me/data` |
| talento | `GET /talent` (filtros) · `GET /talent/facets` · `GET /talent/{profile_id}` |
| catálogo | `POST /catalog/job-templates/search` · `GET /catalog/job-templates/{id}` · `GET /catalog/skills` · `GET /catalog/defaults` |
| proyectos | `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` · `POST /projects/{id}/positions` · `GET /positions` · `GET/PATCH/DELETE /positions/{id}` |
| matching | `POST /positions/{id}/match` · `GET /positions/{id}/runs` · `GET /positions/{id}/latest-run` · `GET /match-runs/{id}` · `GET /match-results/{id}` · `POST/GET /positions/{id}/decisions` · `GET /decisions` |
| oportunidades | `GET /opportunities` · `GET /opportunities/{position_id}` · `GET /opportunities/processes` |
| desarrollo | `GET /development/me` · `GET /development/me/recommendations` · `POST /development/me/paths` · `PATCH /development/items/{id}` · `POST/GET /development/paths` · `POST /development/paths/{id}/archive` · `POST /development/recommend` |
| analítica | `GET /analytics/overview` · `/skills` · `/positions` · `/training` · `/filters` |
| dashboard | `GET /dashboard` (respuesta distinta según el rol) |
| privacidad | `POST /privacy/requests` · `GET /privacy/requests/me` · `GET /privacy/requests` · `PATCH /privacy/requests/{id}` |
| admin | `GET /admin/users` · `PATCH /admin/users/{id}` · `POST /admin/users/{id}/unlock` · `POST /admin/users/{id}/revoke-sessions` · `GET/PUT /admin/settings` · `GET /admin/system` · `GET /admin/security-events` |
| auditoría | `GET /audit` · `GET /audit/verify` |
| gobernanza | `GET /governance/card` · `GET /governance/metrics` · `GET /governance/benchmark` |

En desarrollo, el contrato completo está en `/docs` (OpenAPI). En producción se desactiva, como en V5. Ningún dato personal viaja por query string; las búsquedas sobre el dataset usan POST con cuerpo.

## 5. Flujo principal conectado

```
RR. HH. invita ─▶ empleado acepta y crea contraseña ─▶ autoriza tratamiento (y, aparte, IA externa)
   ─▶ carga CV ─▶ lectura (PDF/OCR/JSON) ─▶ descarte de sensibles ─▶ parser local con evidencia
   ─▶ [IA externa opcional, solo con evidencia literal] ─▶ elementos "por revisar"
   ─▶ empleado confirma / corrige / rechaza ─▶ publica
RR. HH. crea proyecto y cargo ─▶ requisitos obligatorios/deseables ─▶ ponderación
   ─▶ ejecuta matching (solo perfiles publicados y autorizados, solo datos confirmados)
   ─▶ resultados persistidos con desglose ─▶ compara ─▶ decisión justificada ─▶ asigna ruta
Empleado ─▶ ve su compatibilidad, la decisión y su ruta ─▶ registra progreso
```

## 6. Navegación

- **Empleado:** Inicio · Mi perfil · Hoja de vida · Oportunidades · Mi desarrollo · Privacidad · Cómo funciona la IA · Mi cuenta
- **RR. HH.:** Inicio · Talento interno · Proyectos y cargos · Matching · Rutas de aprendizaje · Analítica · Invitaciones · Gobernanza · Mi cuenta
- **Administración:** Inicio · Usuarios y roles · Invitaciones · Configuración · Auditoría · Solicitudes de privacidad · Gobernanza · Mi cuenta

## 7. Diseño UX/UI

| Decisión | Motivo |
|---|---|
| Fondo gris frío `#F5F6F8`, tinta `#17202B`, acento petróleo `#12506B` | Sobrio y corporativo, sin gradientes ni la estética de plantilla |
| IBM Plex Sans autoalojada, cifras tabulares | Tono de herramienta empresarial; compatible con la CSP estricta (sin Google Fonts) |
| **Anatomía del puntaje** como elemento distintivo | Una barra divide el porcentaje en la contribución de cada componente y deja visible la brecha. Se usa igual en RR. HH. y en la vista del empleado |
| Colores de componentes: primeros 4 tonos de una paleta categórica validada para daltonismo | Los estados (bien, advertencia, crítico) usan colores distintos y siempre van con texto o ícono |
| Franja de indicadores en una sola superficie, tablas y listas antes que mosaicos de tarjetas | Jerarquía clara y densidad de información propia de un SaaS de RR. HH. |
| Paneles laterales para el detalle, modales para crear o editar | El contexto de la lista se conserva |
| Estados vacíos con la siguiente acción y errores que explican cómo resolver | Cada pantalla dice qué hacer |
| Responsive: menú lateral plegable bajo 860 px; `prefers-reduced-motion` respetado; foco visible | Calidad mínima de accesibilidad |

## 8. Plan de integración ejecutado

1. Núcleo de V5 copiado y extendido (`config`, `crypto` con MultiFernet, `security` con `sid`).
2. Módulos de extracción y catálogo de Iteración 4 portados a `modules/extraction` y `modules/catalog` (imports adaptados, URLs de cursos validadas como en V5).
3. Motor de matching de It4 reescrito en `modules/matching/engine.py` con obligatorios, certificaciones y redistribución de pesos.
4. Recomendador TF-IDF de It4 en `modules/development/recommender.py`.
5. Nuevos módulos: invitaciones, perfiles, proyectos, desarrollo, analítica, privacidad, administración, gobernanza.
6. Frontend nuevo (React + Vite) compilado a `frontend/dist`, servido por FastAPI con *fallback* de SPA.
7. Pruebas de V5 conservadas y adaptadas al modelo de roles. Las de It4 se integraron en la suite de extracción, que usa sus mismos CV etiquetados.
