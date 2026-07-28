import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  Boxes,
  ChevronDown,
  CircleGauge,
  Database,
  GitMerge,
  HelpCircle,
  LayoutDashboard,
  Network,
  Pause,
  Play,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Timer,
  TrendingUp,
  WandSparkles,
  Workflow,
  Zap,
} from "lucide-react";
import { AbstractionPanel } from "./components/AbstractionPanel";
import { BpmnProcessModel } from "./components/BpmnProcessModel";
import { CorrelationPanel } from "./components/CorrelationPanel";
import { NetworkGraph } from "./components/NetworkGraph";
import { SensorStream, StreamBridge } from "./components/SensorStream";

const pipelineSteps = [
  { id: "pipeline", label: "Environment", meta: "9 edge nodes", icon: Network, color: "blue" },
  { id: "pipeline", label: "Preprocessing", meta: "98.7% retained", icon: ShieldCheck, color: "cyan" },
  { id: "abstraction", label: "Abstraction", meta: "9 activities", icon: WandSparkles, color: "violet" },
  { id: "correlation", label: "Case correlation", meta: "24 active cases", icon: GitMerge, color: "green" },
  { id: "model", label: "Process model", meta: "3 variants", icon: Workflow, color: "amber" },
];

const sectionIds = ["overview", "pipeline", "abstraction", "correlation", "model"];

