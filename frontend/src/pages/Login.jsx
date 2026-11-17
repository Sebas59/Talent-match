import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { Alert, Button, Field } from "../ui/index.jsx";

// Cuentas de DEMOSTRACIÓN (datos sintéticos de scripts/demo_data.py). No son credenciales reales.
const DEMO = [
  { label: "Empleada · flujo completo desde cero", email: "sofia.arango@talentmatch.demo", password: "EmpleadoDemo2026!" },
  { label: "Empleada con perfil publicado", email: "valentina.ospina@talentmatch.demo", password: "EmpleadoDemo2026!" },
  { label: "Recursos Humanos", email: "rrhh@talentmatch.demo", password: "RrhhDemo2026!" },
  { label: "Administración", email: "admin@talentmatch.demo", password: "AdminDemo2026!" },
];
const HOME = { employee: "/app", hr: "/rrhh", admin: "/admin" };

export default function Login() {
  const { signIn } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState(false);
  useEffect(() => { fetch("/health").then((r) => r.json()).then((h) => setDemo(Boolean(h.demo_mode))).catch(() => {}); }, []);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (!email || !password) { setError("Escriba su correo y contraseña."); return; }
    setBusy(true);
    try {
      const u = await signIn(email.trim(), password);
      const from = loc.state?.from;
      nav(from && from.startsWith(HOME[u.role]) ? from : HOME[u.role], { replace: true });
    } catch (err) {
      setError(err.status === 401 ? "Correo o contraseña incorrectos. Tras 5 intentos la cuenta se bloquea 15 minutos."
        : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-aside">
        <div>
          <div className="row" style={{ marginBottom: 40 }}>
            <span className="brand-mark" style={{ background: "rgba(255,255,255,.14)" }} aria-hidden>
              <svg width="16" height="16" viewBox="0 0 16 16"><path d="M1 13h3V8H1zm5 0h3V3H6zm5 0h3V6h-3z" fill="#fff" /></svg>
            </span>
            <strong style={{ color: "#fff" }}>Talent Match</strong>
          </div>
          <h1>Encuentre primero el talento que ya trabaja con usted.</h1>
          <p>Perfiles construidos por cada empleado, compatibilidad explicable con los cargos de sus proyectos
            y rutas de formación para cerrar brechas. La IA recomienda; las personas deciden.</p>
        </div>
        <div className="stack">
          {demo && <div className="auth-demo">
            <h2>Cuentas de demostración</h2>
            {DEMO.map((d) => (
              <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword(d.password); }}>
                <span>{d.label}</span><span>{d.email}</span>
              </button>
            ))}
          </div>}
          <p className="team">Proyecto académico, Universidad Católica de Colombia. Electiva Problem Discovery & Solution
            Design with AI. Docente: Juan Carlos Navarro Beltrán. Equipo: Juan Sebastián Lozano Calderón, Andrés David
            Rojas Villamil, Juan Sebastián López Urrego, Jeison Oswaldo Romero Cajamarca.</p>
        </div>
      </section>
      <section className="auth-main">
        <form className="auth-form" onSubmit={submit} noValidate>
          <div>
            <h2 style={{ fontSize: "1.35rem" }}>Iniciar sesión</h2>
            <p className="muted small" style={{ marginTop: 4 }}>Use su correo corporativo.</p>
          </div>
          {error && <Alert tone="critical">{error}</Alert>}
          <Field label="Correo">
            <input className="input" type="email" autoComplete="username" value={email} maxLength={254}
                   onChange={(e) => setEmail(e.target.value)} aria-invalid={Boolean(error)} />
          </Field>
          <Field label="Contraseña">
            <input className="input" type="password" autoComplete="current-password" value={password} maxLength={128}
                   onChange={(e) => setPassword(e.target.value)} aria-invalid={Boolean(error)} />
          </Field>
          <Button variant="primary" type="submit" loading={busy}>Iniciar sesión</Button>
          <p className="muted xs">¿Recibió una invitación? Abra el enlace que le compartió Recursos Humanos para crear su contraseña.</p>
        </form>
      </section>
    </div>
  );
}
