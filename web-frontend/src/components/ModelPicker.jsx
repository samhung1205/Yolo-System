import { useEffect, useRef, useState } from "react";

/**
 * ModelPicker — pill button that opens a dropdown list of LLM providers/models.
 *
 * Props:
 *   providerGroups  – array from GET /api/models
 *   selectedProvider – currently selected provider string
 *   selectedModel    – currently selected model string
 *   onSelect(provider, model) – called when user picks a model
 *   disabled         – disable when message is being sent
 */
export default function ModelPicker({
  providerGroups = [],
  selectedProvider,
  selectedModel,
  onSelect,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function handleOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const currentGroup = providerGroups.find((g) => g.provider === selectedProvider);
  const displayLabel =
    currentGroup && selectedModel
      ? `${currentGroup.label} · ${selectedModel}`
      : "選擇模型";

  return (
    <div className="model-picker" ref={wrapperRef}>
      <button
        type="button"
        className="model-picker-btn"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="切換 LLM 模型"
      >
        <span className="model-picker-label">{displayLabel}</span>
        <svg
          className="model-picker-chevron"
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="model-picker-dropdown" role="listbox">
          {providerGroups.map((group) => (
            <div key={group.provider} className="model-picker-group">
              <div className="model-picker-group-header">
                <span>{group.label}</span>
                {!group.available && (
                  <span className="model-picker-badge">需設定 API Key</span>
                )}
              </div>

              {group.available ? (
                group.models.map((model) => {
                  const active =
                    selectedProvider === group.provider && selectedModel === model;
                  return (
                    <button
                      key={model}
                      type="button"
                      role="option"
                      aria-selected={active}
                      className={`model-picker-item${active ? " active" : ""}`}
                      onClick={() => {
                        onSelect(group.provider, model);
                        setOpen(false);
                      }}
                    >
                      {active && (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
                          <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                      {model}
                    </button>
                  );
                })
              ) : (
                <div className="model-picker-item-hint">
                  在 <code>backend/.env</code> 設定 API Key 後可用
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
