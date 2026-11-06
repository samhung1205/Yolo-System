import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import "./SelectField.css";

const EDGE = 12;
const GAP = 6;
const MAX_HEIGHT = 384;

function placePopover(trigger, panel, searchable) {
  const rect = trigger.getBoundingClientRect();
  const viewport = window.visualViewport;
  const left = (viewport?.offsetLeft ?? 0) + EDGE;
  const top = (viewport?.offsetTop ?? 0) + EDGE;
  const right = left + (viewport?.width ?? document.documentElement.clientWidth) - 2 * EDGE;
  const bottom = top + (viewport?.height ?? window.innerHeight) - 2 * EDGE;
  const width = Math.min(right - left, Math.max(rect.width, searchable ? 336 : 192));
  const belowStart = Math.max(top, rect.bottom + GAP);
  const aboveEnd = Math.min(bottom, rect.top - GAP);
  const below = bottom - belowStart;
  const above = aboveEnd - top;
  const openUp = below < MAX_HEIGHT && above > below;

  Object.assign(panel.style, {
    width: `${width}px`,
    left: `${Math.max(left, Math.min(rect.left, right - width))}px`,
    top: openUp ? "auto" : `${belowStart}px`,
    bottom: openUp ? `${window.innerHeight - aboveEnd}px` : "auto",
    maxHeight: `${Math.max(0, Math.min(MAX_HEIGHT, openUp ? above : below))}px`,
  });
}

function normalize(text) {
  return text.normalize("NFKC").toLowerCase();
}

