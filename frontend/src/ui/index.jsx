import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleAlert, CircleDashed, Info, Search, X, XCircle } from "lucide-react";
import { COMPONENTS, fmtPct } from "../format.js";

/* ------------------------------ Toasts ------------------------------ */
const ToastCtx = createContext(() => {});
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, kind = "ok") => {
    const id = Math.random().toString(36).slice(2);
    setItems((xs) => [...xs, { id, text, kind }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), kind === "error" ? 6000 : 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind === "error" ? "error" : ""}`}>
            {t.kind === "error" ? <XCircle size={17} /> : <CheckCircle2 size={17} />}<span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

/* ------------------------------ Básicos ------------------------------ */
export function Button({ variant, size, icon: Icon, children, loading, className = "", ...rest }) {
  const cls = ["btn", variant, size, !children && Icon ? "icon" : "", className].filter(Boolean).join(" ");
  return (
    <button type="button" className={cls} disabled={loading || rest.disabled} {...rest}>
      {loading ? <span className="spin" aria-hidden /> : Icon ? <Icon size={16} aria-hidden /> : null}
      {children}
    </button>
  );
}

export const Badge = ({ tone, children, icon: Icon, title }) => (
  <span className={`badge ${tone || ""}`} title={title}>{Icon && <Icon size={12} aria-hidden />}{children}</span>
);

export function Panel({ title, hint, actions, children, flush, className = "", id }) {
  return (
    <section className={`panel ${className}`} aria-labelledby={title ? `${id || title}-h` : undefined}>
      {(title || actions) && (
        <div className="panel-head">
          <div>
            {title && <h2 id={`${id || title}-h`}>{title}</h2>}
            {hint && <div className="hint">{hint}</div>}
          </div>
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      <div className={`panel-body ${flush ? "flush" : ""}`}>{children}</div>
    </section>
  );
}

export function PageHead({ title, sub, actions, crumbs }) {
  return (
    <header className="page-head">
      <div>
        {crumbs && <div className="crumbs">{crumbs}</div>}
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}

export const Kpis = ({ items }) => (
  <div className="kpis">
    {items.map((k) => (
      <div className="kpi" key={k.label}>
        <div className="v">{k.value}</div>
        <div className="l">{k.label}</div>
        {k.detail && <div className="d">{k.detail}</div>}
      </div>
    ))}
  </div>
);

export function Empty({ icon: Icon = CircleDashed, title, children, action }) {
  return (
    <div className="empty">
      <div className="ico"><Icon size={22} aria-hidden /></div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export const Loading = ({ label = "Cargando…" }) => (
  <div className="loading" role="status"><span className="spin" aria-hidden />{label}</div>
);

export function ErrorState({ error, onRetry }) {
  return (
    <Alert tone="critical" title="No se pudo cargar la información">
      {error?.message || "Error desconocido."}{" "}
      {onRetry && <button className="btn sm" onClick={onRetry} style={{ marginLeft: 8 }}>Reintentar</button>}
    </Alert>
  );
}

export function Alert({ tone = "info", title, children }) {
  const Icon = { info: Info, warning: AlertTriangle, critical: CircleAlert, good: CheckCircle2 }[tone];
  return (
    <div className={`alert ${tone}`} role={tone === "critical" ? "alert" : "note"}>
      <Icon size={17} aria-hidden />
      <div>{title && <div className="strong">{title}</div>}<div>{children}</div></div>
    </div>
  );
}

export function Field({ label, help, error, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {error ? <span className="err">{error}</span> : help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function SearchInput({ value, onChange, placeholder = "Buscar", label = "Buscar" }) {
  return (
    <div className="search">
      <Search size={15} aria-hidden />
      <input className="input" type="search" aria-label={label} placeholder={placeholder} value={value}
             onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" type="button" aria-selected={value === t.value} onClick={() => onChange(t.value)}>
          {t.label}{t.count != null && <span className="badge">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------ Modal y panel lateral ------------------------------ */
function useEscape(onClose) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
}

export function Modal({ title, sub, onClose, children, footer, wide }) {
  useEscape(onClose);
  const ref = useRef(null);
  const id = useId();
  useEffect(() => { ref.current?.querySelector("input,select,textarea,button")?.focus(); }, []);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={id} ref={ref}>
        <div className="modal-head">
          <div><h2 id={id}>{title}</h2>{sub && <p>{sub}</p>}</div>
          <Button variant="ghost" icon={X} aria-label="Cerrar" onClick={onClose} />
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({ title, sub, onClose, children, head }) {
  useEscape(onClose);
  const id = useId();
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby={id}>
        <div className="drawer-head">
          {head}
          <div style={{ flex: 1, minWidth: 0 }}><h2 id={id}>{title}</h2>{sub && <div className="muted small">{sub}</div>}</div>
          <Button variant="ghost" icon={X} aria-label="Cerrar" onClick={onClose} />
        </div>
        <div className="drawer-body">{children}</div>
      </aside>
    </>
  );
}

export function Confirm({ title, children, confirmLabel, danger, onConfirm, onClose }) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant={danger ? "danger solid" : "primary"} loading={busy}
              onClick={async () => { setBusy(true); try { await onConfirm(); onClose(); } finally { setBusy(false); } }}>
        {confirmLabel}
      </Button></>}>
      <div className="prose">{children}</div>
    </Modal>
  );
}

/* ------------------------------ Datos ------------------------------ */
export const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
export const Avatar = ({ name, lg }) => <span className={`avatar ${lg ? "lg" : ""}`} aria-hidden>{initials(name)}</span>;

export const Progress = ({ value, tone }) => (
  <div className={`progress ${tone || ""}`} role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
    <i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
  </div>
);

export const Ring = ({ value, label }) => (
  <div className="ring" style={{ "--p": value }} role="img" aria-label={`${label || "Completitud"}: ${value} %`}>
    <span>{value}%</span>
  </div>
);

/** Anatomía del puntaje: cada segmento es la contribución (puntos) de un componente; el resto es brecha. */
export function ScoreAnatomy({ components, size, legend = false }) {
  const parts = COMPONENTS.map((c) => ({ ...c, ...(components?.[c.key] || {}) }));
  const label = parts.filter((p) => p.applicable).map((p) => `${p.label} ${p.points} puntos`).join(", ");
  return (
    <div className="anatomy-wrap">
      <div className={`anatomy ${size || ""}`} role="img" aria-label={`Composición del puntaje: ${label}`}>
        {parts.filter((p) => p.applicable && p.points > 0).map((p) => (
          <i key={p.key} style={{ width: `${p.points}%`, background: `var(${p.var})` }}
             title={`${p.label}: ${p.points} puntos (${p.value} % × peso ${Math.round(p.effective_weight * 100)} %)`} />
        ))}
      </div>
      {legend && (
        <div className="anatomy-legend">
          {parts.map((p) => (
            <span key={p.key} className={p.applicable ? "" : "muted"}>
              <i className="swatch" style={{ background: p.applicable ? `var(${p.var})` : "var(--c-gap)" }} />
              {p.label} {p.applicable ? <strong className="num">{p.points}</strong> : "no aplica"}
            </span>
          ))}
          <span><i className="swatch" style={{ background: "var(--c-gap)" }} />Brecha</span>
        </div>
      )}
    </div>
  );
}

export const MiniScore = ({ score, components }) => (
  <div className="mini-score"><ScoreAnatomy components={components} /><span className="score">{fmtPct(score)}</span></div>
);

export function ComponentTable({ components }) {
  return (
    <table className="comp-table">
      <tbody>
        {COMPONENTS.map((c) => {
          const v = components?.[c.key] || {};
          return (
            <tr key={c.key} className={v.applicable ? "" : "na"}>
              <td><span className="row"><i className="swatch" style={{ background: v.applicable ? `var(${c.var})` : "var(--c-gap)" }} />{c.label}</span></td>
              <td className="r">{v.applicable ? `${v.value} %` : "No aplica"}</td>
              <td className="r muted">{v.applicable ? `× ${Math.round(v.effective_weight * 100)} %` : `peso ${Math.round((v.configured_weight || 0) * 100)} % redistribuido`}</td>
              <td className="r strong">{v.applicable ? `${v.points} pts` : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const REQ_KIND = { tech: "Técnica", power: "Power skill", certification: "Certificación" };
export function RequirementList({ requirements }) {
  const icon = (r) => r.status === "met" ? <CheckCircle2 size={17} className="ico-met" aria-label="Cumple" />
    : r.status === "partial" ? <CircleAlert size={17} className="ico-partial" aria-label="Parcial" />
      : <XCircle size={17} className="ico-missing" aria-label="No cumple" />;
  return (
    <div>
      {requirements.map((r) => (
        <div className="req" key={`${r.kind}-${r.key}`}>
          {icon(r)}
          <div>
            <div><span className="strong">{r.name}</span> <span className="muted xs">{REQ_KIND[r.kind]}</span></div>
            {r.status !== "missing" && r.matched_with && (
              <div className="ev">Respaldo: {r.matched_with}{r.match_type && r.match_type !== "exacta" ? ` (coincidencia ${r.match_type})` : ""}
                {r.evidence && r.evidence !== r.matched_with ? ` · “${r.evidence.slice(0, 110)}”` : ""}</div>
            )}
            {r.blocks_eligibility && <div className="ev" style={{ color: "var(--critical)" }}>Obligatorio no cubierto: afecta la elegibilidad</div>}
          </div>
          <div className="row">
            {r.importance === "mandatory" ? <Badge tone="accent">Obligatorio</Badge> : <Badge>Deseable</Badge>}
            <span className="num xs muted" title="Crédito asignado">{Math.round(r.credit * 100)} %</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Barras horizontales con tooltip por fila. */
export function BarList({ rows, max, color = "var(--c-tech)", format = (v) => v, empty = "Sin datos" }) {
  const [hover, setHover] = useState(null);
  if (!rows?.length) return <p className="muted small">{empty}</p>;
  const m = max || Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="bars" role="list">
      {rows.map((r, i) => (
        <div className="bar-row" role="listitem" key={r.label + i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
          <span className="label" title={r.label}>{r.label}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(r.value / m) * 100}%`, background: r.color || color }} /></div>
          <span className="val">{format(r.value)}</span>
          {hover === i && r.tip && <span className="tip">{r.tip}</span>}
        </div>
      ))}
    </div>
  );
}

export function useAsync() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn, okText) => {
    setBusy(true);
    try {
      const r = await fn();
      if (okText) toast(okText);
      return r;
    } catch (e) {
      toast(e.message || "Ocurrió un error", "error");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, [toast]);
  return [run, busy];
}
