import { create } from "zustand";
import { DigitalTwinApi } from "../lib/api";
import type {
  CartesianPose,
  ColorLabel,
  ColorPickerRoi,
  ColorSample,
  ExecutionState,
  InterpolationMode,
  GripperAction,
  JointLimit,
  ModelInfo,
  MovementGraph,
  MovementGraphEdge,
  MovementGraphNode,
  MovementGraphNodeType,
  MovementOrder,
  MovementStep,
  RobotStatus,
  SavedPosition
} from "../lib/types";

const HOME_PREVIEW = [0, 0, 0, 0, 0, 0];
const DEFAULT_POSE = [0, 0.2368, 0.334, Math.PI / 2, 0, Math.PI / 2];
const STORAGE_KEY = "parol6-digital-twin-programming/v1";

const DEFAULT_STEP: Omit<MovementStep, "id" | "positionId"> = {
  speed: 0.45,
  acceleration: 1,
  delayMs: 250,
  interpolation: "joint",
  gripperAction: "none"
};

const DEFAULT_ROI: ColorPickerRoi = {
  x: 35,
  y: 35,
  width: 30,
  height: 30
};

const DEFAULT_BRANCHES: ColorLabel[] = ["red", "blue", "unknown"];

const ID_PREFIX = "pgm";

type PersistedProgrammingState = {
  savedPositions: SavedPosition[];
  movementOrders: MovementOrder[];
  movementGraphs: MovementGraph[];
  selectedOrderId: string | null;
  selectedGraphId: string | null;
};

export type OrderValidation = {
  valid: boolean;
  errors: string[];
};

export type GraphValidation = {
  valid: boolean;
  errors: string[];
};

type DigitalTwinState = {
  model: ModelInfo | null;
  status: RobotStatus | null;
  previewAngles: number[];
  anchorPose: number[];
  anchorTransformMode: "translate" | "rotate";
  selectedJoint: string | null;
  speedScale: number;
  applyAnchorOnRelease: boolean;
  savedPositions: SavedPosition[];
  movementOrders: MovementOrder[];
  movementGraphs: MovementGraph[];
  selectedOrderId: string | null;
  selectedGraphId: string | null;
  executionState: ExecutionState;
  cameraStatus: "idle" | "ready" | "missing" | "error";
  log: string[];
  loading: boolean;
  error: string | null;
  loadModel: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  setPreviewAngles: (angles: number[]) => void;
  setJointPreview: (index: number, value: number) => void;
  setAnchorPose: (pose: number[]) => void;
  setAnchorRotationDeg: (axisIndex: number, valueDeg: number) => void;
  setAnchorTransformMode: (mode: "translate" | "rotate") => void;
  solveAnchorTarget: (pose?: number[]) => Promise<void>;
  moveToAnchor: (pose?: number[]) => Promise<void>;
  captureLivePosition: () => void;
  saveCurrentPosition: (name?: string, description?: string) => void;
  updateSavedPosition: (id: string, patch: Partial<Pick<SavedPosition, "name" | "description">>) => void;
  replaceSavedPositionWithCurrentPose: (id: string) => void;
  deleteSavedPosition: (id: string) => void;
  removeSavedPosition: (id: string) => void;
  loadSavedPosition: (id: string) => void;
  exportSavedPositions: () => string;
  setSelectedJoint: (name: string | null) => void;
  setSpeedScale: (value: number) => void;
  setApplyAnchorOnRelease: (enabled: boolean) => void;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  setLive: (live: boolean) => Promise<void>;
  setMovement: (enabled: boolean) => Promise<void>;
  home: () => Promise<void>;
  halt: () => Promise<void>;
  dispatchMove: () => Promise<void>;
  resetPreviewToTelemetry: () => void;
  createMovementOrder: (name?: string) => string;
  selectMovementOrder: (id: string | null) => void;
  updateMovementOrder: (id: string, patch: Partial<Pick<MovementOrder, "name" | "description">>) => void;
  duplicateMovementOrder: (id: string) => string | null;
  deleteMovementOrder: (id: string) => void;
  addPositionToOrder: (orderId: string, positionId: string) => void;
  removeStepFromOrder: (orderId: string, stepId: string) => void;
  reorderOrderStep: (orderId: string, stepId: string, targetIndex: number) => void;
  updateMovementStep: (orderId: string, stepId: string, patch: Partial<Omit<MovementStep, "id">>) => void;
  validateMovementOrder: (orderId: string) => OrderValidation;
  previewMovementStep: (orderId: string, stepIndex: number) => void;
  simulateMovementOrder: (orderId: string) => Promise<void>;
  executeMovementOrder: (orderId: string) => Promise<void>;
  createMovementGraph: (name?: string) => string;
  selectMovementGraph: (id: string | null) => void;
  updateMovementGraph: (id: string, patch: Partial<Pick<MovementGraph, "name" | "description">>) => void;
  duplicateMovementGraph: (id: string) => string | null;
  deleteMovementGraph: (id: string) => void;
  addGraphNode: (graphId: string, type: MovementGraphNodeType) => string | null;
  updateGraphNode: (graphId: string, nodeId: string, patch: Partial<MovementGraphNode>) => void;
  deleteGraphNode: (graphId: string, nodeId: string) => void;
  connectGraphNodes: (graphId: string, fromNodeId: string, toNodeId: string | null, branch?: ColorLabel | "default") => void;
  validateMovementGraph: (graphId: string) => GraphValidation;
  simulateMovementGraph: (graphId: string) => Promise<void>;
  executeMovementGraph: (graphId: string) => Promise<void>;
  setGraphColorSample: (graphId: string, nodeId: string, sample: ColorSample) => void;
  setCameraStatus: (status: DigitalTwinState["cameraStatus"]) => void;
  pauseExecution: () => void;
  resumeExecution: () => void;
  stopExecution: () => void;
};

function nowIso(): string {
  return new Date().toISOString();
}

function makeId(prefix = ID_PREFIX): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function poseArrayToCartesianPose(pose: number[] | undefined): CartesianPose | undefined {
  if (!pose || pose.length < 6) return undefined;
  return {
    x: Number(pose[0] ?? 0),
    y: Number(pose[1] ?? 0),
    z: Number(pose[2] ?? 0),
    rx: Number(pose[3] ?? 0),
    ry: Number(pose[4] ?? 0),
    rz: Number(pose[5] ?? 0)
  };
}

export function cartesianPoseToArray(pose: CartesianPose | undefined): number[] | undefined {
  if (!pose) return undefined;
  return [pose.x, pose.y, pose.z, pose.rx, pose.ry, pose.rz];
}

function appendLog(log: string[], message: string): string[] {
  return [`${new Date().toLocaleTimeString()} ${message}`, ...log].slice(0, 12);
}

