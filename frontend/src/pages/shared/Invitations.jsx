import { useState } from "react";
import { Copy, UserPlus } from "lucide-react";
import { del, post } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { useApi } from "../../hooks.js";
import { Alert, Badge, Button, Empty, ErrorState, Field, Loading, Modal, PageHead, Panel, useAsync, useToast } from "../../ui/index.jsx";
import { fmtDate } from "../../format.js";

const ST = { pending: ["Pendiente", "warning"], accepted: ["Aceptada", "good"], revoked: ["Revocada", "muted"], expired: ["Vencida", "muted"] };
const ROLE = { employee: "Empleado", hr: "Recursos Humanos", admin: "Administrador" };

export default function Invitations() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi("/invitations");
  const [form, setForm] = useState(false);
  const [created, setCreated] = useState(null);
  const [run] = useAsync();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  return (
    <>
      <PageHead title="Invitaciones" sub={user.role === "hr" ? "Invite empleados para que creen su cuenta y gestionen su propio perfil." : "Invite empleados, personal de RR. HH. o administradores."}
                actions={<Button variant="primary" icon={UserPlus} onClick={() => setForm(true)}>Nueva invitación</Button>} />
      <Panel flush>
        {data.length === 0 ? <Empty icon={UserPlus} title="Sin invitaciones" action={<Button variant="primary" onClick={() => setForm(true)}>Invitar a alguien</Button>} /> : (
          <div className="table-wrap"><table className="t">
            <thead><tr><th>Persona</th><th>Rol</th><th>Área</th><th>Estado</th><th>Vence</th><th /></tr></thead>
            <tbody>{data.map((i) => (
              <tr key={i.id}><td><div className="cell-title">{i.full_name}</div><div className="cell-sub">{i.email}</div></td>
                <td className="small">{ROLE[i.role]}</td><td className="small">{i.department || "—"}</td>
                <td><Badge tone={ST[i.status][1]}>{ST[i.status][0]}</Badge></td>
                <td className="small">{i.status === "pending" ? fmtDate(i.expires_at) : "—"}</td>
                <td className="r">{i.status === "pending" && <Button size="sm" variant="ghost" onClick={() => run(() => del(`/invitations/${i.id}`), "Invitación revocada").then(reload)}>Revocar</Button>}</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Panel>
      {form && <InviteForm isAdmin={user.role === "admin"} onClose={() => setForm(false)} onCreated={(inv) => { setForm(false); setCreated(inv); reload(); }} />}
      {created && <CreatedLink inv={created} onClose={() => setCreated(null)} />}
    </>
  );
}

function InviteForm({ isAdmin, onClose, onCreated }) {
  const [f, setF] = useState({ email: "", full_name: "", role: "employee", department: "", job_title: "" });
  const [run, busy] = useAsync();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const valid = /\S+@\S+\.\S+/.test(f.email) && f.full_name.trim().length >= 3;
  return (
    <Modal title="Nueva invitación" sub="Se genera un enlace de un solo uso, válido 7 días." onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={!valid}
             onClick={() => run(() => post("/invitations", { ...f, department: f.department || null, job_title: f.job_title || null })).then((r) => r && onCreated(r))}>Crear invitación</Button></>}>
      <Field label="Nombre completo"><input className="input" value={f.full_name} onChange={set("full_name")} /></Field>
      <Field label="Correo corporativo"><input className="input" type="email" value={f.email} onChange={set("email")} /></Field>
      <div className="grid g2">
        <Field label="Área"><input className="input" value={f.department} onChange={set("department")} /></Field>
        <Field label="Cargo actual"><input className="input" value={f.job_title} onChange={set("job_title")} /></Field>
      </div>
      {isAdmin && <Field label="Rol"><select className="select" value={f.role} onChange={set("role")}>{Object.entries(ROLE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>}
    </Modal>
  );
}

function CreatedLink({ inv, onClose }) {
  const toast = useToast();
  const url = `${window.location.origin}${inv.invite_url}`;
  return (
    <Modal title="Invitación creada" onClose={onClose} footer={<Button variant="primary" onClick={onClose}>Listo</Button>}>
      <Alert tone="info">Comparta este enlace con {inv.full_name} por un canal seguro. Solo se muestra esta vez: en la base de datos se guarda únicamente su huella.</Alert>
      <div className="row"><input className="input" readOnly value={url} aria-label="Enlace de invitación" onFocus={(e) => e.target.select()} />
        <Button icon={Copy} onClick={() => navigator.clipboard?.writeText(url).then(() => toast("Enlace copiado"))}>Copiar</Button></div>
      <p className="muted xs">En producción este enlace se enviaría por correo electrónico.</p>
    </Modal>
  );
}
