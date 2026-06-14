/**
 * JointJS UML Class Diagram shapes for Code Workbench.
 * Renders classes from the enriched UML snapshot as interactive boxes.
 */
(function(joint) {
    'use strict';

    if (!joint || !joint.dia) {
        console.warn('JointJS not loaded — UML shapes skipped');
        return;
    }

    // UML Class shape
    const UMLClass = joint.dia.Element.define('uml.Class', {
        attrs: {
            body: {
                refWidth: '100%',
                refHeight: '100%',
                fill: '#f0fdf4',
                stroke: '#86efac',
                strokeWidth: 2,
                rx: 8,
                ry: 8,
            },
            headerRect: {
                refWidth: '100%',
                height: 32,
                fill: '#dcfce7',
                stroke: '#86efac',
                strokeWidth: 1,
                rx: 8,
                ry: 8,
            },
            className: {
                refX: '50%',
                y: 20,
                textAnchor: 'middle',
                fontWeight: 700,
                fontSize: 13,
                fontFamily: 'Inter, system-ui, sans-serif',
                fill: '#166534',
            },
            separator: {
                refWidth: '100%',
                y: 32,
                d: 'M 0 0 L calc(w) 0',
                stroke: '#86efac',
                strokeWidth: 1,
            },
            fields: {
                refX: 8,
                y: 44,
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
                fill: '#374151',
                lineHeight: 18,
            },
        },
    }, {
        markup: [
            { tagName: 'rect', selector: 'body' },
            { tagName: 'rect', selector: 'headerRect' },
            { tagName: 'text', selector: 'className' },
            { tagName: 'path', selector: 'separator' },
            { tagName: 'text', selector: 'fields' },
        ],
    });

    /**
     * Render a class diagram on a JointJS paper.
     * @param {HTMLElement} container - DOM element to render into
     * @param {Object} classDiagram - UML class_diagram from snapshot
     * @param {Object} opts - { width, height, onClassClick }
     * @returns {{ graph, paper }} - JointJS instances
     */
    function renderClassDiagram(container, classDiagram, opts) {
        opts = opts || {};
        const width = opts.width || container.clientWidth || 800;
        const height = opts.height || 600;

        const graph = new joint.dia.Graph();
        const paper = new joint.dia.Paper({
            el: container,
            model: graph,
            width: width,
            height: height,
            gridSize: 20,
            drawGrid: { name: 'dot', args: { color: '#e5e7eb' } },
            background: { color: '#fafafa' },
            interactive: { elementMove: true, addLinkFromMagnet: false },
        });

        const classes = (classDiagram && classDiagram.classes) || [];
        const elements = [];
        const classPositions = {};

        // Create class elements
        classes.forEach(function(cls, idx) {
            const fieldLines = (cls.fields || []).map(function(f) {
                const typeStr = f.type || 'str';
                const nullable = f.nullable ? '?' : '';
                const pk = f.primary_key ? ' PK' : '';
                const fk = f.foreign_key ? ' FK→' + f.foreign_key : '';
                return f.name + ': ' + typeStr + nullable + pk + fk;
            });

            const boxHeight = 44 + (fieldLines.length * 18) + 12;
            const boxWidth = 220;

            // Auto-layout: grid with 3 columns
            const col = idx % 3;
            const row = Math.floor(idx / 3);
            const x = 40 + col * 260;
            const y = 40 + row * (boxHeight + 40);

            const el = new UMLClass({
                position: { x: x, y: y },
                size: { width: boxWidth, height: boxHeight },
                attrs: {
                    className: { text: cls.name },
                    fields: { text: fieldLines.join('\n') },
                },
                classData: cls,
            });

            elements.push(el);
            classPositions[cls.name] = el.id;
        });

        graph.addCells(elements);

        // Add relationship links
        classes.forEach(function(cls) {
            (cls.relationships || []).forEach(function(rel) {
                const sourceId = classPositions[cls.name];
                const targetId = classPositions[rel.target_class];
                if (sourceId && targetId) {
                    const link = new joint.shapes.standard.Link({
                        source: { id: sourceId },
                        target: { id: targetId },
                        attrs: {
                            line: {
                                stroke: '#6b7280',
                                strokeWidth: 1.5,
                                targetMarker: {
                                    type: rel.type === 'one_to_many' ? 'path' : 'classic',
                                    d: rel.type === 'one_to_many' ? 'M 0 -5 L 10 0 L 0 5' : 'M 10 -5 0 0 10 5 z',
                                    fill: '#6b7280',
                                },
                            },
                        },
                        labels: [{
                            position: 0.5,
                            attrs: {
                                text: { text: rel.type.replace('_', ':'), fontSize: 10, fill: '#9ca3af' },
                                rect: { fill: '#fafafa', rx: 3, ry: 3 },
                            },
                        }],
                    });
                    graph.addCell(link);
                }
            });
        });

        // Click handler
        if (opts.onClassClick) {
            paper.on('element:pointerclick', function(elementView) {
                const classData = elementView.model.get('classData');
                if (classData) {
                    opts.onClassClick(classData);
                }
            });
        }

        // Auto-fit
        paper.scaleContentToFit({ padding: 20, maxScale: 1.2 });

        return { graph: graph, paper: paper };
    }

    // Export
    window.UMLShapes = {
        UMLClass: UMLClass,
        renderClassDiagram: renderClassDiagram,
    };

})(window.joint);
