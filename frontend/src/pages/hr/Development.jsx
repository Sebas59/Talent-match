import { useState } from "react";
import { BookOpenCheck } from "lucide-react";
import { post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Avatar, Badge, Button, Drawer, Empty, ErrorState, Kpis, Loading, PageHead, Panel, Progress, SearchInput, Segmented, useAsync } from "../../ui/index.jsx";
import { PathItems } from "../employee/Development.jsx";
import { fmtDate } from "../../format.js";
import { norm } from "../../text.js";

export default function Development() {
  const { data, error, loading, reload } = useApi("/development/paths");
  const [q, setQ] = useState("");
  const [st, setSt] = useState("active");
  const [open, setOpen] = useState(null);
  const [run] = useAsync();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const rows = data.filter((p) => (st === "all" || p.status === st) && (!q || norm(`${p.full_name} ${p.title}`).includes(norm(q))));
  const avg = data.length ? Math.round(data.reduce((a, p) => a + p.progress, 0) / data.length) : 0;
  const overdue = data.filter((p) => p.status === "active" && p.due_date && new Date(p.due_date) < new Date()).length;
  return (
    <>
      <PageHead title="Rutas de aprendizaje" sub="Seguimiento de las rutas asignadas desde el matching y las que crean los propios empleados." />
      <Kpis items={[{ label: "Rutas activas", value: data.filter((p) => p.status === "active").length },
        { label: "Completadas", value: data.filter((p) => p.status === "completed").length },
        { label: "Avance promedio", value: `${avg} %` }, { label: "Vencidas", value: overdue, detail: "con fecha objetivo pasada" }]} />
      <div className="filters">
        <SearchInput value={q} onChange={setQ} placeholder="Persona o ruta" />
        <Segmented label="Estado" value={st} onChange={setSt} options={[{ value: "active", label: "Activas" }, { value: "completed", label: "Completadas" }, { value: "all", label: "Todas" }]} />
      </div>
      <Panel flush>
        {rows.length === 0 ? <Empty icon={BookOpenCheck} title="No hay rutas con este filtro">Asigne rutas desde los resultados del matching.</Empty> : (
          <div className="table-wrap"><table className="t">
            <thead><tr><th>Persona</th><th>Ruta</th><th>Origen</th><th style={{ minWidth: 160 }}>Avance</th><th>Fecha objetivo</th></tr></thead>
            <tbody>{rows.map((p) => (
              <tr key={p.id} className="clickable" onClick={() => setOpen(p)}>
                <td><div className="row"><Avatar name={p.full_name} /><div><div className="cell-title">{p.full_name}</div><div className="cell-sub">{p.department}</div></div></div></td>
                <td><div>{p.title}</div><div className="cell-sub">{p.target_skills.slice(0, 3).join(", ")}</div></td>
                <td>{p.self_assigned ? <Badge tone="info">Autoasignada</Badge> : <span className="small">{p.assigned_by}</span>}</td>
                <td><div className="row"><div style={{ flex: 1 }}><Progress value={p.progress} tone={p.status === "completed" ? "good" : ""} /></div><span className="num small">{p.progress} %</span></div></td>
                <td className="small">{p.due_date ? fmtDate(p.due_date) : "—"}</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Panel>
      {open && <Drawer title={open.title} sub={`${open.full_name} · ${open.completed_items}/${open.total_items} actividades · ${open.total_hours} h`} onClose={() => setOpen(null)}>
        {open.note && <p className="small">{open.note}</p>}
        <Progress value={open.progress} />
        <div className="panel"><PathItems path={open} /></div>
        <p className="muted xs">{open.catalog_note}</p>
        <div className="row"><Button variant="danger" onClick={() => run(() => post(`/development/paths/${open.id}/archive`), "Ruta archivada").then(() => { setOpen(null); reload(); })}>Archivar ruta</Button></div>
      </Drawer>}
    </>
  );
}
