import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import authService from "../services/authService";

const NAV_ITEMS = [
  { to: "/", label: "工作台", end: true },
  { to: "/detections", label: "物件偵測", end: true },
  { to: "/detections/batch", label: "批次分析", end: true },
  { to: "/detections/history", label: "偵測紀錄", end: true },
  { to: "/chat", label: "AI 助理", end: true, assistant: true },
];

export default function Layout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => { document.getElementById("main-content")?.focus(); }, [pathname]);
  const [menuOpen, setMenuOpen] = useState(false);
  const user = authService.getCurrentUser();

  function handleLogout() {
    authService.clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className={`app-layout${menuOpen ? " navigation-open" : ""}`}
      onKeyDown={(event) => {
        if (event.key === "Escape" && menuOpen) {
          setMenuOpen(false);
          document.querySelector(".mobile-topbar button")?.focus();
        }
      }}>
      <a className="skip-link" href="#main-content">跳至主要內容</a>
      <header className="mobile-topbar">
        <NavLink to="/" onClick={() => setMenuOpen(false)}>YOLO System</NavLink>
        <button type="button" className="button button-secondary" aria-expanded={menuOpen}
          aria-controls="app-navigation" onClick={() => setMenuOpen((open) => !open)}>
          {menuOpen ? "關閉選單" : "開啟選單"}
        </button>
      </header>
      <aside id="app-navigation" className="sidebar" aria-label="網站導覽"
        onClick={(event) => { if (event.target.closest("a")) setMenuOpen(false); }}>
        <div className="brand-block">
          <div className="brand-kicker">YOLO System</div>
          <p className="brand-title">Web Console</p>
          <p className="muted">AI 物件偵測分析平台</p>
        </div>

        <nav className="nav-list" aria-label="主選單">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.assistant && pathname === "/agent" ? "/agent" : item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive || (item.assistant && pathname === "/agent") ? "nav-link nav-link-active" : "nav-link"
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
              使用者管理
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-chip-title">{user?.nickname || user?.username}</div>
            <div className="muted small">
              {user?.is_admin ? "管理員" : "一般使用者"}
            </div>
          </div>
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
          >
            個人資料
          </NavLink>
          <button type="button" className="button button-secondary" onClick={handleLogout}>
            登出
          </button>
        </div>
      </aside>

      <main id="main-content" tabIndex={-1} className="content-shell">
        <Outlet />
      </main>
    </div>
  );
}
