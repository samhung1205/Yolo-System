import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { normalizeApiError } from "../services/api";
import agentService from "../services/agentService";
import authService from "../services/authService";
import modelService, { pickDefaultSelection } from "../services/modelService";
import ModelPicker from "../components/ModelPicker";
import SelectField from "../components/SelectField";
import { useAssistantState } from "../state/assistantState";
import SavedResultPicker from "../components/SavedResultPicker";
import AnalysisEvidence from "../components/AnalysisEvidence";
import AssistantTranscript, { AssistantEmpty, AssistantIcon, AssistantMarkdown, useAssistantScroll } from "../components/AssistantTranscript";
import useAssistantPane from "../hooks/useAssistantPane";

const BUILTIN_MODES = [
  { key: "auto", label: "自動選擇" },
  { key: "general_chat", label: "一般聊天" },
  { key: "explain_detection", label: "解釋偵測結果" },
  { key: "history_analysis", label: "歷史趨勢" },
  { key: "report", label: "產生報告" },
  { key: "batch_analysis", label: "批次分析" },
  { key: "admin_help", label: "管理員協助" },
];

// Tool names sent by the backend tool-calling engine (AGENT_ENGINE=tool_calling).
const TOOL_LABELS = {
  get_detection_detail: "讀取偵測結果",
  compare_detections: "比較兩筆偵測",
  summarize_detection_history: "統計偵測歷史",
  list_recent_detections: "查詢近期偵測",
  summarize_model_performance: "統計模型表現",
  generate_detection_report: "產生偵測報告",
  summarize_batch: "統計批次結果",
  list_batch_images_by_class: "查詢含特定類別的影像",
  admin_list_users: "查詢使用者清單",
  admin_detection_overview: "統計全站偵測",
};

function applyToolEvent(liveTools = [], event) {
  if (event.status === "running") {
    return [...liveTools, { tool: event.tool, status: "running" }];
  }
  const index = liveTools.findIndex((item) => item.tool === event.tool && item.status === "running");
  if (index === -1) return [...liveTools, { tool: event.tool, status: "done", ok: event.ok }];
  const updated = [...liveTools];
  updated[index] = { ...updated[index], status: "done", ok: event.ok };
  return updated;
}

function getDefaultMessage(mode, detectionId, batchId) {
  if (detectionId) {
    if (mode === "explain_detection") {
      return `請解釋這筆偵測結果（偵測 #${detectionId}）`;
    }
    if (mode === "report") {
      return `請幫我產生這筆偵測的 Markdown 報告（偵測 #${detectionId}）`;
    }
  }
  if (mode === "batch_analysis" && batchId) {
    return `請摘要這批影像（批次 #${batchId}）的偵測結果，指出值得人工複查的影像與類別。`;
  }
  if (mode === "history_analysis") {
    return "請分析我的偵測歷史紀錄，摘要各狀態數量、常見類別與平均推論時間，並指出值得注意的趨勢。";
  }
  if (mode === "admin_help") {
    return "請彙整目前系統的使用者數量與最近的偵測情況，並指出任何值得關注的指標。";
  }
  return "";
}

