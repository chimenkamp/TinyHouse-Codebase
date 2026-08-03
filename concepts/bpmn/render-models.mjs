import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';

const require = createRequire(import.meta.url);
const BpmnModdle = require('../../modules/process-mining-frontend/node_modules/bpmn-moddle/dist/index.cjs');

const here = dirname(fileURLToPath(import.meta.url));
const moddle = new BpmnModdle();

const palette = {
  blush: { fill: '#FAE7EB', stroke: '#C9B6BA' },
  lavender: { fill: '#E0D4E7', stroke: '#AFA3B6' },
  ice: { fill: '#DBEEF7', stroke: '#AABDC6' },
  powder: { fill: '#BDD2E4', stroke: '#8CA1B3' },
  rose: { fill: '#EECEDA', stroke: '#BD9DA9' },
  mist: { fill: '#CCDCEB', stroke: '#9BABBA' }
};

const textColor = '#3B3440';

function xml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function lines(value, max = 18) {
  const words = String(value ?? '').trim().split(/\s+/).filter(Boolean);
  const result = [];
  let current = '';

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && candidate.length > max) {
      result.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }

  if (current) result.push(current);
  return result.slice(0, 3);
}

function textBlock(value, x, y, max = 18, className = 'node-label') {
  const wrapped = lines(value, max);
  const firstY = y - ((wrapped.length - 1) * 8);
  return `<text x="${x}" y="${firstY}" text-anchor="middle" class="${className}">${wrapped.map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : 16}">${xml(line)}</tspan>`).join('')}</text>`;
}

function taskIcon(type, x, y) {
  if (type === 'bpmn:UserTask') {
    return `<g class="task-icon"><circle cx="${x + 13}" cy="${y + 11}" r="3"/><path d="M${x + 8} ${y + 20} Q${x + 13} ${y + 14} ${x + 18} ${y + 20}"/></g>`;
  }
  if (type === 'bpmn:ManualTask') {
    return `<g class="task-icon"><path d="M${x + 7} ${y + 18} L${x + 9} ${y + 9} L${x + 12} ${y + 15} L${x + 14} ${y + 7} L${x + 16} ${y + 15} L${x + 19} ${y + 10} L${x + 18} ${y + 20} Z"/></g>`;
  }
  if (type === 'bpmn:ServiceTask') {
    return `<g class="task-icon"><circle cx="${x + 13}" cy="${y + 13}" r="5"/><path d="M${x + 13} ${y + 5}V${y + 8}M${x + 13} ${y + 18}V${y + 21}M${x + 5} ${y + 13}H${x + 8}M${x + 18} ${y + 13}H${x + 21}"/></g>`;
  }
  if (type === 'bpmn:BusinessRuleTask') {
    return `<g class="task-icon"><rect x="${x + 6}" y="${y + 6}" width="14" height="14"/><path d="M${x + 6} ${y + 11}H${x + 20}M${x + 11} ${y + 6}V${y + 20}"/></g>`;
  }
  if (type === 'bpmn:SendTask' || type === 'bpmn:ReceiveTask') {
    const fill = type === 'bpmn:SendTask' ? palette.powder.stroke : 'none';
    return `<g class="task-icon"><rect x="${x + 6}" y="${y + 8}" width="16" height="11" fill="${fill}"/><path d="M${x + 6} ${y + 8}L${x + 14} ${y + 14}L${x + 22} ${y + 8}"/></g>`;
  }
  return '';
}

function renderParticipant(shape, element, bounds, fill, stroke) {
  const labelX = bounds.x + 24;
  const labelY = bounds.y + bounds.height / 2;
  return `<g data-bpmn-element="${xml(element.id)}">
    <rect x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bounds.height}" rx="5" fill="${fill}" fill-opacity="0.30" stroke="${stroke}" stroke-width="2"/>
    <line x1="${bounds.x + 48}" y1="${bounds.y}" x2="${bounds.x + 48}" y2="${bounds.y + bounds.height}" stroke="${stroke}" stroke-width="2"/>
    <text x="${labelX}" y="${labelY}" text-anchor="middle" class="pool-label" transform="rotate(-90 ${labelX} ${labelY})">${xml(element.name)}</text>
  </g>`;
}

function renderGateway(element, bounds, fill, stroke) {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;
  const marker = element.$type === 'bpmn:ParallelGateway'
    ? `<path d="M${cx - 10} ${cy}H${cx + 10}M${cx} ${cy - 10}V${cy + 10}" class="gateway-marker"/>`
    : `<path d="M${cx - 8} ${cy - 8}L${cx + 8} ${cy + 8}M${cx + 8} ${cy - 8}L${cx - 8} ${cy + 8}" class="gateway-marker"/>`;
  const label = element.name ? textBlock(element.name, cx, bounds.y + bounds.height + 22, 16, 'small-label') : '';
  return `<g data-bpmn-element="${xml(element.id)}"><polygon points="${cx},${bounds.y} ${bounds.x + bounds.width},${cy} ${cx},${bounds.y + bounds.height} ${bounds.x},${cy}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>${marker}${label}</g>`;
}

