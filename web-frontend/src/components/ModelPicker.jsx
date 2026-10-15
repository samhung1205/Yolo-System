/** A native grouped select supplies keyboard, touch and screen-reader behavior. */
export default function ModelPicker({
  providerGroups = [], selectedProvider, selectedModel, onSelect, disabled = false,
}) {
  const hasSelection = providerGroups.some((group) =>
    group.available && group.provider === selectedProvider && group.models.includes(selectedModel)
  );
  return (
    <select className="model-picker-native" aria-label="AI 模型"
      value={hasSelection ? JSON.stringify([selectedProvider, selectedModel]) : ""}
      disabled={disabled} onChange={(event) => onSelect(...JSON.parse(event.target.value))}>
      {!hasSelection && <option value="" disabled>選擇可用的 AI 模型</option>}
      {providerGroups.map((group) => (
        <optgroup key={group.provider} label={group.label}>
          {group.available ? group.models.map((model) => (
            <option key={model} value={JSON.stringify([group.provider, model])}>{group.label} · {model}</option>
          )) : <option disabled>{group.label} 暫不可用，請聯絡管理員</option>}
        </optgroup>
      ))}
    </select>
  );
}
