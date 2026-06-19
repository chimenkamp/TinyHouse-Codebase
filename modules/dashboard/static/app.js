const state = {
  config: null,
  mqttSocket: null,
  shellSocket: null,
  shellSessions: new Map(),
  mqttSessions: new Map(),
  mqttLines: 0,
  healthTimer: null,
};

const MAX_TERMINAL_CHARS = 180000;

const els = {
  modeLine: document.querySelector("#modeLine"),
  tunnelStatus: document.querySelector("#tunnelStatus"),
  docsLink: document.querySelector("#docsLink"),
  refreshStatus: document.querySelector("#refreshStatus"),
  statusSummary: document.querySelector("#statusSummary"),
  scanTime: document.querySelector("#scanTime"),
  statusGrid: document.querySelector("#statusGrid"),
  mqttSummary: document.querySelector("#mqttSummary"),
  mqttConnect: document.querySelector("#mqttConnect"),
  mqttClear: document.querySelector("#mqttClear"),
  mqttLog: document.querySelector("#mqttLog"),
  shellSummary: document.querySelector("#shellSummary"),
  shellConnect: document.querySelector("#shellConnect"),
  terminalOutput: document.querySelector("#terminalOutput"),
  shellWindows: document.querySelector("#shellWindows"),
  cameraSummary: document.querySelector("#cameraSummary"),
  cameraReload: document.querySelector("#cameraReload"),
  cameraForm: document.querySelector("#cameraForm"),
  cameraFrame: document.querySelector("#cameraFrame"),
  cameraOpen: document.querySelector("#cameraOpen"),
  cameraIp: document.querySelector("#cameraIp"),
  cameraPort: document.querySelector("#cameraPort"),
  cameraScheme: document.querySelector("#cameraScheme"),
  cameraPath: document.querySelector("#cameraPath"),
  cameraUser: document.querySelector("#cameraUser"),
  cameraPassword: document.querySelector("#cameraPassword"),
};

