# TinyHouse Process-Mining Frontend

An isolated, mock-data dashboard for the TinyHouse IoT process-mining pipeline.
It simulates sensor ingestion, preprocessing with physically explained outliers,
activity abstraction, case correlation, and BPMN process discovery. No backend
or lab hardware is required.

## Run

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:5174`.

## Build

```bash
npm run build
```

The simulation is intentionally deterministic enough to tell a coherent
production story while introducing small random changes to live values,
throughput, anomalies, and trace confidence.
