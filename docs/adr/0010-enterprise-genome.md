# ADR 0010: The Enterprise Genome — generalise the codegen IR to every EA domain

Status: proposed (1 Sep 2026)

## The insight (owner, 1 Sep 2026)

The codegen subsystem's real value is not code generation. It is a *pattern*:

> a model → a validated intermediate representation (the **genome**) → many
> generated artifacts, each traceable back to the model element that caused it.

Today that pattern is pointed at **one slice** of the enterprise — application /
solution → code. But an enterprise architecture has seven ArchiMate layers, and
Archie already models all of them (measured: business 13 element types,
technology 13, motivation 10, application 9, implementation 5, strategy 4,
physical 4). Applications are one aspect. **The logic should be applied to every
domain, not replicated as more code generators.**

The deterministic core that makes this cheap already exists:
`genome_to_bundle.py` turns a genome into artifacts with **zero LLM calls**, and
documentation is Jinja, not LLM. Only *code content* generation is LLM-based (and
unproven — see the reuse assessment). So generalising the pattern to other
domains rides on the **deterministic** half, which is the safe, reproducible half.

## Decision

Promote the codegen genome to an **Enterprise Genome**: one validated IR over the
whole ArchiMate model, from which each domain generates its own artifacts, and
over which the AI reasons with a single shared context.

Per domain — source elements Archie already holds → genome slice → artifacts →
the traceability that is the actual product:

| Domain | Source elements (already modelled) | Generated artifacts | Traceability that sells it |
|---|---|---|---|
| **Application** *(exists)* | components, services, interfaces | code, API stubs, mobile | code → requirement |
| **Data** | data objects, entities | DDL, ORM, lineage graphs, data catalogue, DPIA records | field → purpose (GDPR Art. 30) |
| **Business** | capabilities, value streams, processes, actors | operating model, RACI, process specs, capability heatmaps | capability → supporting system |
| **Technology** | nodes, system software, networks | IaC (Terraform / K8s), network diagrams, CMDB entries | infrastructure → business service |
| **Security** | controls, risks, constraints, requirements | policy-as-code, control matrices, evidence packs, audit bundles | control → requirement (SOC 2 / ISO 27001) |
| **Motivation** | drivers, goals, requirements, principles | OKRs, strategy briefs, requirement traceability matrices | outcome → driver |
| **Implementation** | plateaus, work packages, gaps | roadmaps, migration plans, project charters, dependency plans | change → gap it closes |

The unit of reuse is **not** a new code generator per domain. It is:
1. a **genome schema per domain** (what fields, what validation) — the data-
   architect / business-architect artefact;
2. a **deterministic emitter** (`genome_to_<domain>_bundle`, Jinja/rule-based,
   the `genome_to_bundle` pattern) — reproducible, no LLM;
3. **provenance carried structurally**, not post-injected — every emitted field
   holds the `archimate_element_id` it came from, done in the emitter where it is
   reliable, not asked of an LLM where the codegen proved it is not.

## Why this is the AI vision, not adjacent to it

The Enterprise Genome is the **shared context** the AI needs to stop being a
navigation assistant. "Which security controls are affected if we decommission
application X?" stops being a screen the human clicks through and becomes a
**query over one genome** that already links application → capability → control →
requirement. The AI reasons over the genome and *emits genome*, which is
schema-validated and traceable — so its output is governable by construction,
which free-text output never is. This is the concrete substrate under
[ADR 0009](0009-continuous-model-maintenance.md)'s maintenance loop: drift
detection becomes *diff the observed estate against the genome*, per domain.

## Consequences

- The AI becomes **domain-general**: the same reason-over-genome / emit-genome
  loop serves the data architect, the security architect, the business architect
  — not just the solution architect. That is what "replace the need to hire more
  architects" actually requires: one engine, every domain.
- **Regulated domains become the wedge.** Security and data carry the strongest
  traceability requirement (prove control → requirement, field → purpose), and
  that is exactly what the genome provenance delivers. This is the sharpest
  external sale.
- It rides the **deterministic** half of codegen, so it does not inherit the
  unproven LLM-codegen risk. Each domain emitter is reproducible and testable —
  and unlike today's codegen, **must ship with tests** (codegen has zero).
- Sequencing: this depends on [ADR 0008](0008-one-system-of-record.md). A genome
  built over stores that disagree produces artifacts that disagree. One system of
  record per concept is the precondition, per domain, before its genome is trusted.

## What must be true before building each domain's genome

The same discipline as everything else: a domain's genome is not "done" because
the schema compiles. It is done when its emitter produces an artifact a
practitioner in that domain confirms is correct, from real model data, with
provenance that traces. Start with **one** domain end to end (data or security —
highest traceability value), prove the loop, then generalise. Do not build seven
genome schemas before the first one has generated a single verified artifact.
