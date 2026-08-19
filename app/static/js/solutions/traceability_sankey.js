/* Extracted from _traceability_sankey.html (ARCH-064: keep large JS out of the
   server-rendered payload; cacheable across the 4 pages that embed the sankey).
   Pure JS, zero Jinja — defines the global traceabilitySankey() Alpine factory. */
function traceabilitySankey(solutionId, apiUrl) {
  return {
    solutionId,
    apiUrl: apiUrl || '',
    loading: false,
    loaded: false,
    error: null,
    nodes: [],
    links: [],
    hasCode: false,
    synthesized: false,
    selectedNode: null,
    colorMode: 'layer',
    columnLabels: [
      {name:'Motivation'},{name:'Strategy'},{name:'Business'},
      {name:'Application'},{name:'Technology'},{name:'Implementation'}
    ],

    colorModes: [
      {id:'layer',  label:'Layer',  icon:'<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 7h18M3 12h18M3 17h18"/></svg>'},
      {id:'health', label:'Health', icon:'<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 016.364 0L12 7.636l1.318-1.318a4.5 4.5 0 116.364 6.364L12 20.364l-7.682-7.682a4.5 4.5 0 010-6.364z"/></svg>'},
      {id:'status', label:'Status', icon:'<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'},
      {id:'origin', label:'Origin', icon:'<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>'},
      {id:'risk',   label:'Risk',   icon:'<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>'},
    ],

    legends: {
      layer:  [{label:'Motivation',color:'#8b5cf6'},{label:'Strategy',color:'#0ea5e9'},{label:'Business',color:'#f59e0b'},{label:'Application',color:'#10b981'},{label:'Technology',color:'#6b7280'},{label:'Implementation',color:'#f97316'},{label:'Code',color:'#ec4899'}],
      health: [{label:'Complete (4/4)',color:'#10b981'},{label:'Partial (2-3/4)',color:'#f59e0b'},{label:'Minimal (1/4)',color:'#f97316'},{label:'Empty (0/4)',color:'#ef4444'}],
      status: [{label:'Implemented',color:'#10b981'},{label:'Approved',color:'#0ea5e9'},{label:'Proposed',color:'#8b5cf6'},{label:'Deprecated',color:'#ef4444'},{label:'Unknown',color:'#94a3b8'}],
      origin: [{label:'Human (primary)',color:'#0ea5e9'},{label:'Human (supporting)',color:'#38bdf8'},{label:'AI derived',color:'#a855f7'},{label:'Impacted',color:'#f59e0b'}],
      risk:   [{label:'Critical path',color:'#ef4444'},{label:'Critical dep.',color:'#f97316'},{label:'High dep.',color:'#f59e0b'},{label:'Medium dep.',color:'#84cc16'},{label:'Low / none',color:'#94a3b8'}],
    },

    get activeLegend() { return this.legends[this.colorMode] || []; },

    setColorMode(mode) { this.colorMode = mode; this.render(); },

    nodeColor(node) {
      switch (this.colorMode) {
        case 'health': return this.healthColor(node);
        case 'status': return this.statusColor(node);
        case 'origin': return this.originColor(node);
        case 'risk':   return this.riskColor(node);
        default:       return this.layerColor(node.layer);
      }
    },

    layerColor(layer) {
      const map = {motivation:'#8b5cf6',strategy:'#0ea5e9',business:'#f59e0b',application:'#10b981',technology:'#6b7280',implementation:'#f97316',code:'#ec4899'};
      return map[layer] || '#94a3b8';
    },

    healthColor(node) {
      const h = node.health ?? 0;
      if (h >= 4) return '#10b981';
      if (h >= 2) return '#f59e0b';
      if (h >= 1) return '#f97316';
      return '#ef4444';
    },

    statusColor(node) {
      const map = {implemented:'#10b981',approved:'#0ea5e9',proposed:'#8b5cf6',deprecated:'#ef4444'};
      return map[(node.status||'').toLowerCase()] || '#94a3b8';
    },

    originColor(node) {
      const map = {primary:'#0ea5e9',supporting:'#38bdf8',ai_derived:'#a855f7',impacted:'#f59e0b'};
      return map[node.origin||'primary'] || '#0ea5e9';
    },

    riskColor(node) {
      if (node.critical_path) return '#ef4444';
      const map = {critical:'#f97316',high:'#f59e0b',medium:'#84cc16',low:'#94a3b8'};
      return map[(node.dependency_level||'').toLowerCase()] || '#94a3b8';
    },

    get linkedNodes() {
      if (!this.selectedNode) return [];
      const idx = this.nodes.indexOf(this.selectedNode);
      const linked = new Set();
      this.links.forEach(l => {
        if (l.source===idx||l.source?.index===idx) linked.add(l.target?.index??l.target);
        if (l.target===idx||l.target?.index===idx) linked.add(l.source?.index??l.source);
      });
      return [...linked].map(i => this.nodes[i]).filter(Boolean);
    },

    init() {
      this.load();
      window.addEventListener(`load-sankey-${this.solutionId}`, () => this.load());
    },

    async load() {
      if (this.loaded || this.loading) return;
      this.loading = true;
      this.error = null;
      try {
        const endpoint = this.apiUrl || `/architecture-journey/${this.solutionId}/traceability-flow`;
        const r = await fetch(endpoint);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        this.nodes = data.nodes || [];
        this.links = data.links || [];
        this.hasCode = data.has_code || false;
        this.synthesized = data.synthesized || false;
        if (data.column_labels && data.column_labels.length) {
          this.columnLabels = data.column_labels;
        } else if (this.hasCode && !this.columnLabels.find(c => c.name==='Code')) {
          this.columnLabels.push({name:'Code'});
        }
        this.loaded = true;
        await this.$nextTick();
        this.render();
      } catch(e) {
        this.error = `Failed to load traceability data: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    render() {
      const container = this.$refs.sankey;
      if (!container || !this.nodes.length || typeof d3==='undefined' || typeof d3.sankey==='undefined') {
        if (typeof d3!=='undefined' && typeof d3.sankey==='undefined') setTimeout(()=>this.render(), 300);
        return;
      }

      const linkedNodeIdxs = new Set();
      this.links.forEach(l => { linkedNodeIdxs.add(l.source); linkedNodeIdxs.add(l.target); });
      const connectedNodes = this.nodes.filter((_,i) => linkedNodeIdxs.has(i));

      if (connectedNodes.length === 0) {
        d3.select(container).selectAll('*').remove();
        d3.select(container).append('p')
          .attr('class','text-xs text-muted-foreground p-4')
          .text(`${this.nodes.length} elements found across layers, but no cross-layer relationships exist yet.`);
        return;
      }

      const oldToNew = new Map();
      connectedNodes.forEach((n,i) => oldToNew.set(this.nodes.indexOf(n), i));
      const connectedLinks = this.links
        .filter(l => oldToNew.has(l.source) && oldToNew.has(l.target))
        .map(l => ({...l, source: oldToNew.get(l.source), target: oldToNew.get(l.target)}));

      const W = container.clientWidth || 800;
      const H = Math.max(300, connectedNodes.length * 22);
      const margin = {top:10, right:10, bottom:10, left:10};

      d3.select(container).selectAll('*').remove();
      const svg = d3.select(container).append('svg')
        .attr('width',W).attr('height',H).attr('viewBox',`0 0 ${W} ${H}`);

      const sankey = d3.sankey()
        .nodeId(d => d.index)
        .nodeAlign(d3.sankeyLeft)
        .nodeWidth(14).nodePadding(8)
        .extent([[margin.left,margin.top],[W-margin.right,H-margin.bottom]]);

      const graph = sankey({
        nodes: connectedNodes.map((n,i) => ({...n, index:i})),
        links: connectedLinks.map(l => ({...l, value:l.value||1})),
      });

      const self = this;

      // Links — always source-layer colour
      svg.append('g').attr('fill','none')
        .selectAll('path').data(graph.links).join('path')
        .attr('d', d3.sankeyLinkHorizontal())
        .attr('stroke', d => self.layerColor(graph.nodes[d.source.index]?.layer||''))
        .attr('stroke-width', d => Math.max(1,d.width))
        .attr('stroke-opacity', 0.22)
        .on('mouseover', function() { d3.select(this).attr('stroke-opacity',0.5); })
        .on('mouseout',  function() { d3.select(this).attr('stroke-opacity',0.22); });

      const node = svg.append('g').selectAll('g').data(graph.nodes).join('g')
        .style('cursor','pointer')
        .on('click', (event,d) => { self.selectedNode = self.selectedNode===d ? null : d; });

      node.append('rect')
        .attr('x', d=>d.x0).attr('y', d=>d.y0)
        .attr('height', d=>Math.max(2,d.y1-d.y0))
        .attr('width',  d=>d.x1-d.x0)
        .attr('fill',   d=>self.nodeColor(d))
        .attr('rx',2).attr('opacity',0.88);

      // Spec / code dot
      node.filter(d => d.has_spec||d.has_code)
        .append('circle')
        .attr('cx', d=>d.x1+4).attr('cy', d=>(d.y0+d.y1)/2)
        .attr('r',3).attr('fill', d=>d.has_code?'#8b5cf6':'#10b981');

      // AI-origin marker
      node.filter(d => d.origin==='ai_derived')
        .append('circle')
        .attr('cx', d=>d.x0+2).attr('cy', d=>d.y0+2)
        .attr('r',2).attr('fill','#a855f7').attr('opacity',0.9);

      // Critical-path ring
      node.filter(d => d.critical_path)
        .append('rect')
        .attr('x', d=>d.x0-2).attr('y', d=>d.y0-2)
        .attr('height', d=>Math.max(2,d.y1-d.y0)+4)
        .attr('width',  d=>(d.x1-d.x0)+4)
        .attr('fill','none').attr('stroke','#ef4444')
        .attr('stroke-width',1.5).attr('rx',3).attr('opacity',0.6);

      node.filter(d => (d.y1-d.y0)>=14)
        .append('text')
        .attr('x', d=>d.x0<W/2 ? d.x1+8 : d.x0-8)
        .attr('y', d=>(d.y0+d.y1)/2)
        .attr('dy','0.35em')
        .attr('text-anchor', d=>d.x0<W/2?'start':'end')
        .attr('font-size','10px')
        .attr('class','fill-foreground')
        .text(d=>d.name.length>28 ? d.name.slice(0,25)+'\u2026' : d.name);
    },
  };
}
