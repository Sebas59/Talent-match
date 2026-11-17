import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BriefcaseBusiness, GaugeCircle, Pencil, Plus, Trash2, Wand2 } from "lucide-react";
import { api, del, patch, post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Badge, Button, Confirm, Empty, ErrorState, Field, Loading, Modal, PageHead, Panel, Segmented, useAsync } from "../../ui/index.jsx";
import { COMPONENTS, EDU, PROJECT_STATUS, fmtDate } from "../../format.js";

const KIND = { tech: "Técnica", power: "Power skill", certification: "Certificación" };

export function WeightsEditor({ value, onChange }) {
  const total = COMPONENTS.reduce((a, c) => a + Number(value[c.key] || 0), 0) || 1;
  return (
    <div className="stack" style={{ gap: 10 }}>
      {COMPONENTS.map((c) => (
        <div key={c.key} className="row" style={{ gap: 12 }}>
          <span className="row small" style={{ width: 200, gap: 8 }}><i className="swatch" style={{ background: `var(${c.var})` }} />{c.label}</span>
          <input type="range" className="range" min={0} max={100} step={5} aria-label={`Peso ${c.label}`}
                 value={Math.round(Number(value[c.key] || 0) * 100)} onChange={(e) => onChange({ ...value, [c.key]: Number(e.target.value) / 100 })} />
          <span className="num small" style={{ width: 54, textAlign: "right" }}>{Math.round((Number(value[c.key] || 0) / total) * 100)} %</span>
        </div>
      ))}
      <p className="muted xs">Los pesos se normalizan para sumar 100 %. Si el cargo no exige un componente (p. ej. sin años mínimos), su peso se reparte entre los demás.</p>
    </div>
  );
}

