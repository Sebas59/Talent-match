import { Fragment, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Columns3, GaugeCircle, GraduationCap, History, Play, SlidersHorizontal } from "lucide-react";
import { post } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Alert, Avatar, Badge, Button, Drawer, Empty, ErrorState, Field, Loading, MiniScore, Modal, PageHead, Panel,
  Segmented, Tabs, useAsync } from "../../ui/index.jsx";
import MatchDetail from "../../ui/MatchDetail.jsx";
import { WeightsEditor } from "./Projects.jsx";
import { COMPONENTS, DECISIONS, fmtDateTime } from "../../format.js";

function DecisionForm({ positionId, result, onDone }) {
  const [decision, setDecision] = useState(result.decision?.decision || "shortlisted");
  const [just, setJust] = useState("");
  const [run, busy] = useAsync();
  const ok = just.trim().length >= 20;
  return (
    <div className="panel" style={{ padding: 16 }}>
      <div className="section-title">Registrar decisión humana</div>
      <div className="stack" style={{ gap: 12 }}>
        <Field label="Decisión"><select className="select" value={decision} onChange={(e) => setDecision(e.target.value)}>
          {Object.entries(DECISIONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Justificación" help="Mínimo 20 caracteres. La persona podrá leerla en su espacio."
               error={just && !ok ? `Faltan ${20 - just.trim().length} caracteres` : null}>
          <textarea className="textarea" value={just} maxLength={1000} onChange={(e) => setJust(e.target.value)}
                    placeholder="Motivos de la decisión, más allá del puntaje: contexto, disponibilidad, conversación con la persona…" />
        </Field>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <Button variant="primary" loading={busy} disabled={!ok} onClick={() => run(() => post(`/positions/${positionId}/decisions`, {
            profile_id: result.profile_id, decision, justification: just.trim(), match_result_id: result.id }), "Decisión registrada").then((d) => d && onDone())}>
            Registrar decisión</Button>
        </div>
      </div>
    </div>
  );
}

function AssignPath({ result, position, onClose }) {
  const [title, setTitle] = useState(`Ruta hacia ${position.title}`);
  const [due, setDue] = useState("");
  const [note, setNote] = useState("");
  const [run, busy] = useAsync();
  return (
    <Modal title={`Asignar ruta a ${result.full_name}`} sub={`Se construye con sus ${result.gaps.length} brechas frente al cargo.`} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} onClick={() => run(() => post("/development/paths", {
             profile_id: result.profile_id, title, position_id: position.id, match_result_id: result.id, due_date: due || null, note: note || null }),
           "Ruta de aprendizaje asignada").then((r) => r && onClose())}>Asignar ruta</Button></>}>
      <div className="tags">{result.gaps.slice(0, 8).map((g) => <span className="tag" key={g.key}>{g.name}</span>)}</div>
      <Field label="Título"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      <Field label="Fecha objetivo"><input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} /></Field>
      <Field label="Nota para la persona (opcional)"><textarea className="textarea" value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} /></Field>
    </Modal>
  );
}

function Compare({ results, onClose }) {
  const reqs = results[0].requirements.map((r) => r.name);
  const mark = (res, name) => {
    const r = res.requirements.find((x) => x.name === name);
    return r?.status === "met" ? <Badge tone="good">Cumple</Badge> : r?.status === "partial" ? <Badge tone="warning">Parcial</Badge> : <Badge tone="critical">No</Badge>;
  };
  const cols = `minmax(160px, 1fr) repeat(${results.length}, minmax(150px, 1fr))`;
  return (
    <Modal wide title="Comparar perfiles" sub="Mismo cargo, mismos pesos. Compare evidencias, no solo porcentajes." onClose={onClose}>
      <div className="compare" style={{ gridTemplateColumns: cols }}>
        <div className="h rowlabel" />{results.map((r) => <div className="h" key={r.id}>{r.full_name}<div className="muted xs">{r.job_title}</div></div>)}
        <div className="rowlabel">Compatibilidad</div>{results.map((r) => <div key={r.id}><MiniScore score={r.score} components={r.components} /></div>)}
        <div className="rowlabel">Elegible</div>{results.map((r) => <div key={r.id}>{r.eligible ? "Sí" : <span style={{ color: "var(--critical)" }}>No: {r.mandatory_unmet.join(", ")}</span>}</div>)}
        <div className="rowlabel">Años acreditados</div>{results.map((r) => <div key={r.id} className="num">{r.years_experience} años</div>)}
        {COMPONENTS.map((c) => <Fragment key={`l${c.key}`}><div className="rowlabel">{c.label}</div>
          {results.map((r) => <div key={r.id + c.key} className="num">{r.components[c.key].applicable ? `${r.components[c.key].value} %` : "No aplica"}</div>)}</Fragment>)}
        {reqs.map((n) => <Fragment key={`r${n}`}><div className="rowlabel">{n}</div>{results.map((r) => <div key={r.id + n}>{mark(r, n)}</div>)}</Fragment>)}
      </div>
    </Modal>
  );
}

