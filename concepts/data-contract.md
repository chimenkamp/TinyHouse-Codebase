# Data Contract

## Contract Goal

The data contract makes every physical and digital action traceable to typed objects. The contract separates raw telemetry, durable task commands, canonical process events, and OCEL projections. Each layer retains its own schema version.

## Identifier Rules

| Entity | Format | Example | Scope |
| --- | --- | --- | --- |
| Site | Lowercase stable alias | `tinyhouse` | Shared |
| Equipment | `<site>:equipment:<local-id>` | `tinyhouse:equipment:printer-01` | Shared research alias |
| Operational object | `<type>:<uuid>` | `component:6f2b...` | Shared when collaboration requires it |
| Local participant | `participant:<random-uuid>` | `participant:46d1...` | Local only by default |
| Event | `<site>:event:<uuid>` | `munich:event:52ab...` | Globally unique |
| Command | `<site>:command:<uuid>` | `tinyhouse:command:077a...` | Globally unique and idempotent |
| Data asset | `sha256:<hex>` or `dataset:<uuid>` | `sha256:9a0c...` | Content-addressed or dataset scoped |

Identifiers must exclude personal and infrastructure data. Prohibited values include a person's name, email address, username, badge serial number, and network address. Object identifiers must remain stable across retries. A replacement physical component must receive a new object identifier.

## MQTT Namespaces

The documented categories retain their original names. The names are `sensor`, `devstatus`, `heartbeat`, and `data`. The proposed path adds site and device scope without changing those category names.

```text
tinyhouse/v1/<site>/<device>/sensor
tinyhouse/v1/<site>/<device>/devstatus
tinyhouse/v1/<site>/<device>/heartbeat
tinyhouse/v1/<site>/<device>/data
lab/v1/<site>/task/<resource-id>/<task-type>
lab/v1/<site>/task-event/<resource-id>/<task-type>
lab/v1/<site>/process-event/<activity-type>
lab/v1/<site>/health/<service-id>
```

The proposed namespace requires project approval because the current application path is undecided. The raw compatibility payload must preserve the documented field name `wifi_connencted`. The canonical normalizer may add `wifi_connected` only through an explicit versioned mapping. The normalizer must retain the source field and mapping rule in lineage metadata.

## MQTT Delivery Profile

| Message class | Quality of Service | Retained | Last Will | Reason |
| --- | --- | --- | --- | --- |
| High-rate raw telemetry | 0 or 1 by experiment protocol | No | No | Balance evidence and load |
| Process event | 1 | No | No | Durable delivery with event deduplication |
| Task command | 1 | No | No | Prevent stale retained commands |
| Task state event | 1 | No | No | Durable state reconstruction |
| Latest service health | 1 | Yes | Offline state | Fast readiness view |
| Latest device heartbeat | 1 | Yes | Offline state | Fast device discovery |

MQTT delivery does not provide end-to-end exactly-once physical execution. Command idempotency and adapter state checks provide duplicate protection. A task command must expire after its declared deadline.

## Canonical Event Envelope

```json
{
  "event_id": "tinyhouse:event:00000000-0000-4000-8000-000000000001",
  "event_type": "Complete print",
  "schema_version": "lab-event/1.0.0",
  "occurred_at": "2026-01-15T10:15:30.123Z",
  "observed_at": "2026-01-15T10:15:30.456Z",
  "source": {
    "site": "tinyhouse",
    "service": "printer-adapter-01",
    "equipment_id": "tinyhouse:equipment:printer-01",
    "sequence": 1842,
    "clock_source": "ntp",
    "clock_offset_ms": 4
  },
  "activity_instance_id": "print-job:00000000-0000-4000-8000-000000000011",
  "correlation_id": "work-order:00000000-0000-4000-8000-000000000021",
  "causation_id": "tinyhouse:command:00000000-0000-4000-8000-000000000031",
  "objects": [
    {
      "object_id": "print-job:00000000-0000-4000-8000-000000000011",
      "object_type": "print-job",
      "qualifier": "input"
    },
    {
      "object_id": "component:00000000-0000-4000-8000-000000000041",
      "object_type": "component",
      "qualifier": "output"
    },
    {
      "object_id": "tinyhouse:equipment:printer-01",
      "object_type": "equipment",
      "qualifier": "resource"
    }
  ],
  "attributes": {
    "result": "succeeded",
    "controller_job_id": "local-4711",
    "duration_ms": 845000
  },
  "quality": {
    "correlation_method": "controller-job-map",
    "correlation_confidence": 1.0,
    "late": false,
    "manual": false
  },
  "privacy": {
    "class": "operational",
    "policy_id": "disclosure-policy:joint-pilot-v1"
  }
}
```

The example values are illustrative. The timestamps and identifiers are not empirical observations.

## Required Envelope Fields

