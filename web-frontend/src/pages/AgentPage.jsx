import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { normalizeApiError } from "../services/api";
import agentService from "../services/agentService";
import authService from "../services/authService";
import modelService from "../services/modelService";
import ModelPicker from "../components/ModelPicker";

const BUILTIN_MODES = [
  { key: "auto", label: "Auto Select" },
  { key: "general_chat", label: "General Chat" },
  { key: "explain_detection", label: "Explain Detection" },
  { key: "history_analysis", label: "History Analysis" },
  { key: "report", label: "Generate Report" },
  { key: "admin_help", label: "Admin Assistance" },
];

function getDefaultMessage(mode, detectionId) {
  if (detectionId) {
    if (mode === "explain_detection") {
      return `請解釋這筆 detection 結果 (ID: ${detectionId})`;
    }
    if (mode === "report") {
      return `請幫我產生這筆 detection 的 markdown 報告 (ID: ${detectionId})`;
    }
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

  const [modes, setModes] = useState(BUILTIN_MODES);
  const [mode, setMode] = useState(initialMode);
  const [detectionId, setDetectionId] = useState(initialDetectionId);
  const [message, setMessage] = useState(
    getDefaultMessage(initialMode, initialDetectionId)
  );
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(true);
  const [error, setError] = useState("");
  const threadRef = useRef(null);
  const abortRef = useRef(null);
  // Tracks the last message we auto-filled, so we can safely replace it when
  // the mode / detection id changes without clobbering user-typed text.
  const autoFilledRef = useRef(getDefaultMessage(initialMode, initialDetectionId));

  function applyDefaultMessage(nextMode, nextDetectionId, currentMessage) {
    const wasAutoFilled =
      !currentMessage || currentMessage === autoFilledRef.current;
    if (wasAutoFilled) {
      const next = getDefaultMessage(nextMode, nextDetectionId);
      autoFilledRef.current = next;
      setMessage(next);
    }
  }

  // Re-apply query params on in-app navigation (e.g. clicking an agent
  // shortcut while already on /agent). Without this, params are only read
  // once via the useState initializers above.
  useEffect(() => {
    const nextMode = searchParams.get("mode");
    const nextDetectionId = searchParams.get("detection_id");
    if (!nextMode && !nextDetectionId) return;
    const resolvedMode = nextMode || "auto";
    const resolvedDetectionId = nextDetectionId || "";
    setMode(resolvedMode);
    setDetectionId(resolvedDetectionId);
    setMessage((current) => {
      const wasAutoFilled = !current || current === autoFilledRef.current;
      if (wasAutoFilled) {
        const next = getDefaultMessage(resolvedMode, resolvedDetectionId);
        autoFilledRef.current = next;
        return next;
      }
      return current;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Model selector state
  const [providerGroups, setProviderGroups] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  useEffect(() => {
    agentService
      .listAgentModes()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setModes(
            data.map((m) => ({
              key: m.key,
              label: `${m.label}${m.admin_only ? " (Admin)" : ""}`,
              admin_only: m.admin_only,
            }))
          );
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    modelService.listModels().then((groups) => {
      if (Array.isArray(groups) && groups.length > 0) {
        setProviderGroups(groups);
        // Prefer the first provider that is actually usable (API key set /
        // local daemon); unavailable ones are only display placeholders.
        const usable = groups.find((g) => g.available !== false) || groups[0];
        setSelectedProvider(usable.provider);
        setSelectedModel(usable.models[0] || null);
      }
    }).catch(() => {});
  }, []);

  const currentModels = providerGroups.find((g) => g.provider === selectedProvider)?.models || [];

  function handleAgentProviderChange(provider) {
    setSelectedProvider(provider);
    const group = providerGroups.find((g) => g.provider === provider);
    setSelectedModel(group?.models[0] || null);
  }

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const isAdminOnlyMode = mode === "admin_help" && !user?.is_admin;

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || isAdminOnlyMode) return;

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
          updated[updated.length - 1] = { ...last, isStreaming: false };
        }
        return updated;
      });
      abortRef.current = null;
      setLoading(false);
    }
  }

  async function handleBatchSubmit(trimmed) {
    try {
      const response = await agentService.sendAgentMessage(trimmed, {
        conversationId,
        mode,
        detectionId: detectionId ? Number(detectionId) : undefined,
        provider: selectedProvider || undefined,
        model: selectedModel || undefined,
      });

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
      setError(normalizeApiError(err, "Agent 請求失敗"));
      setMessages((prev) => {
        const updated = [...prev];
        if (updated[updated.length - 1]?.isStreaming) updated.pop();
        updated.pop();
        return updated;
      });
      setMessage(trimmed);
    } finally {
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
    applyDefaultMessage(nextMode, detectionId, message);
  }

  function handleDetectionIdChange(value) {
    setDetectionId(value);
    applyDefaultMessage(mode, value, message);
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">AI DETECTION ANALYST</div>
          <h1>Detection Analyst</h1>
          <p className="muted">
            Explain detection results, analyze historical trends, and generate detection reports.
          </p>
        </div>
        <div className="page-header-actions">
          <label className="field-checkbox">
            <input
              type="checkbox"
              checked={streaming}
              onChange={(e) => setStreaming(e.target.checked)}
              disabled={loading}
            />
            <span>Streaming</span>
          </label>
          <button
            type="button"
            className="button button-secondary"
            onClick={handleNewConversation}
            disabled={loading}
          >
            New Conversation
          </button>
        </div>
      </section>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      {isAdminOnlyMode ? (
        <div className="alert alert-warning" role="status">
          <strong>admin_help</strong> 模式僅管理員可用。
        </div>
      ) : null}

      <div className="agent-layout">
        <aside className="panel agent-controls">
          <h2>Analysis Settings</h2>

          <label className="field">
            <span>Analysis Mode</span>
            <select
              value={mode}
              onChange={(e) => handleModeChange(e.target.value)}
              disabled={loading}
            >
              {modes.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Detection ID (Optional)</span>
            <input
              type="number"
              min="1"
              placeholder="例：123"
              value={detectionId}
              onChange={(e) => handleDetectionIdChange(e.target.value)}
              disabled={loading}
            />
          </label>

          {conversationId ? (
            <div className="agent-meta">
              <span className="detail-label">Conversation</span>
              <code className="small">{conversationId}</code>
            </div>
          ) : null}
        </aside>

        <div className="panel agent-main">
          <div ref={threadRef} className="agent-thread">
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
                        <span className="agent-mode-badge"> · {msg.mode}</span>
                      ) : null}
                      {msg.isStreaming ? (
                        <span className="agent-streaming-indicator"> ▍</span>
                      ) : null}
                    </span>
                    <p>{msg.content || (msg.isStreaming ? "" : "(no answer)")}</p>

                    {!msg.isStreaming && msg.tool_calls?.length > 0 ? (
                      <div className="agent-tool-calls">
                        <div className="detail-label">Tool Calls</div>
                        {msg.tool_calls.map((tc, ti) => (
                          <pre key={ti} className="agent-tool-call-item">
                            {JSON.stringify(tc, null, 2)}
                          </pre>
                        ))}
                      </div>
                    ) : null}

                    {!msg.isStreaming && msg.references?.length > 0 ? (
                      <div className="agent-reference-list">
                        <div className="detail-label">References</div>
                        {msg.references.map((ref, ri) => (
                          <div key={ri} className="agent-reference-item">
                            {JSON.stringify(ref)}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              )
            ) : (
              <div className="chat-empty">
                <p className="muted">Choose an analysis mode and enter a message to start.</p>
              </div>
            )}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="輸入要問 Agent 的問題"
                disabled={loading || isAdminOnlyMode}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!loading && message.trim() && !isAdminOnlyMode) handleSubmit(e);
                  }
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
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={loading || !message.trim() || isAdminOnlyMode}
                  aria-label="送出訊息"
                >
                  {loading ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" strokeDasharray="31.4" strokeDashoffset="10" strokeLinecap="round">
                        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
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
