# SAP Code-Generation: Hybrid Architecture Assessment

Bucket: `sap-s4-interface-register`
Author: ai-solution-architect
Status: **advisory memo — not an ADR, not a build instruction**
Date: 16 Sep 2026

Downstream: `llm-architect` turns any accepted part of §B into binding LLM
ADRs before a line of LLM code is written. `tech-lead` reconciles this with
`solution-architect`'s SDD. **§D contains a commercial/licensing question
that is explicitly the owner's to decide, not mine** (root CLAUDE.md, "Own
the decision" — genuine escalations are commercial and licensing choices).

---

## 0. What this memo is answering

The Interface Register built in this bucket is a governance/tracking layer:
`ArchiMateElement(type='ApplicationInterface')` + `ApplicationInterfaceMetadata`
+ `Gap(gap_kind='plateau_transition')` between two `Plateau`s +
`WorkPackage` cost rollup against the initiative's `investment_budget`
(£3m). Per `integration-spec.md` it deliberately does **not** touch SAP.

An earlier CTO decision ruled out building an SAP code generator inside
Archie, on the grounds that Archie has zero SAP connectivity today — no
RFC/BAPI client, no ABAP templates, no transport automation — and that
adding them is a new subsystem requiring real SAP Basis credentials, not a
feature.

Five external references have been surfaced. This memo asks whether any of
them change that decision, and what a "hybrid" would concretely be.

---

## 1. Evidence status of each reference — read before the analysis