| Field | Type | Rule |
| --- | --- | --- |
| `event_id` | String | Immutable and globally unique |
| `event_type` | String | Exact reviewed activity name |
| `schema_version` | String | Semantic version of the envelope |
| `occurred_at` | Timestamp | Best estimate of physical or controller occurrence |
| `observed_at` | Timestamp | Time when the adapter observed the occurrence |
| `source.site` | String | Stable site alias |
| `source.service` | String | Stable producer alias |
| `source.sequence` | Integer | Monotonic per producer boot epoch or documented stream |
| `objects` | Array | At least one qualified object reference |
| `attributes` | Object | Event-type-specific values with declared units |
| `quality` | Object | Correlation, timing, and manual flags |
| `privacy.class` | String | Disclosure classification |

## Durable Task Command

```json
{
  "command_id": "tinyhouse:command:00000000-0000-4000-8000-000000000031",
  "command_type": "Execute validated robot program",
  "schema_version": "lab-command/1.0.0",
  "issued_at": "2026-01-15T10:20:00Z",
  "expires_at": "2026-01-15T10:25:00Z",
  "resource_id": "tinyhouse:equipment:robot-01",
  "program_id": "move-component-to-inspection:v3",
  "parameters": {
    "component_id": "component:00000000-0000-4000-8000-000000000041",
    "source_fixture": "fixture:printer-output-01",
    "target_fixture": "fixture:inspection-01"
  },
  "preconditions": [
    "resource-ready",
    "local-safety-ready",
    "component-identity-confirmed",
    "target-fixture-clear"
  ],
  "requested_by": "human-task:00000000-0000-4000-8000-000000000051"
}
```

A machine adapter must accept only validated program identifiers. The command must not contain arbitrary robot code. The adapter must recheck every local precondition.

## Decision Event

```json
{
  "event_type": "Evaluate route",
  "policy_id": "print-routing-policy",
  "policy_version": "1.2.0",
  "inputs": {
    "tinyhouse_queue_duration_s": 900,
    "munich_queue_duration_s": 120,
    "tinyhouse_material_available": true,
    "munich_material_available": true,
    "cross_site_gateway_available": true
  },
  "eligible_options": [
    "tinyhouse",
    "munich"
  ],
  "chosen_option": "munich",
  "reason_code": "lowest-eligible-queue-duration"
}
```

The decision event must contain the complete policy input snapshot. A derived score must include its formula or model version. A human override must create a new event with the selected option and structured reason code.

## Correlation Policy

The correlator should resolve objects through explicit evidence. Time proximity alone must not create a final object relation.

| Priority | Evidence | Result quality |
| --- | --- | --- |
| 1 | QR or registered identifier scan at the station | Explicit |
| 2 | Controller job identifier mapped at command acceptance | Explicit |
| 3 | Fixture slot with confirmed load and unload events | Derived-high |
| 4 | Weight and design-revision candidate set with one valid match | Derived-reviewable |
| 5 | Manual selection with two confirmations | Manual |
| Rejected | Timestamp proximity without identity evidence | No final correlation |

## Units and Values

Every numeric measurement must include a unit in the schema or field definition. Mass should use `g` or `kg`. Duration should use integer milliseconds in event payloads. Temperature should state `°C`. Voltage should state `V`.

Raw sensor values should preserve the original reading and calibration state. Derived values should record the transformation version. Missing values must be absent or explicitly null according to the schema. The pipeline must not replace a missing value with zero.

## Time Policy

Every producer should synchronize through the approved local time service. Each event must record the time source and estimated offset when available. A source sequence number supports ordering when time quality is poor.

The pipeline must preserve occurrence time during late ingestion. The pipeline must not overwrite occurrence time with processing time. A corrected time must retain the original timestamp and the correction method.

## Data-Quality Flags

| Flag | Meaning |
| --- | --- |
| `explicit` | Direct identifier or controller evidence supports the relation. |
| `derived` | A documented rule or model supports the event or relation. |
| `manual` | A participant supplied or corrected the value. |
| `late` | Ingestion exceeded the configured delay threshold. |
| `duplicate` | The pipeline received an existing event identifier. |
| `out_of_order` | Source sequence or causal evidence contradicts arrival order. |
| `clock_uncertain` | The source lacks an acceptable offset estimate. |
| `privacy_transformed` | The disclosure view removed or generalized fields. |
| `incomplete` | A required field or relation is missing. |

## Schema Governance

Schema evolution must remain auditable. Every schema change requires a version, example, compatibility statement, and validation test. A producer must advertise its supported schema version in health data. A consumer must reject an unsupported major version.

The schema repository should preserve complete evolution evidence. The contents should include source schemas, valid examples, invalid examples, migration rules, and release notes. The pilot should avoid a schema registry service until file-based versioning becomes insufficient.

## OCEL Projection

The OCEL projector maps `event_id` to the OCEL event identifier. The projector maps `event_type` to the OCEL event type. The projector maps `occurred_at` to the OCEL event time. The projector maps each qualified object reference without flattening.

Object attributes can change over time. The projector should represent state and location changes as timed object attributes when the analysis requires them. The canonical event store must remain the lineage source for every projection.
