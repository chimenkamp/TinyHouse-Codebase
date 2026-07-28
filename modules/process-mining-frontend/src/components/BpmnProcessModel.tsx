import { useEffect, useRef, useState } from "react";
import { Clock3, Crosshair, Maximize2, Minus, MousePointer2, Plus, Route, Sparkles, TimerReset } from "lucide-react";
import Viewer from "bpmn-js/lib/Viewer";
import "bpmn-js/dist/assets/diagram-js.css";
import "bpmn-js/dist/assets/bpmn-font/css/bpmn.css";
import { productionProcessBpmn } from "../data/processModel";

interface BpmnProcessModelProps {
  tick: number;
}

const simulatedPath = [
  "StartEvent_Order",
  "Task_Print",
  "Task_Remove",
  "Task_Pick",
  "Task_Color",
  "Gateway_Color",
  "Task_Store",
  "Event_Demand",
  "Task_Retrieve",
  "Task_Surface",
  "Task_Human",
  "EndEvent_Complete",
];

const elementDetails: Record<string, { label: string; type: string; median: string; source: string }> = {
  StartEvent_Order: { label: "Part order received", type: "Start event", median: "—", source: "Production order" },
  Task_Print: { label: "Print part", type: "Automated activity", median: "8m 42s", source: "EMQX001" },
  Task_Remove: { label: "Remove from print bed", type: "Manual activity", median: "34s", source: "EMQX001 + JETSON-01" },
  Task_Pick: { label: "Robot picks part", type: "Service activity", median: "12s", source: "EMQX002" },
  Task_Color: { label: "Check color", type: "Inspection activity", median: "8s", source: "EMQX003 + JETSON-01" },
  Gateway_Color: { label: "Color accepted?", type: "Exclusive gateway", median: "96.2% accepted", source: "Vision classification" },
  Task_Recheck: { label: "Calibrate & recheck", type: "Rework activity", median: "41s", source: "EMQX003" },
  Task_Store: { label: "Store in drawer", type: "Service activity", median: "17s", source: "EMQX004" },
  Event_Demand: { label: "Work request", type: "Message event", median: "6m 14s", source: "Production queue" },
  Task_Retrieve: { label: "Retrieve from drawer", type: "Manual activity", median: "22s", source: "EMQX004" },
  Task_Surface: { label: "Place on work surface", type: "Observed activity", median: "11s", source: "EMQX005" },
  Task_Human: { label: "Human interaction", type: "User activity", median: "3m 18s", source: "EMQX005 + JETSON-02" },
  EndEvent_Complete: { label: "Part completed", type: "End event", median: "—", source: "Case lifecycle" },
};