export default function AgentPage() {
  const [searchParams] = useSearchParams();
  const user = authService.getCurrentUser();

  const initialMode = searchParams.get("mode") || "auto";
  const initialDetectionId = searchParams.get("detection_id") || "";
  const initialBatchId = searchParams.get("batch_id") || "";

  const [artifactReady, setArtifactReady] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [contextKind, setContextKind] = useAssistantState("agent", "contextKind", initialBatchId ? "batch" : "detection");
  const { wide, paneOpen, setPaneOpen } = useAssistantPane("agent", "settingsOpen");
  const [modes, setModes] = useState(BUILTIN_MODES);
  const [mode, setMode] = useAssistantState("agent", "mode", initialMode);
  const [detectionId, setDetectionId] = useAssistantState("agent", "detectionId", initialDetectionId);
  const [batchId, setBatchId] = useAssistantState("agent", "batchId", initialBatchId);
  const [message, setMessage] = useAssistantState("agent", "message", () =>
    getDefaultMessage(initialMode, initialDetectionId, initialBatchId)
  );
  const [messages, setMessages] = useAssistantState("agent", "messages", []);
  const [conversationId, setConversationId] = useAssistantState("agent", "conversationId", null);
  const [loading, setLoading] = useAssistantState("agent", "loading", false);
  const [streaming, setStreaming] = useAssistantState("agent", "streaming", true);
  const [error, setError] = useAssistantState("agent", "error", "");
  const [reportDownloading, setReportDownloading] = useState("");
  const scroll = useAssistantScroll(messages, null, wide || !paneOpen);
  const settingsHeadingRef = useRef(null);
  const settingsToggleRef = useRef(null);
  const analysisHeadingRef = useRef(null);
  const abortRef = useRef(null);
  // True while an IME (e.g. Chinese/Japanese/Korean input method) composition
  // is in progress, so the confirm-selection Enter key doesn't submit the form.
  const isComposingRef = useRef(false);
  const messageInputRef = useRef(null);
  // Tracks the last message we auto-filled, so we can safely replace it when
  // the mode / detection id / batch id changes without clobbering user-typed text.
  const [lastDefaultMessage, setLastDefaultMessage] = useAssistantState("agent", "lastDefaultMessage", () =>
    getDefaultMessage(initialMode, initialDetectionId, initialBatchId)
  );
  const autoFilledRef = useRef(lastDefaultMessage);

  function applyDefaultMessage(nextMode, nextDetectionId, nextBatchId, currentMessage) {
    const wasAutoFilled =
      !currentMessage || currentMessage === autoFilledRef.current;
    if (wasAutoFilled) {
      const next = getDefaultMessage(nextMode, nextDetectionId, nextBatchId);
      autoFilledRef.current = next;
      setLastDefaultMessage(next);
      setMessage(next);
    }
  }

  // Re-apply query params on in-app navigation (e.g. clicking an agent
  // shortcut while already on /agent). Without this, params are only read
  // once via the useState initializers above.
  useEffect(() => {
    const nextMode = searchParams.get("mode");
    const nextDetectionId = searchParams.get("detection_id");
    const nextBatchId = searchParams.get("batch_id");
    if (!nextMode && !nextDetectionId && !nextBatchId) return;
    const resolvedMode = nextMode || "auto";
    const resolvedDetectionId = nextDetectionId || "";
    const resolvedBatchId = nextBatchId || "";
    setMode(resolvedMode);
    setContextKind(resolvedBatchId ? "batch" : "detection");
    setDetectionId(resolvedDetectionId);
    setBatchId(resolvedBatchId);
    const previousDefault = autoFilledRef.current;
    const nextDefault = getDefaultMessage(resolvedMode, resolvedDetectionId, resolvedBatchId);
    setMessage((current) => !current || current === previousDefault ? nextDefault : current);
    autoFilledRef.current = nextDefault;
    setLastDefaultMessage(nextDefault);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Model selector state
  const [providerGroups, setProviderGroups] = useState([]);
  const [selectedProvider, setSelectedProvider] = useAssistantState("agent", "selectedProvider", null);
  const [selectedModel, setSelectedModel] = useAssistantState("agent", "selectedModel", null);

  useEffect(() => {
    let active = true;
    agentService
      .listAgentModes()
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data) && data.length > 0) {
          setModes(
            data.map((m) => ({
              key: m.key,
              label: `${BUILTIN_MODES.find((mode) => mode.key === m.key)?.label || m.label}${m.admin_only ? "（管理員）" : ""}`,
              admin_only: m.admin_only,
            }))
          );
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    modelService.listModels("agent").then((groups) => {
      if (!active) return;
      if (Array.isArray(groups) && groups.length > 0) {
        setProviderGroups(groups);
        // Start from the backend's default (e.g. local gemma4 for the agent)
        // rather than the first provider in the list, which may be a paid API.
        const initial = pickDefaultSelection(groups);
        setSelectedProvider((current) => current || initial.provider);
        setSelectedModel((current) => current || initial.model);
      }
    }).catch(() => {});
    return () => {
      active = false;
    };
  }, []);


  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
        setError("切換分頁已停止接收回覆；目前對話已保留，後端作業可能仍在進行。");
      }
    };
  }, [setError]);

  const isAdminOnlyMode = mode === "admin_help" && !user?.is_admin;
  // General chat lives in its own tab, and admin-only modes are only listed for
  // admins; a mode arriving through a `mode=` shortcut stays selectable.
  const visibleModes = modes.filter((m) => m.key === mode
    || (m.key !== "general_chat" && (user?.is_admin || !(m.admin_only || m.key === "admin_help"))));
  const contextLabel = batchId ? `批次 #${batchId}` : detectionId ? `偵測 #${detectionId}` : "";
  const detectionModes = ["explain_detection", "report"];
  const requiresDetectionId = detectionModes.includes(mode);
  const requiresBatchId = mode === "batch_analysis";
  // "Auto Select" without a Detection ID silently falls back to General Chat
  // server-side, so questions about a specific image get no detection data.
  const autoModeMissingDetectionId = mode === "auto" && !detectionId && !batchId;

  const needsArtifact = requiresDetectionId || requiresBatchId || (mode === "auto" && Boolean(detectionId || batchId));
  const missingContext = needsArtifact && (!artifactReady || (requiresDetectionId && !detectionId) || (requiresBatchId && !batchId));
  const canChooseArtifact = needsArtifact || mode === "auto";
  const artifactName = selectedArtifact
    ? selectedArtifact.source_filename || selectedArtifact.name || contextLabel
    : contextLabel ? "資料尚未確認" : "尚未選擇資料";
  const activeModeLabel = visibleModes.find((item) => item.key === mode)?.label || "偵測分析";

  function openSettings() {
    setPaneOpen(true);
    requestAnimationFrame(() => settingsHeadingRef.current?.focus({ preventScroll: true }));
  }

  function handleStop() {
    abortRef.current?.abort();
    setError("已停止接收回覆；後端作業可能仍在進行。");
    // The stop button unmounts once loading ends; keep focus in the composer.
    messageInputRef.current?.focus();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || isAdminOnlyMode || loading) return;
    if (missingContext) {
      openSettings();
      setError("請先選擇一筆已完成的分析資料。");
      return;
    }

    scroll.jumpToLatest();
    setLoading(true);
    setError("");
    setMessage("");

    const userMsg = { role: "user", content: trimmed };
    const placeholderMsg = {
      role: "assistant",
      content: "",
      mode,
      tool_calls: [],
      references: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, placeholderMsg]);

    if (streaming) {
      await handleStreamSubmit(trimmed);
    } else {
      await handleBatchSubmit(trimmed);
    }
  }

  async function handleStreamSubmit(trimmed) {
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const event of agentService.streamAgentMessage(
        trimmed,
        {
          conversationId,
          mode,
          detectionId: detectionId ? Number(detectionId) : undefined,
          batchId: batchId ? Number(batchId) : undefined,
          provider: selectedProvider || undefined,
          model: selectedModel || undefined,
        },
        controller.signal
      )) {
        if (event.type === "start") {
          if (event.conversation_id) setConversationId(event.conversation_id);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                mode: event.mode || mode,
                tool_calls: event.tool_calls || [],
                references: event.references || [],
              };
            }
            return updated;
          });
        } else if (event.type === "tool") {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.isStreaming) {
              updated[updated.length - 1] = { ...last, live_tools: applyToolEvent(last.live_tools, event) };
            }
            return updated;
          });
        } else if (event.type === "chunk") {
          const delta = event.delta || "";
          if (delta) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last?.isStreaming) {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + delta,
                };
              }
              return updated;
            });
          }
        } else if (event.type === "done") {
          if (event.conversation_id) setConversationId(event.conversation_id);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                content: event.answer || last.content,
                mode: event.mode || last.mode,
                tool_calls: event.tool_calls || last.tool_calls || [],
                references: event.references || last.references || [],
                isStreaming: false,
              };
            }
            return updated;
          });
        } else if (event.type === "error") {
          setError(event.message || "Agent streaming 失敗");
          setMessages((prev) => {
            const updated = [...prev];
            if (updated[updated.length - 1]?.isStreaming) {
              updated.pop();
            }
            updated.pop(); // remove user msg
            return updated;
          });
          setMessage(trimmed);
        }
      }
    } catch (err) {
      if (err?.name === "AbortError") return;
      setError(err.message || "回覆串流中斷，請重試。");
      setMessages((prev) => {
        const updated = [...prev];
        if (updated[updated.length - 1]?.isStreaming) updated.pop();
        updated.pop();
        return updated;
      });
      setMessage(trimmed);
    } finally {
      // Ensure streaming flag is cleared if never got a "done" event
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.isStreaming) {
          updated[updated.length - 1] = { ...last, isStreaming: false, interrupted: controller.signal.aborted, content: last.content || (controller.signal.aborted ? "已停止接收回覆。" : "未收到完整回覆，請重試。") };
        }
        return updated;
      });
      abortRef.current = null;
      setLoading(false);
    }
  }

  async function handleBatchSubmit(trimmed) {
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await agentService.sendAgentMessage(trimmed, {
        conversationId,
        mode,
        detectionId: detectionId ? Number(detectionId) : undefined,
        batchId: batchId ? Number(batchId) : undefined,
        provider: selectedProvider || undefined,
        model: selectedModel || undefined,
        signal: controller.signal,
      });

      if (response.success === false) {
        throw new Error(
          response.answer || response.errors?.[0] || "分析助理無法完成這次請求"
        );
      }

      setConversationId(response.conversation_id);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.isStreaming) {
          updated[updated.length - 1] = {
            ...last,
            content: response.answer,
            mode: response.mode,
            tool_calls: response.tool_calls || [],
            references: response.references || [],
            isStreaming: false,
          };
        }
        return updated;
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(normalizeApiError(err, "分析請求失敗"));
      setMessages((prev) => {
        const updated = [...prev];
        if (updated[updated.length - 1]?.isStreaming) updated.pop();
        updated.pop();
        return updated;
      });
      setMessage(trimmed);
    } finally {
      abortRef.current = null;
      setMessages((previous) => previous.map((item) => item.isStreaming ? { ...item, isStreaming: false, interrupted: controller.signal.aborted, content: item.content || "已停止接收回覆。" } : item));
      setLoading(false);
    }
  }

  function handleNewConversation() {
    abortRef.current?.abort();
    if (!wide) setPaneOpen(false);
    scroll.jumpToLatest();
    setMessages([]);
    setConversationId(null);
    setMessage("");
    setError("");
    requestAnimationFrame(() => analysisHeadingRef.current?.focus({ preventScroll: true }));
  }

  function handleModeChange(nextMode) {
    setMode(nextMode);
    if (nextMode === "batch_analysis") { setContextKind("batch"); setDetectionId(""); }
    if (["explain_detection", "report"].includes(nextMode)) { setContextKind("detection"); setBatchId(""); }
    if (["general_chat", "history_analysis", "admin_help"].includes(nextMode)) { setDetectionId(""); setBatchId(""); }
    applyDefaultMessage(nextMode, detectionId, batchId, message);
  }

  function handleDetectionIdChange(value) {
    setDetectionId(value);
    setBatchId("");
    applyDefaultMessage(mode, value, "", message);
  }

  function handleBatchIdChange(value) {
    setBatchId(value);
    setDetectionId("");
    applyDefaultMessage(mode, "", value, message);
  }

  async function handleReportDownload(format) {
    if (!detectionId) return;
    setReportDownloading(format);
    setError("");
    try {
      await agentService.downloadDetectionReport(Number(detectionId), format);
    } catch (err) {
      setError(normalizeApiError(err, "報告下載失敗"));
    } finally {
      setReportDownloading("");
    }
  }

  return (
    <div className="assistant-page agent-page" onKeyDown={(event) => {
      if (event.key === "Escape" && !event.defaultPrevented && !wide && paneOpen) {
        setPaneOpen(false);
        settingsToggleRef.current?.focus();
      }
    }}>
      <div className="assistant-toolbar">
        <button type="button" className="assistant-tool-button" ref={settingsToggleRef}
          aria-expanded={paneOpen} aria-controls="analysis-settings"
          onClick={() => paneOpen ? setPaneOpen(false) : openSettings()}>
          <AssistantIcon name={!wide && paneOpen ? "back" : "settings"} />
          {paneOpen ? wide ? "收合設定" : "返回分析" : "分析設定"}
        </button>
        <h2 ref={analysisHeadingRef} tabIndex={-1}>{activeModeLabel}</h2>
        <button type="button" className="assistant-tool-button assistant-new" aria-label="新對話"
          onClick={handleNewConversation} disabled={loading}>
          <AssistantIcon name="new" /><span>新對話</span>
        </button>
      </div>

      {error && <div className="alert alert-error assistant-notice" role="alert">{error}</div>}

      {isAdminOnlyMode ? (
        <div className="alert alert-warning assistant-notice" role="status">
          「管理員協助」模式僅管理員可用，請改選其他分析模式。
        </div>
      ) : null}

      <p className="sr-only" role="status">{loading ? "分析助理正在回覆" : messages.length ? "分析回覆已更新" : "輸入訊息開始分析"}</p>
      <div className="assistant-layout" data-pane-open={paneOpen || undefined}>

        <aside id="analysis-settings" className="assistant-side assistant-settings" aria-labelledby="analysis-settings-title" hidden={!paneOpen}>
          <h3 id="analysis-settings-title" ref={settingsHeadingRef} tabIndex={-1}>分析設定</h3>

          <div className="field">
            <label htmlFor="agent-mode"><span>分析模式</span></label>
            <SelectField id="agent-mode" label="分析模式" value={mode} onChange={handleModeChange}
              options={visibleModes.map((item) => ({
                value: item.key, label: item.label,
                disabled: (item.admin_only || item.key === "admin_help") && !user?.is_admin,
              }))}
              disabled={loading} describedBy="agent-mode-hint" />
            <span id="agent-mode-hint" className="field-hint">不需要讀取偵測資料的一般問答，請改用「一般對話」分頁。</span>
          </div>

          {mode === "auto" && <div className="field">
            <label htmlFor="agent-context-kind"><span>分析資料類型</span></label>
            <SelectField id="agent-context-kind" label="分析資料類型" value={contextKind}
              options={[{ value: "detection", label: "單筆偵測" }, { value: "batch", label: "影像批次" }]}
              disabled={loading} onChange={(kind) => {
                setContextKind(kind);
                setDetectionId("");
                setBatchId("");
              }} />
          </div>}
          {(requiresDetectionId || requiresBatchId || mode === "auto") && <>
            <SavedResultPicker kind={requiresBatchId ? "batch" : requiresDetectionId ? "detection" : contextKind}
              value={requiresBatchId || (mode === "auto" && contextKind === "batch") ? batchId : detectionId}
              onChange={requiresBatchId || (mode === "auto" && contextKind === "batch") ? handleBatchIdChange : handleDetectionIdChange}
              onAvailabilityChange={setArtifactReady} onSelectionChange={setSelectedArtifact} disabled={loading} />
            {missingContext && <p className="field-hint field-hint-warning" role="status">請先選擇已完成的結果，再送出分析。</p>}
            {autoModeMissingDetectionId && <p className="muted small">未選資料時，自動模式只做一般問答；要分析影像請先選擇結果。</p>}
          </>}

          {mode === "report" && detectionId ? (
            <div className="report-download-actions">
              <span className="detail-label">確定性報告（不經 AI 改寫）</span>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => handleReportDownload("markdown")}
                disabled={Boolean(reportDownloading)}
              >
                {reportDownloading === "markdown" ? "準備中…" : "下載 Markdown"}
              </button>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => handleReportDownload("pdf")}
                disabled={Boolean(reportDownloading)}
              >
                {reportDownloading === "pdf" ? "產生中…" : "下載 PDF"}
              </button>
            </div>
          ) : null}

          <label className="field-checkbox assistant-streaming">
            <input type="checkbox" checked={streaming} onChange={(event) => setStreaming(event.target.checked)} disabled={loading} />
            <span>逐字顯示回覆</span>
          </label>

          {conversationId ? (
            <div className="agent-meta">
              <span className="detail-label">對話編號</span>
              <code className="small">{conversationId}</code>
            </div>
          ) : null}
        </aside>

        <div className="assistant-main" hidden={!wide && paneOpen}>
          {needsArtifact && <div className="analysis-current-context" role="status">
            <span>分析依據{contextLabel && ` · ${contextLabel}`}</span>
            <strong title={artifactName}>{artifactName}</strong>
            {contextLabel && !artifactReady && selectedArtifact && <span>尚未完成</span>}
          </div>}
          <AssistantTranscript label="分析對話" busy={loading} scroll={scroll} empty={!messages.length}>
            {messages.length ? (
              messages.map((msg, index) =>
                msg.role === "user" ? (
                  <div key={index} className="assistant-message assistant-message-user">
                    <span className="chat-role">你</span>
                    <p>{msg.content}</p>
                  </div>
                ) : (
                  <div key={index} className="assistant-message assistant-message-reply">
                    <span className="chat-role">
                      分析助理
                      {msg.mode ? (
                        <span className="agent-mode-badge"> · {BUILTIN_MODES.find((item) => item.key === msg.mode)?.label || msg.mode}</span>
                      ) : null}
                      {msg.isStreaming ? (
                        <span className="agent-streaming-indicator"> ▍</span>
                      ) : null}
                    </span>
                    {msg.isStreaming && !msg.content && !msg.live_tools?.length ? (
                      <p className="muted small agent-waiting">
                        {contextLabel ? `正在讀取${contextLabel} 並整理回覆…` : "正在整理回覆…"}
                      </p>
                    ) : null}
                    {msg.isStreaming && msg.live_tools?.length ? (
                      <ul className="agent-tool-progress" aria-live="polite">
                        {msg.live_tools.map((item, toolIndex) => (
                          <li key={toolIndex} className={`agent-tool-progress-item is-${item.status}${item.ok === false ? " is-failed" : ""}`}>
                            {TOOL_LABELS[item.tool] || item.tool}
                            {item.status === "running" ? "…" : item.ok === false ? "（失敗）" : "（完成）"}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <AssistantMarkdown>{msg.content || (msg.isStreaming ? "" : "（沒有回覆內容）")}</AssistantMarkdown>

                    {msg.interrupted && <p className="muted small">已停止接收，此回覆可能不完整。</p>}
                    {!msg.isStreaming && <AnalysisEvidence references={msg.references} tools={msg.tool_calls} />}

                  </div>
                )
              )
            ) : (
              <AssistantEmpty icon="analysis" title={artifactReady ? "開始分析這筆結果" : "開始偵測分析"}>
                <p>{artifactReady ? "可以詢問偵測到的物件、數量，或哪些結果需要人工確認。"
                  : canChooseArtifact ? "選擇一筆已保存的偵測或批次，再輸入問題。"
                  : "輸入想查的偵測趨勢或紀錄摘要。"}</p>
                {canChooseArtifact && !artifactReady && (
                  <button type="button" className="button button-secondary" onClick={openSettings}>選擇分析資料</button>
                )}
              </AssistantEmpty>
            )}
          </AssistantTranscript>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
              <textarea
                ref={messageInputRef}
                aria-label="傳送給分析助理的訊息"
                rows={2}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="輸入要問分析助理的問題"
                readOnly={loading}
                disabled={isAdminOnlyMode}
                onCompositionStart={() => {
                  isComposingRef.current = true;
                }}
                onCompositionEnd={() => {
                  isComposingRef.current = false;
                }}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" || e.shiftKey) return;
                  // isComposing / keyCode 229 guards the Enter keystroke used
                  // to confirm an IME candidate (Chinese/Japanese/Korean input)
                  // so it doesn't also submit the message.
                  if (isComposingRef.current || e.nativeEvent?.isComposing || e.keyCode === 229) {
                    return;
                  }
                  e.preventDefault();
                  if (!loading && message.trim() && !isAdminOnlyMode) handleSubmit(e);
                }}
              />
              <div className="chat-input-bar">
                {providerGroups.length > 0 && (
                  <ModelPicker
                    providerGroups={providerGroups}
                    selectedProvider={selectedProvider}
                    selectedModel={selectedModel}
                    onSelect={(provider, model) => {
                      setSelectedProvider(provider);
                      setSelectedModel(model);
                    }}
                    disabled={loading}
                  />
                )}
                <div className="chat-input-spacer" />
                {loading && <button type="button" className="button-ghost" onClick={handleStop}>停止接收</button>}
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={isAdminOnlyMode}
                  aria-disabled={loading || !message.trim() || missingContext || undefined}
                  aria-label="送出訊息"
                >
                  {loading ? (
                    <svg className="loading-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" strokeDasharray="31.4" strokeDashoffset="10" strokeLinecap="round">

                      </circle>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