function clampToLimits(angles: number[], limits: JointLimit[] | undefined): number[] {
  if (!limits) return angles.slice(0, 6);
  return angles.slice(0, 6).map((angle, index) => {
    const limit = limits[index];
    return Math.min(Math.max(Number(angle), limit.lower_deg), limit.upper_deg);
  });
}

function jointLimitErrors(angles: number[], limits: JointLimit[] | undefined, label: string): string[] {
  if (angles.length !== 6) return [`${label} must have 6 joint values`];
  if (!limits?.length) return [];
  const errors: string[] = [];
  angles.forEach((raw, index) => {
    const value = Number(raw);
    const limit = limits[index];
    if (!Number.isFinite(value)) {
      errors.push(`${label} ${limit?.name ?? index + 1} is not finite`);
    } else if (limit && (value < limit.lower_deg || value > limit.upper_deg)) {
      errors.push(`${label} ${limit.name} ${value.toFixed(2)} deg outside ${limit.lower_deg.toFixed(2)}..${limit.upper_deg.toFixed(2)}`);
    }
  });
  return errors;
}

function normalizePosition(raw: unknown, index: number): SavedPosition | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const jointValues = Array.isArray(record.jointValues)
    ? record.jointValues.map(Number).slice(0, 6)
    : Array.isArray(record.angles_deg)
      ? record.angles_deg.map(Number).slice(0, 6)
      : [];
  if (jointValues.length !== 6 || jointValues.some((value) => !Number.isFinite(value))) return null;
  const createdAt = typeof record.createdAt === "string" ? record.createdAt : nowIso();
  const updatedAt = typeof record.updatedAt === "string" ? record.updatedAt : createdAt;
  const poseArray = Array.isArray(record.pose_m_rad) ? record.pose_m_rad.map(Number) : undefined;
  const cartesianPose = record.cartesianPose && typeof record.cartesianPose === "object"
    ? record.cartesianPose as CartesianPose
    : poseArrayToCartesianPose(poseArray);
  return {
    id: typeof record.id === "string" ? record.id : makeId("pos"),
    name: typeof record.name === "string" && record.name.trim() ? record.name.trim() : `Position ${index + 1}`,
    jointValues,
    cartesianPose,
    description: typeof record.description === "string" ? record.description : "",
    source: record.source === "live" ? "live" : "simulated",
    createdAt,
    updatedAt
  };
}

function normalizeStep(raw: unknown): MovementStep | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (typeof record.positionId !== "string") return null;
  const interpolation = record.interpolation === "linear" ? "linear" : "joint";
  const gripperAction = record.gripperAction === "open" || record.gripperAction === "close" ? record.gripperAction : "none";
  return {
    id: typeof record.id === "string" ? record.id : makeId("step"),
    positionId: record.positionId,
    speed: clampNumber(Number(record.speed ?? DEFAULT_STEP.speed), 0.05, 1),
    acceleration: clampNumber(Number(record.acceleration ?? DEFAULT_STEP.acceleration), 0.1, 5),
    delayMs: clampNumber(Number(record.delayMs ?? DEFAULT_STEP.delayMs), 0, 60000),
    interpolation: interpolation as InterpolationMode,
    gripperAction: gripperAction as GripperAction
  };
}

function normalizeOrder(raw: unknown, index: number): MovementOrder | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const createdAt = typeof record.createdAt === "string" ? record.createdAt : nowIso();
  const updatedAt = typeof record.updatedAt === "string" ? record.updatedAt : createdAt;
  const steps = Array.isArray(record.steps) ? record.steps.map(normalizeStep).filter((step): step is MovementStep => Boolean(step)) : [];
  return {
    id: typeof record.id === "string" ? record.id : makeId("order"),
    name: typeof record.name === "string" && record.name.trim() ? record.name.trim() : `Movement Order ${index + 1}`,
    description: typeof record.description === "string" ? record.description : "",
    steps,
    createdAt,
    updatedAt
  };
}

function normalizeNode(raw: unknown): MovementGraphNode | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const type = record.type;
  if (type !== "start" && type !== "position" && type !== "movementOrder" && type !== "camera" && type !== "colorPicker" && type !== "conditional") {
    return null;
  }
  const node: MovementGraphNode = {
    id: typeof record.id === "string" ? record.id : makeId("node"),
    type,
    label: typeof record.label === "string" && record.label.trim() ? record.label.trim() : labelForNodeType(type),
    x: Number.isFinite(Number(record.x)) ? Number(record.x) : 24,
    y: Number.isFinite(Number(record.y)) ? Number(record.y) : 24
  };
  if (typeof record.positionId === "string") node.positionId = record.positionId;
  if (typeof record.orderId === "string") node.orderId = record.orderId;
  if (typeof record.sourceNodeId === "string") node.sourceNodeId = record.sourceNodeId;
  if (record.roi && typeof record.roi === "object") {
    const roi = record.roi as Record<string, unknown>;
    node.roi = {
      x: clampNumber(Number(roi.x ?? DEFAULT_ROI.x), 0, 100),
      y: clampNumber(Number(roi.y ?? DEFAULT_ROI.y), 0, 100),
      width: clampNumber(Number(roi.width ?? DEFAULT_ROI.width), 1, 100),
      height: clampNumber(Number(roi.height ?? DEFAULT_ROI.height), 1, 100)
    };
  }
  if (Array.isArray(record.branches)) {
    node.branches = record.branches.filter(isColorLabel);
  }
  if (record.detectedColor && typeof record.detectedColor === "object") {
    node.detectedColor = record.detectedColor as ColorSample;
  }
  return node;
}

function normalizeGraph(raw: unknown, index: number): MovementGraph | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  const nodes = Array.isArray(record.nodes) ? record.nodes.map(normalizeNode).filter((node): node is MovementGraphNode => Boolean(node)) : [];
  const createdAt = typeof record.createdAt === "string" ? record.createdAt : nowIso();
  const updatedAt = typeof record.updatedAt === "string" ? record.updatedAt : createdAt;
  const startNode = nodes.find((node) => node.type === "start") ?? createGraphNode("start", 0);
  if (!nodes.some((node) => node.id === startNode.id)) nodes.unshift(startNode);
  const edges = Array.isArray(record.edges)
    ? record.edges
      .map((edge) => normalizeEdge(edge))
      .filter((edge): edge is MovementGraphEdge => Boolean(edge))
    : [];
  return {
    id: typeof record.id === "string" ? record.id : makeId("graph"),
    name: typeof record.name === "string" && record.name.trim() ? record.name.trim() : `Movement Graph ${index + 1}`,
    description: typeof record.description === "string" ? record.description : "",
    nodes,
    edges,
    startNodeId: typeof record.startNodeId === "string" ? record.startNodeId : startNode.id,
    createdAt,
    updatedAt
  };
}

