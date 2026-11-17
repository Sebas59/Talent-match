import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Eye, EyeOff, Pencil, Plus, Trash2, Undo2, X } from "lucide-react";
import { api, del, patch, post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Confirm, Empty, ErrorState, Field, Loading, Modal, PageHead, Panel, Ring, Segmented,
  Tabs, useAsync } from "../../ui/index.jsx";
import { EDU, ENTRY_KIND, ORIGIN, STATUS, fmtDate } from "../../format.js";

export function Confidence({ label }) {
  if (!label) return null;
  return (
    <span className={`conf ${label}`} title={`Confianza heurística ${label.toLowerCase()} (no es una probabilidad calibrada)`}>
      <i /><i /><i /><span className="visually-hidden">Confianza {label}</span>
    </span>
  );
}

function SkillRow({ s, onChange, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(s.name);
  const o = ORIGIN[s.origin] || ORIGIN.extracted;
  return (
    <div className={`skill-row ${s.status}`}>
      <div style={{ minWidth: 0 }}>
        {editing ? (
          <div className="row">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Nombre de la competencia" style={{ maxWidth: 280 }} />
            <Button size="sm" variant="primary" onClick={() => { onChange({ name, status: "confirmed" }); setEditing(false); }}>Guardar</Button>
            <Button size="sm" variant="ghost" onClick={() => { setName(s.name); setEditing(false); }}>Cancelar</Button>
          </div>
        ) : <div className="skill-name">{s.name}</div>}
        <div className="skill-meta">
          <Badge tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Badge>
          <span title={o.label}>{o.short}</span>
          {s.confidence_label && <span className="row" style={{ gap: 5 }}><Confidence label={s.confidence_label} />{s.confidence_label}</span>}
          {s.source && <span>{s.source}</span>}
        </div>
        {s.evidence && s.origin !== "manual" && <div className="evidence">“{s.evidence}”</div>}
      </div>
      <div className="row">
        {s.status !== "confirmed" && <Button size="sm" icon={Check} onClick={() => onChange({ status: "confirmed" })}>Confirmar</Button>}
        {s.status === "pending" && <Button size="sm" variant="ghost" icon={X} onClick={() => onChange({ status: "rejected" })}>Rechazar</Button>}
        {s.status === "rejected" && <Button size="sm" variant="ghost" icon={Undo2} onClick={() => onChange({ status: "pending" })}>Restaurar</Button>}
        {s.status === "confirmed" && <Button size="sm" variant="ghost" icon={Pencil} aria-label={`Corregir ${s.name}`} onClick={() => setEditing(true)} />}
        <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Eliminar ${s.name}`} onClick={onDelete} />
      </div>
    </div>
  );
}

function EntryRow({ e, onChange, onDelete }) {
  return (
    <div className={`skill-row ${e.status}`}>
      <div style={{ minWidth: 0 }}>
        <div className="skill-name">{e.title}</div>
        <div className="skill-meta">
          <Badge tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Badge>
          {e.organization && <span>{e.organization}</span>}
          {(e.start || e.end || e.current) && <span>{e.start || "?"} – {e.current ? "actual" : e.end || "?"}</span>}
          {e.years != null && e.kind === "experience" && <span>{e.years} años</span>}
          {e.level && <span>{e.level}</span>}
          <span>{(ORIGIN[e.origin] || ORIGIN.extracted).short}</span>
        </div>
        {e.evidence && e.origin !== "manual" && e.evidence !== e.title && <div className="evidence">“{e.evidence}”</div>}
      </div>
      <div className="row">
        {e.status !== "confirmed" && <Button size="sm" icon={Check} onClick={() => onChange({ status: "confirmed" })}>Confirmar</Button>}
        {e.status === "pending" && <Button size="sm" variant="ghost" icon={X} onClick={() => onChange({ status: "rejected" })}>Rechazar</Button>}
        {e.status === "rejected" && <Button size="sm" variant="ghost" icon={Undo2} onClick={() => onChange({ status: "pending" })}>Restaurar</Button>}
        <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Eliminar ${e.title}`} onClick={onDelete} />
      </div>
    </div>
  );
}

