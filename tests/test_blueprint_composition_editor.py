"""Rendered Chromium composition editor; only HTTP JSON boundaries are doubled.

Uses real composition/governance partials, Platform modal/core, Alpine and blueprint
script. No Flask login, database, authorization or persistence is exercised here.
"""
import json

import pytest
from playwright.sync_api import expect

import test_blueprint_governance_editor as harness

browser = harness.browser
BASE = harness.BASE
EXISTING = {"id": 7, "solution_id": 32, "component_type": "application",
            "component_id": 41, "component_name": "Payments", "role": "core",
            "criticality": "high", "coupling": "tightly_coupled", "notes": "Keep",
            "failure_impact": "degrades_solution", "replacement_difficulty": "moderate"}


@pytest.fixture
def page(browser):
    p = browser.new_page(viewport={'width': 1280, 'height': 900})
    errors = []
    p.on('pageerror', lambda error: errors.append(str(error)))
    p.route(BASE + '/static/**', lambda route: route.fulfill(path=str(
        harness.ROOT / 'app' / route.request.url[len(BASE) + 1:].split('?')[0])))
    yield p
    p.close()
    assert errors == [], 'Browser runtime errors: ' + '; '.join(errors)


def open_page(page, sad_data=None):
    html = harness.page_html(sad_data or {})
    # Render the real control before the editor exists to reproduce the dead button.
    env = harness.Environment(loader=harness.FileSystemLoader(harness.ROOT / "app/templates"), autoescape=True)
    body = env.from_string("{% include 'solutions/partials/_solution_composition.html' %}"
                           "{% include 'solutions/partials/_blueprint_composition_editor.html' ignore missing %}").render()
    html = html.replace('</div></body>', body + '</div></body>')
    page.route(BASE + '/', lambda route: route.fulfill(body=html, content_type='text/html'))
    page.goto(BASE + '/')
    page.wait_for_function('window.Alpine && window.Platform && window.Platform.modal')
    return page.locator('#bp-composition-editor')


def choose_application(page, dialog):
    page.route(BASE + '/applications/api/list?*', lambda route: route.fulfill(
        content_type='application/json', body=json.dumps({'applications': [
            {'id': 41, 'name': 'Payments', 'component_type': 'Business Application',
             'business_criticality': 'high', 'technology_stack': None, 'vendor_name': None,
             'lifecycle_status': 'operational', 'capability_count': 0, 'created_at': None}],
            'total': 1, 'page': 1, 'pages': 1, 'per_page': 10})))
    dialog.get_by_label('Application *', exact=True).fill('Pay')
    dialog.get_by_role('button', name='Payments', exact=True).click()


def test_component_opens_accessible_editor_cancel_escape_and_reopen(page):
    dialog = open_page(page)
    page.get_by_role('button', name='+ Component', exact=True).click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('heading', name='Add Component', exact=True)).to_be_visible()
    expect(dialog.locator(':focus')).to_have_count(1)
    dialog.get_by_role('button', name='Cancel', exact=True).click()
    expect(dialog).to_be_hidden()
    page.get_by_role('button', name='+ Component', exact=True).click()
    page.keyboard.press('Escape')
    expect(dialog).to_be_hidden()
    page.get_by_role('button', name='+ Component', exact=True).click()
    expect(dialog).to_be_visible()


def test_typed_name_without_selection_cannot_save(page):
    dialog = open_page(page)
    api = harness.Api(page)
    page.get_by_role('button', name='+ Component', exact=True).click()
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('Select')
    assert api.writes == []


def test_application_selection_posts_identity_and_refreshes_visible_row(page):
    dialog = open_page(page)
    api = harness.Api(page)
    page.get_by_role('button', name='+ Component', exact=True).click()
    choose_application(page, dialog)
    dialog.get_by_label('Notes', exact=True).fill('Payment processing')
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(dialog).to_be_hidden()
    assert api.writes == [('POST', BASE + '/solutions/32/composition', {
        'component_type': 'application', 'component_id': 41, 'component_name': 'Payments',
        'role': 'supporting', 'criticality': 'medium', 'coupling': 'loosely_coupled', 'notes': 'Payment processing'})]
    expect(page.get_by_role('cell', name='Payments', exact=True)).to_be_visible()


def test_edit_preserves_identity_and_other_model_fields(page):
    dialog = open_page(page, {'composition': [EXISTING]})
    api = harness.Api(page, lists={'composition': [EXISTING]})
    page.get_by_role('button', name='Edit', exact=True).click()
    expect(dialog.get_by_role('heading', name='Edit Component', exact=True)).to_be_visible()
    expect(dialog.get_by_text('Payments', exact=True)).to_be_visible()
    expect(dialog.get_by_label('Role', exact=True)).to_have_value('core')
    dialog.get_by_label('Notes', exact=True).fill('Updated')
    dialog.get_by_role('button', name='Save changes', exact=True).click()
    expect(dialog).to_be_hidden()
    method, url, payload = api.writes[0]
    assert (method, url) == ('PUT', BASE + '/solutions/32/composition/7')
    assert payload['component_id'] == 41
    assert payload['notes'] == 'Updated'
    assert payload['failure_impact'] == 'degrades_solution'