| # | Thing | Research status | Confidence |
|---|---|---|---|
| 1 | sapdev.ai | Researched (vendor's own marketing claims, not independently verified) | Claims understood; **capability unverified** |
| 2 | Google *Vertex AI / Agent Platform SDK for ABAP* | Researched | High |
| 3 | AWS SDK for SAP ABAP | Researched | High |
| 4 | SAP *ABAP AI SDK / Generative AI in ABAP Cloud* (ISLM) | **FETCH FAILED — JS-rendered page, only the title returned. No content obtained.** | **None. Treated as unknown.** |
| 5 | Microsoft *AI SDK for SAP ABAP* (`microsoft.github.io/aisdkforsapabap`) | Researched (added late) | High |

**#4 is explicitly unresearched.** I have no information about what SAP's own
first-party generative-AI-in-ABAP-Cloud capability does, what it costs, what
it requires, or whether it overlaps sapdev.ai. I am not going to infer it
from the name. Per this repo's no-fabrication rule, an unknown is written as
an unknown rather than as a plausible-sounding paragraph.

**Action required before any decision in §D is final:** someone with a
browser or an SAP account (S-user) must read
`help.sap.com` on "Generative AI in ABAP Cloud" / ISLM. It is the single
highest-leverage open question here, because if SAP ships a first-party
capability covering part of sapdev.ai's scope, the buy question in §D
changes shape entirely — a first-party SAP capability comes with support,
licensing clarity and upgrade safety that a third-party CLI tool driving
SAP GUI Scripting does not.

Note also on #1: everything known about sapdev.ai is the vendor's own
description. "Enforces quality gates", "signed approval gates", "reversible
changes" are marketing claims, not observed behaviour. Nothing in §D should
be decided on those claims without a proof-of-concept against a real
sandbox.

---

## A. Do #2, #3, #5 (or possibly #4) change the earlier analysis?

**No — and the reason is sharper than "they're different tools". They sit on
the opposite side of the SAP boundary and point the opposite direction.
With #5 added, this is now demonstrably an industry-wide pattern rather than
a coincidence of two examples.**

I confirm the reasoning as handed to me, and would state it more precisely:

There are two entirely distinct integration directions, and conflating them
is the trap this whole question contains.

**Direction A — outside-in (spec → ABAP).** Something external holds a
design specification and must cause ABAP objects to come into existence
inside a SAP system: create DDIC objects, generate classes/function
modules/RFC wrappers/CDS views/RAP BOs, assign transports, run ATC and ABAP
Unit, move through STMS. This requires: SAP system credentials, a write
channel into the system (RFC APIs or GUI Scripting), transport authority, a
sandbox to fail safely in, and Basis governance. **This is sapdev.ai's
problem, and it is the problem the earlier CTO decision was about.**

**Direction B — inside-out (ABAP → cloud AI).** ABAP code *that already
exists and is already running* calls out to an external service — Gemini,
Claude, Azure OpenAI, an embeddings endpoint, Bedrock, Textract — to add an
AI feature to a business process. Requires: an existing SAP system
(NetWeaver 7.4+ / S/4HANA / BTP ABAP Environment), an account with the AI
provider, existing ABAP developers, and an ABAP developer to *write the
calling code by hand*. **This is what #2, #3 and #5 all are.**

### A.1 The 3-for-3 convergence — this is the load-bearing observation

Google, AWS and Microsoft have each independently shipped the same product:

| Vendor | Product | AI services exposed to ABAP | Prerequisite | Generates ABAP? |
|---|---|---|---|---|
| Google | Vertex AI / Agent Platform SDK for ABAP | Gemini, Claude, Gemma, embeddings, vector search, function calling | Existing SAP system (Compute Engine SAP / RISE PCE / on-prem) | **No** |
| AWS | SDK for SAP ABAP | 200+ AWS services — IDP, image recognition, event-driven | Existing SAP system, NetWeaver 7.4+ | **No** |
| Microsoft | AI SDK for SAP ABAP | Azure OpenAI — chat completion, models, fine-tuning; product recommendation, customer-service automation | Existing SAP system + Azure OpenAI account | **No** |

Three independent vendors, three independent engineering organisations,
three independent commercial strategies — and all three converged on an
*identical* shape: an ABAP-side client library, installed into a running
system, consumed by hand-written ABAP, for adding AI features to business
logic. Not one of them attempts code generation, custom-code inventory,
S/4HANA readiness remediation, ATC automation or transport assignment.

That convergence is evidence, not decoration. When three competitors
independently draw the same product boundary, the boundary is a real
structural feature of the market rather than one vendor's scoping choice. It
means "these SDKs are a different problem from codegen" is not a plausible
reading I constructed to defend a prior decision — it is the industry's own
settled segmentation. A hypothetical fourth vendor's ABAP AI SDK can now be
predicted to sit on the same side of the line without being researched,
which is a useful property for whoever fields the next "but have you seen
this one?" question.

It also raises the prior on what #4 turns out to be. SAP's own offering,
being an *ABAP AI SDK* by name, is more likely than not to be the
first-party member of this same family — i.e. Direction B, not a code
generator. **I am not treating that as established** (§1 stands: #4 is
unresearched and must be read by a human), but it is the hypothesis to test
first, and it means the realistic upside from researching #4 is "SAP has a
native version of #2/#3/#5", not "SAP has a free sapdev.ai".

### A.2 Does any of them reduce a cost the earlier decision named?

The load-bearing test: *does #2, #3 or #5 reduce any of the four costs?*

| Cost named in the earlier decision | Do #2/#3/#5 reduce it? |
|---|---|
| No RFC/BAPI client in Archie | No — these are ABAP-side libraries; they do not give a Python/Flask app an RFC client. |
| No ABAP templates / codegen capability | No — none generates ABAP. They are consumed *by* hand-written ABAP. |
| No transport automation | No — out of scope for all three. |
| No real SAP Basis credentials / access | **No — worse: all three *require* exactly that access as a precondition.** |

Every cell is "no", three times over, and the last one inverts: these SDKs
are downstream of the blocker, not a way around it. A tool whose first
install step assumes the access you lack cannot be the answer to lacking the
access.

**One correction/nuance I'll add rather than just agreeing.** There is a
tempting-but-wrong reading available, and it should be named so nobody
re-derives it in three weeks: "Google's SDK does vector search and embeddings
in ABAP — Archie also does embeddings via `sentence-transformers` — therefore
they connect." They do not. Archie's embeddings serve Archie's own retrieval
over its own EA model. Google's ABAP vector search serves ABAP code over SAP
business data. Two systems both having embeddings creates no integration
surface whatsoever; it is a coincidence of technique, and if anything it is a
second-system-of-record hazard (two stores answering "what is semantically
similar to this?") if anyone later tries to federate them. ADR-0008 applies
across the boundary too.

**Verdict on (a): the earlier decision stands unchanged, and is now better
evidenced than when it was made.** Only #1 (sapdev.ai) and possibly #4
(unknown) are even in the category of thing that could change it. #2, #3 and
#5 are not evidence bearing on it.

---

## B. What a genuine hybrid would actually look like

The hybrid is real, and it is architecturally cleaner than either extreme,
**because the split falls exactly on the boundary that already exists**:
Archie owns the *decision and its justification*; something else owns the
*artefact and its deployment*. Archie is a system of record for architecture
intent. It is not, and per the earlier decision should not become, a SAP
deployment tool.

### B.1 The shape

```
  ARCHIE (this repo)                 |  BOUNDARY  |   SAP-SIDE TOOLING
  ---------------------------------- |            | ---------------------------
  ArchiMateElement                   |            |
   (type=ApplicationInterface)       |            |
  + ApplicationInterfaceMetadata     |            |
  + SystemDependency x2              |   export   |
  + ArchiMateRelationship x2-3       |  ========> |   sapdev.ai "sap-gen-code"
  + Gap(plateau_transition)          |   (spec    |   (or equivalent, or a
  + WorkPackage(cost, effort)        |   handoff) |    human ABAP developer)
  + Initiative.investment_budget     |            |
                                     |            |          |
  Interface Build Record   <======== |   import   |          v
  (status, transport id, ATC result) |  <=======  |   ABAP objects, transports
                                     | (evidence) |
```

Archie's half is a **spec-and-evidence ledger**. It never holds ABAP, never
holds SAP credentials, never calls SAP. The downstream tool never decides
*what* should be built or *whether it is affordable* — that is the register's
job and it is already built.

### B.2 The trigger point in the lifecycle

The right trigger is **not** "interface created". An interface row in the
register is a statement that something exists or should exist; it is not yet
an approved, funded, specified piece of work. Generating code from it would
be generating from an unratified intent.

The correct trigger, in the vocabulary this bucket already established:

> An interface becomes eligible for downstream code generation when its
> `Gap` (with `gap_kind='plateau_transition'`, `originating_plateau_id` =
> Current Integration Landscape, `target_plateau_id` = S/4HANA-Integrated
> Landscape) has **at least one `WorkPackage` attached carrying a non-NULL
> `estimated_cost` and `estimated_effort_hours`**, and that work package has
> been accepted against the initiative's `investment_budget`.

That is precisely the state the Task 04 cost rollup already computes. It is
not a new concept and needs no new column beyond a status marker.

Why that point and not earlier: a costed, budget-accepted WorkPackage is the
first moment the organisation has actually said "we are doing this one, at
this size". Before that, an export is speculative. Gating on it also means
the £3m budget rollup is load-bearing rather than decorative — the money
question gates the build question, which is the correct ordering for a
governance product.

Why not later (e.g. gate on ARB approval): defensible, and `tech-lead`
should consider it. An ARB decision gate would be stricter and would reuse
this repo's existing governance workflow. I'd note it as the obvious
alternative rather than silently picking the looser one. **Flagged for
tech-lead: costed-WorkPackage gate vs ARB-decision gate is a real fork.**

### B.3 What actually flows out — content, not format

The export is an **interface build specification**, one document per gap
(not per interface — the gap is what carries the change intent; a
`gap_type='retirement'` interface must not export as something to build).

Content, all of which the register already holds:

- **Identity & provenance** — `archimate_element_id`, gap id, work package
  id, initiative id, organisation id, register URL, export timestamp,
  Archie `build_id`. Provenance is not optional: the downstream artefact
  must be traceable back to the exact register state that justified it, or
  the ledger is decorative.
- **Interface technical contract** — from `ApplicationInterfaceMetadata`:
  `interface_type`, `protocol`, `data_format`, `message_pattern`,
  `is_synchronous`, `authentication_method`, `business_criticality`,
  `transaction_volume_daily`. This is the substance a generator needs to
  choose IDoc vs RFC vs OData/CDS vs RAP.
- **Endpoints** — source and target `ApplicationComponent` identity via the
  two `SystemDependency` rows, plus the ArchiMate composition/serving/
  realization edges. Which side is SAP and which is the satellite system is
  derivable from these and must be explicit in the export, not implied.
- **Change intent** — `gap_type` ∈ `{protocol_change, new_interface,
  retirement}` and the two plateau names. `new_interface` → build;
  `protocol_change` → modify an existing object; `retirement` → **decommission,
  explicitly not a generation input.** A generator handed a retirement row
  and told to "generate" is a real hazard; the export must carry the verb.
- **Sizing & budget envelope** — `estimated_effort_hours`, `estimated_cost`,
  the derived T-shirt band (derived at display time per the brief — do not
  persist it just to export it; derive it in the exporter the same way).
- **Explicitly NOT exported** — anything Archie does not actually know:
  field-level mappings, SAP table/field names, ABAP object naming, transport
  layer, package assignment. Archie's register does not hold these. Emitting
  a plausible-looking guess for them is exactly the `fabricated-data` failure
  this repo has a gate for, and it is far more dangerous crossing a system
  boundary than on a screen, because the receiving tool cannot tell a guess
  from a fact. **Absent fields must be absent, not defaulted.**

### B.4 Format

A versioned JSON document (`spec_version`, so the contract can evolve without
silently changing meaning) is the right primary form — it is machine-readable,
diffable, and it is what a CLI tool ingests. sapdev.ai's stated inputs are
Excel/PDF/Word; if a PoC confirms JSON is not accepted, a generated
structured Word/Excel rendering of the *same* JSON is acceptable — but the
JSON stays the system of record and the document is a projection of it, never
hand-edited. Two hand-editable copies of a spec is ADR-0008 again.

### B.5 What flows back — and why this half matters more than people expect

The return path is what makes this a governance product rather than a
one-way export button. For each exported spec, the register should be able to
record and display: downstream status (`exported` / `generated` /
`in_transport` / `deployed` / `failed`), transport request id, ATC result
summary, ABAP Unit result summary, and a link to the downstream audit ledger
entry.

Without it, the Interface Register answers "what did we decide and what will
it cost" and goes silent exactly when the programme most needs an answer —
"is it actually in the system yet". With it, the £3m rollup can eventually
show *committed vs delivered*, which is the number a transformation
programme director actually wants.

Two hard constraints on this return path:

1. **Archie must not poll SAP for it.** That reintroduces the SAP
   connectivity the whole decision avoids. The downstream tool (or a human,
   or a CI job in the SAP landscape) posts status into Archie. Archie stays
   credential-free with respect to SAP.
2. **Status must never be inferred.** An interface whose downstream status is
   unknown displays as unknown (em dash), not as "pending" and certainly not
   as "deployed". A fabricated delivery status on a £3m programme dashboard
   is the worst instance of this repo's named failure mode.

### B.6 Where the LLM actually is in this hybrid — and where it is not

This is the part `llm-architect` owns, so I will bound it rather than
specify it.

**The code generation LLM is not in Archie.** It is in the downstream tool,
running against SAP, under that tool's governance. Archie does not gain an
ABAP-generating model. That boundary is also what keeps the existing
`llm-boundary` gate (ratchet @ 0 — "a codegen emitter calling an LLM
directly") honest: the exporter is a codegen emitter, and it must not call an
LLM. Serialising register rows into a spec document is deterministic
templating, full stop.

**There is a legitimate, bounded LLM role on Archie's side**, and it is
assistive, not authoritative:

- *Draft* an interface's description or a work package's scope narrative from
  the ArchiMate context, for a human to accept — this is the same shape as
  existing `ai_suggestion_service` behaviour and routes through the existing
  approval choke point (`AIChatApprovalService.approve_and_execute`,
  `app/modules/ai_chat/services/ai_chat_approval_service.py`).
- *Classify* a bulk-imported interface catalogue row into `gap_type` and
  `interface_type` as a **suggestion with confidence**, never a silent write.
- *Explain* a rollup ("why is this XL?") by grounding strictly in the
  retrieved WorkPackage/Gap rows.

**Autonomy line — my actual recommendation to `llm-architect`:**

| Action | Autonomy |
|---|---|
| Summarise / explain register content | Autonomous (read-only, grounded) |
| Suggest a field value on a draft interface | Autonomous to *propose*; human accepts |
| Write/update an `ArchiMateElement`, `Gap`, or `WorkPackage` | **Approval required** — goes through the existing CRUD approval service, no exceptions |
| Set or change `estimated_cost` / `estimated_effort_hours` | **Approval required, and by a different human than the requester** — this number rolls into a £3m budget |
| Emit an export to the downstream codegen tool | **Human action only. No agent triggers this, ever.** |
| Ingest downstream status back into Archie | Mechanical, authenticated, no LLM in the path |

The export trigger being human-only is the single most important line in this
memo. An agent that can cause ABAP to be generated and transported into a
SAP landscape, without a named person pressing a button, is an unacceptable
blast radius — and it would be reached through a chain of individually
reasonable-looking steps, which is exactly how this class of incident
happens. Any retrieved content crossing into a prompt here (interface
descriptions, imported catalogue rows — both partly attacker-influenceable
via CSV import) must be fenced per the `ai-untrusted-content` gate.

### B.7 Conflicts to flag for `tech-lead`

Per my remit I flag rather than resolve:

1. **Gate point**: costed-WorkPackage (§B.2) vs ARB decision. Not resolved
   here.
2. **New persisted state**: the return path (§B.5) needs somewhere to store
   downstream status/transport id. That is a new store and therefore an
   ADR-0008 question `solution-architect`'s SDD does not currently cover.
   Likely correct home is columns on `WorkPackage` or a small
   `InterfaceBuildRecord` carrying `source_table`/`source_id` — but it must
   be decided, not accreted. **Note this is not free: new columns must be
   nullable and NULL-tolerant per `reconcile-schema`'s ADD-only constraint.**
3. **Pre-existing duplicate**: `integration-spec.md` §0 already flags
   `ApplicationInterface` (`application_layer.py`) as an unretired
   overlapping store. Any export contract must read from the chosen system of
   record (`ArchiMateElement` + `ApplicationInterfaceMetadata`), or the
   exported spec and the on-screen register will eventually disagree — and
   the disagreement will be discovered in a SAP transport, not on a screen.

---

## C. Where #2/#3/#5 actually fit — distraction now, plausible later, different budget line

**For the current decision: a distraction.** They answer a question nobody in
this programme has asked. Including them in a build-vs-buy comparison would
make the comparison incoherent, because they are not substitutes for the
thing being compared. I would remove all three from the decision pack
entirely rather than list them as "also considered" — a rejected-but-listed
option invites someone to re-litigate it later, and with three near-identical
entries the pack looks like it contains four options when it contains one.

**Is there a legitimate later-stage use case? Yes, one, and it is genuinely
distinct.** Once the customer's S/4HANA landscape is live and has custom ABAP
in it, a later programme might want an AI feature *inside* a SAP business
process — classify an incoming supplier document, triage an inbound order
exception, semantic-match a material master record, the product-recommendation
and customer-service-automation cases Microsoft's SDK names explicitly. That
is Direction B, and #2, #3, #5 (or #4) would be the right tool for it.

Three things follow, and they are why this stays off the current page:

1. **It is a different programme with a different sponsor.** It is an SAP
   application-development initiative, not an EA-tooling or
   integration-migration initiative. Different budget, different team.
2. **It is strictly after this one.** Its precondition is a live S/4HANA
   system with custom ABAP — i.e. the output of the transformation this
   register is governing. You cannot start it now even if you wanted to.
3. **Archie's role in it would be to model it, not to build it.** If such an
   AI-in-SAP feature is ever built, it appears in Archie as an
   `ApplicationService`/`ApplicationComponent` with its dependency on an
   external AI provider modelled as a real ArchiMate element — which is
   exactly what Archie is for, and requires zero new Archie capability. That
   is the honest, non-inflated answer to "does Archie have a role here".

One practical consequence of the 3-for-3 convergence (§A.1) worth recording
for that later programme: because Google, AWS and Microsoft ship
functionally equivalent SDKs, **the vendor choice at that point is not an
architecture decision at all** — it falls out of whichever hyperscaler
The customer's SAP landscape already runs on and whose commercial agreement
already exists. Nobody should spend architecture time comparing them; the
comparison has no discriminating technical axis.

---

## D. Recommendation

**Recommendation: HYBRID, staged — and the first stage is the only one to
authorise now.**

Concretely: **build the export contract (§B.3/§B.4) inside Archie; do not
build, and do not yet buy, any code generation.** Re-open the buy question
only after (i) #4 is actually researched and (ii) a sapdev.ai PoC has been
run against a real sandbox.

Why not the alternatives:

- **Build** (SAP codegen inside Archie) — rejected, and the earlier CTO
  decision was right. Nothing in #1–#5 moves it. RFC client + ABAP templates
  + transport automation + ATC integration is a subsystem comparable in size
  to everything this repo already is, in a domain this team has no assets in,
  gated on credentials we don't hold.
- **Buy** (sapdev.ai now) — premature, not wrong. Everything known about it
  is vendor marketing, #4 is unresearched, and the integration point it would
  plug into does not exist yet.
- **Defer entirely** — wasteful. The export contract is genuinely useful with
  or without any downstream tool: the same structured spec is what you hand a
  human ABAP developer or a systems integrator. Building it is not a bet on
  sapdev.ai.

That last point is the crux and the reason this recommendation is safe:
**stage 1 has no vendor dependency.** A versioned interface build spec
serialised from the register is valuable if the downstream is sapdev.ai, if
it's SAP's own tooling, if it's Capgemini's ABAP team, or if it's one
developer with SE38 open. It is the deliverable the register was always
implicitly producing informally in Word documents. Building it commits to
nothing and de-risks every later option.

### D.1 Staging

**Stage 1 — Export contract (recommend: authorise now).**
Versioned JSON spec per costed gap, a human-triggered export action, and the
"no fabricated fields" rule enforced. No SAP contact, no credentials, no
vendor. Small, in-repo, testable by a browser walkthrough per this repo's
*Done means DEMONSTRATED* rule. Decisions needed: §B.7's three items.

**Stage 2 — Research + PoC (recommend: authorise the research half now; it
is nearly free).**
(a) Someone reads SAP's own generative-AI-in-ABAP-Cloud documentation and
closes the #4 gap — testing first the §A.1 hypothesis that it is the
first-party member of the #2/#3/#5 family rather than a code generator.
(b) If still interesting, a time-boxed sapdev.ai PoC against a **sandbox
only** — take one real exported spec, see whether the generated ABAP is
production-plausible, and verify the "reversible changes" and "signed
approval gates" claims rather than accepting them.

**Stage 3 — Buy decision.** Only after Stage 2 produces evidence. Owner's
call (see D.3).

**Stage 4 — Return-path ledger.** Downstream status back into the register.
Only worth building once something downstream actually exists to report.

### D.2 Decision criteria, stated for a non-technical reader

- **Cost.** Stage 1 is internal effort only, no licence, no vendor. Stage 2's
  research half is hours. Stage 2's PoC half costs a sandbox and some SAP
  Basis time — which is the customer's to grant, not ours. Stage 3's cost is
  unknown because sapdev.ai's pricing has not been obtained; that must be
  asked before, not after, anyone becomes attached to the tool.
- **Timeline.** The register exists now. Stage 1 is the natural next
  increment. Nothing here needs to block the £3m programme's current phase —
  which matters, because the register's value to the programme is
  governance-today, not code-generation-someday.
- **Risk.** The serious risks are all in Stage 3, not Stage 1: a third-party
  tool driving SAP GUI Scripting and RFC APIs against a customer's landscape
  is a high-trust position. Who holds the credentials, whose sandbox, what
  happens on a bad transport, and what the vendor's data-handling posture is
  (does the design spec leave the customer's tenancy?) are all unanswered.
  Stage 1 carries none of this.
- **Licensing / commercial dependency.** Adopting sapdev.ai creates a
  dependency on a single vendor at the point where architecture intent
  becomes deployed code. Note the asymmetry the §A.1 convergence exposes:
  the *AI-in-SAP* market has three interchangeable major vendors and
  therefore near-zero lock-in, whereas the *spec-to-ABAP codegen* market —
  as far as this research reaches — has one named candidate and no
  identified alternative. That is exactly the situation in which to stage
  the commitment rather than take it early. If they disappear, the exported
  spec survives (it's ours, and it's plain JSON) but the generation does not.
- **Third-party data.** A PoC touches the customer's SAP landscape — another
  organisation's real systems and, potentially, their data. That is squarely
  in the escalate-always category.

### D.3 What I am deciding and what I am escalating

**Decided here** (competent-architect calls, per this repo's standing
instruction — not handed back):

- #2, #3 and #5 do not change the earlier analysis and should be dropped from
  the decision pack (§A).
- Archie does not acquire SAP connectivity or ABAP generation (§A, confirming
  the earlier CTO decision).
- The hybrid split is spec-and-governance in Archie / artefact-and-deployment
  outside it, gated on a costed WorkPackage (§B.2, with the ARB-gate
  alternative flagged to tech-lead).
- Export is human-triggered only; no agent autonomy over it (§B.6).
- The exporter emits no LLM-generated field values and omits unknowns rather
  than defaulting them (§B.3).
- Stage 1 is vendor-independent and worth doing regardless of Stage 3.

**Escalated to the owner** (genuinely not mine — commercial, licensing, and
another organisation's real systems):

1. **Do we buy sapdev.ai, or anything like it?** Commercial commitment and
   single-vendor dependency at a critical point in the delivery chain, in a
   segment where no second vendor has been identified.
2. **Do we ask the customer for sandbox SAP access to run a PoC?** This is a
   request to another organisation to touch their real landscape, and it
   changes the engagement's shape and liability.
3. **Is downstream ABAP delivery in Archie's product scope at all,** or is
   Archie deliberately staying an EA governance platform that hands off to
   whatever the client's SI already uses? This is a product-direction
   question with no technically-correct answer — and it is the one that
   actually determines whether Stages 3 and 4 ever happen.

None of these block Stage 1, which is the reason for recommending Stage 1 in
this shape.

---

## E. Open items

- [ ] **#4 unresearched** — SAP's own generative-AI-in-ABAP-Cloud / ISLM
      capability. Fetch failed; content unknown. Must be closed by a human
      with browser or S-user access before §D is final. Hypothesis to test
      first: it is the first-party member of the #2/#3/#5 family (§A.1).
- [ ] sapdev.ai pricing, data-handling posture, and support model — not
      obtained.
- [ ] sapdev.ai's "reversible changes" and "signed approval gates" claims —
      vendor-stated, unverified.
- [ ] Is there a *second* vendor in sapdev.ai's segment? None identified.
      Worth one search before a single-source commitment (§D.2, licensing).
- [ ] `tech-lead`: gate point (costed WorkPackage vs ARB decision).
- [ ] `tech-lead` / `solution-architect`: where downstream build status is
      stored (§B.7 item 2) — an ADR-0008 question not covered by the SDD.
- [ ] `llm-architect`: binding ADRs for the autonomy table in §B.6 before any
      LLM code is written for this feature.