function ProjectModal({ project, onClose, onSaved }) {
  const [f, setF] = useState(project || { name: "", area: "", description: "", status: "active", start_date: "", end_date: "" });
  const [run, busy] = useAsync();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const body = { name: f.name, area: f.area, description: f.description, status: f.status, start_date: f.start_date || null, end_date: f.end_date || null };
  const valid = f.name.trim().length >= 3 && f.area.trim().length >= 2;
  return (
    <Modal title={project ? "Editar proyecto" : "Nuevo proyecto"} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={!valid}
             onClick={() => run(() => (project ? patch(`/projects/${project.id}`, body) : post("/projects", body)), project ? "Proyecto actualizado" : "Proyecto creado").then((p) => p && onSaved(p))}>
             {project ? "Guardar cambios" : "Crear proyecto"}</Button></>}>
      <Field label="Nombre" error={f.name && f.name.trim().length < 3 ? "Mínimo 3 caracteres" : null}><input className="input" value={f.name} onChange={set("name")} /></Field>
      <div className="grid g2">
        <Field label="Área"><input className="input" value={f.area} onChange={set("area")} /></Field>
        <Field label="Estado"><select className="select" value={f.status} onChange={set("status")}>
          {Object.entries(PROJECT_STATUS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Inicio"><input className="input" type="date" value={f.start_date || ""} onChange={set("start_date")} /></Field>
        <Field label="Fin"><input className="input" type="date" value={f.end_date || ""} onChange={set("end_date")} /></Field>
      </div>
      <Field label="Descripción"><textarea className="textarea" value={f.description} onChange={set("description")} maxLength={1200} /></Field>
    </Modal>
  );
}

function TemplatePicker({ onPick, onClose }) {
  const [q, setQ] = useState("data engineer");
  const [items, setItems] = useState(null);
  const [run, busy] = useAsync();
  const search = () => run(() => post("/catalog/job-templates/search", { query: q, limit: 10 })).then((r) => r && setItems(r.items));
  useEffect(() => { search(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Modal wide title="Usar una plantilla del dataset" sub="Ofertas reales de referencia (JobsDatasetProcessed.csv, en inglés). Revise y ajuste los requisitos antes de guardar." onClose={onClose}>
      <div className="row"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} aria-label="Buscar plantilla" />
        <Button loading={busy} onClick={search}>Buscar</Button></div>
      {items && items.length === 0 && <p className="muted small">Sin resultados.</p>}
      <div className="stack" style={{ gap: 10, maxHeight: 420, overflowY: "auto" }}>
        {items?.map((t) => (
          <div key={t.job_id} className="panel" style={{ padding: 12 }}>
            <div className="row between"><div><div className="strong">{t.title}</div><div className="muted xs">{t.category} · {t.min_years ? `${t.min_years} años` : "sin años"} · {t.education_label}</div></div>
              <Button size="sm" onClick={() => run(() => api(`/catalog/job-templates/${t.job_id}`)).then((d) => d && onPick(d))}>Usar</Button></div>
            <div className="tags" style={{ marginTop: 8 }}>{t.tech.map((s) => <span className="tag" key={s}>{s}</span>)}</div>
          </div>
        ))}
      </div>
    </Modal>
  );
}

function PositionModal({ project, position, defaults, onClose, onSaved }) {
  const init = position ? { ...position, requirements: position.requirements.map(({ kind, name, importance, weight }) => ({ kind, name, importance, weight })) }
    : { title: "", description: "", seniority: "", openings: 1, min_years: 0, min_years_mandatory: false, education_level: 0, status: "open",
      weights: defaults, requirements: [], source_job_id: null };
  const [f, setF] = useState(init);
  const [draft, setDraft] = useState({ kind: "tech", name: "", importance: "desirable" });
  const [tpl, setTpl] = useState(false);
  const [run, busy] = useAsync();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const addReq = () => { if (!draft.name.trim()) return; set("requirements", [...f.requirements, { ...draft, name: draft.name.trim(), weight: 1 }]); setDraft({ ...draft, name: "" }); };
  const body = { title: f.title, description: f.description, seniority: f.seniority || null, openings: Number(f.openings), min_years: Number(f.min_years),
    min_years_mandatory: f.min_years_mandatory, education_level: Number(f.education_level), weights: f.weights, status: f.status,
    requirements: f.requirements };
  const valid = f.title.trim().length >= 3 && f.requirements.length > 0;
  return (
    <Modal wide title={position ? "Editar cargo" : `Nuevo cargo en ${project.name}`} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={!valid}
             onClick={() => run(() => (position ? patch(`/positions/${position.id}`, body) : post(`/projects/${project.id}/positions`, { ...body, source_job_id: f.source_job_id })),
               position ? "Cargo actualizado" : "Cargo creado").then((p) => p && onSaved(p))}>{position ? "Guardar cambios" : "Crear cargo"}</Button></>}>
      {!position && <div className="row"><Button size="sm" icon={Wand2} onClick={() => setTpl(true)}>Partir de una plantilla del dataset</Button>
        {f.source_job_id && <Badge tone="info">Plantilla #{f.source_job_id}</Badge>}</div>}
      <div className="grid g2">
        <Field label="Título del cargo"><input className="input" value={f.title} onChange={(e) => set("title", e.target.value)} /></Field>
        <Field label="Nivel"><input className="input" value={f.seniority || ""} placeholder="Junior, semi-senior, senior…" onChange={(e) => set("seniority", e.target.value)} /></Field>
        <Field label="Vacantes"><input className="input" type="number" min={1} max={50} value={f.openings} onChange={(e) => set("openings", e.target.value)} /></Field>
        <Field label="Formación mínima"><select className="select" value={f.education_level} onChange={(e) => set("education_level", e.target.value)}>
          {EDU.map((l, i) => <option key={l} value={i}>{i === 0 ? "No exigida" : l}</option>)}</select></Field>
        <Field label="Años de experiencia"><input className="input" type="number" min={0} max={40} step={0.5} value={f.min_years} onChange={(e) => set("min_years", e.target.value)} /></Field>
        <label className="check" style={{ alignSelf: "end", paddingBottom: 8 }}><input type="checkbox" checked={f.min_years_mandatory} onChange={(e) => set("min_years_mandatory", e.target.checked)} />La experiencia mínima es obligatoria</label>
      </div>
      <Field label="Descripción"><textarea className="textarea" value={f.description} maxLength={1500} onChange={(e) => set("description", e.target.value)} /></Field>
      <div>
        <div className="section-title">Requisitos ({f.requirements.length})</div>
        <div className="row wrap" style={{ marginBottom: 10 }}>
          <select className="select" style={{ width: 150 }} aria-label="Tipo" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
            {Object.entries(KIND).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          <input className="input" style={{ flex: 1, minWidth: 180 }} placeholder="Nombre (p. ej. Python, Liderazgo, AWS Certified…)" value={draft.name}
                 onChange={(e) => setDraft({ ...draft, name: e.target.value })} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addReq())} aria-label="Nombre del requisito" />
          <Segmented label="Importancia" value={draft.importance} onChange={(v) => setDraft({ ...draft, importance: v })}
                     options={[{ value: "mandatory", label: "Obligatorio" }, { value: "desirable", label: "Deseable" }]} />
          <Button icon={Plus} onClick={addReq}>Agregar</Button>
        </div>
        {f.requirements.length === 0 ? <p className="muted small">Agregue al menos un requisito.</p> : (
          <table className="t"><thead><tr><th>Requisito</th><th>Tipo</th><th>Importancia</th><th>Peso relativo</th><th /></tr></thead>
            <tbody>{f.requirements.map((r, i) => (
              <tr key={`${r.kind}-${r.name}-${i}`}>
                <td className="strong">{r.name}</td><td className="small">{KIND[r.kind]}</td>
                <td><Segmented label="Importancia" value={r.importance} onChange={(v) => set("requirements", f.requirements.map((x, j) => (j === i ? { ...x, importance: v } : x)))}
                               options={[{ value: "mandatory", label: "Obligatorio" }, { value: "desirable", label: "Deseable" }]} /></td>
                <td><select className="select" style={{ width: 110 }} value={r.weight} aria-label="Peso relativo" onChange={(e) => set("requirements", f.requirements.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)))}>
                  <option value={0.5}>Bajo</option><option value={1}>Normal</option><option value={1.5}>Alto</option><option value={2}>Crítico</option></select></td>
                <td className="r"><Button size="sm" variant="ghost" icon={Trash2} aria-label={`Quitar ${r.name}`} onClick={() => set("requirements", f.requirements.filter((_, j) => j !== i))} /></td>
              </tr>))}</tbody></table>
        )}
        <p className="muted xs" style={{ marginTop: 6 }}>Los obligatorios pesan 1,5 veces más y definen la elegibilidad. Los nombres se normalizan con el catálogo ES↔EN.</p>
      </div>
      <div><div className="section-title">Ponderación del puntaje</div><WeightsEditor value={f.weights} onChange={(w) => set("weights", w)} /></div>
      {tpl && <TemplatePicker onClose={() => setTpl(false)} onPick={(d) => {
        setF((x) => ({ ...x, title: x.title || d.title, description: x.description || d.summary, min_years: d.min_years || x.min_years,
          education_level: d.education_level || x.education_level, requirements: d.requirements, source_job_id: d.job_id }));
        setTpl(false);
      }} />}
    </Modal>
  );
}

