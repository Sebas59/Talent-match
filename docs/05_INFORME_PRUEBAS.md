# Informe de pruebas · Talent Match V6

Fecha de ejecución: 2026-11-16. Entorno: Linux, Python 3.13.18, Node 22.23, Google Chrome (sin interfaz, con Playwright), Tesseract disponible. **Todos los resultados de este informe provienen de ejecuciones reales**; nada se reporta como exitoso sin haberse ejecutado.

## 1. Línea base (antes de V6)

| Proyecto | Resultado |
|---|---|
| V5 `pytest` | 8 de 8 aprobadas |
| Iteración 4 `pytest` | 13 de 13 aprobadas |
| Iteración 4 `scripts.evaluate` | precisión técnica 84,2 %, recall técnico 97,8 %, línea base 72,0 % |

## 2. Pruebas automatizadas del backend: 86 de 86 aprobadas (≈18 s)

| Archivo | Pruebas | Cubre |
|---|---:|---|
| `test_auth_security.py` | 13 | Cabeceras OWASP y CSP sin `unsafe-inline`, `no-store`, 401 sin token, `alg=none`, sin fuga de hash, TrustedHost, correo y nombre cifrados en BD, **logout que revoca el JWT**, rotación de refresh y detección de reutilización, bloqueo por intentos, desbloqueo por admin, contraseña débil, rate limit 429 |
| `test_roles_permissions.py` | 20 | Matriz de permisos por rol (18 combinaciones), admin sin acceso a perfiles, 403 auditados, dashboard por rol, RR. HH. no cambia roles |
| `test_invitations.py` | 4 | RR. HH. solo invita empleados, flujo completo (vista previa enmascarada, contraseña débil, un solo uso, login), duplicados, token inexistente |
| `test_employee_flow.py` | 6 | Carga bloqueada sin consentimiento, versión de política, flujo completo (CV → sensibles descartados → pendientes con origen → rechazo, confirmación, manual → publicación → vista de RR. HH. solo confirmada → oportunidades → reprocesar conserva decisiones), revocar despublica, validación de archivos (firma, extensión, 413, PDF sin texto), exportación |
| `test_ownership.py` | 5 | Un empleado no puede modificar competencias, registros ni ítems de aprendizaje de otro; RR. HH. no ve borradores |
| `test_extraction_ai.py` | 15 | 5 formatos de It4 con recall ≥ 80 % frente a `gold.json` (PDF texto, JSON×2, PDF escaneado y PNG con OCR), evidencia por competencia, valores sensibles nunca guardados, rechazo de archivos inválidos, IA externa solo con evidencia literal y texto minimizado, *fallback* si el proveedor falla, no se llama sin autorización, la API respeta la elección del empleado, contrato de Gemini, JSON inválido del LLM, regresión «Networking» |
| `test_matching_projects.py` | 7 | Normalización y redistribución de pesos, obligatorio cubierto por habilidad relacionada, experiencia y certificaciones, creación de proyecto/cargo con canonización ES↔EN, ejecución, orden, persistencia, pesos ad hoc, decisión con justificación obligatoria, decisión visible al empleado, plantillas, autocompletado |
| `test_development_privacy_audit.py` | 9 | Ruta desde un resultado de matching (ítems = brechas), progreso del empleado, recomendaciones justificadas (https, calificación > 4), ciclo de solicitud de privacidad con supresión ejecutada, borrado propio, cadena de auditoría íntegra y **detección de alteración**, auditoría sin datos personales, validación de configuración, desactivar revoca sesiones, admin no se degrada a sí mismo |
| `test_analytics_governance.py` | 5 | Indicadores coinciden con la BD, oferta/demanda (Kafka crítica), filtros, reportes de cargos y formación, tarjeta ética (10 ítems) y métricas, benchmark de extracción |
| `test_zz_demo_seed.py` | 2 | La semilla se niega en producción y no borra si hay usuarios no demo |

Las 8 pruebas de V5 se conservaron adaptadas al nuevo modelo (rutas y roles). Los CV etiquetados de It4 y su `gold.json` se reutilizan en `test_extraction_ai.py`.

## 3. Evaluación del matching (`python -m scripts.evaluate_matching`)

| Métrica | Resultado |
|---|---|
| Perfil esperado en el primer lugar (10 cargos) | 100 % |
| Perfil esperado entre los 3 primeros | 100 % |
| MRR | 1,0 |
| Estabilidad del ranking con pesos ±10 puntos (tau de Kendall) | promedio 0,983, mínimo 0,897 |
| Propiedades verificadas | 6 de 6: pesos suman 1, redistribución, monotonía, equivalencia ES↔EN, obligatorio quita elegibilidad, contrato sin atributos personales |

**Lectura correcta:** la referencia se construyó con datos sintéticos alineados a cada cargo. Mide la coherencia interna del motor, **no** su validez predictiva con personas reales.