function renderEvent(element, bounds, fill, stroke) {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;
  const isEnd = element.$type === 'bpmn:EndEvent';
  const isIntermediate = element.$type.startsWith('bpmn:Intermediate');
  const rings = isEnd
    ? `<circle cx="${cx}" cy="${cy}" r="${bounds.width / 2 - 2}" fill="${fill}" stroke="${stroke}" stroke-width="4"/>`
    : `<circle cx="${cx}" cy="${cy}" r="${bounds.width / 2 - 2}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>${isIntermediate ? `<circle cx="${cx}" cy="${cy}" r="${bounds.width / 2 - 6}" fill="none" stroke="${stroke}" stroke-width="1.5"/>` : ''}`;
  const hasMessage = element.eventDefinitions?.some((definition) => definition.$type === 'bpmn:MessageEventDefinition');
  const envelope = hasMessage ? `<rect x="${cx - 8}" y="${cy - 5}" width="16" height="10" fill="none" stroke="${stroke}"/><path d="M${cx - 8} ${cy - 5}L${cx} ${cy + 1}L${cx + 8} ${cy - 5}" fill="none" stroke="${stroke}"/>` : '';
  const label = element.name ? textBlock(element.name, cx, bounds.y + bounds.height + 22, 18, 'small-label') : '';
  return `<g data-bpmn-element="${xml(element.id)}">${rings}${envelope}${label}</g>`;
}

function renderTask(element, bounds, fill, stroke) {
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2 + 4;
  return `<g data-bpmn-element="${xml(element.id)}"><rect x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bounds.height}" rx="10" fill="${fill}" stroke="${stroke}" stroke-width="2"/>${taskIcon(element.$type, bounds.x, bounds.y)}${textBlock(element.name, cx, cy, 17)}</g>`;
}

function renderChoreographyTask(element, bounds, fill, stroke) {
  const bandHeight = Math.min(36, Math.round(bounds.height * 0.24));
  const participantRefs = element.participantRef ?? [];
  const initiatorId = element.initiatingParticipantRef?.id;
  const top = participantRefs[0];
  const bottom = participantRefs[1];
  const topPalette = top?.id === initiatorId ? palette.powder : palette.ice;
  const bottomPalette = bottom?.id === initiatorId ? palette.powder : palette.ice;
  const cx = bounds.x + bounds.width / 2;
  const taskY = bounds.y + bandHeight;
  const taskHeight = bounds.height - (2 * bandHeight);
  return `<g data-bpmn-element="${xml(element.id)}">
    <rect x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bounds.height}" rx="9" fill="${fill}" stroke="${stroke}" stroke-width="2"/>
    <rect x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bandHeight}" rx="9" fill="${topPalette.fill}" stroke="${topPalette.stroke}" stroke-width="2"/>
    <rect x="${bounds.x}" y="${bounds.y + bounds.height - bandHeight}" width="${bounds.width}" height="${bandHeight}" rx="9" fill="${bottomPalette.fill}" stroke="${bottomPalette.stroke}" stroke-width="2"/>
    <text x="${cx}" y="${bounds.y + bandHeight / 2 + 5}" text-anchor="middle" class="participant-label">${xml(top?.name)}</text>
    <text x="${cx}" y="${bounds.y + bounds.height - bandHeight / 2 + 5}" text-anchor="middle" class="participant-label">${xml(bottom?.name)}</text>
    ${textBlock(element.name, cx, taskY + taskHeight / 2 + 4, 21)}
  </g>`;
}

