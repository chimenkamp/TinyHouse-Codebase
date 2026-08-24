# Fragment definitions

Place the five executable CPEE full-instance definitions here as:

- `wa1.xml`
- `wa2.xml`
- `wa3.xml`
- `wa4.xml`
- `munich.xml`

The gateway never accepts a model path or CPEE URL from a workflow call. It
loads only these statically configured definitions, injects `run_id`,
`work_order_id`, `fragment_id`, `attempt`, `input_json`, immutable attributes,
and a `state/change` subscription, then creates the child in `ready` before
starting it.

No placeholder fragment is included. These five process fragments are the next
implementation increment; launching a holistic run fails explicitly while a
required definition is absent.
