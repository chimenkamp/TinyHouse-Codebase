export type NodeKind = "raspberry" | "jetson" | "broker";

export interface NetworkNode {
  id: string;
  label: string;
  kind: NodeKind;
  role: string;
  sensor: string;
  ip: string;
  x: number;
  y: number;
  health: number;
  rate: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  rate: number;
}

export interface ActivityEvent {
  id: string;
  caseId: string;
  activity: string;
  resource: string;
  source: string;
  timestamp: string;
  confidence: number;
  tone: "blue" | "cyan" | "green" | "violet" | "amber";
}

export interface ProcessCase {
  id: string;
  object: string;
  started: string;
  duration: string;
  status: "running" | "complete" | "attention";
  confidence: number;
  variant: string;
  events: string[];
}

export const networkNodes: NetworkNode[] = [
  { id: "pi-1", label: "EMQX001", kind: "raspberry", role: "3D printer", sensor: "Nozzle temp · vibration", ip: "192.168.1.31", x: 42, y: 54, health: 99.8, rate: 24 },
  { id: "pi-2", label: "EMQX002", kind: "raspberry", role: "Robot arm", sensor: "Joint current · IMU", ip: "192.168.1.32", x: 42, y: 142, health: 99.6, rate: 31 },
  { id: "pi-3", label: "EMQX003", kind: "raspberry", role: "Color station", sensor: "RGB camera · lux", ip: "192.168.1.33", x: 42, y: 230, health: 99.9, rate: 18 },
  { id: "pi-4", label: "EMQX004", kind: "raspberry", role: "Smart drawer", sensor: "Load cell · reed", ip: "192.168.1.34", x: 42, y: 318, health: 98.9, rate: 12 },
  { id: "pi-5", label: "EMQX005", kind: "raspberry", role: "Work surface", sensor: "Pressure · presence", ip: "192.168.1.35", x: 42, y: 406, health: 99.4, rate: 16 },
  { id: "pi-6", label: "EMQX006", kind: "raspberry", role: "Environment", sensor: "Humidity · ambient", ip: "192.168.1.36", x: 42, y: 494, health: 97.8, rate: 8 },
  { id: "broker", label: "MQTT", kind: "broker", role: "EMQX broker", sensor: "QoS 1 · retained", ip: "192.168.1.20", x: 300, y: 252, health: 99.99, rate: 109 },
  { id: "jetson-1", label: "JETSON-01", kind: "jetson", role: "Vision edge", sensor: "Object + color model", ip: "192.168.1.41", x: 462, y: 164, health: 99.5, rate: 42 },
  { id: "jetson-2", label: "JETSON-02", kind: "jetson", role: "Event edge", sensor: "Segmentation + MSEG", ip: "192.168.1.42", x: 462, y: 340, health: 99.2, rate: 67 },
];

export const networkLinks: NetworkLink[] = [
  ...networkNodes.filter((node) => node.kind === "raspberry").map((node) => ({ source: node.id, target: "broker", rate: node.rate })),
  { source: "broker", target: "jetson-1", rate: 42 },
  { source: "broker", target: "jetson-2", rate: 67 },
  { source: "jetson-1", target: "jetson-2", rate: 9 },
];

export const abstractionRules = [
  { signal: "nozzle.temp > 185°C\nAND imu.rms stable", rule: "MSEG · 8.2 s segment", activity: "PRINT_PART", confidence: 98.8, source: "EMQX001" },
  { signal: "imu.impact > 3.8\nAND vision.part = true", rule: "Temporal join · ±1.5 s", activity: "REMOVE_FROM_BED", confidence: 96.4, source: "EMQX001 + JETSON-01" },
  { signal: "joint.j3 > 3.2 A\nAND gripper.closed", rule: "State transition", activity: "ROBOT_PICK_PART", confidence: 99.1, source: "EMQX002" },
  { signal: "rgb.class = blue\nAND score > .92", rule: "Vision classification", activity: "CHECK_COLOR", confidence: 97.6, source: "EMQX003 + JETSON-01" },
  { signal: "drawer.reed = closed\nAND load Δ > 160 g", rule: "Causal window · 3.0 s", activity: "STORE_IN_DRAWER", confidence: 98.2, source: "EMQX004" },
  { signal: "surface.pressure > 1.2 kg\nAND person = true", rule: "Spatial join · zone A", activity: "HUMAN_INTERACTION", confidence: 94.7, source: "EMQX005 + JETSON-02" },
];

export const recentEvents: ActivityEvent[] = [
  { id: "ev-1", caseId: "CASE-0248", activity: "HUMAN_INTERACTION", resource: "Operator · Mia", source: "EMQX005", timestamp: "14:32:11.802", confidence: 94.7, tone: "violet" },
  { id: "ev-2", caseId: "CASE-0251", activity: "REMOVE_FROM_BED", resource: "Printer P-01", source: "EMQX001", timestamp: "14:32:08.441", confidence: 96.4, tone: "amber" },
  { id: "ev-3", caseId: "CASE-0250", activity: "STORE_IN_DRAWER", resource: "Drawer D-04", source: "EMQX004", timestamp: "14:32:04.193", confidence: 98.2, tone: "green" },
  { id: "ev-4", caseId: "CASE-0251", activity: "PRINT_PART", resource: "Printer P-01", source: "EMQX001", timestamp: "14:31:58.990", confidence: 98.8, tone: "blue" },
  { id: "ev-5", caseId: "CASE-0250", activity: "CHECK_COLOR", resource: "Color station", source: "EMQX003", timestamp: "14:31:57.014", confidence: 97.6, tone: "cyan" },
];

export const processCases: ProcessCase[] = [
  { id: "CASE-0251", object: "Part TH-91B7", started: "14:22:18", duration: "09:54", status: "running", confidence: 97.8, variant: "V1 · Standard", events: ["Print part", "Remove from bed"] },
  { id: "CASE-0250", object: "Part TH-91B6", started: "14:17:06", duration: "14:58", status: "running", confidence: 98.4, variant: "V1 · Standard", events: ["Print part", "Remove from bed", "Robot pickup", "Check color", "Store in drawer"] },
  { id: "CASE-0249", object: "Part TH-91B5", started: "14:11:29", duration: "18:44", status: "attention", confidence: 91.2, variant: "V2 · Color recheck", events: ["Print part", "Remove from bed", "Robot pickup", "Check color", "Color recheck", "Store in drawer"] },
  { id: "CASE-0248", object: "Part TH-91B4", started: "14:03:12", duration: "28:59", status: "complete", confidence: 96.9, variant: "V1 · Standard", events: ["Print part", "Remove from bed", "Robot pickup", "Check color", "Store in drawer", "Retrieve part", "Place on surface", "Human interaction"] },
];

export const evidenceMatrix = [
  { label: "CASE-0251", scores: [0.99, 0.93, 0.97, 0.96] },
  { label: "CASE-0250", scores: [0.98, 0.96, 0.99, 0.97] },
  { label: "CASE-0249", scores: [0.91, 0.88, 0.94, 0.92] },
  { label: "CASE-0248", scores: [0.97, 0.95, 0.96, 0.99] },
];

export const activityColors: Record<string, string> = {
  "Print part": "#5e81ac",
  "Remove from bed": "#d08770",
  "Robot pickup": "#88c0d0",
  "Check color": "#b48ead",
  "Color recheck": "#bf616a",
  "Store in drawer": "#a3be8c",
  "Retrieve part": "#8fbcbb",
  "Place on surface": "#81a1c1",
  "Human interaction": "#ebcb8b",
};
