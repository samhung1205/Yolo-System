import { useReducer } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { AssistantStateContext, updateWorkspace } from "../state/assistantState";

export default function AssistantWorkspace() {
  const [state, dispatch] = useReducer(updateWorkspace, { chat: {}, agent: {} });
  const { pathname } = useLocation();
  const isAnalysis = pathname === "/agent";

  return (
    <AssistantStateContext.Provider value={{ state, dispatch }}>
      <div className="page-stack assistant-workspace">
        <header className="page-header">
          <div>
            <h1>AI 助理</h1>
            <p className="muted">{isAnalysis
              ? "選擇已保存的偵測結果，解釋物件、分析趨勢或產生報告。"
              : "詢問一般問題，或切換至偵測分析，讓回覆以已保存的結果為依據。"}</p>
          </div>
        </header>
        <nav className="assistant-tabs" aria-label="AI 助理功能">
          <NavLink to="/chat" end>一般對話</NavLink>
          <NavLink to="/agent" end>偵測分析</NavLink>
        </nav>
        {(state.chat.loading || state.agent.loading) && <p className="muted small" role="status">
          切換分頁會停止接收目前回覆，並保留草稿與已收到的內容；後端可能仍在處理。
        </p>}
        <Outlet />
      </div>
    </AssistantStateContext.Provider>
  );
}
