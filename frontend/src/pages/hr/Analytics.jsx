import { useState } from "react";
import { useApi } from "../../hooks.js";
import { Badge, BarList, ErrorState, Kpis, Loading, PageHead, Panel, Segmented } from "../../ui/index.jsx";
import { GapBars } from "./Dashboard.jsx";

const STATUS_TONE = { crítica: "critical", escasa: "warning", cubierta: "good" };

export default function Analytics() {
  const filters = useApi("/analytics/filters");
  const [dept, setDept] = useState("");
  const [kind, setKind] = useState("");
  const [proj, setProj] = useState("");
  const qs = new URLSearchParams({ ...(dept && { department: dept }), ...(kind && { kind }), ...(proj && { project_id: proj }) }).toString();
  const skills = useApi(`/analytics/skills?${qs}`, [qs]);
  const positions = useApi(`/analytics/positions${proj ? `?project_id=${proj}` : ""}`, [proj]);
  const training = useApi("/analytics/training");
  const [view, setView] = useState("chart");
  if (skills.error) return <ErrorState error={skills.error} onRetry={skills.reload} />;
  const s = skills.data;
  return (
    <>
      <PageHead title="Analítica de talento" sub="Oferta: competencias confirmadas en perfiles publicados. Demanda: requisitos de cargos abiertos. Todo se calcula desde la base de datos." />
      <div className="filters">
        <select className="select" aria-label="Área" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">Todas las áreas</option>{filters.data?.departments.map((d) => <option key={d}>{d}</option>)}</select>
        <select className="select" aria-label="Proyecto" value={proj} onChange={(e) => setProj(e.target.value)}>
          <option value="">Todos los proyectos</option>{filters.data?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <Segmented label="Tipo de competencia" value={kind} onChange={setKind} options={[{ value: "", label: "Todas" }, { value: "tech", label: "Técnicas" }, { value: "power", label: "Power skills" }]} />
        <span className="spacer" />
        <Segmented label="Vista" value={view} onChange={setView} options={[{ value: "chart", label: "Gráfico" }, { value: "table", label: "Tabla" }]} />
      </div>
      {!s ? <Loading /> : (
        <>
          <Kpis items={[{ label: "Perfiles analizados", value: s.profiles }, { label: "Competencias distintas", value: s.distinct_skills },
            { label: "Demanda con oferta interna", value: `${s.coverage_pct} %` },
            { label: "Brechas críticas", value: s.gaps.filter((g) => g.status === "crítica").length, detail: "sin ningún perfil que la tenga" }]} />
          <div className="grid g2">
            <Panel title="Competencias más frecuentes" hint="Número de perfiles con la competencia confirmada">
              {view === "chart" ? <BarList rows={s.top.map((t) => ({ label: t.name, value: t.profiles, tip: `${t.profiles} perfiles, ${t.share} % del total`,
                color: t.kind === "power" ? "var(--c-power)" : "var(--c-tech)" }))} /> : (
                <table className="t"><thead><tr><th>Competencia</th><th>Tipo</th><th className="r">Perfiles</th><th className="r">%</th></tr></thead>
                  <tbody>{s.top.map((t) => <tr key={t.key}><td>{t.name}</td><td className="small">{t.kind === "power" ? "Power skill" : "Técnica"}</td><td className="r num">{t.profiles}</td><td className="r num">{t.share}</td></tr>)}</tbody></table>)}
            </Panel>
            <Panel title="Competencias escasas" hint="Demanda de cargos abiertos frente a oferta interna">
              {view === "chart" ? <GapBars gaps={s.scarce} /> : (
                <table className="t"><thead><tr><th>Competencia</th><th className="r">Demanda</th><th className="r">Oferta</th><th>Estado</th></tr></thead>
                  <tbody>{s.scarce.map((g) => <tr key={g.key}><td>{g.name}</td><td className="r num">{g.demand}</td><td className="r num">{g.supply}</td>
                    <td><Badge tone={STATUS_TONE[g.status]}>{g.status}</Badge></td></tr>)}</tbody></table>)}
            </Panel>
          </div>
          <div style={{ height: 16 }} />
          <div className="grid g-main">
            <Panel title="Disponibilidad de talento por cargo" hint="Última ejecución de matching" flush>
              {!positions.data ? <Loading /> : (
                <table className="t"><thead><tr><th>Cargo</th><th className="r">Elegibles</th><th className="r">Disponibles</th><th className="r">Promedio</th><th className="r">Mejor</th></tr></thead>
                  <tbody>{positions.data.map((p) => (
                    <tr key={p.position_id}><td><div className="cell-title">{p.title}</div><div className="cell-sub">{p.project}</div></td>
                      <td className="r num">{p.has_run ? `${p.eligible}/${p.evaluated}` : "—"}</td>
                      <td className="r num">{p.has_run ? p.available : "—"}</td>
                      <td className="r num">{p.avg_score != null ? `${p.avg_score} %` : "—"}</td>
                      <td className="r num">{p.best_score != null ? `${p.best_score} %` : "—"}</td></tr>))}</tbody></table>
              )}
            </Panel>
            <Panel title="Necesidades de capacitación" hint="Brechas de los 5 mejores perfiles de cada cargo">
              {!training.data ? <Loading /> : <BarList rows={training.data.needs.map((n) => ({ label: n.name, value: n.count, color: "var(--c-cred)", tip: `Aparece en ${n.count} resultados` }))}
                                                     empty="Ejecute matching para identificar necesidades." />}
            </Panel>
          </div>
          <div style={{ height: 16 }} />
          <Panel title="Todas las competencias demandadas" flush>
            <table className="t"><thead><tr><th>Competencia</th><th>Tipo</th><th className="r">Cargos que la piden</th><th className="r">Como obligatoria</th><th className="r">Perfiles que la tienen</th><th>Estado</th></tr></thead>
              <tbody>{s.gaps.map((g) => <tr key={g.key}><td>{g.name}</td><td className="small">{g.kind === "power" ? "Power skill" : "Técnica"}</td><td className="r num">{g.demand}</td>
                <td className="r num">{g.mandatory_in}</td><td className="r num">{g.supply}</td><td><Badge tone={STATUS_TONE[g.status]}>{g.status}</Badge></td></tr>)}</tbody></table>
          </Panel>
        </>
      )}
    </>
  );
}
