"""The walkthrough driver and seed must agree on every persona identity."""

from scripts.seed_walkthrough_users import PERSONAS


def test_seed_emails_are_the_addresses_driven_by_the_browser_walkthrough():
    assert PERSONAS == {
        "cto": "cto@walkthrough.example.com",
        "enterprise_architect": "ea@walkthrough.example.com",
        "portfolio_manager": "pm@walkthrough.example.com",
        "arb_member": "arb@walkthrough.example.com",
        "solution_architect": "solution@walkthrough.example.com",
    }
