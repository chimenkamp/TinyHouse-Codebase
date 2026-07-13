import { selectors, useDigitalTwinStore } from "../store/digitalTwinStore";

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

export function MovementOrderLibrary({ onOpenEditor }: { onOpenEditor: () => void }) {
  const status = useDigitalTwinStore((state) => state.status);
  const savedPositions = useDigitalTwinStore((state) => state.savedPositions);
  const movementOrders = useDigitalTwinStore((state) => state.movementOrders);
  const selectMovementOrder = useDigitalTwinStore((state) => state.selectMovementOrder);
  const duplicateMovementOrder = useDigitalTwinStore((state) => state.duplicateMovementOrder);
  const deleteMovementOrder = useDigitalTwinStore((state) => state.deleteMovementOrder);
  const validateMovementOrder = useDigitalTwinStore((state) => state.validateMovementOrder);
  const simulateMovementOrder = useDigitalTwinStore((state) => state.simulateMovementOrder);
  const executeMovementOrder = useDigitalTwinStore((state) => state.executeMovementOrder);

  const openOrder = (id: string) => {
    selectMovementOrder(id);
    onOpenEditor();
  };

  const confirmAndRun = (id: string, name: string) => {
    const validation = validateMovementOrder(id);
    if (!validation.valid) return;
    const ok = window.confirm(`Execute "${name}" on the real PAROL6 arm? Simulation is safer; only continue if the workspace is clear.`);
    if (ok) void executeMovementOrder(id);
  };

  return (
    <>
      <section className="panel">
        <h2>Movement Order Library</h2>
        <div className="safetyChecklist">
          <span className={status?.connected ? "ok" : ""}>Robot connection</span>
          <span className={status?.homed ? "ok" : ""}>Homing status</span>
          <span className={!status?.estop ? "ok" : ""}>Emergency stop clear</span>
          <span className={!status?.error ? "ok" : ""}>No robot error</span>
          <span className={selectors.canSendLiveMove(status) ? "ok" : ""}>Live execution gates</span>
        </div>
      </section>

      <section className="panel">
        <h2>Saved Orders</h2>
        <div className="libraryList">
          {movementOrders.length ? movementOrders.map((order) => {
            const validation = validateMovementOrder(order.id);
            const positionNames = order.steps
              .map((step) => savedPositions.find((position) => position.id === step.positionId)?.name ?? "Missing position")
              .slice(0, 3)
              .join(" → ");
            return (
              <article key={order.id} className="libraryCard">
                <div className="panelHeader">
                  <div>
                    <h3>{order.name}</h3>
                    <span className="mutedLine">{order.steps.length} steps · modified {formatDate(order.updatedAt)}</span>
                  </div>
                  <span className={validation.valid ? "modePill ok" : "modePill warn"}>{validation.valid ? "Ready" : "Invalid"}</span>
                </div>
                <p>{order.description || "No description"}</p>
                <code>{positionNames || "Empty order"}</code>
                {!validation.valid ? (
                  <div className="validationBox">
                    {validation.errors.slice(0, 3).map((error) => <div key={error}>{error}</div>)}
                  </div>
                ) : null}
                <div className="buttonGrid">
                  <button onClick={() => openOrder(order.id)}>Open</button>
                  <button onClick={() => void simulateMovementOrder(order.id)} disabled={!order.steps.length}>Simulate</button>
                  <button className="danger" onClick={() => confirmAndRun(order.id, order.name)} disabled={!validation.valid}>Run Real Arm</button>
                  <button onClick={() => duplicateMovementOrder(order.id)}>Duplicate</button>
                  <button className="danger" onClick={() => deleteMovementOrder(order.id)}>Delete</button>
                </div>
              </article>
            );
          }) : <div className="emptyState">No movement orders yet. Build one in the editor.</div>}
        </div>
      </section>
    </>
  );
}
