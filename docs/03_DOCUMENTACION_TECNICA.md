# Documentación técnica · Talent Match V6

## 1. Seguridad

| Control | Implementación | Origen |
|---|---|---|
| Contraseñas | Argon2id (`pwdlib`), política de 12+ caracteres con letras y números, hash señuelo contra ataques de tiempo | V5 + política V6 |
| Token de acceso | JWT HS256 de 15 min con `iss`, `aud`, `exp`, `nbf`, `jti` y `sid`. Lista explícita de algoritmos (bloquea `alg=none`) | V5 + `sid` |
| Revocación | Cada token referencia una `AuthSession`. Logout, cambio de contraseña, desactivación o cambio de rol revocan la sesión y el token deja de servir aunque no haya expirado | V6 |
| Refresh | Token opaco `"<sesión>.<aleatorio>"` en cookie `HttpOnly`, `SameSite=Strict`, `Path=/api/v1/auth`, `Secure` configurable. Rota en cada uso; reutilizar uno anterior revoca la sesión completa. Exige la cabecera `X-TM-Refresh` | V6 |
| Almacenamiento en el cliente | El token de acceso vive solo en memoria (no `localStorage`). Al recargar, la sesión se recupera con la cookie | V5 + V6 |
| Fuerza bruta | Bloqueo de 15 min tras 5 intentos; ventana de rate limit propia y más estricta para `/auth/token` | V5 + V6 |
| Rate limiting | Ventana deslizante por IP en memoria (`RATE_LIMIT_PER_MINUTE`). Con varias instancias: Redis | V5 |
| Cabeceras | CSP `default-src 'self'` sin `unsafe-inline`, `frame-ancestors 'none'`, `nosniff`, `DENY`, `no-referrer`, COOP/CORP, `Cache-Control: no-store` en la API, HSTS en producción | V5 (fuentes autoalojadas en V6) |
| CORS / TrustedHost | Orígenes y hosts explícitos desde `.env` | V5 |
| Errores | 422 sin reflejar la entrada; 500 genérico con `request_id` | V5 |
| Carga de archivos | Lista de extensiones, verificación por firma (`%PDF-`, PNG, JPEG, JSON válido), límite de tamaño leído sin exceder el máximo, límite de páginas, PDF cifrado o dañado rechazado, límite de 40 MP en imágenes; el archivo nunca se guarda | V5 + It4 |
| Autorización | Roles en el servidor (`require_role`), propiedad por diseño en rutas del empleado, 403 auditados | V6 |
| Auditoría | Cadena de hashes SHA-256 verificable (`GET /audit/verify`); sin datos personales; IP seudonimizada con HMAC | V6 |
| Secretos | Solo en `.env` (`SecretStr`); `.env.example` sin valores; `scripts/setup_env.py` los genera | V5 |

## 2. Cifrado y gestión de claves

| Dato | Tratamiento | Motivo |
|---|---|---|
| Correo del usuario | Fernet + índice HMAC (`BLIND_INDEX_KEY`) | Identificador personal directo; el login necesita búsqueda exacta |
| Nombre completo | Fernet | Identificador personal |
| Correo y nombre de invitados | Fernet + HMAC | Igual que usuarios |
| Detalle y respuesta de solicitudes de privacidad | Fernet | Texto libre que puede contener información personal |
| Competencias, experiencia, formación | En claro | No identifican por sí solas; se requieren para analítica y matching agregados. Acceso restringido por rol y publicación |
| Teléfono, ubicación, documento, fecha de nacimiento del CV | **No se almacenan** | Minimización: la cuenta ya identifica a la persona; los sensibles se descartan |
| Archivo del CV | **No se almacena** (solo SHA-256) | Minimización |
| Refresh tokens e invitaciones | Solo huella SHA-256 | Robo de la base no permite suplantar |

**Claves:** `SECRET_KEY` (JWT), `FIELD_ENCRYPTION_KEY` (Fernet; admite varias claves separadas por coma: la primera cifra, todas descifran → rotación sin pérdida), `BLIND_INDEX_KEY` (HMAC; separada de la del JWT para poder rotar una sin romper la otra). En producción deben venir de un gestor de secretos (Azure Key Vault, AWS Secrets Manager, etc.), nunca del repositorio.

## 3. Extracción de CV e IA

```
archivo ─▶ validate() ─▶ lector (pdfplumber · OCR Tesseract · JSON) ─▶ redact_sensitive()
        ─▶ parse_text() local (secciones, competencias con evidencia, rangos de fechas, formación, idiomas)
        ─▶ [proveedor externo] ─▶ verify_items(): solo se acepta lo que tiene evidencia literal
        ─▶ apply_extraction(): elementos "por revisar"; lo confirmado y rechazado se conserva
```

