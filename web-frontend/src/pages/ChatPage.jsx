import { useEffect, useMemo, useRef, useState } from "react";

import chatService from "../services/chatService";
import modelService, { pickDefaultSelection } from "../services/modelService";
import ModelPicker from "../components/ModelPicker";
import { useAssistantState } from "../state/assistantState";
import { normalizeApiError } from "../services/api";
import ConfirmDialog from "../components/ConfirmDialog";
import AssistantTranscript, { AssistantEmpty, AssistantIcon, AssistantMarkdown, useAssistantScroll } from "../components/AssistantTranscript";
import useAssistantPane from "../hooks/useAssistantPane";

const CONVERSATION_LIMIT = 100;

export default function ChatPage() {
  const { wide, paneOpen, setPaneOpen } = useAssistantPane("chat", "showConversations");
  const [conversations, setConversations] = useAssistantState("chat", "conversations", []);
  const [activeConversationId, setActiveConversationId] = useAssistantState("chat", "activeConversationId", null);
  const [messages, setMessages] = useAssistantState("chat", "messages", []);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [openingConversationId, setOpeningConversationId] = useState(null);
  const [historyQuery, setHistoryQuery] = useAssistantState("chat", "historyQuery", "");
  const [initialized, setInitialized] = useAssistantState("chat", "initialized", false);
  const requestRef = useRef(null);
  const [question, setQuestion] = useAssistantState("chat", "question", "");
  const [loading, setLoading] = useAssistantState("chat", "loading", false);
  const [initLoading, setInitLoading] = useState(true);
  const [error, setError] = useAssistantState("chat", "error", "");
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const sidebarHeadingRef = useRef(null);
  const paneToggleRef = useRef(null);
  const conversationHeadingRef = useRef(null);
  // The deleted row (and its trigger) unmounts; land focus on the list heading.
  const focusListAfterDeleteRef = useRef(false);
  useEffect(() => {
    if (!focusListAfterDeleteRef.current) return;
    focusListAfterDeleteRef.current = false;
    sidebarHeadingRef.current?.focus();
  }, [conversations]);
  const [deletingConversationId, setDeletingConversationId] = useState(null);

  // Mirrors activeConversationId so async handlers can check the *current*
  // selection after an await (avoids races with user navigation).
  const activeIdRef = useRef(activeConversationId);
  // Set once the user manually opens/creates a conversation; blocks the
  // initial auto-open from overriding their choice.
  const userNavigatedRef = useRef(initialized);
  // Sequence number so out-of-order getConversation responses are dropped.
  const openSeqRef = useRef(0);
  const pageActiveRef = useRef(true);
  // True while an IME (e.g. Chinese/Japanese/Korean input method) composition
  // is in progress, so the confirm-selection Enter key doesn't submit the form.
  const isComposingRef = useRef(false);
  const questionInputRef = useRef(null);
  const scroll = useAssistantScroll(messages, pendingQuestion, wide || !paneOpen);

  // Model selector state
  const [providerGroups, setProviderGroups] = useState([]);
  const [selectedProvider, setSelectedProvider] = useAssistantState("chat", "selectedProvider", null);
  const [selectedModel, setSelectedModel] = useAssistantState("chat", "selectedModel", null);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.conversation_id === activeConversationId) || null,
    [activeConversationId, conversations]
  );
  const confirmDeleteConversation = conversations.find((item) => item.conversation_id === confirmDeleteId) || null;
  const historyTerm = historyQuery.trim().normalize("NFKC").toLowerCase();
  const visibleConversations = historyTerm
    ? conversations.filter((item) => item.title.normalize("NFKC").toLowerCase().includes(historyTerm))
    : conversations;

  useEffect(() => {
    let active = true;
    modelService.listModels("chat").then((groups) => {
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
    return () => { active = false; };
  }, []);


  useEffect(() => {
    pageActiveRef.current = true;
    return () => {
      pageActiveRef.current = false;
      openSeqRef.current += 1;
      if (requestRef.current) {
        requestRef.current.abort();
        setError("切換分頁已停止接收回覆；草稿已保留，後端作業可能仍在進行。");
      }
    };
  }, [setError]);

  useEffect(() => {
    let mounted = true;

    async function loadConversations() {
      try {
        const rows = (await chatService.listConversations(CONVERSATION_LIMIT))
          .filter((item) => item.provider !== "langgraph-agent");
        if (!mounted) {
          return;
        }
        setConversations(rows);
        // Don't auto-open if the user already clicked "新對話" or another
        // conversation while this request was in flight.
        if (rows.length > 0 && !userNavigatedRef.current) {
          await handleOpenConversation(rows[0].conversation_id, mounted, { auto: true });
        }
      } catch (err) {
        if (mounted) {
          setError(normalizeApiError(err, "無法載入聊天紀錄"));
        }
      } finally {
        if (mounted) { setInitLoading(false); setInitialized(true); }
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
      setInitialized(true);
      setOpeningConversationId(conversationId);
      setError("");
      if (!wide) {
        setPaneOpen(false);
        requestAnimationFrame(() => conversationHeadingRef.current?.focus({ preventScroll: true }));
      }
    }
    setConfirmDeleteId(null);
    const seq = ++openSeqRef.current;
    try {
      const detail = await chatService.getConversation(conversationId);
      if (!mounted || !pageActiveRef.current || seq !== openSeqRef.current) {
        return;
      }
      if (auto && userNavigatedRef.current) {
        return;
      }
      activeIdRef.current = detail.conversation_id;
      if (!auto) scroll.readFromStart();
      setActiveConversationId(detail.conversation_id);
      setMessages(detail.messages);
    } catch (err) {
      if (mounted && pageActiveRef.current && seq === openSeqRef.current) {
        setError(normalizeApiError(err, "無法載入對話內容"));
      }
    } finally {
      if (!auto && pageActiveRef.current && seq === openSeqRef.current) setOpeningConversationId(null);
    }
  }

  async function refreshConversations() {
    const rows = (await chatService.listConversations(CONVERSATION_LIMIT))
      .filter((item) => item.provider !== "langgraph-agent");
    setConversations(rows);
  }

  async function handleDeleteConversation(conversationId) {
    if (!conversationId || deletingConversationId) return;

    setDeletingConversationId(conversationId);
    setError("");
    try {
      await chatService.deleteConversation(conversationId);
      openSeqRef.current += 1;
      setOpeningConversationId(null);
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
      focusListAfterDeleteRef.current = true;
    } catch (err) {
      setDeleteError(normalizeApiError(err, "刪除對話失敗，請稍後再試。"));
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!question.trim() || loading || openingConversationId) {
      return;
    }

    const sentInConversationId = activeConversationId;
    const controller = new AbortController();
    requestRef.current = controller;
    scroll.jumpToLatest();
    setPendingQuestion(question.trim());
    setLoading(true);
    setError("");
    try {
      const response = await chatService.sendMessage(
        question.trim(),
        sentInConversationId,
        selectedProvider,
        selectedModel,
        controller.signal,
      );
      // Only apply the response if the user hasn't switched conversation
      // while the request was in flight.
      if (!controller.signal.aborted && activeIdRef.current === sentInConversationId) {
        activeIdRef.current = response.conversation_id;
        setActiveConversationId(response.conversation_id);
        setMessages((prev) => [...prev, response]);
        setQuestion("");
      }
      await refreshConversations();
    } catch (err) {
      if (!controller.signal.aborted) setError(normalizeApiError(err, "聊天請求失敗"));
    } finally {
      requestRef.current = null;
      setPendingQuestion("");
      setLoading(false);
    }
  }

  function handleNewConversation() {
    if (!wide) setPaneOpen(false);
    scroll.jumpToLatest();
    userNavigatedRef.current = true;
    setInitialized(true);
    openSeqRef.current += 1; // invalidate in-flight opens
    activeIdRef.current = null;
    setActiveConversationId(null);
    setMessages([]);
    setOpeningConversationId(null);
    setQuestion("");
    setConfirmDeleteId(null);
    setError("");
    // Keep the mobile keyboard closed until the user taps the input.
    requestAnimationFrame(() => conversationHeadingRef.current?.focus({ preventScroll: true }));
  }

  function toggleHistory() {
    setPaneOpen(!paneOpen);
    if (!wide && !paneOpen) requestAnimationFrame(() => sidebarHeadingRef.current?.focus({ preventScroll: true }));
  }

  return (
    <div className="assistant-page chat-page" onKeyDown={(event) => {
      if (event.key === "Escape" && !event.defaultPrevented && !wide && paneOpen) {
        setPaneOpen(false);
        paneToggleRef.current?.focus();
      }
    }}>
      <div className="assistant-toolbar">
        <button type="button" className="assistant-tool-button" ref={paneToggleRef}
          aria-expanded={paneOpen} aria-controls="conversation-list" onClick={toggleHistory}>
          <AssistantIcon name={!wide && paneOpen ? "back" : "history"} />
          {paneOpen ? wide ? "收合歷史" : "返回對話" : "歷史對話"}
        </button>
        <h2 ref={conversationHeadingRef} tabIndex={-1} title={activeConversation?.title}>
          {activeConversation?.title || "新對話"}
        </h2>
        <button type="button" className="assistant-tool-button assistant-new" aria-label="新對話"
          onClick={handleNewConversation} disabled={loading}>
          <AssistantIcon name="new" /><span>新對話</span>
        </button>
      </div>
      {error && <div className="alert alert-error assistant-notice" role="alert">{error}</div>}
      <p className="sr-only" role="status">{openingConversationId ? "正在開啟歷史對話" : loading ? "AI 正在回覆" : messages.length ? "對話內容已更新" : "輸入訊息開始對話"}</p>
      {confirmDeleteConversation && (
        <ConfirmDialog
          title="刪除這則對話？"
          confirmLabel="確認刪除"
          busy={deletingConversationId === confirmDeleteConversation.conversation_id}
          error={deleteError}
          onConfirm={() => handleDeleteConversation(confirmDeleteConversation.conversation_id)}
          onCancel={() => { setConfirmDeleteId(null); setDeleteError(""); }}
        >
          <p>「{confirmDeleteConversation.title}」的 {confirmDeleteConversation.turn_count} 輪問答會被刪除，無法復原。</p>
        </ConfirmDialog>
      )}
      <div className="assistant-layout" data-pane-open={paneOpen || undefined}>

        <aside id="conversation-list" className="assistant-side assistant-history" aria-labelledby="conversation-list-title" hidden={!paneOpen}>
          <div className="assistant-side-heading">
            <h3 id="conversation-list-title" ref={sidebarHeadingRef} tabIndex={-1}>歷史對話</h3>
            <input type="search" aria-label="篩選對話標題" placeholder="篩選對話標題"
              value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} />
            <p className="muted small" role="status">
              {historyTerm ? `${visibleConversations.length} 則符合 · 共 ${conversations.length} 則`
                : `${conversations.length} 則對話 · 最多顯示最近 ${CONVERSATION_LIMIT} 則`}
            </p>
          </div>

          <div className="chat-conversation-scroll">
            <div className="chat-conversation-list">
              {initLoading ? (
                <p className="muted small">載入聊天紀錄…</p>
              ) : (
                <>
                {visibleConversations.map((item) => (
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
                      disabled={loading}
                      aria-current={activeConversationId === item.conversation_id ? "true" : undefined}
                    >
                      <span className="chat-conversation-title" title={item.title}>{item.title}</span>
                      <span className="chat-conversation-meta">
                        {item.provider} · {item.turn_count} 輪
                      </span>
                    </button>

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
                  </div>
                ))}
                {!visibleConversations.length && <p className="muted small">
                  {historyTerm ? "找不到符合的標題。試試其他關鍵字。" : "尚無聊天紀錄。"}
                </p>}
                </>
              )}
            </div>
          </div>
        </aside>

        <div className="assistant-main" hidden={!wide && paneOpen}>
          <AssistantTranscript label="對話內容" busy={loading || Boolean(openingConversationId)} scroll={scroll}
            empty={Boolean(openingConversationId) || (!messages.length && !pendingQuestion)}>
            {openingConversationId ? <p className="muted">載入對話內容…</p> : messages.length || pendingQuestion ? (
              <>{messages.map((item) => (
                <div key={item.id} className="chat-turn">
                  <div className="assistant-message assistant-message-user">
                    <span className="chat-role">你</span>
                    <p>{item.question}</p>
                  </div>
                  <div className="assistant-message assistant-message-reply">
                    <span className="chat-role">
                      {item.model_name || item.provider || "AI 助理"}
                    </span>
                    <AssistantMarkdown>{item.answer}</AssistantMarkdown>
                  </div>
                </div>
              ))}
              {pendingQuestion && <div className="chat-turn"><div className="assistant-message assistant-message-user"><span className="chat-role">你</span><p>{pendingQuestion}</p></div><p className="muted">AI 正在回覆…</p></div>}
              </>
            ) : (
              <AssistantEmpty icon="chat" title="開始一段對話">
                <p>輸入問題，或從歷史對話接續上次的討論。</p>
              </AssistantEmpty>
            )}
          </AssistantTranscript>

          <form className="chat-form" onSubmit={handleSubmit}>
            <div className="chat-input-wrapper">
              <textarea
                ref={questionInputRef}
                aria-label="傳送給 AI 的訊息"
                rows={2}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="請輸入想問 AI 的問題"
                readOnly={loading || Boolean(openingConversationId)}
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
                {loading && <button type="button" className="button-ghost" onClick={() => {
                  requestRef.current?.abort();
                  setError("已停止接收回覆；後端作業可能仍在進行。");
                  // The stop button unmounts once loading ends; keep focus in the composer.
                  questionInputRef.current?.focus();
                }}>停止接收</button>}
                <button
                  type="submit"
                  className="chat-send-btn"
                  aria-disabled={loading || Boolean(openingConversationId) || !question.trim() || undefined}
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
