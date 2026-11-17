import { useState } from "react";
import { Download, ShieldCheck, Trash2 } from "lucide-react";
import { del, download, post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Confirm, ErrorState, Field, Loading, Modal, PageHead, Panel, useAsync } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

const TYPES = [["access", "Acceso / copia de datos"], ["rectification", "Rectificación"], ["deletion", "Supresión de datos"],
  ["revocation", "Revocatoria de autorización"], ["objection", "Oposición o consulta"]];
const RSTATUS = { open: ["Abierta", "warning"], in_progress: ["En trámite", "info"], resolved: ["Resuelta", "good"], rejected: ["Rechazada", "critical"] };

export default function Privacy() {
  const policy = useApi("/consent/policy");
  const consent = useApi("/consent/me");
  const history = useApi("/consent/me/history");
  const reqs = useApi("/privacy/requests/me");
  const [processing, setProcessing] = useState(null);
  const [ai, setAi] = useState(null);
  const [newReq, setNewReq] = useState(false);
  const [wipe, setWipe] = useState(false);
  const [run, busy] = useAsync();
  if ((policy.loading && !policy.data) || (consent.loading && !consent.data)) return <Loading />;
  if (policy.error || consent.error) return <ErrorState error={policy.error || consent.error} />;
  const c = consent.data;
  const pol = policy.data;
  const proc = processing ?? c.processing;
  const ext = proc ? (ai ?? c.external_ai) : false;
  const changed = proc !== c.processing || ext !== c.external_ai;

  const save = () => run(() => post("/consent/me", { processing: proc, external_ai: ext, policy_version: pol.version }),
    proc ? "Autorización guardada" : "Autorización revocada; su perfil se retiró de RR. HH.").then((r) => {
    if (r) { consent.setData(r); history.reload(); setProcessing(null); setAi(null); }
  });

  return (
    <>
      <PageHead title="Privacidad y mis datos" sub="Usted decide si sus datos se tratan, si se usa IA externa y qué publica."
                actions={<Button icon={Download} onClick={() => run(() => download("/profiles/me/export", "mis-datos-talent-match.json"), "Descarga iniciada")}>Descargar mis datos</Button>} />
      <div className="grid g-main">
        <div className="stack">
          <Panel title="Autorizaciones" hint={c.granted_at ? `Último cambio: ${fmtDateTime(c.granted_at)} · política ${c.policy_version}` : "Aún no ha otorgado ninguna autorización"}>
            <div className="stack">
              <label className="check"><input type="checkbox" checked={proc} onChange={(e) => setProcessing(e.target.checked)} />
                <span><strong>Autorizo el tratamiento de mis datos para gestión del talento interno.</strong><br />
                  <span className="muted small">{pol.finalidades.join(" ")}</span></span></label>
              <label className="check" style={{ opacity: proc ? 1 : 0.5 }}>
                <input type="checkbox" checked={ext} disabled={!proc} onChange={(e) => setAi(e.target.checked)} />
                <span><strong>Autorizo, por separado, el uso de un proveedor externo de IA.</strong><br />
                  <span className="muted small">{pol.finalidad_opcional_ia_externa}</span></span></label>
              {c.processing && !proc && <Alert tone="warning">Al revocar, su perfil deja de ser visible para RR. HH. y no se procesarán nuevas hojas de vida.</Alert>}
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <Button variant="primary" disabled={!changed} loading={busy} onClick={save}>Guardar autorización</Button>
              </div>
            </div>
          </Panel>
          <Panel title="Solicitudes sobre mis datos" actions={<Button size="sm" onClick={() => setNewReq(true)}>Nueva solicitud</Button>} flush>
            {!reqs.data?.length ? <p className="muted small" style={{ padding: 18 }}>No ha enviado solicitudes. El administrador las atiende y usted ve aquí la respuesta.</p> : (
              <ul className="list">{reqs.data.map((r) => (
                <li key={r.id}>
                  <div className="row between"><span className="strong">{r.type_label}</span><Badge tone={RSTATUS[r.status][1]}>{RSTATUS[r.status][0]}</Badge></div>
                  {r.detail && <p className="small muted">{r.detail}</p>}
                  {r.resolution && <p className="small" style={{ marginTop: 4 }}>Respuesta: {r.resolution}</p>}
                  <div className="cell-sub">{fmtDateTime(r.created_at)}</div>
                </li>))}</ul>
            )}
          </Panel>
          <Panel title="Eliminar el contenido de mi perfil">
            <div className="row between wrap">
              <p className="small prose">Borra competencias, experiencia, formación e historial de análisis. Su cuenta se conserva. Esta acción no se puede deshacer.</p>
              <Button variant="danger" icon={Trash2} onClick={() => setWipe(true)}>Eliminar contenido</Button>
            </div>
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Quién accede a qué">
            <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{pol.quien_accede.map((x) => <li key={x}>{x}</li>)}</ul>
          </Panel>
          <Panel title="Datos que no se tratan"><p className="small">{pol.datos_no_tratados.join(" ")}</p></Panel>
          <Panel title="Historial de autorizaciones" flush>
            <ul className="list">{(history.data || []).map((h, i) => (
              <li key={i} className="small row between">
                <span>{fmtDateTime(h.granted_at)}</span>
                <span className="row">{h.processing ? <Badge tone="good" icon={ShieldCheck}>Tratamiento</Badge> : <Badge>Sin autorización</Badge>}
                  {h.external_ai && <Badge tone="violet">IA externa</Badge>}</span>
              </li>))}</ul>
          </Panel>
          <p className="muted xs">{pol.marco_referencia} Responsable: {pol.responsable}. Contacto: {pol.contacto}.</p>
        </div>
      </div>
      {newReq && <NewRequest onClose={() => setNewReq(false)} onDone={() => { setNewReq(false); reqs.reload(); }} />}
      {wipe && <Confirm title="Eliminar el contenido del perfil" danger confirmLabel="Eliminar definitivamente" onClose={() => setWipe(false)}
                        onConfirm={() => run(() => del("/profiles/me/data"), "Contenido del perfil eliminado")}>
        Se borrarán todas sus competencias, registros y análisis de hojas de vida, y el perfil quedará sin publicar.</Confirm>}
    </>
  );
}

function NewRequest({ onClose, onDone }) {
  const [type, setType] = useState("access");
  const [detail, setDetail] = useState("");
  const [run, busy] = useAsync();
  return (
    <Modal title="Nueva solicitud" sub="El administrador de la plataforma la atenderá." onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy}
             onClick={() => run(() => post("/privacy/requests", { type, detail }), "Solicitud enviada").then((r) => r && onDone())}>Enviar solicitud</Button></>}>
      <Field label="Tipo"><select className="select" value={type} onChange={(e) => setType(e.target.value)}>
        {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
      <Field label="Detalle (opcional)" help="Se guarda cifrado."><textarea className="textarea" maxLength={1000} value={detail} onChange={(e) => setDetail(e.target.value)} /></Field>
    </Modal>
  );
}
