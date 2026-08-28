import { useEffect, useMemo, useRef, useState } from "react";

import chatService from "../services/chatService";
import modelService from "../services/modelService";
import ModelPicker from "../components/ModelPicker";
import { normalizeApiError } from "../services/api";

const CONVERSATION_LIMIT = 100;

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [initLoading, setInitLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingConversationId, setDeletingConversationId] = useState(null);

  // Mirrors activeConversationId so async handlers can check the *current*
  // selection after an await (avoids races with user navigation).
  const activeIdRef = useRef(null);
  // Set once the user manually opens/creates a conversation; blocks the
  // initial auto-open from overriding their choice.
  const userNavigatedRef = useRef(false);
  // Sequence number so out-of-order getConversation responses are dropped.
  const openSeqRef = useRef(0);
  // True while an IME (e.g. Chinese/Japanese/Korean input method) composition
  // is in progress, so the confirm-selection Enter key doesn't submit the form.
  const isComposingRef = useRef(false);
  // Scrollable thread container — the CSS caps its height, so we auto-scroll
  // to the latest message instead of letting the page grow unbounded.
  const threadRef = useRef(null);

  // Model selector state
  const [providerGroups, setProviderGroups] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.conversation_id === activeConversationId) || null,
    [activeConversationId, conversations]
  );

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

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  function handleProviderChange(provider) {
    setSelectedProvider(provider);
    const group = providerGroups.find((g) => g.provider === provider);
    setSelectedModel(group?.models[0] || null);
  }

  useEffect(() => {
    let mounted = true;

    async function loadConversations() {
      try {
        const rows = await chatService.listConversations(CONVERSATION_LIMIT);
        if (!mounted) {
          return;
        }
        setConversations(rows);
        // Don't auto-open if the user already clicked "New" or another
        // conversation while this request was in flight.
        if (rows.length > 0 && !userNavigatedRef.current) {
          await handleOpenConversation(rows[0].conversation_id, mounted, { auto: true });
        }
      } catch (err) {
        if (mounted) {
          setError(normalizeApiError(err, "無法載入聊天紀錄"));
        }
      } finally {
        if (mounted) setInitLoading(false);
      }
    }

    loadConversations();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleOpenConversation(conversationId, mounted = true, { auto = false } = {}) {
    if (!auto) {
      userNavigatedRef.current = true;
    }
    setConfirmDeleteId(null);
    const seq = ++openSeqRef.current;
    try {
      const detail = await chatService.getConversation(conversationId);
      if (!mounted || seq !== openSeqRef.current) {
        return;
      }
      if (auto && userNavigatedRef.current) {
        return;
      }
      activeIdRef.current = detail.conversation_id;
      setActiveConversationId(detail.conversation_id);
      setMessages(detail.messages);
    } catch (err) {
      if (mounted) {
        setError(normalizeApiError(err, "無法載入對話內容"));
      }
    }
  }

  async function refreshConversations() {
    const rows = await chatService.listConversations(CONVERSATION_LIMIT);
    setConversations(rows);
  }

  async function handleDeleteConversation(conversationId) {
    if (!conversationId || deletingConversationId) return;

    setDeletingConversationId(conversationId);
    setError("");
    try {
      await chatService.deleteConversation(conversationId);
      openSeqRef.current += 1;
      setConversations((prev) =>
        prev.filter((item) => item.conversation_id !== conversationId)
      );
      if (activeIdRef.current === conversationId) {
        activeIdRef.current = null;
        setActiveConversationId(null);
        setMessages([]);
        setQuestion("");
      }
      setConfirmDeleteId(null);
    } catch (err) {
      setError(normalizeApiError(err, "刪除對話失敗"));
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }

    const sentInConversationId = activeConversationId;
    setLoading(true);
    setError("");
    try {
      const response = await chatService.sendMessage(
        question.trim(),
        sentInConversationId,
        selectedProvider,
        selectedModel,
      );
      // Only apply the response if the user hasn't switched conversation
      // while the request was in flight.
      if (activeIdRef.current === sentInConversationId) {
        activeIdRef.current = response.conversation_id;
        setActiveConversationId(response.conversation_id);
        setMessages((prev) => [...prev, response]);
        setQuestion("");
      }
      await refreshConversations();
    } catch (err) {
      setError(normalizeApiError(err, "聊天請求失敗"));
    } finally {
      setLoading(false);
    }
  }

  function handleNewConversation() {
    userNavigatedRef.current = true;
    openSeqRef.current += 1; // invalidate in-flight opens
    activeIdRef.current = null;
    setActiveConversationId(null);
    setMessages([]);
    setQuestion("");
    setConfirmDeleteId(null);
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">CHAT</div>
          <h1>AI Chat</h1>
          <p className="muted">Chat with the AI for general assistance. Use Detection Analyst for detection-specific analysis.</p>
        </div>
      </section>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      <section className="chat-layout">
        <aside className="panel chat-sidebar">
          <div className="section-title chat-sidebar-header">
            <div>
              <h2>Conversations</h2>
              <span className="muted small">
                {conversations.length} conversations · latest {CONVERSATION_LIMIT}
              </span>
            </div>
            <button type="button" className="button button-secondary" onClick={handleNewConversation}>
              New
            </button>
          </div>

          <div className="chat-conversation-scroll">
            <div className="list-stack chat-conversation-list">
              {initLoading ? (
                <p className="muted small">載入聊天紀錄...</p>
              ) : (
                <>
                {conversations.map((item) => (
                  <div
                    key={item.conversation_id}
                    className={
                      activeConversationId === item.conversation_id
                        ? "chat-conversation-item chat-conversation-item-active"
                        : "chat-conversation-item"
                    }
                  >
                    <button
                      type="button"
                      className="chat-conversation-open"
                      onClick={() => handleOpenConversation(item.conversation_id)}
                      aria-current={activeConversationId === item.conversation_id ? "true" : undefined}
                    >
                      <span className="chat-conversation-title" title={item.title}>{item.title}</span>
                      <span className="chat-conversation-meta">
                        {item.provider} · {item.turn_count} turns
                      </span>
                    </button>

                    {confirmDeleteId === item.conversation_id ? (
                      <div className="chat-delete-confirm" role="group" aria-label={`確認刪除 ${item.title}`}>
                        <span>確定刪除？</span>
                        <button
                          type="button"
                          className="chat-delete-confirm-button"
                          disabled={deletingConversationId === item.conversation_id || loading}
                          onClick={() => handleDeleteConversation(item.conversation_id)}
                        >
                          {deletingConversationId === item.conversation_id ? "刪除中..." : "刪除"}
                        </button>
                        <button
                          type="button"
                          className="chat-delete-cancel-button"
                          disabled={deletingConversationId === item.conversation_id}
                          onClick={() => setConfirmDeleteId(null)}
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="chat-conversation-delete"
                        disabled={Boolean(deletingConversationId) || loading}
                        onClick={() => setConfirmDeleteId(item.conversation_id)}
                        aria-label={`刪除對話 ${item.title}`}
                        title="刪除對話"
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                          <path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
                {!conversations.length ? <p className="muted">尚無聊天紀錄。</p> : null}
                </>
              )}
            </div>
          </div>
        </aside>

        <div className="panel chat-main">
          <div className="chat-header">
            <h2>{activeConversation?.title || "New Conversation"}</h2>
            <span className="muted">
              {activeConversation ? `${activeConversation.turn_count} turns` : "尚未建立對話"}
            </span>
          </div>

          <div ref={threadRef} className="chat-thread">
            {messages.length ? (
              messages.map((item) => (
                <div key={item.id} className="chat-turn">
                  <div className="chat-bubble chat-bubble-user">
                    <span className="chat-role">You</span>
                    <p>{item.question}</p>
                  </div>
                  <div className="chat-bubble chat-bubble-assistant">
                    <span className="chat-role">
                      {item.provider} · {item.model_name}
                    </span>
                    <p>{item.answer}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="chat-empty">
                <p className="muted">輸入第一則訊息開始新的對話。</p>
              </div>
            )}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="請輸入想問 AI 的問題"
                disabled={loading}
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
                  if (!loading && question.trim()) handleSubmit(e);
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
                  disabled={loading || !question.trim()}
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
      </section>
    </div>
  );
}
