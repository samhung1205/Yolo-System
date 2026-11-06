import { useId, useState } from "react";
import SelectField from "./SelectField";

const CLASS_PREVIEW_LIMIT = 12;

function modelGroup(model) {
  const count = model.class_count ?? Object.keys(model.canonical_class_names || {}).length;
  if (model.task === "obb") return `旋轉框 OBB · ${count} 類別`;
  if (/\bcoco\b/i.test(model.dataset_variant || "")) return `COCO · ${count} 類別`;
  return `${count} 類別${/\bpre\b/i.test(model.dataset_variant || "") ? " · Pre" : ""}`;
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
    groups.get(label).push({
      value: model.key,
      label: model.architecture || model.display_name,
      selectedDetail: label,
      searchText: `${model.key} ${model.display_name} ${orderedClassNames(model.canonical_class_names).join(" ")}`,
      description: model.available ? undefined : "暫不可用",
      disabled: !model.available,
    });
  }

  return (
    <div className="field yolo-model-field">
      <label htmlFor={selectId}>選擇推論模型</label>
      <SelectField id={selectId} label="選擇推論模型" value={value} onChange={onChange}
        groups={Array.from(groups, ([label, options]) => ({ label, options }))}
        placeholder={loading ? "載入模型清單中…" : "請選擇模型"} searchPlaceholder="搜尋推論模型或類別"
        emptyText="找不到符合的推論模型" disabled={loading || !models.length} required
        describedBy={selected ? descriptionId : undefined} />
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
