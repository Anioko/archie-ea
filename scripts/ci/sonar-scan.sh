#!/usr/bin/env bash
# Run a SonarQube analysis against a self-hosted server.
#
# SonarQube Community Build is free (LGPLv3) and analyses private code without a
# licence. Only SonarQube CLOUD charges for private repositories - the two were
# conflated when this was first set up, and a SonarCloud job was added that could
# never run.
#
# This script is deliberately usable both locally and from CI. It is NOT wired
# into .github/workflows/ci.yml, because a GitHub-hosted runner cannot reach a
# SonarQube instance running on someone's laptop, and a workflow job that
# permanently skips still reports a green tick - which is worse than no job at
# all. Add a CI job only once SONAR_HOST_URL points at something the runner can
# actually reach.
#
# Usage:
#   SONAR_HOST_URL=http://127.0.0.1:9010 SONAR_TOKEN=xxx scripts/ci/sonar-scan.sh
#
# Optional:
#   COVERAGE_XML=path/to/coverage.xml   include coverage in the analysis
set -euo pipefail

: "${SONAR_HOST_URL:?set SONAR_HOST_URL, e.g. http://127.0.0.1:9010}"
: "${SONAR_TOKEN:?set SONAR_TOKEN (SonarQube > My Account > Security > Generate)}"

PROJECT_KEY="${SONAR_PROJECT_KEY:-archie-oss}"
COVERAGE_XML="${COVERAGE_XML:-coverage.xml}"

if ! command -v sonar-scanner >/dev/null 2>&1; then
    cat >&2 <<'EOF'
sonar-scanner not found on PATH.

Download the CLI from:
  https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/

Note: do NOT use the `pysonar-scanner` pip package on Windows - it fails to
spawn its own subprocess (FileNotFoundError [WinError 2]).

The scanner needs a full JDK 17+. SonarQube's own bundled JRE is not enough for
the server either: it lacks jdk.jlink, which Elasticsearch 8 requires, so the
server dies on startup with
  java.lang.module.FindException: Module jdk.jlink not found
EOF
    exit 1
fi

ARGS=(
  "-Dsonar.host.url=${SONAR_HOST_URL}"
  "-Dsonar.token=${SONAR_TOKEN}"
  "-Dsonar.projectKey=${PROJECT_KEY}"
  "-Dsonar.scm.disabled=true"
)

if [ -f "$COVERAGE_XML" ]; then
    ARGS+=("-Dsonar.python.coverage.reportPaths=${COVERAGE_XML}")
    echo "including coverage from ${COVERAGE_XML}"
else
    # Without this the dashboard reports 0.0% coverage, which reads as "no tests"
    # when it actually means "no report was supplied". Say so explicitly.
    echo "WARNING: ${COVERAGE_XML} not found - coverage will show as 0%, meaning NO DATA, not zero tests."
    echo "         Produce it with: pytest --cov=app --cov-report=xml:coverage.xml"
    echo "         Or download it from a CI run: gh run download <id> --name test-reports"
fi

echo "analysing ${PROJECT_KEY} against ${SONAR_HOST_URL}"
sonar-scanner "${ARGS[@]}"

cat <<EOF

Analysis submitted. The scanner only UPLOADS a report; the server processes it
asynchronously afterwards, so the dashboard shows 0 issues until the Compute
Engine finishes. Poll it:

  curl -s -H "Authorization: Bearer \$SONAR_TOKEN" \n       "${SONAR_HOST_URL}/api/ce/component?component=${PROJECT_KEY}"

Results: ${SONAR_HOST_URL}/dashboard?id=${PROJECT_KEY}
EOF