function AddSkill({ kind, onClose, onSaved }) {
  const [name, setName] = useState("");
  const [level, setLevel] = useState(3);
  const [sugg, setSugg] = useState([]);
  const [run, busy] = useAsync();
  async function search(q) {
    setName(q);
    if (q.length < 2) return setSugg([]);
    try { setSugg(await api(`/catalog/skills?kind=${kind}&q=${encodeURIComponent(q)}&limit=6`)); } catch { setSugg([]); }
  }
  return (
    <Modal title={kind === "tech" ? "Agregar competencia técnica" : "Agregar power skill"} onClose={onClose}
           sub="Se guarda como confirmada y con origen manual."
           footer={<><Button onClick={onClose}>Cancelar</Button>
             <Button variant="primary" loading={busy} disabled={!name.trim()}
                     onClick={() => run(() => post("/profiles/me/skills", { kind, name: name.trim(), level }), "Competencia agregada").then((p) => p && onSaved(p))}>
               Agregar</Button></>}>
      <Field label="Competencia" help="Se normaliza con el catálogo (p. ej. «postgres» → PostgreSQL).">
        <input className="input" value={name} onChange={(e) => search(e.target.value)} list="skill-sugg" />
      </Field>
      {sugg.length > 0 && <div className="tags">{sugg.map((s) => <button key={s.key} type="button" className="tag" onClick={() => { setName(s.name); setSugg([]); }}>{s.name}</button>)}</div>}
      <Field label={`Autovaloración: ${level} de 5`} help="Opcional. No interviene en el cálculo de compatibilidad.">
        <input type="range" className="range" min={1} max={5} value={level} onChange={(e) => setLevel(Number(e.target.value))} />
      </Field>
    </Modal>
  );
}

function AddEntry({ kind, onClose, onSaved }) {
  const [f, setF] = useState({ title: "", organization: "", start: "", end: "", current: false, level: "" });
  const [run, busy] = useAsync();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = () => run(() => post("/profiles/me/entries", {
    kind, title: f.title.trim(), organization: f.organization || null, start: f.start || null,
    end: f.current ? null : f.end || null, current: f.current, level: f.level || null,
  }), "Registro agregado").then((p) => p && onSaved(p));
  return (
    <Modal title={`Agregar: ${ENTRY_KIND[kind].toLowerCase()}`} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={f.title.trim().length < 2} onClick={save}>Agregar</Button></>}>
      <Field label={kind === "experience" ? "Cargo" : kind === "language" ? "Idioma" : "Título"}><input className="input" value={f.title} onChange={set("title")} /></Field>
      {kind !== "language" && <Field label={kind === "experience" ? "Empresa" : "Institución"}><input className="input" value={f.organization} onChange={set("organization")} /></Field>}
      {(kind === "experience" || kind === "education") && (
        <div className="grid g2">
          <Field label="Inicio"><input className="input" type="month" value={f.start} onChange={set("start")} /></Field>
          <Field label="Fin"><input className="input" type="month" value={f.end} onChange={set("end")} disabled={f.current} /></Field>
        </div>
      )}
      {kind === "experience" && <label className="check"><input type="checkbox" checked={f.current} onChange={set("current")} />Es mi cargo actual</label>}
      {kind === "language" && <Field label="Nivel"><input className="input" value={f.level} onChange={set("level")} placeholder="B2, avanzado…" /></Field>}
    </Modal>
  );
}

