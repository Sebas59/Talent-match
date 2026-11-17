# Etapa 1 · Auditoría técnica de V5 e Iteración 4

Fecha: 2026-11-16. Fuentes inspeccionadas (código real, no documentos):

- `Downloads/talentmatch-v5/talentmatch` — 48 archivos de código, pruebas y frontend (se excluyeron `.venv`, `.env` local y `data/talentmatch.db`).
- `Downloads/PHASE_4_TALENT_MATCH_CV/TalentMatch-Iteracion4.zip` — la copia más reciente de la Iteración 4 (la de `TALENT_MATCH_PHASE_4` es anterior y contiene `storage/.fernet.key`, `storage/.jwt.secret` y una base con datos; no se usó).

## 1. Línea base ejecutada

| Proyecto | Comando | Resultado real |
|---|---|---|
| V5 | `pytest -q` | **8 passed** (3,1 s) |
| Iteración 4 | `pytest -q` | **13 passed** (15,8 s) |
| Iteración 4 | `python -m scripts.evaluate` | precisión técnica 84,2 %, recall técnico 97,8 %, línea base 72,0 %; power skills 95,0 % / 100 %; años 5/5, educación 5/5, sensibles 5/5 |

Entorno de la auditoría: Linux, Python 3.13.18, FastAPI 0.162.7, SQLModel 0.0.50, Tesseract disponible.

## 2. Mapa de arquitectura actual

### V5 (base técnica)
```
app/main.py            lifespan, middlewares (TrustedHost, CORS, RateLimit, SecurityHeaders), handlers 422/500
app/core/              config (pydantic-settings, SecretStr) · security (Argon2id + JWT iss/aud/jti/exp)
                       crypto (Fernet + HMAC blind index) · database (SQLModel) · middleware · text
app/modules/auth       User, login OAuth2 password, bloqueo por intentos, require_role
app/modules/consent    Consent ligado al candidato, política Ley 1581
app/modules/candidates carga PDF (en memoria), extractor local / Claude, CRUD ARCO
app/modules/catalog    vacantes y cursos desde los datasets (pandas, cache)
app/modules/matching   cobertura por contenencia + pesos it/soft/experience
app/modules/audit      bitácora con IP seudonimizada
frontend/              HTML + CSS + JS sin dependencias
```

### Iteración 4 (fuente de funcionalidades)
```
app/presentation  routers REST (cookie JWT), SPA con Chart.js
app/business      extracción (pdfplumber, OCR Tesseract, JSON), datos sensibles, catálogo de skills ES↔EN,
                  matching explicable con crédito parcial, plan de capacitación TF-IDF, privacidad, evaluación ética
app/persistence   repositorios SQLAlchemy, datasets, Fernet
app/database      modelos (12 tablas), proyectos semilla ligados a filas del dataset
```

## 3. Funcionalidades verificadas

| Funcionalidad | V5 | Iteración 4 |
|---|---|---|
| Argon2id | Sí (`pwdlib`) | No (bcrypt) |
| JWT Bearer con `iss/aud/jti/exp`, lista de algoritmos | Sí | Cookie HttpOnly, sin `aud/iss` |
| Revocación de sesión / logout real | **No** (el `jti` no se consulta) | Borra la cookie; el token sigue válido |
| Bloqueo por intentos, hash señuelo | Sí | Sí |
| TrustedHost, CORS, CSP sin `unsafe-inline`, rate limit | Sí | CSP con `unsafe-inline` en estilos, sin rate limit |
| Cifrado Fernet + índice HMAC | Nombre y correo del candidato | Nombre, correo, teléfono, ubicación |
| Roles | Solo `hr_admin` efectivo | Un solo rol (analista) para 4 cuentas fijas |
| Autoservicio del empleado | **No** | **No** |
| Quién carga el CV | RR. HH. | RR. HH. (declara el consentimiento en nombre del titular) |
| Formatos de CV | PDF con texto (pypdf) | PDF texto, PDF escaneado y PNG/JPG (OCR), JSON |
| Datos sensibles | Redacción de correo/teléfono/documento antes de la IA | Detección por 12 categorías y descarte; solo se guarda la categoría |
| Evidencia por habilidad | No | Sí (fragmento literal, confianza, fuente) |
| IA externa | Claude con SDK oficial, salida validada con Pydantic | Claude por `httpx`, solo acepta habilidades con evidencia literal |
| Distinción extraído / inferido / confirmado | No | Parcial (extraída vs. inferida de logros); no existe "confirmado por el empleado" |
| Matching | Contra 3.000 vacantes del dataset; pesos it/soft/exp | Contra cargos de proyectos internos; 4 componentes; crédito parcial y habilidades relacionadas; explicación |
| Requisitos obligatorios vs. deseables | No | No |
| Proyectos y cargos creados por RR. HH. | No | No (8 proyectos fijos en código) |
| Decisión humana justificada | No | Sí (`hr_decisions`) |
| Plan de capacitación | Búsqueda por subcadena | TF-IDF, cursos > 4.0, horas, proyección de puntaje |
| Rutas de aprendizaje con progreso | No | No (el plan se genera, no se asigna ni se sigue) |
| Analítica | No | Insights básicos y métricas éticas |
| Auditoría con cadena de hashes | **No existe** | No |
| Datos de demostración | No | No (usuarios reales del equipo) |