export default function Matching() {
  const [params, setParams] = useSearchParams();
  const positions = useApi("/positions?status=open");
  const pid = params.get("position") || positions.data?.[0]?.id;
  const position = positions.data?.find((p) => String(p.id) === String(pid));
  const latest = useApi(pid ? `/positions/${pid}/latest-run` : null, [pid]);
  const runs = useApi(pid ? `/positions/${pid}/runs` : null, [pid]);
  const decisions = useApi(pid ? `/positions/${pid}/decisions` : null, [pid]);
  const [weights, setWeights] = useState(null);
  const [showW, setShowW] = useState(false);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);
  const [pick, setPick] = useState([]);
  const [cmp, setCmp] = useState(false);
  const [assign, setAssign] = useState(null);
  const [tab, setTab] = useState("results");
  const [run, busy] = useAsync();
  useEffect(() => { setWeights(position?.weights || null); setPick([]); setOpen(null); }, [position?.id]); // eslint-disable-line

  const results = useMemo(() => (latest.data?.results || []).filter((r) => filter === "all" || (filter === "eligible" ? r.eligible : r.score >= 70)), [latest.data, filter]);
  if (positions.loading && !positions.data) return <Loading />;
  if (positions.error) return <ErrorState error={positions.error} onRetry={positions.reload} />;
  if (!positions.data.length) return <><PageHead title="Matching" /><Panel><Empty icon={GaugeCircle} title="No hay cargos abiertos">Cree un proyecto y un cargo con requisitos para ejecutar el matching.</Empty></Panel></>;

  const execute = (custom) => run(() => post(`/positions/${pid}/match`, custom ? { weights } : {}), "Matching ejecutado").then((r) => {
    if (r) { latest.setData(r); runs.reload(); setTab("results"); }
  });
  const openRes = open && latest.data?.results.find((r) => r.id === open);
  const togglePick = (id) => setPick((xs) => (xs.includes(id) ? xs.filter((x) => x !== id) : xs.length < 3 ? [...xs, id] : xs));

  return (
    <>
      <PageHead title="Matching de talento" sub="Compare los perfiles publicados con un cargo. El sistema ordena y explica; usted decide."
                actions={<>
                  <select className="select" style={{ minWidth: 300 }} aria-label="Cargo" value={pid || ""} onChange={(e) => setParams({ position: e.target.value })}>
                    {positions.data.map((p) => <option key={p.id} value={p.id}>{p.title} · {p.project_name}</option>)}
                  </select>
                  <Button icon={SlidersHorizontal} onClick={() => setShowW((s) => !s)} aria-expanded={showW}>Ponderación</Button>
                  <Button variant="primary" icon={Play} loading={busy} onClick={() => execute(false)}>Ejecutar matching</Button>
                </>} />
      {position && (
        <Panel className="" title={position.title} hint={`${position.project_name} · ${position.openings} vacante(s) · ${position.min_years ? `${position.min_years} años${position.min_years_mandatory ? " (obligatorio)" : ""}` : "sin años mínimos"} · ${position.education_label}`}>
          <div className="tags">{position.requirements.map((r) => <span key={r.id} className="tag"
            style={r.importance === "mandatory" ? { borderColor: "var(--accent)", color: "var(--accent-ink)" } : undefined}>{r.name}{r.importance === "mandatory" ? " · obligatorio" : ""}</span>)}</div>
          {showW && weights && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line-2)" }}>
              <WeightsEditor value={weights} onChange={setWeights} />
              <div className="row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
                <Button onClick={() => setWeights(position.weights)}>Restablecer los del cargo</Button>
                <Button variant="primary" loading={busy} onClick={() => execute(true)}>Ejecutar con esta ponderación</Button>
              </div>
            </div>
          )}
        </Panel>
      )}
      <div style={{ height: 16 }} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "results", label: "Resultados", count: latest.data?.results.length ?? 0 },
        { value: "decisions", label: "Decisiones", count: decisions.data?.length ?? 0 }, { value: "history", label: "Ejecuciones", count: runs.data?.length ?? 0 }]} />
      {tab === "results" && (latest.loading && !latest.data ? <Loading /> : !latest.data ? (
        <Panel><Empty icon={GaugeCircle} title="Este cargo aún no tiene resultados" action={<Button variant="primary" icon={Play} loading={busy} onClick={() => execute(false)}>Ejecutar matching</Button>}>
          Se evaluarán todos los perfiles publicados con autorización vigente.</Empty></Panel>
      ) : (
        <>
          <div className="filters">
            <Segmented label="Filtrar resultados" value={filter} onChange={setFilter} options={[{ value: "all", label: "Todos" },
              { value: "eligible", label: `Elegibles (${latest.data.eligible})` }, { value: "70", label: "70 % o más" }]} />
            <span className="muted small">Ejecutado {fmtDateTime(latest.data.created_at)} por {latest.data.run_by} · {latest.data.evaluated} perfiles evaluados</span>
            <span className="spacer" />
            <Button icon={Columns3} disabled={pick.length < 2} onClick={() => setCmp(true)}>Comparar ({pick.length})</Button>
          </div>
          <Panel flush>
            {results.length === 0 ? <Empty title="Ningún perfil con este filtro" /> : (
              <div className="table-wrap"><table className="t">
                <thead><tr><th style={{ width: 36 }}><span className="visually-hidden">Comparar</span></th><th className="r">#</th><th>Persona</th><th style={{ minWidth: 200 }}>Compatibilidad</th><th>Requisitos</th><th>Brechas principales</th><th>Decisión</th></tr></thead>
                <tbody>{results.map((r) => (
                  <tr key={r.id} className={`clickable ${open === r.id ? "selected" : ""}`} onClick={() => setOpen(r.id)}>
                    <td onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`Comparar ${r.full_name}`} checked={pick.includes(r.id)} onChange={() => togglePick(r.id)} /></td>
                    <td className="r num muted">{r.rank}</td>
                    <td><div className="row"><Avatar name={r.full_name} /><div><div className="cell-title">{r.full_name}</div><div className="cell-sub">{r.job_title} · {r.years_experience} años</div></div></div></td>
                    <td><MiniScore score={r.score} components={r.components} /></td>
                    <td className="small">{r.eligible ? <Badge tone="good">Elegible</Badge> : <Badge tone="warning">Falta obligatorio</Badge>}
                      <div className="cell-sub">{r.matched.length}/{r.requirements.length} cumplidos</div></td>
                    <td className="small muted">{r.gaps.slice(0, 3).map((g) => g.name).join(", ") || "Ninguna"}</td>
                    <td>{r.decision ? <Badge tone="accent">{r.decision.label}</Badge> : <span className="muted small nowrap">Sin decisión</span>}</td>
                  </tr>))}</tbody>
              </table></div>
            )}
          </Panel>
          <p className="muted xs" style={{ marginTop: 8 }}>Primero aparecen quienes cumplen todos los requisitos obligatorios. El puntaje usa solo información confirmada y publicada por cada persona.</p>
        </>
      ))}
      {tab === "decisions" && (
        <Panel flush>{!decisions.data?.length ? <Empty title="Sin decisiones registradas">Abra un resultado y registre una decisión justificada.</Empty> : (
          <ul className="list">{decisions.data.map((d) => (
            <li key={d.id}><div className="row between"><span className="strong">{d.full_name}</span><Badge tone="accent">{d.label}</Badge></div>
              <p className="small" style={{ marginTop: 4 }}>{d.justification}</p>
              <div className="cell-sub">{d.decided_by} · {fmtDateTime(d.created_at)}{d.score_at_decision != null ? ` · puntaje al decidir ${d.score_at_decision} %` : ""}</div></li>))}</ul>
        )}</Panel>
      )}
      {tab === "history" && (
        <Panel flush>{!runs.data?.length ? <Empty icon={History} title="Sin ejecuciones" /> : (
          <table className="t"><thead><tr><th>Fecha</th><th className="r">Evaluados</th><th className="r">Elegibles</th><th>Ponderación</th></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r.id}><td>{fmtDateTime(r.created_at)}</td><td className="r num">{r.evaluated}</td><td className="r num">{r.eligible}</td>
                <td className="small muted">{COMPONENTS.map((c) => `${c.label} ${Math.round(r.weights[c.key] * 100)} %`).join(", ")}</td></tr>))}</tbody></table>
        )}</Panel>
      )}
      {openRes && (
        <Drawer title={openRes.full_name} sub={`${openRes.job_title} · ${openRes.department}`} head={<Avatar name={openRes.full_name} lg />} onClose={() => setOpen(null)}>
          {!openRes.still_published && <Alert tone="warning">La persona retiró su perfil después de esta ejecución.</Alert>}
          <MatchDetail m={openRes} />
          {openRes.still_published && <>
            <div className="row"><Button icon={GraduationCap} disabled={!openRes.gaps.length} onClick={() => setAssign(openRes)}>Asignar ruta de aprendizaje</Button></div>
            <DecisionForm positionId={pid} result={openRes} onDone={() => { latest.reload(); decisions.reload(); }} />
          </>}
        </Drawer>
      )}
      {cmp && <Compare results={latest.data.results.filter((r) => pick.includes(r.id))} onClose={() => setCmp(false)} />}
      {assign && <AssignPath result={assign} position={position} onClose={() => setAssign(null)} />}
    </>
  );
}
