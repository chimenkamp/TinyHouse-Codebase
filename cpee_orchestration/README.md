# TinyHouse CPEE orchestration

This folder is the Ruby implementation of the first executable CPEE instance:
the holistic coordinator. The upstream engines remain in [`../CPEE`](../CPEE)
and [`../weel`](../weel); their code is not duplicated here.

## Executed topology

The model in [`models/holistic_coordinator.xml`](models/holistic_coordinator.xml)
is a complete CPEE `testset`. CPEE transforms its DSLX description into WEEL.
Its control flow is:

```text
parallel (wait for both)
├── WA-4 · control, scheduling, lid receipt, outcome
└── production
    ├── parallel (wait for both)
    │   ├── WA-1 · print and inspect base
    │   └── Munich · print and dispatch lid
    ├── WA-2 · prepare kit
    └── WA-3 · assemble, test, approve
```

Each WEEL call remains open until the corresponding real child CPEE instance
finishes. An abandoned or lost child resumes the call with `CPEE-SALVAGE`, and
the model's rescue handler fails that branch explicitly.

## Ruby fragment gateway

CPEE/WEEL has no native five-child supervision primitive. The Ruby gateway
implements only that missing lifecycle boundary:

1. accept the correlation and callback headers automatically sent by CPEE;
2. atomically claim `(run_id, fragment_id, attempt)` in `PStore`;
3. load a whitelisted child definition and inject correlation plus a state
   subscription;
4. create the child in `ready`, persist its ID/URL/UUID, then set `running`;
5. return `202`, an empty body, and `CPEE-CALLBACK: true` to hold the parent;
6. consume child state events and poll as recovery for lost notifications;
7. read final data elements and PUT the result to the parent callback.

An ambiguous create failure becomes `create_unknown`; the software does not
blindly recreate physical printer or robot work. Known children that disappear
become `lost`. Callback payloads remain durable until CPEE accepts them.

## Run

Use the same modern Ruby deployment selected for CPEE (Ruby 2.7 or newer):

```bash
cd cpee_orchestration
bundle install
set -a
source config/environment.example
set +a
ruby main.rb
```

The example node names are intentional deployment labels, not verified DNS
assignments. Replace them with the commissioned Pi and Munich addresses. Keep
the service on loopback unless it is protected by authenticated TLS through a
reverse proxy or a site-to-site VPN.

Create one holistic coordinator run:

```bash
curl -fsS -X POST http://127.0.0.1:8400/v1/runs \
  -H 'Content-Type: application/json' \
  --data '{"run_id":"run-001","work_order_id":"order-001"}'
```

Inspect its parent and child identities:

```bash
curl -fsS http://127.0.0.1:8400/v1/runs/run-001
```

The five real child definitions must exist at the configured paths before the
parent reaches its gateway calls. See [`models/fragments/README.md`](models/fragments/README.md).

## Verify

```bash
bundle exec rake test
xmllint --noout --relaxng ../CPEE/lib/properties/set-testset.rng \
  models/holistic_coordinator.xml
```

To validate the generated WEEL/Ruby syntax, extract the nested description,
transform it with
`../CPEE/server/executionhandlers/ruby/dsl_to_dslx.xsl`, prepend
`# encoding: UTF-8`, and pipe it to `ruby -c`. The encoding marker is needed
because WEEL's generated helper method names contain Unicode characters.

## Operational boundary

This coordinator starts and observes process instances; it does not issue
printer heater commands, robot motion, or safety decisions. Machine interlocks,
E-stop handling, guard monitoring, electrical limits, and BMS protection remain
local to each workstation.

The current repository environment cannot perform a live engine smoke test:
its system Ruby is 2.6.10, while the bundled CPEE requires Ruby 2.7 or newer,
and the CPEE/Redis gems and Redis service are not installed. XML schema,
DSLX-to-WEEL syntax, gateway wire contracts, persistence, and HTTP routes are
verified locally; a commissioned CPEE stack is still required for end-to-end
execution.
