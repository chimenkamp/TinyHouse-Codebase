import { useEffect, useState } from "react";
import { MovementOrderEditor } from "./components/MovementOrderEditor";
import { MovementOrderLibrary } from "./components/MovementOrderLibrary";
import { NodeEditor } from "./components/NodeEditor";
import { PoseEditor } from "./components/PoseEditor";
import { RobotScene } from "./components/RobotScene";
import { StatusStrip } from "./components/StatusStrip";
import { useDigitalTwinStore } from "./store/digitalTwinStore";

type AppView = "pose" | "order" | "library" | "graph";

const VIEWS: Array<{ id: AppView; label: string }> = [
  { id: "pose", label: "Pose" },
  { id: "order", label: "Order" },
  { id: "library", label: "Library" },
  { id: "graph", label: "Graph" }
];

export function App() {
  const [view, setView] = useState<AppView>("pose");
  const loadModel = useDigitalTwinStore((state) => state.loadModel);
  const refreshStatus = useDigitalTwinStore((state) => state.refreshStatus);
  const status = useDigitalTwinStore((state) => state.status);
  const error = useDigitalTwinStore((state) => state.error);
  const executionState = useDigitalTwinStore((state) => state.executionState);

  useEffect(() => {
    void loadModel();
    void refreshStatus();
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 500);
    return () => window.clearInterval(timer);
  }, [loadModel, refreshStatus]);

  return (
    <main className="appShell">
      <section className="viewportPane">
        <div className="topBar">
          <div>
            <h1>PAROL6 Movement Programmer</h1>
            <p>Simulation-first pose, order, and conditional graph programming for the digital twin</p>
          </div>
          <StatusStrip status={status} />
        </div>
        <RobotScene />
        <div className="executionBar">
          <strong>{executionState.message}</strong>
          {executionState.errors.length ? <span>{executionState.errors[0]}</span> : null}
        </div>
        {error ? <div className="errorBanner">{error}</div> : null}
      </section>
      <aside className="sidePane">
        <nav className="viewTabs" aria-label="Digital twin views">
          {VIEWS.map((candidate) => (
            <button
              key={candidate.id}
              className={view === candidate.id ? "active" : ""}
              onClick={() => setView(candidate.id)}
            >
              {candidate.label}
            </button>
          ))}
        </nav>
        {view === "pose" ? <PoseEditor /> : null}
        {view === "order" ? <MovementOrderEditor /> : null}
        {view === "library" ? <MovementOrderLibrary onOpenEditor={() => setView("order")} /> : null}
        {view === "graph" ? <NodeEditor /> : null}
      </aside>
    </main>
  );
}
