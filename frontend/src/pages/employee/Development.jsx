import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, GraduationCap, PlayCircle } from "lucide-react";
import { patch } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Badge, Button, Empty, ErrorState, Loading, PageHead, Panel, Progress, useAsync } from "../../ui/index.jsx";
import { CourseList } from "./Opportunities.jsx";
import { fmtDate } from "../../format.js";

export function PathItems({ path, editable, onChange }) {
  const [run] = useAsync();
  const set = (it, body) => run(() => patch(`/development/items/${it.id}`, body)).then((p) => p && onChange?.(p));
  return (
    <div>
      {path.items.map((it) => (
        <div className="skill-row" key={it.id}>
          <div style={{ minWidth: 0 }}>
            <div className="row"><span className="skill-name">{it.skill}</span>
              <Badge tone={it.status === "completed" ? "good" : it.status === "in_progress" ? "info" : undefined}>
                {it.status === "completed" ? "Completado" : it.status === "in_progress" ? "En curso" : "Pendiente"}</Badge></div>
            <div className="skill-meta">
              {it.url ? <a href={it.url} target="_blank" rel="noopener noreferrer" className="row" style={{ gap: 4 }}>{it.course_title}<ExternalLink size={12} aria-hidden /></a>
                : <span>Formación interna por definir con RR. HH.</span>}
              {it.platform && <span>{it.platform}</span>}
              {it.hours && <span>{it.hours} h{it.hours_estimated ? " (estimado)" : ""}</span>}
            </div>
            <div style={{ marginTop: 8, maxWidth: 320 }}><Progress value={it.progress} tone={it.status === "completed" ? "good" : ""} /></div>
          </div>
          {editable && (
            <div className="row">
              {it.status !== "completed" && <Button size="sm" variant="ghost" icon={PlayCircle} onClick={() => set(it, { progress: Math.min(100, it.progress + 25) })}>+25 %</Button>}
              {it.status !== "completed"
                ? <Button size="sm" icon={CheckCircle2} onClick={() => set(it, { status: "completed" })}>Marcar completado</Button>
                : <Button size="sm" variant="ghost" onClick={() => set(it, { status: "in_progress" })}>Reabrir</Button>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function Development() {
  const paths = useApi("/development/me");
  const rec = useApi("/development/me/recommendations");
  if (paths.loading && !paths.data) return <Loading />;
  if (paths.error) return <ErrorState error={paths.error} onRetry={paths.reload} />;
  const replace = (np) => paths.setData(paths.data.map((p) => (p.id === np.id ? np : p)));
  return (
    <>
      <PageHead title="Mi desarrollo" sub="Rutas de aprendizaje asignadas por RR. HH. o creadas por usted a partir de sus brechas." />
      <div className="grid g-main">
        <div className="stack">
          {paths.data.length === 0 ? (
            <Panel><Empty icon={GraduationCap} title="Aún no tiene rutas" action={<Link className="btn primary" to="/app/oportunidades">Explorar oportunidades</Link>}>
              Abra una oportunidad y cree una ruta para cerrar las brechas que tenga.</Empty></Panel>
          ) : paths.data.map((p) => (
            <Panel key={p.id} title={p.title} flush
                   hint={`${p.self_assigned ? "Creada por usted" : `Asignada por ${p.assigned_by}`}${p.position ? ` · Objetivo: ${p.position.title}` : ""}${p.due_date ? ` · Fecha objetivo ${fmtDate(p.due_date)}` : ""}`}
                   actions={<span className="num strong">{p.progress} %</span>}>
              <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--line-2)" }}>
                <Progress value={p.progress} tone={p.status === "completed" ? "good" : ""} />
                <div className="row between xs muted" style={{ marginTop: 6 }}>
                  <span>{p.completed_items} de {p.total_items} actividades</span><span>{p.total_hours} h en total</span></div>
                {p.note && <p className="small" style={{ marginTop: 8 }}>{p.note}</p>}
              </div>
              <PathItems path={p} editable onChange={replace} />
            </Panel>
          ))}
        </div>
        <div className="stack">
          <Panel title="Recomendado para usted" hint={rec.data?.position ? `Según sus brechas frente a «${rec.data.position.title}» (${rec.data.position.score} %)` : "Según su oportunidad más compatible"}>
            {rec.loading ? <Loading /> : rec.data?.recommendations?.length ? <CourseList recs={rec.data.recommendations} />
              : <p className="muted small">Confirme competencias en su perfil para recibir recomendaciones.</p>}
          </Panel>
        </div>
      </div>
    </>
  );
}