def test_type_change_clears_selection_and_archimate_picker_saves_identity(page):
    dialog = open_page(page)
    api = harness.Api(page)
    page.get_by_role('button', name='+ Component', exact=True).click()
    choose_application(page, dialog)
    dialog.get_by_label('Component type *').select_option('archimate_element')
    expect(dialog.get_by_text('Payments', exact=True)).to_have_count(0)
    page.route(BASE + '/archimate/api/elements/search?*', lambda route: route.fulfill(
        content_type='application/json', body='{"data":[{"id":56,"name":"Message bus","type":"ApplicationComponent"}]}'))
    dialog.get_by_label('ArchiMate element *').fill('Message')
    dialog.get_by_role('button', name='Message bus', exact=True).click()
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(dialog).to_be_hidden()
    assert api.writes[0][2]['component_type'] == 'archimate_element'
    assert api.writes[0][2]['component_id'] == 56
    assert api.writes[0][2]['component_name'] == 'Message bus'


@pytest.mark.parametrize('status', [400, 200])
def test_save_failure_preserves_input_and_allows_retry(page, status):
    dialog = open_page(page)
    harness.Api(page, fail_with=(status, 'Component already exists'))
    page.get_by_role('button', name='+ Component', exact=True).click()
    choose_application(page, dialog)
    dialog.get_by_label('Notes', exact=True).fill('Keep my work')
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(dialog.get_by_role('alert')).to_have_text('Component already exists')
    expect(dialog.get_by_label('Notes', exact=True)).to_have_value('Keep my work')
    expect(dialog.get_by_role('button', name='Save', exact=True)).to_be_enabled()


@pytest.mark.parametrize('status', [503, 200])
def test_saved_write_failed_refresh_closes_to_prevent_duplicate_save(page, status):
    dialog = open_page(page)
    api = harness.Api(page)
    page.route(BASE + '/solutions/32/composition', lambda route: route.fulfill(
        status=status, content_type='application/json', body='{"error":"Unavailable"}')
        if route.request.method == 'GET' else route.fallback())
    page.get_by_role('button', name='+ Component', exact=True).click()
    choose_application(page, dialog)
    dialog.get_by_role('button', name='Save', exact=True).click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('status').filter(has_text='Saved, but the list')).to_be_visible()
    assert len(api.writes) == 1


@pytest.mark.parametrize('status', [201, 400])
def test_late_save_cannot_close_or_overwrite_next_editor(page, status):
    dialog = open_page(page)
    harness.Api(page)
    pending = []
    page.route(BASE + '/solutions/32/composition', lambda route:
               pending.append(route) if route.request.method == 'POST' else route.fallback())
    page.get_by_role('button', name='+ Component', exact=True).click()
    choose_application(page, dialog)
    with page.expect_request(lambda request: request.method == 'POST'):
        dialog.get_by_role('button', name='Save', exact=True).click()
    page.keyboard.press('Escape')
    page.get_by_role('button', name='+ Compliance', exact=True).click()
    governance = page.locator('#bp-governance-editor')
    governance.get_by_label('Framework *').fill('Next unsaved editor')
    with page.expect_response(lambda response: response.request.method == ('GET' if status == 201 else 'POST')):
        pending[0].fulfill(status=status, content_type='application/json',
                           body='{"success":true,"item":{"id":99}}' if status == 201 else '{"success":false,"error":"Rejected"}')
    if status == 400:
        expect(page.get_by_role('status')).to_contain_text('dismissed editor')
    expect(governance).to_be_visible()
    expect(governance.get_by_label('Framework *')).to_have_value('Next unsaved editor')


def test_malformed_search_is_an_error_not_no_results(page):
    dialog = open_page(page)
    page.route(BASE + '/applications/api/list?*', lambda route: route.fulfill(
        content_type='application/json', body='{"success":true}'))
    page.get_by_role('button', name='+ Component', exact=True).click()
    dialog.get_by_label('Application *').fill('Pay')
    expect(dialog.get_by_role('status')).to_contain_text('invalid response')


def test_unknown_existing_classifications_survive_edit(page):
    existing = dict(EXISTING, component_type='service', role='gateway', criticality='urgent', coupling='event_driven')
    dialog = open_page(page, {'composition': [existing]})
    api = harness.Api(page)
    page.get_by_role('button', name='Edit', exact=True).click()
    expect(dialog.get_by_label('Component type *')).to_have_value('service')
    expect(dialog.get_by_label('Role', exact=True)).to_have_value('gateway')
    dialog.get_by_label('Notes', exact=True).fill('Preserve classifications')
    dialog.get_by_role('button', name='Save changes', exact=True).click()
    expect(dialog).to_be_hidden()
    assert api.writes[0][2]['role'] == 'gateway'
    assert api.writes[0][2]['coupling'] == 'event_driven'


def test_old_search_response_cannot_replace_new_search_results(page):
    dialog = open_page(page)
    pending = []
    page.route(BASE + '/applications/api/list?*', lambda route: pending.append(route)
               if 'search=Old' in route.request.url else route.fulfill(
                   content_type='application/json', body='{"applications":[{"id":42,"name":"New application"}]}'))
    page.get_by_role('button', name='+ Component', exact=True).click()
    with page.expect_request(lambda request: '/applications/api/list?' in request.url):
        dialog.get_by_label('Application *').fill('Old')
    with page.expect_request(lambda request: 'search=New' in request.url):
        dialog.get_by_label('Application *').fill('New')
    expect(dialog.get_by_role('button', name='New application', exact=True)).to_be_visible()
    with page.expect_response(lambda response: 'search=Old' in response.url):
        pending[0].fulfill(content_type='application/json', body='{"applications":[{"id":41,"name":"Old application"}]}')
    expect(dialog.get_by_role('button', name='New application', exact=True)).to_be_visible()
    expect(dialog.get_by_role('button', name='Old application', exact=True)).to_have_count(0)
    # Native keyboard activation selects the result and then shows its identity.
    dialog.get_by_label('Application *').press('Tab')
    page.keyboard.press('Enter')
    expect(dialog.get_by_role('button', name='Clear', exact=True)).to_be_visible()
