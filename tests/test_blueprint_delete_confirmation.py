"""Real rendered delete controls in Chromium; only HTTP responses are doubled.

No application server, database, authentication, or production deletion occurs.
"""
import json

import pytest
from playwright.sync_api import expect

import test_blueprint_composition_editor as composition

browser = composition.browser
page = composition.page
harness = composition.harness
BASE = composition.BASE


def open_page(page, sad_data=None):
    html = harness.page_html(sad_data or {'composition': [composition.EXISTING]})
    env = harness.Environment(loader=harness.FileSystemLoader(harness.ROOT / 'app/templates'), autoescape=True)
    body = env.from_string(
        "{% include 'solutions/partials/_solution_composition.html' %}"
        "{% include 'solutions/partials/_blueprint_composition_editor.html' %}"
        "{% include 'solutions/partials/_blueprint_delete_confirmation.html' ignore missing %}"
    ).render()
    html = html.replace('</div></body>', body + '</div></body>')
    page.route(BASE + '/', lambda route: route.fulfill(body=html, content_type='text/html'))
    page.goto(BASE + '/')
    page.get_by_role('button', name='Delete', exact=True).first.wait_for()
    return page.locator('#bp-delete-confirmation')


def install_api(page, failure=None, refresh_failure=False, pending=None, refresh_status=503):
    writes = []

    def handle(route):
        if route.request.method == 'DELETE':
            writes.append((route.request.method, route.request.url))
            if pending is not None:
                pending.append(route)
                return
            status, body = failure or (200, {'success': True})
        else:
            status, body = (refresh_status, {'error': 'Refresh unavailable'}) if refresh_failure else (200, {'items': []})
        route.fulfill(status=status, content_type='application/json', body=json.dumps(body))

    page.route(BASE + '/solutions/32/**', handle)
    return writes


def test_delete_opens_named_confirmation_cancel_escape_send_nothing(page):
    dialog = open_page(page)
    writes = install_api(page)
    trigger = page.get_by_role('button', name='Delete', exact=True)
    trigger.click()
    expect(dialog).to_be_visible()
    expect(dialog).to_have_attribute('aria-modal', 'true')
    expect(dialog.get_by_role('heading', name='Delete item?', exact=True)).to_be_visible()
    expect(dialog.get_by_text('Payments', exact=True)).to_be_visible()
    expect(dialog.locator(':focus')).to_have_count(1)
    dialog.get_by_role('button', name='Cancel', exact=True).click()
    expect(dialog).to_be_hidden()
    expect(trigger).to_be_focused()
    trigger.click()
    page.keyboard.press('Escape')
    expect(dialog).to_be_hidden()
    assert writes == []


def test_confirm_deletes_exact_composition_and_removes_visible_row(page):
    dialog = open_page(page)
    writes = install_api(page)
    page.get_by_role('button', name='Delete', exact=True).click()
    dialog.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('cell', name='Payments', exact=True)).to_have_count(0)
    assert writes == [('DELETE', BASE + '/solutions/32/composition/7')]


@pytest.mark.parametrize('status', [400, 200])
def test_delete_rejection_keeps_target_and_allows_retry(page, status):
    dialog = open_page(page)
    writes = install_api(page, failure=(status, {'success': False, 'error': 'Deletion blocked'}))
    page.get_by_role('button', name='Delete', exact=True).click()
    dialog.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog.get_by_role('alert')).to_have_text('Deletion blocked')
    expect(dialog.get_by_text('Payments', exact=True)).to_be_visible()
    expect(dialog.get_by_role('button', name='Delete', exact=True)).to_be_enabled()
    expect(page.get_by_role('cell', name='Payments', exact=True)).to_be_visible()
    assert len(writes) == 1


@pytest.mark.parametrize('refresh_status', [503, 200])
def test_successful_delete_with_failed_refresh_cannot_be_repeated(page, refresh_status):
    dialog = open_page(page)
    writes = install_api(page, refresh_failure=True, refresh_status=refresh_status)
    page.get_by_role('button', name='Delete', exact=True).click()
    dialog.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('status').filter(has_text='Deleted, but the list')).to_be_visible()
    expect(page.get_by_role('cell', name='Payments', exact=True)).to_have_count(0)
    assert len(writes) == 1


def test_generic_confirmation_uses_governance_type_and_id(page):
    dialog = open_page(page, {'governance_exceptions': [harness.EXISTING_EXCEPTION]})
    writes = install_api(page)
    page.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog.get_by_text(harness.EXISTING_EXCEPTION['exception_description'], exact=True)).to_be_visible()
    dialog.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog).to_be_hidden()
    assert writes == [('DELETE', BASE + '/solutions/32/governance-exceptions/7')]


@pytest.mark.parametrize('status', [200, 400])
def test_late_delete_does_not_close_or_clear_new_editor(page, status):
    dialog = open_page(page)
    pending = []
    writes = install_api(page, pending=pending)
    page.get_by_role('button', name='Delete', exact=True).click()
    with page.expect_request(lambda request: request.method == 'DELETE'):
        dialog.get_by_role('button', name='Delete', exact=True).click()
    expect(dialog.get_by_role('button', name='Deleting…', exact=True)).to_be_disabled()
    page.keyboard.press('Escape')
    page.get_by_role('button', name='+ Compliance', exact=True).click()
    editor = page.locator('#bp-governance-editor')
    editor.get_by_label('Framework *').fill('Unrelated unsaved work')
    with page.expect_response(lambda response: response.request.method == ('GET' if status == 200 else 'DELETE')):
        pending[0].fulfill(status=status, content_type='application/json', body=json.dumps(
            {'success': True} if status == 200 else {'success': False, 'error': 'Deletion blocked'}))
    expect(editor).to_be_visible()
    expect(editor.get_by_label('Framework *')).to_have_value('Unrelated unsaved work')
    if status == 400:
        expect(page.get_by_role('status')).to_contain_text('Deletion blocked')
    assert len(writes) == 1


def test_reopening_pending_delete_cannot_send_duplicate(page):
    dialog = open_page(page)
    pending = []
    writes = install_api(page, pending=pending)
    page.get_by_role('button', name='Delete', exact=True).click()
    with page.expect_request(lambda request: request.method == 'DELETE'):
        dialog.get_by_role('button', name='Delete', exact=True).click()
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Delete', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('already in progress')
    expect(dialog).to_be_hidden()
    pending[0].fulfill(content_type='application/json', body='{"success":true}')
    expect(page.get_by_role('cell', name='Payments', exact=True)).to_have_count(0)
    expect(page.get_by_role('status').filter(has_text='already in progress')).to_have_count(0)
    assert len(writes) == 1
