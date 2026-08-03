# Privacy Safety and Governance

## Governance Outcome

The laboratory should separate distinct governance domains. The domains cover safety control, operational data, research data, and cross-site disclosure. The [privacy-boundary model](privacy-boundaries.svg) shows the required zones. Raw video and direct participant identity remain local by default.

The concept supports privacy by design. The laboratory collects process evidence that answers a defined research question. The laboratory does not collect continuous human observation merely because a camera exists.

## Data Classes

| Class | Examples | Default zone | Cross-site rule | Suggested retention rule |
| --- | --- | --- | --- | --- |
| Safety transient | Guard state, emergency-stop state, short video buffer | Machine or site | Share only incident milestone | Keep only for incident policy or overwrite buffer |
| Raw machine telemetry | Temperature, axis state, printer progress | Site | Share only approved features | Retain for the approved experiment window |
| Raw visual data | Workcell frame, part image | Site restricted | Do not share by default | Delete after derived evidence and review window |
| Derived inspection data | Feature vector, defect class, confidence | Site research | Share when policy permits | Retain with model and threshold version |
| Process event | Activity, time, qualified object references | Site and shared view | Share minimized event | Retain with research dataset |
| Participant mapping | Name to local pseudonym | Local identity vault | Never share by default | Delete or archive under ethics protocol |
| Participant process data | Role, task duration, override reason | Site research | Share pseudonym or role only | Retain under consent and protocol |
| Consent evidence | Policy version, scope, withdrawal | Local governance | Share authorization status only | Retain as required by governance policy |
| Research dataset | Curated OCEL and evidence references | Controlled research zone | Share under agreement | Retain under data-management plan |

The suggested retention rules are design recommendations. The responsible university offices must set exact durations. The project must not treat the table as legal advice.

## Privacy Principles

| Principle | Laboratory implementation | Verification |
| --- | --- | --- |
| Purpose limitation | Link every collected field to a protocol purpose | Schema review and dataset manifest |
| Data minimization | Store derived events instead of continuous media where possible | Field allowlist and media inventory |
| Separation | Store identity mapping outside operational and research stores | Access test and storage inspection |
| Transparency | Show active sensors and current collection mode | Participant notice and status light |
| Choice | Offer non-camera tasks or camera-free experiment variants where feasible | Consent and assignment audit |
| Accuracy | Allow participants to flag incorrect task attribution | Correction workflow test |
| Storage limitation | Apply retention class and deletion deadline at creation | Retention job evidence |
| Security | Use per-service identities and encrypted transport | Configuration and access review |
| Accountability | Record policy versions and disclosure decisions | Immutable governance events |

## Participant Identity Model

The local identity vault maps a person to a random participant pseudonym. Operational events use the pseudonym or a role identifier. Shared events use the role by default.

The identity vault must prevent sensitive identifiers from becoming research pseudonyms. Prohibited sources include device identifiers, usernames, and badge serial numbers. A consent withdrawal must create a governance event. Future nonessential collection must stop after the withdrawal becomes effective.

The system should separate operator authentication from research identity. An operator can authenticate for safety and accountability while the research export receives only a pseudonym. The local audit system can retain the accountable identity under a separate access policy.

## Camera Policy

The default camera mode observes the workpiece and machine zone. The camera framing should exclude faces and unrelated work areas. The system should show the active mode with a visible indicator.

The default inspection pipeline computes the required features locally. The pipeline stores the result, confidence, model version, and source-frame hash. The pipeline deletes the frame after the configured review window unless the protocol permits retention.

The safety camera path must remain separate from the research path. A safety function must not depend on a research computer-vision model unless the model and system meet the required safety standard. The concept does not make that claim.

## Disclosure Policy

Each event receives one privacy class. The disclosure gateway applies an allowlist for the destination, study, and consent version. A failed rule blocks the event and emits a local `Disclosure blocked` event.

| Field | Local operational view | Local research view | Shared Munich view |
| --- | --- | --- | --- |
| Direct name | Allowed only for authorized audit | Excluded | Excluded |
| Local participant pseudonym | Optional | Allowed when protocol permits | Replaced with role or study pseudonym |
| Role | Allowed | Allowed | Allowed |
| Exact workcell location | Allowed | Generalize when unnecessary | Site and station class only |
| Raw image | Restricted | Allowed only by protocol | Excluded by default |
| Derived defect feature | Allowed | Allowed | Allowed when required |
| Machine identifier | Allowed | Allowed | Stable research alias |
| Product and component identifiers | Allowed | Allowed | Shared collaboration identifiers |
| Free text | Restricted | Structured reason code preferred | Excluded by default |
| Exact timestamp | Allowed | Allowed | Allowed or bucketed by protocol |

## Safety Architecture

Safety functions remain local and independent from research orchestration. The robot and printer must use their documented manufacturer safety mechanisms. The laboratory must complete a local risk assessment before automated physical operation.

| Safety function | Required authority | Orchestrator behavior |
| --- | --- | --- |
| Emergency stop | Hardwired or manufacturer-approved local system | Observe state and stop issuing work |
| Guard or safe-zone check | Local safety controller or approved controller function | Require readiness before job acceptance |
| Robot speed and force mode | Robot controller and approved program | Select only validated program identifiers |
| Printer thermal protection | Printer controller | Treat fault as terminal for the job |
| Manual recovery | Trained local operator | Create an explicit recovery task |
| Remote request | Cross-site coordinator | Request an outcome and never direct motion |
| Restart after fault | Authorized local operator | Require a new readiness event |

Safety barriers must remain active. No experiment may disable an emergency stop, thermal limit, guard, safe-speed mode, or manufacturer safety check. Fault injection must occur above the safety layer or through approved controller test modes.

## Access Roles

| Role | Operational access | Research access | Governance access |
| --- | --- | --- | --- |
| Participant | Assigned tasks and own notices | Own consent and correction request | Consent choice |
| Operator | Local equipment and recovery tasks | Limited run context | No identity-vault administration by default |
| Site administrator | Infrastructure and service configuration | No automatic dataset access | System audit metadata |
| Researcher | Experiment configuration and curated data | Approved datasets | Protocol status |
| Data steward | Dataset release and retention | Curated and restricted datasets | Disclosure and deletion records |
| Principal investigator | Study oversight | Approved analyses | Protocol and incident oversight |
| Munich collaborator | Shared commitments and shared events | Approved collaboration dataset | Shared agreement status |

## Research Governance Checklist

The responsible team should complete the checklist before participant data collection.

- Define the research question and required fields.
- Define the lawful basis and ethics-review path.
- Define participant information and consent handling.
- Define withdrawal and correction handling.
- Define camera zones and visible recording indicators.
- Define local and shared pseudonym rules.
- Define exact retention periods and deletion evidence.
- Define the controller or joint-controller roles for both laboratories.
- Define a data-sharing agreement for the Munich collaboration.
- Define incident notification and breach handling.
- Define allowed secondary use and publication rules.
- Perform a data-protection impact assessment when the responsible office requires one.
- Perform a machine and workcell risk assessment.
- Record the approved protocol version in every experiment run.

## Dataset Release Levels

| Release | Contents | Intended audience |
| --- | --- | --- |
| Internal operational | Full process events and local equipment identifiers | Operators and administrators |
| Internal research | Pseudonymous OCEL with approved derived evidence | Approved researchers |
| Partner shared | Site-minimized OCEL with role-level human data | Munich collaboration |
| Public benchmark | Synthetic or strongly de-identified OCEL plus protocol | External research community |

The public benchmark should not contain raw images or direct identifiers. Rare event combinations can still identify a participant. The release review must assess combination risk before publication.
