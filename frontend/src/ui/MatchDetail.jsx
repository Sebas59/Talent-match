import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Alert, Badge, ComponentTable, RequirementList, ScoreAnatomy } from "./index.jsx";

/** Explicación completa de un resultado de compatibilidad (misma vista para empleado y RR. HH.). */
export default function MatchDetail({ m, audience = "hr" }) {
  const reqs = m.requirements || [];
  return (
    <div className="stack" style={{ gap: 20 }}>
      <div>
        <div className="row" style={{ alignItems: "flex-end", gap: 14, marginBottom: 12 }}>
          <div className="score-big">{m.score}<small>%</small></div>
          <div style={{ paddingBottom: 4 }}>
            {m.eligible
              ? <Badge tone="good" icon={CheckCircle2}>Cumple los requisitos obligatorios</Badge>
              : <Badge tone="warning" icon={AlertTriangle}>Requisitos obligatorios pendientes</Badge>}
          </div>
        </div>
        <ScoreAnatomy components={m.components} size="lg" legend />
      </div>
      {!m.eligible && m.mandatory_unmet?.length > 0 && (
        <Alert tone="warning" title={audience === "employee" ? "Para ser elegible le falta" : "No cumple"}>{m.mandatory_unmet.join(", ")}.</Alert>
      )}
      <div>
        <div className="section-title">Cómo se calculó</div>
        <ComponentTable components={m.components} />
        <ul className="small" style={{ margin: "10px 0 0", paddingLeft: 18, color: "var(--ink-2)" }}>
          {m.explanation.filter((e) => !/ puntos\.$/.test(e)).map((e) => <li key={e}>{e}</li>)}
        </ul>
      </div>
      {m.strengths?.length > 0 && (
        <div>
          <div className="section-title">Fortalezas</div>
          <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{m.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
      )}
      <div>
        <div className="section-title">Requisitos ({reqs.filter((r) => r.status === "met").length} de {reqs.length} cumplidos)</div>
        <RequirementList requirements={[...reqs].sort((a, b) => ({ missing: 0, partial: 1, met: 2 }[a.status] - { missing: 0, partial: 1, met: 2 }[b.status]))} />
      </div>
      <p className="muted xs">El puntaje resume información confirmada frente a los requisitos del cargo. No mide potencial ni desempeño, y no decide: la decisión la toma una persona de RR. HH.</p>
    </div>
  );
}
