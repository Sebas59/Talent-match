import { Link } from "react-router-dom";
import { CheckCircle2, Circle, FileUp, ShieldCheck, Sparkles } from "lucide-react";
import { useApi } from "../../hooks.js";
import { useAuth } from "../../auth.jsx";
import { Alert, Badge, Empty, ErrorState, Kpis, Loading, PageHead, Panel, Progress, Ring } from "../../ui/index.jsx";
import { fmtDate, fmtPct } from "../../format.js";

export default function Dashboard() {
  const { user } = useAuth();
  const { data: d, error, loading, reload } = useApi("/dashboard");
  if (loading && !d) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const steps = [
    { done: d.consent?.processing, label: "Autorizar el tratamiento de datos", to: "/app/privacidad" },
    { done: d.has_cv, label: "Cargar la hoja de vida", to: "/app/cv" },
    { done: d.profile_status === "published" || (d.has_cv && d.pending_review === 0), label: "Revisar lo extraído", to: "/app/perfil" },
    { done: d.profile_status === "published", label: "Publicar el perfil", to: "/app/perfil" },
  ];
  const next = steps.find((s) => !s.done);

  return (
    <>
      <PageHead title={`Hola, ${user.full_name.split(" ")[0]}`}
                sub="Su perfil profesional, sus oportunidades internas y su desarrollo, en un solo lugar." />
      {next ? (
        <Alert tone="info" title="Siguiente paso">
          <Link to={next.to}>{next.label}</Link>. Recursos Humanos solo ve su perfil cuando usted lo publica.
        </Alert>
      ) : d.pending_review > 0 && (
        <Alert tone="info" title={`${d.pending_review} elementos sin revisar`}>
          No se publican hasta que los confirme. <Link to="/app/perfil">Revisarlos</Link>.
        </Alert>
      )}
      <div style={{ height: 16 }} />
      <Kpis items={[
        { label: "Estado del perfil", value: d.profile_status === "published" ? "Publicado" : "Borrador",
          detail: d.profile_status === "published" ? "Visible para RR. HH." : "Solo usted lo ve" },
        { label: "Competencias confirmadas", value: d.confirmed_tech + d.confirmed_power,
          detail: `${d.confirmed_tech} técnicas, ${d.confirmed_power} power skills` },
        { label: "Por revisar", value: d.pending_review, detail: "Elementos extraídos sin confirmar" },
        { label: "Oportunidades ≥ 70 %", value: d.opportunities_70, detail: `de ${d.opportunities_total} cargos abiertos` },
      ]} />
      <div className="grid g-main">
        <div className="stack">
          <Panel title="Oportunidades compatibles" hint="Calculadas con la información que usted confirmó"
                 actions={<Link className="btn sm" to="/app/oportunidades">Ver todas</Link>} flush>
            {d.opportunities.length === 0 ? (
              <Empty icon={Sparkles} title="Aún no hay compatibilidad que mostrar">
                Confirme competencias en su perfil para calcular su compatibilidad con los cargos abiertos.
              </Empty>
            ) : (
              <ul className="list">
                {d.opportunities.map((o) => (
                  <li key={o.position_id}>
                    <div className="row between">
                      <div style={{ minWidth: 0 }}>
                        <Link to={`/app/oportunidades/${o.position_id}`} className="cell-title" style={{ textDecoration: "none", color: "inherit" }}>{o.title}</Link>
                        <div className="cell-sub">{o.project_name}{o.missing.length ? `. Le falta: ${o.missing.join(", ")}` : ""}</div>
                      </div>
                      <div className="row">
                        {!o.eligible && <Badge tone="warning">Obligatorios pendientes</Badge>}
                        <span className="score">{fmtPct(o.score)}</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Mis rutas de aprendizaje" actions={<Link className="btn sm" to="/app/desarrollo">Abrir</Link>} flush>
            {d.paths.length === 0 ? (
              <Empty title="Sin rutas activas">Puede crear una desde una oportunidad, o RR. HH. puede asignarle una.</Empty>
            ) : (
              <ul className="list">
                {d.paths.map((p) => (
                  <li key={p.id}>
                    <div className="row between"><span className="strong">{p.title}</span>
                      <span className="num small">{p.completed_items}/{p.total_items} · {p.progress} %</span></div>
                    <div style={{ marginTop: 8 }}><Progress value={p.progress} /></div>
                    {p.due_date && <div className="cell-sub" style={{ marginTop: 4 }}>Fecha objetivo: {fmtDate(p.due_date)}</div>}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Completitud del perfil">
            <div className="row" style={{ gap: 16, alignItems: "flex-start" }}>
              <Ring value={d.completeness} />
              <ul className="list" style={{ flex: 1 }}>
                {d.completeness_breakdown.map((c) => (
                  <li key={c.label} style={{ padding: "4px 0", border: 0 }} className="row small">
                    {c.done ? <CheckCircle2 size={15} color="var(--good)" aria-label="Hecho" /> : <Circle size={15} color="var(--ink-3)" aria-label="Pendiente" />}
                    <span className={c.done ? "" : "muted"}>{c.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Panel>
          <Panel title="Brechas más frecuentes" hint="En sus tres oportunidades más compatibles">
            {d.top_gaps.length === 0 ? <p className="muted small">Sin brechas detectadas.</p> : (
              <div className="tags">{d.top_gaps.map((g) => <span className="tag" key={g.name}>{g.name}
                <span className="muted xs">{g.kind === "power" ? "power skill" : g.kind === "certification" ? "certificación" : "técnica"}</span></span>)}</div>
            )}
          </Panel>
          <Panel title="Mis datos">
            <div className="stack small">
              <div className="row"><ShieldCheck size={16} color={d.consent?.processing ? "var(--good)" : "var(--warning)"} aria-hidden />
                {d.consent?.processing ? "Autorización de tratamiento vigente" : "Sin autorización de tratamiento"}</div>
              <div className="row"><FileUp size={16} aria-hidden />{d.consent?.external_ai ? "Autorizó IA externa (texto anonimizado)" : "Solo extracción local"}</div>
              {d.processes > 0 && <div className="row"><Sparkles size={16} aria-hidden />{d.processes} decisión(es) de RR. HH. sobre su perfil. <Link to="/app/oportunidades">Ver</Link></div>}
              <Link to="/app/privacidad" className="btn sm" style={{ alignSelf: "flex-start" }}>Gestionar privacidad</Link>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
