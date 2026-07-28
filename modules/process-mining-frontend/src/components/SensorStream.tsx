import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, ShieldCheck, SlidersHorizontal, Sparkles } from "lucide-react";
import { networkNodes } from "../data/mockData";
import {
  defaultSensorProfile,
  facilityGuards,
  sensorProfiles,
  type SensorChannel,
} from "../data/sensorProfiles";

interface SensorStreamProps {
  selectedNode: string;
  tick: number;
}

interface StreamPoint {
  index: number;
  raw: number;
  clean: number;
}

const sampleCount = 46;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function semanticValue(metric: SensorChannel, index: number, tick: number, seed: number) {
  const guardSpan = Math.max(0.01, metric.guard.max - metric.guard.min);
  const phase = index + tick * 0.24 + seed;
  const fine = Math.sin(phase * 1.73) * guardSpan * 0.012;
  let value = metric.baseline;

  switch (metric.pattern) {
    case "steady":
      value += Math.sin(phase * 0.23) * guardSpan * 0.055 + fine;
      break;
    case "cyclic":
      value += Math.sin(phase * 0.54) * guardSpan * 0.23 + Math.sin(phase * 1.4) * guardSpan * 0.035;
      break;
    case "pulse": {
      const impulse = Math.pow(Math.max(0, Math.sin(phase * 0.38)), 9);
      value += impulse * guardSpan * 0.48 + fine;
      break;
    }
    case "step": {
      const active = Math.floor(phase / 9) % 2 === 0;
      value += active ? guardSpan * 0.18 : -guardSpan * 0.1;
      value += fine;
      break;
    }
    case "ramp": {
      const progress = ((phase % 20) + 20) % 20 / 20;
      value += (progress - 0.5) * guardSpan * 0.42 + fine;
      break;
    }
    case "binary": {
      const active = ((phase % 18) + 18) % 18 < 13;
      value = active ? metric.guard.max : metric.guard.min;
      break;
    }
  }

  const margin = metric.pattern === "binary" ? 0 : guardSpan * 0.025;
  return clamp(value, metric.guard.min + margin, metric.guard.max - margin);
}

function makeSeries(metric: SensorChannel, tick: number, seed: number): StreamPoint[] {
  const outlierIndex = sampleCount - 12;
  return Array.from({ length: sampleCount }, (_, index) => {
    const normalValue = semanticValue(metric, index, tick, seed);
    if (index !== outlierIndex) {
      const clean = metric.pattern === "binary"
        ? normalValue
        : metric.baseline + (normalValue - metric.baseline) * 0.86;
      return { index, raw: normalValue, clean };
    }

    const clean = clamp(metric.context.anomalyValue, metric.guard.min, metric.guard.max);
    return { index, raw: metric.context.anomalyValue, clean };
  });
}