- **Transparencia:** `extracted` (literal en el documento), `inferred` (deducido de logros por el parser), `ai_external` (propuesto por un modelo con evidencia verificada pero cuyo nombre no aparece literal), `manual`. Solo el empleado asigna `confirmed`.
- **Confianza:** heurística (0,95 en sección de habilidades; 0,85 a 0,75 en el resto; 0,6 inferida; 0,8/0,7 IA externa). La interfaz la muestra como Alta, Media o Baja y aclara que no es una probabilidad calibrada.
- **Proveedores intercambiables** (`modules/extraction/providers/`): cada uno implementa `available()` y `call(text)`. Se incluyen `AnthropicProvider` (SDK oficial, como V5) y `GeminiProvider` (REST con `httpx`). La selección respeta `AI_PROVIDER`, la preferencia del administrador y la disponibilidad de claves. Un fallo del proveedor vuelve al modo local.
- **Controles previos al envío:** autorización separada del titular, política de la organización y minimización (`redact_sensitive` → `redact_for_external` → `redact_pii`: correo, teléfono, URLs, documentos), con un máximo de 12.000 caracteres. La salida se valida con Pydantic, como en V5.
- **Estado de verificación:** ambos proveedores se probaron con respuestas simuladas (contrato, minimización, verificación de evidencia, *fallback*). **No se probaron contra las APIs reales** porque el entorno de desarrollo no tenía claves.

## 4. Motor de matching

Puntaje = 100 · Σ ŵᵢ · cᵢ con ŵ normalizado sobre los componentes **aplicables**:

| Componente | Valor cᵢ | Aplica si |
|---|---|---|
| Técnicas | Σ(crédito · peso) / Σ peso de requisitos técnicos | Hay requisitos técnicos |
| Power skills | Igual con requisitos de power skills | Hay requisitos de power skills |
| Experiencia | min(1, años / años mínimos) | El cargo exige años |
| Certificaciones y formación | Promedio de educación (1; 0,7 a un nivel; 0,35; 0,4 sin dato) y cobertura de certificaciones exigidas | El cargo exige formación o certificaciones |

- Crédito por requisito (It4): 1,0 exacta con sinónimos ES↔EN · 0,85 casi idéntica · 0,7 contenida · 0,6 relacionada.
- Obligatorios: pesan ×1,5. Si un obligatorio queda por debajo de 0,7 (incluido el caso cubierto solo por una habilidad "relacionada") el perfil no es elegible. La experiencia mínima puede marcarse como obligatoria.
- Orden: primero los elegibles y después por puntaje.
- Solo se usa información **confirmada** de perfiles **publicados** con autorización vigente. El contrato del motor (`Candidate`) no contiene nombre, género, edad, foto, origen ni departamento.
- Salida: puntaje, elegibilidad, componentes (peso configurado, peso efectivo, valor y puntos), requisitos con estado, crédito, tipo de coincidencia y evidencia, fortalezas, brechas priorizadas y explicación textual.

## 5. Recomendación de formación

TF-IDF (bigramas) sobre título, habilidades y descripción de 11.550 cursos con calificación > 4,0 de `Coursera.csv` y `Udemy_Courses.xlsx` (It4). Cada brecha recibe hasta un curso por plataforma y se exige que el término clave aparezca en el título o en las habilidades. Las horas de Udemy son reales; las de Coursera se estiman por nivel y se marcan así. Las URL solo se aceptan de dominios https de Coursera y Udemy. La interfaz aclara que no se verifican disponibilidad ni precio.

## 6. Operación

- `python -m scripts.init_db`: crea las tablas (idempotente) y el administrador inicial si `ADMIN_EMAIL`/`ADMIN_PASSWORD` están definidos.
- `python -m scripts.seed_demo [--reset] [--force]`: datos demo. Se niega con `ENVIRONMENT=production` o `DEMO_MODE=false`, y `--reset` se niega si existen usuarios no demo.
- Al iniciar, un hilo carga el catálogo (unos 10 s la primera vez). `/health` informa su estado.
- Migraciones: V6 usa `create_all` (reproducible para el MVP). Para evolucionar el esquema en producción se recomienda incorporar Alembic.

## 7. PostgreSQL

El código no usa funciones específicas de SQLite (UUID, JSON y claves foráneas son portables). Para usarlo:

```powershell
pip install "psycopg[binary]>=3.2"
# .env
DATABASE_URL=postgresql+psycopg://talent:clave@localhost:5432/talentmatch
python -m scripts.init_db
```

**No verificado en este entorno** (no había servidor PostgreSQL disponible). La cadena de auditoría requiere serializar las inserciones con varias instancias concurrentes (bloqueo asesor), como se documenta en `modules/audit/service.py`.

## 8. Estructura del proyecto

```
TalentMatch_V6/
├── app/
│   ├── main.py
│   ├── core/            config · security · crypto · database · middleware · text · time
│   └── modules/         auth · consent · profiles · extraction · catalog · projects · matching ·
│                        development · analytics · dashboard · privacy · admin · audit · governance
├── frontend/            React + Vite (src/) y build (dist/)
├── scripts/             setup_env · init_db · seed_demo · demo_data · evaluate_matching · evaluate_extraction · package
├── tests/               86 pruebas + fixtures etiquetados (It4)
├── data/                datasets del proyecto (solo lectura)
├── demo/cvs/            CV sintéticos en PDF
├── docs/                auditoría, diseño, técnica, manual, informe de pruebas
├── .env.example · requirements.txt · pytest.ini · iniciar.ps1 · Dockerfile · LEEME_V6.md
```
