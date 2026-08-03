"""
Governance alignment: retrieved architecture context influencing option ranking.

Two routes retrieved RAG context — architecture principles, prior ARB decisions,
reference architectures, established patterns — and threw the result away.
`design_solution()` could not consume it: it is deterministic, ranking
vendor/build/hybrid options from the capability, its vendors and the constraints,
with no LLM prompt for a text blob to enter. So the retrieval was four SQL queries
per request feeding nothing.

The context now contributes a bounded, explainable term to ranking. The design
constraints that shaped it, each pinned by a test below:

  It must be invisible when absent. The endpoint retrieves best-effort and
  swallows failures, so ranking must not depend on retrieval having succeeded —
  no context has to mean byte-identical scores.

  It must be bounded. Alignment with a principle is a tie-breaker between
  comparable options, not grounds for promoting a poor option over a strong one.

  It must be explainable. An architect has to see WHICH principle or prior
  decision moved an option up, or the ranking cannot be defended in an ARB. That
  is also why matching is term-overlap rather than embeddings: there is no vector
  index behind get_context_for_solution(), and an opaque similarity score would be
  worse than no score at all.
"""

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    return application


@pytest.fixture
def service(app):
    from app.services.architecture_assistant_service import ArchitectureAssistantService

    with app.app_context():
        yield ArchitectureAssistantService()


def _option(name, description="", pros=None, score=50.0):
    from app.services.architecture_assistant_service import SolutionOption

    return SolutionOption(
        id=name.lower().replace(" ", "-"),
        name=name,
        description=description,
        pros=pros or [],
        total_score=score,
    )


CONTEXT = {
    "principles": [
        {
            "name": "Prefer managed cloud services",
            "description": "Favour managed cloud hosting over self-managed infrastructure.",
        }
    ],
    "prior_decisions": [
        {"name": "ARB-114 kubernetes standard", "description": "Kubernetes approved for container workloads."}
    ],
    "reference_architectures": [],
    "existing_patterns": [],
}


class TestAbsentContextChangesNothing:
    """The no-context path must be identical to the previous behaviour."""

    @pytest.mark.parametrize("ctx", [None, {}, {"principles": []}])
    def test_scores_are_untouched(self, service, ctx):
        options = [_option("Alpha", score=70.0), _option("Beta", score=40.0)]
        ranked = service._rank_options(options, constraints=None, rag_context=ctx)

        assert [o.total_score for o in ranked] == [70.0, 40.0]
        assert all(o.governance_alignment == 0.0 for o in ranked)
        assert all(o.governance_notes == [] for o in ranked)

    def test_rank_options_still_works_without_the_argument(self, service):
        """Existing callers pass two arguments; that must keep working."""
        ranked = service._rank_options([_option("Solo", score=10.0)])
        assert ranked[0].recommendation_rank == 1


class TestAlignmentIsScored:
    def test_matching_option_gains_score_and_a_reason(self, service):
        aligned = _option(
            "Managed Cloud Kubernetes Platform",
            description="Managed cloud hosting on kubernetes for container workloads.",
            score=50.0,
        )
        ranked = service._rank_options([aligned], rag_context=CONTEXT)

        assert ranked[0].governance_alignment > 0
        assert ranked[0].total_score > 50.0
        assert ranked[0].governance_notes, "an adjusted score must carry its reason"
        joined = " ".join(ranked[0].governance_notes).lower()
        assert "principle" in joined or "prior arb decision" in joined

    def test_unrelated_option_is_not_credited(self, service):
        unrelated = _option(
            "Fax Gateway Appliance",
            description="On-premises fax transmission hardware for paper documents.",
            score=50.0,
        )
        ranked = service._rank_options([unrelated], rag_context=CONTEXT)

        assert ranked[0].governance_alignment == 0.0
        assert ranked[0].total_score == 50.0

    def test_a_single_shared_word_is_not_evidence(self, service):
        """One overlap is coincidence often enough to make everything look aligned."""
        weak = _option("Cloud Fax Appliance", description="Fax hardware.", score=50.0)
        ranked = service._rank_options([weak], rag_context=CONTEXT)
        assert ranked[0].governance_alignment == 0.0

    def test_generic_words_do_not_count(self, service):
        """'solution', 'platform', 'architecture' match everything and mean nothing."""
        generic = _option(
            "Enterprise Solution Platform",
            description="A solution platform for business systems and services.",
            score=50.0,
        )
        ranked = service._rank_options([generic], rag_context=CONTEXT)
        assert ranked[0].governance_alignment == 0.0


class TestTheAdjustmentIsBounded:
    def test_alignment_cannot_overturn_a_large_score_gap(self, service):
        """A tie-breaker, not a trump card."""
        strong = _option("Strong But Unaligned", description="Fax hardware.", score=90.0)
        aligned = _option(
            "Weak But Aligned",
            description="Managed cloud kubernetes hosting for container workloads.",
            score=50.0,
        )
        ranked = service._rank_options([strong, aligned], rag_context=CONTEXT)

        assert ranked[0].name == "Strong But Unaligned"
        assert ranked[0].recommendation_rank == 1

    def test_alignment_breaks_a_tie(self, service):
        tied_aligned = _option(
            "Aligned",
            description="Managed cloud kubernetes hosting for container workloads.",
            score=60.0,
        )
        tied_plain = _option("Plain", description="Fax hardware.", score=60.0)
        ranked = service._rank_options([tied_plain, tied_aligned], rag_context=CONTEXT)

        assert ranked[0].name == "Aligned"

    def test_gain_never_exceeds_the_declared_weight(self, service):
        """Saturating, so many near-duplicate principles cannot compound."""
        many = {
            "principles": [
                {"name": f"Principle {i}", "description": "Managed cloud kubernetes container hosting."}
                for i in range(25)
            ]
        }
        option = _option(
            "Managed Cloud Kubernetes",
            description="Managed cloud kubernetes container hosting.",
            score=50.0,
        )
        ranked = service._rank_options([option], rag_context=many)

        assert ranked[0].governance_alignment <= 1.0
        assert ranked[0].total_score <= 50.0 + service.GOVERNANCE_WEIGHT
        assert len(ranked[0].governance_notes) <= 5, "notes must stay readable"


class TestMalformedContextIsSurvivable:
    """Retrieval is best-effort upstream; the ranker must not be the thing that breaks."""

    @pytest.mark.parametrize(
        "ctx",
        [
            {"principles": [None, "not a dict", 42]},
            {"principles": [{}]},
            {"principles": [{"name": None, "description": None}]},
            {"unexpected_key": [{"name": "x", "description": "y"}]},
        ],
    )
    def test_does_not_raise(self, service, ctx):
        ranked = service._rank_options([_option("Any", score=50.0)], rag_context=ctx)
        assert ranked[0].total_score == 50.0


class TestSignatureRemainsBackwardCompatible:
    def test_design_solution_accepts_rag_context(self):
        import inspect

        from app.services.architecture_assistant_service import ArchitectureAssistantService

        params = inspect.signature(ArchitectureAssistantService.design_solution).parameters
        assert "rag_context" in params
        assert params["rag_context"].default is None, "must stay optional"