function normalizeEdge(raw: unknown): MovementGraphEdge | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (typeof record.fromNodeId !== "string" || typeof record.toNodeId !== "string") return null;
  const branch = record.branch === "default" || isColorLabel(record.branch) ? record.branch : undefined;
  return {
    id: typeof record.id === "string" ? record.id : makeId("edge"),
    fromNodeId: record.fromNodeId,
    toNodeId: record.toNodeId,
    branch
  };
}

function loadPersistedProgrammingState(): PersistedProgrammingState {
  if (typeof window === "undefined") {
    return emptyPersisted();
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyPersisted();
    const parsed = JSON.parse(raw) as Partial<PersistedProgrammingState>;
    const savedPositions = Array.isArray(parsed.savedPositions)
      ? parsed.savedPositions.map(normalizePosition).filter((position): position is SavedPosition => Boolean(position))
      : [];
    const movementOrders = Array.isArray(parsed.movementOrders)
      ? parsed.movementOrders.map(normalizeOrder).filter((order): order is MovementOrder => Boolean(order))
      : [];
    const movementGraphs = Array.isArray(parsed.movementGraphs)
      ? parsed.movementGraphs.map(normalizeGraph).filter((graph): graph is MovementGraph => Boolean(graph))
      : [];
    return {
      savedPositions,
      movementOrders,
      movementGraphs,
      selectedOrderId: typeof parsed.selectedOrderId === "string" ? parsed.selectedOrderId : movementOrders[0]?.id ?? null,
      selectedGraphId: typeof parsed.selectedGraphId === "string" ? parsed.selectedGraphId : movementGraphs[0]?.id ?? null
    };
  } catch {
    return emptyPersisted();
  }
}

function emptyPersisted(): PersistedProgrammingState {
  return {
    savedPositions: [],
    movementOrders: [],
    movementGraphs: [],
    selectedOrderId: null,
    selectedGraphId: null
  };
}

function persistProgrammingState(state: DigitalTwinState): void {
  if (typeof window === "undefined") return;
  const persisted: PersistedProgrammingState = {
    savedPositions: state.savedPositions,
    movementOrders: state.movementOrders,
    movementGraphs: state.movementGraphs,
    selectedOrderId: state.selectedOrderId,
    selectedGraphId: state.selectedGraphId
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function isColorLabel(value: unknown): value is ColorLabel {
  return value === "red" || value === "green" || value === "blue" || value === "yellow" || value === "black" || value === "white" || value === "unknown";
}

function labelForNodeType(type: MovementGraphNodeType): string {
  switch (type) {
    case "start":
      return "Start";
    case "position":
      return "Position";
    case "movementOrder":
      return "Movement Order";
    case "camera":
      return "Camera";
    case "colorPicker":
      return "Color Picker";
    case "conditional":
      return "Condition";
  }
}

function createGraphNode(type: MovementGraphNodeType, index: number): MovementGraphNode {
  const node: MovementGraphNode = {
    id: makeId("node"),
    type,
    label: labelForNodeType(type),
    x: 24 + (index % 3) * 220,
    y: 24 + Math.floor(index / 3) * 165
  };
  if (type === "colorPicker") {
    node.roi = DEFAULT_ROI;
    node.detectedColor = {
      r: 0,
      g: 0,
      b: 0,
      label: "unknown",
      sampledAt: nowIso()
    };
  }
  if (type === "conditional") {
    node.branches = DEFAULT_BRANCHES;
  }
  return node;
}

function createMovementStep(positionId: string): MovementStep {
  return {
    id: makeId("step"),
    positionId,
    ...DEFAULT_STEP
  };
}

function createMovementOrder(name: string, index: number): MovementOrder {
  const timestamp = nowIso();
  return {
    id: makeId("order"),
    name: name.trim() || `Movement Order ${index + 1}`,
    description: "",
    steps: [],
    createdAt: timestamp,
    updatedAt: timestamp
  };
}

function createMovementGraph(name: string, index: number): MovementGraph {
  const timestamp = nowIso();
  const startNode = createGraphNode("start", 0);
  return {
    id: makeId("graph"),
    name: name.trim() || `Movement Graph ${index + 1}`,
    description: "",
    nodes: [startNode],
    edges: [],
    startNodeId: startNode.id,
    createdAt: timestamp,
    updatedAt: timestamp
  };
}

function validateMovementOrderObject(
  order: MovementOrder | undefined,
  positions: SavedPosition[],
  model: ModelInfo | null
): OrderValidation {
  const errors: string[] = [];
  if (!order) {
    return { valid: false, errors: ["Movement order not found"] };
  }
  if (!order.steps.length) {
    errors.push("Add at least one saved position to the order");
  }
  order.steps.forEach((step, index) => {
    const position = positions.find((candidate) => candidate.id === step.positionId);
    if (!position) {
      errors.push(`Step ${index + 1} references a missing saved position`);
      return;
    }
    errors.push(...jointLimitErrors(position.jointValues, model?.joint_limits, `Step ${index + 1}`));
    if (step.speed < 0.05 || step.speed > 1) errors.push(`Step ${index + 1} speed must be 0.05..1.00`);
    if (step.acceleration <= 0) errors.push(`Step ${index + 1} acceleration must be positive`);
    if (step.delayMs < 0) errors.push(`Step ${index + 1} delay cannot be negative`);
  });
  return { valid: errors.length === 0, errors };
}

function validateMovementGraphObject(
  graph: MovementGraph | undefined,
  positions: SavedPosition[],
  orders: MovementOrder[],
  model: ModelInfo | null
): GraphValidation {
  const errors: string[] = [];
  if (!graph) {
    return { valid: false, errors: ["Movement graph not found"] };
  }
  const start = graph.nodes.find((node) => node.id === graph.startNodeId);
  if (!start) errors.push("Graph start node is missing");
  const ids = new Set(graph.nodes.map((node) => node.id));
  graph.edges.forEach((edge) => {
    if (!ids.has(edge.fromNodeId)) errors.push("Graph has an edge from a missing node");
    if (!ids.has(edge.toNodeId)) errors.push("Graph has an edge to a missing node");
  });
  graph.nodes.forEach((node) => {
    if (node.type === "position") {
      if (!node.positionId) errors.push(`${node.label} needs a saved position`);
      const position = positions.find((candidate) => candidate.id === node.positionId);
      if (node.positionId && !position) errors.push(`${node.label} references a missing saved position`);
      if (position) errors.push(...jointLimitErrors(position.jointValues, model?.joint_limits, node.label));
    }
    if (node.type === "movementOrder") {
      const order = orders.find((candidate) => candidate.id === node.orderId);
      if (!node.orderId) errors.push(`${node.label} needs a movement order`);
      if (node.orderId && !order) errors.push(`${node.label} references a missing movement order`);
      const validation = validateMovementOrderObject(order, positions, model);
      if (order && !validation.valid) {
        validation.errors.forEach((error) => errors.push(`${node.label}: ${error}`));
      }
    }
    if (node.type === "colorPicker") {
      const source = graph.nodes.find((candidate) => candidate.id === node.sourceNodeId);
      if (!source || source.type !== "camera") errors.push(`${node.label} needs a camera node source`);
    }
    if (node.type === "conditional") {
      const branches = node.branches?.length ? node.branches : DEFAULT_BRANCHES;
      branches.forEach((branch) => {
        const hasEdge = graph.edges.some((edge) => edge.fromNodeId === node.id && edge.branch === branch);
        if (!hasEdge) errors.push(`${node.label} branch "${branch}" is not connected`);
      });
    }
  });
  if (start) {
    const hasStartEdge = graph.edges.some((edge) => edge.fromNodeId === start.id);
    if (!hasStartEdge && graph.nodes.length > 1) errors.push("Start node is not connected");
  }
  return { valid: errors.length === 0, errors };
}

function findPosition(state: DigitalTwinState, id: string | undefined): SavedPosition | undefined {
  return state.savedPositions.find((position) => position.id === id);
}

function nextEdge(graph: MovementGraph, nodeId: string, branch?: ColorLabel | "default"): MovementGraphEdge | undefined {
  if (branch) {
    return graph.edges.find((edge) => edge.fromNodeId === nodeId && edge.branch === branch)
      ?? graph.edges.find((edge) => edge.fromNodeId === nodeId && edge.branch === "default");
  }
  return graph.edges.find((edge) => edge.fromNodeId === nodeId && (edge.branch === undefined || edge.branch === "default"))
    ?? graph.edges.find((edge) => edge.fromNodeId === nodeId);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms)));
}

