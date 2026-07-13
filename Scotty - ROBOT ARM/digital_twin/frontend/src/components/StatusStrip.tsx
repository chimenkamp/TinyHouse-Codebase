import type { RobotStatus } from "../lib/types";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

type Props = {
  status: RobotStatus | null;
};

function Dot({ ok }: { ok: boolean }) {
  return <span className={ok ? "dot ok" : "dot bad"} />;
}

export function StatusStrip({ status }: Props) {
  const cameraStatus = useDigitalTwinStore((state) => state.cameraStatus);
  const executionState = useDigitalTwinStore((state) => state.executionState);

  return (
    <div className="statusStrip">
      <span><Dot ok={Boolean(status?.connected)} /> Connected</span>
      <span><Dot ok={Boolean(status?.homed)} /> Homed</span>
      <span><Dot ok={Boolean(status?.movement_enabled)} /> Enabled</span>
      <span><Dot ok={!status?.estop} /> E-stop</span>
      <span><Dot ok={!status?.error} /> Error</span>
      <span><Dot ok={cameraStatus === "ready"} /> Camera</span>
      <span><Dot ok={executionState.mode !== "error"} /> {executionState.mode}</span>
      <strong>{status?.live_enabled ? "LIVE" : "SIM"}</strong>
    </div>
  );
}
