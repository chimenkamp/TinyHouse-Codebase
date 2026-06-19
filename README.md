# TinyHouse Codebase

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