export function BpmnProcessModel({ tick }: BpmnProcessModelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const selectedMarkerRef = useRef<string | null>(null);
  const activeMarkerRef = useRef<string | null>(null);
  const [selectedId, setSelectedId] = useState("Task_Color");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    const viewer = new Viewer({ container: containerRef.current });
    viewerRef.current = viewer;

    viewer.importXML(productionProcessBpmn).then(() => {
      if (cancelled) return;
      const canvas = viewer.get("canvas") as any;
      const eventBus = viewer.get("eventBus") as any;
      canvas.zoom("fit-viewport");
      canvas.addMarker("Task_Recheck", "bpmn-rework");
      canvas.addMarker("Event_Demand", "bpmn-waiting");
      canvas.addMarker("Task_Color", "bpmn-selected");
      selectedMarkerRef.current = "Task_Color";

      eventBus.on("element.click", (event: any) => {
        const id = event.element?.id;
        if (!id || id.startsWith("Flow_") || id === "Process_Production") return;
        if (selectedMarkerRef.current) canvas.removeMarker(selectedMarkerRef.current, "bpmn-selected");
        canvas.addMarker(id, "bpmn-selected");
        selectedMarkerRef.current = id;
        setSelectedId(id);
      });
      setReady(true);
    }).catch((reason: Error) => {
      if (!cancelled) setError(reason.message);
    });

    return () => {
      cancelled = true;
      viewer.destroy();
      if (viewerRef.current === viewer) viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !viewerRef.current) return;
    const canvas = viewerRef.current.get("canvas") as any;
    if (activeMarkerRef.current) canvas.removeMarker(activeMarkerRef.current, "bpmn-active");
    const next = simulatedPath[tick % simulatedPath.length];
    canvas.addMarker(next, "bpmn-active");
    activeMarkerRef.current = next;
  }, [ready, tick]);

  const zoom = (factor: number) => {
    const canvas = viewerRef.current?.get("canvas") as any;
    if (!canvas) return;
    const current = Number(canvas.zoom()) || 1;
    canvas.zoom(Math.max(0.35, Math.min(2.2, current * factor)));
  };

  const fit = () => {
    const canvas = viewerRef.current?.get("canvas") as any;
    canvas?.zoom("fit-viewport");
  };

  const detail = elementDetails[selectedId] ?? { label: selectedId, type: "BPMN element", median: "—", source: "Discovered event log" };

  return (
    <div className="bpmn-layout">
      <div className="bpmn-canvas-panel">
        <div className="bpmn-toolbar">
          <div className="bpmn-legend">
            <span><i className="observed" /> Discovered path</span>
            <span><i className="active" /> Live token</span>
            <span><i className="rework" /> Rework variant</span>
          </div>
          <div className="canvas-actions">
            <button type="button" onClick={() => zoom(1 / 1.18)} aria-label="Zoom out"><Minus size={15} /></button>
            <button type="button" onClick={() => zoom(1.18)} aria-label="Zoom in"><Plus size={15} /></button>
            <button type="button" onClick={fit} aria-label="Fit BPMN model"><Maximize2 size={15} /><span>Fit</span></button>
          </div>
        </div>
        <div className="bpmn-stage">
          {!ready && !error && <div className="bpmn-loading"><i /><span>Discovering process model…</span></div>}
          {error && <div className="bpmn-error">Could not render BPMN: {error}</div>}
          <div ref={containerRef} className="bpmn-canvas" />
          <div className="canvas-hint"><MousePointer2 size={13} /> Select an activity to inspect evidence</div>
        </div>
      </div>

      <aside className="model-insights">
        <div className="selected-element-card">
          <span className="eyebrow">Selected model element</span>
          <div className="selected-element-title"><i><Crosshair size={18} /></i><div><h3>{detail.label}</h3><span>{detail.type}</span></div></div>
          <dl>
            <div><dt><Clock3 size={14} /> Median</dt><dd>{detail.median}</dd></div>
            <div><dt><Sparkles size={14} /> Evidence</dt><dd>{detail.source}</dd></div>
          </dl>
        </div>

        <div className="model-stat-grid">
          <div><Route size={16} /><span>Variants</span><strong>3</strong><small>V1 covers 89.4%</small></div>
          <div><TimerReset size={16} /><span>Cycle time</span><strong>24m 18s</strong><small>↓ 6.8% this shift</small></div>
        </div>

        <div className="variant-list">
          <div className="variant-heading"><strong>Variant distribution</strong><span>Last 7 days</span></div>
          <div className="variant-row"><span><i className="v1" /> Standard flow</span><strong>89.4%</strong><div><i style={{ width: "89.4%" }} /></div></div>
          <div className="variant-row"><span><i className="v2" /> Color recheck</span><strong>7.8%</strong><div><i style={{ width: "7.8%" }} /></div></div>
          <div className="variant-row"><span><i className="v3" /> Manual recovery</span><strong>2.8%</strong><div><i style={{ width: "2.8%" }} /></div></div>
        </div>

        <div className="bottleneck-note">
          <i><Clock3 size={15} /></i>
          <div><strong>Potential wait-state bottleneck</strong><span>Drawer dwell contributes 25.6% of total cycle time.</span></div>
        </div>
      </aside>
    </div>
  );
}