export default function Projects() {
  const { data, setData, error, loading, reload } = useApi("/projects");
  const settings = useApi("/catalog/defaults");
  const nav = useNavigate();
  const [sel, setSel] = useState(null);
  const [projModal, setProjModal] = useState(null);
  const [posModal, setPosModal] = useState(null);
  const [delPos, setDelPos] = useState(null);
  const [run] = useAsync();
  const current = useMemo(() => data?.find((p) => p.id === sel) || data?.[0], [data, sel]);
  const defaults = settings.data?.weights || { technical: 0.4, power: 0.25, experience: 0.2, credentials: 0.15 };
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const upsert = (p) => { setData(data.some((x) => x.id === p.id) ? data.map((x) => (x.id === p.id ? p : x)) : [p, ...data]); setSel(p.id); };
  const refreshProject = async (pid) => upsert(await api(`/projects/${pid}`));

  return (
    <>
      <PageHead title="Proyectos y cargos" sub="Defina los cargos de cada proyecto, sus requisitos y cómo se pondera la compatibilidad."
                actions={<Button variant="primary" icon={Plus} onClick={() => setProjModal({})}>Nuevo proyecto</Button>} />
      {data.length === 0 ? <Panel><Empty icon={BriefcaseBusiness} title="Aún no hay proyectos" action={<Button variant="primary" onClick={() => setProjModal({})}>Crear el primero</Button>} /></Panel> : (
        <div className="grid" style={{ gridTemplateColumns: "minmax(240px, 300px) minmax(0, 1fr)" }}>
          <Panel flush title="Proyectos">
            <ul className="list">{data.map((p) => (
              <li key={p.id} onClick={() => setSel(p.id)} style={{ cursor: "pointer", background: current?.id === p.id ? "var(--accent-soft)" : undefined }}>
                <div className="strong">{p.name}</div>
                <div className="row between xs muted"><span>{p.code} · {p.area}</span><span>{p.open_positions} abiertos</span></div>
              </li>))}</ul>
          </Panel>
          {current && (
            <div className="stack">
              <Panel title={current.name} hint={`${current.code} · ${current.area} · ${fmtDate(current.start_date)} – ${fmtDate(current.end_date)}`}
                     actions={<><Badge tone={current.status === "active" ? "good" : current.status === "closed" ? "muted" : "info"}>{PROJECT_STATUS[current.status]}</Badge>
                       <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setProjModal(current)}>Editar</Button></>}>
                <p className="small prose">{current.description || "Sin descripción."}</p>
              </Panel>
              <Panel title="Cargos" flush actions={<Button size="sm" icon={Plus} onClick={() => setPosModal({ project: current })}>Nuevo cargo</Button>}>
                {current.positions.length === 0 ? <Empty title="Sin cargos" action={<Button onClick={() => setPosModal({ project: current })}>Crear cargo</Button>}>Defina un cargo con sus requisitos para ejecutar el matching.</Empty> : (
                  <ul className="list">{current.positions.map((pos) => (
                    <li key={pos.id}>
                      <div className="row between wrap">
                        <div>
                          <div className="row"><span className="strong">{pos.title}</span>
                            <Badge tone={pos.status === "open" ? "good" : "muted"}>{pos.status === "open" ? "Abierto" : "Cerrado"}</Badge>
                            {pos.source_job_id && <Badge tone="info">Plantilla del dataset</Badge>}</div>
                          <div className="cell-sub">{pos.seniority || "Sin nivel"} · {pos.openings} vacante(s) · {pos.min_years ? `${pos.min_years} años${pos.min_years_mandatory ? " (obligatorio)" : ""}` : "sin años mínimos"} · {pos.education_label}</div>
                        </div>
                        <div className="row">
                          <Button size="sm" icon={GaugeCircle} onClick={() => nav(`/rrhh/matching?position=${pos.id}`)}>{pos.last_run ? "Ver matching" : "Ejecutar matching"}</Button>
                          <Button size="sm" variant="ghost" icon={Pencil} aria-label={`Editar ${pos.title}`} onClick={() => setPosModal({ project: current, position: pos })} />
                          <Button size="sm" variant="ghost" onClick={() => run(() => patch(`/positions/${pos.id}`, { status: pos.status === "open" ? "closed" : "open" }), "Estado actualizado").then(() => refreshProject(current.id))}>
                            {pos.status === "open" ? "Cerrar" : "Reabrir"}</Button>
                          <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Eliminar ${pos.title}`} onClick={() => setDelPos(pos)} />
                        </div>
                      </div>
                      <div className="tags" style={{ marginTop: 8 }}>
                        {pos.requirements.map((r) => <span className="tag" key={r.id} title={r.importance === "mandatory" ? "Obligatorio" : "Deseable"}
                          style={r.importance === "mandatory" ? { borderColor: "var(--accent)", color: "var(--accent-ink)" } : undefined}>{r.name}</span>)}
                      </div>
                    </li>))}</ul>
                )}
              </Panel>
            </div>
          )}
        </div>
      )}
      {projModal && <ProjectModal project={projModal.id ? projModal : null} onClose={() => setProjModal(null)} onSaved={(p) => { upsert(p); setProjModal(null); }} />}
      {posModal && <PositionModal {...posModal} defaults={defaults} onClose={() => setPosModal(null)}
                                  onSaved={() => { refreshProject(posModal.project.id); setPosModal(null); }} />}
      {delPos && <Confirm title="Eliminar cargo" danger confirmLabel="Eliminar" onClose={() => setDelPos(null)}
                          onConfirm={() => run(() => del(`/positions/${delPos.id}`), "Cargo eliminado").then(() => refreshProject(current.id))}>
        Se eliminarán el cargo «{delPos.title}», sus ejecuciones de matching y las decisiones registradas. Considere cerrarlo en su lugar.</Confirm>}
    </>
  );
}
