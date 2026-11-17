const toDate = (v) => (v ? new Date(/Z|[+-]\d\d:\d\d$/.test(v) ? v : `${v}Z`) : null);

export const fmtDate = (v) => {
  const d = toDate(v);
  return d ? d.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "—";
};
export const fmtDateTime = (v) => {
  const d = toDate(v);
  return d ? d.toLocaleString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
};
export const fmtPct = (v, digits = 0) => (v == null ? "—" : `${Number(v).toFixed(digits)} %`);
export const fmtNum = (v) => (v == null ? "—" : Number(v).toLocaleString("es-CO"));
export const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

export const ORIGIN = {
  extracted: { label: "Encontrada en el documento", short: "Literal", tone: "neutral" },
  inferred: { label: "Inferida a partir de logros o contexto", short: "Inferida", tone: "info" },
  ai_external: { label: "Propuesta por IA externa con evidencia verificada", short: "IA externa", tone: "violet" },
  manual: { label: "Agregada por usted", short: "Manual", tone: "neutral" },
};
export const STATUS = {
  pending: { label: "Por revisar", tone: "warning" },
  confirmed: { label: "Confirmada", tone: "good" },
  rejected: { label: "Rechazada", tone: "muted" },
};
export const ENTRY_KIND = { experience: "Experiencia", education: "Formación", certification: "Certificaciones",
  language: "Idiomas" };
export const PROJECT_STATUS = { planning: "En planeación", active: "Activo", on_hold: "En pausa", closed: "Cerrado" };
export const EDU = ["No especificado", "Bachiller", "Técnico", "Tecnólogo", "Profesional (pregrado)",
  "Especialización", "Maestría", "Doctorado"];
export const DECISIONS = { shortlisted: "Preseleccionado", interview: "Entrevista", selected: "Seleccionado",
  on_hold: "En espera", not_selected: "No seleccionado" };
export const COMPONENTS = [
  { key: "technical", label: "Técnicas", var: "--c-tech" },
  { key: "power", label: "Power skills", var: "--c-power" },
  { key: "experience", label: "Experiencia", var: "--c-exp" },
  { key: "credentials", label: "Certificaciones y formación", var: "--c-cred" },
];
