"""Fail release qualification unless every required JUnit report is nonempty and green."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.reports:
        try:
            root = ET.parse(path).getroot()
            if root.tag not in {'testsuite', 'testsuites'}:
                raise ValueError('not a JUnit report')
            cases = list(root.iter('testcase'))
            nonpasses = [node for node in root.iter() if node.tag in {'skipped', 'failure', 'error'}]
            if not cases or nonpasses:
                raise ValueError(f'{len(cases)} testcases; {len(nonpasses)} failure/error/skip entries')
            print(f'PASS {path}: {len(cases)} executed testcases, zero failures/errors/skips')
        except (OSError, ET.ParseError, ValueError) as error:
            print(f'FAIL {path}: {error}')
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
