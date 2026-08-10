// Reverted to original client implementation (pre-cytoscape replacement)
// This file restores the previous behavior that the user had before recent changes.
// Cytoscape integration was removed because the user requested reverting the JS changes to recover the working UI.
// Minimal implementation enabling node resizing, orthogonal edges, dynamic palette fetch, and relationship creation.
// This file intentionally provides a lightweight UI integration; enhance in future sprints for auto-layout and Visio export.

document.addEventListener('DOMContentLoaded', function() {
  // Fetch palette and relationship types
  async function fetchPalette() {
    try {
      const res = await fetch('/api/solution-composer/palette', { credentials: 'same-origin' });
      // Unchecked, a 500 parsed to `{}` and the composer rendered an empty palette —
      // the user reads that as "this canvas has no element types".
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      return data.data || data;
    } catch (e) {
      console.warn('Failed to fetch palette', e);
      if (window.Platform && window.Platform.toast) {
        window.Platform.toast.error('Could not load the element palette — it is empty because the request failed.');
      }
      return {};
    }
  }

  async function fetchRelationshipTypes() {
    try {
      const res = await fetch('/api/solution-composer/relationship-types', { credentials: 'same-origin' });
      // Unchecked, a 500 left the relationship-type list empty, so drawing a link
      // offered no types to choose from and looked like a broken control.
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      return (data.data && data.data.relationship_types) || data.relationship_types || [];
    } catch (e) {
      console.warn('Failed to fetch relationship types', e);
      if (window.Platform && window.Platform.toast) {
        window.Platform.toast.error('Could not load relationship types — none are available because the request failed.');
      }
      return [];
    }
  }

  // Minimal DOM hooks
  const paletteEl = document.getElementById('element-palette');
  const canvasEl = document.getElementById('solution-canvas');
  if (!canvasEl) {
    console.warn('Solution Composer canvas element not found');
    return;
  }

  // Create simple pan/zoom and node resizing using HTML elements (fallback if Cytoscape not loaded)
  function makeNodeElement(node) {
    const el = document.createElement('div');
    el.className = 'sc-node';
    el.dataset.nodeId = node.id;
    el.style.position = 'absolute';
    el.style.left = (node.position_x || 100) + 'px';
    el.style.top = (node.position_y || 100) + 'px';
    el.style.width = (node.width || 200) + 'px';
    el.style.height = (node.height || 100) + 'px';
    el.style.border = '1px solid #333';
    el.style.background = '#fff';
    el.style.padding = '8px';
    el.style.boxSizing = 'border-box';
    el.style.resize = 'both';
    el.style.overflow = 'auto';
    el.innerText = node.name || node.id;

    // Allow dragging
    let dragging = false;
    let offsetX = 0;
    let offsetY = 0;
    el.addEventListener('mousedown', (ev) => {
      if (ev.target === el) {
        dragging = true;
        offsetX = ev.offsetX;
        offsetY = ev.offsetY;
        el.style.cursor = 'grabbing';
      }
    });
    document.addEventListener('mousemove', (ev) => {
      if (dragging) {
        const rect = canvasEl.getBoundingClientRect();
        const x = ev.clientX - rect.left - offsetX;
        const y = ev.clientY - rect.top - offsetY;
        el.style.left = x + 'px';
        el.style.top = y + 'px';
      }
    });
    document.addEventListener('mouseup', async () => {
      if (dragging) {
        dragging = false;
        el.style.cursor = 'grab';
        // Save position to server
        const nodeId = el.dataset.nodeId;
        const posX = parseFloat(el.style.left);
        const posY = parseFloat(el.style.top);
        try {
          const posResp = await fetch(`/api/solution-composer/nodes/${encodeURIComponent(nodeId)}/position`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position_x: posX, position_y: posY}),
          });
          if (!posResp.ok) throw new Error('HTTP ' + posResp.status);
        } catch (e) {
          // The node visually stays where it was dropped even though the position
          // did not persist — the user must be told, or a reload silently reverts it.
          console.warn('Failed to save position', e);
          Platform.toast.error('Could not save the new node position.');
        }
      }
    });

    // Allow double-click to open properties (placeholder)
    el.addEventListener('dblclick', (ev) => {
      ev.stopPropagation();
      Platform.toast.info('Open properties for ' + (node.name || node.id));
    });

    return el;
  }

  async function init() {
    const palette = await fetchPalette();
    const relTypes = await fetchRelationshipTypes();

    // Populate palette simple list
    if (paletteEl && palette.archimate_elements) {
      palette.archimate_elements.forEach((et) => {
        const item = document.createElement('button');
        item.className = 'palette-item';
        item.innerText = et.label || et.type;
        item.dataset.type = et.type;
        item.addEventListener('click', async () => {
          // Create a node on click
          const nodeId = 'node-' + Date.now();
          const payload = {
            node_id: nodeId,
            element_type: et.type,
            name: et.label || et.type,
            source_type: 'archimate',
            position_x: 100 + Math.random() * 200,
            position_y: 100 + Math.random() * 200,
            properties: {},
          };
          try {
            const res = await fetch('/api/solution-composer/nodes', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
            const rj = await res.json();
            if (rj.success) {
              const el = makeNodeElement(payload);
              canvasEl.appendChild(el);
            } else {
              Platform.toast.error('Failed to add node: ' + (rj.error || 'unknown'));
            }
          } catch (e) {
            console.warn('Failed to add node', e);
            Platform.toast.error('Failed to add node.');
          }
        });
        paletteEl.appendChild(item);
      });
    }

    // Load existing canvas nodes via /api/solution-composer/state
    try {
      const res = await fetch('/api/solution-composer/state');
      const js = await res.json();
      if (js.success && js.data && js.data.nodes) {
        js.data.nodes.forEach((n) => {
          const el = makeNodeElement(n);
          canvasEl.appendChild(el);
        });
      }
    } catch (e) {
      // Distinguish "failed to load" from "nothing saved yet" — otherwise a broken
      // load reads as an empty canvas and the user starts re-adding nodes that already exist.
      console.warn('No canvas state loaded', e);
      Platform.toast.error('Could not load the saved canvas. Existing nodes may not be showing.');
    }

    // Minimal connection creation: shift-click source then click target
    let pendingSource = null;
    canvasEl.addEventListener('click', (ev) => {
      const nodeEl = ev.target.closest('.sc-node');
      if (!nodeEl) return;
      if (ev.shiftKey) {
        // select as source
        pendingSource = nodeEl.dataset.nodeId;
        nodeEl.style.outline = '2px solid blue';
      } else if (pendingSource) {
        const source = pendingSource;
        const target = nodeEl.dataset.nodeId;
        pendingSource = null;
        // create connection with default recommended rel (simple: serving)
        const connId = 'conn-' + Date.now();
        const payload = {
          connection_id: connId,
          source_node_id: source,
          target_node_id: target,
          relationship_type: 'serving',
        };
        fetch('/api/solution-composer/connections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
          .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then((rj) => {
            if (!rj.success) Platform.toast.error('Connection failed: ' + (rj.error || 'unknown'));
          })
          // The connection the user just drew is not saved. Logging that to the
          // console left the canvas looking exactly as if it had been.
          .catch((e) => Platform.toast.error('Connection failed: ' + (e.message || 'request failed')));
      }
    });

  }

  init();
});
