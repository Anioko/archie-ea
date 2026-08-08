# ADR 0005 — Enterprise network readiness: egress, telemetry and AI data flow

- **Status:** Accepted; egress and CVE items done, remainder tracked below
- **Date:** 2026-07-30
- **Context:** Archie is being prepared for deployment inside a corporate network.
  The DigitalOcean instance is a demonstrator, not production. The gate that
  matters is the receiving organisation's architecture and security review, so
  this ADR records what leaves the network, what does not, and how each is
  enforced rather than merely asserted.

## The question a reviewer actually asks

*"When this runs on our network, what does it talk to?"*

An assurance in a document is worth little; the answer needs to be machine-checked
and re-checked on every change. Each claim below therefore names its gate.

## 1. Browser egress — none

**Was:** 78 external resource loads across 39 distinct assets — jsdelivr, unpkg,
cdnjs, d3js.org, Google Fonts, `cdn.tailwindcss.com`.

**Now:** zero. All 22 libraries are served from `app/static/vendor/`, with
`VENDOR_MANIFEST.txt` recording upstream URL, byte size and SHA-384 for each.

Four were not merely inconvenient:

| Asset | Consequence when blocked |
|---|---|
| `alpinejs` | the entire interactivity layer — every interactive page inert |
| `cdn.tailwindcss.com` | the CSS framework itself; page renders unstyled |
| `dompurify` | an XSS sanitiser. Does not fail loudly — silently stops sanitising |
| `lucide@latest` | unpinned: any upstream compromise executes on next page load |

Vendoring also removed genuine version drift. Chart.js was pinned three ways
(`4.4.1`, `4`, `4.4.0`), d3 loaded from two different origins, Alpine as `@3` and
`@3.14.3`, DOMPurify as `@3` and `@3.0.8`, lucide as `@latest` and `@0.344.0`.
Different pages ran different versions of the same library.

**Gate:** `scripts/check_external_origins.py`, wired as the `air-gap` gate and set
to **zero** — not ratcheted, because there is no remaining debt. Any new external
asset fails the build. A genuinely required external load must be marked
`air-gap-ok` on the line, which makes it a reviewable decision.

## 2. Server-side egress — two cases, both eliminated or gated

**PDF export.** `solutions/export_executive.html` is rendered *server-side* by
WeasyPrint, and carried an `@import` of Google Fonts. That is an outbound request
from the application host, not the browser: on an air-gapped or proxied network it
stalls until timeout, delaying or failing every executive PDF export. Removed; the
font stack now resolves to fonts the host already has.

`app/static/css/vendor/semantic.min.css` carried a Google Fonts `@import` firing on
every page load. Removed.

**Content-Security-Policy** is now `default-src 'self'` with no external origins in
`script-src`. The previous policy still permitted jsdelivr, unpkg and
`cdn.tailwindcss.com` after those assets were vendored — a dead allowance is a
standing invitation, since an injected tag pointing at a permitted host would still
execute.

## 3. Third-party telemetry — present as capability, dormant by default

Four integrations exist. All are **off unless explicitly configured**, verified by
reading the code rather than the documentation:

| Integration | Gate | Default |
|---|---|---|
| Google Analytics | `{% if config.GOOGLE_ANALYTICS_ID %}` | `""` |
| Segment | `{% if config.SEGMENT_API_KEY %}` | `""` |
| PostHog (browser) | `{% if posthog_key %}` | `""` |
| PostHog (server) | `AnalyticsService._enabled = bool(api_key)` | disabled; `_post()` returns before `requests.post` |

The live demonstrator confirms this: `/health` reports zero enabled providers.

Because the CSP no longer permits `cdn.segment.com` or `www.google-analytics.com`,
enabling any of these now *also* requires widening the policy explicitly — turning
third-party telemetry into a visible, reviewable decision instead of a silent
default.

## 4. AI / LLM data flow

Archie's AI features call an LLM provider. What is sent is the architecture context
of the request — which for this deployment means the organisation's own application
portfolio and design artefacts.

Current posture, verified on the demonstrator: **no provider is enabled**
(`/health` reports `enabled_providers: 0`, and no cloud embedding provider is
configured). Providers are configured per-deployment via the `APISettings` table,
not baked in.

For an internal deployment the supported positions are, in order of preference:

1. **AI disabled.** No provider configured; every AI surface degrades to its
   non-AI behaviour. This is the current default and requires no network egress.
2. **Internal model endpoint.** Point the provider base URL at a model hosted
   inside the network. No data crosses the boundary.
3. **Approved external provider**, only under an executed data-processing
   agreement, with the egress explicitly allowed at the proxy.

This must be stated in the deployment record for whichever position is chosen; it
is the first question an architecture review will ask about an "AI-native" tool.

## 5. Dependency vulnerabilities — zero, gated

`pip-audit` reported 62 advisories across four packages, two of which (`pypdf`,
`Pillow`) parse untrusted uploaded files — the first surface a reviewer probes.
All cleared.

Two pins had been blocking their own fixes (`pypdf<6.0.0`, `weasyprint<61.0`). A
third, `pydyf<0.11.0`, was blocking for a *good* reason recorded in its comment;
WeasyPrint 68 requires the newer pydyf, so the two had to move together.

Test tooling (pytest, playwright and friends) moved out of `requirements.txt`: it
was shipping in the production image, enlarging both attack surface and CVE
reporting surface for no runtime benefit.

**Gate:** `dependency-cves` runs `pip-audit` against `requirements.txt` in CI.

## Not yet done

- **SBOM** (CycloneDX) generated in CI and published per release.
- **Air-gap runtime test:** these gates prove no external asset is *referenced*.
  They do not prove the app behaves correctly with egress actually blocked. Run the
  stack with outbound traffic denied and exercise the primary journeys.
- **SSO against the target IdP.** Azure AD wiring already exists
  (`login.microsoftonline.com` is the one allowlisted external origin).
- **Licence position.** AGPL-3.0 with a commercial option. Internal deployment is
  not distribution, so AGPL imposes no obligation here — but enterprise legal teams
  commonly reject AGPL on sight. Decide which licence the deployment receives before
  legal review, not during it.
