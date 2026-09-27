"""Code Workbench: a real deterministic codegen run, not just a dialog open/close.

test_solution_blueprint_controls.py already covers opening/closing the
"Code Generation" modal from the solution blueprint page, and the Code
Workbench page itself is reachable, but nothing previously clicked the real
"Quick Generate" control and checked an artifact came out and persisted.

This exercises the one-click deterministic path (codegen/workbench.js
quickGenerate() -> generate(), generation_mode='deterministic', no LLM
enrichment needed) against the `codegen_solution` fixture, which has one
ArchiMate element linked via SolutionArchiMateElement -- the precondition
codegen_routes.workbench_page checks (linked_elements_count > 0) before it
will even render the Quick Generate button. Confirms the generated file
list survives a hard reload, which is only possible if the file bundle
was written to app.modules.codegen.models.CodegenGeneration.generated_files
rather than held only in Alpine state.
"""
import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

# Deterministic generation still does real file-template rendering server-side
# and can legitimately take tens of seconds for a multi-file FastAPI bundle.
GENERATE_TIMEOUT = 180_000


def test_quick_generate_produces_and_persists_a_code_bundle(browser, live_server, seeded):
    page = browser.new_page()
    solution_id = seeded['ids']['codegen_solution']
    try:
        _login(page, live_server, seeded['emails']['solution_architect'])
        response = page.goto(
            live_server + '/solutions/%s/codegen' % solution_id,
            timeout=PAGE_TIMEOUT,
        )
        assert response.status == 200
        expect(page.get_by_role('heading', name='Code Workbench')).to_be_visible(timeout=PAGE_TIMEOUT)

        quick_generate = page.get_by_role('button', name='Quick Generate', exact=True)
        expect(quick_generate).to_be_visible(timeout=PAGE_TIMEOUT)
        quick_generate.click()

        # workbench.js's own success banner ("Generated <N> files (...)") auto-
        # dismisses after 5s, which is too narrow a window to assert on
        # reliably against a real (tens-of-seconds) generation run. The file
        # count badge (`fileList.length + ' files'`) is not transient -- it
        # stays rendered once generation populates fileList, so wait on that
        # instead as the completion signal.
        files_label = page.locator('text=/\\d+ files$/').first
        expect(files_label).to_be_visible(timeout=GENERATE_TIMEOUT)
        file_count_text = files_label.inner_text()
        file_count = int(file_count_text.split()[0])
        assert file_count > 0, 'Quick Generate reported success but produced no files'

        # ---- Persistence: reload and confirm the bundle survived server-side ----
        # A completed generation switches the page from the setup wizard (which
        # has the "Code Workbench" <h1>) to the file-tree IDE view, so re-assert
        # on the file-count badge -- present in both views -- not the wizard's
        # heading, which is gone once files exist.
        page.reload(timeout=PAGE_TIMEOUT)
        reloaded_files_label = page.locator('text=/\\d+ files$/').first
        expect(reloaded_files_label).to_be_visible(timeout=PAGE_TIMEOUT)
        reloaded_count = int(reloaded_files_label.inner_text().split()[0])
        assert reloaded_count == file_count, (
            'Generated file count did not survive a reload: %s before, %s after -- '
            'the bundle was held only in client state, not persisted server-side.'
            % (file_count, reloaded_count)
        )
    finally:
        page.close()
