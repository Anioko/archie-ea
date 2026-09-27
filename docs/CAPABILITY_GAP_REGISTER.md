# Capability-Gap Register — archetype × task × what Archie + the copilot cannot yet do

Grounded gap analysis across all 11 archetypes (charters, role-access, and the
ai-chat tool registry read from code, 1 Sep 2026). This is the roadmap for making
Archie a platform that *runs* enterprise architecture for its users, and for
making the AI copilot an architect that acts, not just drafts.

## The one finding everything rolls up to

**The copilot is write-rich for _building_ one solution, but read-poor and
act-less for _governing, assuring, and operating_ the estate.** Of ~73 write
tools, ~54 are generated `create_<ArchiMateElement>` and the rest cluster on the
solution-authoring path (create_solution → motivation CRUD → options → ArchiMate
→ submit_for_arb). The stateful actions each charter names as the *core job* have
no tool, and the reads the personas need have no binding even though the services
exist. Tools are also **not** persona-gated (`agent_runner` hands all 92 to every
charter), so "you brief, you don't build" is prompt etiquette, not enforcement.

## Cross-cutting gaps, ranked by how many personas they unblock

| # | Gap | Personas hit | Why it matters | The close |
|---|-----|--------------|----------------|-----------|
| G1 | **No governance/exec READ tools** over existing services | CTO, arb_member, portfolio_mgr, solution_architect, security | The AI recites 3 injected aggregates and can't answer the persona's headline question; data + routes already exist | A read-tool layer: `get_investment_priorities`, `get_executive_dashboard`, `get_arb_status`, `query_control_coverage`, `get_portfolio_cost_breakdown`, `query_traceability` |
| G2 | **No UPDATE/action tools** — AI creates & reads, cannot mutate stateful artifacts | EA, BA, DA, portfolio_mgr, arb_member, app_mgr, solution_architect | Every remediation the AI *detects* drops back to a human form | `approve`-tier action tools through the existing gate: `record_capability_maturity`, `score_rationalization`, `set_data_classification`, `record_arb_decision`, `create_adr`, `update_application_fields` |
| G3 | **No MERGE/dedup anywhere** | EA, BA, DA (systemic) | `store-agreement` ratchet, 6 unreconciled capability stores; the #1 way the record rots | `merge_capabilities`, `merge_data_objects` (repoint-then-retire, reversible per the owner's remediation rule) |
| G4 | **No BULK operational tools** | app_mgr, portfolio_mgr, platform_admin | A portfolio sweep = N confirmations | `bulk_update_application_status(filter, status, rationale)` — one confirmation per set |
| G5 | **Orphaned / unpromoted capabilities** | procurement, platform_admin, security | Real engines exist but the agent can't reach them | Promote to tools: `create_vendor`, `bulk_import_with_ai`, `contract_ai_extract`; wire the built-but-buried compliance API to nav + tools |
| G6 | **`security_architect` is a phantom role** | security_architect | Not in VALID_ROLES, no charter, no nav → falls back to solution_architect sidebar + EA persona; compliance/control model built but orphaned | Add the role, a charter, a `ROLE_SECTION_ACCESS` + a Compliance zone; `map_control_to_application`, `query_control_coverage` |
| G7 | **`platform_admin` has no charter** | platform_admin | The most operational role gets an EA persona with no admin data | An operational charter + `_platform_admin_context`; admin action tools (`invite_user`, `set_user_role`) |
| G8 | **No procurement contract/license write tools** | procurement | The entire procurement mutation surface is UI-only | `create_contract`/`renew_contract`/`upsert_license` (approve-tier) |

## Per-persona headline (top gap each)

- **enterprise_architect** — cannot persist a rationalization score (`propose_rationalization` is read-only).
- **business_architect** — no maturity-write tool; the persona's core artifact is heatmap-UI only.
- **data_architect** — canonical-entity consolidation (its defining job) has no support anywhere; cannot set `data_classification` despite the route existing.
- **solution_architect** — cannot author an ADR (the artifact its charter centres on) though `ADRService.create_adr` exists; ARB is write-only to the AI.
- **security_architect** — does not exist as a first-class role; compliance model built but orphaned.
- **cto** — its headline question (investment posture) has a screen but no tool.
- **arb_member** — cannot record a decision or its conditions; the decisive governance act is human-on-screen only.
- **portfolio_manager** — cannot write a TIME disposition/score; no cost/savings tool.
- **application_manager** — no bulk lifecycle tool; cannot create/edit an application; charter's "incident coherence" has no data source.
- **procurement** — zero contract/license write tools.
- **platform_admin** — no charter; zero admin write tools.

## Build order (highest leverage first)

1. **G1 governance/exec read-tool pack** — lowest risk (read-only), broadest coverage, prerequisite for acting. Wraps existing services.
2. **G2 governed action tools** — `create_adr` first (clean, high-value, real service), then `record_capability_maturity`, `score_rationalization`, `set_data_classification` through the propose→validate→approve→apply pattern already proven for genome patches.
3. **G3 merge tools** — resolves the systemic duplication debt.
4. **G6/G7 missing roles/charters** — unblock security_architect and platform_admin.
5. **G4/G5/G8 operational + promotion** — bulk actions, promote buried engines, procurement writes.

The through-line: the genome-substrate pattern (propose → validate → ground → approve → apply, with the LLM never applying directly) is the safe chassis for turning every one of these detected-but-unactionable findings into a governed action. This register is what "the AI is the architect" cashes out to, task by task.