## 4. Riesgos y errores reales encontrados

1. **Rol único.** `User.role` vale `hr_admin` por defecto y todas las rutas exigen `HRAdmin`. No hay separación RR. HH. / administrador / empleado.
2. **El titular no participa.** En ambas versiones RR. HH. sube el CV y marca la casilla de consentimiento por el empleado. La prueba de autorización queda firmada por un tercero.
3. **Sin control de propiedad.** Cualquier `hr_admin` lee, modifica o borra cualquier candidato. No existe un dueño del perfil.
4. **Logout sin revocación.** El JWT de V5 vive 15 min y no puede invalidarse; el frontend lo guarda solo en memoria, así que recargar la página cierra la sesión.
5. **Correo del usuario en claro.** `User.email` se guarda sin cifrar en V5 (el de candidato sí está cifrado).
6. **Matching de V5 generoso.** La contenencia de cadenas hace que "SQL" cubra "SQL Server Reporting"; no hay crédito parcial ni evidencias.
7. **Extractor local de V5 limitado.** Solo busca términos del vocabulario del dataset; no extrae experiencia por fechas, educación, certificaciones ni evidencias.
8. **Iteración 4 con cuentas reales en código.** `init_db.py` contiene correos y hashes bcrypt del equipo y borra cualquier otro usuario al iniciar. No sirve para un sistema multiusuario.
9. **Iteración 4 genera secretos en disco** (`storage/.jwt.secret`, `.fernet.key`) si no hay variables de entorno; cómodo, pero la clave Fernet queda junto a la base de datos.
10. **Sin migraciones.** Ambos usan `create_all`; no hay mecanismo de reinicio seguro de datos demo.
11. **Bitácora sin integridad.** Se puede alterar una fila sin que se note.

## 5. Qué se conserva, qué se recupera, qué se corrige

| Decisión | Detalle |
|---|---|
| **Se conserva de V5** | Monolito modular `core/` + `modules/`, SQLModel, pydantic-settings con `SecretStr`, Argon2id, JWT con validación estricta, Fernet + HMAC, middlewares de seguridad, manejo de errores sin reflejar input, PDF en memoria, validación de la salida del LLM, sus 8 pruebas (adaptadas al nuevo modelo de roles). |
| **Se recupera de Iteración 4** | Lectores PDF/OCR/JSON, detección de datos sensibles, catálogo de skills ES↔EN, parser con evidencia y confianza, motor de matching explicable, recomendador TF-IDF, decisiones humanas, métricas de evaluación y tarjeta ética, CV de prueba etiquetados y `gold.json`. |
| **Se descarta** | Usuarios fijos de It4, secretos autogenerados en disco, cookie JWT sin `aud`, bcrypt (se migra a Argon2id), `pypdf` (sustituido por `pdfplumber`, que además detecta fotos), frontend vanilla de V5 (se reconstruye). |
| **Se corrige / agrega** | Tres roles con permisos en servidor; invitaciones; autoservicio del empleado; propiedad de perfiles; consentimiento firmado por el titular con autorización separada para IA externa; estados extraído / inferido / confirmado; publicación controlada; proyectos y cargos creados por RR. HH. con requisitos obligatorios y deseables; rutas de aprendizaje con progreso; analítica; sesiones revocables con refresh token; cadena de hashes en auditoría; datos demo reproducibles. |

## 6. Plan de evolución

1. Rehacer `auth` con roles `employee`, `hr`, `admin`, sesiones revocables e invitaciones.
2. Sustituir `candidates` por `profiles` (perfil propiedad del empleado) y portar la extracción de It4 a `modules/extraction` con proveedores intercambiables.
3. Nuevo `projects` (proyectos, cargos, requisitos) y reescritura de `matching` sobre el motor de It4.
4. Nuevo `development` (recomendaciones, rutas, progreso), `analytics`, `privacy` y `admin`.
5. Cadena de hashes en `audit`.
6. Frontend React + Vite, compilado y servido por FastAPI.
7. Semilla demo, pruebas, documentación y ZIP.
