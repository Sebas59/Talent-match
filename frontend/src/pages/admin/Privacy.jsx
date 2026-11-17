import { useState } from "react";
import { ClipboardList } from "lucide-react";
import { patch } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Empty, ErrorState, Field, Loading, Modal, PageHead, Panel, Segmented, useAsync } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

const RSTATUS = { open: ["Abierta", "warning"], in_progress: ["En trámite", "info"], resolved: ["Resuelta", "good"], rejected: ["Rechazada", "critical"] };

export default function Privacy() {
  const [st, setSt] = useState("");
  const { data, error, loading, reload } = useApi(`/privacy/requests${st ? `?status=${st}` : ""}`, [st]);
  const [open, setOpen] = useState(null);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  return (
    <>
      <PageHead title="Solicitudes de privacidad" sub="Solicitudes de acceso, rectificación, supresión, revocatoria u oposición enviadas por los empleados." />
      <div className="filters"><Segmented label="Estado" value={st} onChange={setSt} options={[{ value: "", label: "Todas" }, { value: "open", label: "Abiertas" }, { value: "in_progress", label: "En trámite" }, { value: "resolved", label: "Resueltas" }]} /></div>
      <Panel flush>
        {loading && !data ? <Loading /> : data.length === 0 ? <Empty icon={ClipboardList} title="Sin solicitudes con este estado" /> : (
          <table className="t"><thead><tr><th>Solicitud</th><th>Titular</th><th>Recibida</th><th>Estado</th><th /></tr></thead>
            <tbody>{data.map((r) => (
              <tr key={r.id}><td><div className="cell-title">{r.type_label}</div><div className="cell-sub">{r.detail || "Sin detalle"}</div></td>
                <td className="small">{r.requester}<div className="cell-sub">{r.requester_email}</div></td>
                <td className="small">{fmtDateTime(r.created_at)}</td><td><Badge tone={RSTATUS[r.status][1]}>{RSTATUS[r.status][0]}</Badge></td>
                <td className="r">{(r.status === "open" || r.status === "in_progress") && <Button size="sm" onClick={() => setOpen(r)}>Gestionar</Button>}</td></tr>))}</tbody></table>
        )}
      </Panel>
      {open && <Resolve r={open} onClose={() => setOpen(null)} onDone={() => { setOpen(null); reload(); }} />}
    </>
  );
}

function Resolve({ r, onClose, onDone }) {
  const [status, setStatus] = useState("resolved");
  const [resolution, setResolution] = useState("");
  const executable = r.type === "deletion" || r.type === "revocation";
  const [execute, setExecute] = useState(executable);
  const [run, busy] = useAsync();
  return (
    <Modal title={`${r.type_label}: ${r.requester}`} sub={r.detail || undefined} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={resolution.trim().length < 5}
             onClick={() => run(() => patch(`/privacy/requests/${r.id}`, { status, resolution, execute: execute && status === "resolved" }), "Solicitud actualizada").then((x) => x && onDone())}>Guardar</Button></>}>
      <Field label="Estado"><select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="in_progress">En trámite</option><option value="resolved">Resuelta</option><option value="rejected">Rechazada</option></select></Field>
      <Field label="Respuesta al titular" help="La persona la verá en su espacio de privacidad. Se guarda cifrada.">
        <textarea className="textarea" value={resolution} maxLength={1000} onChange={(e) => setResolution(e.target.value)} /></Field>
      {executable && status === "resolved" && (
        <>
          <label className="check"><input type="checkbox" checked={execute} onChange={(e) => setExecute(e.target.checked)} />
            {r.type === "deletion" ? "Ejecutar la supresión del contenido del perfil y revocar la autorización" : "Revocar la autorización y retirar el perfil de RR. HH."}</label>
          {execute && <Alert tone="warning">La acción se ejecuta sin que usted vea el contenido del perfil y no se puede deshacer.</Alert>}
        </>
      )}
    </Modal>
  );
}
