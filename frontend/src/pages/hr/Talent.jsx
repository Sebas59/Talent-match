import { useState } from "react";
import { Users } from "lucide-react";
import { useApi, useDebounced } from "../../hooks.js";
import { Avatar, Badge, Drawer, Empty, ErrorState, Loading, PageHead, Panel, SearchInput } from "../../ui/index.jsx";
import { ENTRY_KIND, ORIGIN, fmtDate } from "../../format.js";

export function PublishedProfile({ id }) {
  const { data: p, error, loading } = useApi(`/talent/${id}`);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  const group = (k) => p.skills.filter((s) => s.kind === k);
  return (
    <div className="stack" style={{ gap: 20 }}>
      <dl className="kv">
        <dt>Cargo actual</dt><dd>{p.job_title || "—"}</dd>
        <dt>Área</dt><dd>{p.department || "—"}</dd>
        <dt>Experiencia</dt><dd className="num">{p.years_experience} años</dd>
        <dt>Formación</dt><dd>{p.education_label}</dd>
        <dt>Movilidad</dt><dd>{p.open_to_mobility ? "Abierto(a) a oportunidades" : "No disponible por ahora"}</dd>
        <dt>Publicado</dt><dd>{fmtDate(p.published_at)}</dd>
      </dl>
      {p.summary && <p className="small prose">{p.summary}</p>}
      {[["tech", "Competencias técnicas"], ["power", "Power skills"]].map(([k, l]) => (
        <div key={k}>
          <div className="section-title">{l} ({group(k).length})</div>
          <div className="tags">{group(k).map((s) => (
            <span className="tag" key={s.id} title={s.evidence ? `Evidencia: ${s.evidence}` : ORIGIN[s.origin]?.label}>{s.name}
              {s.level && <span className="muted xs">{s.level}/5</span>}</span>))}</div>
        </div>
      ))}
      {Object.entries(ENTRY_KIND).map(([k, l]) => {
        const xs = p.entries.filter((e) => e.kind === k);
        if (!xs.length) return null;
        return (
          <div key={k}>
            <div className="section-title">{l}</div>
            <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
              {xs.map((e) => <li key={e.id}>{e.title}{e.organization ? `, ${e.organization}` : ""}
                {e.start ? <span className="muted"> ({e.start} – {e.current ? "actual" : e.end || "?"})</span> : null}{e.level ? <span className="muted"> {e.level}</span> : null}</li>)}
            </ul>
          </div>
        );
      })}
      <p className="muted xs">Solo se muestran los elementos que la persona confirmó y las secciones que decidió publicar. Esta consulta queda registrada en la auditoría.</p>
    </div>
  );
}

export default function Talent() {
  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [dept, setDept] = useState("");
  const [mob, setMob] = useState(false);
  const [open, setOpen] = useState(null);
  const dq = useDebounced(q);
  const params = new URLSearchParams({ q: dq, skill, department: dept, ...(mob ? { mobility: "true" } : {}) }).toString();
  const { data, error, loading, reload } = useApi(`/talent?${params}`, [params]);
  const facets = useApi("/talent/facets");
  return (
    <>
      <PageHead title="Talento interno" sub="Perfiles que los empleados confirmaron y publicaron. Los borradores y lo no confirmado no aparecen." />
      <div className="filters">
        <SearchInput value={q} onChange={setQ} placeholder="Nombre, cargo o competencia" />
        <select className="select" aria-label="Competencia" value={skill} onChange={(e) => setSkill(e.target.value)}>
          <option value="">Todas las competencias</option>
          {facets.data?.skills.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="select" aria-label="Área" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">Todas las áreas</option>
          {facets.data?.departments.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="check small"><input type="checkbox" checked={mob} onChange={(e) => setMob(e.target.checked)} />Solo abiertos a movilidad</label>
        <span className="spacer" />
        {data && <span className="muted small">{data.length} perfiles</span>}
      </div>
      {error ? <ErrorState error={error} onRetry={reload} /> : (
        <Panel flush>
          {loading && !data ? <Loading /> : data.length === 0 ? (
            <Empty icon={Users} title="Ningún perfil coincide">Ajuste los filtros. Recuerde que solo aparecen perfiles publicados con autorización vigente.</Empty>
          ) : (
            <div className="table-wrap"><table className="t">
              <thead><tr><th>Persona</th><th>Competencias destacadas</th><th className="r">Experiencia</th><th className="r">Completitud</th><th>Estado</th></tr></thead>
              <tbody>{data.map((c) => (
                <tr key={c.profile_id} className="clickable" onClick={() => setOpen(c)}>
                  <td><div className="row"><Avatar name={c.full_name} /><div><div className="cell-title">{c.full_name}</div>
                    <div className="cell-sub">{c.job_title} · {c.department}</div></div></div></td>
                  <td><div className="tags">{c.top_tech.slice(0, 4).map((s) => <span className="tag" key={s}>{s}</span>)}
                    {c.tech_count > 4 && <span className="muted xs">+{c.tech_count - 4}</span>}</div></td>
                  <td className="r num">{c.years_experience} años</td>
                  <td className="r num">{c.completeness} %</td>
                  <td><div className="row">{c.open_to_mobility ? <Badge tone="good">Movilidad</Badge> : <Badge>No disponible</Badge>}
                    {c.active_paths > 0 && <Badge tone="info">En formación</Badge>}</div></td>
                </tr>))}</tbody>
            </table></div>
          )}
        </Panel>
      )}
      {open && <Drawer title={open.full_name} sub={open.headline} head={<Avatar name={open.full_name} lg />} onClose={() => setOpen(null)}>
        <PublishedProfile id={open.profile_id} /></Drawer>}
    </>
  );
}
