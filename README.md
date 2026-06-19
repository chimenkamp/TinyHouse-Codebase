# TinyHouse Codebase

The TinyHouse Codebase documents and supports a TinyHouse lab for sensor data. The lab connects sensors and Arduino based sensor nodes. The lab uses Raspberry Pi broker nodes and Jetson edge computers. The lab uses a management PC for access and administration. The documentation records the observed infrastructure state from 2026-06-15.

The repository additionally separates documentation from operating tools. The `docs` directory contains the VitePress documentation. The `modules/dashboard` directory contains a Python dashboard for operations. The `modules/administration` directory contains Ansible files and network collection scripts. The `extensions/sage` directory contains the SAGE sensor abstraction prototype.

The documentation describes the current network and infrastructure. The private TinyHouse network uses `192.168.1.0/24` behind the router. The router exposes selected devices through DNAT ports on `132.180.196.167`. The documentation furthermore covers MQTT services and device inventory. The VitePress source starts at `docs/index.md`.

The dashboard provides a local web view for operations. The dashboard shows known private IP addresses. The dashboard can stream MQTT messages. The dashboard can open shell sessions through configured access paths. The dashboard additionally proxies a configured camera feed.

The administration module contains operational scripts. The Ansible inventory lives in `modules/administration/lab-ansible`. The inventory files describe bootstrap and administration access. The Python scripts collect network and device information. The collected TinyHouse state is stored under `docs/tinyhouse_collection_20260615_072208_btq8x1`.

The SAGE extension contains a sensor event abstraction prototype. The prototype reads sensor data from Arduino or ESP sources. The prototype publishes or collects MQTT events. The prototype furthermore exports event logs for process mining. The extension documentation starts at `extensions/sage/README.md`.

The project uses Node for the documentation site. The `package.json` file defines the VitePress commands. The project uses Python for the dashboard and administration scripts. The dashboard dependencies live in `modules/dashboard/requirements.txt`.

## Documentation Commands

The documentation server runs with this command.

```bash
npm run docs:dev
```

The documentation build runs with this command.

```bash
npm run docs:build
```

The documentation preview runs with this command.

```bash
npm run docs:preview
```

## Dashboard Commands

The dashboard therefore needs its Python environment first.

```bash
cd modules/dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The local dashboard starts with this command.

```bash
npm run dashboard:run:local
```

The tunnel dashboard starts with this command.

```bash
npm run dashboard:run:tunnel
```

The dashboard stop helper runs with this command.

```bash
npm run dashboard:kill
```

## Main Paths

The root `package.json` stores project scripts.
The `docs` directory stores VitePress documentation.
The `modules/dashboard` directory stores the operations dashboard.
The `modules/administration` directory stores Ansible and collection scripts.
The `extensions/sage` directory stores sensor abstraction code.
