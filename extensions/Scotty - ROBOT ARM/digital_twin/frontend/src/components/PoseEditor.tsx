import { useState } from "react";
import { selectors, useDigitalTwinStore } from "../store/digitalTwinStore";
import { JointControls } from "./JointControls";

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

export function PoseEditor() {
  const [positionName, setPositionName] = useState("");
  const [positionDescription, setPositionDescription] = useState("");
  const status = useDigitalTwinStore((state) => state.status);
  const log = useDigitalTwinStore((state) => state.log);
  const loading = useDigitalTwinStore((state) => state.loading);
  const speedScale = useDigitalTwinStore((state) => state.speedScale);
  const anchorPose = useDigitalTwinStore((state) => state.anchorPose);
  const anchorTransformMode = useDigitalTwinStore((state) => state.anchorTransformMode);
  const applyAnchorOnRelease = useDigitalTwinStore((state) => state.applyAnchorOnRelease);
  const savedPositions = useDigitalTwinStore((state) => state.savedPositions);
  const connect = useDigitalTwinStore((state) => state.connect);
  const disconnect = useDigitalTwinStore((state) => state.disconnect);
  const setLive = useDigitalTwinStore((state) => state.setLive);
  const setMovement = useDigitalTwinStore((state) => state.setMovement);
  const setSpeedScale = useDigitalTwinStore((state) => state.setSpeedScale);
  const setAnchorRotationDeg = useDigitalTwinStore((state) => state.setAnchorRotationDeg);
  const setAnchorTransformMode = useDigitalTwinStore((state) => state.setAnchorTransformMode);
  const setApplyAnchorOnRelease = useDigitalTwinStore((state) => state.setApplyAnchorOnRelease);
  const captureLivePosition = useDigitalTwinStore((state) => state.captureLivePosition);
  const saveCurrentPosition = useDigitalTwinStore((state) => state.saveCurrentPosition);
  const updateSavedPosition = useDigitalTwinStore((state) => state.updateSavedPosition);
  const replaceSavedPositionWithCurrentPose = useDigitalTwinStore((state) => state.replaceSavedPositionWithCurrentPose);
  const deleteSavedPosition = useDigitalTwinStore((state) => state.deleteSavedPosition);
  const loadSavedPosition = useDigitalTwinStore((state) => state.loadSavedPosition);
  const exportSavedPositions = useDigitalTwinStore((state) => state.exportSavedPositions);
  const home = useDigitalTwinStore((state) => state.home);
  const halt = useDigitalTwinStore((state) => state.halt);
  const dispatchMove = useDigitalTwinStore((state) => state.dispatchMove);
  const solveAnchorTarget = useDigitalTwinStore((state) => state.solveAnchorTarget);
  const moveToAnchor = useDigitalTwinStore((state) => state.moveToAnchor);
  const resetPreviewToTelemetry = useDigitalTwinStore((state) => state.resetPreviewToTelemetry);
  const canLiveMove = selectors.canSendLiveMove(status);

  const exportPositions = () => {
    const blob = new Blob([exportSavedPositions()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `parol6-positions-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const savePosition = () => {
    saveCurrentPosition(positionName, positionDescription);
    setPositionName("");
    setPositionDescription("");
  };

  const editingMode = status?.live_enabled ? "Live robot pose" : "Simulated pose";

  return (
    <>
      <section className="panel">
        <div className="panelHeader">
          <div>
            <h2>Pose Editor</h2>
            <span className={status?.live_enabled ? "modePill live" : "modePill"}>{editingMode}</span>
          </div>
        </div>

        <div className="buttonGrid">
          <button onClick={() => void connect()} disabled={loading || status?.connected}>Connect</button>
          <button onClick={() => void disconnect()} disabled={!status?.connected}>Disconnect</button>
          <button onClick={() => void home()} disabled={!status?.connected}>Home</button>
          <button className="danger" onClick={() => void halt()} disabled={!status?.connected}>HALT</button>
        </div>

        <label className="switchRow">
          <span>Track live robot pose</span>
          <input
            type="checkbox"
            checked={Boolean(status?.live_enabled)}
            onChange={(event) => void setLive(event.target.checked)}
          />
        </label>
        <label className="switchRow">
          <span>Allow real movement</span>
          <input
            type="checkbox"
            checked={Boolean(status?.movement_enabled)}
            disabled={!status?.live_enabled}
            onChange={(event) => void setMovement(event.target.checked)}
          />
        </label>

        {status?.live_enabled ? (
          <div className="warningBox">
            Live tracking is active. Real movement still requires homing, movement enable, clear errors, and explicit commands.
          </div>
        ) : null}

        <label className="rangeRow">
          <span>Speed limit</span>
          <input
            type="range"
            min="0.05"
            max="1"
            step="0.05"
            value={speedScale}
            onChange={(event) => setSpeedScale(Number(event.target.value))}
          />
          <strong>{Math.round(speedScale * 100)}%</strong>
        </label>

        <div className="buttonGrid">
          <button onClick={resetPreviewToTelemetry}>Use Telemetry</button>
          <button onClick={captureLivePosition} disabled={!status?.angles_deg}>Capture Live Pose</button>
          <button onClick={() => void dispatchMove()} disabled={!canLiveMove}>Send Joint Target</button>
          <button className="primary" onClick={() => void moveToAnchor()} disabled={!canLiveMove}>Send TCP Anchor</button>
        </div>
      </section>

      <section className="panel">
        <h2>TCP Anchor</h2>
        <code>
          x {anchorPose[0].toFixed(3)} m · y {anchorPose[1].toFixed(3)} m · z {anchorPose[2].toFixed(3)} m
        </code>
        <div className="segmentedRow">
          <button className={anchorTransformMode === "translate" ? "active" : ""} onClick={() => setAnchorTransformMode("translate")}>Move</button>
          <button className={anchorTransformMode === "rotate" ? "active" : ""} onClick={() => setAnchorTransformMode("rotate")}>Rotate</button>
        </div>
        <div className="rotationGrid">
          {["RX", "RY", "RZ"].map((axis, index) => (
            <label key={axis}>
              <span>{axis}</span>
              <input
                type="number"
                step="1"
                value={((anchorPose[3 + index] * 180) / Math.PI).toFixed(1)}
                onChange={(event) => setAnchorRotationDeg(index, Number(event.target.value))}
              />
            </label>
          ))}
        </div>
        <div className="buttonGrid">
          <button onClick={() => void solveAnchorTarget()}>Solve IK Preview</button>
          <button className="primary" onClick={() => void moveToAnchor()} disabled={!canLiveMove}>Send Anchor</button>
        </div>
        <label className="switchRow">
          <span>Apply anchor on release</span>
          <input
            type="checkbox"
            checked={applyAnchorOnRelease}
            disabled={!canLiveMove}
            onChange={(event) => setApplyAnchorOnRelease(event.target.checked)}
          />
        </label>
      </section>

      <section className="panel">
        <h2>Save Current Pose</h2>
        <div className="stack">
          <input
            type="text"
            value={positionName}
            placeholder={`Position ${savedPositions.length + 1}`}
            onChange={(event) => setPositionName(event.target.value)}
          />
          <textarea
            value={positionDescription}
            placeholder="Notes or description"
            onChange={(event) => setPositionDescription(event.target.value)}
          />
          <div className="buttonGrid">
            <button className="primary" onClick={savePosition}>Save Pose</button>
            <button onClick={exportPositions} disabled={!savedPositions.length}>Export</button>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Saved Positions</h2>
        <div className="savedList">
          {savedPositions.length ? savedPositions.map((position) => (
            <div key={position.id} className="savedItem">
              <input
                type="text"
                value={position.name}
                onChange={(event) => updateSavedPosition(position.id, { name: event.target.value })}
              />
              <textarea
                value={position.description ?? ""}
                placeholder="Notes"
                onChange={(event) => updateSavedPosition(position.id, { description: event.target.value })}
              />
              <code>{position.jointValues.map((angle) => angle.toFixed(1)).join(", ")}</code>
              <span className="mutedLine">{position.source ?? "simulated"} · updated {formatDate(position.updatedAt)}</span>
              <div className="buttonRow">
                <button onClick={() => loadSavedPosition(position.id)}>Load</button>
                <button onClick={() => replaceSavedPositionWithCurrentPose(position.id)}>Update Pose</button>
                <button className="danger" onClick={() => deleteSavedPosition(position.id)}>Delete</button>
              </div>
            </div>
          )) : <div className="emptyState">No saved positions yet.</div>}
        </div>
      </section>

      <JointControls />

      <section className="panel">
        <h2>Robot Readout</h2>
        <div className="statusReadout">
          <div><span>Pose</span><code>{status?.pose ? status.pose.map((v) => v.toFixed(1)).join(" ") : "-"}</code></div>
          <div><span>Activity</span><code>{status?.activity ? JSON.stringify(status.activity) : "-"}</code></div>
          <div><span>Message</span><code>{status?.message || "-"}</code></div>
        </div>
        <div className="logBox">
          {log.length ? log.map((line) => <div key={line}>{line}</div>) : <div>No commands yet.</div>}
        </div>
      </section>
    </>
  );
}
