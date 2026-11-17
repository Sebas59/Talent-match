import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  BarChart3, BookOpenCheck, BriefcaseBusiness, ClipboardList, FileText, GaugeCircle, GraduationCap, KeyRound,
  LayoutDashboard, LogOut, Menu, Scale, ScrollText, Settings, ShieldCheck, Sparkles, UserCircle2, UserPlus, Users,
} from "lucide-react";
import { useAuth } from "../auth.jsx";
import { Avatar, Button } from "../ui/index.jsx";

export const NAV = {
  employee: [
    { title: "Mi espacio", items: [
      { to: "/app", label: "Inicio", icon: LayoutDashboard, end: true },
      { to: "/app/perfil", label: "Mi perfil", icon: UserCircle2 },
      { to: "/app/cv", label: "Hoja de vida", icon: FileText },
      { to: "/app/oportunidades", label: "Oportunidades", icon: Sparkles },
      { to: "/app/desarrollo", label: "Mi desarrollo", icon: GraduationCap },
    ] },
    { title: "Mis datos", items: [
      { to: "/app/privacidad", label: "Privacidad", icon: ShieldCheck },
      { to: "/app/gobernanza", label: "Cómo funciona la IA", icon: Scale },
    ] },
  ],
  hr: [
    { title: "Gestión del talento", items: [
      { to: "/rrhh", label: "Inicio", icon: LayoutDashboard, end: true },
      { to: "/rrhh/talento", label: "Talento interno", icon: Users },
      { to: "/rrhh/proyectos", label: "Proyectos y cargos", icon: BriefcaseBusiness },
      { to: "/rrhh/matching", label: "Matching", icon: GaugeCircle },
      { to: "/rrhh/desarrollo", label: "Rutas de aprendizaje", icon: BookOpenCheck },
      { to: "/rrhh/analitica", label: "Analítica", icon: BarChart3 },
    ] },
    { title: "Personas", items: [
      { to: "/rrhh/invitaciones", label: "Invitaciones", icon: UserPlus },
      { to: "/rrhh/gobernanza", label: "Gobernanza", icon: Scale },
    ] },
  ],
  admin: [
    { title: "Plataforma", items: [
      { to: "/admin", label: "Inicio", icon: LayoutDashboard, end: true },
      { to: "/admin/usuarios", label: "Usuarios y roles", icon: Users },
      { to: "/admin/invitaciones", label: "Invitaciones", icon: UserPlus },
      { to: "/admin/configuracion", label: "Configuración", icon: Settings },
    ] },
    { title: "Control", items: [
      { to: "/admin/auditoria", label: "Auditoría", icon: ScrollText },
      { to: "/admin/privacidad", label: "Solicitudes de privacidad", icon: ClipboardList },
      { to: "/admin/gobernanza", label: "Gobernanza", icon: Scale },
    ] },
  ],
};

export default function Shell() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const groups = NAV[user.role] || [];
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Navegación principal">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 16 16"><path d="M1 13h3V8H1zm5 0h3V3H6zm5 0h3V6h-3z" fill="#fff" /></svg>
          </span>
          <div><div className="brand-name">Talent Match</div><div className="brand-org">Organización Demo S.A.S.</div></div>
        </div>
        <nav className="nav" onClick={() => setOpen(false)}>
          {groups.map((g) => (
            <div className="nav-group" key={g.title}>
              <div className="nav-group-title">{g.title}</div>
              {g.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={it.end}><it.icon size={17} aria-hidden />{it.label}</NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <Avatar name={user.full_name} />
            <div style={{ minWidth: 0 }}>
              <div className="name">{user.full_name}</div>
              <div className="role">{user.role_label}</div>
            </div>
          </div>
          <nav className="nav" onClick={() => setOpen(false)}>
            <NavLink to={`${user.role === "employee" ? "/app" : user.role === "hr" ? "/rrhh" : "/admin"}/cuenta`}>
              <KeyRound size={17} aria-hidden />Mi cuenta</NavLink>
            <a href="#salir" onClick={(e) => { e.preventDefault(); signOut(); }}><LogOut size={17} aria-hidden />Cerrar sesión</a>
          </nav>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <Button variant="ghost" icon={Menu} aria-label="Abrir menú" onClick={() => setOpen((o) => !o)} />
          <strong>Talent Match</strong>
        </div>
        <main className="page" key={loc.pathname}><Outlet /></main>
      </div>
    </div>
  );
}
