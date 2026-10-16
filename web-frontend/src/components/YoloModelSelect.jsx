import { useId } from "react";

function modelGroup(model) {
  if (model.task === "obb") return `旋轉框 OBB · ${model.class_count} 類別`;
  if (/\bcoco\b/i.test(model.dataset_variant || "")) return `COCO · ${model.class_count} 類別`;
  const count = model.class_count ?? Object.keys(model.canonical_class_names || {}).length;
  return `${count} 類別${/\bpre\b/i.test(model.dataset_variant || "") ? " · Pre" : ""}`;
}

/** Native optgroups preserve keyboard navigation while separating model families. */
export default function YoloModelSelect({ models, value, onChange, loading }) {
  const descriptionId = useId();
  const selected = models.find((model) => model.key === value);
  const groups = new Map();
  for (const model of models) {
    const label = modelGroup(model);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(model);
  }

  return (
    <label className="field yolo-model-field">
      <span id={`${descriptionId}-label`}>選擇推論模型</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}
        disabled={loading || !models.some((model) => model.available)} required
        aria-labelledby={`${descriptionId}-label`} aria-describedby={selected ? descriptionId : undefined}>
        {loading && <option value="">載入模型清單中…</option>}
        {!loading && !value && <option value="">請選擇模型</option>}
        {Array.from(groups, ([label, items]) => (
          <optgroup key={label} label={label}>
            {items.map((model) => <option key={model.key} value={model.key} disabled={!model.available}>
              {model.architecture || model.display_name}{model.available ? "" : "（不可用）"}
            </option>)}
          </optgroup>
        ))}
      </select>
      {selected && <span id={descriptionId} className="field-hint yolo-model-description">
        <span className="yolo-model-description-label">目前模型</span>
        <span>{selected.display_name}</span>
      </span>}
    </label>
  );
}
