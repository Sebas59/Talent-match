"""Aviso de privacidad (V5 + Iteración 4). Se muestra ANTES de cualquier tratamiento.

Nota: el texto describe controles técnicos implementados. No constituye una certificación de
cumplimiento normativo; la conformidad legal debe validarla el responsable del tratamiento.
"""
from app.core.config import get_settings

PURPOSES = [
    "Construir y mantener un perfil profesional interno a partir de la hoja de vida.",
    "Calcular la compatibilidad con cargos y proyectos internos (movilidad interna).",
    "Identificar brechas de competencias y recomendar rutas de formación.",
    "Generar indicadores agregados de talento para la planeación de Recursos Humanos.",
]
EXTERNAL_AI_PURPOSE = ("Enviar el texto de la hoja de vida, sin correo, teléfono, URLs ni datos sensibles detectados, "
                       "a un proveedor externo de IA (Anthropic Claude o Google Gemini, según la configuración) "
                       "únicamente para mejorar la extracción de competencias.")


def policy_document() -> dict:
    s = get_settings()
    return {
        "version": s.consent_policy_version,
        "responsable": s.data_controller,
        "contacto": str(s.data_contact_email),
        "finalidades": PURPOSES,
        "finalidad_opcional_ia_externa": EXTERNAL_AI_PURPOSE,
        "datos_tratados": ["Nombre y correo corporativo (cifrados en reposo)",
                           "Competencias técnicas y power skills", "Experiencia laboral", "Formación y certificaciones",
                           "Idiomas"],
        "datos_no_tratados": ["Documento de identidad, fecha de nacimiento, edad, sexo/género, estado civil, religión, "
                              "origen, salud, afiliación política o sindical, fotografía, dirección y referencias de "
                              "terceros: se detectan y descartan, solo se registra la categoría.",
                              "El archivo original del CV no se almacena; solo su huella SHA-256."],
        "quien_accede": ["Usted: todo su perfil, incluido lo no publicado.",
                         "Recursos Humanos: solo la información que usted confirme y publique.",
                         "Administración: no accede al contenido de perfiles ni hojas de vida."],
        "derechos": ["Conocer y descargar sus datos.", "Corregir la información extraída.",
                     "Retirar la publicación del perfil en cualquier momento.",
                     "Revocar la autorización y solicitar la supresión de sus datos.",
                     "Recibir explicación de los resultados de compatibilidad.",
                     "Que ninguna decisión laboral se tome solo con el resultado automático."],
        "retencion_dias": s.retention_days,
        "marco_referencia": "Elaborado tomando como referencia la Ley Estatutaria 1581 de 2012 y el Decreto 1377 de 2013 "
                            "(Colombia). Proyecto académico: la validación jurídica corresponde al responsable.",
    }
