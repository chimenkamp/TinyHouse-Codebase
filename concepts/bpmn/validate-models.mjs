import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFile } from 'node:fs/promises';

const require = createRequire(import.meta.url);
const BpmnModdle = require('../../modules/process-mining-frontend/node_modules/bpmn-moddle/dist/index.cjs');
const here = dirname(fileURLToPath(import.meta.url));
const moddle = new BpmnModdle();

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function typeOf(element) {
  return element?.$type ?? '';
}

function isSequenceFlow(element) {
  return typeOf(element) === 'bpmn:SequenceFlow';
}

function stateKey(counts, completed, flowIds) {
  return `${completed}|${flowIds.map((id) => counts.get(id) ?? 0).join(',')}`;
}

function exploreSoundness(container) {
  const elements = container.flowElements ?? [];
  const flows = elements.filter(isSequenceFlow);
  const nodes = elements.filter((element) => !isSequenceFlow(element));
  const starts = nodes.filter((element) => typeOf(element) === 'bpmn:StartEvent');
  const ends = nodes.filter((element) => typeOf(element) === 'bpmn:EndEvent');

  assert(starts.length === 1, `${container.id} must have exactly one start event`);
  assert(ends.length >= 1, `${container.id} must have at least one end event`);

  const flowIds = flows.map((flow) => flow.id).sort();
  const initialCounts = new Map();
  for (const outgoing of starts[0].outgoing ?? []) initialCounts.set(outgoing.id, 1);
  const initialKey = stateKey(initialCounts, 0, flowIds);
  const states = new Map([[initialKey, { counts: initialCounts, completed: 0 }]]);
  const queue = [initialKey];
  const successors = new Map();
  const firedNodes = new Set([starts[0].id]);

  function addSuccessor(fromKey, counts, completed, node) {
    for (const count of counts.values()) assert(count <= 1, `${container.id} is not 1-safe after ${node.id}`);
    assert(completed <= 1, `${container.id} can complete more than once`);
    const key = stateKey(counts, completed, flowIds);
    if (!successors.has(fromKey)) successors.set(fromKey, new Set());
    successors.get(fromKey).add(key);
    firedNodes.add(node.id);
    if (!states.has(key)) {
      states.set(key, { counts, completed });
      queue.push(key);
    }
  }

  while (queue.length) {
    const key = queue.shift();
    const state = states.get(key);
    const { counts, completed } = state;
    let enabled = 0;

    for (const node of nodes) {
      if (typeOf(node) === 'bpmn:StartEvent') continue;
      const incoming = node.incoming ?? [];
      const outgoing = node.outgoing ?? [];
      const isParallelJoin = typeOf(node) === 'bpmn:ParallelGateway' && incoming.length > 1;

      if (isParallelJoin) {
        if (!incoming.every((flow) => (counts.get(flow.id) ?? 0) > 0)) continue;
        enabled += 1;
        const next = new Map(counts);
        for (const flow of incoming) next.delete(flow.id);
        for (const flow of outgoing) next.set(flow.id, (next.get(flow.id) ?? 0) + 1);
        addSuccessor(key, next, completed, node);
        continue;
      }

      for (const incomingFlow of incoming) {
        if ((counts.get(incomingFlow.id) ?? 0) === 0) continue;
        enabled += 1;
        const base = new Map(counts);
        base.delete(incomingFlow.id);

        if (typeOf(node) === 'bpmn:EndEvent') {
          addSuccessor(key, base, completed + 1, node);
        } else if (typeOf(node) === 'bpmn:ExclusiveGateway' && outgoing.length > 1) {
          for (const outgoingFlow of outgoing) {
            const next = new Map(base);
            next.set(outgoingFlow.id, (next.get(outgoingFlow.id) ?? 0) + 1);
            addSuccessor(key, next, completed, node);
          }
        } else {
          const next = new Map(base);
          for (const outgoingFlow of outgoing) next.set(outgoingFlow.id, (next.get(outgoingFlow.id) ?? 0) + 1);
          addSuccessor(key, next, completed, node);
        }
      }
    }

    const isFinal = counts.size === 0 && completed === 1;
    assert(enabled > 0 || isFinal, `${container.id} has a dead marking ${key}`);
  }

  const finalKeys = [...states.entries()]
    .filter(([, state]) => state.counts.size === 0 && state.completed === 1)
    .map(([key]) => key);
  assert(finalKeys.length === 1, `${container.id} must have one proper final marking`);

  const predecessors = new Map();
  for (const [from, targets] of successors) {
    for (const target of targets) {
      if (!predecessors.has(target)) predecessors.set(target, new Set());
      predecessors.get(target).add(from);
    }
  }
  const canFinish = new Set(finalKeys);
  const reverseQueue = [...finalKeys];
  while (reverseQueue.length) {
    const key = reverseQueue.shift();
    for (const predecessor of predecessors.get(key) ?? []) {
      if (canFinish.has(predecessor)) continue;
      canFinish.add(predecessor);
      reverseQueue.push(predecessor);
    }
  }
  assert(canFinish.size === states.size, `${container.id} has a reachable marking that cannot reach completion`);

  const expectedNodes = nodes.map((node) => node.id).sort();
  const deadNodes = expectedNodes.filter((id) => !firedNodes.has(id));
  assert(deadNodes.length === 0, `${container.id} has dead flow nodes: ${deadNodes.join(', ')}`);

  return { states: states.size, nodes: nodes.length, flows: flows.length };
}