function wsUrl(path) {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${path}`;
}

async function loadConfig() {
  const response = await fetch("/api/config");
  state.config = await response.json();
  const mode = state.config.mode === "local" ? "Management PC mode" : "SSH tunnel mode";
  const build = state.config.dashboard?.build || "unknown build";
  els.modeLine.textContent = `${mode}. Targets: ${state.config.targets.length}. Build: ${build}.`;
  els.docsLink.href = state.config.server.docs_url || "#";
  fillCameraForm(state.config.camera);
  refreshCameraFrame();
}

function fillCameraForm(camera) {
  els.cameraIp.value = camera.ip || "";
  els.cameraPort.value = camera.port || 80;
  els.cameraScheme.value = camera.scheme || "http";
  els.cameraPath.value = camera.path || "/";
  els.cameraUser.value = camera.username || "";
  els.cameraPassword.value = camera.password === "configured" ? "configured" : "";
}

async function refreshHealth() {
  renderHealth({
    label: "Checking",
    connected: false,
    detail: "Connection check is running.",
    mode: state.config?.mode || "unknown",
  });

  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    renderHealth(payload);
    return payload;
  } catch (error) {
    const payload = {
      mode: state.config?.mode || "unknown",
      connected: false,
      label: "Health check failed",
      detail: error.message,
    };
    renderHealth(payload);
    return payload;
  }
}

function renderHealth(payload) {
  const isLocal = payload.mode === "local";
  const isConnected = Boolean(payload.connected);
  const className = isLocal ? "local" : isConnected ? "ok" : "bad";
  els.tunnelStatus.className = `connection-badge ${className}`;
  els.tunnelStatus.textContent = payload.label || "Unknown";
  els.tunnelStatus.title = payload.detail || "";
}

async function refreshStatus() {
  els.refreshStatus.disabled = true;
  els.scanTime.textContent = "Scanning";

  try {
    const response = await fetch("/api/status");
    const payload = await response.json();
    if (payload.connection) {
      renderHealth(payload.connection);
    }
    renderStatus(payload);
  } catch (error) {
    els.statusSummary.textContent = `Status scan failed: ${error.message}`;
    els.scanTime.textContent = "Error";
  } finally {
    els.refreshStatus.disabled = false;
  }
}

function renderStatus(payload) {
  const targets = payload.targets || [];
  const online = targets.filter((target) => target.reachable).length;
  const connection = payload.connection;

  if (connection && payload.mode === "tunnel" && !connection.connected) {
    els.statusSummary.textContent = `SSH tunnel failed. ${connection.detail || ""}`;
  } else {
    els.statusSummary.textContent = `${online} of ${targets.length} targets are reachable.`;
  }

  els.scanTime.textContent = shortTime(payload.checked_at);
  els.statusGrid.replaceChildren(...targets.map(statusCard));
}

function shellRoute(target) {
  const mode = state.config?.mode || "tunnel";
  const ports = target.ports || [];

  if (target.shell_capable) {
    return {
      scope: target.shell_transport === "management_wsl" ? "WSL inventory" : "configured shell",
      host: target.shell_description || target.name || target.ip,
      port: target.ansible_port || "",
    };
  }

  if (!target.reachable) {
    return null;
  }

  if (isManagementTarget(target) && mode === "tunnel") {
    return ports.find((port) => port.open && port.scope === "public") || {
      scope: "tunnel",
      host: "Management PC",
      port: 22,
    };
  }

  if (target.shell_command) {
    return {
      scope: "configured shell",
      host: target.shell_command,
      port: "",
    };
  }

  if (mode === "local") {
    return ports.find((port) => port.open && port.scope !== "public" && Number(port.port) === 22);
  }

  return null;
}

function shellRouteTitle(target, route) {
  if (!route) {
    return "";
  }

  const routeText = route.port ? `${route.host}:${route.port}` : route.host || `${target.ip}:22`;
  return `Open shell for ${target.name || target.ip} via ${route.scope || "ssh"} ${routeText}`;
}

function webShellRouteTitle(target, route) {
  const suffix = shellRouteTitle(target, route);
  return suffix ? `${suffix} in the browser` : "";
}

function nativeShellRouteTitle(target, route) {
  const suffix = shellRouteTitle(target, route);
  return suffix ? `${suffix} in a local terminal` : "";
}

function mqttRoute(target) {
  const host = target.mqtt_host || target.mqtt?.host || "";
  const topics = mqttTopics(target);

  if (!target.mqtt_capable && !host && topics.length === 0) {
    return null;
  }

  return {
    host: host || "configured broker",
    port: target.mqtt_port || target.mqtt?.port || 1883,
    topics: topics.length ? topics : ["#"],
    description: target.mqtt_description || "",
  };
}

function mqttTopics(target) {
  const configured = target.mqtt_topics
    || target.mqtt_topic
    || target.mqtt?.topics
    || target.mqtt?.topic;

  if (!configured) {
    return [];
  }

  if (Array.isArray(configured)) {
    return configured.map((topic) => String(topic).trim()).filter(Boolean);
  }

  return [String(configured).trim()].filter(Boolean);
}

function mqttRouteTitle(target, route) {
  if (!route) {
    return "";
  }

  return `Subscribe to MQTT for ${target.name || target.ip} via ${route.host}:${route.port} ${route.topics.join(", ")}`;
}

function isManagementTarget(target) {
  const name = String(target.name || "").toLowerCase();
  const role = String(target.role || "").toLowerCase();
  return name.includes("management") || role === "management";
}

function statusCard(target) {
  const card = document.createElement("article");
  card.className = `status-card ${target.reachable ? "online" : "offline"}`;
  const route = shellRoute(target);
  const mqtt = mqttRoute(target);
  const portText = (target.ports || [])
    .map((port) => {
      const scope = port.scope ? `${port.scope} ` : "";
      const host = port.host ? `${port.host}:` : "";
      return `${scope}${host}${port.port}:${port.open ? "open" : "closed"}`;
    })
    .join("  ");
  const publicHost = target.public_host
    ? `<dt>Public</dt><dd>${escapeHtml(target.public_host)}</dd>`
    : "";
  const webShellButton = route
    ? `<button class="card-action-button shell-card-button web-shell-card-button" type="button" title="${escapeHtml(webShellRouteTitle(target, route))}" aria-label="${escapeHtml(webShellRouteTitle(target, route))}">WEB</button>`
    : "";
  const nativeShellButton = route
    ? `<button class="card-action-button shell-card-button native-shell-card-button" type="button" title="${escapeHtml(nativeShellRouteTitle(target, route))}" aria-label="${escapeHtml(nativeShellRouteTitle(target, route))}">PC</button>`
    : "";
  const mqttButton = mqtt
    ? `<button class="card-action-button mqtt-card-button" type="button" title="${escapeHtml(mqttRouteTitle(target, mqtt))}" aria-label="${escapeHtml(mqttRouteTitle(target, mqtt))}">MQ</button>`
    : "";
  const actionButtons = webShellButton || nativeShellButton || mqttButton
    ? `<div class="status-card-actions">${webShellButton}${nativeShellButton}${mqttButton}</div>`
    : "";
  card.innerHTML = `
    <div class="status-card-title">
      <h3>${escapeHtml(target.name || target.ip)}</h3>
      ${actionButtons}
    </div>
    <dl>
      <dt>IP</dt><dd>${escapeHtml(target.ip || "")}</dd>
      ${publicHost}
      <dt>Role</dt><dd>${escapeHtml(target.role || "")}</dd>
      <dt>Status</dt><dd>${target.reachable ? "online" : "offline"}</dd>
      <dt>Error</dt><dd>${escapeHtml(target.error || "-")}</dd>
    </dl>
    <div class="ports">${escapeHtml(portText || "No configured port checks")}</div>
  `;

  const webShellAction = card.querySelector(".web-shell-card-button");
  if (webShellAction) {
    webShellAction.addEventListener("click", (event) => {
      event.stopPropagation();
      connectShell(target);
    });
  }

  const nativeShellAction = card.querySelector(".native-shell-card-button");
  if (nativeShellAction) {
    nativeShellAction.addEventListener("click", (event) => {
      event.stopPropagation();
      openNativeTerminal(target);
    });
  }

  const mqttAction = card.querySelector(".mqtt-card-button");
  if (mqttAction) {
    mqttAction.addEventListener("click", (event) => {
      event.stopPropagation();
      connectMqtt(target);
    });
  }

  return card;
}

async function openNativeTerminal(target) {
  const targetKey = target.shell_target || target.ansible_name || target.ip || target.name || "";

  try {
    const response = await fetch("/api/shell/native-terminal", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ target: targetKey }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Native terminal could not be opened.");
    }

    els.statusSummary.textContent = `Opened local terminal for ${payload.label || target.name || target.ip}.`;
  } catch (error) {
    els.statusSummary.textContent = `Local terminal failed: ${error.message}`;
  }
}

function connectMqtt(target = null) {
  if (target) {
    openMqttDialog(target);
    return;
  }

  if (state.mqttSocket && state.mqttSocket.readyState === WebSocket.OPEN) {
    state.mqttSocket.close();
    return;
  }

  const socket = new WebSocket(wsUrl("/ws/mqtt"));
  state.mqttSocket = socket;
  els.mqttSummary.textContent = "Connecting...";
  els.mqttConnect.textContent = "Disconnect";

  socket.addEventListener("open", () => {
    els.mqttSummary.textContent = "Connected.";
  });

  socket.addEventListener("message", (event) => {
    appendMqttLine(JSON.parse(event.data));
  });

  socket.addEventListener("close", () => {
    els.mqttSummary.textContent = "Disconnected.";
    els.mqttConnect.textContent = "Connect";
  });

  socket.addEventListener("error", () => {
    els.mqttSummary.textContent = "MQTT stream error.";
  });
}

function appendMqttLine(item, log = els.mqttLog) {
  const line = document.createElement("div");
  line.className = "log-line";

  if (item.kind === "message") {
    line.innerHTML = `
      <div class="log-topic">${escapeHtml(item.topic || "")}</div>
      <div class="log-payload">${escapeHtml(item.payload || "")}</div>
    `;
  } else {
    line.textContent = `[${item.kind}] ${item.message}`;
  }

  log.appendChild(line);
  log.dataset.lines = String(Number(log.dataset.lines || 0) + 1);

  while (Number(log.dataset.lines || 0) > 300 && log.firstChild) {
    log.firstChild.remove();
    log.dataset.lines = String(Number(log.dataset.lines || 0) - 1);
  }

  log.scrollTop = log.scrollHeight;

  if (log === els.mqttLog) {
    state.mqttLines = Number(log.dataset.lines || 0);
  }
}

function connectShell(target = null) {
  const requestedTarget = target && (target.shell_target || target.ip || target.name) ? target : null;

  if (requestedTarget) {
    openShellDialog(requestedTarget);
    return;
  }

  const activeSocket = state.shellSocket
    && [WebSocket.CONNECTING, WebSocket.OPEN].includes(state.shellSocket.readyState);

  if (activeSocket) {
    state.shellSocket.close();
    return;
  }

  openShellSocket();
}

function openShellSocket() {
  const socket = new WebSocket(wsUrl("/ws/shell"));
  state.shellSocket = socket;
  els.shellSummary.textContent = "Connecting to Management PC...";
  els.shellConnect.textContent = "Disconnect";
  els.terminalOutput.textContent = "";

  socket.addEventListener("open", () => {
    els.shellSummary.textContent = "Connected to Management PC.";
    focusTerminal(els.terminalOutput);
  });

  socket.addEventListener("message", (event) => {
    appendTerminalText(els.terminalOutput, event.data);
  });

  socket.addEventListener("close", () => {
    if (state.shellSocket === socket) {
      els.shellSummary.textContent = "Disconnected.";
      els.shellConnect.textContent = "Connect";
    }
  });

  socket.addEventListener("error", () => {
    els.shellSummary.textContent = "Shell connection error for Management PC.";
  });

  focusTerminal(els.terminalOutput);
}

function sendTerminalKey(event, socket = state.shellSocket) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }

  if (event.metaKey || isBrowserCopyPaste(event)) {
    return;
  }

  const sequence = terminalKeySequence(event);

  if (sequence !== null) {
    socket.send(sequence);
    event.preventDefault();
  }
}

function terminalKeySequence(event) {
  if (event.isComposing) {
    return null;
  }

  const cursorKeys = {
    ArrowUp: "A",
    ArrowDown: "B",
    ArrowRight: "C",
    ArrowLeft: "D",
  };
  const functionKeys = {
    F1: "\u001bOP",
    F2: "\u001bOQ",
    F3: "\u001bOR",
    F4: "\u001bOS",
    F5: "\u001b[15~",
    F6: "\u001b[17~",
    F7: "\u001b[18~",
    F8: "\u001b[19~",
    F9: "\u001b[20~",
    F10: "\u001b[21~",
    F11: "\u001b[23~",
    F12: "\u001b[24~",
  };

  if (event.getModifierState?.("AltGraph") && event.key.length === 1) {
    return event.key;
  }

  if (cursorKeys[event.key]) {
    return csiWithModifier(event, cursorKeys[event.key]);
  }

  if (event.key === "Home") {
    return csiWithModifier(event, "H");
  }

  if (event.key === "End") {
    return csiWithModifier(event, "F");
  }

  const keyMap = {
    Enter: "\r",
    Backspace: "\u007f",
    Tab: event.shiftKey ? "\u001b[Z" : "\t",
    Escape: "\u001b",
    Delete: "\u001b[3~",
    Insert: "\u001b[2~",
    PageUp: "\u001b[5~",
    PageDown: "\u001b[6~",
  };

  if (keyMap[event.key]) {
    return keyMap[event.key];
  }

  if (functionKeys[event.key]) {
    return functionKeys[event.key];
  }

  if (event.ctrlKey && !event.altKey && event.key.length === 1) {
    return ctrlSequence(event.key);
  }

  if (event.altKey && !event.ctrlKey && event.key.length === 1) {
    return `\u001b${event.key}`;
  }

  if (event.key.length === 1 && !event.ctrlKey && !event.altKey) {
    return event.key;
  }

  return null;
}

function csiWithModifier(event, code) {
  const modifier = terminalModifierCode(event);
  return modifier ? `\u001b[1;${modifier}${code}` : `\u001b[${code}`;
}

function terminalModifierCode(event) {
  let modifier = 1;

  if (event.shiftKey) {
    modifier += 1;
  }

  if (event.altKey) {
    modifier += 2;
  }

  if (event.ctrlKey) {
    modifier += 4;
  }

  return modifier === 1 ? null : modifier;
}

function ctrlSequence(key) {
  const lower = key.toLowerCase();

  if (lower >= "a" && lower <= "z") {
    return String.fromCharCode(lower.charCodeAt(0) - 96);
  }

  const controlMap = {
    " ": "\u0000",
    "[": "\u001b",
    "\\": "\u001c",
    "]": "\u001d",
    "^": "\u001e",
    "_": "\u001f",
    "?": "\u007f",
  };

  return controlMap[key] || null;
}

function isBrowserCopyPaste(event) {
  const key = event.key.toLowerCase();
  return event.ctrlKey && (key === "v" || (event.shiftKey && ["c", "v"].includes(key)));
}

function openShellDialog(target) {
  const sessionId = `shell-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const label = target.name || target.inventory_hostname || target.ansible_name || target.ip;
  const targetKey = target.shell_target || target.ansible_name || target.ip || target.name;
  const socket = new WebSocket(wsUrl(`/ws/shell?target=${encodeURIComponent(targetKey)}`));
  const windowEl = document.createElement("section");
  windowEl.className = "shell-dialog";
  windowEl.innerHTML = `
    <header class="shell-dialog-bar">
      <div>
        <h2>${escapeHtml(label)}</h2>
        <p>${escapeHtml(target.shell_description || "Connecting...")}</p>
      </div>
      <button class="shell-dialog-close" type="button" aria-label="Close shell">x</button>
    </header>
    <pre class="terminal shell-dialog-terminal" tabindex="0" role="terminal" aria-label="${escapeHtml(label)} shell"></pre>
  `;

  const terminal = windowEl.querySelector(".shell-dialog-terminal");
  const closeButton = windowEl.querySelector(".shell-dialog-close");
  els.shellWindows.appendChild(windowEl);
  state.shellSessions.set(sessionId, { socket, windowEl, terminal });

  closeButton.addEventListener("click", () => closeShellDialog(sessionId));
  windowEl.addEventListener("pointerdown", () => focusTerminal(terminal));
  terminal.addEventListener("keydown", (event) => sendTerminalKey(event, socket));
  terminal.addEventListener("paste", (event) => {
    if (socket.readyState !== WebSocket.OPEN) {
      return;
    }

    socket.send(event.clipboardData.getData("text"));
    event.preventDefault();
  });

  socket.addEventListener("open", () => {
    appendTerminalText(terminal, `Connected to ${label}.\r\n`);
    focusTerminal(terminal);
  });

  socket.addEventListener("message", (event) => {
    appendTerminalText(terminal, event.data);
  });

  socket.addEventListener("close", () => {
    appendTerminalText(terminal, "\r\n[connection closed]\r\n");
    windowEl.classList.add("shell-dialog-closed");
  });

  socket.addEventListener("error", () => {
    appendTerminalText(terminal, `\r\nShell connection error for ${label}.\r\n`);
  });

  focusTerminal(terminal);
}

function closeShellDialog(sessionId) {
  const session = state.shellSessions.get(sessionId);

  if (!session) {
    return;
  }

  if ([WebSocket.CONNECTING, WebSocket.OPEN].includes(session.socket.readyState)) {
    session.socket.close();
  }

  session.windowEl.remove();
  state.shellSessions.delete(sessionId);
}

function openMqttDialog(target) {
  const sessionId = `mqtt-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const label = target.name || target.mqtt_target || target.ip || "MQTT target";
  const targetKey = target.mqtt_target || target.name || target.ip;
  const route = mqttRoute(target);
  const detail = route
    ? `${route.host}:${route.port} ${route.topics.join(", ")}`
    : "Connecting...";
  const socket = new WebSocket(wsUrl(`/ws/mqtt?target=${encodeURIComponent(targetKey)}`));
  const windowEl = document.createElement("section");
  windowEl.className = "shell-dialog mqtt-dialog";
  windowEl.innerHTML = `
    <header class="shell-dialog-bar">
      <div>
        <h2>${escapeHtml(label)} MQTT</h2>
        <p>${escapeHtml(target.mqtt_description || detail)}</p>
      </div>
      <button class="shell-dialog-close" type="button" aria-label="Close MQTT stream">x</button>
    </header>
    <div class="log mqtt-dialog-log" role="log" aria-label="${escapeHtml(label)} MQTT stream"></div>
  `;

  const log = windowEl.querySelector(".mqtt-dialog-log");
  const closeButton = windowEl.querySelector(".shell-dialog-close");
  els.shellWindows.appendChild(windowEl);
  state.mqttSessions.set(sessionId, { socket, windowEl, log });

  closeButton.addEventListener("click", () => closeMqttDialog(sessionId));

  socket.addEventListener("open", () => {
    appendMqttLine(
      {
        kind: "status",
        message: `connecting to ${detail}`,
      },
      log,
    );
  });

  socket.addEventListener("message", (event) => {
    appendMqttLine(parseMqttSocketMessage(event.data), log);
  });

  socket.addEventListener("close", () => {
    appendMqttLine(
      {
        kind: "status",
        message: "connection closed",
      },
      log,
    );
    windowEl.classList.add("shell-dialog-closed");
  });

  socket.addEventListener("error", () => {
    appendMqttLine(
      {
        kind: "error",
        message: `MQTT connection error for ${label}`,
      },
      log,
    );
  });
}

function closeMqttDialog(sessionId) {
  const session = state.mqttSessions.get(sessionId);

  if (!session) {
    return;
  }

  if ([WebSocket.CONNECTING, WebSocket.OPEN].includes(session.socket.readyState)) {
    session.socket.close();
  }

  session.windowEl.remove();
  state.mqttSessions.delete(sessionId);
}

function parseMqttSocketMessage(data) {
  try {
    return JSON.parse(data);
  } catch {
    return {
      kind: "message",
      topic: "websocket",
      payload: data,
    };
  }
}

function appendTerminalText(terminal, text) {
  terminal.textContent += text;

  if (terminal.textContent.length > MAX_TERMINAL_CHARS) {
    terminal.textContent = terminal.textContent.slice(-MAX_TERMINAL_CHARS);
  }

  terminal.scrollTop = terminal.scrollHeight;
}

function focusTerminal(terminal) {
  window.requestAnimationFrame(() => terminal.focus({ preventScroll: true }));
}

async function saveCamera(event) {
  event.preventDefault();
  const payload = {
    ip: els.cameraIp.value.trim(),
    port: Number(els.cameraPort.value || 80),
    scheme: els.cameraScheme.value,
    path: els.cameraPath.value || "/",
    username: els.cameraUser.value.trim(),
    password: els.cameraPassword.value,
  };
  const response = await fetch("/api/camera", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    els.cameraSummary.textContent = "Camera config could not be saved.";
    return;
  }

  const data = await response.json();
  fillCameraForm(data.camera);
  refreshCameraFrame();
}

function refreshCameraFrame() {
  const ip = els.cameraIp.value.trim();

  if (!ip) {
    els.cameraSummary.textContent = "No camera is configured.";
    els.cameraFrame.removeAttribute("src");
    return;
  }

  els.cameraSummary.textContent = `Camera proxy is configured for ${ip}.`;
  const url = `/api/camera/feed?ts=${Date.now()}`;
  els.cameraFrame.src = url;
  els.cameraOpen.href = url;
}

function shortTime(value) {
  if (!value) {
    return "Unknown";
  }

  try {
    return new Date(value).toLocaleTimeString();
  } catch {
    return value;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

els.refreshStatus.addEventListener("click", refreshStatus);
els.mqttConnect.addEventListener("click", connectMqtt);
els.mqttClear.addEventListener("click", () => {
  els.mqttLog.textContent = "";
  els.mqttLog.dataset.lines = "0";
  state.mqttLines = 0;
});
els.shellConnect.addEventListener("click", () => connectShell());
els.terminalOutput.addEventListener("pointerdown", () => focusTerminal(els.terminalOutput));
els.terminalOutput.addEventListener("keydown", sendTerminalKey);
els.terminalOutput.addEventListener("paste", (event) => {
  const socket = state.shellSocket;

  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }

  const text = event.clipboardData.getData("text");
  socket.send(text);
  event.preventDefault();
});
els.cameraForm.addEventListener("submit", saveCamera);
els.cameraReload.addEventListener("click", refreshCameraFrame);

loadConfig().then(async () => {
  await refreshHealth();
  await refreshStatus();
  state.healthTimer = window.setInterval(refreshHealth, 15000);
});
