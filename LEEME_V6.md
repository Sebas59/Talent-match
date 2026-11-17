# Talent Match V6

Módulo empresarial de gestión estratégica del talento interno. Cada empleado construye su perfil profesional a partir de su hoja de vida y decide qué confirmar y publicar. Recursos Humanos crea proyectos y cargos, ejecuta un matching explicable, registra decisiones humanas justificadas y asigna rutas de aprendizaje. La administración gestiona usuarios, seguridad, auditoría y privacidad sin acceder al contenido de los perfiles.
C:\Program Files\Tesseract-OCR
**La IA recomienda; las personas responsables deciden.**

| | |
|---|---|
| Equipo | Juan Sebastián Lozano Calderón · Andrés David Rojas Villamil · Juan Sebastián López Urrego · Jeison Oswaldo Romero Cajamarca |
| Docente | Juan Carlos Navarro Beltrán |
| Electiva | Problem Discovery & Solution Design with Artificial Intelligence, Universidad Católica de Colombia |
| Base técnica | Talent Match V5 (monolito modular FastAPI) + funcionalidades recuperadas de la Iteración 4 |

---

## 1. Requisitos previos

| Herramienta | Versión | ¿Obligatoria? |
|---|---|---|
| Python | 3.11, 3.12 o 3.13 (probado con 3.13.18) | Sí |
| Node.js | 18 o superior (probado con 22.23) | Solo para **modificar** el frontend. El ZIP ya trae `frontend/dist` compilado |
| Tesseract OCR con idioma español | 5.x | Solo para CV **escaneados** o imágenes. Sin él, PDF con texto y JSON funcionan igual |

Tesseract en Windows: instalador de UB Mannheim, marcar *Spanish* en *Additional language data* y agregar `C:\Program Files\Tesseract-OCR` al `PATH`.

## 2. Instalación rápida en Windows (PowerShell)

Descomprima `TalentMatch_V6.zip`, abra PowerShell **en la carpeta `TalentMatch_V6`** y ejecute:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # solo para esta ventana
.\iniciar.ps1
```

El script crea el entorno virtual, instala dependencias, genera `.env` con secretos aleatorios, carga los datos de demostración y arranca el servidor. Abra **http://127.0.0.1:8000**.

Para iniciar de nuevo más adelante: `.\iniciar.ps1 -SoloIniciar`. Para recargar la demo desde cero: `.\iniciar.ps1 -ReiniciarDemo`.

## 3. Instalación manual (paso a paso)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 3.1 Variables de entorno: crea .env con SECRET_KEY, FIELD_ENCRYPTION_KEY y BLIND_INDEX_KEY aleatorias
python -m scripts.setup_env

# 3.2 Base de datos (idempotente)
python -m scripts.init_db

# 3.3 Datos de demostración
python -m scripts.seed_demo --reset

# 3.4 Backend + frontend compilado (una sola dirección)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Configuración (`.env`)

Todas las variables están documentadas en `.env.example`. Las más relevantes:

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Firma de los JWT (mínimo 32 caracteres) |
| `FIELD_ENCRYPTION_KEY` | Clave(s) Fernet para nombre, correo y textos de privacidad. Varias separadas por coma permiten rotación |
| `BLIND_INDEX_KEY` | Clave HMAC de los índices ciegos (búsqueda por correo sin guardarlo en claro) |
| `DATABASE_URL` | SQLite por defecto (`data/talentmatch_v6.db`). PostgreSQL: `postgresql+psycopg://usuario:clave@localhost:5432/talentmatch` e instalar `psycopg[binary]` |
| `AI_PROVIDER` | `auto`, `local`, `anthropic` o `gemini` |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Opcionales. Sin ellas la aplicación usa el proveedor local |
| `DEMO_MODE` | `true` permite la semilla y muestra las cuentas demo en el login. En producción: `false` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Opcional: crea el primer administrador si no existe ninguno (instalación sin demo) |

> Si cambia `FIELD_ENCRYPTION_KEY` sin conservar la anterior, los datos cifrados ya guardados no se podrán leer. Para rotar, ponga la nueva primero y la anterior después: `FIELD_ENCRYPTION_KEY=nueva,anterior`.