function validateGateways(container) {
  for (const element of container.flowElements ?? []) {
    if (typeOf(element) !== 'bpmn:ExclusiveGateway' || (element.outgoing?.length ?? 0) <= 1) continue;
    assert(element.default, `${element.id} needs a default sequence flow`);
    for (const outgoing of element.outgoing) {
      if (outgoing.id === element.default.id) continue;
      assert(outgoing.conditionExpression, `${outgoing.id} needs a formal condition`);
    }
  }
}

function validateChoreography(choreography) {
  for (const task of (choreography.flowElements ?? []).filter((element) => typeOf(element) === 'bpmn:ChoreographyTask')) {
    const participants = task.participantRef ?? [];
    const messages = task.messageFlowRef ?? [];
    assert(participants.length === 2, `${task.id} must reference exactly two participants`);
    assert(messages.length >= 1 && messages.length <= 2, `${task.id} must reference one or two message flows`);
    assert(participants.some((participant) => participant.id === task.initiatingParticipantRef?.id), `${task.id} has an invalid initiating participant`);
    assert(messages[0].sourceRef.id === task.initiatingParticipantRef.id, `${task.id} must list the initiating message first`);
    if (messages.length === 2) {
      assert(messages[0].sourceRef.id !== messages[1].sourceRef.id, `${task.id} has two messages from one participant`);
      assert(messages[0].targetRef.id !== messages[1].targetRef.id, `${task.id} has two messages to one participant`);
    }
  }
}

function validateDiagramCoverage(definitions) {
  const diagrams = definitions.diagrams ?? [];
  assert(diagrams.length === 1, 'Each model file must contain one BPMN diagram');
  const planeElements = diagrams[0].plane?.planeElement ?? [];
  const depicted = new Set(planeElements.map((element) => element.bpmnElement?.id).filter(Boolean));

  for (const root of definitions.rootElements ?? []) {
    if (!['bpmn:Process', 'bpmn:Collaboration', 'bpmn:Choreography'].includes(typeOf(root))) continue;
    for (const element of root.flowElements ?? []) {
      assert(depicted.has(element.id), `${element.id} has no BPMN Diagram Interchange element`);
    }
    if (typeOf(root) === 'bpmn:Collaboration') {
      for (const participant of root.participants ?? []) assert(depicted.has(participant.id), `${participant.id} has no pool shape`);
      for (const flow of root.messageFlows ?? []) assert(depicted.has(flow.id), `${flow.id} has no message-flow edge`);
    }
  }
}

