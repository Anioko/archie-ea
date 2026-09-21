"""Spelling-variant folding shared by every text search in the product.

A label written "Licences" and a query typed "license" are the same word to the person typing it; en-GB source
text and a user's en-US habit should never be a reason a working page cannot be found. normalise_search_text
folds both directions of four known variant pairs, then lowercases, so any comparison done on its output is
spelling-blind for those words and unaffected for everything else.
"""
import pytest

from app.utils.search_text import normalise_search_text


@pytest.mark.parametrize("a,b", [
    ("licence", "license"),
    ("Licences", "licenses"),
    ("organisation", "organization"),
    ("Organisational", "organizational"),
    ("programme", "program"),
    ("Programmes", "programs"),
    ("rationalisation", "rationalization"),
    ("Rationalisation", "rationalization"),
])
def test_variant_pairs_normalise_to_the_same_string(a, b):
    assert normalise_search_text(a) == normalise_search_text(b)


def test_normalisation_is_case_insensitive():
    assert normalise_search_text("LICENCE") == normalise_search_text("licence")


@pytest.mark.parametrize("text", ["Vendors", "Impact Analysis", "Data Architecture", ""])
def test_words_with_no_variant_are_unaffected_besides_case(text):
    assert normalise_search_text(text) == text.lower()


def test_a_variant_substring_inside_a_longer_word_is_still_folded():
    # "Licences" contains "licence"; the whole label must match a query of either spelling.
    assert "license" in normalise_search_text("Vendor Licences")


def test_matching_uses_the_normalised_forms_on_both_sides():
    label = normalise_search_text("Licences")
    query = normalise_search_text("licence")
    assert query in label


@pytest.mark.parametrize("prefix,label", [
    ("lic", "Licences"), ("licen", "Licences"), ("licenc", "Licences"),
    ("organis", "Organisations"), ("organisatio", "Organisations"),
    ("programm", "Programmes"),
    ("rationalisatio", "Rationalisation"),
])
def test_a_partial_british_spelling_still_matches_while_typing(prefix, label):
    # A query is typed one character at a time. The British and American spellings diverge partway
    # through each word ("licen" then "c" vs "s"), so a prefix that has diverged but not yet completed
    # the British word (e.g. "licenc") must still match -- not just the finished word.
    assert normalise_search_text(prefix) in normalise_search_text(label)
