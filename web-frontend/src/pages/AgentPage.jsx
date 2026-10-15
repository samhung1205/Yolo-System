import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { normalizeApiError } from "../services/api";
import agentService from "../services/agentService";
import authService from "../services/authService";
import modelService from "../services/modelService";
import ModelPicker from "../components/ModelPicker";
import { useAssistantState } from "../state/assistantState";
import SavedResultPicker from "../components/SavedResultPicker";
import AnalysisEvidence from "../components/AnalysisEvidence";

const BUILTIN_MODES = [
  { key: "auto", label: "自動選擇" },
  { key: "general_chat", label: "一般聊天" },
  { key: "explain_detection", label: "解釋偵測結果" },
  { key: "history_analysis", label: "歷史趨勢" },
  { key: "report", label: "產生報告" },
  { key: "batch_analysis", label: "批次分析" },
  { key: "admin_help", label: "管理員協助" },
];
const MARKDOWN_PLUGINS = [remarkGfm];

function getDefaultMessage(mode, detectionId, batchId) {
  if (detectionId) {
    if (mode === "explain_detection") {
      return `請解釋這筆 detection 結果 (ID: ${detectionId})`;
    }
    if (mode === "report") {
      return `請幫我產生這筆 detection 的 markdown 報告 (ID: ${detectionId})`;
    }
  }
  if (mode === "batch_analysis" && batchId) {
    return `請統計這批影像 (Batch ID: ${batchId}) 中各類別總數，並指出有幾張影像沒偵測到任何物件。`;
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
  const [settingsOpen, setSettingsOpen] = useAssistantState("agent", "settingsOpen", false);
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
  const threadRef = useRef(null);
  const abortRef = useRef(null);
  // True while an IME (e.g. Chinese/Japanese/Korean input method) composition
  // is in progress, so the confirm-selection Enter key doesn't submit the form.
  const isComposingRef = useRef(false);
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
    modelService.listModels().then((groups) => {
      if (!active) return;
      if (Array.isArray(groups) && groups.length > 0) {
        setProviderGroups(groups);
        // Prefer the first provider that is actually usable (API key set /
        // local daemon); unavailable ones are only display placeholders.
        const usable = groups.find((g) => g.available !== false) || groups[0];
        setSelectedProvider((current) => current || usable.provider);
        setSelectedModel((current) => current || usable.models[0] || null);
      }
    }).catch(() => {});
    return () => {
      active = false;
    };
  }, []);


  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

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
  const detectionModes = ["explain_detection", "report"];
  const requiresDetectionId = detectionModes.includes(mode);
  const requiresBatchId = mode === "batch_analysis";
  // "Auto Select" without a Detection ID silently falls back to General Chat
  // server-side, so questions about a specific image get no detection data.
  const autoModeMissingDetectionId = mode === "auto" && !detectionId && !batchId;

  const needsArtifact = requiresDetectionId || requiresBatchId || (mode === "auto" && Boolean(detectionId || batchId));
  const missingContext = needsArtifact && (!artifactReady || (requiresDetectionId && !detectionId) || (requiresBatchId && !batchId));

  function handleStop() {
    abortRef.current?.abort();
    setError("已停止接收回覆；後端作業可能仍在進行。");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || isAdminOnlyMode || loading) return;
    if (missingContext) { setSettingsOpen(true); setError("請先選擇一筆已完成的分析資料。"); return; }

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
      setError(err.message || "Streaming request failed");
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
          response.answer || response.errors?.[0] || "Agent 無法完成這次請求"
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
      setError(normalizeApiError(err, "Agent 請求失敗"));
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
    setMessages([]);
    setConversationId(null);
    setMessage("");
    setError("");
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
    <div className="page-stack agent-page">
      <div className="assistant-actions">
        <div className="page-header-actions">
          <button type="button" className="button button-secondary agent-settings-toggle"
            aria-expanded={settingsOpen} aria-controls="analysis-settings"
            onClick={() => setSettingsOpen((open) => !open)}>{settingsOpen ? "收合分析設定" : "分析設定"}</button>
          <label className="field-checkbox">
            <input
              type="checkbox"
              checked={streaming}
              onChange={(e) => setStreaming(e.target.checked)}
              disabled={loading}
            />
            <span>逐字顯示回覆</span>
          </label>
          <button
            type="button"
            className="button button-secondary"
            onClick={handleNewConversation}
            disabled={loading}
          >
            新對話
          </button>
        </div>
      </div>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      {isAdminOnlyMode ? (
        <div className="alert alert-warning" role="status">
          <strong>admin_help</strong> 模式僅管理員可用。
        </div>
      ) : null}

      {needsArtifact && <div className="analysis-current-context" role="status">
        <span>分析依據</span>
        <strong>{selectedArtifact
          ? selectedArtifact.source_filename || selectedArtifact.name || `批次 #${batchId}`
          : detectionId || batchId ? "正在確認所選資料…" : "尚未選擇資料"}</strong>
        {(detectionId || batchId) && <span>{batchId ? "批次" : "偵測"} #{batchId || detectionId}</span>}
        {(detectionId || batchId) && !artifactReady && <span>資料尚未確認可用，請在分析設定檢查。</span>}
      </div>}

      <p className="sr-only" role="status">{loading ? "分析助理正在回覆" : messages.length ? "分析回覆已更新" : "輸入訊息開始分析"}</p>
      <div className={`agent-layout${settingsOpen ? " settings-open" : ""}`}>

        <aside id="analysis-settings" className="panel agent-controls">
          <h2>分析設定</h2>

          <label className="field">
            <span>分析模式</span>
            <select
              value={mode}
              onChange={(e) => handleModeChange(e.target.value)}
              disabled={loading}
            >
              {modes.map((m) => (
                <option key={m.key} value={m.key} disabled={(m.admin_only || m.key === "admin_help") && !user?.is_admin}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          {mode === "auto" && <label className="field">
            <span>分析資料類型</span>
            <select value={contextKind} disabled={loading} onChange={(event) => {
              setContextKind(event.target.value); setDetectionId(""); setBatchId("");
            }}>
              <option value="detection">單筆偵測</option><option value="batch">影像批次</option>
            </select>
          </label>}
          {(requiresDetectionId || requiresBatchId || mode === "auto") && <>
            <SavedResultPicker kind={requiresBatchId ? "batch" : requiresDetectionId ? "detection" : contextKind}
              value={requiresBatchId || (mode === "auto" && contextKind === "batch") ? batchId : detectionId}
              onChange={requiresBatchId || (mode === "auto" && contextKind === "batch") ? handleBatchIdChange : handleDetectionIdChange}
              onAvailabilityChange={setArtifactReady} onSelectionChange={setSelectedArtifact} disabled={loading} />
            {missingContext && <p className="field-hint field-hint-warning" role="status">請先選擇已完成的結果，再送出分析。</p>}
            {autoModeMissingDetectionId && <p className="muted small">未選資料時，自動模式使用一般聊天；影像分析請先選擇結果。</p>}
          </>}

          {mode === "report" && detectionId ? (
            <div className="report-download-actions">
              <span className="detail-label">Deterministic Report</span>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => handleReportDownload("markdown")}
                disabled={Boolean(reportDownloading)}
              >
                {reportDownloading === "markdown" ? "準備中..." : "下載 Markdown"}
              </button>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => handleReportDownload("pdf")}
                disabled={Boolean(reportDownloading)}
              >
                {reportDownloading === "pdf" ? "產生中..." : "下載 PDF"}
              </button>
            </div>
          ) : null}

          {conversationId ? (
            <div className="agent-meta">
              <span className="detail-label">Conversation</span>
              <code className="small">{conversationId}</code>
            </div>
          ) : null}
        </aside>

        <div className="panel agent-main">
          <div ref={threadRef} className="agent-thread" role="region" aria-label="分析對話" tabIndex={0} aria-busy={loading}>
            {messages.length ? (
              messages.map((msg, index) =>
                msg.role === "user" ? (
                  <div key={index} className="agent-message agent-message-user">
                    <span className="chat-role">You</span>
                    <p>{msg.content}</p>
                  </div>
                ) : (
                  <div key={index} className="agent-message agent-message-assistant">
                    <span className="chat-role">
                      Agent
                      {msg.mode ? (
                        <span className="agent-mode-badge"> · {BUILTIN_MODES.find((item) => item.key === msg.mode)?.label || msg.mode}</span>
                      ) : null}
                      {msg.isStreaming ? (
                        <span className="agent-streaming-indicator"> ▍</span>
                      ) : null}
                    </span>
                    <div className="markdown-report">
                      <ReactMarkdown remarkPlugins={MARKDOWN_PLUGINS}>
                        {msg.content || (msg.isStreaming ? "" : "(no answer)")}
                      </ReactMarkdown>
                    </div>

                    {msg.interrupted && <p className="muted small">已停止接收，此回覆可能不完整。</p>}
                    {!msg.isStreaming && <AnalysisEvidence references={msg.references} tools={msg.tool_calls} />}

                  </div>
                )
              )
            ) : (
              <div className="chat-empty">
                <p className="muted">選擇分析資料，再輸入問題開始對話。</p>
              </div>
            )}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
              <textarea
                aria-label="傳送給分析助理的訊息"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="輸入要問 Agent 的問題"
                disabled={loading || isAdminOnlyMode}
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
                  disabled={loading || !message.trim() || isAdminOnlyMode || missingContext}
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
