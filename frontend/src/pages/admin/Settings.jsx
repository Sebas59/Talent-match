import { useEffect, useState } from "react";
import { put } from "../../api.js";
import { useApi } from "../../hooks.js";
import { Button, ErrorState, Field, Loading, PageHead, Panel, useAsync } from "../../ui/index.jsx";
import { WeightsEditor } from "../hr/Projects.jsx";

export default function Settings() {
  const { data, setData, error, loading, reload } = useApi("/admin/settings");
  const [v, setV] = useState(null);
  const [run, busy] = useAsync();
  useEffect(() => { if (data) setV(data.values); }, [data]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!v) return null;
  const d = data.descriptions;
  const dirty = JSON.stringify(v) !== JSON.stringify(data.values);
  return (
    <>
      <PageHead title="Configuración" sub="Parámetros de la organización. Los cambios quedan en la auditoría."
                actions={<><Button disabled={!dirty} onClick={() => setV(data.values)}>Descartar</Button>
                  <Button variant="primary" disabled={!dirty} loading={busy} onClick={() => run(() => put("/admin/settings", { values: v }), "Configuración guardada").then((r) => r && setData(r))}>Guardar cambios</Button></>} />
      <div className="grid g2">
        <Panel title="Inteligencia artificial">
          <div className="stack">
            <label className="check"><input type="checkbox" checked={v.external_ai_allowed} onChange={(e) => setV({ ...v, external_ai_allowed: e.target.checked })} />
              <span>{d.external_ai_allowed}</span></label>
            <Field label="Proveedor preferido" help={d.preferred_provider}>
              <select className="select" value={v.preferred_provider} onChange={(e) => setV({ ...v, preferred_provider: e.target.value })}>
                <option value="auto">Automático (el que esté configurado)</option><option value="anthropic">Anthropic Claude</option><option value="gemini">Google Gemini</option></select></Field>
            <p className="muted xs">Las claves de API se configuran en el archivo .env del servidor, nunca desde la interfaz.</p>
          </div>
        </Panel>
        <Panel title="Perfiles y disponibilidad">
          <div className="stack">
            <Field label="Competencias confirmadas mínimas para publicar" help={d.min_confirmed_skills_to_publish}>
              <input className="input" type="number" min={1} max={20} value={v.min_confirmed_skills_to_publish} onChange={(e) => setV({ ...v, min_confirmed_skills_to_publish: Number(e.target.value) })} /></Field>
            <Field label="Umbral de disponibilidad (%)" help={d.availability_threshold}>
              <input className="input" type="number" min={1} max={100} value={v.availability_threshold} onChange={(e) => setV({ ...v, availability_threshold: Number(e.target.value) })} /></Field>
            <Field label="Retención de referencia (días)" help={d.retention_days}>
              <input className="input" type="number" min={30} max={3650} value={v.retention_days} onChange={(e) => setV({ ...v, retention_days: Number(e.target.value) })} /></Field>
          </div>
        </Panel>
        <Panel title="Ponderación por defecto para cargos nuevos" hint={d.default_weights}>
          <WeightsEditor value={v.default_weights} onChange={(w) => setV({ ...v, default_weights: w })} />
        </Panel>
        <Panel title="Sesiones"><p className="small">{v.session_idle_note} Los tiempos se definen en variables de entorno (ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_DAYS).</p></Panel>
      </div>
    </>
  );
}
