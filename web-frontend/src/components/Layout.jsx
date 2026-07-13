import { NavLink, Outlet, useNavigate } from "react-router-dom";

import authService from "../services/authService";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/detections", label: "Object Detection", end: true },
  { to: "/detections/history", label: "Detection Records", end: true },
  { to: "/chat", label: "AI Chat", end: true },
  { to: "/agent", label: "Detection Analyst", end: true },
];

export default function Layout() {
  const navigate = useNavigate();
  const user = authService.getCurrentUser();

  function handleLogout() {
    authService.clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-kicker">YOLO System</div>
          <p className="brand-title">Web Console</p>
          <p className="muted">AI 物件偵測分析平台</p>
        </div>

        <nav className="nav-list" aria-label="主選單">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
          {user?.is_admin ? (
            <NavLink
              to="/admin/users"
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              Admin Users
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-chip-title">{user?.nickname || user?.username}</div>
            <div className="muted small">
              {user?.is_admin ? "Administrator" : "Standard User"}
            </div>
          </div>
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
          >
            Profile
          </NavLink>
          <button type="button" className="button button-secondary" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </aside>

      <main className="content-shell">
        <Outlet />
      </main>
    </div>
  );
}