export default function Profile() {
  const { data: p, setData, error, loading, reload } = useApi("/profiles/me");
  const [tab, setTab] = useState("tech");
  const [filter, setFilter] = useState("all");
  const [adding, setAdding] = useState(null);
  const [edit, setEdit] = useState(false);
  const [confirmPub, setConfirmPub] = useState(false);
  const [run, busy] = useAsync();

  const counts = useMemo(() => {
    if (!p) return {};
    const c = (xs) => ({ total: xs.length, pending: xs.filter((x) => x.status === "pending").length });
    return { tech: c(p.skills.filter((s) => s.kind === "tech")), power: c(p.skills.filter((s) => s.kind === "power")),
      ...Object.fromEntries(Object.keys(ENTRY_KIND).map((k) => [k, c(p.entries.filter((e) => e.kind === k))])) };
  }, [p]);

  if (loading && !p) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const isSkill = tab === "tech" || tab === "power";
  const rows = (isSkill ? p.skills.filter((s) => s.kind === tab) : p.entries.filter((e) => e.kind === tab))
    .filter((x) => filter === "all" || x.status === filter);
  const pendingTotal = p.skills.filter((s) => s.status === "pending").length + p.entries.filter((e) => e.status === "pending").length;
  const act = (fn, msg) => run(fn, msg).then((np) => np && setData(np));

  return (
    <>
      <PageHead title="Mi perfil profesional"
                sub="Revise lo que se extrajo de su hoja de vida. Solo lo confirmado se publica y se usa para calcular compatibilidad."
                actions={<>
                  {p.status === "published"
                    ? <Button icon={EyeOff} onClick={() => act(() => post("/profiles/me/unpublish"), "Perfil retirado de RR. HH.")}>Retirar publicación</Button>
                    : <Button variant="primary" icon={Eye} disabled={!p.can_publish} onClick={() => setConfirmPub(true)}>Publicar perfil</Button>}
                </>} />
      {p.status === "published"
        ? <Alert tone="good" title="Perfil publicado">Recursos Humanos ve sus elementos confirmados desde el {fmtDate(p.published_at)}. Puede retirarlo en cualquier momento.</Alert>
        : p.publish_blockers.length > 0
          ? <Alert tone="warning" title="Antes de publicar">{p.publish_blockers.join(" ")}{!p.consent?.processing && <> <Link to="/app/privacidad">Otorgar autorización</Link>.</>}</Alert>
          : <Alert tone="info" title="Listo para publicar">Su perfil cumple los requisitos. Al publicarlo, RR. HH. verá solo lo confirmado.</Alert>}
      <div style={{ height: 16 }} />
      <div className="grid g-main">
        <div className="stack">
          <Panel flush title={null}>
            <div style={{ padding: "6px 18px 0" }}>
              <Tabs value={tab} onChange={(v) => { setTab(v); setFilter("all"); }} tabs={[
                { value: "tech", label: "Técnicas", count: counts.tech.total },
                { value: "power", label: "Power skills", count: counts.power.total },
                ...Object.entries(ENTRY_KIND).map(([k, l]) => ({ value: k, label: l, count: counts[k].total })),
              ]} />
              <div className="row between wrap" style={{ marginBottom: 12 }}>
                <Segmented label="Filtrar por estado" value={filter} onChange={setFilter} options={[
                  { value: "all", label: "Todo" }, { value: "pending", label: `Por revisar (${counts[tab].pending})` },
                  { value: "confirmed", label: "Confirmado" }, { value: "rejected", label: "Rechazado" }]} />
                <div className="row">
                  {counts[tab].pending > 0 && isSkill && (
                    <Button size="sm" loading={busy} onClick={() => act(() => post("/profiles/me/confirm-all", { kind: tab, min_confidence: 0.85, include_entries: false }), "Confirmadas las de confianza alta")}>
                      Confirmar las de confianza alta</Button>)}
                  <Button size="sm" icon={Plus} onClick={() => setAdding(tab)}>Agregar</Button>
                </div>
              </div>
            </div>
            {rows.length === 0 ? (
              <Empty title={filter === "all" ? "Nada aquí todavía" : "No hay elementos con este estado"}
                     action={filter === "all" && !p.last_extraction ? <Link className="btn primary" to="/app/cv">Cargar hoja de vida</Link> : null}>
                {filter === "all" ? "Cargue su hoja de vida para extraer información automáticamente, o agréguela a mano." : null}
              </Empty>
            ) : (
              <div style={{ borderTop: "1px solid var(--line-2)" }}>
                {rows.map((x) => isSkill
                  ? <SkillRow key={x.id} s={x} onChange={(b) => act(() => patch(`/profiles/me/skills/${x.id}`, b))}
                              onDelete={() => act(() => del(`/profiles/me/skills/${x.id}`), "Eliminada")} />
                  : <EntryRow key={x.id} e={x} onChange={(b) => act(() => patch(`/profiles/me/entries/${x.id}`, b))}
                              onDelete={() => act(() => del(`/profiles/me/entries/${x.id}`), "Eliminado")} />)}
              </div>
            )}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Resumen" actions={<Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEdit(true)}>Editar</Button>}>
            <div className="row" style={{ gap: 14, marginBottom: 14 }}>
              <Ring value={p.completeness} />
              <div>
                <div className="strong">{p.full_name}</div>
                <div className="muted small">{p.headline || p.job_title || "Sin titular"}</div>
                <div className="muted xs">{p.department}</div>
              </div>
            </div>
            <dl className="kv">
              <dt>Experiencia</dt><dd className="num">{p.years_experience} años <span className="muted xs">({p.years_source === "manual" ? "ajustado por usted" : p.years_source === "extracted" ? "calculado del CV" : "sin dato"})</span></dd>
              <dt>Formación</dt><dd>{p.education_label}</dd>
              <dt>Movilidad</dt><dd>{p.open_to_mobility ? "Abierto(a) a oportunidades" : "No disponible por ahora"}</dd>
            </dl>
            {p.summary && <p className="small" style={{ marginTop: 12, color: "var(--ink-2)" }}>{p.summary}</p>}
          </Panel>
          <Panel title="Qué publica" hint="Secciones visibles para RR. HH. (solo elementos confirmados)">
            <div className="stack" style={{ gap: 8 }}>
              {[["summary", "Resumen"], ["experience", "Experiencia"], ["education", "Formación"], ["certification", "Certificaciones"], ["language", "Idiomas"]].map(([k, l]) => (
                <label className="check" key={k}>
                  <input type="checkbox" checked={p.visibility[k] !== false}
                         onChange={(e) => act(() => patch("/profiles/me", { visibility: { [k]: e.target.checked } }), "Visibilidad actualizada")} />{l}
                </label>
              ))}
              <p className="muted xs">Las competencias confirmadas siempre se publican: son la base del matching.</p>
            </div>
          </Panel>
          {pendingTotal > 0 && <Alert tone="warning">{pendingTotal} elementos esperan su revisión.</Alert>}
        </div>
      </div>
      {adding && (adding === "tech" || adding === "power"
        ? <AddSkill kind={adding} onClose={() => setAdding(null)} onSaved={(np) => { setData(np); setAdding(null); }} />
        : <AddEntry kind={adding} onClose={() => setAdding(null)} onSaved={(np) => { setData(np); setAdding(null); }} />)}
      {edit && <EditSummary p={p} onClose={() => setEdit(false)} onSaved={(np) => { setData(np); setEdit(false); }} />}
      {confirmPub && (
        <Confirm title="Publicar perfil" confirmLabel="Publicar" onClose={() => setConfirmPub(false)}
                 onConfirm={() => act(() => post("/profiles/me/publish"), "Perfil publicado")}>
          Recursos Humanos podrá ver sus {p.skills.filter((s) => s.status === "confirmed").length} competencias confirmadas y las
          secciones marcadas como visibles. Los elementos por revisar o rechazados no se publican.
        </Confirm>
      )}
    </>
  );
}