async function waitIfPaused(get: () => DigitalTwinState): Promise<boolean> {
  while (get().executionState.mode === "paused") {
    await delay(100);
  }
  return get().executionState.mode === "stopped";
}

function shouldStop(get: () => DigitalTwinState): boolean {
  return get().executionState.mode === "stopped" || get().executionState.mode === "error";
}

function applyPositionToPreview(
  position: SavedPosition,
  set: (partial: Partial<DigitalTwinState> | ((state: DigitalTwinState) => Partial<DigitalTwinState>)) => void,
  get: () => DigitalTwinState
): void {
  const pose = cartesianPoseToArray(position.cartesianPose);
  set((state) => ({
    previewAngles: clampToLimits(position.jointValues, state.model?.joint_limits),
    anchorPose: pose ?? state.anchorPose,
    log: appendLog(state.log, `preview ${position.name}`)
  }));
  persistProgrammingState(get());
}

function selectedColorFromGraph(graph: MovementGraph): ColorLabel {
  const sampleNode = graph.nodes.find((node) => node.type === "colorPicker" && node.detectedColor);
  return sampleNode?.detectedColor?.label ?? "unknown";
}

const persisted = loadPersistedProgrammingState();

export const useDigitalTwinStore = create<DigitalTwinState>((set, get) => ({
  model: null,
  status: null,
  previewAngles: HOME_PREVIEW,
  anchorPose: DEFAULT_POSE,
  anchorTransformMode: "translate",
  selectedJoint: null,
  speedScale: 0.5,
  applyAnchorOnRelease: false,
  savedPositions: persisted.savedPositions,
  movementOrders: persisted.movementOrders,
  movementGraphs: persisted.movementGraphs,
  selectedOrderId: persisted.selectedOrderId,
  selectedGraphId: persisted.selectedGraphId,
  executionState: {
    mode: "idle",
    message: "Ready",
    errors: []
  },
  cameraStatus: "idle",
  log: [],
  loading: false,
  error: null,

  loadModel: async () => {
    const model = await DigitalTwinApi.model();
    const previewAngles = clampToLimits(model.home_angles_deg, model.joint_limits);
    set({ model, previewAngles });
    try {
      const fk = await DigitalTwinApi.fk(previewAngles);
      if (fk.ok && fk.pose_m_rad) set({ anchorPose: fk.pose_m_rad });
    } catch {
      // Keep the deterministic fallback pose; status polling will recover later.
    }
  },

  refreshStatus: async () => {
    const status = await DigitalTwinApi.status();
    set((state) => ({
      status,
      previewAngles: status.angles_deg && !status.live_enabled ? clampToLimits(status.angles_deg, state.model?.joint_limits) : state.previewAngles,
      anchorPose: status.tcp_pose_m_rad && !status.live_enabled ? status.tcp_pose_m_rad : state.anchorPose,
      error: status.error
    }));
  },

  setPreviewAngles: (angles) => set((state) => ({ previewAngles: clampToLimits(angles, state.model?.joint_limits) })),

  setJointPreview: (index, value) =>
    set((state) => {
      const next = state.previewAngles.slice();
      next[index] = value;
      return { previewAngles: clampToLimits(next, state.model?.joint_limits) };
    }),

  setAnchorPose: (pose) => set({ anchorPose: pose.slice(0, 6) }),

  setAnchorRotationDeg: (axisIndex, valueDeg) =>
    set((state) => {
      const next = state.anchorPose.slice();
      next[3 + axisIndex] = (valueDeg * Math.PI) / 180;
      return { anchorPose: next };
    }),

  setAnchorTransformMode: (mode) => set({ anchorTransformMode: mode }),

  solveAnchorTarget: async (pose) => {
    const targetPose = pose ?? get().anchorPose;
    const { previewAngles } = get();
    try {
      const result = await DigitalTwinApi.ik(targetPose, previewAngles);
      if (!result.ok || !result.angles_deg) {
        set((state) => ({ error: result.message, log: appendLog(state.log, result.message) }));
        return;
      }
      set((state) => ({
        previewAngles: clampToLimits(result.angles_deg ?? state.previewAngles, state.model?.joint_limits),
        anchorPose: targetPose,
        error: null,
        log: appendLog(state.log, result.message)
      }));
    } catch (err) {
      set((state) => ({ error: String(err), log: appendLog(state.log, `IK failed: ${String(err)}`) }));
    }
  },

  moveToAnchor: async (pose) => {
    const targetPose = pose ?? get().anchorPose;
    const { previewAngles, speedScale } = get();
    const result = await DigitalTwinApi.movePose(targetPose, previewAngles, speedScale);
    set((state) => ({
      status: result.status,
      log: appendLog(state.log, result.message),
      error: result.ok ? null : result.message
    }));
  },

  captureLivePosition: () => {
    const { status } = get();
    if (!status?.angles_deg) {
      set((state) => ({
        error: "Live joint readback is unavailable",
        log: appendLog(state.log, "capture failed: live joint readback unavailable")
      }));
      return;
    }
    set((state) => ({
      previewAngles: clampToLimits(status.angles_deg ?? state.previewAngles, state.model?.joint_limits),
      anchorPose: status.tcp_pose_m_rad ?? state.anchorPose,
      error: null,
      log: appendLog(state.log, "captured live robot position")
    }));
  },

  saveCurrentPosition: (name, description) => {
    set((state) => {
      const timestamp = nowIso();
      const index = state.savedPositions.length + 1;
      const saved: SavedPosition = {
        id: makeId("pos"),
        name: name?.trim() || `Position ${index}`,
        jointValues: state.previewAngles.slice(0, 6),
        cartesianPose: poseArrayToCartesianPose(state.anchorPose),
        description: description?.trim() ?? "",
        source: state.status?.live_enabled ? "live" : "simulated",
        createdAt: timestamp,
        updatedAt: timestamp
      };
      return {
        savedPositions: [...state.savedPositions, saved],
        log: appendLog(state.log, `saved ${saved.name}`)
      };
    });
    persistProgrammingState(get());
  },

  updateSavedPosition: (id, patch) => {
    set((state) => ({
      savedPositions: state.savedPositions.map((position) =>
        position.id === id
          ? {
            ...position,
            name: patch.name !== undefined ? patch.name : position.name,
            description: patch.description !== undefined ? patch.description : position.description,
            updatedAt: nowIso()
          }
          : position
      )
    }));
    persistProgrammingState(get());
  },

  replaceSavedPositionWithCurrentPose: (id) => {
    set((state) => ({
      savedPositions: state.savedPositions.map((position) =>
        position.id === id
          ? {
            ...position,
            jointValues: state.previewAngles.slice(0, 6),
            cartesianPose: poseArrayToCartesianPose(state.anchorPose),
            source: state.status?.live_enabled ? "live" : "simulated",
            updatedAt: nowIso()
          }
          : position
      ),
      log: appendLog(state.log, "updated saved position from current pose")
    }));
    persistProgrammingState(get());
  },

  deleteSavedPosition: (id) => {
    set((state) => ({
      savedPositions: state.savedPositions.filter((position) => position.id !== id),
      movementOrders: state.movementOrders.map((order) => ({
        ...order,
        steps: order.steps.filter((step) => step.positionId !== id),
        updatedAt: order.steps.some((step) => step.positionId === id) ? nowIso() : order.updatedAt
      })),
      movementGraphs: state.movementGraphs.map((graph) => ({
        ...graph,
        nodes: graph.nodes.map((node) => node.positionId === id ? { ...node, positionId: undefined } : node),
        updatedAt: graph.nodes.some((node) => node.positionId === id) ? nowIso() : graph.updatedAt
      }))
    }));
    persistProgrammingState(get());
  },

  removeSavedPosition: (id) => get().deleteSavedPosition(id),

  loadSavedPosition: (id) => {
    const saved = get().savedPositions.find((position) => position.id === id);
    if (!saved) return;
    applyPositionToPreview(saved, set, get);
  },

  exportSavedPositions: () => {
    const { savedPositions } = get();
    return JSON.stringify(
      {
        exportedAt: nowIso(),
        format: "parol6-digital-twin-positions/v2",
        positions: savedPositions
      },
      null,
      2
    );
  },

  setSelectedJoint: (name) => set({ selectedJoint: name }),
  setSpeedScale: (value) => set({ speedScale: Math.min(Math.max(value, 0.05), 1) }),
  setApplyAnchorOnRelease: (enabled) => set({ applyAnchorOnRelease: enabled }),

  connect: async () => {
    set({ loading: true });
    try {
      const status = await DigitalTwinApi.connect();
      set((state) => ({ status, loading: false, log: appendLog(state.log, status.message) }));
    } catch (err) {
      set((state) => ({ loading: false, error: String(err), log: appendLog(state.log, `connect failed: ${String(err)}`) }));
    }
  },

  disconnect: async () => {
    const status = await DigitalTwinApi.disconnect();
    set((state) => ({ status, log: appendLog(state.log, status.message) }));
  },

  setLive: async (live) => {
    const status = await DigitalTwinApi.setMode({ live_enabled: live });
    set((state) => ({ status, log: appendLog(state.log, status.message) }));
  },

  setMovement: async (enabled) => {
    const status = await DigitalTwinApi.setMode({ movement_enabled: enabled });
    set((state) => ({ status, log: appendLog(state.log, status.message) }));
  },

  home: async () => {
    const result = await DigitalTwinApi.home();
    set((state) => ({ status: result.status, log: appendLog(state.log, result.message) }));
  },

  halt: async () => {
    const result = await DigitalTwinApi.halt();
    set((state) => ({ status: result.status, log: appendLog(state.log, result.message) }));
  },

  dispatchMove: async () => {
    const { previewAngles, speedScale } = get();
    const result = await DigitalTwinApi.moveJoints(previewAngles, speedScale);
    set((state) => ({ status: result.status, log: appendLog(state.log, result.message), error: result.ok ? null : result.message }));
  },

  resetPreviewToTelemetry: () =>
    set((state) => ({
      previewAngles: clampToLimits(state.status?.angles_deg ?? state.model?.home_angles_deg ?? HOME_PREVIEW, state.model?.joint_limits),
      anchorPose: state.status?.tcp_pose_m_rad ?? state.anchorPose
    })),

  createMovementOrder: (name) => {
    const order = createMovementOrder(name ?? "", get().movementOrders.length);
    set((state) => ({
      movementOrders: [...state.movementOrders, order],
      selectedOrderId: order.id,
      log: appendLog(state.log, `created ${order.name}`)
    }));
    persistProgrammingState(get());
    return order.id;
  },

  selectMovementOrder: (id) => {
    set({ selectedOrderId: id });
    persistProgrammingState(get());
  },

  updateMovementOrder: (id, patch) => {
    set((state) => ({
      movementOrders: state.movementOrders.map((order) =>
        order.id === id
          ? {
            ...order,
            name: patch.name !== undefined ? patch.name : order.name,
            description: patch.description !== undefined ? patch.description : order.description,
            updatedAt: nowIso()
          }
          : order
      )
    }));
    persistProgrammingState(get());
  },

  duplicateMovementOrder: (id) => {
    const source = get().movementOrders.find((order) => order.id === id);
    if (!source) return null;
    const timestamp = nowIso();
    const copy: MovementOrder = {
      ...source,
      id: makeId("order"),
      name: `${source.name} Copy`,
      steps: source.steps.map((step) => ({ ...step, id: makeId("step") })),
      createdAt: timestamp,
      updatedAt: timestamp
    };
    set((state) => ({
      movementOrders: [...state.movementOrders, copy],
      selectedOrderId: copy.id,
      log: appendLog(state.log, `duplicated ${source.name}`)
    }));
    persistProgrammingState(get());
    return copy.id;
  },

  deleteMovementOrder: (id) => {
    set((state) => {
      const nextOrders = state.movementOrders.filter((order) => order.id !== id);
      return {
        movementOrders: nextOrders,
        selectedOrderId: state.selectedOrderId === id ? nextOrders[0]?.id ?? null : state.selectedOrderId,
        movementGraphs: state.movementGraphs.map((graph) => ({
          ...graph,
          nodes: graph.nodes.map((node) => node.orderId === id ? { ...node, orderId: undefined } : node),
          updatedAt: graph.nodes.some((node) => node.orderId === id) ? nowIso() : graph.updatedAt
        }))
      };
    });
    persistProgrammingState(get());
  },

  addPositionToOrder: (orderId, positionId) => {
    set((state) => ({
      movementOrders: state.movementOrders.map((order) =>
        order.id === orderId
          ? {
            ...order,
            steps: [...order.steps, createMovementStep(positionId)],
            updatedAt: nowIso()
          }
          : order
      )
    }));
    persistProgrammingState(get());
  },

  removeStepFromOrder: (orderId, stepId) => {
    set((state) => ({
      movementOrders: state.movementOrders.map((order) =>
        order.id === orderId
          ? {
            ...order,
            steps: order.steps.filter((step) => step.id !== stepId),
            updatedAt: nowIso()
          }
          : order
      )
    }));
    persistProgrammingState(get());
  },

  reorderOrderStep: (orderId, stepId, targetIndex) => {
    set((state) => ({
      movementOrders: state.movementOrders.map((order) => {
        if (order.id !== orderId) return order;
        const currentIndex = order.steps.findIndex((step) => step.id === stepId);
        if (currentIndex < 0) return order;
        const steps = order.steps.slice();
        const [step] = steps.splice(currentIndex, 1);
        steps.splice(clampNumber(targetIndex, 0, steps.length), 0, step);
        return { ...order, steps, updatedAt: nowIso() };
      })
    }));
    persistProgrammingState(get());
  },

  updateMovementStep: (orderId, stepId, patch) => {
    set((state) => ({
      movementOrders: state.movementOrders.map((order) =>
        order.id === orderId
          ? {
            ...order,
            steps: order.steps.map((step) =>
              step.id === stepId
                ? {
                  ...step,
                  ...patch,
                  speed: patch.speed !== undefined ? clampNumber(patch.speed, 0.05, 1) : step.speed,
                  acceleration: patch.acceleration !== undefined ? clampNumber(patch.acceleration, 0.1, 5) : step.acceleration,
                  delayMs: patch.delayMs !== undefined ? clampNumber(patch.delayMs, 0, 60000) : step.delayMs
                }
                : step
            ),
            updatedAt: nowIso()
          }
          : order
      )
    }));
    persistProgrammingState(get());
  },

  validateMovementOrder: (orderId) => {
    const state = get();
    return validateMovementOrderObject(
      state.movementOrders.find((order) => order.id === orderId),
      state.savedPositions,
      state.model
    );
  },

  previewMovementStep: (orderId, stepIndex) => {
    const state = get();
    const order = state.movementOrders.find((candidate) => candidate.id === orderId);
    const step = order?.steps[stepIndex];
    const position = findPosition(state, step?.positionId);
    if (!order || !step || !position) return;
    set({
      executionState: {
        mode: "idle",
        activeOrderId: order.id,
        activeStepId: step.id,
        message: `Previewing step ${stepIndex + 1}: ${position.name}`,
        errors: []
      }
    });
    applyPositionToPreview(position, set, get);
  },

  simulateMovementOrder: async (orderId) => {
    const state = get();
    const order = state.movementOrders.find((candidate) => candidate.id === orderId);
    const validation = validateMovementOrderObject(order, state.savedPositions, state.model);
    if (!order || !validation.valid) {
      set({
        executionState: {
          mode: "error",
          activeOrderId: orderId,
          message: "Movement order is not ready to simulate",
          errors: validation.errors
        },
        error: validation.errors[0] ?? "Movement order is not ready"
      });
      return;
    }
    set({
      executionState: {
        mode: "simulating",
        activeOrderId: order.id,
        message: `Simulating ${order.name}`,
        errors: []
      },
      error: null
    });
    for (const step of order.steps) {
      if (await waitIfPaused(get) || shouldStop(get)) return;
      const position = findPosition(get(), step.positionId);
      if (!position) continue;
      set({
        executionState: {
          mode: "simulating",
          activeOrderId: order.id,
          activeStepId: step.id,
          message: `Simulating ${position.name}`,
          errors: []
        }
      });
      applyPositionToPreview(position, set, get);
      await delay(step.delayMs);
    }
    if (!shouldStop(get)) {
      set((current) => ({
        executionState: {
          mode: "idle",
          message: `Finished simulation: ${order.name}`,
          errors: []
        },
        log: appendLog(current.log, `simulated ${order.name}`)
      }));
    }
  },

  executeMovementOrder: async (orderId) => {
    const state = get();
    const order = state.movementOrders.find((candidate) => candidate.id === orderId);
    const validation = validateMovementOrderObject(order, state.savedPositions, state.model);
    if (!selectors.canSendLiveMove(state.status)) {
      validation.errors.push("Robot is not connected, homed, live, enabled, and clear of errors");
    }
    if (!order || !validation.valid) {
      set({
        executionState: {
          mode: "error",
          activeOrderId: orderId,
          message: "Movement order is not safe to execute",
          errors: validation.errors
        },
        error: validation.errors[0] ?? "Movement order is not safe to execute"
      });
      return;
    }
    set({
      executionState: {
        mode: "executing",
        activeOrderId: order.id,
        message: `Executing ${order.name}`,
        errors: []
      },
      error: null
    });
    for (const step of order.steps) {
      if (await waitIfPaused(get) || shouldStop(get)) return;
      const position = findPosition(get(), step.positionId);
      if (!position) continue;
      set({
        executionState: {
          mode: "executing",
          activeOrderId: order.id,
          activeStepId: step.id,
          message: `Executing ${position.name}`,
          errors: []
        }
      });
      const result = await DigitalTwinApi.moveJoints(position.jointValues, step.speed, true);
      set((current) => ({
        status: result.status,
        error: result.ok ? null : result.message,
        log: appendLog(current.log, result.message)
      }));
      if (!result.ok) {
        set({
          executionState: {
            mode: "error",
            activeOrderId: order.id,
            activeStepId: step.id,
            message: result.message,
            errors: [result.message]
          }
        });
        return;
      }
      await delay(step.delayMs);
    }
    if (!shouldStop(get)) {
      set((current) => ({
        executionState: {
          mode: "idle",
          message: `Finished real execution: ${order.name}`,
          errors: []
        },
        log: appendLog(current.log, `executed ${order.name}`)
      }));
    }
  },

  createMovementGraph: (name) => {
    const graph = createMovementGraph(name ?? "", get().movementGraphs.length);
    set((state) => ({
      movementGraphs: [...state.movementGraphs, graph],
      selectedGraphId: graph.id,
      log: appendLog(state.log, `created ${graph.name}`)
    }));
    persistProgrammingState(get());
    return graph.id;
  },

  selectMovementGraph: (id) => {
    set({ selectedGraphId: id });
    persistProgrammingState(get());
  },

  updateMovementGraph: (id, patch) => {
    set((state) => ({
      movementGraphs: state.movementGraphs.map((graph) =>
        graph.id === id
          ? {
            ...graph,
            name: patch.name !== undefined ? patch.name : graph.name,
            description: patch.description !== undefined ? patch.description : graph.description,
            updatedAt: nowIso()
          }
          : graph
      )
    }));
    persistProgrammingState(get());
  },

  duplicateMovementGraph: (id) => {
    const source = get().movementGraphs.find((graph) => graph.id === id);
    if (!source) return null;
    const timestamp = nowIso();
    const idMap = new Map(source.nodes.map((node) => [node.id, makeId("node")]));
    const copy: MovementGraph = {
      ...source,
      id: makeId("graph"),
      name: `${source.name} Copy`,
      nodes: source.nodes.map((node) => ({
        ...node,
        id: idMap.get(node.id) ?? makeId("node"),
        sourceNodeId: node.sourceNodeId ? idMap.get(node.sourceNodeId) ?? node.sourceNodeId : undefined
      })),
      edges: source.edges.map((edge) => ({
        ...edge,
        id: makeId("edge"),
        fromNodeId: idMap.get(edge.fromNodeId) ?? edge.fromNodeId,
        toNodeId: idMap.get(edge.toNodeId) ?? edge.toNodeId
      })),
      startNodeId: idMap.get(source.startNodeId) ?? source.startNodeId,
      createdAt: timestamp,
      updatedAt: timestamp
    };
    set((state) => ({
      movementGraphs: [...state.movementGraphs, copy],
      selectedGraphId: copy.id,
      log: appendLog(state.log, `duplicated ${source.name}`)
    }));
    persistProgrammingState(get());
    return copy.id;
  },

  deleteMovementGraph: (id) => {
    set((state) => {
      const nextGraphs = state.movementGraphs.filter((graph) => graph.id !== id);
      return {
        movementGraphs: nextGraphs,
        selectedGraphId: state.selectedGraphId === id ? nextGraphs[0]?.id ?? null : state.selectedGraphId
      };
    });
    persistProgrammingState(get());
  },

  addGraphNode: (graphId, type) => {
    const graph = get().movementGraphs.find((candidate) => candidate.id === graphId);
    if (!graph) return null;
    const node = createGraphNode(type, graph.nodes.length);
    set((state) => ({
      movementGraphs: state.movementGraphs.map((candidate) =>
        candidate.id === graphId
          ? { ...candidate, nodes: [...candidate.nodes, node], updatedAt: nowIso() }
          : candidate
      )
    }));
    persistProgrammingState(get());
    return node.id;
  },

  updateGraphNode: (graphId, nodeId, patch) => {
    set((state) => ({
      movementGraphs: state.movementGraphs.map((graph) =>
        graph.id === graphId
          ? {
            ...graph,
            nodes: graph.nodes.map((node) => node.id === nodeId ? { ...node, ...patch } : node),
            updatedAt: nowIso()
          }
          : graph
      )
    }));
    persistProgrammingState(get());
  },

  deleteGraphNode: (graphId, nodeId) => {
    set((state) => ({
      movementGraphs: state.movementGraphs.map((graph) => {
        if (graph.id !== graphId) return graph;
        const node = graph.nodes.find((candidate) => candidate.id === nodeId);
        if (!node || node.type === "start") return graph;
        return {
          ...graph,
          nodes: graph.nodes.filter((candidate) => candidate.id !== nodeId),
          edges: graph.edges.filter((edge) => edge.fromNodeId !== nodeId && edge.toNodeId !== nodeId),
          updatedAt: nowIso()
        };
      })
    }));
    persistProgrammingState(get());
  },

  connectGraphNodes: (graphId, fromNodeId, toNodeId, branch) => {
    set((state) => ({
      movementGraphs: state.movementGraphs.map((graph) => {
        if (graph.id !== graphId) return graph;
        const edges = graph.edges.filter((edge) => !(edge.fromNodeId === fromNodeId && (edge.branch ?? "default") === (branch ?? "default")));
        if (toNodeId) {
          edges.push({
            id: makeId("edge"),
            fromNodeId,
            toNodeId,
            branch
          });
        }
        return { ...graph, edges, updatedAt: nowIso() };
      })
    }));
    persistProgrammingState(get());
  },

  validateMovementGraph: (graphId) => {
    const state = get();
    return validateMovementGraphObject(
      state.movementGraphs.find((graph) => graph.id === graphId),
      state.savedPositions,
      state.movementOrders,
      state.model
    );
  },

  simulateMovementGraph: async (graphId) => {
    const initial = get();
    const graph = initial.movementGraphs.find((candidate) => candidate.id === graphId);
    const validation = validateMovementGraphObject(graph, initial.savedPositions, initial.movementOrders, initial.model);
    if (!graph || !validation.valid) {
      set({
        executionState: {
          mode: "error",
          message: "Movement graph is not ready to simulate",
          errors: validation.errors
        },
        error: validation.errors[0] ?? "Movement graph is not ready"
      });
      return;
    }
    set({
      executionState: {
        mode: "simulating",
        message: `Simulating ${graph.name}`,
        errors: []
      },
      error: null
    });
    let currentNodeId: string | undefined = graph.startNodeId;
    let colorLabel: ColorLabel = selectedColorFromGraph(graph);
    const visited = new Map<string, number>();
    for (let guard = 0; guard < 80 && currentNodeId; guard += 1) {
      if (await waitIfPaused(get) || shouldStop(get)) return;
      const latestGraph = get().movementGraphs.find((candidate) => candidate.id === graphId) ?? graph;
      const node = latestGraph.nodes.find((candidate) => candidate.id === currentNodeId);
      if (!node) break;
      visited.set(node.id, (visited.get(node.id) ?? 0) + 1);
      if ((visited.get(node.id) ?? 0) > 8) {
        set({
          executionState: {
            mode: "error",
            activeNodeId: node.id,
            message: "Graph loop guard stopped simulation",
            errors: ["The graph appears to loop without a stop condition"]
          }
        });
        return;
      }
      set({
        executionState: {
          mode: "simulating",
          activeNodeId: node.id,
          message: `Simulating node: ${node.label}`,
          errors: []
        }
      });
      if (node.type === "position") {
        const position = findPosition(get(), node.positionId);
        if (position) applyPositionToPreview(position, set, get);
      }
      if (node.type === "movementOrder" && node.orderId) {
        const order = get().movementOrders.find((candidate) => candidate.id === node.orderId);
        if (order) {
          for (const step of order.steps) {
            const position = findPosition(get(), step.positionId);
            if (position) applyPositionToPreview(position, set, get);
            await delay(step.delayMs);
          }
        }
      }
      if (node.type === "colorPicker") {
        colorLabel = node.detectedColor?.label ?? "unknown";
      }
      await delay(180);
      const branch = node.type === "conditional" ? colorLabel : undefined;
      currentNodeId = nextEdge(latestGraph, node.id, branch)?.toNodeId;
    }
    if (!shouldStop(get)) {
      set((current) => ({
        executionState: {
          mode: "idle",
          message: `Finished graph simulation: ${graph.name}`,
          errors: []
        },
        log: appendLog(current.log, `simulated graph ${graph.name}`)
      }));
    }
  },

  executeMovementGraph: async (graphId) => {
    const initial = get();
    const graph = initial.movementGraphs.find((candidate) => candidate.id === graphId);
    const validation = validateMovementGraphObject(graph, initial.savedPositions, initial.movementOrders, initial.model);
    if (!selectors.canSendLiveMove(initial.status)) {
      validation.errors.push("Robot is not connected, homed, live, enabled, and clear of errors");
    }
    if (!graph || !validation.valid) {
      set({
        executionState: {
          mode: "error",
          message: "Movement graph is not safe to execute",
          errors: validation.errors
        },
        error: validation.errors[0] ?? "Movement graph is not safe to execute"
      });
      return;
    }
    set({
      executionState: {
        mode: "executing",
        message: `Executing graph ${graph.name}`,
        errors: []
      },
      error: null
    });
    let currentNodeId: string | undefined = graph.startNodeId;
    let colorLabel: ColorLabel = selectedColorFromGraph(graph);
    const visited = new Map<string, number>();
    for (let guard = 0; guard < 80 && currentNodeId; guard += 1) {
      if (await waitIfPaused(get) || shouldStop(get)) return;
      const latestGraph = get().movementGraphs.find((candidate) => candidate.id === graphId) ?? graph;
      const node = latestGraph.nodes.find((candidate) => candidate.id === currentNodeId);
      if (!node) break;
      visited.set(node.id, (visited.get(node.id) ?? 0) + 1);
      if ((visited.get(node.id) ?? 0) > 8) {
        set({
          executionState: {
            mode: "error",
            activeNodeId: node.id,
            message: "Graph loop guard stopped execution",
            errors: ["The graph appears to loop without a stop condition"]
          }
        });
        return;
      }
      set({
        executionState: {
          mode: "executing",
          activeNodeId: node.id,
          message: `Executing node: ${node.label}`,
          errors: []
        }
      });
      if (node.type === "position") {
        const position = findPosition(get(), node.positionId);
        if (position) {
          const result = await DigitalTwinApi.moveJoints(position.jointValues, get().speedScale, true);
          set((current) => ({
            status: result.status,
            error: result.ok ? null : result.message,
            log: appendLog(current.log, result.message)
          }));
          if (!result.ok) {
            set({
              executionState: {
                mode: "error",
                activeNodeId: node.id,
                message: result.message,
                errors: [result.message]
              }
            });
            return;
          }
        }
      }
      if (node.type === "movementOrder" && node.orderId) {
        const order = get().movementOrders.find((candidate) => candidate.id === node.orderId);
        if (order) {
          for (const step of order.steps) {
            if (await waitIfPaused(get) || shouldStop(get)) return;
            const position = findPosition(get(), step.positionId);
            if (!position) continue;
            const result = await DigitalTwinApi.moveJoints(position.jointValues, step.speed, true);
            set((current) => ({
              status: result.status,
              error: result.ok ? null : result.message,
              log: appendLog(current.log, result.message)
            }));
            if (!result.ok) {
              set({
                executionState: {
                  mode: "error",
                  activeNodeId: node.id,
                  message: result.message,
                  errors: [result.message]
                }
              });
              return;
            }
            await delay(step.delayMs);
          }
        }
      }
      if (node.type === "colorPicker") {
        colorLabel = node.detectedColor?.label ?? "unknown";
      }
      const branch = node.type === "conditional" ? colorLabel : undefined;
      currentNodeId = nextEdge(latestGraph, node.id, branch)?.toNodeId;
    }
    if (!shouldStop(get)) {
      set((current) => ({
        executionState: {
          mode: "idle",
          message: `Finished graph execution: ${graph.name}`,
          errors: []
        },
        log: appendLog(current.log, `executed graph ${graph.name}`)
      }));
    }
  },

  setGraphColorSample: (graphId, nodeId, sample) => {
    set((state) => ({
      movementGraphs: state.movementGraphs.map((graph) =>
        graph.id === graphId
          ? {
            ...graph,
            nodes: graph.nodes.map((node) => node.id === nodeId ? { ...node, detectedColor: sample } : node),
            updatedAt: nowIso()
          }
          : graph
      )
    }));
    persistProgrammingState(get());
  },

  setCameraStatus: (status) => set({ cameraStatus: status }),

  pauseExecution: () => {
    const current = get().executionState;
    if (current.mode !== "executing" && current.mode !== "simulating") return;
    set({
      executionState: {
        ...current,
        mode: "paused",
        resumeMode: current.mode,
        message: "Execution paused"
      }
    });
  },

  resumeExecution: () => {
    const current = get().executionState;
    if (current.mode !== "paused" || !current.resumeMode) return;
    set({
      executionState: {
        ...current,
        mode: current.resumeMode,
        resumeMode: undefined,
        message: "Execution resumed"
      }
    });
  },

  stopExecution: () => {
    set({
      executionState: {
        mode: "stopped",
        message: "Execution stopped",
        errors: []
      }
    });
  }
}));

export const selectors = {
  canSendLiveMove: (status: RobotStatus | null): boolean =>
    Boolean(status?.connected && status.live_enabled && status.movement_enabled && status.homed && !status.estop && !status.error),
  validateMovementOrderObject,
  validateMovementGraphObject,
  cartesianPoseToArray
};
