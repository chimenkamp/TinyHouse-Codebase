import { useEffect, useMemo, useRef, useState, type MutableRefObject, type PointerEvent } from "react";
import type { ColorLabel, ColorPickerRoi, ColorSample, MovementGraph, MovementGraphNode, MovementGraphNodeType } from "../lib/types";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

const COLOR_LABELS: ColorLabel[] = ["red", "green", "blue", "yellow", "black", "white", "unknown"];

type DragState = {
  nodeId: string;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
};

function formatColor(sample: ColorSample | undefined): string {
  if (!sample) return "unknown";
  return `${sample.label} · rgb(${sample.r}, ${sample.g}, ${sample.b})`;
}

function colorHex(sample: ColorSample | undefined): string {
  if (!sample) return "#58616d";
  return `#${[sample.r, sample.g, sample.b].map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function labelColor(r: number, g: number, b: number): ColorLabel {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (max < 45) return "black";
  if (min > 205 && delta < 35) return "white";
  if (delta < 35) return "unknown";
  if (r > 145 && g > 115 && b < 95) return "yellow";
  if (r === max && r > g * 1.25 && r > b * 1.25) return "red";
  if (g === max && g > r * 1.15 && g > b * 1.15) return "green";
  if (b === max && b > r * 1.15 && b > g * 1.15) return "blue";
  return "unknown";
}

function nodeTitle(type: MovementGraphNodeType): string {
  switch (type) {
    case "start":
      return "Start";
    case "position":
      return "Position Node";
    case "movementOrder":
      return "Movement Order Node";
    case "camera":
      return "Camera Node";
    case "colorPicker":
      return "Color Picker Node";
    case "conditional":
      return "Conditional Node";
  }
}

function connectedNodeId(graph: MovementGraph, nodeId: string, branch?: ColorLabel | "default"): string {
  return graph.edges.find((edge) => edge.fromNodeId === nodeId && (edge.branch ?? "default") === (branch ?? "default"))?.toNodeId ?? "";
}

function TargetSelect({
  graph,
  fromNode,
  branch
}: {
  graph: MovementGraph;
  fromNode: MovementGraphNode;
  branch?: ColorLabel | "default";
}) {
  const connectGraphNodes = useDigitalTwinStore((state) => state.connectGraphNodes);
  return (
    <select
      value={connectedNodeId(graph, fromNode.id, branch)}
      onChange={(event) => connectGraphNodes(graph.id, fromNode.id, event.target.value || null, branch)}
    >
      <option value="">End program</option>
      {graph.nodes.filter((node) => node.id !== fromNode.id).map((node) => (
        <option key={node.id} value={node.id}>{node.label}</option>
      ))}
    </select>
  );
}

export function NodeEditor() {
  const [newGraphName, setNewGraphName] = useState("");
  const [drag, setDrag] = useState<DragState | null>(null);
  const [cameraMessages, setCameraMessages] = useState<Record<string, string>>({});
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({});
  const streams = useRef<Record<string, MediaStream | null>>({});

  const savedPositions = useDigitalTwinStore((state) => state.savedPositions);
  const movementOrders = useDigitalTwinStore((state) => state.movementOrders);
  const movementGraphs = useDigitalTwinStore((state) => state.movementGraphs);
  const selectedGraphId = useDigitalTwinStore((state) => state.selectedGraphId);
  const executionState = useDigitalTwinStore((state) => state.executionState);
  const cameraStatus = useDigitalTwinStore((state) => state.cameraStatus);
  const createMovementGraph = useDigitalTwinStore((state) => state.createMovementGraph);
  const selectMovementGraph = useDigitalTwinStore((state) => state.selectMovementGraph);
  const updateMovementGraph = useDigitalTwinStore((state) => state.updateMovementGraph);
  const duplicateMovementGraph = useDigitalTwinStore((state) => state.duplicateMovementGraph);
  const deleteMovementGraph = useDigitalTwinStore((state) => state.deleteMovementGraph);
  const addGraphNode = useDigitalTwinStore((state) => state.addGraphNode);
  const updateGraphNode = useDigitalTwinStore((state) => state.updateGraphNode);
  const deleteGraphNode = useDigitalTwinStore((state) => state.deleteGraphNode);
  const validateMovementGraph = useDigitalTwinStore((state) => state.validateMovementGraph);
  const simulateMovementGraph = useDigitalTwinStore((state) => state.simulateMovementGraph);
  const executeMovementGraph = useDigitalTwinStore((state) => state.executeMovementGraph);
  const setGraphColorSample = useDigitalTwinStore((state) => state.setGraphColorSample);
  const setCameraStatus = useDigitalTwinStore((state) => state.setCameraStatus);
  const pauseExecution = useDigitalTwinStore((state) => state.pauseExecution);
  const resumeExecution = useDigitalTwinStore((state) => state.resumeExecution);
  const stopExecution = useDigitalTwinStore((state) => state.stopExecution);

  const graph = movementGraphs.find((candidate) => candidate.id === selectedGraphId) ?? null;
  const validation = graph ? validateMovementGraph(graph.id) : { valid: false, errors: ["Create or select a graph"] };
  const cameraNodes = useMemo(() => graph?.nodes.filter((node) => node.type === "camera") ?? [], [graph]);

  useEffect(() => {
    return () => {
      Object.values(streams.current).forEach((stream) => stream?.getTracks().forEach((track) => track.stop()));
    };
  }, []);

  const createGraph = () => {
    const id = createMovementGraph(newGraphName);
    setNewGraphName("");
    selectMovementGraph(id);
  };

  const startCamera = async (nodeId: string) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraMessages((current) => ({ ...current, [nodeId]: "Camera API unavailable" }));
      setCameraStatus("missing");
      return;
    }
    try {
      streams.current[nodeId]?.getTracks().forEach((track) => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streams.current[nodeId] = stream;
      const video = videoRefs.current[nodeId];
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      setCameraMessages((current) => ({ ...current, [nodeId]: "Camera ready" }));
      setCameraStatus("ready");
    } catch (error) {
      setCameraMessages((current) => ({ ...current, [nodeId]: `Camera failed: ${String(error)}` }));
      setCameraStatus("error");
    }
  };

  const stopCamera = (nodeId: string) => {
    streams.current[nodeId]?.getTracks().forEach((track) => track.stop());
    streams.current[nodeId] = null;
    const video = videoRefs.current[nodeId];
    if (video) video.srcObject = null;
    setCameraMessages((current) => ({ ...current, [nodeId]: "Camera stopped" }));
    setCameraStatus("idle");
  };

  const sampleColor = (node: MovementGraphNode) => {
    if (!graph) return;
    const sourceNodeId = node.sourceNodeId || cameraNodes[0]?.id;
    const video = sourceNodeId ? videoRefs.current[sourceNodeId] : null;
    if (!video || !video.videoWidth || !video.videoHeight) {
      const sample: ColorSample = { r: 0, g: 0, b: 0, label: "unknown", sampledAt: new Date().toISOString() };
      setGraphColorSample(graph.id, node.id, sample);
      return;
    }
    const roi = node.roi ?? { x: 35, y: 35, width: 30, height: 30 };
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const x = Math.floor((roi.x / 100) * canvas.width);
    const y = Math.floor((roi.y / 100) * canvas.height);
    const width = Math.max(1, Math.floor((roi.width / 100) * canvas.width));
    const height = Math.max(1, Math.floor((roi.height / 100) * canvas.height));
    const data = ctx.getImageData(x, y, Math.min(width, canvas.width - x), Math.min(height, canvas.height - y)).data;
    let r = 0;
    let g = 0;
    let b = 0;
    let count = 0;
    for (let i = 0; i < data.length; i += 16) {
      r += data[i];
      g += data[i + 1];
      b += data[i + 2];
      count += 1;
    }
    const sampleR = Math.round(r / Math.max(1, count));
    const sampleG = Math.round(g / Math.max(1, count));
    const sampleB = Math.round(b / Math.max(1, count));
    setGraphColorSample(graph.id, node.id, {
      r: sampleR,
      g: sampleG,
      b: sampleB,
      label: labelColor(sampleR, sampleG, sampleB),
      sampledAt: new Date().toISOString()
    });
  };

  const confirmAndExecute = () => {
    if (!graph) return;
    const ok = window.confirm(`Run graph "${graph.name}" on the real PAROL6 arm? Conditional branches will move the physical robot.`);
    if (ok) void executeMovementGraph(graph.id);
  };

  const onCanvasPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag || !graph) return;
    updateGraphNode(graph.id, drag.nodeId, {
      x: Math.max(0, drag.originX + event.clientX - drag.startX),
      y: Math.max(0, drag.originY + event.clientY - drag.startY)
    });
  };

  const nodeCenter = (node: MovementGraphNode) => ({ x: node.x + 88, y: node.y + 42 });

  return (
    <>
      <section className="panel">
        <h2>Conditional Graph Editor</h2>
        <div className="stack">
          <div className="inputLine">
            <input
              type="text"
              value={newGraphName}
              placeholder={`Movement Graph ${movementGraphs.length + 1}`}
              onChange={(event) => setNewGraphName(event.target.value)}
            />
            <button className="primary" onClick={createGraph}>New</button>
          </div>
          <select value={selectedGraphId ?? ""} onChange={(event) => selectMovementGraph(event.target.value || null)}>
            <option value="">Select a graph</option>
            {movementGraphs.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{candidate.name}</option>
            ))}
          </select>
        </div>
      </section>

      {graph ? (
        <>
          <section className="panel">
            <div className="panelHeader">
              <h2>Graph Controls</h2>
              <span className={validation.valid ? "modePill ok" : "modePill warn"}>{validation.valid ? "Valid" : "Needs work"}</span>
            </div>
            <div className="stack">
              <input
                type="text"
                value={graph.name}
                onChange={(event) => updateMovementGraph(graph.id, { name: event.target.value })}
              />
              <textarea
                value={graph.description ?? ""}
                placeholder="Graph description"
                onChange={(event) => updateMovementGraph(graph.id, { description: event.target.value })}
              />
              <div className="nodeButtonGrid">
                {(["position", "movementOrder", "camera", "colorPicker", "conditional"] as MovementGraphNodeType[]).map((type) => (
                  <button key={type} onClick={() => addGraphNode(graph.id, type)}>{nodeTitle(type)}</button>
                ))}
              </div>
              {!validation.valid ? (
                <div className="validationBox">
                  {validation.errors.slice(0, 6).map((error) => <div key={error}>{error}</div>)}
                </div>
              ) : null}
              <div className="buttonGrid">
                <button onClick={() => void simulateMovementGraph(graph.id)}>Simulate Graph</button>
                <button className="danger" onClick={confirmAndExecute} disabled={!validation.valid}>Run Real Arm</button>
                <button onClick={() => duplicateMovementGraph(graph.id)}>Duplicate</button>
                <button className="danger" onClick={() => deleteMovementGraph(graph.id)}>Delete</button>
              </div>
              <div className="buttonRow">
                <button onClick={pauseExecution} disabled={executionState.mode !== "simulating" && executionState.mode !== "executing"}>Pause</button>
                <button onClick={resumeExecution} disabled={executionState.mode !== "paused"}>Resume</button>
                <button className="danger" onClick={stopExecution} disabled={executionState.mode === "idle"}>Stop</button>
              </div>
              <span className="mutedLine">Camera status: {cameraStatus}</span>
            </div>
          </section>

          <section className="graphWorkspace">
            <div
              className="graphCanvas"
              onPointerMove={onCanvasPointerMove}
              onPointerUp={() => setDrag(null)}
              onPointerLeave={() => setDrag(null)}
            >
              <svg className="edgeLayer" width="100%" height="100%">
                <defs>
                  <marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L7,3 z" fill="#7f95a8" />
                  </marker>
                </defs>
                {graph.edges.map((edge) => {
                  const from = graph.nodes.find((node) => node.id === edge.fromNodeId);
                  const to = graph.nodes.find((node) => node.id === edge.toNodeId);
                  if (!from || !to) return null;
                  const a = nodeCenter(from);
                  const b = nodeCenter(to);
                  return (
                    <g key={edge.id}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} markerEnd="url(#arrow)" />
                      {edge.branch ? <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 5}>{edge.branch}</text> : null}
                    </g>
                  );
                })}
              </svg>
              {graph.nodes.map((node) => (
                <div
                  key={node.id}
                  className={executionState.activeNodeId === node.id ? "graphNode active" : "graphNode"}
                  style={{ left: node.x, top: node.y }}
                >
                  <div
                    className="nodeDrag"
                    onPointerDown={(event) => {
                      setDrag({
                        nodeId: node.id,
                        startX: event.clientX,
                        startY: event.clientY,
                        originX: node.x,
                        originY: node.y
                      });
                    }}
                  >
                    <strong>{node.label}</strong>
                    <span>{nodeTitle(node.type)}</span>
                  </div>
                  {node.type !== "start" ? (
                    <input
                      type="text"
                      value={node.label}
                      onChange={(event) => updateGraphNode(graph.id, node.id, { label: event.target.value })}
                    />
                  ) : null}
                  <NodeBody
                    graph={graph}
                    node={node}
                    savedPositions={savedPositions}
                    movementOrders={movementOrders}
                    cameraNodes={cameraNodes}
                    cameraMessages={cameraMessages}
                    videoRefs={videoRefs}
                    updateGraphNode={updateGraphNode}
                    deleteGraphNode={deleteGraphNode}
                    startCamera={startCamera}
                    stopCamera={stopCamera}
                    sampleColor={sampleColor}
                  />
                </div>
              ))}
            </div>
          </section>
        </>
      ) : <section className="panel"><div className="emptyState">Create a graph to start composing conditional movement logic.</div></section>}
    </>
  );
}

function NodeBody({
  graph,
  node,
  savedPositions,
  movementOrders,
  cameraNodes,
  cameraMessages,
  videoRefs,
  updateGraphNode,
  deleteGraphNode,
  startCamera,
  stopCamera,
  sampleColor
}: {
  graph: MovementGraph;
  node: MovementGraphNode;
  savedPositions: Array<{ id: string; name: string; jointValues: number[] }>;
  movementOrders: Array<{ id: string; name: string; steps: unknown[] }>;
  cameraNodes: MovementGraphNode[];
  cameraMessages: Record<string, string>;
  videoRefs: MutableRefObject<Record<string, HTMLVideoElement | null>>;
  updateGraphNode: (graphId: string, nodeId: string, patch: Partial<MovementGraphNode>) => void;
  deleteGraphNode: (graphId: string, nodeId: string) => void;
  startCamera: (nodeId: string) => Promise<void>;
  stopCamera: (nodeId: string) => void;
  sampleColor: (node: MovementGraphNode) => void;
}) {
  if (node.type === "start") {
    return (
      <label>
        <span>Next</span>
        <TargetSelect graph={graph} fromNode={node} />
      </label>
    );
  }

  return (
    <>
      {node.type === "position" ? (
        <>
          <label>
            <span>Saved position</span>
            <select value={node.positionId ?? ""} onChange={(event) => updateGraphNode(graph.id, node.id, { positionId: event.target.value || undefined })}>
              <option value="">Select position</option>
              {savedPositions.map((position) => (
                <option key={position.id} value={position.id}>{position.name}</option>
              ))}
            </select>
          </label>
          <code>{savedPositions.find((position) => position.id === node.positionId)?.jointValues.map((angle) => angle.toFixed(1)).join(", ") ?? "No pose selected"}</code>
          <label>
            <span>Next</span>
            <TargetSelect graph={graph} fromNode={node} />
          </label>
        </>
      ) : null}

      {node.type === "movementOrder" ? (
        <>
          <label>
            <span>Movement order</span>
            <select value={node.orderId ?? ""} onChange={(event) => updateGraphNode(graph.id, node.id, { orderId: event.target.value || undefined })}>
              <option value="">Select order</option>
              {movementOrders.map((order) => (
                <option key={order.id} value={order.id}>{order.name} ({order.steps.length})</option>
              ))}
            </select>
          </label>
          <label>
            <span>Next</span>
            <TargetSelect graph={graph} fromNode={node} />
          </label>
        </>
      ) : null}

      {node.type === "camera" ? (
        <>
          <video
            ref={(element) => {
              videoRefs.current[node.id] = element;
            }}
            muted
            playsInline
            className="cameraPreview"
          />
          <span className="mutedLine">{cameraMessages[node.id] ?? "Camera idle"}</span>
          <div className="buttonRow">
            <button onClick={() => void startCamera(node.id)}>Start</button>
            <button onClick={() => stopCamera(node.id)}>Stop</button>
          </div>
          <label>
            <span>Next</span>
            <TargetSelect graph={graph} fromNode={node} />
          </label>
        </>
      ) : null}

      {node.type === "colorPicker" ? (
        <>
          <label>
            <span>Camera source</span>
            <select value={node.sourceNodeId ?? ""} onChange={(event) => updateGraphNode(graph.id, node.id, { sourceNodeId: event.target.value || undefined })}>
              <option value="">Select camera</option>
              {cameraNodes.map((camera) => (
                <option key={camera.id} value={camera.id}>{camera.label}</option>
              ))}
            </select>
          </label>
          <RoiControls
            roi={node.roi ?? { x: 35, y: 35, width: 30, height: 30 }}
            onChange={(roi) => updateGraphNode(graph.id, node.id, { roi })}
          />
          <div className="colorReadout">
            <span style={{ background: colorHex(node.detectedColor) }} />
            <code>{formatColor(node.detectedColor)}</code>
          </div>
          <button onClick={() => sampleColor(node)}>Sample ROI</button>
          <label>
            <span>Next</span>
            <TargetSelect graph={graph} fromNode={node} />
          </label>
        </>
      ) : null}

      {node.type === "conditional" ? (
        <>
          {(node.branches?.length ? node.branches : ["red", "blue", "unknown"] as ColorLabel[]).map((branch) => (
            <label key={branch}>
              <span>If {branch}</span>
              <TargetSelect graph={graph} fromNode={node} branch={branch} />
            </label>
          ))}
          <label>
            <span>Otherwise</span>
            <TargetSelect graph={graph} fromNode={node} branch="default" />
          </label>
          <div className="chipRow">
            {COLOR_LABELS.map((label) => (
              <button
                key={label}
                className={node.branches?.includes(label) ? "active" : ""}
                onClick={() => {
                  const branches = new Set(node.branches?.length ? node.branches : ["red", "blue", "unknown"] as ColorLabel[]);
                  if (branches.has(label)) branches.delete(label);
                  else branches.add(label);
                  updateGraphNode(graph.id, node.id, { branches: Array.from(branches) });
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </>
      ) : null}

      <button className="danger" onClick={() => deleteGraphNode(graph.id, node.id)}>Delete Node</button>
    </>
  );
}

function RoiControls({ roi, onChange }: { roi: ColorPickerRoi; onChange: (roi: ColorPickerRoi) => void }) {
  const setValue = (key: keyof ColorPickerRoi, value: number) => {
    onChange({
      ...roi,
      [key]: Math.min(Math.max(value, key === "width" || key === "height" ? 1 : 0), 100)
    });
  };
  return (
    <div className="roiGrid">
      {(["x", "y", "width", "height"] as Array<keyof ColorPickerRoi>).map((key) => (
        <label key={key}>
          <span>{key}</span>
          <input
            type="number"
            min={key === "width" || key === "height" ? 1 : 0}
            max="100"
            value={roi[key]}
            onChange={(event) => setValue(key, Number(event.target.value))}
          />
        </label>
      ))}
    </div>
  );
}
