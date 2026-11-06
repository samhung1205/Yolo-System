import { useCallback, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const MARKDOWN_PLUGINS = [remarkGfm];
const MARKDOWN_COMPONENTS = {
  pre: ({ node: _node, ...props }) => <pre tabIndex={0} {...props} />,
  table: ({ node: _node, ...props }) => (
    <div className="assistant-table-scroll" role="region" aria-label="回覆表格" tabIndex={0}>
      <table {...props} />
    </div>
  ),
};
const NEAR_BOTTOM = 40;
const ICON_PATHS = {
  history: "M3 12a9 9 0 1 1 2.6 6.4M3 5v7h7m2-4v5l3 2",
  settings: "M4 7h16M4 17h16M8 4v6m8 4v6",
  new: "M12 5v14M5 12h14",
  back: "M19 12H5m7 7-7-7 7-7",
  down: "M12 5v14m-6-6 6 6 6-6",
  chat: "M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm2 6h10",
  analysis: "M7 3H5a2 2 0 0 0-2 2v2m14-4h2a2 2 0 0 1 2 2v2M3 17v2a2 2 0 0 0 2 2h2m10 0h2a2 2 0 0 0 2-2v-2M8 14v3m4-8v8m4-5v5",
};

export function AssistantIcon({ name }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}

export function AssistantMarkdown({ children }) {
  return <div className="markdown-report assistant-markdown">
    <ReactMarkdown remarkPlugins={MARKDOWN_PLUGINS} components={MARKDOWN_COMPONENTS}>{children}</ReactMarkdown>
  </div>;
}

export function AssistantEmpty({ icon, title, children }) {
  return <div className="assistant-empty">
    <div className="assistant-empty-icon"><AssistantIcon name={icon} /></div>
    <h3>{title}</h3>
    {children}
  </div>;
}

export function useAssistantScroll(messages, pending, visible) {
  const threadRef = useRef(null);
  const follow = useRef(true);
  const restartAtTop = useRef(false);
  const [awayFromLatest, setAwayFromLatest] = useState(false);

  const syncPosition = useCallback(() => {
    const thread = threadRef.current;
    if (!thread?.clientHeight) return;
    if (restartAtTop.current) {
      thread.scrollTop = 0;
      restartAtTop.current = false;
    } else if (follow.current) {
      thread.scrollTop = thread.scrollHeight;
    }
    setAwayFromLatest(thread.scrollHeight - thread.clientHeight - thread.scrollTop > NEAR_BOTTOM);
  }, []);

  useLayoutEffect(syncPosition, [syncPosition, messages, pending, visible]);

  useLayoutEffect(() => {
    const observer = new ResizeObserver(syncPosition);
    observer.observe(threadRef.current);
    return () => observer.disconnect();
  }, [syncPosition]);

  function trackScroll(event) {
    const thread = event.currentTarget;
    if (!thread.clientHeight) return;
    follow.current = thread.scrollHeight - thread.clientHeight - thread.scrollTop <= NEAR_BOTTOM;
    setAwayFromLatest(!follow.current);
  }

  function readFromStart() {
    follow.current = false;
    restartAtTop.current = true;
  }

  function jumpToLatest() {
    restartAtTop.current = false;
    follow.current = true;
    syncPosition();
  }

  return { threadRef, awayFromLatest, trackScroll, readFromStart, jumpToLatest };
}

export default function AssistantTranscript({ label, busy, scroll, empty, children }) {
  return (
    <div className="assistant-transcript">
      <div ref={scroll.threadRef} className="assistant-thread" role="region" aria-label={label}
        tabIndex={0} aria-busy={busy || undefined} onScroll={scroll.trackScroll}>
        <div className={`assistant-thread-inner${empty ? " is-empty" : ""}`}>{children}</div>
      </div>
      {scroll.awayFromLatest && (
        <button type="button" className="assistant-jump-latest" onClick={() => {
          scroll.jumpToLatest();
          scroll.threadRef.current?.focus({ preventScroll: true });
        }}>
          <AssistantIcon name="down" />回到最新
        </button>
      )}
    </div>
  );
}