async function loadModel(fileName) {
  const source = await readFile(join(here, fileName), 'utf8');
  const { rootElement, warnings } = await moddle.fromXML(source);
  assert(warnings.length === 0, `${fileName} has ${warnings.length} moddle warnings`);
  validateDiagramCoverage(rootElement);
  return rootElement;
}

const orchestration = await loadModel('distributed-orchestration.bpmn');
const choreographyDefinitions = await loadModel('distributed-choreography.bpmn');
const processResults = [];

for (const process of orchestration.rootElements.filter((element) => typeOf(element) === 'bpmn:Process')) {
  validateGateways(process);
  processResults.push([process.id, exploreSoundness(process)]);
}

const collaboration = orchestration.rootElements.find((element) => typeOf(element) === 'bpmn:Collaboration');
assert(collaboration.messageFlows.length === 7, 'The orchestration must expose seven concrete message flows');
const processByNode = new Map();
for (const process of orchestration.rootElements.filter((element) => typeOf(element) === 'bpmn:Process')) {
  for (const element of process.flowElements.filter((candidate) => !isSequenceFlow(candidate))) processByNode.set(element.id, process.id);
}
for (const flow of collaboration.messageFlows) {
  assert(flow.messageRef, `${flow.id} needs a message reference`);
  assert(processByNode.get(flow.sourceRef.id) !== processByNode.get(flow.targetRef.id), `${flow.id} must cross participant boundaries`);
}

const productionJoin = orchestration.get('rootElements').find((element) => element.id === 'Process_TinyHouse')
  .flowElements.find((element) => element.id === 'Gateway_ProductionJoin');
assert(productionJoin.incoming.length === 2, 'The production parallel join must have exactly two incoming flows');

const choreography = choreographyDefinitions.rootElements.find((element) => typeOf(element) === 'bpmn:Choreography');
assert(choreography.messageFlows.length === 5, 'The choreography must expose five message contracts');
validateGateways(choreography);
validateChoreography(choreography);
processResults.push([choreography.id, exploreSoundness(choreography)]);

const orchestrationContracts = new Set(collaboration.messageFlows.map((flow) => flow.messageRef.name));
const choreographyContracts = new Set(choreography.messageFlows.map((flow) => flow.messageRef.name));
assert(orchestrationContracts.size === 5, 'The orchestration must use five distinct message contracts');
assert([...orchestrationContracts].every((name) => choreographyContracts.has(name)), 'The choreography contracts must match the orchestration contracts');

const allowedSvgColors = new Set([
  '#FAE7EB', '#C9B6BA', '#E0D4E7', '#AFA3B6', '#DBEEF7', '#AABDC6',
  '#BDD2E4', '#8CA1B3', '#EECEDA', '#BD9DA9', '#CCDCEB', '#9BABBA',
  '#3B3440', '#FFFFFF'
]);
const svgFiles = [
  '../distributed-process.svg', '../distributed-choreography.svg', '../object-centric-model.svg',
  '../orchestration-architecture.svg', '../monitoring-abstraction.svg', '../privacy-boundaries.svg'
];
for (const relativePath of svgFiles) {
  const source = await readFile(join(here, relativePath), 'utf8');
  assert(!/<(?:title|desc)\b/i.test(source), `${relativePath} contains an embedded header or description`);
  assert(!/legend/i.test(source), `${relativePath} contains an embedded legend`);
  const colors = source.match(/#[0-9A-Fa-f]{6}/g) ?? [];
  const invalidColors = [...new Set(colors.map((color) => color.toUpperCase()).filter((color) => !allowedSvgColors.has(color)))];
  assert(invalidColors.length === 0, `${relativePath} contains colors outside the approved palette: ${invalidColors.join(', ')}`);
}

for (const [id, result] of processResults) {
  console.log(`${id}: control-flow sound state space with ${result.states} markings, ${result.nodes} nodes, and ${result.flows} flows`);
}
console.log('BPMN metamodel, Diagram Interchange, message, SVG text, and palette checks passed');
