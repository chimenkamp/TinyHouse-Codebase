export type JointLimit = {
  name: string;
  lower_deg: number;
  upper_deg: number;
};

export type NamedState = {
  name: string;
  group: string;
  values: Record<string, number>;
};

export type ModelInfo = {
  urdf_url: string;
  package_name: string;
  package_url: string;
  mesh_url: string;
  joint_limits: JointLimit[];
  home_angles_deg: number[];
  named_states: NamedState[];
};

export type RobotStatus = {
  connected: boolean;
  live_enabled: boolean;
  movement_enabled: boolean;
  homed: boolean;
  estop: boolean;
  error: string | null;
  moving: boolean;
  simulator_active: boolean | null;
  hardware_connected: boolean | null;
  angles_deg: number[] | null;
  target_angles_deg: number[] | null;
  pose: number[] | null;
  tcp_pose_m_rad: number[] | null;
  speeds: number[] | null;
  io: number[] | null;
  activity: Record<string, unknown> | null;
  message: string;
};

export type CommandResult = {
  ok: boolean;
  message: string;
  command_index: number | null;
  status: RobotStatus;
};

export type ValidationResult = {
  valid: boolean;
  clamped_angles_deg: number[];
  errors: string[];
};

export type PoseResult = {
  ok: boolean;
  message: string;
  pose_m_rad: number[] | null;
  angles_deg: number[] | null;
};

export type CartesianPose = {
  x: number;
  y: number;
  z: number;
  rx: number;
  ry: number;
  rz: number;
};

export type SavedPosition = {
  id: string;
  name: string;
  jointValues: number[];
  cartesianPose?: CartesianPose;
  description?: string;
  source?: "simulated" | "live";
  createdAt: string;
  updatedAt: string;
};

export type InterpolationMode = "joint" | "linear";
export type GripperAction = "none" | "open" | "close";

export type MovementStep = {
  id: string;
  positionId: string;
  speed: number;
  acceleration: number;
  delayMs: number;
  interpolation: InterpolationMode;
  gripperAction: GripperAction;
};

export type MovementOrder = {
  id: string;
  name: string;
  description?: string;
  steps: MovementStep[];
  createdAt: string;
  updatedAt: string;
};

export type ColorLabel = "red" | "green" | "blue" | "yellow" | "black" | "white" | "unknown";

export type ColorSample = {
  r: number;
  g: number;
  b: number;
  label: ColorLabel;
  sampledAt: string;
};

export type ColorPickerRoi = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type MovementGraphNodeType = "start" | "position" | "movementOrder" | "camera" | "colorPicker" | "conditional";

export type MovementGraphNode = {
  id: string;
  type: MovementGraphNodeType;
  label: string;
  x: number;
  y: number;
  positionId?: string;
  orderId?: string;
  sourceNodeId?: string;
  roi?: ColorPickerRoi;
  detectedColor?: ColorSample;
  branches?: ColorLabel[];
};

export type MovementGraphEdge = {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  branch?: ColorLabel | "default";
};

export type MovementGraph = {
  id: string;
  name: string;
  description?: string;
  nodes: MovementGraphNode[];
  edges: MovementGraphEdge[];
  startNodeId: string;
  createdAt: string;
  updatedAt: string;
};

export type ExecutionMode = "idle" | "simulating" | "executing" | "paused" | "stopped" | "error";

export type ExecutionState = {
  mode: ExecutionMode;
  resumeMode?: "simulating" | "executing";
  activeNodeId?: string;
  activeOrderId?: string;
  activeStepId?: string;
  message: string;
  errors: string[];
};
