/**
 * Knowledge Graph Viewer - D3.js-based interactive graph visualization
 *
 * Features:
 * - Force-directed graph layout
 * - Interactive node dragging
 * - Zoom and pan
 * - Node selection and highlighting
 * - Layer-based coloring (ArchiMate 3.2)
 * - Relationship filtering
 */

let svg, g, simulation, link, node, graphData, selectedNode;
let width, height;
let zoom;

// ArchiMate layer colors
const LAYER_COLORS = {
    'business': '#FFB74D',      // Orange
    'application': '#4FC3F7',   // Light Blue
    'technology': '#81C784',    // Green
    'physical': '#A1887F',      // Brown
    'motivation': '#9575CD',    // Purple
    'strategy': '#F06292',      // Pink
    'implementation': '#64B5F6' // Blue
};

/**
 * Initialize the graph viewer
 */
function initKnowledgeGraphViewer() {
    const container = document.getElementById('graph-container');
    width = container.clientWidth;
    height = container.clientHeight;

    // Create SVG
    svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create zoom behavior
    zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });

    svg.call(zoom);

    // Create container group for graph elements
    g = svg.append('g');

    // Add arrow markers for directed edges
    svg.append('defs').selectAll('marker')
        .data(['composition', 'aggregation', 'realization', 'serving', 'flow', 'triggering', 'default'])
        .enter().append('marker')
        .attr('id', d => `arrow-${d}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#999');

    // Initialize force simulation
    simulation = d3.forceSimulation()
        .force('link', d3.forceLink().id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));
}

/**
 * Load graph data from API
 */
async function loadGraphData() {
    try {
        showLoading(true);

        const layer = document.getElementById('layer-filter').value;
        const maxNodes = document.getElementById('max-nodes').value;

        let url = `/api/knowledge-graph/graph?max_nodes=${maxNodes}`;
        if (layer) url += `&layer=${layer}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            graphData = data.graph;
            updateStatistics(data.metadata);
            renderGraph(graphData);
        } else {
            console.error('Failed to load graph data:', data.error);
            Platform.toast.error('Failed to load graph data: ' + data.error);
        }

    } catch (error) {
        console.error('Error loading graph:', error);
        Platform.toast.error('Error loading graph: ' + error.message);
    } finally {
        showLoading(false);
    }
}

/**
 * Render the graph visualization
 */
function renderGraph(data) {
    // Clear existing elements
    g.selectAll('*').remove();

    if (!data.nodes || data.nodes.length === 0) {
        g.append('text')
            .attr('x', width / 2)
            .attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#999')
            .text('No data to display. Try adjusting filters.');
        return;
    }

    // Create links
    link = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(data.edges || [])
        .enter().append('line')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', d => Math.sqrt(2))
        .attr('marker-end', d => `url(#arrow-${d.type || 'default'})`);

    // Create nodes
    node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(data.nodes)
        .enter().append('g')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Add circles to nodes
    node.append('circle')
        .attr('r', 10)
        .attr('fill', d => LAYER_COLORS[d.layer] || '#ccc')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .on('click', handleNodeClick)
        .on('mouseover', handleNodeHover)
        .on('mouseout', handleNodeHoverOut);

    // Add labels to nodes
    node.append('text')
        .text(d => d.label)
        .attr('x', 15)
        .attr('y', 4)
        .attr('font-size', '11px')
        .attr('fill', '#333')
        .attr('pointer-events', 'none');

    // Update simulation
    simulation.nodes(data.nodes).on('tick', ticked);
    simulation.force('link').links(data.edges || []);
    simulation.alpha(1).restart();
}

/**
 * Simulation tick handler
 */
function ticked() {
    link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

    node.attr('transform', d => `translate(${d.x},${d.y})`);
}

/**
 * Drag handlers
 */
function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

/**
 * Node click handler
 */
function handleNodeClick(event, d) {
    event.stopPropagation();
    selectedNode = d;

    // Highlight selected node
    node.selectAll('circle')
        .attr('stroke', n => n === d ? '#ff6b6b' : '#fff')
        .attr('stroke-width', n => n === d ? 3 : 2);

    // Show node info
    const infoPanel = document.getElementById('node-info');
    const nodeName = document.getElementById('node-name');
    const nodeDetails = document.getElementById('node-details');
    const nodeActions = document.getElementById('node-actions');

    nodeName.textContent = d.label;
    safeHTML(nodeDetails, `
        <div><strong>Type:</strong> ${d.type}</div>
        <div><strong>Layer:</strong> ${d.layer}</div>
        ${d.description ? `<div class="mt-2">${d.description}</div>` : ''}
    `);
    nodeActions.style.display = 'flex';
    infoPanel.classList.add('active');
}

/**
 * Node hover handlers
 */
function handleNodeHover(event, d) {
    d3.select(event.target)
        .transition()
        .duration(200)
        .attr('r', 12);
}

function handleNodeHoverOut(event, d) {
    d3.select(event.target)
        .transition()
        .duration(200)
        .attr('r', 10);
}

/**
 * Show neighbors of selected node
 */
