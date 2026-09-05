"""Qualification must reject skipped or absent execution, not just exit zero."""
from pathlib import Path
import os
import subprocess
import sys

import pytest

GATE = Path(__file__).resolve().parents[1] / 'scripts/ci/check_junit_qualification.py'


@pytest.mark.parametrize('xml,ok', [
    ('<testsuites><testsuite tests="1"><testcase name="real"/></testsuite></testsuites>', True),
    ('<testsuite><testcase name="xfail"><skipped type="pytest.xfail"/></testcase></testsuite>', False),
    ('<testsuite><testcase name="skip"><skipped/></testcase></testsuite>', False),
    ('<testsuite><testcase name="bad"><failure/></testcase></testsuite>', False),
    ('<testsuite><testcase name="error"><error/></testcase></testsuite>', False),
    ('<testsuite tests="99"/>', False),
    ('broken xml', False),
])
def test_actual_testcases_required_without_nonpasses(tmp_path, xml, ok):
    assert GATE.is_file()
    report = tmp_path / 'report.xml'
    report.write_text(xml, encoding='utf-8')
    result = subprocess.run([sys.executable, str(GATE), str(report)], capture_output=True, text=True)
    assert (result.returncode == 0) is ok, result.stdout + result.stderr


def test_missing_report_fails_even_when_another_passes(tmp_path):
    assert GATE.is_file()
    report = tmp_path / 'good.xml'
    report.write_text('<testsuite><testcase name="ok"/></testsuite>', encoding='utf-8')
    result = subprocess.run([sys.executable, str(GATE), str(report), str(tmp_path / 'absent.xml')],
                            capture_output=True, text=True)
    assert result.returncode != 0


@pytest.mark.parametrize('case', ['skip', 'xfail', 'xpass'])
def test_real_pytest_nonpass_report_is_rejected(tmp_path, case):
    test = tmp_path / 'test_example.py'
    body = {
        'skip': 'import pytest\ndef test_case(): pytest.skip("not exercised")\n',
        'xfail': 'import pytest\n@pytest.mark.xfail(reason="known issue")\ndef test_case(): assert False\n',
        'xpass': 'import pytest\n@pytest.mark.xfail(reason="stale expectation")\ndef test_case(): assert True\n',
    }[case]
    test.write_text(body, encoding='utf-8')
    report = tmp_path / 'actual.xml'
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='')
    run = subprocess.run([sys.executable, '-m', 'pytest', str(test), '-q',
                          '-o', 'xfail_strict=true', '--junitxml=' + str(report)],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == (1 if case == 'xpass' else 0), run.stdout + run.stderr
    result = subprocess.run([sys.executable, str(GATE), str(report)], capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
