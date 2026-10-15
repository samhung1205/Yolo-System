import { useCallback, useEffect, useMemo } from "react";

/**
 * Per-class confidence / IoU threshold editor.
 *
 * The class list comes from the selected model's `canonical_class_names`
 * (already returned by `GET /api/yolo-models`), so switching models
 * re-populates the rows automatically.
 *
 * `values` is a map of `classId -> { conf, iou }` holding only the classes
 * the user actually customised; everything else falls back to the page's
 * global conf/iou, which is also what the backend does for absent keys.
 */
export default function ClassThresholdEditor({
  classNames,
  enabled,
  onToggle,
  values,
  onChange,
  defaultConf,
  defaultIou,
  disabled = false,
}) {
  const classEntries = useMemo(() => {
    if (!classNames) return [];
    return Object.entries(classNames)
      .map(([id, name]) => ({ id: String(id), name }))
      .sort((a, b) => Number(a.id) - Number(b.id));
  }, [classNames]);

  // Drop overrides for classes that no longer exist after a model switch, so
  // the request can't carry class ids the backend will reject.
  useEffect(() => {
    if (!enabled) return;
    const validIds = new Set(classEntries.map((entry) => entry.id));
    const stale = Object.keys(values).filter((id) => !validIds.has(id));
    if (stale.length > 0) {
      const next = { ...values };
      for (const id of stale) delete next[id];
      onChange(next);
    }
  }, [classEntries, enabled, values, onChange]);

  const updateClass = useCallback(
    (classId, field, rawValue) => {
      const parsed = parseFloat(rawValue);
      if (Number.isNaN(parsed)) return;
      const clamped = Math.min(1, Math.max(0, parsed));
      const current = values[classId] || { conf: defaultConf, iou: defaultIou };
      onChange({ ...values, [classId]: { ...current, [field]: clamped } });
    },
    [values, onChange, defaultConf, defaultIou]
  );

  const resetClass = useCallback(
    (classId) => {
      if (!(classId in values)) return;
      const next = { ...values };
      delete next[classId];
      onChange(next);
    },
    [values, onChange]
  );

  const customisedCount = Object.keys(values).length;

  return (
    <div className="class-threshold-editor">
      <label className="class-threshold-toggle">
        <input
          type="checkbox"
          checked={enabled}
          disabled={disabled || classEntries.length === 0}
          onChange={(event) => onToggle(event.target.checked)}
        />
        <span>
          各類別自訂閾值
          {enabled && customisedCount > 0 ? `（已自訂 ${customisedCount} 類）` : ""}
        </span>
      </label>

      {!enabled ? (
        <p className="muted small">
          目前所有類別共用上方的 conf / IOU。勾選後可針對單一類別（例如只放寬 ship、收緊
          airplane）分別設定。
        </p>
      ) : (
        <>
          <p className="muted small">
            留空（顯示為預設）的類別會沿用上方的 conf {defaultConf.toFixed(2)} / IOU{" "}
            {defaultIou.toFixed(2)}。這只影響推論後的篩選與去重，不會改變模型本身，
            因此無法找回信心低於所有門檻最小值的物件。
          </p>
          <div className="table-wrapper">
            <table className="class-threshold-table">
              <thead>
                <tr>
                  <th>類別</th>
                  <th>信心閾值 (conf)</th>
                  <th>IOU 閾值</th>
                  <th aria-label="重設" />
                </tr>
              </thead>
              <tbody>
                {classEntries.map(({ id, name }) => {
                  const override = values[id];
                  const isCustom = Boolean(override);
                  return (
                    <tr key={id} className={isCustom ? "is-custom" : ""}>
                      <td>
                        <span className="class-threshold-name">{name}</span>
                        <span className="class-threshold-id">#{id}</span>
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.05"
                          disabled={disabled}
                          value={override ? override.conf : defaultConf}
                          onChange={(event) => updateClass(id, "conf", event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.05"
                          disabled={disabled}
                          value={override ? override.iou : defaultIou}
                          onChange={(event) => updateClass(id, "iou", event.target.value)}
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button button-secondary class-threshold-reset"
                          disabled={disabled || !isCustom}
                          onClick={() => resetClass(id)}
                        >
                          {isCustom ? "重設" : "預設"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {customisedCount > 0 ? (
            <button
              type="button"
              className="button button-secondary class-threshold-reset"
              disabled={disabled}
              onClick={() => onChange({})}
            >
              全部回復預設
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
