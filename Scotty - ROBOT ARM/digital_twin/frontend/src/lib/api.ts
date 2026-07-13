import type { CommandResult, ModelInfo, PoseResult, RobotStatus, ValidationResult } from "./types";

const jsonHeaders = { "Content-Type": "application/json" };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export const DigitalTwinApi = {
  model: () => api<ModelInfo>("/api/model"),
  status: () => api<RobotStatus>("/api/status"),
  connect: () => api<RobotStatus>("/api/connect", { method: "POST", headers: jsonHeaders, body: JSON.stringify({}) }),
  disconnect: () => api<RobotStatus>("/api/disconnect", { method: "POST" }),
  setMode: (payload: { live_enabled?: boolean; movement_enabled?: boolean }) =>
    api<RobotStatus>("/api/mode", { method: "POST", headers: jsonHeaders, body: JSON.stringify(payload) }),
  validate: (angles_deg: number[]) =>
    api<ValidationResult>("/api/validate", { method: "POST", headers: jsonHeaders, body: JSON.stringify({ angles_deg }) }),
  fk: (angles_deg: number[]) =>
    api<PoseResult>("/api/fk", { method: "POST", headers: jsonHeaders, body: JSON.stringify({ angles_deg }) }),
  ik: (pose_m_rad: number[], seed_angles_deg?: number[]) =>
    api<PoseResult>("/api/ik", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ pose_m_rad, seed_angles_deg })
    }),
  home: () => api<CommandResult>("/api/home", { method: "POST" }),
  resume: () => api<CommandResult>("/api/resume", { method: "POST" }),
  halt: () => api<CommandResult>("/api/halt", { method: "POST" }),
  moveJoints: (angles_deg: number[], speed_scale: number, wait = false) =>
    api<CommandResult>("/api/move-joints", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ angles_deg, speed_scale, wait })
    }),
  movePose: (pose_m_rad: number[], seed_angles_deg: number[], speed_scale: number, wait = false) =>
    api<CommandResult>("/api/move-pose", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ pose_m_rad, seed_angles_deg, speed_scale, wait })
    })
};
