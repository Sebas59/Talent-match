import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, ErrorState, Loading, PageHead, Panel, Segmented, useAsync } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

const CAT = { auth: "Acceso", security: "Seguridad", data: "Datos", privacy: "Privacidad", matching: "Matching", admin: "Administración", development: "Desarrollo" };

export default function Audit() {
  const [cat, setCat] = useState("");
  const [extra, setExtra] = useState([]);
  const qs = new URLSearchParams({ limit: "100", ...(cat && { category: cat }) }).toString();
  const { data, error, loading, reload } = useApi(`/audit?${qs}`, [qs]);
  const [verify, setVerify] = useState(null);
  const [run, busy] = useAsync();
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const rows = [...(data || []), ...extra];
  const more = () => run(() => api(`/audit?${qs}&before_id=${rows[rows.length - 1].id}`)).then((r) => r && setExtra((x) => [...x, ...r]));
  return (
    <>
      <PageHead title="Auditoría" sub="Registro de eventos sin datos personales. Cada registro sella el anterior con SHA-256: alterar uno rompe la cadena."
                actions={<Button icon={ShieldCheck} loading={busy} onClick={() => run(() => api("/audit/verify")).then((v) => v && setVerify(v))}>Verificar integridad</Button>} />
      {verify && <><Alert tone={verify.valid ? "good" : "critical"} title={verify.valid ? "Cadena íntegra" : "Cadena alterada"}>
        {verify.valid ? `Se verificaron ${verify.checked} registros. Huella actual: ${verify.head?.slice(0, 16)}…` : `La verificación falló en el registro ${verify.broken_at}.`}</Alert><div style={{ height: 14 }} /></>}
      <div className="filters">
        <Segmented label="Categoría" value={cat} onChange={(v) => { setCat(v); setExtra([]); }} options={[{ value: "", label: "Todas" }, ...Object.entries(CAT).map(([k, l]) => ({ value: k, label: l }))]} />
      </div>
      <Panel flush>
        {loading && !data ? <Loading /> : (
          <div className="table-wrap"><table className="t">
            <thead><tr><th className="r">#</th><th>Fecha</th><th>Categoría</th><th>Acción</th><th>Actor</th><th>Recurso</th><th>Detalle</th><th>Huella</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}><td className="r num muted">{r.id}</td><td className="small">{fmtDateTime(r.ts)}</td>
                <td><Badge tone={r.category === "security" ? "warning" : r.category === "privacy" ? "violet" : undefined}>{CAT[r.category] || r.category}</Badge></td>
                <td className="small strong">{r.action}</td><td className="small">{r.actor_role || "anónimo"}</td>
                <td className="small">{r.resource}{r.resource_id ? <span className="muted"> {String(r.resource_id).slice(0, 8)}</span> : ""}</td>
                <td className="small muted">{r.detail || ""}</td><td className="xs muted num" title={r.hash}>{r.hash.slice(0, 10)}</td></tr>))}</tbody>
          </table></div>
        )}
      </Panel>
      {data && data.length === 100 && <div className="row" style={{ justifyContent: "center", marginTop: 12 }}><Button loading={busy} onClick={more}>Cargar más</Button></div>}
      <p className="muted xs" style={{ marginTop: 8 }}>Los actores se registran por identificador y rol; la IP se guarda seudonimizada con HMAC.</p>
    </>
  );
}