function linePath(values: number[], metric: SensorChannel, width: number, height: number) {
  const left = 48;
  const right = width - 18;
  const top = 16;
  const bottom = height - 28;
  return values.map((value, index) => {
    const x = left + (index / (values.length - 1)) * (right - left);
    const y = top + (1 - (value - metric.min) / (metric.max - metric.min)) * (bottom - top);
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
}

function formatValue(metric: SensorChannel, value: number) {
  if (metric.id === "reed-state") return value >= 0.5 ? "Closed" : "Open";
  return `${value.toFixed(metric.decimals)} ${metric.unit}`;
}

function formatGuardBoundary(metric: SensorChannel, value: number) {
  if (metric.id === "reed-state") return value === 0 ? "Open" : "Closed";
  return value.toFixed(metric.decimals);
}

export function StreamBridge() {
  return (
    <div className="stream-bridge" aria-label="Animated MQTT streams entering preprocessing">
      <span className="bridge-label">MQTT / QoS 1</span>
      {[0, 1, 2, 3, 4].map((line) => (
        <i key={line} style={{ top: `${31 + line * 9}%`, animationDelay: `${line * -0.34}s` }} />
      ))}
      <div className="bridge-arrow"><ArrowRight size={16} /></div>
    </div>
  );
}

export function SensorStream({ selectedNode, tick }: SensorStreamProps) {
  const profile = sensorProfiles[selectedNode] ?? defaultSensorProfile;
  const [metricId, setMetricId] = useState(profile.channels[0].id);
  const metric = profile.channels.find((channel) => channel.id === metricId) ?? profile.channels[0];
  const selected = networkNodes.find((node) => node.id === selectedNode) ?? networkNodes[0];
  const seed = selected.label.split("").reduce((sum, character) => sum + character.charCodeAt(0), 0) % 17;
  const series = useMemo(() => makeSeries(metric, tick, seed), [metric, tick, seed]);

  useEffect(() => {
    setMetricId(profile.channels[0].id);
  }, [profile]);

  const width = 760;
  const height = 244;
  const plotLeft = 48;
  const plotRight = width - 18;
  const plotTop = 16;
  const plotBottom = height - 28;
  const yFor = (value: number) => plotTop + (1 - (value - metric.min) / (metric.max - metric.min)) * (plotBottom - plotTop);
  const rawPath = linePath(series.map((point) => point.raw), metric, width, height);
  const cleanPath = linePath(series.map((point) => point.clean), metric, width, height);
  const guardUpperY = yFor(metric.guard.max);
  const guardLowerY = yFor(metric.guard.min);
  const outlier = series[sampleCount - 12];
  const outlierX = plotLeft + (outlier.index / (series.length - 1)) * (plotRight - plotLeft);
  const outlierY = yFor(outlier.raw);
  const currentValue = series[series.length - 1].raw;
  const currentInGuard = currentValue >= metric.guard.min && currentValue <= metric.guard.max;
  const gradientId = `raw-area-${selectedNode.replace(/[^a-z0-9]/gi, "")}`;

  return (
    <div className="sensor-stream">
      <div className="chart-controls">
        <div className="metric-tabs" role="tablist" aria-label={`${selected.label} sensor channels`}>
          {profile.channels.map((channel) => (
            <button key={channel.id} className={metric.id === channel.id ? "active" : ""} onClick={() => setMetricId(channel.id)} type="button">
              {channel.label}
            </button>
          ))}
        </div>
        <div className="live-value"><i /> {selected.label} <strong>{formatValue(metric, currentValue)}</strong></div>
      </div>

      <div className="signal-semantics">
        <div><span>Signal meaning</span><strong>{metric.semantic}</strong></div>
        <div><span>Expected behavior</span><strong>{metric.behavior}</strong></div>
        <div className={currentInGuard ? "guard-valid" : "guard-warning"}>
          <ShieldCheck size={15} />
          <span>{metric.guard.label}</span>
          <strong>{formatGuardBoundary(metric, metric.guard.min)}–{formatGuardBoundary(metric, metric.guard.max)} {metric.unit === "state" ? "" : metric.unit}</strong>
        </div>
      </div>

      <div className="stream-chart-wrap">
        <svg className="stream-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`${metric.label} raw and context-aware signal with ${metric.guard.label}`}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={metric.color} stopOpacity=".2" />
              <stop offset="1" stopColor={metric.color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <rect x={plotLeft} y={guardUpperY} width={plotRight - plotLeft} height={guardLowerY - guardUpperY} className="guard-band" />
          {[0, 1, 2, 3, 4].map((line) => {
            const y = plotTop + line * ((plotBottom - plotTop) / 4);
            const value = metric.max - line * ((metric.max - metric.min) / 4);
            return (
              <g key={line}>
                <line x1={plotLeft} x2={plotRight} y1={y} y2={y} className="chart-grid-line" />
                <text x={plotLeft - 7} y={y + 3} textAnchor="end" className="y-axis-label">{value.toFixed(metric.decimals)}</text>
              </g>
            );
          })}
          <line x1={plotLeft} x2={plotRight} y1={guardUpperY} y2={guardUpperY} className="guard-limit" />
          <line x1={plotLeft} x2={plotRight} y1={guardLowerY} y2={guardLowerY} className="guard-limit" />
          <text x={plotRight - 3} y={Math.max(guardUpperY - 6, 10)} textAnchor="end" className="guard-label">{metric.guard.label} · {formatGuardBoundary(metric, metric.guard.min)}–{formatGuardBoundary(metric, metric.guard.max)} {metric.unit === "state" ? "" : metric.unit}</text>
          <path d={`${rawPath} L ${plotRight} ${plotBottom} L ${plotLeft} ${plotBottom} Z`} fill={`url(#${gradientId})`} />
          <path d={rawPath} className="raw-signal" style={{ stroke: metric.color }} />
          <path d={cleanPath} className="clean-signal" />
          <line x1={outlierX} x2={outlierX} y1={outlierY} y2={plotBottom} className="outlier-guide" />
          <circle cx={outlierX} cy={outlierY} r="9" className="outlier-ring" />
          <circle cx={outlierX} cy={outlierY} r="4" className="outlier-dot" />
          <text x={plotLeft} y={height - 6} className="axis-label">− 45 seconds</text>
          <text x={plotRight} y={height - 6} textAnchor="end" className="axis-label">now</text>
        </svg>
        <div className="chart-legend">
          <span><i className="raw" style={{ background: metric.color }} /> Raw</span>
          <span><i className="clean" /> Guard-aware signal</span>
          <span><i className="guard" /> Valid operating band</span>
          <span><i className="anomaly" /> Explained deviation</span>
        </div>
      </div>

      <div className="cause-card">
        <div className="cause-icon"><Sparkles size={17} /></div>
        <div className="cause-copy">
          <span className="eyebrow">Physical context · {metric.label}</span>
          <strong>{metric.context.cause}</strong>
          <p>{metric.context.evidence}</p>
        </div>
        <div className="cause-resolution">
          <CheckCircle2 size={15} />
          <span>{metric.context.action}</span>
        </div>
        <div className="next-anomaly"><SlidersHorizontal size={13} /> {profile.processContext}</div>
      </div>

      <div className="facility-guards">
        <div className="facility-guard-heading"><ShieldCheck size={14} /><span>Cross-cell guards</span><em>4/4 within range</em></div>
        <div className="facility-guard-list">
          {facilityGuards.map((guard, index) => {
            const value = guard.value + Math.sin((tick + index * 3) * 0.31) * (guard.max - guard.min) * 0.018;
            return (
              <div key={guard.id} className={guard.source === selected.label ? "selected" : ""}>
                <span>{guard.label} <small>{guard.source}</small></span>
                <strong>{value.toFixed(guard.unit === "°C" || guard.unit === "%RH" || guard.unit === "ΔE" ? 1 : 0)} {guard.unit}</strong>
                <em><i /> {guard.min}–{guard.max}</em>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
