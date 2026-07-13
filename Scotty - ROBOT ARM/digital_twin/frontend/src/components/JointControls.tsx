import { useDigitalTwinStore } from "../store/digitalTwinStore";

export function JointControls() {
  const model = useDigitalTwinStore((state) => state.model);
  const status = useDigitalTwinStore((state) => state.status);
  const previewAngles = useDigitalTwinStore((state) => state.previewAngles);
  const selectedJoint = useDigitalTwinStore((state) => state.selectedJoint);
  const setSelectedJoint = useDigitalTwinStore((state) => state.setSelectedJoint);
  const setJointPreview = useDigitalTwinStore((state) => state.setJointPreview);

  if (!model) {
    return <section className="panel"><h2>Joints</h2><p>Loading joint limits...</p></section>;
  }

  return (
    <section className="panel jointsPanel">
      <h2>Joint Targets</h2>
      {model.joint_limits.map((limit, index) => {
        const actual = status?.angles_deg?.[index];
        const target = previewAngles[index] ?? 0;
        const selected = selectedJoint === limit.name;
        return (
          <div className={selected ? "jointRow selected" : "jointRow"} key={limit.name}>
            <button className="jointName" onClick={() => setSelectedJoint(selected ? null : limit.name)}>{limit.name}</button>
            <div className="jointValues">
              <span>actual <strong>{actual === undefined ? "-" : actual.toFixed(2)} deg</strong></span>
              <span>target <strong>{target.toFixed(2)} deg</strong></span>
            </div>
            <input
              type="range"
              min={limit.lower_deg}
              max={limit.upper_deg}
              step="0.1"
              value={target}
              onChange={(event) => setJointPreview(index, Number(event.target.value))}
            />
            <div className="jointInputLine">
              <input
                type="number"
                min={limit.lower_deg}
                max={limit.upper_deg}
                step="0.1"
                value={target.toFixed(1)}
                onChange={(event) => setJointPreview(index, Number(event.target.value))}
              />
              <code>{limit.lower_deg.toFixed(1)} .. {limit.upper_deg.toFixed(1)}</code>
            </div>
          </div>
        );
      })}
    </section>
  );
}

