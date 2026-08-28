import { Link } from "react-router-dom";

import authService from "../services/authService";

/* ─── Inline SVG icons (Heroicons v2 outline, 20×20) ────────── */

function ScanIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7.5 3.75H6A2.25 2.25 0 003.75 6v1.5M16.5 3.75H18A2.25 2.25 0 0120.25 6v1.5m0 9V18A2.25 2.25 0 0118 20.25h-1.5m-9 0H6A2.25 2.25 0 013.75 18v-1.5M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function StackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  );
}

function AgentIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="icon-card-arrow" aria-hidden="true">
      <path d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
  );
}

/* ─── Nav card definitions ───────────────────────────────────── */

const NAV_LINKS = [
  {
    to: "/detections",
    icon: <ScanIcon />,
    title: "Object Detection",
    description: "上傳圖片，即時辨識並標注畫面中的物件。",
  },
  {
    to: "/detections/batch",
    icon: <StackIcon />,
    title: "Batch Analysis",
    description: "一次上傳多張影像或整個資料夾，逐張偵測並彙總統計結果。",
  },
  {
    to: "/detections/history",
    icon: <ClockIcon />,
    title: "Detection Records",
    description: "查詢歷史偵測紀錄，依狀態或類型篩選，查看物件詳情。",
  },
  {
    to: "/chat",
    icon: <ChatIcon />,
    title: "AI Chat",
    description: "與 AI 進行多輪對話，適合一般問題諮詢與知識查詢。",
  },
  {
    to: "/agent",
    icon: <AgentIcon />,
    title: "Detection Analyst",
    description: "深度分析偵測結果與歷史趨勢，並自動產出偵測報告。",
  },
  {
    to: "/profile",
    icon: <UserIcon />,
    title: "Profile",
    description: "查看帳號資訊、角色與帳號狀態。",
  },
];

/* ─── NavCard component ──────────────────────────────────────── */

function NavCard({ to, icon, title, description }) {
  return (
    <Link to={to} className="panel panel-link">
      <div className="icon-card">
        <div className="icon-card-header">
          <div className="icon-card-icon">{icon}</div>
          <ArrowRightIcon />
        </div>
        <div>
          <h2>{title}</h2>
          <p className="muted small">{description}</p>
        </div>
      </div>
    </Link>
  );
}

/* ─── Page ───────────────────────────────────────────────────── */

export default function DashboardPage() {
  const user = authService.getCurrentUser();
  const displayName = user?.nickname || user?.username || "—";

  return (
    <div className="page-stack">

      {/* Hero */}
      <section className="hero-panel">
        <div>
          <div className="eyebrow">Dashboard</div>
          <h1>{displayName}</h1>
          <p className="muted" style={{ maxWidth: "52ch" }}>
            {user?.is_admin
              ? "以管理員身分登入。可管理使用者帳號、執行偵測，並與 AI Agent 互動分析結果。"
              : "以一般使用者身分登入。執行圖片偵測、查詢歷史紀錄，或透過 AI Agent 深入分析。"}
          </p>
        </div>

        {/* Account stat cards */}
        <div className="summary-grid summary-grid-compact">
          <div className="stat-card">
            <span className="stat-label">Role</span>
            {user?.is_admin ? (
              <span className="status-badge status-processing">Admin</span>
            ) : (
              <span className="status-badge status-completed">User</span>
            )}
          </div>
          <div className="stat-card">
            <span className="stat-label">Account Status</span>
            {user?.is_active ? (
              <span className="status-badge status-completed">Active</span>
            ) : (
              <span className="status-badge status-failed">Inactive</span>
            )}
          </div>
          <div className="stat-card">
            <span className="stat-label">Member Since</span>
            <strong>{user?.register_time ? String(user.register_time).slice(0, 10) : "—"}</strong>
          </div>
        </div>
      </section>

      {/* Feature navigation */}
      <section aria-label="功能入口">
        <p className="section-label">功能入口</p>
        <div className="card-grid">
          {NAV_LINKS.map((item) => (
            <NavCard key={item.to} {...item} />
          ))}
          {user?.is_admin && (
            <NavCard
              to="/admin/users"
              icon={<UsersIcon />}
              title="User Management"
              description="建立、搜尋與刪除使用者帳號；僅管理員可存取。"
            />
          )}
        </div>
      </section>

    </div>
  );
}
