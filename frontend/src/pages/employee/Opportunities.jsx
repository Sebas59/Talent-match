import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ExternalLink, GraduationCap, Sparkles } from "lucide-react";
import { post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Drawer, Empty, ErrorState, Loading, MiniScore, PageHead, Panel, SearchInput, Segmented,
  Tabs, useAsync } from "../../ui/index.jsx";
import MatchDetail from "../../ui/MatchDetail.jsx";
import { fmtDate } from "../../format.js";
import { norm } from "../../text.js";

export function CourseList({ recs }) {
  if (!recs?.length) return <p className="muted small">Sin brechas que requieran formación.</p>;
  return (
    <div className="stack" style={{ gap: 12 }}>
      {recs.map((r) => (
        <div key={r.skill} style={{ borderBottom: "1px solid var(--line-2)", paddingBottom: 10 }}>
          <div className="row"><span className="strong">{r.skill}</span>
            {r.importance === "mandatory" && <Badge tone="accent">Obligatorio en el cargo</Badge>}
            <Badge>{r.kind === "power" ? "Power skill" : r.kind === "certification" ? "Certificación" : "Técnica"}</Badge></div>
          {r.courses.length === 0 ? <p className="muted xs" style={{ marginTop: 4 }}>{r.note}</p> : r.courses.map((c) => (
            <div key={c.url} className="row between small" style={{ marginTop: 6 }}>
              <div style={{ minWidth: 0 }}>
                <a href={c.url} target="_blank" rel="noopener noreferrer" className="row" style={{ gap: 5 }}>{c.course_title}<ExternalLink size={13} aria-hidden /></a>
                <div className="muted xs">{c.platform} · {c.provider} · {c.level} · {c.hours} h{c.hours_estimated ? " (estimado)" : ""}</div>
              </div>
              <span className="num xs muted" title="Calificación en el dataset">★ {c.rating.toFixed(1)}</span>
            </div>
          ))}
        </div>
      ))}
      <p className="muted xs">Cursos tomados de los datasets del proyecto (Coursera.csv, Udemy_Courses.xlsx). Disponibilidad y precio no verificados.</p>
    </div>
  );
}

function OpportunityDrawer({ id, onClose }) {
  const { data: m, error, loading } = useApi(`/opportunities/${id}`);
  const [run, busy] = useAsync();
  const nav = useNavigate();
  return (
    <Drawer title={m ? m.title : "Oportunidad"} sub={m ? `${m.project_name} · ${m.project_area}` : ""} onClose={onClose}>
      {loading && <Loading label="Calculando su compatibilidad…" />}
      {error && <ErrorState error={error} />}
      {m && (
        <>
          {m.description && <p className="small prose">{m.description}</p>}
          <MatchDetail m={m} audience="employee" />
          <div>
            <div className="row between" style={{ marginBottom: 8 }}>
              <div className="section-title" style={{ margin: 0 }}>Formación recomendada para sus brechas</div>
              {m.gaps.length > 0 && (
                <Button size="sm" icon={GraduationCap} loading={busy}
                        onClick={() => run(() => post("/development/me/paths", { position_id: m.position_id }), "Ruta de aprendizaje creada").then((r) => r && nav("/app/desarrollo"))}>
                  Crear mi ruta de aprendizaje</Button>)}
            </div>
            <CourseList recs={m.recommendations} />
          </div>
        </>
      )}
    </Drawer>
  );
}

export default function Opportunities() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data, error, loading, reload } = useApi("/opportunities");
  const procs = useApi("/opportunities/processes");
  const [tab, setTab] = useState("open");
  const [q, setQ] = useState("");
  const [only, setOnly] = useState("all");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const items = data.items.filter((o) => (!q || norm(`${o.title} ${o.project_name}`).includes(norm(q)))
    && (only === "all" || (only === "eligible" ? o.eligible : o.score >= 70)));
  return (
    <>
      <PageHead title="Oportunidades internas" sub="Su compatibilidad con los cargos abiertos de los proyectos de la organización. Solo usted ve estos resultados." />
      {data.confirmed_skills === 0 && <><Alert tone="info" title="Aún no hay datos confirmados">
        La compatibilidad usa solo lo que usted confirma. <Link to="/app/perfil">Revise su perfil</Link>.</Alert><div style={{ height: 14 }} /></>}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "open", label: "Cargos abiertos", count: data.items.length },
        { value: "proc", label: "Mis procesos", count: procs.data?.length ?? 0 }]} />
      {tab === "open" ? (
        <>
          <div className="filters">
            <SearchInput value={q} onChange={setQ} placeholder="Buscar cargo o proyecto" />
            <Segmented label="Filtrar" value={only} onChange={setOnly} options={[{ value: "all", label: "Todos" },
              { value: "eligible", label: "Cumplo obligatorios" }, { value: "70", label: "70 % o más" }]} />
          </div>
          <Panel flush>
            {items.length === 0 ? <Empty icon={Sparkles} title="No hay cargos con ese filtro">Pruebe con otro filtro o búsqueda.</Empty> : (
              <div className="table-wrap"><table className="t">
                <thead><tr><th>Cargo</th><th>Proyecto</th><th>Compatibilidad</th><th>Le falta</th><th /></tr></thead>
                <tbody>
                  {items.map((o) => (
                    <tr key={o.position_id} className="clickable" onClick={() => nav(`/app/oportunidades/${o.position_id}`)}>
                      <td><div className="cell-title">{o.title}</div><div className="cell-sub">{o.seniority || ""}{o.openings > 1 ? ` · ${o.openings} vacantes` : ""}</div></td>
                      <td><div>{o.project_name}</div><div className="cell-sub">{o.project_area}</div></td>
                      <td><MiniScore score={o.score} components={o.components} /></td>
                      <td className="small">{o.mandatory_unmet.length ? <Badge tone="warning">{o.mandatory_unmet.length} obligatorio(s)</Badge> : null}
                        <span className="muted"> {o.missing.slice(0, 3).join(", ") || "Nada"}</span></td>
                      <td className="r"><Button size="sm" onClick={(e) => { e.stopPropagation(); nav(`/app/oportunidades/${o.position_id}`); }}>Ver detalle</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
          </Panel>
        </>
      ) : (
        <Panel flush>
          {!procs.data?.length ? <Empty title="Sin procesos">Cuando RR. HH. registre una decisión sobre su perfil, aparecerá aquí con su justificación.</Empty> : (
            <ul className="list">
              {procs.data.map((p) => (
                <li key={`${p.position_id}-${p.created_at}`}>
                  <div className="row between"><span className="strong">{p.position_title}</span><Badge tone="accent">{p.label}</Badge></div>
                  <p className="small" style={{ marginTop: 4, color: "var(--ink-2)" }}>{p.justification}</p>
                  <div className="cell-sub">{fmtDate(p.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
      {id && <OpportunityDrawer id={id} onClose={() => nav("/app/oportunidades")} />}
    </>
  );
}