/** Single choice with optional in-panel search. Form callers own the committed value. */
export default function SelectField({
  id, label, describedBy, value, onChange, options = [], groups = [{ options }],
  placeholder = "請選擇", searchPlaceholder, emptyText = "沒有符合的選項",
  disabled = false, required = false, variant = "field", applied = false,
}) {
  const uid = useId();
  const fieldId = id || uid;
  const valueId = `${uid}-value`;
  const panelId = `${uid}-panel`;
  const listId = `${uid}-list`;
  const trigger = useRef(null);
  const panel = useRef(null);
  const list = useRef(null);
  const search = useRef(null);
  const root = useRef(null);
  const typeahead = useRef({ text: "", time: 0 });
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(null);
  const [touchOpen, setTouchOpen] = useState(false);
  const searchable = Boolean(searchPlaceholder);
  const selected = groups.flatMap((group) => group.options).find((option) => option.value === value);
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  const visible = groups.map((group) => ({
    ...group,
    options: group.options.filter((option) => {
      if (!terms.length) return true;
      const text = normalize(`${group.label || ""} ${option.label} ${option.description || ""} ${option.searchText || ""}`);
      return terms.every((term) => text.includes(term));
    }),
  })).filter((group) => group.options.length > 0);
  const choices = visible.flatMap((group) => group.options);
  const enabled = choices.filter((option) => !option.disabled);
  const active = enabled.find((option) => option.value === highlight) || enabled[0];
  const optionId = (option) => `${listId}-${encodeURIComponent(option.value)}`;
  const activeId = open && active ? optionId(active) : undefined;

  function close(returnFocus = false) {
    if (!panel.current?.matches(":popover-open")) return;
    panel.current.hidePopover();
    setOpen(false);
    if (returnFocus) trigger.current.focus({ preventScroll: true });
  }

  function show(fromEnd = false, touch = false) {
    if (disabled) return;
    const last = fromEnd ? groups.flatMap((group) => group.options).findLast((option) => !option.disabled) : null;
    setHighlight(selected && !selected.disabled ? value : last?.value);
    setQuery("");
    setTouchOpen(touch);
    typeahead.current.text = "";
    placePopover(trigger.current, panel.current, searchable);
    panel.current.showPopover();
    setOpen(true);
  }

  useLayoutEffect(() => {
    if (!open || !searchable) return;
    // On touch, let the user browse before asking the on-screen keyboard to open.
    (touchOpen ? panel.current : search.current).focus({ preventScroll: true });
  }, [open, searchable, touchOpen]);

  useLayoutEffect(() => {
    if (!activeId) return;
    const row = document.getElementById(activeId)?.getBoundingClientRect();
    const bounds = list.current.getBoundingClientRect();
    if (row && row.top < bounds.top) list.current.scrollTop -= bounds.top - row.top;
    else if (row && row.bottom > bounds.bottom) list.current.scrollTop += row.bottom - bounds.bottom;
  }, [activeId, query]);

  useEffect(() => {
    if (!open) return;
    const node = panel.current;
    if (disabled) {
      node.hidePopover();
      setOpen(false);
      return;
    }
    function dismiss(event) {
      if (!root.current.contains(event.target)) close();
    }
    function reposition(event) {
      if (event.target instanceof Node && node.contains(event.target)) return;
      placePopover(trigger.current, node, searchable);
    }
    window.addEventListener("pointerdown", dismiss, true);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    window.visualViewport?.addEventListener("resize", reposition);
    window.visualViewport?.addEventListener("scroll", reposition);
    return () => {
      window.removeEventListener("pointerdown", dismiss, true);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
      window.visualViewport?.removeEventListener("resize", reposition);
      window.visualViewport?.removeEventListener("scroll", reposition);
    };
  }, [open, disabled, searchable]);

  function choose(option) {
    if (!option || option.disabled) return;
    close(true);
    if (option.value !== value) onChange(option.value);
  }

  function handleKey(event) {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    const { key } = event;
    if (!open) {
      if (key !== "ArrowDown" && key !== "ArrowUp") return;
      event.preventDefault();
      show(key === "ArrowUp");
      return;
    }
    if (key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (key === "Tab" && event.shiftKey && searchable && event.target !== trigger.current) {
      event.preventDefault();
      close(true);
    } else if (key === "Enter" || (key === " " && !searchable)) {
      event.preventDefault();
      choose(active);
    } else if (key === "ArrowDown" || key === "ArrowUp" || (!searchable && (key === "Home" || key === "End"))) {
      event.preventDefault();
      const index = enabled.indexOf(active);
      const next = key === "Home" ? 0 : key === "End" ? enabled.length - 1
        : Math.max(0, Math.min(enabled.length - 1, index + (key === "ArrowDown" ? 1 : -1)));
      setHighlight(enabled[next]?.value);
    } else if (!searchable && key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
      const now = performance.now();
      const letter = normalize(key);
      const previous = now - typeahead.current.time < 650 ? typeahead.current.text : "";
      const text = previous === letter ? letter : previous + letter;
      typeahead.current = { text, time: now };
      const start = enabled.indexOf(active) + (text.length === 1 ? 1 : 0);
      const ordered = [...enabled.slice(start), ...enabled.slice(0, start)];
      const match = ordered.find((option) => normalize(option.label).startsWith(text));
      if (match) setHighlight(match.value);
    }
  }

  if (typeof HTMLElement.prototype.showPopover !== "function") {
    const renderOption = (option) => (
      <option key={option.value} value={option.value} disabled={option.disabled}>
        {[option.selectedLabel || option.label, option.selectedDetail, option.description].filter(Boolean).join(" · ")}
      </option>
    );
    return (
      <select id={fieldId} className={`select-trigger select-${variant}`} aria-label={label}
        aria-describedby={describedBy} value={selected ? value : ""} disabled={disabled} required={required}
        onChange={(event) => onChange(event.target.value)}>
        {!selected && !groups.some((group) => group.options.some((option) => option.value === "")) &&
          <option value="" disabled>{placeholder}</option>}
        {groups.map((group) => group.label
          ? <optgroup key={group.label} label={group.label}>{group.options.map(renderOption)}</optgroup>
          : group.options.map(renderOption))}
      </select>
    );
  }

  return (
    <div className={`select-field select-${variant}`} ref={root} onKeyDown={handleKey}
      onBlur={(event) => {
        if (!open || event.currentTarget.contains(event.relatedTarget)) return;
        queueMicrotask(() => {
          if (!root.current?.contains(document.activeElement)) close();
        });
      }}>
      <button type="button" className="select-trigger" ref={trigger} id={fieldId} disabled={disabled}
        role={searchable ? undefined : "combobox"} aria-label={label}
        aria-describedby={[valueId, describedBy].filter(Boolean).join(" ")}
        aria-required={!searchable && required ? true : undefined}
        aria-haspopup={searchable ? "dialog" : "listbox"} aria-expanded={open}
        aria-controls={searchable ? panelId : listId} aria-activedescendant={searchable ? undefined : activeId}
        data-applied={applied || undefined}
        onClick={(event) => {
          if (open) close(true);
          else {
            trigger.current.focus({ preventScroll: true });
            show(false, event.nativeEvent.pointerType === "touch");
          }
        }}>
        {selected?.indicator && <i className={`select-dot select-dot-${selected.indicator}`} aria-hidden="true" />}
        <span className="select-value" id={valueId} data-placeholder={!selected || undefined}>
          <span>{selected?.selectedLabel || selected?.label || placeholder}</span>
          {selected?.selectedDetail && <span className="select-value-detail">{selected.selectedDetail}</span>}
        </span>
        <svg className="select-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m4 6 4 4 4-4" />
        </svg>
      </button>
      <div className="select-popover" ref={panel} id={panelId} popover="manual"
        role={searchable ? "dialog" : undefined} aria-label={searchable ? label : undefined}
        tabIndex={searchable ? -1 : undefined}>
        {searchable && <div className="select-search">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="4.75" /><path d="m12 12 4 4" />
          </svg>
          <input ref={search} role="combobox" aria-label={searchPlaceholder} aria-autocomplete="list"
            aria-controls={listId} aria-expanded={open} aria-activedescendant={activeId}
            autoComplete="off" placeholder={searchPlaceholder} value={query}
            onChange={(event) => { setQuery(event.target.value); setHighlight(null); }} />
        </div>}
        <div className="select-options" role="listbox" aria-label={label} ref={list} id={listId} tabIndex={-1}>
          {visible.map((group) => {
            const rows = group.options.map((option) => (
              <div className="select-option" role="option" id={optionId(option)} key={option.value}
                aria-selected={option.value === value} aria-disabled={option.disabled || undefined}
                data-active={option.value === active?.value || undefined}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(option)}>
                {option.indicator && <i className={`select-dot select-dot-${option.indicator}`} aria-hidden="true" />}
                <span className="select-option-text">
                  <span>{option.label}</span>
                  {option.description && <span className="select-option-detail">{option.description}</span>}
                </span>
                {option.value === value && <svg className="select-check" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="m3.5 8 3 3 6-6" />
                </svg>}
              </div>
            ));
            return group.label ? <div className="select-option-group" role="group" aria-label={group.label} key={group.label}>
              <div className="select-group-label" aria-hidden="true">{group.label}</div>{rows}
            </div> : rows;
          })}
        </div>
        <p className={choices.length ? "sr-only" : "select-empty"} role="status">
          {choices.length ? (query ? `找到 ${choices.length} 個選項` : "") : emptyText}
        </p>
      </div>
    </div>
  );
}
