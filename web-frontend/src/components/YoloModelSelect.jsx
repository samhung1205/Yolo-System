import { useId, useState } from "react";

const CLASS_PREVIEW_LIMIT = 12;

function modelGroup(model) {
  if (model.task === "obb") return `旋轉框 OBB · ${model.class_count} 類別`;
  if (/\bcoco\b/i.test(model.dataset_variant || "")) return `COCO · ${model.class_count} 類別`;
  const count = model.class_count ?? Object.keys(model.canonical_class_names || {}).length;
  return `${count} 類別${/\bpre\b/i.test(model.dataset_variant || "") ? " · Pre" : ""}`;
}

/** Short family tag for option text, so same-named architectures stay distinct
 * in the closed select without overflowing narrow screens. */
function modelTag(model) {
  const count = model.class_count ?? Object.keys(model.canonical_class_names || {}).length;
  if (model.task === "obb" && !/\bobb\b/i.test(model.architecture || "")) return `OBB ${count} 類`;
  if (/\bcoco\b/i.test(model.dataset_variant || "")) return `COCO ${count} 類`;
  return `${count} 類${/\bpre\b/i.test(model.dataset_variant || "") ? " Pre" : ""}`;
}

/** Class names in class-id order, from a `{ id: name }` map. */
export function orderedClassNames(classNames) {
  return Object.entries(classNames || {})
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([, name]) => name);
}

function ModelClassList({ names }) {
  const [expanded, setExpanded] = useState(false);
  if (!names.length) return null;
  const collapsible = names.length > CLASS_PREVIEW_LIMIT;
  const visible = collapsible && !expanded ? names.slice(0, CLASS_PREVIEW_LIMIT - 2) : names;

  return (
    <div className="model-class-list">
      <ul aria-label="此模型可偵測的類別">
        {visible.map((name) => <li key={name}>{name}</li>)}
      </ul>
      {collapsible ? (
        <button type="button" className="button-ghost model-class-toggle" aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}>
          {expanded ? "收合類別" : `顯示全部 ${names.length} 類`}
        </button>
      ) : null}
    </div>
  );
}

/** Native optgroups preserve keyboard navigation while separating model families. */
export default function YoloModelSelect({ models, value, onChange, loading }) {
  const baseId = useId();
  const selectId = `${baseId}-select`;
  const descriptionId = `${baseId}-description`;
  const selected = models.find((model) => model.key === value);
  const selectedClasses = orderedClassNames(selected?.canonical_class_names);
  const groups = new Map();
  for (const model of models) {
    const label = modelGroup(model);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(model);
  }

  return (
    <div className="field yolo-model-field">
      <label htmlFor={selectId}>選擇推論模型</label>
      <select id={selectId} value={value} onChange={(event) => onChange(event.target.value)}
        disabled={loading || !models.some((model) => model.available)} required
        aria-describedby={selected ? descriptionId : undefined}>
        {loading && <option value="">載入模型清單中…</option>}
        {!loading && !value && <option value="">請選擇模型</option>}
        {Array.from(groups, ([label, items]) => (
          <optgroup key={label} label={label}>
            {items.map((model) => <option key={model.key} value={model.key} disabled={!model.available}>
              {model.architecture || model.display_name}（{modelTag(model)}）{model.available ? "" : "（不可用）"}
            </option>)}
          </optgroup>
        ))}
      </select>
      {selected && <div className="yolo-model-description">
        <p id={descriptionId}>
          <span className="yolo-model-description-label">目前模型</span>
          <span className="yolo-model-description-name">{selected.display_name}</span>
          {selectedClasses.length ? <span>只會偵測以下 {selectedClasses.length} 類</span> : null}
        </p>
        <ModelClassList key={selected.key} names={selectedClasses} />
      </div>}
    </div>
  );
}