function formatTime(date: Date) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function App() {
  const [running, setRunning] = useState(true);
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(new Date());
  const [selectedNode, setSelectedNode] = useState("pi-6");
  const [selectedCase, setSelectedCase] = useState("CASE-0248");
  const [activeSection, setActiveSection] = useState("overview");
  const [toast, setToast] = useState("");

  useEffect(() => {
    const clock = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(clock);
  }, []);

  useEffect(() => {
    if (!running) return;
    const simulation = window.setInterval(() => {
      setTick((value) => value + 1 + Math.floor(Math.random() * 2));
    }, 1_650);
    return () => window.clearInterval(simulation);
  }, [running]);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: "-15% 0px -65% 0px", threshold: [0.05, 0.2, 0.5] });
    sectionIds.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const targetId = window.location.hash.slice(1);
    if (!sectionIds.includes(targetId)) return;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2_800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const kpis = useMemo(() => [
    { label: "Ingest rate", value: `${(109.2 + (tick % 8) * 0.34).toFixed(1)}`, unit: "events/s", delta: "+4.8%", icon: Zap, tone: "blue", bars: [42, 54, 47, 63, 58, 72, 69, 82, 76, 91] },
    { label: "Data quality", value: `${(98.7 + (tick % 3) * 0.04).toFixed(1)}%`, unit: "context-aware", delta: "+0.6%", icon: ShieldCheck, tone: "green", bars: [74, 78, 81, 79, 86, 84, 91, 89, 94, 97] },
    { label: "Active cases", value: `${24 + (tick % 4 === 3 ? 1 : 0)}`, unit: "6 in progress", delta: "3 queued", icon: Boxes, tone: "violet", bars: [38, 42, 57, 51, 62, 66, 58, 73, 70, 79] },
    { label: "Conformance", value: "96.2%", unit: "fitness score", delta: "+1.2%", icon: CircleGauge, tone: "amber", bars: [82, 86, 84, 88, 85, 91, 90, 92, 94, 96] },
  ], [tick]);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const generateTrace = () => {
    const caseNumber = 252 + Math.floor(Math.random() * 748);
    const segmentCount = 7 + Math.floor(Math.random() * 5);
    setTick((value) => value + 2 + Math.floor(Math.random() * 4));
    setSelectedCase("CASE-0251");
    setToast(`CASE-${String(caseNumber).padStart(4, "0")} generated · ${segmentCount} sensor segments correlated`);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand" onClick={() => scrollTo("overview")} role="button" tabIndex={0}>
          <div className="brand-mark"><span /><i /></div>
          <div><strong>NORTHSTAR</strong><span>Process Intelligence</span></div>
        </div>

        <nav className="primary-nav" aria-label="Dashboard sections">
          <span className="nav-section-label">Workspace</span>
          <button type="button" className={activeSection === "overview" ? "active" : ""} onClick={() => scrollTo("overview")}><LayoutDashboard size={18} /><span>Overview</span></button>
          <button type="button" className={activeSection === "pipeline" ? "active" : ""} onClick={() => scrollTo("pipeline")}><Activity size={18} /><span>Live pipeline</span><i className="nav-live" /></button>
          <button type="button" className={activeSection === "abstraction" ? "active" : ""} onClick={() => scrollTo("abstraction")}><WandSparkles size={18} /><span>Abstraction</span></button>
          <button type="button" className={activeSection === "correlation" ? "active" : ""} onClick={() => scrollTo("correlation")}><GitMerge size={18} /><span>Case correlation</span><em>24</em></button>
          <button type="button" className={activeSection === "model" ? "active" : ""} onClick={() => scrollTo("model")}><Workflow size={18} /><span>Process model</span></button>
          <span className="nav-section-label secondary">Manage</span>
          <button type="button"><Database size={18} /><span>Data sources</span></button>
          <button type="button"><Settings size={18} /><span>Pipeline settings</span></button>
        </nav>

        <div className="sidebar-status">
          <div className="edge-cluster-icon"><Network size={18} /></div>
          <div><span>Edge cluster</span><strong><i /> All systems normal</strong></div>
          <ChevronDown size={15} />
        </div>
        <div className="sidebar-user">
          <div className="avatar">CI</div>
          <div><strong>Christian I.</strong><span>Process engineer</span></div>
          <button type="button" aria-label="Open user menu"><ChevronDown size={15} /></button>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>TinyHouse Lab</span><i>/</i><strong>Production Cell 01</strong></div>
          <div className="topbar-actions">
            <label className="global-search"><Search size={16} /><input aria-label="Search dashboard" placeholder="Search cases, devices…" /><kbd>⌘ K</kbd></label>
            <button type="button" className="icon-button" aria-label="Notifications"><Bell size={18} /><i /></button>
            <button type="button" className="icon-button" aria-label="Help"><HelpCircle size={18} /></button>
          </div>
        </header>

        <main>
          <section className="hero" id="overview">
            <div>
              <span className="eyebrow">Operational process twin</span>
              <h1>IoT Process Mining</h1>
              <p>From raw edge signals to a living production process model.</p>
            </div>
            <div className="hero-actions">
              <div className="simulation-clock"><span><i className={running ? "running" : ""} /> {running ? "Live simulation" : "Simulation paused"}</span><strong>{formatTime(now)} <small>CEST</small></strong></div>
              <button type="button" className="secondary-button" onClick={() => setRunning((value) => !value)}>{running ? <Pause size={16} /> : <Play size={16} />}{running ? "Pause" : "Resume"}</button>
              <button type="button" className="primary-button" onClick={generateTrace}><Sparkles size={16} /> Generate trace</button>
            </div>
          </section>

          <section className="pipeline-rail" aria-label="Process mining pipeline stages">
            {pipelineSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <div className="pipeline-step-wrap" key={`${step.label}-${index}`}>
                  <button type="button" className={`pipeline-step ${step.color}`} onClick={() => scrollTo(step.id)}>
                    <i className="stage-number">0{index + 1}</i>
                    <span className="stage-icon"><Icon size={19} /></span>
                    <span><strong>{step.label}</strong><small>{step.meta}</small></span>
                    <i className="stage-check">✓</i>
                  </button>
                  {index < pipelineSteps.length - 1 && <div className="stage-connector"><i /><i /><i /></div>}
                </div>
              );
            })}
          </section>

          <section className="kpi-grid" aria-label="Pipeline metrics">
            {kpis.map((kpi) => {
              const Icon = kpi.icon;
              return (
                <article className={`kpi-card ${kpi.tone}`} key={kpi.label}>
                  <div className="kpi-top"><span>{kpi.label}</span><i><Icon size={17} /></i></div>
                  <div className="kpi-value"><strong>{kpi.value}</strong><span>{kpi.unit}</span></div>
                  <div className="mini-bars">{kpi.bars.map((bar, index) => <i key={index} style={{ height: `${bar}%` }} />)}</div>
                  <div className="kpi-foot"><TrendingUp size={13} /><strong>{kpi.delta}</strong><span>vs previous shift</span></div>
                </article>
              );
            })}
          </section>

          <section className="dashboard-section" id="pipeline">
            <div className="section-heading">
              <div className="section-title"><span>01—02</span><div><h2>Environment & preprocessing</h2><p>Edge topology and context-aware signal cleansing</p></div></div>
              <div className="section-meta"><span><i /> 9/9 online</span><span>109 msg/s</span><span>42 ms latency</span></div>
            </div>
            <div className="pipeline-live-grid">
              <article className="dashboard-card network-card">
                <div className="card-heading"><div><span className="eyebrow">Physical environment</span><h3>Edge network topology</h3></div><span className="card-badge"><i /> Live</span></div>
                <NetworkGraph selectedNode={selectedNode} onSelectNode={setSelectedNode} tick={tick} />
              </article>
              <StreamBridge />
              <article className="dashboard-card stream-card">
                <div className="card-heading"><div><span className="eyebrow">Context-aware preprocessing</span><h3>Sensor streams & outliers</h3></div><div className="quality-ring"><span>98.7<small>%</small></span><em>quality</em></div></div>
                <SensorStream selectedNode={selectedNode} tick={tick} />
              </article>
            </div>
          </section>

          <section className="dashboard-section" id="abstraction">
            <div className="section-heading">
              <div className="section-title"><span>03</span><div><h2>Activity abstraction</h2><p>Transforming multivariate sensor behavior into semantic events</p></div></div>
              <div className="section-meta"><span><i /> MSEG active</span><span>9 activity classes</span><span>97.4% avg confidence</span></div>
            </div>
            <article className="dashboard-card section-card">
              <AbstractionPanel tick={tick} />
            </article>
          </section>

          <section className="dashboard-section" id="correlation">
            <div className="section-heading">
              <div className="section-title"><span>04</span><div><h2>Case correlation</h2><p>Linking distributed events to physical production objects</p></div></div>
              <div className="section-meta"><span><i /> Online correlator</span><span>4 evidence dimensions</span><span>24 open cases</span></div>
            </div>
            <article className="dashboard-card section-card">
              <CorrelationPanel selectedCase={selectedCase} onSelectCase={setSelectedCase} />
            </article>
          </section>

          <section className="dashboard-section model-section" id="model">
            <div className="section-heading">
              <div className="section-title"><span>05</span><div><h2>Discovered process model</h2><p>BPMN model derived from correlated production traces</p></div></div>
              <div className="section-meta"><span><i /> Model current</span><span>96.2% fitness</span><span>89.4% precision</span></div>
            </div>
            <article className="dashboard-card section-card bpmn-card">
              <BpmnProcessModel tick={tick} />
            </article>
          </section>

          <footer className="dashboard-footer"><span>NORTHSTAR mock environment · No live systems connected</span><span>Generated locally · Nord UI system</span></footer>
        </main>
      </div>

      {toast && <div className="toast"><span><Sparkles size={16} /></span><div><strong>New trace simulated</strong><p>{toast}</p></div></div>}
    </div>
  );
}

export default App;