async function showNeighbors() {
    if (!selectedNode) {
        Platform.toast.warning('Please select a node first');
        return;
    }

    try {
        const nodeId = selectedNode.id.split('_')[1]; // Extract ID from "archimate_123"
        const response = await fetch('/ai-chat/knowledge-graph/related', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ element: nodeId })
        });
        const data = await response.json();

        if (data.success) {
            const related = data.related_entities || [];
            const subgraph = {
                nodes: [selectedNode, ...related.map(e => ({ id: e.id || e.name, label: e.name || e.id, type: e.type }))],
                edges: related.map(e => ({ source: selectedNode.id, target: e.id || e.name }))
            };
            renderGraph(subgraph);
        }
    } catch (error) {
        console.error('Error loading neighbors:', error);
        Platform.toast.error('Error loading neighbors: ' + error.message);
    }
}

/**
 * Clear node selection
 */
function clearSelection() {
    selectedNode = null;
    node.selectAll('circle')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
    document.getElementById('node-info').classList.remove('active');
}

/**
 * Apply filters and reload graph
 */
async function applyFilters() {
    await loadGraphData();
}

/**
 * Reset filters
 */
function resetFilters() {
    document.getElementById('layer-filter').value = '';
    document.getElementById('relationship-filter').value = '';
    document.getElementById('max-nodes').value = '50';
    loadGraphData();
}

/**
 * Export graph data as JSON
 */
function exportGraph() {
    if (!graphData) {
        Platform.toast.warning('No graph data to export');
        return;
    }

    const dataStr = JSON.stringify(graphData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'knowledge-graph-export.json';
    link.click();
    URL.revokeObjectURL(url);
}

/**
 * Zoom graph
 */
function zoomGraph(factor) {
    svg.transition()
        .duration(300)
        .call(zoom.scaleBy, factor);
}

/**
 * Fit graph to screen
 */
function fitGraphToScreen() {
    const bounds = g.node().getBBox();
    const fullWidth = width;
    const fullHeight = height;
    const widthScale = fullWidth / bounds.width;
    const heightScale = fullHeight / bounds.height;
    const scale = 0.9 * Math.min(widthScale, heightScale);
    const translate = [
        fullWidth / 2 - scale * (bounds.x + bounds.width / 2),
        fullHeight / 2 - scale * (bounds.y + bounds.height / 2)
    ];

    svg.transition()
        .duration(750)
        .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
}

/**
 * Find path between two nodes
 */
async function findPath() {
    const source = document.getElementById('path-source').value.trim();
    const target = document.getElementById('path-target').value.trim();

    if (!source || !target) {
        Platform.toast.warning('Please enter both source and target elements');
        return;
    }

    try {
        const response = await fetch('/ai-chat/knowledge-graph/related', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ element: source, target })
        });
        const data = await response.json();

        const resultDiv = document.getElementById('path-result');
        if (data.success && data.path) {
            safeHTML(resultDiv, `
                <div class="rounded-md bg-emerald-500/5 p-4 border border-emerald-200">
                    <div class="font-semibold text-emerald-900 mb-2">Path Found (${data.length} hops)</div>
                    <div class="text-sm text-emerald-800">${data.path.join(' \u2192 ')}</div>
                </div>
            `);
            resultDiv.style.display = 'block';

            // Highlight path in graph if visible
            highlightPath(data.path);
        } else {
            safeHTML(resultDiv, `
                <div class="rounded-md bg-amber-500/5 p-4 border border-amber-200">
                    <div class="text-sm text-amber-800">${data.message || 'No path found'}</div>
                </div>
            `);
            resultDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error finding path:', error);
        Platform.toast.error('Error finding path: ' + error.message);
    }
}

/**
 * Highlight path in graph
 */
function highlightPath(path) {
    if (!node) return;

    const pathSet = new Set(path);

    node.selectAll('circle')
        .attr('stroke', d => pathSet.has(d.id) ? '#ff6b6b' : '#fff')
        .attr('stroke-width', d => pathSet.has(d.id) ? 3 : 2)
        .attr('r', d => pathSet.has(d.id) ? 12 : 10);
}

/**
 * Update statistics display
 */
function updateStatistics(metadata) {
    document.getElementById('total-nodes').textContent = metadata.total_nodes || 0;
    document.getElementById('total-edges').textContent = metadata.total_edges || 0;
    document.getElementById('displayed-nodes').textContent = metadata.displayed_nodes || 0;
    document.getElementById('displayed-edges').textContent = metadata.displayed_edges || 0;
}

/**
 * Show/hide loading indicator
 */
function showLoading(show) {
    // Could add a loading spinner here
    if (show) {
        document.getElementById('graph-container').style.opacity = '0.5';
    } else {
        document.getElementById('graph-container').style.opacity = '1';
    }
}

// Handle window resize
window.addEventListener('resize', () => {
    const container = document.getElementById('graph-container');
    width = container.clientWidth;
    height = container.clientHeight;

    if (svg) {
        svg.attr('width', width).attr('height', height);
        simulation.force('center', d3.forceCenter(width / 2, height / 2));
        simulation.alpha(0.3).restart();
    }
});