function renderShape(shape) {
  const element = shape.bpmnElement;
  const bounds = shape.bounds;
  const fill = shape.get('bioc:fill') || palette.ice.fill;
  const stroke = shape.get('bioc:stroke') || palette.ice.stroke;

  if (element.$type === 'bpmn:Participant') return renderParticipant(shape, element, bounds, fill, stroke);
  if (element.$type === 'bpmn:ChoreographyTask') return renderChoreographyTask(element, bounds, fill, stroke);
  if (element.$type.endsWith('Gateway')) return renderGateway(element, bounds, fill, stroke);
  if (element.$type.endsWith('Event')) return renderEvent(element, bounds, fill, stroke);
  return renderTask(element, bounds, fill, stroke);
}

function renderEdge(edge) {
  const element = edge.bpmnElement;
  const waypoints = edge.waypoint ?? [];
  if (waypoints.length < 2) return '';
  const isMessage = element.$type === 'bpmn:MessageFlow';
  const stroke = edge.get('bioc:stroke') || (isMessage ? palette.mist.stroke : palette.powder.stroke);
  const path = waypoints.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x} ${point.y}`).join(' ');
  const start = waypoints[0];
  const middle = waypoints[Math.floor(waypoints.length / 2)];
  const label = element.name ? `<text x="${middle.x + 7}" y="${middle.y - 7}" class="edge-label">${xml(element.name)}</text>` : '';
  const startCircle = isMessage ? `<circle cx="${start.x}" cy="${start.y}" r="4" fill="#FFFFFF" stroke="${stroke}" stroke-width="1.5"/>` : '';
  return `<g data-bpmn-element="${xml(element.id)}"><path d="${path}" fill="none" stroke="${stroke}" stroke-width="2" ${isMessage ? 'stroke-dasharray="8 6"' : ''} marker-end="url(#${isMessage ? 'message-arrow' : 'sequence-arrow'})"/>${startCircle}${label}</g>`;
}

async function render(sourceName, outputName, ariaLabel) {
  const source = await readFile(join(here, sourceName), 'utf8');
  const { rootElement, warnings } = await moddle.fromXML(source);
  if (warnings.length) throw new Error(`${sourceName} produced ${warnings.length} import warnings`);

  const plane = rootElement.diagrams[0]?.plane;
  if (!plane) throw new Error(`${sourceName} has no BPMN DI plane`);
  const elements = plane.planeElement ?? [];
  const shapes = elements.filter((element) => element.$type === 'bpmndi:BPMNShape');
  const edges = elements.filter((element) => element.$type === 'bpmndi:BPMNEdge');
  const minX = Math.min(...shapes.map((shape) => shape.bounds.x)) - 20;
  const minY = Math.min(...shapes.map((shape) => shape.bounds.y)) - 20;
  const maxX = Math.max(...shapes.map((shape) => shape.bounds.x + shape.bounds.width)) + 20;
  const maxY = Math.max(...shapes.map((shape) => shape.bounds.y + shape.bounds.height)) + 45;
  const width = maxX - minX;
  const height = maxY - minY;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="${minX} ${minY} ${width} ${height}" role="img" aria-label="${xml(ariaLabel)}">
  <defs>
    <style>
      text{font-family:Inter,Arial,sans-serif;fill:${textColor}}
      .node-label{font-size:13px;font-weight:650}
      .small-label{font-size:11px;font-weight:600}
      .pool-label{font-size:16px;font-weight:700;letter-spacing:.2px}
      .participant-label{font-size:12px;font-weight:700}
      .edge-label{font-size:10px;font-weight:650;paint-order:stroke;stroke:#FFFFFF;stroke-width:4px;stroke-linejoin:round}
      .gateway-marker,.task-icon{fill:none;stroke:${palette.powder.stroke};stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
    </style>
    <marker id="sequence-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="${palette.powder.stroke}"/></marker>
    <marker id="message-arrow" markerWidth="12" markerHeight="12" refX="11" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L11,4 L0,8 z" fill="#FFFFFF" stroke="${palette.mist.stroke}" stroke-width="1.4"/></marker>
  </defs>
  <rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="#FFFFFF"/>
  ${edges.map(renderEdge).join('\n  ')}
  ${shapes.map(renderShape).join('\n  ')}
</svg>
`;
  await writeFile(join(here, '..', outputName), svg, 'utf8');
}

await render('distributed-orchestration.bpmn', 'distributed-process.svg', 'BPMN orchestration for the TinyHouse and Munich distributed sensor-node process');
await render('distributed-choreography.bpmn', 'distributed-choreography.svg', 'BPMN choreography for TinyHouse and Munich interaction points');
