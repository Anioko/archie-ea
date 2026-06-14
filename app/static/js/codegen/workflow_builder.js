/**
 * workflow_builder.js — JointJS-based visual workflow designer
 *
 * Reuses patterns from app/static/js/archimate/composer.js:
 * - joint.dia.Graph / joint.dia.Paper initialisation
 * - Custom shapes (similar to uml_shapes.js)
 * - Drag-drop palette (similar to Composer element palette)
 * - JSON serialisation (similar to composer_persistence.js)
 *
 * Returns an Alpine.js-compatible object via workflowBuilderApp().
 */

/* global joint */

function workflowBuilderApp() {
    return {
        graph: null,
        paper: null,
        selectedStep: null,
        workflowName: '',
        steps: [],
        _stepCounter: 0,

        init() {
            this.graph = new joint.dia.Graph();
            this.paper = new joint.dia.Paper({
                el: this.$refs.canvas,
                model: this.graph,
                width: '100%',
                height: 600,
                gridSize: 20,
                drawGrid: true,
                background: { color: 'var(--color-background, #ffffff)' },
                defaultLink: function () {
                    return new joint.shapes.standard.Link({
                        attrs: {
                            line: {
                                stroke: 'var(--color-primary, #6366f1)',
                                strokeWidth: 2,
                                targetMarker: { type: 'path', d: 'M 10 -5 0 0 10 5 Z' },
                            },
                        },
                    });
                },
                validateConnection: function (cellViewS, _magnetS, cellViewT, _magnetT) {
                    // No self-connections
                    return cellViewS !== cellViewT;
                },
                linkPinning: false,
                snapLinks: { radius: 30 },
            });

            this._registerShapes();
            this._setupEvents();
        },

        _registerShapes() {
            // Namespace for workflow shapes
            if (!joint.shapes.workflow) {
                joint.shapes.workflow = {};
            }

            // Base step shape — extends standard.Rectangle with in/out ports
            joint.shapes.workflow.Step = joint.shapes.standard.Rectangle.extend({
                defaults: joint.util.defaultsDeep({
                    type: 'workflow.Step',
                    size: { width: 160, height: 60 },
                    attrs: {
                        body: {
                            fill: 'var(--color-card, #ffffff)',
                            stroke: 'var(--color-border, #e5e7eb)',
                            strokeWidth: 2,
                            rx: 8,
                            ry: 8,
                        },
                        label: {
                            text: 'Step',
                            fill: 'var(--color-foreground, #111827)',
                            fontSize: 12,
                            fontFamily: 'Inter, system-ui, sans-serif',
                        },
                    },
                    ports: {
                        groups: {
                            in: {
                                position: 'top',
                                attrs: {
                                    circle: {
                                        r: 6,
                                        magnet: 'passive',
                                        fill: 'var(--color-muted, #9ca3af)',
                                        stroke: 'var(--color-border, #e5e7eb)',
                                        strokeWidth: 1,
                                    },
                                },
                            },
                            out: {
                                position: 'bottom',
                                attrs: {
                                    circle: {
                                        r: 6,
                                        magnet: true,
                                        fill: 'var(--color-primary, #6366f1)',
                                        stroke: 'var(--color-border, #e5e7eb)',
                                        strokeWidth: 1,
                                    },
                                },
                            },
                        },
                    },
                }, joint.shapes.standard.Rectangle.prototype.defaults),
            });
        },

        /**
         * Add a step of the given type to the canvas.
         * @param {string} type - One of: approval, email, wait, condition,
         *   update_field, create_record, call_api, trigger
         */
        addStep(type) {
            let stepConfig = {
                trigger:       { label: 'Trigger',        color: '#ef4444' },
                approval:      { label: 'Approval',       color: '#f59e0b' },
                email:         { label: 'Send Email',     color: '#3b82f6' },
                wait:          { label: 'Wait',           color: '#6b7280' },
                condition:     { label: 'Condition',      color: '#8b5cf6' },
                update_field:  { label: 'Update Field',   color: '#10b981' },
                create_record: { label: 'Create Record',  color: '#14b8a6' },
                call_api:      { label: 'Call API',       color: '#f97316' },
            };
            let config = stepConfig[type] || { label: type, color: '#6b7280' };

            this._stepCounter++;
            let xPos = 80 + ((this._stepCounter - 1) % 4) * 200;
            let yPos = 60 + Math.floor((this._stepCounter - 1) / 4) * 120;

            let step = new joint.shapes.workflow.Step({
                position: { x: xPos, y: yPos },
                attrs: {
                    body: { stroke: config.color, strokeWidth: 2 },
                    label: { text: config.label },
                },
                ports: {
                    items: [
                        { group: 'in' },
                        { group: 'out' },
                    ],
                },
                stepType: type,
                stepConfig: {},
            });

            this.graph.addCell(step);
            return step;
        },

        /**
         * Export the current graph as a workflow definition JSON object
         * compatible with WorkflowToN8nCompiler.compile().
         *
         * @returns {{ name: string, steps: Array, connections: Array }}
         */
        exportWorkflow() {
            let cells = this.graph.toJSON();
            let steps = [];
            let connections = [];

            cells.cells.forEach(function (cell) {
                if (cell.type === 'workflow.Step') {
                    steps.push({
                        id: cell.id,
                        type: cell.stepType || 'call_api',
                        config: cell.stepConfig || {},
                        position: cell.position,
                    });
                } else if (cell.type === 'standard.Link') {
                    if (cell.source && cell.source.id && cell.target && cell.target.id) {
                        connections.push({
                            from: cell.source.id,
                            to: cell.target.id,
                        });
                    }
                }
            });

            return {
                name: this.workflowName || 'Untitled Workflow',
                steps: steps,
                connections: connections,
            };
        },

        /**
         * Remove the currently selected step from the canvas.
         */
        removeSelected() {
            if (this.selectedStep) {
                let cell = this.graph.getCell(this.selectedStep.id);
                if (cell) {
                    cell.remove();
                }
                this.selectedStep = null;
            }
        },

        /**
         * Clear all cells from the canvas.
         */
        clearCanvas() {
            this.graph.clear();
            this.selectedStep = null;
            this._stepCounter = 0;
        },

        _setupEvents() {
            let self = this;

            // Click to select a step
            this.paper.on('cell:pointerclick', function (cellView) {
                // Deselect previous
                if (self.selectedStep) {
                    let prev = self.graph.getCell(self.selectedStep.id);
                    if (prev) {
                        prev.attr('body/strokeWidth', 2);
                    }
                }

                let model = cellView.model;
                if (model.get('type') === 'workflow.Step') {
                    model.attr('body/strokeWidth', 3);
                    self.selectedStep = {
                        id: model.id,
                        type: model.get('stepType'),
                        config: model.get('stepConfig'),
                    };
                }
            });

            // Click blank to deselect
            this.paper.on('blank:pointerclick', function () {
                if (self.selectedStep) {
                    let prev = self.graph.getCell(self.selectedStep.id);
                    if (prev) {
                        prev.attr('body/strokeWidth', 2);
                    }
                    self.selectedStep = null;
                }
            });
        },
    };
}
