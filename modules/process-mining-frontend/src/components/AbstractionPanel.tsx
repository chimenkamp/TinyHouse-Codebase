import { ArrowRight, Braces, CheckCircle2, Cpu, RadioTower, WandSparkles } from "lucide-react";
import { abstractionRules, recentEvents } from "../data/mockData";

interface AbstractionPanelProps {
  tick: number;
}

export function AbstractionPanel({ tick }: AbstractionPanelProps) {
  const activeRule = tick % 5;

  return (
    <div className="abstraction-layout">
      <div className="abstraction-flow" aria-label="Sensor to activity abstraction rules">
        <div className="flow-column-title"><RadioTower size={15} /> Sensor evidence</div>
        <div className="flow-column-title"><Braces size={15} /> Abstraction rule</div>
        <div className="flow-column-title"><WandSparkles size={15} /> Semantic activity</div>

        {abstractionRules.slice(0, 5).map((rule, index) => (
          <div className={`abstraction-row ${index === activeRule ? "active" : ""}`} key={rule.activity}>
            <div className="signal-block">
              <span>{rule.source}</span>
              <code>{rule.signal.split("\n").map((line) => <em key={line}>{line}</em>)}</code>
            </div>
            <div className="rule-link">
              <span>{rule.rule}</span>
              <i><ArrowRight size={14} /></i>
            </div>
            <div className="activity-block">
              <i><Cpu size={15} /></i>
              <div>
                <strong>{rule.activity}</strong>
                <span>{rule.confidence}% confidence</span>
              </div>
              <CheckCircle2 size={15} />
            </div>
          </div>
        ))}
      </div>

      <div className="event-log-panel">
        <div className="subpanel-heading">
          <div>
            <span className="eyebrow">Semantic event stream</span>
            <h3>Latest abstractions</h3>
          </div>
          <span className="streaming-badge"><i /> Writing XES</span>
        </div>
        <div className="event-log-header">
          <span>Activity</span><span>Case candidate</span><span>Confidence</span>
        </div>
        <div className="event-log-list">
          {recentEvents.map((event, index) => (
            <div className={`event-log-row ${index === tick % recentEvents.length ? "fresh" : ""}`} key={event.id}>
              <div className="event-activity">
                <i className={`event-tone ${event.tone}`} />
                <div><strong>{event.activity}</strong><span>{event.resource} · {event.timestamp}</span></div>
              </div>
              <code>{event.caseId}</code>
              <div className="confidence-value">
                <strong>{event.confidence}%</strong>
                <span><i style={{ width: `${event.confidence}%` }} /></span>
              </div>
            </div>
          ))}
        </div>
        <div className="xes-footer">
          <span><strong>9</strong> activity classes</span>
          <span><strong>{1_842 + tick * 3}</strong> events today</span>
          <span><strong>42 ms</strong> median latency</span>
        </div>
      </div>
    </div>
  );
}
