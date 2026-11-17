import { Brain, ClipboardCheck, Eye, FileLock2, Globe2, Handshake, Pencil, Scale, ShieldCheck, TriangleAlert } from "lucide-react";
import { useAuth } from "../../auth.jsx";
import { useApi } from "../../hooks.js";
import { Alert, BarList, ErrorState, Kpis, Loading, PageHead, Panel } from "../../ui/index.jsx";

const ICONS = { consent: Handshake, purpose: ClipboardCheck, protection: FileLock2, external_ai: Globe2, explainability: Eye,
  correction: Pencil, limits: TriangleAlert, bias: Scale, oversight: Brain, traceability: ShieldCheck };
const ORIGIN = { extracted: "Encontradas en el documento", inferred: "Inferidas", ai_external: "IA externa (verificadas)", manual: "Manuales" };

export default function Governance() {
  const { user } = useAuth();
  const card = useApi("/governance/card");
  const metrics = useApi(user.role !== "employee" ? "/governance/metrics" : null);
  const bench = useApi(user.role !== "employee" ? "/governance/benchmark" : null);
  if (card.loading && !card.data) return <Loading />;
  if (card.error) return <ErrorState error={card.error} />;
  const m = metrics.data;
  return (
    <>
      <PageHead title="Tarjeta ética y de gobernanza" sub="Cómo Talent Match usa la inteligencia artificial y qué controles protegen a las personas." />
      <Panel>
        <p className="principle">{card.data.principle}</p>
        <p className="small muted" style={{ marginTop: 8 }}>{card.data.disclaimer}</p>
      </Panel>
      <div style={{ height: 16 }} />
      <section className="panel">
        <div className="gov-list">
          {card.data.items.map((it) => { const I = ICONS[it.id] || ShieldCheck; return (
            <div className="gov-item" key={it.id}><I size={20} aria-hidden /><div><h3>{it.title}</h3><p>{it.body}</p></div></div>); })}
        </div>
      </section>
      {m && (
        <>
          <h2 style={{ margin: "28px 0 12px" }}>Indicadores en vivo</h2>
          <Kpis items={[
            { label: "Autorizaciones vigentes", value: m.consents_active, detail: `${m.external_ai_authorized} autorizan IA externa` },
            { label: "Análisis de CV", value: m.extractions, detail: `${m.external_extractions} con proveedor externo` },
            { label: "Competencias confirmadas", value: `${m.confirmed_pct} %`, detail: "del total extraído o agregado" },
            { label: "Decisiones humanas", value: m.human_decisions, detail: `${m.automatic_decisions} decisiones automáticas` },
          ]} />
          {m.fairness_alert && <Alert tone="warning" title="Alerta de equidad">La diferencia de puntaje promedio por tipo de documento supera 10 puntos ({m.fairness_gap}). Revise si el formato del CV está penalizando a algunas personas.</Alert>}
          <div className="grid g3" style={{ marginTop: 16 }}>
            <Panel title="Datos sensibles descartados" hint="Categorías detectadas; los valores nunca se guardan">
              <BarList rows={Object.entries(m.sensitive_discarded).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: k, value: v, color: "var(--c-exp)" }))} empty="Ninguno" />
            </Panel>
            <Panel title="Origen de las competencias">
              <BarList rows={Object.entries(m.skills_by_origin).map(([k, v]) => ({ label: ORIGIN[k] || k, value: v }))} />
            </Panel>
            <Panel title="Equidad por tipo de documento" hint={`Brecha actual: ${m.fairness_gap} puntos (alerta sobre 10)`}>
              <BarList rows={Object.entries(m.fairness_by_source).map(([k, v]) => ({ label: k, value: v, color: "var(--c-cred)" }))} max={100} format={(v) => `${v}`} empty="Sin resultados" />
            </Panel>
          </div>
          {bench.data?.available && (
            <Panel title="Evaluación de la extracción" hint={`Conjunto etiquetado de ${bench.data.n} CV ficticios (PDF texto, escaneado, imagen y JSON)`} className="" >
              <table className="t"><tbody>
                <tr><td>Precisión, competencias técnicas</td><td className="r num strong">{bench.data.precision_tecnica} %</td></tr>
                <tr><td>Exhaustividad, competencias técnicas</td><td className="r num strong">{bench.data.recall_tecnica} %</td></tr>
                <tr><td>Línea base (solo separar por comas)</td><td className="r num">{bench.data.baseline_recall_tecnica} %</td></tr>
                <tr><td>Precisión / exhaustividad, power skills</td><td className="r num">{bench.data.precision_power} % / {bench.data.recall_power} %</td></tr>
                <tr><td>Datos sensibles descartados correctamente</td><td className="r num">{bench.data.sensibles_ok} de {bench.data.n}</td></tr>
              </tbody></table>
              <p className="muted xs" style={{ marginTop: 8 }}>Muestra pequeña y sintética: indica el comportamiento del extractor, no su desempeño con hojas de vida reales.</p>
            </Panel>
          )}
        </>
      )}
    </>
  );
}
