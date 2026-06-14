/**
 * WorkflowShapes — Custom JointJS shapes for the workflow designer.
 *
 * 8 step types, each with distinct color, icon path, and port layout.
 * Follows the IIFE pattern from composer_renderer.js.
 *
 * Usage:
 *   let shape = WorkflowShapes.createStep(graph, { type: 'condition', ... });
 */
let WorkflowShapes = (function() {
    'use strict';

    /* -- Step type colors ---------------------------------------- */
    let STEP_COLORS = {
        trigger:       { fill: '#dbeafe', stroke: '#2563eb', text: '#1e40af', icon: '#3b82f6' },
        condition:     { fill: '#fef3c7', stroke: '#d97706', text: '#92400e', icon: '#f59e0b' },
        approval:      { fill: '#fce7f3', stroke: '#db2777', text: '#9d174d', icon: '#ec4899' },
        email:         { fill: '#e0e7ff', stroke: '#4f46e5', text: '#3730a3', icon: '#6366f1' },
        delay:         { fill: '#f3e8ff', stroke: '#7c3aed', text: '#5b21b6', icon: '#8b5cf6' },
        wait:          { fill: '#f3e8ff', stroke: '#7c3aed', text: '#5b21b6', icon: '#8b5cf6' },
        update_field:  { fill: '#d1fae5', stroke: '#059669', text: '#065f46', icon: '#10b981' },
        create_record: { fill: '#ccfbf1', stroke: '#0d9488', text: '#115e59', icon: '#14b8a6' },
        call_api:      { fill: '#fee2e2', stroke: '#dc2626', text: '#991b1b', icon: '#ef4444' },
        run_rule:      { fill: '#fff7ed', stroke: '#ea580c', text: '#9a3412', icon: '#f97316' }
    };

    let DEFAULT_STEP_COLOR = { fill: '#f1f5f9', stroke: '#64748b', text: '#334155', icon: '#94a3b8' };

    function stepColor(type) {
        return STEP_COLORS[type] || DEFAULT_STEP_COLOR;
    }

    /* -- SVG icon paths (16x16 viewbox, simplified) -------------- */
    let STEP_ICONS = {
        trigger:       'M3 3l5 5-5 5M11 3h5v10h-5',
        condition:     'M8 2l6 6-6 6-6-6z',
        approval:      'M8 1a7 7 0 100 14A7 7 0 008 1zm-1 10l-3-3 1-1 2 2 4-4 1 1z',
        email:         'M2 4h12v8H2zm0 0l6 4 6-4',
        delay:         'M8 1a7 7 0 100 14A7 7 0 008 1zm0 3v4l3 2',
        wait:          'M8 1a7 7 0 100 14A7 7 0 008 1zm0 3v4l3 2',
        update_field:  'M11.5 1.5l3 3L5 14H2v-3zm-1 4l3 3',
        create_record: 'M8 2v12M2 8h12',
        call_api:      'M2 4h3v8H2zm5-2h2v12H7zm5 4h2v4h-2',
        run_rule:      'M4 2l8 6-8 6z'
    };

    /* -- Step palette for the designer sidebar ------------------- */
    let PALETTE = [
        { type: 'trigger',       label: 'Trigger',        category: 'Start' },
        { type: 'condition',     label: 'Condition',      category: 'Logic' },
        { type: 'approval',      label: 'Approval',       category: 'Human' },
        { type: 'email',         label: 'Send Email',     category: 'Action' },
        { type: 'delay',         label: 'Wait / Delay',   category: 'Logic' },
        { type: 'update_field',  label: 'Update Field',   category: 'Action' },
        { type: 'create_record', label: 'Create Record',  category: 'Action' },
        { type: 'call_api',      label: 'Call API',       category: 'Action' },
        { type: 'run_rule',      label: 'Run Rule',       category: 'Action' }
    ];

    /* -- Port layout (1 input left, 1 output right; conditions get 2 outputs) -- */
    function portConfig(type) {
        let color = stepColor(type);
        let inPort = {
            group: 'in',
            id: 'in',
            attrs: {
                circle: { r: 6, fill: color.stroke, stroke: '#fff', strokeWidth: 2, magnet: 'passive' }
            }
        };

        let ports = [inPort];

        if (type === 'condition') {
            ports.push({
                group: 'out-true',
                id: 'out-true',
                attrs: {
                    circle: { r: 6, fill: '#16a34a', stroke: '#fff', strokeWidth: 2, magnet: true },
                    text: { text: 'T', fontSize: 8, fill: '#16a34a', refY: 14 }
                }
            });
            ports.push({
                group: 'out-false',
                id: 'out-false',
                attrs: {
                    circle: { r: 6, fill: '#dc2626', stroke: '#fff', strokeWidth: 2, magnet: true },
                    text: { text: 'F', fontSize: 8, fill: '#dc2626', refY: 14 }
                }
            });
        } else {
            ports.push({
                group: 'out',
                id: 'out',
                attrs: {
                    circle: { r: 6, fill: color.stroke, stroke: '#fff', strokeWidth: 2, magnet: true }
                }
            });
        }

        return ports;
    }

    /* -- Shape factory: creates a JointJS element for a step ----- */
    function createStep(graph, stepDef) {
        let type = stepDef.type || 'call_api';
        let color = stepColor(type);
        let paletteItem = null;
        for (let i = 0; i < PALETTE.length; i++) {
            if (PALETTE[i].type === type) { paletteItem = PALETTE[i]; break; }
        }
        let label = stepDef.label || (paletteItem ? paletteItem.label : type);

        let width = 180;
        let height = 60;
        let x = (stepDef.position && stepDef.position.x) || 100;
        let y = (stepDef.position && stepDef.position.y) || 100;

        let el = new joint.shapes.standard.Rectangle({
            position: { x: x, y: y },
            size: { width: width, height: height },
            attrs: {
                body: {
                    fill: color.fill,
                    stroke: color.stroke,
                    strokeWidth: 2,
                    rx: 8,
                    ry: 8,
                    filter: { name: 'dropShadow', args: { dx: 0, dy: 1, blur: 3, opacity: 0.1 } }
                },
                label: {
                    text: label,
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: 'Inter, system-ui, sans-serif',
                    fill: color.text,
                    refX: '50%',
                    refY: '50%',
                    textAnchor: 'middle',
                    textVerticalAnchor: 'middle'
                }
            },
            ports: {
                groups: {
                    'in':        { position: { name: 'left' },  attrs: { circle: { magnet: 'passive' } } },
                    'out':       { position: { name: 'right' }, attrs: { circle: { magnet: true } } },
                    'out-true':  { position: { name: 'right',  args: { dy: -10 } }, attrs: { circle: { magnet: true } } },
                    'out-false': { position: { name: 'right',  args: { dy: 10 } },  attrs: { circle: { magnet: true } } }
                },
                items: portConfig(type)
            }
        });

        // Attach metadata for serialization
        el.set('stepType', type);
        el.set('stepId', stepDef.id || 'step-' + Date.now());
        el.set('stepProperties', stepDef.properties || {});

        if (graph) graph.addCell(el);
        return el;
    }

    /* -- Serialize graph back to workflow definition JSON --------- */
    function serializeGraph(graph) {
        let elements = graph.getElements();
        let links = graph.getLinks();

        let steps = elements.map(function(el) {
            let pos = el.position();
            return {
                id: el.get('stepId'),
                type: el.get('stepType'),
                position: { x: pos.x, y: pos.y },
                properties: el.get('stepProperties') || {}
            };
        });

        let connections = links.map(function(link) {
            let sourceEl = link.getSourceElement();
            let targetEl = link.getTargetElement();
            let sourceId = sourceEl ? sourceEl.get('stepId') : null;
            let targetId = targetEl ? targetEl.get('stepId') : null;
            let sourcePort = link.source() ? link.source().port : '';
            let label = '';
            if (sourcePort === 'out-true') label = 'true';
            if (sourcePort === 'out-false') label = 'false';

            return { from: sourceId, to: targetId, label: label };
        }).filter(function(c) { return c.from && c.to; });

        return { steps: steps, connections: connections };
    }

    /* -- Deserialize workflow definition into graph elements ------ */
    function loadWorkflow(graph, workflowDef) {
        graph.clear();

        let elementMap = {};
        let steps = workflowDef.steps || [];
        let connections = workflowDef.connections || [];

        steps.forEach(function(stepDef) {
            let el = createStep(graph, stepDef);
            elementMap[stepDef.id] = el;
        });

        connections.forEach(function(conn) {
            let source = elementMap[conn.from];
            let target = elementMap[conn.to];
            if (!source || !target) return;

            let sourcePort = 'out';
            if (conn.label === 'true') sourcePort = 'out-true';
            if (conn.label === 'false') sourcePort = 'out-false';

            let link = new joint.shapes.standard.Link({
                source: { id: source.id, port: sourcePort },
                target: { id: target.id, port: 'in' },
                attrs: {
                    line: {
                        stroke: '#64748b',
                        strokeWidth: 2,
                        targetMarker: { type: 'path', d: 'M 10 -5 0 0 10 5 z', fill: '#64748b' }
                    }
                },
                labels: conn.label ? [{
                    attrs: {
                        text: { text: conn.label, fontSize: 10, fontWeight: 500, fill: '#64748b' },
                        rect: { fill: '#fff', stroke: '#e2e8f0', rx: 3, ry: 3 }
                    },
                    position: { distance: 0.5, offset: -12 }
                }] : []
            });
            graph.addCell(link);
        });
    }

    /* -- Public API ----------------------------------------------- */
    return {
        STEP_COLORS: STEP_COLORS,
        STEP_ICONS: STEP_ICONS,
        PALETTE: PALETTE,
        stepColor: stepColor,
        portConfig: portConfig,
        createStep: createStep,
        serializeGraph: serializeGraph,
        loadWorkflow: loadWorkflow
    };
})();
