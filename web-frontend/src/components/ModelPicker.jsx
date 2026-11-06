import SelectField from "./SelectField";

export default function ModelPicker({
  providerGroups = [], selectedProvider, selectedModel, onSelect, disabled = false,
}) {
  const groups = providerGroups.map((group) => ({
    label: group.label,
    options: group.available && group.models.length ? group.models.map((model) => ({
      value: JSON.stringify([group.provider, model]),
      label: model,
      selectedDetail: group.label,
      searchText: group.provider,
    })) : [{
      value: JSON.stringify([group.provider]),
      label: group.available ? "目前沒有可選模型" : "暫不可用",
      description: group.available ? undefined : "請聯絡管理員",
      disabled: true,
    }],
  }));

  return (
    <SelectField label="AI 模型" variant="composer" groups={groups}
      value={JSON.stringify([selectedProvider, selectedModel])}
      onChange={(value) => onSelect(...JSON.parse(value))} disabled={disabled}
      placeholder="選擇 AI 模型" searchPlaceholder="搜尋模型或供應商"
      emptyText="找不到符合的 AI 模型" />
  );
}
