export default function ThresholdSummary({ conf, iou }) {
  return (
    <summary className="threshold-summary">
      <span className="threshold-summary-title">進階閾值設定</span>
      <span className="threshold-summary-values">
        <span>conf {conf.toFixed(2)}</span>
        <span>IoU {iou.toFixed(2)}</span>
      </span>
    </summary>
  );
}
