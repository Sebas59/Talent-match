import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Cpu, FileUp, Globe2, ShieldOff } from "lucide-react";
import { upload } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Empty, ErrorState, Loading, PageHead, Panel, useToast } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

const SOURCE = { "pdf-texto": "PDF con texto", "pdf-escaneado": "PDF escaneado (OCR)", imagen: "Imagen (OCR)", json: "JSON" };
const PHASES = ["Validando el archivo", "Leyendo el texto", "Descartando datos sensibles", "Identificando competencias, experiencia y formación"];

export default function Cv() {
  const consent = useApi("/consent/me");
  const runs = useApi("/profiles/me/extractions");
  const toast = useToast();
  const nav = useNavigate();
  const input = useRef(null);
  const [file, setFile] = useState(null);
  const [over, setOver] = useState(false);
  const [phase, setPhase] = useState(-1);
  const [err, setErr] = useState("");

  if ((consent.loading && !consent.data) || (runs.loading && !runs.data)) return <Loading />;
  if (consent.error) return <ErrorState error={consent.error} onRetry={consent.reload} />;
  const c = consent.data;
  const last = runs.data?.[0];

  function pick(f) {
    setErr("");
    if (!f) return;
    if (!/\.(pdf|json|png|jpe?g)$/i.test(f.name)) { setErr("Formato no permitido. Use PDF, JSON, PNG o JPG."); return; }
    if (f.size > 5 * 1024 * 1024) { setErr("El archivo supera 5 MB."); return; }
    setFile(f);
  }

  async function send() {
    setErr("");
    setPhase(0);
    const timer = setInterval(() => setPhase((p) => Math.min(p + 1, PHASES.length - 1)), 700);
    try {
      await upload("/profiles/me/cv", file);
      toast("Hoja de vida analizada. Revise los resultados.");
      setFile(null);
      await runs.reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      clearInterval(timer);
      setPhase(-1);
    }
  }

  return (
    <>
      <PageHead title="Hoja de vida" sub="Cargue su CV para construir un perfil preliminar. El archivo se procesa en memoria y no se almacena." />
      {!c.processing ? (
        <Panel>
          <Empty icon={ShieldOff} title="Primero autorice el tratamiento de sus datos"
                 action={<Link className="btn primary" to="/app/privacidad">Revisar la autorización</Link>}>
            Sin su autorización no se procesa ninguna hoja de vida. Puede retirarla cuando quiera.
          </Empty>
        </Panel>
      ) : (
        <div className="grid g-main">
          <div className="stack">
            <Panel title={last ? "Actualizar hoja de vida" : "Cargar hoja de vida"}
                   hint="Lo que ya confirmó o rechazó se conserva; lo nuevo llega como «por revisar».">
              <div className={`drop ${over ? "over" : ""}`} role="button" tabIndex={0}
                   onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
                   onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                   onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}>
                <FileUp size={26} color="var(--accent)" aria-hidden />
                <p className="strong" style={{ marginTop: 8 }}>{file ? file.name : "Arrastre su archivo o haga clic para elegirlo"}</p>
                <p className="muted small">{file ? `${(file.size / 1024).toFixed(0)} KB` : "PDF (con texto o escaneado), JSON, PNG o JPG. Máximo 5 MB."}</p>
                <input ref={input} type="file" hidden accept=".pdf,.json,.png,.jpg,.jpeg" onChange={(e) => pick(e.target.files[0])} />
              </div>
              {err && <div style={{ marginTop: 12 }}><Alert tone="critical">{err}</Alert></div>}
              {phase >= 0 ? (
                <div className="steps" style={{ marginTop: 16 }} aria-live="polite">
                  {PHASES.map((p, i) => (
                    <div key={p} className={`step ${i < phase ? "done" : i === phase ? "now" : ""}`}>
                      {i < phase ? <CheckCircle2 size={16} /> : <span className="spin" style={{ visibility: i === phase ? "visible" : "hidden" }} />}{p}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="row" style={{ marginTop: 14, justifyContent: "flex-end" }}>
                  {file && <Button variant="ghost" onClick={() => setFile(null)}>Quitar</Button>}
                  <Button variant="primary" disabled={!file} onClick={send}>Analizar hoja de vida</Button>
                </div>
              )}
            </Panel>
            {last && <ExtractionResult r={last} onReview={() => nav("/app/perfil")} />}
          </div>
          <div className="stack">
            <Panel title="Cómo se procesará">
              <div className="stack small">
                <div className="row"><Cpu size={16} aria-hidden /><span><strong>Extracción local</strong>: siempre se ejecuta, sin enviar datos fuera de la organización.</span></div>
                <div className="row"><Globe2 size={16} aria-hidden />
                  <span>{c.external_ai
                    ? <>Autorizó <strong>IA externa</strong>: si la organización la tiene configurada, se envía el texto sin correo, teléfono, URLs ni datos sensibles. Solo se aceptan resultados con evidencia literal.</>
                    : <>No autorizó IA externa. Puede cambiarlo en <Link to="/app/privacidad">Privacidad</Link>.</>}</span></div>
                <p className="muted xs">Se detectan y descartan documento de identidad, fecha de nacimiento, edad, estado civil, género, religión, salud, dirección, fotografía y referencias.</p>
              </div>
            </Panel>
            <Panel title="Historial de análisis" flush>
              {runs.data.length === 0 ? <p className="muted small" style={{ padding: 18 }}>Aún no ha cargado ninguna hoja de vida.</p> : (
                <ul className="list">
                  {runs.data.map((r) => (
                    <li key={r.id} className="small">
                      <div className="row between"><span>{fmtDateTime(r.created_at)}</span>
                        <Badge tone={r.external_used ? "violet" : "neutral"}>{r.external_used ? `IA externa: ${r.provider}` : "Local"}</Badge></div>
                      <div className="muted xs">{SOURCE[r.source_type] || r.source_type} · {r.stats.tech} técnicas, {r.stats.power} power skills</div>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}

function ExtractionResult({ r, onReview }) {
  return (
    <Panel title="Resultado del último análisis" hint={fmtDateTime(r.created_at)}
           actions={<Button variant="primary" onClick={onReview}>Revisar y confirmar</Button>}>
      <div className="stack">
        <div className="row wrap">
          <Badge tone={r.external_used ? "violet" : "accent"} icon={r.external_used ? Globe2 : Cpu}>
            {r.external_used ? `Proveedor externo: ${r.provider} (${r.provider_model})` : "Extracción local (sin proveedor externo)"}
          </Badge>
          <Badge>{SOURCE[r.source_type] || r.source_type}</Badge>
          {r.ocr_used && <Badge tone="info">Se usó OCR</Badge>}
          <Badge>{r.pages} {r.pages === 1 ? "página" : "páginas"}</Badge>
        </div>
        <div className="kpis" style={{ marginBottom: 0 }}>
          <div className="kpi"><div className="v">{r.stats.extracted}</div><div className="l">Encontradas literalmente</div></div>
          <div className="kpi"><div className="v">{r.stats.inferred}</div><div className="l">Inferidas</div><div className="d">Requieren su criterio</div></div>
          <div className="kpi"><div className="v">{r.stats.experience}</div><div className="l">Experiencias</div></div>
          <div className="kpi"><div className="v">{r.stats.education + r.stats.certifications}</div><div className="l">Formación y certificaciones</div></div>
        </div>
        {r.sensitive_categories.length > 0 && (
          <Alert tone="good" title="Datos sensibles descartados">
            Se detectaron y no se guardaron: {r.sensitive_categories.join(", ")}. Solo queda registro de la categoría.
          </Alert>
        )}
        {r.suggested?.years_experience > 0 && (
          <p className="small">Experiencia calculada a partir de las fechas: <strong className="num">{r.suggested.years_experience} años</strong>
            {r.suggested.education_label ? <>; formación detectada: <strong>{r.suggested.education_label}</strong></> : null}. Puede ajustarlas en su perfil.</p>
        )}
        {r.warnings.filter(Boolean).length > 0 && (
          <Alert tone="warning" title="Advertencias del análisis">
            <ul style={{ margin: 0, paddingLeft: 18 }}>{r.warnings.filter(Boolean).map((w) => <li key={w}>{w}</li>)}</ul>
          </Alert>
        )}
        <p className="muted xs">{r.method}. La confianza mostrada en cada elemento es heurística y no una probabilidad estadística.</p>
      </div>
    </Panel>
  );
}
