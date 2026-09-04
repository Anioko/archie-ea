"""Runtime behavior checks for the ArchiMate dashboard Alpine controller."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "app" / "static" / "js" / "archimate_crud" / "dashboard.js"


@pytest.mark.parametrize(
    ("element_types", "expected_type_filters"),
    [
        ([], [None]),
        (["Goal", "Driver"], [None, "Goal,Driver"]),
    ],
)
def test_init_only_refreshes_elements_for_a_viewpoint_with_type_filters(
    element_types: list[str], expected_type_filters: list[str | None]
):
    """An empty default viewpoint must not duplicate the initial element load."""
    node = shutil.which("node")
    if not node:
        pytest.fail("Node.js is required for the dashboard runtime behavior test")

    harness = r"""
const fs = require('fs');
const vm = require('vm');
const elementTypes = JSON.parse(process.argv[1]);
const elementRequests = [];
let factory;

global.window = {
  __APP_CONFIG__: {
    initialLayer: 'motivation',
    layerConfig: { motivation: { name: 'Motivation', elements: ['Goal', 'Driver'] } }
  },
  location: { search: '', pathname: '/architecture/dashboard', hash: '' },
  history: { pushState() {} },
  addEventListener() {},
  removeEventListener() {},
  scrollTo() {}
};
global.localStorage = { getItem() { return null; }, setItem() {} };
global.document = {
  addEventListener(name, callback) {
    if (name === 'alpine:init') callback();
  }
};
global.Alpine = { data(name, callback) { factory = callback; } };
global.Platform = {
  fetch: {
    get(url, params) {
      if (url.endsWith('/elements')) {
        elementRequests.push(params && params.element_type ? params.element_type : null);
        return Promise.resolve({
          elements: [],
          pagination: { page: 1, pages: 0, per_page: 25, total: 0,
                        has_next: false, has_prev: false }
        });
      }
      if (url.endsWith('/count')) return Promise.resolve({ total: 0 });
      if (url === '/api/archimate/viewpoints') {
        return Promise.resolve({ basic: { name: 'All Elements', element_types: elementTypes } });
      }
      throw new Error('Unexpected GET ' + url);
    }
  },
  toast: { error() {} }
};

vm.runInThisContext(fs.readFileSync(process.argv[2], 'utf8'), { filename: process.argv[2] });
const component = factory();
component.$nextTick = callback => callback();
component.init();
setImmediate(() => setImmediate(() => process.stdout.write(JSON.stringify(elementRequests))));
"""
    completed = subprocess.run(
        [node, "-e", harness, json.dumps(element_types), str(SCRIPT_PATH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == expected_type_filters