## 4. Frontend en modo desarrollo (opcional)

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173, redirige /api al backend en :8000
npm run build      # regenera frontend/dist, que sirve FastAPI
```

## 5. Usuarios de demostración

Credenciales **exclusivamente de demostración**, creadas por `scripts/seed_demo.py` con datos sintéticos. Todas las personas, empresas, correos y teléfonos son ficticios.

| Rol | Correo | Contraseña |
|---|---|---|
| Administración | `admin@talentmatch.demo` | `AdminDemo2026!` |
| Recursos Humanos | `rrhh@talentmatch.demo` | `RrhhDemo2026!` |
| Recursos Humanos | `talento@talentmatch.demo` | `RrhhDemo2026!` |
| Empleada sin perfil (flujo en vivo) | `sofia.arango@talentmatch.demo` | `EmpleadoDemo2026!` |
| Empleada con perfil publicado | `valentina.ospina@talentmatch.demo` | `EmpleadoDemo2026!` |
| Otros 12 empleados | `nombre.apellido@talentmatch.demo` (p. ej. `santiago.herrera`, `paula.rios`, `isabela.moreno`) | `EmpleadoDemo2026!` |

La demo incluye 15 empleados (13 con perfil publicado, 1 en borrador, 1 sin perfil), 5 proyectos, 10 cargos, ejecuciones de matching, 4 decisiones, 4 rutas de aprendizaje con avance, 2 solicitudes de privacidad y una invitación pendiente (el enlace se imprime al cargar la semilla). Los CV sintéticos en PDF quedan en `demo/cvs/`.

## 6. Flujo recomendado para presentar el MVP (≈15 minutos)

1. **Login** (`/login`): mostrar las tres experiencias. Mencionar que el token vive solo en memoria y la sesión se renueva con una cookie HttpOnly.
2. **Empleada, Sofía Arango.** Inicio con el siguiente paso sugerido. Luego *Hoja de vida* aparece bloqueada sin autorización. En *Privacidad*, otorgar el tratamiento (y explicar la casilla separada de IA externa). Cargar `demo/cvs/cv_demo_sofia_arango.pdf` y mostrar el resultado: extracción local, 13 elementos literales y los datos sensibles descartados (fecha de nacimiento, estado civil).
3. **Revisar y confirmar** (*Mi perfil*): origen de cada competencia (literal, inferida, manual), evidencia, confianza heurística. Rechazar una, corregir otra, agregar una manual y publicar.
4. **Oportunidades:** abrir *Ingeniero(a) de Datos*. Mostrar la barra con la contribución de cada componente, la tabla del cálculo, los requisitos con su respaldo y la formación recomendada. Crear la ruta de aprendizaje.
5. **RR. HH., Carolina Beltrán.** Ver el dashboard, *Talento interno* (solo lo publicado) y *Proyectos y cargos*: crear un cargo, partir de una plantilla del dataset, definir requisitos obligatorios y deseables y ajustar la ponderación.
6. **Matching:** ejecutar para *Ingeniero(a) de Datos*. Sofía aparece con su puntaje y el obligatorio que le falta. Comparar dos perfiles, abrir un resultado, registrar una decisión justificada y asignar una ruta.
7. **Analítica:** oferta frente a demanda, brechas críticas (p. ej. Apache Kafka) y necesidades de capacitación, con filtros.
8. **Empleada de nuevo:** en *Oportunidades → Mis procesos* ve la decisión con su justificación. En *Mi desarrollo* marca avance.
9. **Administración:** usuarios y roles; auditoría con *Verificar integridad* (cadena de hashes); gestión de una solicitud de privacidad; configuración; estado del sistema. Recalcar que el administrador no puede abrir perfiles.
10. **Gobernanza:** tarjeta ética con indicadores en vivo y la evaluación de la extracción.

## 7. Pruebas

```powershell
python -m pytest -q                       # 86 pruebas: auth, permisos, propiedad, consentimiento, CV, IA, matching, auditoría…
python -m scripts.evaluate_matching       # coherencia del ranking, propiedades del motor y sensibilidad a los pesos
python -m scripts.evaluate_extraction     # precisión / exhaustividad de la extracción frente a CV etiquetados
```

Las pruebas usan una base temporal y no tocan `data/`. Resultados reales en `docs/05_INFORME_PRUEBAS.md`.

## 8. Empaquetado

```powershell
python -m scripts.package        # crea ..\TalentMatch_V6.zip sin .env, bases de datos ni dependencias
```

## 9. Problemas conocidos y soluciones

| Síntoma | Causa | Solución |
|---|---|---|
| `iniciar.ps1 no se puede cargar… la ejecución de scripts está deshabilitada` | Política de ejecución de PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` en esa ventana |
| `py` no se reconoce | Python instalado sin el lanzador | Use `python -m venv .venv` o reinstale Python marcando *Add to PATH* |
| Error de validación `secret_key` / `field_encryption_key` al arrancar | Falta `.env` | `python -m scripts.setup_env` |
| «La base ya tiene datos» al cargar la demo | Protección de la semilla | `python -m scripts.seed_demo --reset` (se niega si hay usuarios que no son demo) |
| Nombres de usuarios aparecen como «—» | Se regeneró `.env` y cambió la clave Fernet | Restaure la clave anterior o recargue la demo con `--reset` |
| «El PDF parece escaneado y el motor OCR no está instalado» | Falta Tesseract | Instálelo (sección 1) o use PDF con texto/JSON |
| La primera carga de CV tarda unos segundos | Se construye el índice del catálogo al iniciar | Espere a que `/health` muestre `"catalog": "ready"` |
| «Frontend no compilado» en el navegador | Falta `frontend/dist` | `cd frontend; npm install; npm run build` |
| Puerto 8000 ocupado | Otra aplicación lo usa | `python -m uvicorn app.main:app --port 8010` |

## 10. Documentación

| Archivo | Contenido |
|---|---|
| `docs/01_AUDITORIA_V5_IT4.md` | Etapa 1: diagnóstico real de V5 e Iteración 4 |
| `docs/02_DISENO_V6.md` | Etapa 2: arquitectura, modelo de datos, roles, contratos API, navegación, UX |
| `docs/03_DOCUMENTACION_TECNICA.md` | Seguridad, cifrado y claves, IA, matching, operación, PostgreSQL |
| `docs/04_MANUAL_USUARIO.md` | Manual breve por rol |
| `docs/05_INFORME_PRUEBAS.md` | Pruebas ejecutadas, resultados, errores corregidos y limitaciones |
| `docs/reports/evaluacion_matching.json` | Salida del script de evaluación del matching |

## Referencias

- isEazy. (s. f.). *Power skills* [Entrada de blog]. https://www.iseazy.com/es/blog/power-skills/
- Congreso de Colombia. (2012). *Ley Estatutaria 1581 de 2012*. (Marco de referencia; la aplicación no constituye una certificación de cumplimiento.)
- Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. *Proceedings of the Conference on Fairness, Accountability, and Transparency*, 220–229.
