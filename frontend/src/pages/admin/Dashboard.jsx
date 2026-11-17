import { Link } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";
import { useApi } from "../../hooks.js";
import { Badge, ErrorState, Kpis, Loading, PageHead, Panel } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

export const SEC_ACTION = { login_failed: "Inicio de sesión fallido", account_locked: "Cuenta bloqueada por intentos", forbidden: "Acceso denegado",
  refresh_rejected: "Renovación de sesión rechazada", cv_rejected: "Archivo rechazado", password_changed: "Cambio de contraseña",
  user_unlocked: "Cuenta desbloqueada", sessions_revoked: "Sesiones revocadas" };

function Activity({ days }) {
  const max = Math.max(1, ...days.map((d) => d.total));
  return (
    <div>
      <div className="cols" role="img" aria-label="Eventos de auditoría por día">
        {days.map((d) => (
          <div className="col" key={d.date} title={`${d.date}: ${d.total} eventos, ${d.security} de seguridad`}>
            <div className="stackbar" style={{ height: `${(d.total / max) * 100}%` }}>
              <i style={{ height: `${((d.total - d.security) / Math.max(d.total, 1)) * 100}%`, background: "var(--c-tech)" }} />
              {d.security > 0 && <i style={{ height: `${(d.security / d.total) * 100}%`, background: "var(--c-power)" }} />}
            </div>
            <span className="lbl">{d.date.slice(5)}</span>
          </div>
        ))}
      </div>
      <div className="anatomy-legend"><span><i className="swatch" style={{ background: "var(--c-tech)" }} />Eventos</span>
        <span><i className="swatch" style={{ background: "var(--c-power)" }} />Seguridad</span></div>
    </div>
  );
}

const Check = ({ ok, children }) => <div className="row small">{ok ? <CheckCircle2 size={16} color="var(--good)" aria-label="Correcto" /> : <XCircle size={16} color="var(--warning)" aria-label="Revisar" />}{children}</div>;

export default function Dashboard() {
  const { data: d, error, loading, reload } = useApi("/dashboard");
  if (loading && !d) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const s = d.system;
  return (
    <>
      <PageHead title="Administración de la plataforma" sub="Usuarios, seguridad, auditoría y configuración. Esta vista no da acceso al contenido de perfiles ni hojas de vida." />
      <Kpis items={[
        { label: "Usuarios", value: d.users_total, detail: `${d.users_by_role.employee} empleados, ${d.users_by_role.hr} RR. HH., ${d.users_by_role.admin} admin.` },
        { label: "Sesiones activas", value: d.active_sessions },
        { label: "Eventos (7 días)", value: d.audit_events_7d, detail: `${d.security_events_7d} de seguridad` },
        { label: "Solicitudes de privacidad", value: d.privacy_open, detail: `abiertas de ${d.privacy_total}` },
        { label: "Cadena de auditoría", value: s.chain.valid ? "Íntegra" : "Alterada", detail: `${s.chain.checked} registros verificados` },
      ]} />
      <div className="grid g-main">
        <div className="stack">
          <Panel title="Actividad registrada" hint="Últimos 7 días"><Activity days={d.activity_by_day} /></Panel>
          <Panel title="Eventos de seguridad recientes" flush actions={<Link className="btn sm" to="/admin/auditoria">Ver auditoría</Link>}>
            {d.security_recent.length === 0 ? <p className="muted small" style={{ padding: 18 }}>Sin eventos.</p> : (
              <table className="t"><tbody>{d.security_recent.map((e) => (
                <tr key={e.id}><td>{SEC_ACTION[e.action] || e.action}<div className="cell-sub">{e.resource}{e.detail ? ` · ${e.detail}` : ""}</div></td>
                  <td className="r small muted">{fmtDateTime(e.ts)}</td></tr>))}</tbody></table>
            )}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Estado del sistema" hint={`Versión ${s.version} · entorno ${s.environment}`}>
            <div className="stack" style={{ gap: 8 }}>
              <Check ok>Base de datos: {s.database}</Check>
              <Check ok={s.catalog.status === "ready"}>Catálogo: {s.catalog.status === "ready" ? `${s.catalog.jobs} ofertas y ${s.catalog.courses} cursos` : s.catalog.status}</Check>
              <Check ok={s.ocr_available}>OCR para CV escaneados {s.ocr_available ? "disponible" : "no instalado"}</Check>
              <Check ok>IA: {s.ai_providers_configured.length ? `proveedores ${s.ai_providers_configured.join(", ")}` : "modo local (sin proveedor externo)"}</Check>
              <Check ok={s.chain.valid}>Cadena de hashes de auditoría {s.chain.valid ? "íntegra" : `rota en el registro ${s.chain.broken_at}`}</Check>
              <Check ok={s.cookie_secure || s.environment !== "production"}>Cookie segura (HTTPS): {s.cookie_secure ? "sí" : "no (desarrollo)"}</Check>
              <Check ok={s.separate_blind_index_key}>Clave HMAC independiente {s.separate_blind_index_key ? "" : "(usa SECRET_KEY)"}</Check>
              <Check ok={!s.demo_mode || s.environment !== "production"}>Modo demostración {s.demo_mode ? "activo" : "inactivo"}</Check>
            </div>
          </Panel>
          <Panel title="Políticas activas" actions={<Link className="btn sm" to="/admin/configuracion">Configurar</Link>}>
            <dl className="kv small">
              <dt>IA externa</dt><dd>{d.settings.external_ai_allowed ? <Badge tone="violet">Permitida con autorización</Badge> : <Badge>Bloqueada</Badge>}</dd>
              <dt>Token de acceso</dt><dd>{s.token_minutes} min, sesión {s.refresh_days} días</dd>
              <dt>Límite de solicitudes</dt><dd>{s.rate_limit_per_minute}/min por IP</dd>
              <dt>Carga máxima</dt><dd>{s.max_upload_mb} MB</dd>
              <dt>Umbral de disponibilidad</dt><dd>{d.settings.availability_threshold} %</dd>
            </dl>
          </Panel>
        </div>
      </div>
    </>
  );
}
