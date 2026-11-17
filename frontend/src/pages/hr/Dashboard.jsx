import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../../hooks.js";
import { Badge, BarList, Empty, ErrorState, Kpis, Loading, PageHead, Panel, Progress } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

const ACTION = { match_run: "ejecutó un matching", hr_decision: "registró una decisión", position_created: "creó un cargo",
  project_created: "creó un proyecto", path_assigned: "asignó una ruta de aprendizaje", profile_published: "publicó su perfil",
  invitation_created: "envió una invitación", invitation_accepted: "aceptó su invitación" };

export function GapBars({ gaps }) {
  if (!gaps?.length) return <p className="muted small">Sin brechas: la oferta cubre la demanda de los cargos abiertos.</p>;
  const max = Math.max(...gaps.map((g) => Math.max(g.demand, g.supply)), 1);
  return (
    <div>
      <div className="anatomy-legend" style={{ marginTop: 0, marginBottom: 10 }}>
        <span><i className="swatch" style={{ background: "var(--c-power)" }} />Cargos que la piden</span>
        <span><i className="swatch" style={{ background: "var(--c-tech)" }} />Perfiles que la tienen</span>
      </div>
      <div className="bars">
        {gaps.map((g) => (
          <div className="bar-row dual" key={g.key} title={`${g.name}: demanda ${g.demand}, oferta ${g.supply}`}>
            <span className="label">{g.name}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(g.demand / max) * 100}%`, background: "var(--c-power)" }} />
              <div className="bar-fill" style={{ width: `${Math.max(g.supply ? 1 : 0, (g.supply / max) * 100)}%`, background: "var(--c-tech)" }} />
            </div>
            <span className="val">{g.status === "crítica" ? <Badge tone="critical">0</Badge> : `${g.supply}/${g.demand}`}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: d, error, loading, reload } = useApi("/dashboard");
  const nav = useNavigate();
  if (loading && !d) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  return (
    <>
      <PageHead title="Talento interno" sub="Estado de la oferta de competencias frente a lo que piden los proyectos."
                actions={<><Link className="btn" to="/rrhh/invitaciones">Invitar empleados</Link><Link className="btn primary" to="/rrhh/matching">Ejecutar matching</Link></>} />
      <Kpis items={[
        { label: "Empleados activos", value: d.employees, detail: `${d.pending_invitations} invitaciones pendientes` },
        { label: "Perfiles publicados", value: d.published_profiles, detail: `${d.draft_profiles} en borrador` },
        { label: "Competencias confirmadas", value: d.distinct_confirmed_skills, detail: "distintas en la organización" },
        { label: "Proyectos activos", value: d.active_projects, detail: `${d.open_positions} cargos abiertos` },
        { label: "Movilidad interna", value: d.mobility_opportunities, detail: "perfil-cargo elegibles sobre el umbral" },
        { label: "Brechas críticas", value: d.critical_gaps, detail: `${d.coverage_pct} % de la demanda tiene oferta` },
      ]} />
      <div className="grid g-main">
        <div className="stack">
          <Panel title="Disponibilidad por cargo" hint="Según la última ejecución de matching de cada cargo" flush>
            {d.positions.length === 0 ? <Empty title="No hay cargos abiertos" action={<Link className="btn primary" to="/rrhh/proyectos">Crear proyecto</Link>} /> : (
              <div className="table-wrap"><table className="t">
                <thead><tr><th>Cargo</th><th className="r">Vacantes</th><th className="r">Elegibles</th><th className="r">Disponibles</th><th className="r">Mejor</th><th>Decisiones</th></tr></thead>
                <tbody>{d.positions.map((p) => (
                  <tr key={p.position_id} className="clickable" onClick={() => nav(`/rrhh/matching?position=${p.position_id}`)}>
                    <td><div className="cell-title">{p.title}</div><div className="cell-sub">{p.project}</div></td>
                    <td className="r num">{p.openings}</td>
                    <td className="r num">{p.has_run ? p.eligible : "—"}</td>
                    <td className="r num">{p.has_run ? p.available : <Badge>Sin ejecutar</Badge>}</td>
                    <td className="r num">{p.best_score != null ? `${p.best_score} %` : "—"}</td>
                    <td>{p.decisions ? <Badge tone="accent">{p.decisions}</Badge> : <span className="muted small">Ninguna</span>}</td>
                  </tr>))}</tbody>
              </table></div>
            )}
          </Panel>
          <Panel title="Brechas de competencias" hint="Requisitos de cargos abiertos con poca o ninguna oferta interna"
                 actions={<Link className="btn sm" to="/rrhh/analitica">Analítica</Link>}>
            <GapBars gaps={d.gaps} />
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Competencias más frecuentes" hint="Perfiles publicados que las tienen confirmadas">
            <BarList rows={d.top_skills.map((s) => ({ label: s.name, value: s.profiles, color: s.kind === "power" ? "var(--c-power)" : "var(--c-tech)",
              tip: `${s.profiles} perfiles (${s.share} %)` }))} />
          </Panel>
          <Panel title="Formación en curso">
            <div className="row between small"><span>{d.training.active} rutas activas, {d.training.completed} completadas</span>
              <span className="num strong">{d.training.avg_progress} %</span></div>
            <div style={{ marginTop: 8 }}><Progress value={d.training.avg_progress} /></div>
            <p className="muted xs" style={{ marginTop: 6 }}>{d.training.items_completed} de {d.training.items} actividades terminadas.</p>
          </Panel>
          <Panel title="Actividad reciente" flush>
            {d.activity.length === 0 ? <p className="muted small" style={{ padding: 18 }}>Sin actividad.</p> : (
              <ul className="list">{d.activity.map((a) => (
                <li key={a.id} className="small"><strong>{a.actor}</strong> {ACTION[a.action] || a.action}
                  <div className="cell-sub">{fmtDateTime(a.ts)}</div></li>))}</ul>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
