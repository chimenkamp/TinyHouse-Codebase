import { useMemo, useState, type DragEvent } from "react";
import type { MovementStep } from "../lib/types";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

function stepLabel(index: number, name: string | undefined): string {
  return `${index + 1}. ${name ?? "Missing position"}`;
}

export function MovementOrderEditor() {
  const [newOrderName, setNewOrderName] = useState("");
  const savedPositions = useDigitalTwinStore((state) => state.savedPositions);
  const movementOrders = useDigitalTwinStore((state) => state.movementOrders);
  const selectedOrderId = useDigitalTwinStore((state) => state.selectedOrderId);
  const executionState = useDigitalTwinStore((state) => state.executionState);
  const createMovementOrder = useDigitalTwinStore((state) => state.createMovementOrder);
  const selectMovementOrder = useDigitalTwinStore((state) => state.selectMovementOrder);
  const updateMovementOrder = useDigitalTwinStore((state) => state.updateMovementOrder);
  const duplicateMovementOrder = useDigitalTwinStore((state) => state.duplicateMovementOrder);
  const deleteMovementOrder = useDigitalTwinStore((state) => state.deleteMovementOrder);
  const addPositionToOrder = useDigitalTwinStore((state) => state.addPositionToOrder);
  const removeStepFromOrder = useDigitalTwinStore((state) => state.removeStepFromOrder);
  const reorderOrderStep = useDigitalTwinStore((state) => state.reorderOrderStep);
  const updateMovementStep = useDigitalTwinStore((state) => state.updateMovementStep);
  const validateMovementOrder = useDigitalTwinStore((state) => state.validateMovementOrder);
  const previewMovementStep = useDigitalTwinStore((state) => state.previewMovementStep);
  const simulateMovementOrder = useDigitalTwinStore((state) => state.simulateMovementOrder);
  const executeMovementOrder = useDigitalTwinStore((state) => state.executeMovementOrder);
  const pauseExecution = useDigitalTwinStore((state) => state.pauseExecution);
  const resumeExecution = useDigitalTwinStore((state) => state.resumeExecution);
  const stopExecution = useDigitalTwinStore((state) => state.stopExecution);

  const selectedOrder = movementOrders.find((order) => order.id === selectedOrderId) ?? null;
  const validation = selectedOrder ? validateMovementOrder(selectedOrder.id) : { valid: false, errors: ["Create or select a movement order"] };
  const positionsById = useMemo(() => new Map(savedPositions.map((position) => [position.id, position])), [savedPositions]);

  const createOrder = () => {
    const id = createMovementOrder(newOrderName);
    setNewOrderName("");
    selectMovementOrder(id);
  };

  const confirmAndExecute = () => {
    if (!selectedOrder) return;
    const ok = window.confirm(`Run "${selectedOrder.name}" on the real PAROL6 arm? The robot must be connected, homed, enabled, and clear of errors.`);
    if (ok) void executeMovementOrder(selectedOrder.id);
  };

  const onStepDrop = (event: DragEvent<HTMLDivElement>, targetIndex: number) => {
    if (!selectedOrder) return;
    const stepId = event.dataTransfer.getData("application/parol6-step");
    if (stepId) reorderOrderStep(selectedOrder.id, stepId, targetIndex);
  };

  return (
    <>
      <section className="panel">
        <h2>Movement Order Editor</h2>
        <div className="stack">
          <div className="inputLine">
            <input
              type="text"
              value={newOrderName}
              placeholder={`Movement Order ${movementOrders.length + 1}`}
              onChange={(event) => setNewOrderName(event.target.value)}
            />
            <button className="primary" onClick={createOrder}>New</button>
          </div>
          <select value={selectedOrderId ?? ""} onChange={(event) => selectMovementOrder(event.target.value || null)}>
            <option value="">Select an order</option>
            {movementOrders.map((order) => (
              <option key={order.id} value={order.id}>{order.name}</option>
            ))}
          </select>
        </div>
      </section>

      {selectedOrder ? (
        <>
          <section className="panel">
            <div className="panelHeader">
              <h2>Order Details</h2>
              <span className={validation.valid ? "modePill ok" : "modePill warn"}>{validation.valid ? "Valid" : "Needs work"}</span>
            </div>
            <div className="stack">
              <input
                type="text"
                value={selectedOrder.name}
                onChange={(event) => updateMovementOrder(selectedOrder.id, { name: event.target.value })}
              />
              <textarea
                value={selectedOrder.description ?? ""}
                placeholder="Short description"
                onChange={(event) => updateMovementOrder(selectedOrder.id, { description: event.target.value })}
              />
              {!validation.valid ? (
                <div className="validationBox">
                  {validation.errors.map((error) => <div key={error}>{error}</div>)}
                </div>
              ) : null}
              <div className="buttonGrid">
                <button onClick={() => void simulateMovementOrder(selectedOrder.id)} disabled={!selectedOrder.steps.length}>Simulate</button>
                <button className="danger" onClick={confirmAndExecute} disabled={!validation.valid}>Run Real Arm</button>
                <button onClick={() => duplicateMovementOrder(selectedOrder.id)}>Duplicate</button>
                <button className="danger" onClick={() => deleteMovementOrder(selectedOrder.id)}>Delete</button>
              </div>
              <div className="buttonRow">
                <button onClick={pauseExecution} disabled={executionState.mode !== "simulating" && executionState.mode !== "executing"}>Pause</button>
                <button onClick={resumeExecution} disabled={executionState.mode !== "paused"}>Resume</button>
                <button className="danger" onClick={stopExecution} disabled={executionState.mode === "idle"}>Stop</button>
              </div>
            </div>
          </section>

          <section className="panel">
            <h2>Available Positions</h2>
            <div className="savedList compact">
              {savedPositions.length ? savedPositions.map((position) => (
                <div key={position.id} className="savedItem">
                  <strong>{position.name}</strong>
                  <code>{position.jointValues.map((angle) => angle.toFixed(1)).join(", ")}</code>
                  <button onClick={() => addPositionToOrder(selectedOrder.id, position.id)}>Add Step</button>
                </div>
              )) : <div className="emptyState">Save poses in the Pose Editor first.</div>}
            </div>
          </section>

          <section className="panel">
            <h2>Movement Sequence</h2>
            <div className="sequenceList">
              {selectedOrder.steps.length ? selectedOrder.steps.map((step, index) => {
                const position = positionsById.get(step.positionId);
                const active = executionState.activeStepId === step.id;
                return (
                  <div
                    key={step.id}
                    className={active ? "stepCard active" : "stepCard"}
                    draggable
                    onDragStart={(event) => event.dataTransfer.setData("application/parol6-step", step.id)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => onStepDrop(event, index)}
                  >
                    <div className="stepHeader">
                      <strong>{stepLabel(index, position?.name)}</strong>
                      <span>drag to reorder</span>
                    </div>
                    <label>
                      <span>Position</span>
                      <select
                        value={step.positionId}
                        onChange={(event) => updateMovementStep(selectedOrder.id, step.id, { positionId: event.target.value })}
                      >
                        {savedPositions.map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>{candidate.name}</option>
                        ))}
                      </select>
                    </label>
                    <label className="rangeRow">
                      <span>Speed</span>
                      <input
                        type="range"
                        min="0.05"
                        max="1"
                        step="0.05"
                        value={step.speed}
                        onChange={(event) => updateStep(selectedOrder.id, step.id, { speed: Number(event.target.value) }, updateMovementStep)}
                      />
                      <strong>{Math.round(step.speed * 100)}%</strong>
                    </label>
                    <details>
                      <summary>Movement parameters</summary>
                      <div className="stepParams">
                        <label>
                          <span>Acceleration</span>
                          <input
                            type="number"
                            min="0.1"
                            max="5"
                            step="0.1"
                            value={step.acceleration}
                            onChange={(event) => updateStep(selectedOrder.id, step.id, { acceleration: Number(event.target.value) }, updateMovementStep)}
                          />
                        </label>
                        <label>
                          <span>Delay after reach</span>
                          <input
                            type="number"
                            min="0"
                            step="50"
                            value={step.delayMs}
                            onChange={(event) => updateStep(selectedOrder.id, step.id, { delayMs: Number(event.target.value) }, updateMovementStep)}
                          />
                        </label>
                        <label>
                          <span>Interpolation</span>
                          <select
                            value={step.interpolation}
                            onChange={(event) => updateStep(selectedOrder.id, step.id, { interpolation: event.target.value as MovementStep["interpolation"] }, updateMovementStep)}
                          >
                            <option value="joint">Joint</option>
                            <option value="linear">Linear</option>
                          </select>
                        </label>
                        <label>
                          <span>Gripper</span>
                          <select
                            value={step.gripperAction}
                            onChange={(event) => updateStep(selectedOrder.id, step.id, { gripperAction: event.target.value as MovementStep["gripperAction"] }, updateMovementStep)}
                          >
                            <option value="none">None</option>
                            <option value="open">Open</option>
                            <option value="close">Close</option>
                          </select>
                        </label>
                      </div>
                    </details>
                    <div className="buttonRow">
                      <button onClick={() => previewMovementStep(selectedOrder.id, index)}>Preview Step</button>
                      <button className="danger" onClick={() => removeStepFromOrder(selectedOrder.id, step.id)}>Remove</button>
                    </div>
                  </div>
                );
              }) : <div className="emptyState">Add saved positions to build a movement order.</div>}
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}

function updateStep(
  orderId: string,
  stepId: string,
  patch: Partial<Omit<MovementStep, "id">>,
  updater: (orderId: string, stepId: string, patch: Partial<Omit<MovementStep, "id">>) => void
) {
  updater(orderId, stepId, patch);
}
