import { useReducer } from "react";
import { NavLink, Outlet } from "react-router";
import { AssistantStateContext, updateWorkspace } from "../state/assistantState";
import "./AssistantWorkspace.css";

export default function AssistantWorkspace() {
  const [state, dispatch] = useReducer(updateWorkspace, { chat: {}, agent: {} });

  return (
    <AssistantStateContext.Provider value={{ state, dispatch }}>
      <div className="assistant-workspace">
        <header className="assistant-header">
          <h1>AI 助理</h1>
          <nav className="assistant-tabs" aria-label="AI 助理功能">
            <NavLink to="/chat" end>一般對話</NavLink>
            <NavLink to="/agent" end>偵測分析</NavLink>
          </nav>
          {(state.chat.loading || state.agent.loading) && <p className="muted small assistant-switch-note" role="status">
            切換分頁會停止接收回覆，並保留草稿和已收到的內容。
          </p>}
        </header>
        <Outlet />
      </div>
    </AssistantStateContext.Provider>
  );
}
