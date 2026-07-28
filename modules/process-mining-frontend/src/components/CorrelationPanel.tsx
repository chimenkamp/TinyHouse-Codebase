import { Box, CircleCheck, Clock3, Fingerprint, GitMerge, MapPin, Route, ScanSearch } from "lucide-react";
import { activityColors, evidenceMatrix, processCases } from "../data/mockData";

interface CorrelationPanelProps {
  selectedCase: string;
  onSelectCase: (caseId: string) => void;
}

const evidenceIcons = [Clock3, MapPin, Fingerprint, Route];
const evidenceLabels = ["Temporal", "Spatial", "Object ID", "Sequence"];

export function CorrelationPanel({ selectedCase, onSelectCase }: CorrelationPanelProps) {
  const activeCase = processCases.find((item) => item.id === selectedCase) ?? processCases[0];

  return (
    <div className="correlation-layout">
      <div className="case-queue">
        <div className="subpanel-heading">
          <div>
            <span className="eyebrow">Object-centric traces</span>
            <h3>Case candidates</h3>
          </div>
          <span className="queue-count">24 open</span>
        </div>
        <div className="case-list">
          {processCases.map((item) => (
            <button type="button" className={`case-item ${item.id === activeCase.id ? "active" : ""}`} key={item.id} onClick={() => onSelectCase(item.id)}>
              <div className="case-icon"><Box size={17} /></div>
              <div className="case-main">
                <strong>{item.id}</strong>
                <span>{item.object} · {item.variant}</span>
              </div>
              <div className="case-meta">
                <span className={`case-status ${item.status}`}>{item.status}</span>
                <strong>{item.confidence}%</strong>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="trace-panel">
        <div className="trace-header">
          <div>
            <span className="eyebrow">Correlated trace · {activeCase.object}</span>
            <h3>{activeCase.id} <small>{activeCase.duration} elapsed</small></h3>
          </div>
          <div className="correlation-score">
            <ScanSearch size={18} />
            <div><span>Correlation confidence</span><strong>{activeCase.confidence}%</strong></div>
          </div>
        </div>

        <div className="trace-scroll">
          <div className="trace-line" style={{ width: `${Math.max(100, activeCase.events.length * 17)}%` }}>
            {activeCase.events.map((event, index) => (
              <div className="trace-step" key={`${event}-${index}`}>
                <div className="trace-node" style={{ "--activity-color": activityColors[event] ?? "#81a1c1" } as React.CSSProperties}>
                  <i>{index + 1}</i>
                  <strong>{event}</strong>
                  <span>{index === 0 ? activeCase.started : `+${(index * 2.7 + 1.1).toFixed(1)}m`}</span>
                </div>
                {index < activeCase.events.length - 1 && (
                  <div className="trace-edge"><span>{Math.max(89, 99 - index * 1.3).toFixed(1)}%</span><i /></div>
                )}
              </div>
            ))}
            {activeCase.status === "running" && <div className="trace-running"><i /><span>Awaiting next event</span></div>}
            {activeCase.status === "complete" && <div className="trace-complete"><CircleCheck size={17} /><span>Case complete</span></div>}
          </div>
        </div>

        <div className="evidence-section">
          <div className="evidence-title">
            <GitMerge size={16} />
            <div><strong>Correlation evidence</strong><span>Weighted multi-perspective matching</span></div>
          </div>
          <div className="evidence-matrix">
            <div className="matrix-header"><span />{evidenceLabels.map((label, index) => { const Icon = evidenceIcons[index]; return <span key={label}><Icon size={13} /> {label}</span>; })}</div>
            {evidenceMatrix.map((row) => (
              <div className={`matrix-row ${row.label === activeCase.id ? "selected" : ""}`} key={row.label}>
                <strong>{row.label}</strong>
                {row.scores.map((score, index) => (
                  <span key={index} title={`${evidenceLabels[index]}: ${(score * 100).toFixed(0)}%`} style={{ "--score": score } as React.CSSProperties}>{(score * 100).toFixed(0)}</span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
