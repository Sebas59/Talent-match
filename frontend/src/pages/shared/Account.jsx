import { useState } from "react";
import { post } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { Button, Field, PageHead, Panel, useAsync } from "../../ui/index.jsx";

export default function Account() {
  const { user } = useAuth();
  const [cur, setCur] = useState("");
  const [pw, setPw] = useState("");
  const [run, busy] = useAsync();
  const strong = pw.length >= 12 && /[A-Za-z]/.test(pw) && /\d/.test(pw);
  return (
    <>
      <PageHead title="Mi cuenta" />
      <div className="grid g2">
        <Panel title="Datos de la cuenta">
          <dl className="kv"><dt>Nombre</dt><dd>{user.full_name}</dd><dt>Correo</dt><dd>{user.email}</dd><dt>Rol</dt><dd>{user.role_label}</dd>
            <dt>Área</dt><dd>{user.department || "—"}</dd><dt>Cargo</dt><dd>{user.job_title || "—"}</dd></dl>
          <p className="muted xs" style={{ marginTop: 12 }}>El nombre y el correo se guardan cifrados. Los cambios de rol los gestiona el administrador.</p>
        </Panel>
        <Panel title="Cambiar contraseña" hint="Se cerrarán sus demás sesiones abiertas">
          <form className="stack" onSubmit={(e) => { e.preventDefault(); run(() => post("/auth/password", { current_password: cur, new_password: pw }), "Contraseña actualizada").then(() => { setCur(""); setPw(""); }); }}>
            <Field label="Contraseña actual"><input className="input" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
            <Field label="Nueva contraseña" help="Mínimo 12 caracteres, con letras y números." error={pw && !strong ? "Aún no cumple los requisitos" : null}>
              <input className="input" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
            <div><Button variant="primary" type="submit" loading={busy} disabled={!cur || !strong}>Actualizar contraseña</Button></div>
          </form>
        </Panel>
      </div>
    </>
  );
}
