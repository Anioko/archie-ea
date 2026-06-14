/**
 * ArchiMate Traceability Sankey Diagram
 * Uses D3.js v7 + d3-sankey for cross-layer element flow visualization.
 */
(function() {
    'use strict';

    const LAYER_COLORS = {
        motivation: '#9575CD', strategy: '#F06292', business: '#FFB74D',
        application: '#4FC3F7', technology: '#81C784', implementation: '#64B5F6'
    };
    const LAYER_LABELS = {
        motivation: 'Motivation', strategy: 'Strategy', business: 'Business',
        application: 'Application', technology: 'Technology', implementation: 'Implementation'
    };

    function createSankey(containerId, apiUrl) {
        const container = d3.select(containerId);
        if (container.empty()) return;

        const margin = {top: 40, right: 20, bottom: 20, left: 20};
        const width = container.node().getBoundingClientRect().width - margin.left - margin.right;
        const height = Math.max(500, window.innerHeight * 0.6);

        container.selectAll('*').remove();

        const svg = container.append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom);

        const g = svg.append('g')
            .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

        // Loading
        g.append('text').attr('x', width / 2).attr('y', height / 2)
            .attr('text-anchor', 'middle').style('font-size', '14px').style('fill', '#94a3b8')
            .text('Loading traceability data...');

        // Zoom
        const zoom = d3.zoom().scaleExtent([0.3, 3])
            .on('zoom', function(event) { g.attr('transform', event.transform); });
        svg.call(zoom);

        // Fetch and render
        fetch(apiUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                g.selectAll('*').remove();
                if (data.error) {
                    g.append('text').attr('x', width / 2).attr('y', height / 2)
                        .attr('text-anchor', 'middle').style('font-size', '14px').style('fill', '#94a3b8')
                        .text('No cross-layer relationships to display.');
                    console.warn('Traceability API returned error:', data.error);
                    return;
                }
                if (!data.nodes || data.nodes.length === 0) {
                    g.append('text').attr('x', width / 2).attr('y', height / 2)
                        .attr('text-anchor', 'middle').style('font-size', '14px').style('fill', '#94a3b8')
                        .text('No cross-layer relationships to display.');
                    return;
                }
                renderSankey(g, data, width, height);
            })
            .catch(function(err) {
                g.selectAll('*').remove();
                g.append('text').attr('x', width / 2).attr('y', height / 2)
                    .attr('text-anchor', 'middle').style('fill', '#ef4444').style('font-size', '14px')
                    .text('Failed to load traceability data.');
                console.error('Sankey load error:', err);
            });
    }

    function renderSankey(g, data, width, height) {
        // Build node index mapping node.id to sequential index
        const nodeIndex = {};
        data.nodes.forEach(function(n, i) { nodeIndex[n.id] = i; });

        // Filter links to valid source/target, map to indices
        let validLinks = data.links.filter(function(l) {
            return nodeIndex[l.source] !== undefined && nodeIndex[l.target] !== undefined;
        }).map(function(l) {
            return {source: nodeIndex[l.source], target: nodeIndex[l.target], value: l.value || 1};
        });

        // Deduplicate (sum values for same source to target)
        const linkMap = {};
        validLinks.forEach(function(l) {
            const key = l.source + '->' + l.target;
            if (!linkMap[key]) linkMap[key] = {source: l.source, target: l.target, value: 0};
            linkMap[key].value += l.value;
        });
        validLinks = Object.values(linkMap);

        // Enforce layer ordering to prevent circular links — d3-sankey throws RangeError on cycles.
        // ArchiMate allows bidirectional relationships across layers; swap backward-flowing links
        // so all links flow motivation→strategy→business→application→technology→implementation.
        const LAYER_ORDER = {motivation: 0, strategy: 1, business: 2, application: 3, technology: 4, implementation: 5};
        const nodesArr = data.nodes.map(function(n, i) { return Object.assign({}, n, {index: i}); });
        validLinks = validLinks.map(function(l) {
            const srcNode = nodesArr[l.source];
            const tgtNode = nodesArr[l.target];
            const srcOrd = srcNode ? (LAYER_ORDER[srcNode.layer] !== undefined ? LAYER_ORDER[srcNode.layer] : 3) : 3;
            const tgtOrd = tgtNode ? (LAYER_ORDER[tgtNode.layer] !== undefined ? LAYER_ORDER[tgtNode.layer] : 3) : 3;
            if (srcOrd > tgtOrd) { return {source: l.target, target: l.source, value: l.value}; }
            return l;
        }).filter(function(l) { return l.source !== l.target; });
        // Re-deduplicate after direction enforcement
        const linkMap2 = {};
        validLinks.forEach(function(l) {
            const key = l.source + '->' + l.target;
            if (!linkMap2[key]) linkMap2[key] = {source: l.source, target: l.target, value: 0};
            linkMap2[key].value += l.value;
        });
        validLinks = Object.values(linkMap2);

        if (validLinks.length === 0) {
            g.append('text').attr('x', width / 2).attr('y', height / 2)
                .attr('text-anchor', 'middle').style('font-size', '14px').style('fill', '#94a3b8')
                .text('Elements found but no cross-layer relationships.');
            return;
        }

        // Sankey layout
        const sankeyLayout = d3.sankey()
            .nodeId(function(d) { return d.index; })
            .nodeWidth(20)
            .nodePadding(8)
            .nodeSort(null)
            .extent([[0, 0], [width, height]]);

        let sankeyData;
        try {
            sankeyData = sankeyLayout({nodes: nodesArr, links: validLinks});
        } catch (e) {
            g.append('text').attr('x', width / 2).attr('y', height / 2)
                .attr('text-anchor', 'middle').style('font-size', '14px').style('fill', '#94a3b8')
                .text('Diagram layout failed — too many cyclic relationships.');
            console.error('Sankey layout error:', e);
            return;
        }

        // Layer headers
        const layerPositions = {};
        sankeyData.nodes.forEach(function(n) {
            const l = n.layer || 'application';
            if (!layerPositions[l] || n.x0 < layerPositions[l]) layerPositions[l] = n.x0;
        });
        Object.entries(layerPositions).forEach(function(entry) {
            const layer = entry[0], x = entry[1];
            g.append('text').attr('x', x + 10).attr('y', -12)
                .style('font-size', '11px').style('font-weight', '600')
                .style('fill', LAYER_COLORS[layer] || '#94a3b8')
                .text(LAYER_LABELS[layer] || layer);
            g.append('text').attr('x', x + 10).attr('y', -1)
                .style('font-size', '10px').style('fill', '#94a3b8')
                .text((data.layer_counts[layer] || 0) + ' elements');
        });

        // Links
        const linkG = g.append('g').attr('fill', 'none').attr('stroke-opacity', 0.3);
        const linkPaths = linkG.selectAll('path')
            .data(sankeyData.links).enter().append('path')
            .attr('d', d3.sankeyLinkHorizontal())
            .attr('stroke-width', function(d) { return Math.max(1, d.width); })
            .attr('stroke', function(d) { return LAYER_COLORS[d.source.layer] || '#94a3b8'; })
            .style('cursor', 'pointer');
        linkPaths.append('title').text(function(d) {
            return d.source.name + ' \u2192 ' + d.target.name;
        });

        // Nodes
        const nodeG = g.append('g');
        const nodeRects = nodeG.selectAll('g')
            .data(sankeyData.nodes).enter().append('g')
            .style('cursor', 'pointer');
        nodeRects.append('rect')
            .attr('x', function(d) { return d.x0; })
            .attr('y', function(d) { return d.y0; })
            .attr('width', function(d) { return d.x1 - d.x0; })
            .attr('height', function(d) { return Math.max(1, d.y1 - d.y0); })
            .attr('fill', function(d) { return LAYER_COLORS[d.layer] || '#94a3b8'; })
            .attr('rx', 3);
        nodeRects.append('text')
            .attr('x', function(d) { return d.x1 + 6; })
            .attr('y', function(d) { return (d.y0 + d.y1) / 2; })
            .attr('dy', '0.35em')
            .style('font-size', '10px').style('fill', 'currentColor')
            .text(function(d) { return d.name.length > 30 ? d.name.substring(0, 30) + '...' : d.name; });

        // Hover interactions
        nodeRects.on('mouseover', function(event, d) {
            const connected = {};
            sankeyData.links.forEach(function(l) {
                if (l.source.index === d.index || l.target.index === d.index) {
                    connected[l.source.index] = true;
                    connected[l.target.index] = true;
                }
            });
            nodeRects.attr('opacity', function(n) { return connected[n.index] ? 1 : 0.15; });
            linkPaths.attr('stroke-opacity', function(l) {
                return (l.source.index === d.index || l.target.index === d.index) ? 0.6 : 0.05;
            });
        }).on('mouseout', function() {
            nodeRects.attr('opacity', 1);
            linkPaths.attr('stroke-opacity', 0.3);
        }).on('click', function(event, d) {
            if (typeof d.id === 'number') {
                window.location.href = '/architecture/traceability/' + d.id;
            }
        });
    }

    window.createTraceabilitySankey = createSankey;
})();
