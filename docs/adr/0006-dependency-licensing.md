# ADR 0006 — GPL in the dependency tree vs. the commercial licence

- **Status:** Accepted; direct GPL dependency removed, transitive ones assessed
- **Date:** 2026-07-30
- **Found by:** CycloneDX SBOM generation while preparing for enterprise review

## Context

Archie is dual-licensed: AGPL-3.0, with a commercial licence offered for
closed-source/SaaS use (`COMMERCIAL-LICENSE.md`). Dual-licensing only works if the
copyright holder can grant *both* sets of terms over the whole work. A GPL-2.0
dependency breaks that: GPL-2.0 cannot be sublicensed under proprietary terms, so a
commercial licensee cannot receive what they are being sold.

Generating the first SBOM surfaced **7 GPL-family licences** in the tree, two of
them direct dependencies:

| Package | Licence | How it entered |
|---|---|---|
| `fuzzywuzzy` 0.18.0 | **GPL-2.0-only** | direct — `requirements.txt` |
| `python-Levenshtein` 0.27.3 | GPL-2.0-or-later | direct — "optional speedup for fuzzywuzzy" |
| `Levenshtein` 0.27.3 | GPL-2.0-or-later | transitive of the above |
| `pyphen` 0.17.2 | GPL-2.0-or-later | transitive of `weasyprint` |
| `text-unidecode` 1.3 | GPL-2.0-or-later / Artistic | transitive of `python-slugify` |
| `dulwich` 1.1.0 | Apache-2.0 **OR** GPL-2.0-or-later | dual — Apache-2.0 may be elected |

Note this is orthogonal to the AGPL question for internal deployment. Deploying
inside an organisation is not distribution, so AGPL imposes no source-provision
obligation there. The problem is specifically the **commercial** licence.

## Decision

**Remove the direct GPL dependency.** `fuzzywuzzy` and `python-Levenshtein` are
replaced by `rapidfuzz` (MIT), which also removes the transitive `Levenshtein`.
Three GPL packages eliminated by one substitution.

The swap is small and was verified rather than assumed:

* Usage is two files and two functions — `fuzz.ratio` (4 sites) and
  `fuzz.token_sort_ratio` (1 site).
* `rapidfuzz` exposes both with the same semantics. Compared on sample inputs:
  identical results except that rapidfuzz returns a float where fuzzywuzzy returned
  `int(round(...))` — e.g. 63.6 vs 64.
* Call sites now `round(...)` so scores stay bit-identical to the previous
  behaviour. This matters because the values feed threshold comparisons
  (`name_similarity >= similarity_threshold`) in duplicate detection, where a
  sub-point shift could change which records are proposed as duplicates.
* `rapidfuzz` is also the maintained successor; `fuzzywuzzy` is archived.

## The three remaining, and why they are acceptable

* **`dulwich`** — dual-licensed `Apache-2.0 OR GPL-2.0-or-later`. Elect Apache-2.0.
  Record the election in the licence documentation; no code change needed.
* **`pyphen`** — pulled in by `weasyprint` for hyphenation during PDF rendering.
  GPL-2.0-or-later, and it is a separate process-level library invoked at runtime
  rather than linked into Archie's own code. If the commercial licensee's counsel
  objects, the options are to drop the WeasyPrint path (the PDF exporter already
  falls back to wkhtmltopdf) or to ship without hyphenation.
* **`text-unidecode`** — via `python-slugify`, dual GPL-2.0/Artistic. `python-slugify`
  can be configured to use the MIT-licensed `Unidecode` alternative, or replaced.

None of these is a direct dependency, and none is load-bearing in the way
`fuzzywuzzy` was. They are recorded here so the answer exists before the question
is asked in legal review, rather than being discovered during it.

## Consequences

* An SBOM is now generated in CI (CycloneDX 1.6, from the installed environment so
  versions and licences are the *resolved* ones — generating from `requirements.txt`
  yields no versions at all, since it pins ranges).
* Licence posture becomes a reviewable artefact rather than an assumption.
* **Open decision for the maintainer:** which licence the enterprise deployment
  receives. Internal deployment under AGPL-3.0 carries no distribution obligation,
  but enterprise legal teams commonly reject AGPL on sight regardless of the
  technical position. Deciding this before legal review is materially cheaper than
  during it.
