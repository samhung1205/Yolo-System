import { useEffect, useState } from "react";
import detectionService from "../services/detectionService";
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

function UsersIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  );
}

/* ─── Nav card definitions ───────────────────────────────────── */

const NAV_LINKS = [
  {
    to: "/detections",
    icon: <ScanIcon />,
    title: "物件偵測",
    description: "上傳圖片，即時辨識並標注畫面中的物件。",
  },
  {
    to: "/detections/batch",
    icon: <StackIcon />,
    title: "批次分析",
    description: "一次上傳多張影像或整個資料夾，逐張偵測並彙總統計結果。",
  },
  {
    to: "/detections/history",
    icon: <ClockIcon />,
    title: "偵測紀錄",
    description: "查詢歷史偵測紀錄，依狀態或類型篩選，查看物件詳情。",
  },
  {
    to: "/chat",
    icon: <ChatIcon />,
    title: "AI 助理",
    description: "進行一般對話，或根據已保存結果分析偵測資料。",
  },
  {
    to: "/profile",
    icon: <UserIcon />,
    title: "個人資料",
    description: "查看帳號資訊、角色與帳號狀態。",
  },
];

export default function DashboardPage() {
  const user = authService.getCurrentUser();
  const displayName = user?.nickname || user?.username || "—";

  const [recent, setRecent] = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setRecentLoading(true); setRecentError(false);
    Promise.allSettled([
      detectionService.listDetections({ limit: 5, signal: controller.signal }),
      detectionService.listBatches({ limit: 3, signal: controller.signal }),
    ]).then((results) => {
      if (!active) return;
      setRecentError(results.some((result) => result.status === "rejected"));
      setRecent(results.flatMap((result, index) => result.status === "fulfilled"
        ? result.value.items.map((item) => ({ ...item, kind: index ? "batch" : "detection" })) : [])
        .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, 6));
      setRecentLoading(false);
    });
    return () => { active = false; controller.abort(); };
  }, [revision]);
  return (
    <div className="page-stack dashboard-page">
      <header className="page-header">
        <div><h1>影像偵測工作台</h1><p className="muted">{displayName}，從影像開始，讓偵測結果成為分析依據。</p></div>
      </header>
      <section className="dashboard-start" aria-label="開始偵測">
        <div><ScanIcon /><h2>辨識一張影像</h2><p>上傳影像、選擇模型，對照原圖與標註結果。</p>
          <Link className="button" to="/detections">開始單張偵測</Link></div>
        <div className="dashboard-batch-entry"><StackIcon /><h2>分析一批影像</h2><p>選取多張影像或資料夾，逐張偵測並彙總結果。</p>
          <Link className="button button-secondary" to="/detections/batch">開始批次偵測</Link></div>
      </section>
      <section className="recent-work" aria-labelledby="recent-work-title">
        <div className="section-title-row"><h2 id="recent-work-title">繼續最近工作</h2><Link className="text-link" to="/detections/history">查看偵測紀錄</Link></div>
        {recentLoading && <p role="status" className="muted">載入最近工作…</p>}
        {recentError && <p role="alert">部分紀錄無法載入。<button type="button" className="button-ghost" onClick={() => setRevision(revision + 1)}>重試</button></p>}
        {!recentLoading && !recent.length && !recentError && <p className="muted">尚無偵測紀錄。完成第一筆偵測後，可從這裡繼續分析。</p>}
        <div className="recent-work-list">{recent.map((item) => {
          const ready = ["completed", "completed_with_errors"].includes(item.status);
          const destination = ready ? `/agent?mode=${item.kind === "batch" ? "batch_analysis&batch_id" : "explain_detection&detection_id"}=${item.id}`
            : item.kind === "batch" ? "/detections/batch" : "/detections/history";
          return <Link key={`${item.kind}-${item.id}`} className="recent-result-row" to={destination}>
            <div><strong>{item.kind === "batch" ? item.name || `批次 #${item.id}` : item.source_filename}</strong>
              <span className="muted small">{item.kind === "batch" ? `${item.total_files} 張影像` : `${item.object_count} 個物件`} · {String(item.created_at || "").slice(0, 10)}</span></div>
            <span className="text-link">{ready ? "繼續分析" : "查看進度"}</span>
          </Link>;
        })}</div>
      </section>
      <section className="dashboard-tools" aria-label="其他功能">
        <h2>其他功能</h2>
        <div className="dashboard-tool-links">{NAV_LINKS.slice(2).map((item) => <Link key={item.to} to={item.to}>{item.icon}<span>{item.title}</span></Link>)}
          {user?.is_admin && <Link to="/admin/users"><UsersIcon /><span>使用者管理</span></Link>}
        </div>
      </section>
    </div>
  );
}
