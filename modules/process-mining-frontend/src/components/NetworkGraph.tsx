import { Cpu, Radio, Server } from "lucide-react";
import { networkLinks, networkNodes } from "../data/mockData";

interface NetworkGraphProps {
  selectedNode: string;
  onSelectNode: (nodeId: string) => void;
  tick: number;
}

function nodeCenter(nodeId: string) {
  const node = networkNodes.find((candidate) => candidate.id === nodeId)!;
  return { x: node.x + 58, y: node.y + 28 };
}

function linkPath(sourceId: string, targetId: string) {
  const source = nodeCenter(sourceId);
  const target = nodeCenter(targetId);
  const bend = Math.max(42, Math.abs(target.x - source.x) * 0.48);
  return `M ${source.x} ${source.y} C ${source.x + bend} ${source.y}, ${target.x - bend} ${target.y}, ${target.x} ${target.y}`;
}

export function NetworkGraph({ selectedNode, onSelectNode, tick }: NetworkGraphProps) {
  const selected = networkNodes.find((node) => node.id === selectedNode) ?? networkNodes[0];

  return (
    <div className="network-visual">
      <div className="network-toolbar">
        <div className="network-legend">
          <span><i className="legend-dot pi" /> Raspberry Pi</span>
          <span><i className="legend-dot edge" /> Jetson edge</span>
          <span><i className="legend-dot broker" /> Broker</span>
        </div>
        <span className="packet-counter">{(109 + (tick % 7)).toFixed(0)} msg/s</span>
      </div>

      <svg className="network-svg" viewBox="0 0 590 576" role="img" aria-label="Interactive TinyHouse edge network topology">
        <defs>
          <filter id="node-shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="5" stdDeviation="7" floodColor="#2e3440" floodOpacity="0.12" />
          </filter>
          <linearGradient id="network-link" x1="0" x2="1">
            <stop offset="0" stopColor="#81a1c1" stopOpacity=".34" />
            <stop offset="1" stopColor="#88c0d0" stopOpacity=".78" />
          </linearGradient>
        </defs>

        <g className="network-links">
          {networkLinks.map((link, index) => {
            const path = linkPath(link.source, link.target);
            return (
              <g key={`${link.source}-${link.target}`}>
                <path d={path} className="network-link-halo" />
                <path d={path} className="network-link" />
                <circle r="3.5" className="data-packet" style={{ animationDelay: `${index * -0.38}s` }}>
                  <animateMotion dur={`${2.2 + (index % 4) * 0.32}s`} repeatCount="indefinite" path={path} />
                </circle>
              </g>
            );
          })}
        </g>

        {networkNodes.map((node) => {
          const isSelected = selectedNode === node.id;
          const statusPulse = Math.max(0, Math.min(4, (tick + node.rate) % 5));
          return (
            <g
              key={node.id}
              className={`graph-node ${node.kind} ${isSelected ? "selected" : ""}`}
              transform={`translate(${node.x} ${node.y})`}
              onClick={() => onSelectNode(node.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelectNode(node.id);
              }}
              aria-label={`Select ${node.label}, ${node.role}`}
            >
              <rect width="116" height="56" rx="10" className="node-shell" filter="url(#node-shadow)" />
              <circle cx="18" cy="19" r="9" className="node-icon-bg" />
              <text x="18" y="22.5" textAnchor="middle" className="node-icon-text">
                {node.kind === "raspberry" ? "π" : node.kind === "jetson" ? "J" : "M"}
              </text>
              <text x="33" y="20" className="node-label">{node.label}</text>
              <text x="12" y="40" className="node-role">{node.role}</text>
              <circle cx="104" cy="12" r={3 + statusPulse * 0.15} className="node-status" />
            </g>
          );
        })}
      </svg>

      <div className="selected-node-detail">
        <div className={`device-icon ${selected.kind}`}>
          {selected.kind === "raspberry" ? <Cpu size={17} /> : selected.kind === "jetson" ? <Server size={17} /> : <Radio size={17} />}
        </div>
        <div>
          <strong>{selected.label}</strong>
          <span>{selected.sensor}</span>
        </div>
        <dl>
          <div><dt>Health</dt><dd>{selected.health}%</dd></div>
          <div><dt>Rate</dt><dd>{selected.rate + (tick % 3)} Hz</dd></div>
          <div><dt>Address</dt><dd>{selected.ip}</dd></div>
        </dl>
      </div>
    </div>
  );
}
