import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Button, Field, Loading } from "../ui/index.jsx";
import { fmtDate } from "../format.js";

export default function Invite() {
  const { token } = useParams();
  const [inv, setInv] = useState(null);
  const [error, setError] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api(`/invitations/token/${token}`).then(setInv).catch((e) => setError(e.message)); }, [token]);
  const strong = pw.length >= 12 && /[A-Za-z]/.test(pw) && /\d/.test(pw);

  async function accept(e) {
    e.preventDefault();
    if (!strong || pw !== pw2) return;
    setBusy(true);
    try { setDone(await api(`/invitations/token/${token}/accept`, { method: "POST", json: { password: pw } })); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <div className="auth-page">
      <section className="auth-aside">
        <div>
          <strong style={{ color: "#fff" }}>Talent Match</strong>
          <h1 style={{ marginTop: 40 }}>Su espacio profesional dentro de la organización.</h1>
          <p>Usted decide qué información de su hoja de vida se confirma y se publica. Recursos Humanos solo ve lo que
            usted publique, y puede retirarlo cuando quiera.</p>
        </div>
      </section>
      <section className="auth-main">
        <div className="auth-form">
          {!inv && !error && <Loading label="Verificando invitación…" />}
          {error && !done && <Alert tone="critical" title="No se puede usar esta invitación">{error}. Pida una nueva a Recursos Humanos.</Alert>}
          {done && (
            <>
              <Alert tone="good" title="Cuenta creada">Ya puede iniciar sesión con {done.email}.</Alert>
              <Link className="btn primary" to="/login">Ir a iniciar sesión</Link>
            </>
          )}
          {inv && !done && (
            <form onSubmit={accept} className="stack" noValidate>
              <div>
                <h2 style={{ fontSize: "1.35rem" }}>Hola, {inv.full_name.split(" ")[0]}</h2>
                <p className="muted small" style={{ marginTop: 4 }}>
                  {inv.organization} le invitó como {inv.role_label.toLowerCase()} ({inv.email_masked}).
                  La invitación vence el {fmtDate(inv.expires_at)}.</p>
              </div>
              <Field label="Cree su contraseña" help="Mínimo 12 caracteres, con al menos una letra y un número."
                     error={pw && !strong ? "Aún no cumple los requisitos." : null}>
                <input className="input" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
              </Field>
              <Field label="Repita la contraseña" error={pw2 && pw !== pw2 ? "Las contraseñas no coinciden." : null}>
                <input className="input" type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
              </Field>
              <Button variant="primary" type="submit" loading={busy} disabled={!strong || pw !== pw2}>Crear cuenta</Button>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}