function EditSummary({ p, onClose, onSaved }) {
  const [f, setF] = useState({ headline: p.headline || "", summary: p.summary || "", years_experience: p.years_experience,
    education_level: p.education_level, open_to_mobility: p.open_to_mobility });
  const [run, busy] = useAsync();
  return (
    <Modal title="Editar resumen" onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button>
             <Button variant="primary" loading={busy} onClick={() => run(() => patch("/profiles/me", {
               ...f, years_experience: Number(f.years_experience), education_level: Number(f.education_level) }), "Perfil actualizado").then((np) => np && onSaved(np))}>Guardar</Button></>}>
      <Field label="Titular profesional"><input className="input" maxLength={160} value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} /></Field>
      <Field label="Resumen"><textarea className="textarea" maxLength={1200} value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} /></Field>
      <div className="grid g2">
        <Field label="Años de experiencia"><input className="input" type="number" min={0} max={60} step={0.5} value={f.years_experience} onChange={(e) => setF({ ...f, years_experience: e.target.value })} /></Field>
        <Field label="Nivel de formación"><select className="select" value={f.education_level} onChange={(e) => setF({ ...f, education_level: e.target.value })}>
          {EDU.map((l, i) => <option key={l} value={i}>{l}</option>)}</select></Field>
      </div>
      <label className="check"><input type="checkbox" checked={f.open_to_mobility} onChange={(e) => setF({ ...f, open_to_mobility: e.target.checked })} />Estoy abierto(a) a oportunidades de movilidad interna</label>
    </Modal>
  );
}
