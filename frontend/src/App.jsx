import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Shell from "./layout/Shell.jsx";
import { Loading } from "./ui/index.jsx";
import Login from "./pages/Login.jsx";
import Invite from "./pages/Invite.jsx";
import Account from "./pages/shared/Account.jsx";
import Governance from "./pages/shared/Governance.jsx";
import EmpDashboard from "./pages/employee/Dashboard.jsx";
import EmpProfile from "./pages/employee/Profile.jsx";
import EmpCv from "./pages/employee/Cv.jsx";
import EmpOpportunities from "./pages/employee/Opportunities.jsx";
import EmpDevelopment from "./pages/employee/Development.jsx";
import EmpPrivacy from "./pages/employee/Privacy.jsx";
import HrDashboard from "./pages/hr/Dashboard.jsx";
import HrTalent from "./pages/hr/Talent.jsx";
import HrProjects from "./pages/hr/Projects.jsx";
import HrMatching from "./pages/hr/Matching.jsx";
import HrDevelopment from "./pages/hr/Development.jsx";
import HrAnalytics from "./pages/hr/Analytics.jsx";
import Invitations from "./pages/shared/Invitations.jsx";
import AdminDashboard from "./pages/admin/Dashboard.jsx";
import AdminUsers from "./pages/admin/Users.jsx";
import AdminAudit from "./pages/admin/Audit.jsx";
import AdminPrivacy from "./pages/admin/Privacy.jsx";
import AdminSettings from "./pages/admin/Settings.jsx";

export const HOME = { employee: "/app", hr: "/rrhh", admin: "/admin" };

function Guard({ role, children }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading label="Verificando sesión…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  // La interfaz solo enruta; los permisos reales los verifica el servidor en cada solicitud.
  if (user.role !== role) return <Navigate to={HOME[user.role]} replace />;
  return children;
}

export default function App() {
  const { user, ready } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={ready && user ? <Navigate to={HOME[user.role]} replace /> : <Login />} />
      <Route path="/invite/:token" element={<Invite />} />
      <Route path="/app" element={<Guard role="employee"><Shell /></Guard>}>
        <Route index element={<EmpDashboard />} />
        <Route path="perfil" element={<EmpProfile />} />
        <Route path="cv" element={<EmpCv />} />
        <Route path="oportunidades" element={<EmpOpportunities />} />
        <Route path="oportunidades/:id" element={<EmpOpportunities />} />
        <Route path="desarrollo" element={<EmpDevelopment />} />
        <Route path="privacidad" element={<EmpPrivacy />} />
        <Route path="gobernanza" element={<Governance />} />
        <Route path="cuenta" element={<Account />} />
      </Route>
      <Route path="/rrhh" element={<Guard role="hr"><Shell /></Guard>}>
        <Route index element={<HrDashboard />} />
        <Route path="talento" element={<HrTalent />} />
        <Route path="proyectos" element={<HrProjects />} />
        <Route path="matching" element={<HrMatching />} />
        <Route path="desarrollo" element={<HrDevelopment />} />
        <Route path="analitica" element={<HrAnalytics />} />
        <Route path="invitaciones" element={<Invitations />} />
        <Route path="gobernanza" element={<Governance />} />
        <Route path="cuenta" element={<Account />} />
      </Route>
      <Route path="/admin" element={<Guard role="admin"><Shell /></Guard>}>
        <Route index element={<AdminDashboard />} />
        <Route path="usuarios" element={<AdminUsers />} />
        <Route path="invitaciones" element={<Invitations />} />
        <Route path="configuracion" element={<AdminSettings />} />
        <Route path="auditoria" element={<AdminAudit />} />
        <Route path="privacidad" element={<AdminPrivacy />} />
        <Route path="gobernanza" element={<Governance />} />
        <Route path="cuenta" element={<Account />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? HOME[user.role] : "/login"} replace />} />
    </Routes>
  );
}