## 4. Evaluación de la extracción (`python -m scripts.evaluate_extraction`)

| Métrica | It4 | V6 |
|---|---:|---:|
| Precisión técnica | 84,2 % | 84,5 % |
| Exhaustividad técnica | 97,8 % | 100 % |
| Línea base (separar por comas) | 72,0 % | 74,2 % |
| Precisión / exhaustividad power skills | 95,0 / 100 % | 100 / 100 % |
| Años, formación y sensibles correctos | 5/5, 5/5, 5/5 | 5/5, 5/5, 5/5 |

La mejora se debe a la corrección de «Networking» (sección 6). Muestra de 5 CV ficticios: no es representativa de hojas de vida reales.

## 5. Integración frontend/backend en navegador real (Chrome sin interfaz)

Recorrido de las 21 pantallas de los tres roles más un flujo completo con clics reales:

| Paso | Resultado |
|---|---|
| Hoja de vida bloqueada sin consentimiento | OK |
| Otorgar consentimiento desde *Privacidad* | OK |
| Cargar `cv_demo_sofia_arango.pdf`, ver resultado y sensibles descartados | OK |
| Confirmar competencias (técnicas y power skills) y publicar | OK |
| RR. HH. ejecuta matching y Sofía aparece | OK |
| Registrar decisión justificada | OK |
| Asignar ruta de aprendizaje desde el resultado | OK (después de corregir el error 2) |
| Comparar dos perfiles | OK |
| Crear proyecto y cargo con requisitos | OK |
| Empleada marca avance de su ruta | OK |
| Crear invitación, aceptarla en otra sesión e iniciar sesión | OK |
| Recargar la página conserva la sesión (cookie de refresh) | OK en los tres roles |
| Vista móvil (390 px) y menú plegable | OK |
| Errores de JavaScript o violaciones de CSP en consola | Ninguno |

## 6. Errores encontrados y corregidos

| # | Error | Dónde | Corrección |
|---|---|---|---|
| 1 | «Networking» (redes) se clasificaba como la power skill «Relaciones interpersonales» y aparecía como brecha crítica aunque había oferta | Catálogo heredado de It4 | Lista `BARE_TECHNICAL` en `canonical_soft` + prueba de regresión |
| 2 | El modal «Asignar ruta» se abría detrás del panel lateral y no se podía usar | Frontend (z-index) | Capa de modales por encima del panel |
| 3 | Un obligatorio cubierto solo por una habilidad «relacionada» (Git para CI/CD) se daba por cumplido | Motor de matching | Umbral de elegibilidad 0,7 para obligatorios |
| 4 | La barra de anatomía del puntaje no se veía en las tablas | CSS | Contenedor flexible correcto |
| 5 | La explicación repetía las líneas de la tabla de cálculo | Vista de detalle | Filtrado en la interfaz |
| 6 | La comprobación de sesión sin cookie generaba un 401 en consola | Endpoint de refresh | Responde 204 cuando no hay sesión |
| 7 | La prueba de la semilla se omitía por el orden de ejecución | Suite de pruebas | Reordenada; ahora se ejecuta |
| 8 | Puntajes de 100 % poco realistas en la demo | Datos demo | Requisitos deseables adicionales que nadie cubre del todo |

## 7. Instalación limpia

Desde el ZIP generado: `setup_env` → `seed_demo --reset` → `uvicorn` → `/health` con catálogo listo → SPA responde 200 → `pytest` 86/86 → `evaluate_matching`. Todo OK (en Linux).

## 8. Limitaciones pendientes (no se presentan como resueltas)

- **Windows:** `iniciar.ps1` y las instrucciones están escritas para PowerShell, pero **no se ejecutaron en Windows** en este entorno. El código evita dependencias exclusivas de Linux.
- **Proveedores externos de IA:** probados con respuestas simuladas; **no** contra las APIs reales de Anthropic y Gemini (no había claves).
- **PostgreSQL:** preparado, pero **no** verificado con un servidor real.
- **Migraciones:** `create_all` reproducible; falta Alembic para evolucionar el esquema en producción.
- **Envío de invitaciones:** el enlace se muestra para copiarlo; no hay servidor de correo.
- **Rate limit en memoria:** válido para una instancia; con varias se requiere Redis.
- **Validez del matching y de la extracción:** evaluadas con datos sintéticos y muestras pequeñas; falta validación con usuarios reales de RR. HH.
- **Cumplimiento normativo:** la aplicación implementa controles alineados con la Ley 1581 de 2012, pero no constituye una certificación; la validación jurídica corresponde al responsable del tratamiento.
- **Accesibilidad:** foco visible, etiquetas, reducción de movimiento y texto junto al color están implementados, pero no se hizo una auditoría formal con lector de pantalla.
