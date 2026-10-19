import { Link } from "react-router";

export default function AnalysisEvidence({ references = [], tools = [] }) {
  return <>
    {references.length > 0 && <div className="agent-reference-list">
      <span className="detail-label">分析依據</span>
      {references.map((reference, index) => {
        const id = reference.detection_id ?? (reference.type === "detection" ? reference.id : null);
        const batch = reference.batch_id ?? (reference.type === "batch" ? reference.id : null);
        return <div key={index} className="agent-reference-item">
          {id ? <Link to={`/agent?mode=explain_detection&detection_id=${encodeURIComponent(id)}`}>偵測結果 #{id}</Link>
            : batch ? <Link to={`/agent?mode=batch_analysis&batch_id=${encodeURIComponent(batch)}`}>批次結果 #{batch}</Link>
              : <span>資料來源 {index + 1}（見技術詳情）</span>}
        </div>;
      })}
    </div>}
    {(tools.length > 0 || references.length > 0) && <details className="technical-details">
      <summary>技術詳情</summary>
      <pre>{JSON.stringify({ tools, references }, null, 2)}</pre>
    </details>}
  </>;
}
