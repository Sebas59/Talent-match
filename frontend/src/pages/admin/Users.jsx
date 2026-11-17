import { useState } from "react";
import { patch, post } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { useApi, useDebounced } from "../../hooks.js";
import { Alert, Avatar, Badge, Button, ErrorState, Field, Loading, Modal, PageHead, Panel, SearchInput, Segmented, useAsync } from "../../ui/index.jsx";
import { fmtDateTime } from "../../format.js";

export default function Users() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const dq = useDebounced(q);
  const qs = new URLSearchParams({ q: dq, ...(role && { role }) }).toString();
  const { data, error, loading, reload } = useApi(`/admin/users?${qs}`, [qs]);
  const [edit, setEdit] = useState(null);
  const [run] = useAsync();
  if (error) return <ErrorState error={error} onRetry={reload} />;
  return (
    <>
      <PageHead title="Usuarios y roles" sub="Gestione cuentas, roles y sesiones. Cambiar el rol o desactivar una cuenta cierra sus sesiones." />
      <div className="filters">
        <SearchInput value={q} onChange={setQ} placeholder="Nombre, correo o área" />
        <Segmented label="Rol" value={role} onChange={setRole} options={[{ value: "", label: "Todos" }, { value: "employee", label: "Empleados" }, { value: "hr", label: "RR. HH." }, { value: "admin", label: "Administradores" }]} />
      </div>
      <Panel flush>
        {loading && !data ? <Loading /> : (
          <div className="table-wrap"><table className="t">
            <thead><tr><th>Usuario</th><th>Rol</th><th>Área</th><th>Estado</th><th>Último acceso</th><th className="r">Sesiones</th><th /></tr></thead>
            <tbody>{data.map((u) => (
              <tr key={u.id}>
                <td><div className="row"><Avatar name={u.full_name} /><div><div className="cell-title">{u.full_name}</div><div className="cell-sub">{u.email}</div></div></div></td>
                <td><Badge tone={u.role === "admin" ? "violet" : u.role === "hr" ? "accent" : undefined}>{u.role_label}</Badge></td>
                <td className="small">{u.department || "—"}</td>
                <td><div className="row">{u.is_active ? <Badge tone="good">Activo</Badge> : <Badge tone="muted">Inactivo</Badge>}{u.locked && <Badge tone="critical">Bloqueado</Badge>}{u.is_demo && <Badge>Demo</Badge>}</div></td>
                <td className="small">{u.last_login_at ? fmtDateTime(u.last_login_at) : "Nunca"}</td>
                <td className="r num">{u.active_sessions}</td>
                <td className="r"><div className="row" style={{ justifyContent: "flex-end" }}>
                  {u.locked && <Button size="sm" onClick={() => run(() => post(`/admin/users/${u.id}/unlock`), "Cuenta desbloqueada").then(reload)}>Desbloquear</Button>}
                  {u.active_sessions > 0 && u.id !== me.id && <Button size="sm" variant="ghost" onClick={() => run(() => post(`/admin/users/${u.id}/revoke-sessions`), "Sesiones cerradas").then(reload)}>Cerrar sesiones</Button>}
                  <Button size="sm" onClick={() => setEdit(u)}>Editar</Button></div></td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Panel>
      {edit && <EditUser u={edit} self={edit.id === me.id} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />}
    </>
  );
}

function EditUser({ u, self, onClose, onSaved }) {
  const [f, setF] = useState({ role: u.role, is_active: u.is_active, department: u.department || "", job_title: u.job_title || "" });
  const [run, busy] = useAsync();
  return (
    <Modal title={`Editar ${u.full_name}`} onClose={onClose}
           footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} onClick={() => run(() => patch(`/admin/users/${u.id}`, f), "Usuario actualizado").then((r) => r && onSaved())}>Guardar cambios</Button></>}>
      {self && <Alert tone="info">No puede quitarse a sí mismo el rol de administrador ni desactivar su cuenta.</Alert>}
      <Field label="Rol" help="Cada rol ve una aplicación distinta. El administrador no accede a perfiles por serlo.">
        <select className="select" value={f.role} disabled={self} onChange={(e) => setF({ ...f, role: e.target.value })}>
          <option value="employee">Empleado</option><option value="hr">Recursos Humanos</option><option value="admin">Administrador</option></select></Field>
      <div className="grid g2">
        <Field label="Área"><input className="input" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></Field>
        <Field label="Cargo"><input className="input" value={f.job_title} onChange={(e) => setF({ ...f, job_title: e.target.value })} /></Field>
      </div>
      <label className="check"><input type="checkbox" checked={f.is_active} disabled={self} onChange={(e) => setF({ ...f, is_active: e.target.checked })} />Cuenta activa</label>
    </Modal>
  );
}
