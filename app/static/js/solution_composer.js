/**
 * Solution Composer - External JavaScript
 * Extracted from solution_composer.html inline scripts
 * Depends on: window.__APP_CONFIG__ (injected by template)
 * Depends on: React 18, ReactDOM 18, react-flow-renderer 11.x
 * Note: This file contains JSX syntax and requires Babel standalone
 *       to be loaded with type="text/babel" on the script tag.
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

let apiBasePalette = APP_CONFIG.apiPaletteUrl || '/api/solution-composer/palette';
let apiBaseRelationshipTypes = APP_CONFIG.apiRelationshipTypesUrl || '/api/solution-composer/relationship-types';
let apiBaseValidateConnection = APP_CONFIG.apiValidateConnectionUrl || '/api/solution-composer/validate-connection';
let apiBaseConnections = APP_CONFIG.apiConnectionsUrl || '/api/solution-composer/connections';
let apiBaseNodes = APP_CONFIG.apiNodesUrl || '/api/solution-composer/nodes';
let apiBaseCanvas = APP_CONFIG.apiCanvasUrl || '/api/solution-composer/canvas';
let apiBaseValidate = APP_CONFIG.apiValidateUrl || '/api/solution-composer/validate';
let apiBaseExport = APP_CONFIG.apiExportUrl || '/api/solution-composer/export-archimate';

const { useState, useCallback, useEffect, useMemo, useRef } = React;
const ReactFlow = window.ReactFlowRenderer;
const {
    ReactFlowProvider,
    useNodesState,
    useEdgesState,
    addEdge,
    Controls,
    Background,
    MiniMap
} = ReactFlow;

// API utility
const api = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    async put(url, data) {
        const response = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    async delete(url) {
        const response = await fetch(url, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }
};

// Custom node component
const CustomNode = ({ data }) => {
    return (
        <div>
            <div className="node-header">{data.label}</div>
            <div className="node-type">{data.type}</div>
        </div>
    );
};

const nodeTypes = {
    custom: CustomNode
};

// Solution templates
const SOLUTION_TEMPLATES = [
    {
        id: 'cloud-migration',
        name: 'Cloud Migration Solution',
        category: 'Infrastructure',
        description: 'Template for cloud migration projects with hybrid architecture',
        nodes: [
            { type: 'application', label: 'Legacy System', x: 100, y: 100 },
            { type: 'capability', label: 'Migration Service', x: 300, y: 100 },
            { type: 'vendor_product', label: 'Cloud Platform', x: 500, y: 100 }
        ],
        connections: [
            { from: 0, to: 1, relationship: 'serving' },
            { from: 1, to: 2, relationship: 'assignment' }
        ]
    },
    {
        id: 'api-integration',
        name: 'API Integration Hub',
        category: 'Integration',
        description: 'Central API gateway pattern with microservices',
        nodes: [
            { type: 'application', label: 'API Gateway', x: 300, y: 100 },
            { type: 'application', label: 'Service A', x: 150, y: 250 },
            { type: 'application', label: 'Service B', x: 300, y: 250 },
            { type: 'application', label: 'Service C', x: 450, y: 250 }
        ],
        connections: [
            { from: 0, to: 1, relationship: 'serving' },
            { from: 0, to: 2, relationship: 'serving' },
            { from: 0, to: 3, relationship: 'serving' }
        ]
    },
    {
        id: 'data-pipeline',
        name: 'Data Pipeline Architecture',
        category: 'Data',
        description: 'ETL pipeline with data lake and analytics',
        nodes: [
            { type: 'application', label: 'Data Source', x: 100, y: 100 },
            { type: 'capability', label: 'ETL Process', x: 300, y: 100 },
            { type: 'application', label: 'Data Lake', x: 500, y: 100 },
            { type: 'application', label: 'Analytics Engine', x: 500, y: 250 }
        ],
        connections: [
            { from: 0, to: 1, relationship: 'flow' },
            { from: 1, to: 2, relationship: 'access' },
            { from: 2, to: 3, relationship: 'serving' }
        ]
    },
    {
        id: 'security-layers',
        name: 'Security Layered Architecture',
        category: 'Security',
        description: 'Defense in depth security architecture',
        nodes: [
            { type: 'application', label: 'Firewall', x: 100, y: 100 },
            { type: 'application', label: 'WAF', x: 250, y: 100 },
            { type: 'application', label: 'Application', x: 400, y: 100 },
            { type: 'capability', label: 'Monitoring', x: 250, y: 250 }
        ],
        connections: [
            { from: 0, to: 1, relationship: 'flow' },
            { from: 1, to: 2, relationship: 'flow' },
            { from: 3, to: 2, relationship: 'serving' }
        ]
    }
];

// Sidebar Tabs Component
function SidebarTabs({ searchTerm, setSearchTerm, groupedPalette, onDragStart, onLoadTemplate }) {
    const [activeTab, setActiveTab] = useState('elements');

    return (
        <div className="composer-sidebar">
            <div className="tabs">
                <div
                    className={`tab ${activeTab === 'elements' ? 'active' : ''}`}
                    onClick={() => setActiveTab('elements')}
                >
                    Elements
                </div>
                <div
                    className={`tab ${activeTab === 'templates' ? 'active' : ''}`}
                    onClick={() => setActiveTab('templates')}
                >
                    Templates
                </div>
            </div>

            {/* Elements Tab */}
            <div className={`tab-content ${activeTab === 'elements' ? 'active' : ''}`}>
                <div className="search-box">
                    <input
                        type="text"
                        placeholder="Search elements..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                {/* Vendor Products */}
                {groupedPalette.vendor_product?.length > 0 && (
                    <div className="palette-section">
                        <h3>Vendor Products</h3>
                        {groupedPalette.vendor_product.map(item => (
                            <div
                                key={`vendor-${item.source_id}`}
                                className="palette-item"
                                draggable
                                onDragStart={(e) => onDragStart(e, item)}
                            >
                                <div className="palette-item-header">
                                    <div className="palette-item-name">{item.name}</div>
                                    <div className="palette-item-type">Vendor</div>
                                </div>
                                {item.vendor && (
                                    <div className="palette-item-description">
                                        {item.vendor}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* Applications */}
                {groupedPalette.application?.length > 0 && (
                    <div className="palette-section">
                        <h3>Applications</h3>
                        {groupedPalette.application.map(item => (
                            <div
                                key={`app-${item.source_id}`}
                                className="palette-item"
                                draggable
                                onDragStart={(e) => onDragStart(e, item)}
                            >
                                <div className="palette-item-header">
                                    <div className="palette-item-name">{item.name}</div>
                                    <div className="palette-item-type">App</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Capabilities */}
                {groupedPalette.capability?.length > 0 && (
                    <div className="palette-section">
                        <h3>Capabilities</h3>
                        {groupedPalette.capability.map(item => (
                            <div
                                key={`cap-${item.source_id}`}
                                className="palette-item"
                                draggable
                                onDragStart={(e) => onDragStart(e, item)}
                            >
                                <div className="palette-item-header">
                                    <div className="palette-item-name">{item.name}</div>
                                    <div className="palette-item-type">Capability</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Templates Tab */}
            <div className={`tab-content ${activeTab === 'templates' ? 'active' : ''}`}>
                <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontSize: '0.875rem', color: '#6b7280', lineHeight: '1.5' }}>
                        Pre-built solution patterns based on common architecture scenarios
                    </p>
                </div>

                <div className="template-grid">
                    {SOLUTION_TEMPLATES.map(template => (
                        <div
                            key={template.id}
                            className="template-card"
                            onClick={() => onLoadTemplate(template)}
                        >
                            <div className="template-header">
                                <div className="template-name">{template.name}</div>
                                <div className="template-category">{template.category}</div>
                            </div>
                            <div className="template-description">{template.description}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// Main composer component
function SolutionComposer() {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [paletteItems, setPaletteItems] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [validationResults, setValidationResults] = useState(null);
    const [canvasName, setCanvasName] = useState('Untitled Solution');
    const [canvasId, setCanvasId] = useState(null);
    const reactFlowWrapper = useRef(null);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);

    // Load palette items on mount
    useEffect(() => {
        loadPalette();
    }, []);

    const loadPalette = async () => {
        try {
            setIsLoading(true);
            const response = await api.get(apiBasePalette);
            if (response.success) {
                setPaletteItems(response.data.items || []);
            }
        } catch (error) {
            console.error('Failed to load palette:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Load template - creates nodes and connections from template
    const loadTemplate = async (template) => {
        try {
            const shouldLoad = await new Promise(function(resolve) {
                let modalId = window.modalManager.createModal({
                    title: 'Load Template',
                    content: '<p class="text-sm text-muted-foreground">Load template &ldquo;' + template.name + '&rdquo;? This will clear your current canvas.</p>',
                    size: 'small',
                    buttons: [
                        { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() { resolve(false); } },
                        { text: 'Load Template', class: 'px-4 py-2 text-sm font-medium text-primary-foreground bg-primary border border-transparent rounded-md hover:bg-primary/90', action: 'load', handler: function() { resolve(true); } }
                    ]
                });
                window.modalManager.open(modalId);
            });
            if (!shouldLoad) {
                return;
            }

            setIsLoading(true);

            // Clear current canvas
            setNodes([]);
            setEdges([]);

            // Create nodes from template
            const newNodes = template.nodes.map((node, idx) => ({
                id: `node-${Date.now()}-${idx}`,
                type: 'custom',
                position: { x: node.x, y: node.y },
                data: {
                    label: node.label,
                    type: node.type,
                    sourceType: node.type
                },
                className: `react-flow__node-${node.type}`
            }));

            setNodes(newNodes);

            // Create connections from template
            setTimeout(() => {
                const newEdges = template.connections.map((conn, idx) => ({
                    id: `edge-${Date.now()}-${idx}`,
                    source: newNodes[conn.from].id,
                    target: newNodes[conn.to].id,
                    type: 'smoothstep',
                    animated: true,
                    label: conn.relationship,
                    data: { relationshipType: conn.relationship }
                }));

                setEdges(newEdges);
                setCanvasName(template.name);
            }, 100);

        } catch (error) {
            console.error('Failed to load template:', error);
            Platform.toast.error('Failed to load template');
        } finally {
            setIsLoading(false);
        }
    };

    // Relationship selector state
    const [showRelationshipSelector, setShowRelationshipSelector] = useState(false);
    const [pendingConnection, setPendingConnection] = useState(null);
    const [relationshipTypes, setRelationshipTypes] = useState([]);
    const [selectedRelationship, setSelectedRelationship] = useState(null);

    // Selected node for properties panel
    const [selectedNode, setSelectedNode] = useState(null);

    // Load relationship types on mount
    useEffect(() => {
        loadRelationshipTypes();
    }, []);

    const loadRelationshipTypes = async () => {
        try {
            const response = await api.get(apiBaseRelationshipTypes);
            if (response.success) {
                setRelationshipTypes(response.data.relationship_types || []);
            }
        } catch (error) {
            console.error('Failed to load relationship types:', error);
        }
    };

    // Handle edge connection with validation - NOW WITH RELATIONSHIP SELECTOR
    const onConnect = useCallback(async (params) => {
        // Store pending connection and show relationship selector
        setPendingConnection(params);
        setShowRelationshipSelector(true);
    }, []);

    // Confirm relationship selection and create connection
    const confirmRelationship = async () => {
        if (!pendingConnection || !selectedRelationship) return;

        try {
            const validation = await api.post(apiBaseValidateConnection, {
                source_node_id: pendingConnection.source,
                target_node_id: pendingConnection.target,
                relationship_type: selectedRelationship.type
            });

            if (validation.success && validation.data.is_valid) {
                setEdges((eds) => addEdge({
                    ...pendingConnection,
                    type: 'smoothstep',
                    animated: true,
                    label: selectedRelationship.label,
                    data: { relationshipType: selectedRelationship.type }
                }, eds));

                // Add connection to backend
                await api.post(apiBaseConnections, {
                    connection_id: `edge-${Date.now()}`,
                    source_node_id: pendingConnection.source,
                    target_node_id: pendingConnection.target,
                    relationship_type: selectedRelationship.type,
                    label: selectedRelationship.label
                });
            } else {
                Platform.toast.error(`Invalid connection: ${validation.data.message || 'ArchiMate rules violated'}`);
            }
        } catch (error) {
            console.error('Connection validation failed:', error);
            Platform.toast.error('Failed to create connection');
        } finally {
            setShowRelationshipSelector(false);
            setPendingConnection(null);
            setSelectedRelationship(null);
        }
    };

    // Handle drag from palette
    const onDragStart = (event, nodeData) => {
        event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeData));
        event.dataTransfer.effectAllowed = 'move';
    };

    const onDrop = useCallback(
        (event) => {
            event.preventDefault();

            const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
            const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));

            if (nodeData && reactFlowInstance) {
                const position = reactFlowInstance.project({
                    x: event.clientX - reactFlowBounds.left,
                    y: event.clientY - reactFlowBounds.top,
                });

                const newNode = {
                    id: `node-${Date.now()}`,
                    type: 'custom',
                    position,
                    data: {
                        label: nodeData.name,
                        type: nodeData.element_type,
                        sourceType: nodeData.source_type,
                        sourceId: nodeData.source_id
                    },
                    className: `react-flow__node-${nodeData.source_type}`
                };

                setNodes((nds) => nds.concat(newNode));

                // Add to backend
                api.post(apiBaseNodes, {
                    node_id: newNode.id,
                    element_type: nodeData.element_type,
                    name: nodeData.name,
                    source_type: nodeData.source_type,
                    source_id: nodeData.source_id,
                    position_x: position.x,
                    position_y: position.y
                }).catch(err => console.error('Failed to add node:', err));
            }
        },
        [reactFlowInstance, setNodes]
    );

    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    // Create new canvas
    const handleNew = () => {
        if (nodes.length > 0 || edges.length > 0) {
            let modalId = window.modalManager.createModal({
                title: 'New Canvas',
                content: '<p class="text-sm text-muted-foreground">Create a new canvas? Unsaved changes will be lost.</p>',
                size: 'small',
                buttons: [
                    { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                    { text: 'Create New', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'new', handler: function() {
                        setCanvasName('Untitled Solution');
                        setCanvasId(null);
                        setNodes([]);
                        setEdges([]);
                        setSelectedNode(null);
                    } }
                ]
            });
            window.modalManager.open(modalId);
            return;
        }
        setCanvasName('Untitled Solution');
        setCanvasId(null);
        setNodes([]);
        setEdges([]);
        setSelectedNode(null);
    };

        // Save canvas
    const handleSave = async () => {
        try {
            setIsLoading(true);
            let response;

            if (canvasId) {
                // Update existing canvas
                response = await api.put(apiBaseCanvas + '/' + canvasId, {
                    name: canvasName,
                    nodes: nodes,
                    edges: edges
                });
            } else {
                // Create new canvas
                response = await api.post(apiBaseCanvas, {
                    name: canvasName,
                    nodes: nodes,
                    edges: edges
                });

                if (response.success && response.data.id) {
                    setCanvasId(response.data.id);
                }
            }

            if (response.success) {
                Platform.toast.success('Canvas saved successfully!');
            }
        } catch (error) {
            Platform.toast.error('Failed to save canvas');
            console.error('Save failed:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Validate canvas
    const handleValidate = async () => {
        try {
            const response = await api.get(apiBaseValidate);
            if (response.success) {
                setValidationResults(response.data);
            }
        } catch (error) {
            console.error('Validation failed:', error);
        }
    };

    // Clear canvas
    const handleClear = () => {
        let modalId = window.modalManager.createModal({
            title: 'Clear Canvas',
            content: '<p class="text-sm text-muted-foreground">Clear the entire canvas? This cannot be undone.</p>',
            size: 'small',
            buttons: [
                { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                { text: 'Clear Canvas', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'clear', handler: function() {
                    setNodes([]);
                    setEdges([]);
                } }
            ]
        });
        window.modalManager.open(modalId);
    };

    // Export to ArchiMate XML
    const handleExportXML = async () => {
        try {
            setIsLoading(true);
            const response = await api.post(apiBaseExport);
            if (response.success) {
                // Create download link for XML
                const blob = new Blob([response.data.xml], { type: 'application/xml' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${canvasName.replace(/\s+/g, '_')}_archimate.xml`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                Platform.toast.success('ArchiMate XML exported successfully!');
            }
        } catch (error) {
            Platform.toast.error('Failed to export ArchiMate XML');
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    // Handle node selection
    const onNodeClick = useCallback((event, node) => {
        setSelectedNode(node);
    }, []);

    // Update selected node properties
    const updateNodeProperty = async (property, value) => {
        if (!selectedNode) return;

        const updatedNode = {
            ...selectedNode,
            data: {
                ...selectedNode.data,
                [property]: value
            }
        };

        setSelectedNode(updatedNode);
        setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? updatedNode : n));

        // Persist to backend if needed
        try {
            await api.put(apiBaseNodes + '/' + selectedNode.id, {
                [property]: value
            });
        } catch (error) {
            console.error('Failed to update node:', error);
        }
    };

    // Filter palette items
    const filteredPalette = useMemo(() => {
        if (!searchTerm) return paletteItems;
        const term = searchTerm.toLowerCase();
        return paletteItems.filter(item =>
            item.name.toLowerCase().includes(term) ||
            (item.vendor && item.vendor.toLowerCase().includes(term))
        );
    }, [paletteItems, searchTerm]);

    // Group palette by source type
    const groupedPalette = useMemo(() => {
        const groups = {
            vendor_product: [],
            application: [],
            capability: []
        };
        filteredPalette.forEach(item => {
            if (groups[item.source_type]) {
                groups[item.source_type].push(item);
            }
        });
        return groups;
    }, [filteredPalette]);

    return (
        <div className="solution-composer">
            <div className="composer-header">
                <div>
                    <input
                        type="text"
                        value={canvasName}
                        onChange={(e) => setCanvasName(e.target.value)}
                        className="text-xl font-semibold border-none focus:outline-none"
                        style={{ border: 'none', outline: 'none' }}
                    />
                    <p className="text-sm text-muted-foreground mt-1">
                        Drag and drop elements to compose your solution architecture
                    </p>
                </div>
                <div className="flex gap-2">
                    <button onClick={handleClear} className="px-4 py-2 text-sm">
                        Clear
                    </button>
                    <button onClick={handleValidate} className="px-4 py-2 text-sm">
                        Validate
                    </button>
                    <button onClick={handleExportXML} className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded">
                        Export ArchiMate XML
                    </button>
                    <button onClick={handleSave} className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded">
                        Save
                    </button>
                </div>
            </div>

            <div className="composer-workspace">
                {/* Sidebar with palette and templates */}
                <SidebarTabs
                    searchTerm={searchTerm}
                    setSearchTerm={setSearchTerm}
                    groupedPalette={groupedPalette}
                    onDragStart={onDragStart}
                    onLoadTemplate={loadTemplate}
                />

                {/* Canvas */}
                <div className="composer-canvas" ref={reactFlowWrapper}>
                    {isLoading && (
                        <div className="loading-overlay">
                            <div className="spinner"></div>
                        </div>
                    )}

                    <ReactFlowProvider>
                        <ReactFlow
                            nodes={nodes}
                            edges={edges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            onConnect={onConnect}
                            onDrop={onDrop}
                            onDragOver={onDragOver}
                            onInit={setReactFlowInstance}
                            onNodeClick={onNodeClick}
                            nodeTypes={nodeTypes}
                            fitView
                        >
                            <Background />
                            <Controls />
                            <MiniMap />
                        </ReactFlow>
                    </ReactFlowProvider>

                    {nodes.length === 0 && !isLoading && (
                        <div className="empty-state">
                            <div className="empty-state-icon">🎨</div>
                            <h3>Start Composing</h3>
                            <p>Drag elements from the sidebar to build your solution</p>
                        </div>
                    )}

                    {validationResults && (
                        <div className="validation-panel">
                            <h4 className="font-semibold mb-2">Validation Results</h4>
                            {validationResults.errors?.map((error, idx) => (
                                <div key={idx} className="validation-item error">
                                    <div className="text-sm">{error.message}</div>
                                </div>
                            ))}
                            {validationResults.warnings?.map((warning, idx) => (
                                <div key={idx} className="validation-item warning">
                                    <div className="text-sm">{warning.message}</div>
                                </div>
                            ))}
                            {!validationResults.errors?.length && !validationResults.warnings?.length && (
                                <div className="validation-item success">
                                    <div className="text-sm">✓ All connections are valid!</div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Properties Panel - Shows when a node is selected */}
                {selectedNode && (
                    <div className="properties-panel">
                        <div className="properties-section">
                            <h4>Node Properties</h4>
                            <div className="property-row">
                                <div className="property-label">Name</div>
                                <input
                                    type="text"
                                    className="property-input"
                                    value={selectedNode.data.label || ''}
                                    onChange={(e) => updateNodeProperty('label', e.target.value)}
                                />
                            </div>
                            <div className="property-row">
                                <div className="property-label">Type</div>
                                <div className="property-value">{selectedNode.data.type}</div>
                            </div>
                            <div className="property-row">
                                <div className="property-label">Source</div>
                                <div className="property-value">{selectedNode.data.sourceType}</div>
                            </div>
                        </div>

                        <div className="properties-section">
                            <h4>Position</h4>
                            <div className="property-row">
                                <div className="property-label">X</div>
                                <div className="property-value">{Math.round(selectedNode.position.x)}</div>
                            </div>
                            <div className="property-row">
                                <div className="property-label">Y</div>
                                <div className="property-value">{Math.round(selectedNode.position.y)}</div>
                            </div>
                        </div>

                        <div className="properties-section">
                            <h4>Actions</h4>
                            <button
                                onClick={() => {
                                    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
                                    setSelectedNode(null);
                                }}
                                style={{
                                    width: '100%',
                                    padding: '0.5rem 0.75rem',
                                    fontSize: '0.875rem',
                                    background: '#dc2626',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '0.375rem',
                                    cursor: 'pointer'
                                }}
                                onMouseOver={(e) => e.target.style.background = '#b91c1c'}
                                onMouseOut={(e) => e.target.style.background = '#dc2626'}
                            >
                                Delete Node
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Relationship Selector Modal */}
            {showRelationshipSelector && (
                <div className="modal-overlay" onClick={() => {
                    setShowRelationshipSelector(false);
                    setPendingConnection(null);
                    setSelectedRelationship(null);
                }}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3 className="modal-title">Choose Relationship Type</h3>
                            <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: '0.5rem' }}>
                                Select the ArchiMate relationship type for this connection
                            </p>
                        </div>
                        <div className="modal-body">
                            {relationshipTypes.map((rel) => (
                                <div
                                    key={rel.type}
                                    className={`relationship-option ${selectedRelationship?.type === rel.type ? 'selected' : ''}`}
                                    onClick={() => setSelectedRelationship(rel)}
                                >
                                    <div className="relationship-name">{rel.label}</div>
                                    <div className="relationship-category">{rel.category}</div>
                                    <div className="relationship-description">
                                        {rel.type === 'composition' && 'Part of a whole - child cannot exist without parent'}
                                        {rel.type === 'aggregation' && 'Part of a whole - child can exist independently'}
                                        {rel.type === 'assignment' && 'Allocation of behavior or resource to an active element'}
                                        {rel.type === 'realization' && 'Implementation or materialization of an abstraction'}
                                        {rel.type === 'serving' && 'Service provided to or used by another element'}
                                        {rel.type === 'access' && 'Read or write access to data or objects'}
                                        {rel.type === 'influence' && 'Change or modification of behavior or state'}
                                        {rel.type === 'triggering' && 'Temporal dependency - one enables the other'}
                                        {rel.type === 'flow' && 'Transfer of information, goods, or energy'}
                                        {rel.type === 'specialization' && 'Generalization/specialization relationship'}
                                        {rel.type === 'association' && 'Generic untyped relationship'}
                                    </div>
                                </div>
                            ))}
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                                <button
                                    onClick={() => {
                                        setShowRelationshipSelector(false);
                                        setPendingConnection(null);
                                        setSelectedRelationship(null);
                                    }}
                                    style={{
                                        padding: '0.5rem 1rem',
                                        fontSize: '0.875rem',
                                        border: '1px solid #d1d5db',
                                        borderRadius: '0.375rem',
                                        background: 'white',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={confirmRelationship}
                                    disabled={!selectedRelationship}
                                    style={{
                                        padding: '0.5rem 1rem',
                                        fontSize: '0.875rem',
                                        background: selectedRelationship ? '#3b82f6' : '#d1d5db',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '0.375rem',
                                        cursor: selectedRelationship ? 'pointer' : 'not-allowed',
                                        opacity: selectedRelationship ? 1 : 0.5
                                    }}
                                >
                                    Connect
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Render the app
const root = ReactDOM.createRoot(document.getElementById('solution-composer-root'));
root.render(<SolutionComposer />);
