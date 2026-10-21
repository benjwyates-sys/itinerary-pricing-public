"""Tests for pricing.match under the post-redesign contract: a similarity
score never gates a pricing decision. `auto_accept` is True in exactly two
cases (identical after normalisation, or a saved-alias hit) and False in
every other case, no matter the score. `score` exists only to order
`candidates()` so the operator's best guess is listed first.

Normalisation is the entire safety boundary, which is why it is
deliberately conservative: plural folding only applies to a small
allowlist of domain nouns (never to an arbitrary token, which would merge
proper nouns and genuinely different services), and a small set of
"marker" punctuation characters (%, *, +, currency symbols) is preserved
as its own token instead of being silently deleted, since a rate sheet
uses exactly those to flag something that changes the price.

Organised around that contract:
  - normalize(): the folding rules it must apply, including the
    allowlisted-plural and marker-punctuation guards
  - auto_accept True: identical-after-normalisation pairs, and alias hits
  - auto_accept False: every pair that previously auto-accepted under any
    earlier (now-abandoned) threshold design, every pair that the
    unguarded plural rule or the punctuation-deletes-everything rule
    previously merged, and other distinct services
  - ambiguity: two catalog items that both come back identical to the
    query must never be broken by alphabetical item_id
  - ranking: candidates() must put the right item first against plausible
    distractors, including the transfer-direction case that a prior
    version got wrong at a perfect 1.000, and an absent-item case
  - must-not-regress: determinism, degenerate inputs
  - Aliases: exact-key lookup, hit counting, save/load round-trip, corrupt
    or malformed-but-valid-JSON file handling, and a deleted-item alias
    falling through to scoring
"""

import pytest

from pricing.catalog import CatalogItem
from pricing.match import Aliases, candidates, normalize


def _item(item_id, name):
    return CatalogItem(id=item_id, name=name, name_cell="X!A1", region="R",
                       currency="EUR", unit="per_person",
                       pricing={"pattern": "flat", "cell": "X!B1"})


ITEMS = [
    _item("IT-1", "Uffizi Gallery — Private Guided Tour"),
    _item("IT-2", "Vatican Museums — Skip the Line"),
    _item("GR-1", "Catamaran Cruise — PM (beverages incl.)"),
]


# ---------------------------------------------------------------------------
# normalize()
# ---------------------------------------------------------------------------

def test_normalize_strips_punctuation_and_case():
    assert normalize("Sunset catamaran w/ open bar!") == "sunset catamaran w open bar"


def test_normalize_hyphen_becomes_space_not_deleted():
    assert normalize("Skip-the-Line Tour") == normalize("Skip the Line Tour")


def test_normalize_en_dash_and_em_dash():
    assert normalize("Uffizi Gallery – Private Tour") == normalize("Uffizi Gallery — Private Tour")
    assert normalize("Uffizi Gallery – Private Tour") == normalize("Uffizi Gallery - Private Tour")


def test_normalize_ampersand_becomes_and():
    assert normalize("Cooking class & wine tasting") == normalize("Cooking Class and Wine Tasting")


def test_normalize_collapses_whitespace():
    assert normalize("Sunset   catamaran\tcruise") == "sunset catamaran cruise"


def test_normalize_folds_simple_plurals():
    assert normalize("Gondola rides") == normalize("Gondola Ride")
    assert normalize("VATICAN MUSEUMS") == normalize("Vatican Museums")


def test_normalize_does_not_fold_short_or_double_s_tokens():
    # "bus" (3 chars) and "class" (ends in "ss") must be left alone.
    assert normalize("bus") == "bus"
    assert normalize("class") == "class"


def test_normalize_pure_punctuation_collapses_to_empty():
    assert normalize("!!! --- ...") == ""


def test_normalize_plural_folding_is_allowlisted_not_universal():
    # These must NOT fold: the trailing "s" is part of a proper noun or a
    # word that genuinely changes meaning/price, not a plural of a domain
    # noun. An earlier version folded ANY 4+ char token ending in a single
    # "s", which merged all of these.
    assert normalize("Rhodes Island Tour") != normalize("Rhode Island Tour")
    assert normalize("Blues Cruise") != normalize("Blue Cruise")
    assert normalize("The Baths Excursion") != normalize("The Bath Excursion")
    assert normalize("Falls Foliage Tour") != normalize("Fall Foliage Tour")
    assert normalize("Paros Day Trip") != normalize("Paro Day Trip")
    assert normalize("Private Guides") != normalize("Private Guide")


def test_normalize_marker_punctuation_is_preserved_not_deleted():
    # A footnote asterisk, a supplement "+", a percentage, and a currency
    # symbol all change what the line means or costs — they must survive
    # normalisation as their own token rather than vanish like ordinary
    # connective punctuation.
    assert normalize("Colosseum Tour *") != normalize("Colosseum Tour")
    assert normalize("Colosseum Tour +") != normalize("Colosseum Tour")
    assert normalize("Deposit 50%") != normalize("Deposit 50")
    assert normalize("Tour €50") != normalize("Tour 50")


def test_normalize_ordinary_punctuation_still_becomes_space():
    # Non-marker punctuation (hyphens, dashes, slashes, parentheses) still
    # collapses to a plain separator, unaffected by the marker carve-out.
    assert normalize("Skip-the-Line Tour") == normalize("Skip the Line Tour")
    assert normalize("Uffizi Gallery – Private Tour") == normalize("Uffizi Gallery - Private Tour")
    assert normalize("Tour (Private)") == "tour private"
    assert normalize("Sunset catamaran w/ open bar!") == "sunset catamaran w open bar"


# ---------------------------------------------------------------------------
# auto_accept is True: identical after normalisation
# ---------------------------------------------------------------------------

IDENTICAL_AFTER_NORMALISATION = [
    ("Skip-the-Line Tour", "Skip the Line Tour"),
    ("Half-Day City Tour", "Half Day City Tour"),
    ("Uffizi Gallery – Private Tour", "Uffizi Gallery - Private Tour"),
    ("Cooking class & wine tasting", "Cooking Class and Wine Tasting"),
    ("Cathedral & bell tower entry", "Cathedral and Bell Tower Entry"),
    ("Gondola rides", "Gondola Ride"),
    ("VATICAN MUSEUMS", "Vatican Museums"),
]


@pytest.mark.parametrize("query, item_name", IDENTICAL_AFTER_NORMALISATION)
def test_auto_accept_true_for_identical_after_normalisation(query, item_name):
    catalog = [_item("X-1", item_name)]
    result = candidates(query, catalog, Aliases())
    assert result[0].item_id == "X-1"
    assert result[0].auto_accept is True


def test_auto_accept_true_for_saved_alias():
    aliases = Aliases()
    aliases.add("Sunset catamaran w/ open bar", "GR-1")
    result = candidates("sunset  catamaran W/ Open Bar", ITEMS, aliases)
    assert len(result) == 1
    assert result[0].item_id == "GR-1"
    assert result[0].auto_accept is True
    assert result[0].score == 1.0
    assert result[0].reason == "saved alias"


# ---------------------------------------------------------------------------
# auto_accept is False: every pair that previously auto-accepted at >= 0.85
# under an earlier threshold design, or is otherwise a different/unconfirmed
# service. No score is asserted here — score no longer means anything safety
# -relevant, only auto_accept does.
# ---------------------------------------------------------------------------

MUST_NOT_AUTO_ACCEPT = [
    ("Transfer from Hotel to Airport", "Transfer from Airport to Hotel"),
    ("Private Transfer — FCO to Rome Centre", "Private Transfer — Rome Centre to FCO"),
    ("Unguided Visit", "Guided Visit"),
    ("Nonrefundable Rate", "Refundable Rate"),
    ("Rome City Tour SKU10041", "Rome City Tour SKU10042"),
    ("Vatican Museums — Skip the Line", "Vatican Museums — Skip the Line (Evening)"),
    ("Uffizi Gallery — Private Guided Tour", "Uffizi Gallery — Group Guided Tour"),
    ("Half Day City Tour", "Full Day City Tour"),
    ("Sunset Catamaran Cruise", "Sunrise Catamaran Cruise"),
    ("2 Hour Walking Tour", "4 Hour Walking Tour"),
    ("Transfer to Airport", "Transfer from Airport"),
    ("Uffizi Gallery private tour", "Uffizi Gallery — Private Guided Tour"),
]


@pytest.mark.parametrize("query, item_name", MUST_NOT_AUTO_ACCEPT)
def test_auto_accept_false_for_distinct_or_unconfirmed_pairs(query, item_name):
    catalog = [_item("X-1", item_name)]
    result = candidates(query, catalog, Aliases())
    assert result[0].auto_accept is False


def test_auto_accept_false_has_no_threshold_backdoor():
    # A pair that scores very high on similarity but is NOT identical after
    # normalisation, and was not confirmed via alias, must still be False —
    # confirming there is no score cutoff hiding in candidates().
    catalog = [_item("X-1", "Nonrefundable Rate")]
    result = candidates("Refundable Rate", catalog, Aliases())
    assert result[0].auto_accept is False


# Normalisation fix-round regression corpus: an unguarded plural rule
# (strip trailing "s" from any 4+ char token) and a punctuation rule that
# deleted every non-word character both used to make these pairs identical
# after normalisation, incorrectly auto-accepting a different service.
MUST_NOT_AUTO_ACCEPT_NORMALISATION_REGRESSIONS = [
    ("Rhodes Island Tour", "Rhode Island Tour"),
    ("Blues Cruise", "Blue Cruise"),
    ("The Baths Excursion", "The Bath Excursion"),
    ("Falls Foliage Tour", "Fall Foliage Tour"),
    ("Paros Day Trip", "Paro Day Trip"),
    ("Private Guides", "Private Guide"),
    ("Colosseum Tour *", "Colosseum Tour"),
    ("Colosseum Tour +", "Colosseum Tour"),
    ("Deposit 50%", "Deposit 50"),
    ("Tour €50", "Tour 50"),
]


@pytest.mark.parametrize("query, item_name", MUST_NOT_AUTO_ACCEPT_NORMALISATION_REGRESSIONS)
def test_auto_accept_false_for_normalisation_fix_round_regressions(query, item_name):
    catalog = [_item("X-1", item_name)]
    result = candidates(query, catalog, Aliases())
    assert result[0].auto_accept is False


# ---------------------------------------------------------------------------
# Ambiguity: normalisation making more than one catalog item identical to
# the query must never be broken by alphabetical item_id — ambiguity always
# goes to the operator.
# ---------------------------------------------------------------------------

def test_auto_accept_false_for_all_when_two_items_tie_after_normalisation():
    # Genuine duplicate catalog rows (e.g. a seasonal variant entered
    # twice) both normalise identical to the query. Without the ambiguity
    # guard, both would show auto_accept True and the alphabetically-first
    # item_id would silently win the tie-break — the wrong item could be
    # the one that gets auto-priced.
    catalog = [
        _item("DUP-B", "Sunset Catamaran Cruise"),
        _item("DUP-A", "Sunset Catamaran Cruise"),
    ]
    result = candidates("Sunset Catamaran Cruise", catalog, Aliases())
    assert len(result) == 2
    assert all(c.auto_accept is False for c in result)


def test_baths_bath_pair_no_longer_ties_after_normalisation_fix():
    # This pair was the reviewer's example of the ambiguity bug: under the
    # old unguarded plural rule, "Baths" folded to "bath" and both items
    # tied at auto_accept True, with the wrong one (B-1) winning the
    # item_id tie-break. The allowlist fix above means "Baths" no longer
    # folds, so there is no longer a tie to break: B-1 ("The Baths
    # Excursion", a different excursion) correctly does not auto-accept,
    # and B-2 ("The Bath Excursion"), which is a genuine exact match for
    # the query, correctly still does — that is the two-case auto_accept
    # rule working as designed, not a case the ambiguity guard needs to
    # touch.
    catalog = [
        _item("B-1", "The Baths Excursion"),
        _item("B-2", "The Bath Excursion"),
    ]
    result = candidates("The Bath Excursion", catalog, Aliases())
    by_id = {c.item_id: c for c in result}
    assert by_id["B-1"].auto_accept is False
    assert by_id["B-2"].auto_accept is True
    assert result[0].item_id == "B-2"


# ---------------------------------------------------------------------------
# Ranking: candidates() must put the right item first against plausible
# distractors. These are the matches she confirms with one keystroke, so a
# wrong item ranking first is the real failure mode now that score doesn't
# gate anything.
# ---------------------------------------------------------------------------

def test_rank_uffizi_private_tour_first():
    catalog = [
        _item("IT-1", "Uffizi Gallery — Private Guided Tour"),
        _item("IT-2", "Uffizi Gallery — Group Guided Tour"),
        _item("IT-3", "Vatican Museums — Skip the Line"),
    ]
    result = candidates("Uffizi Gallery private tour", catalog, Aliases())
    assert result[0].item_id == "IT-1"


def test_rank_colosseum_guided_tour_first():
    catalog = [
        _item("C-1", "Colosseum Guided Tour"),
        _item("C-2", "Colosseum Skip-the-Line Tour"),
        _item("C-3", "Roman Forum Guided Tour"),
    ]
    result = candidates("Guided tour of the Colosseum", catalog, Aliases())
    assert result[0].item_id == "C-1"


def test_rank_capri_boat_tour_first():
    catalog = [
        _item("B-1", "Capri Boat Tour"),
        _item("B-2", "Amalfi Boat Tour"),
        _item("B-3", "Capri Walking Tour"),
    ]
    result = candidates("Boat tour of Capri", catalog, Aliases())
    assert result[0].item_id == "B-1"


def test_rank_segway_city_centre_tour_first():
    catalog = [
        _item("S-1", "City Centre Segway Tour"),
        _item("S-2", "City Centre Walking Tour"),
        _item("S-3", "Segway Tour — Vatican Area"),
    ]
    result = candidates("Segway tours of the city centre", catalog, Aliases())
    assert result[0].item_id == "S-1"


def test_rank_tuscany_wine_tasting_tour_first():
    catalog = [
        _item("T-1", "Tuscany Wine Tasting Tour"),
        _item("T-2", "Cooking Class and Wine Tasting"),
        _item("T-3", "Tuscan Countryside Bicycle Tour"),
    ]
    result = candidates("Wine tasting Tuscany", catalog, Aliases())
    assert result[0].item_id == "T-1"


def test_rank_uffizi_private_guided_tour_first_despite_typo():
    catalog = [
        _item("IT-1", "Private Guided Tour — Uffizi Gallery"),
        _item("IT-2", "Group Guided Tour — Uffizi Gallery"),
        _item("IT-3", "Vatican Museums — Skip the Line"),
    ]
    result = candidates("Prvate guided tour of Uffizi", catalog, Aliases())
    assert result[0].item_id == "IT-1"


def test_rank_sunset_catamaran_open_bar_first():
    catalog = [
        _item("B-1", "Sunset Catamaran w/ Open Bar"),
        _item("B-2", "Full Day Boat Tour"),
        _item("B-3", "Aperitivo Cruise on the Bay"),
    ]
    result = candidates("Sunset catamaran cruise", catalog, Aliases())
    assert result[0].item_id == "B-1"


def test_rank_michelangelos_david_skip_the_line_first():
    catalog = [
        _item("M-1", "Skip the Line: Michelangelo's David"),
        _item("M-2", "Uffizi Gallery Skip the Line"),
        _item("M-3", "Michelangelo's David Guided Tour"),
    ]
    result = candidates("Michelangelo's David skip-the-line", catalog, Aliases())
    assert result[0].item_id == "M-1"


def test_rank_transfer_picks_correct_direction_first():
    # A prior version returned the wrong direction at a perfect 1.000.
    # Verify the correct direction ranks first even with a same-direction
    # distractor and the reverse-direction item both present.
    catalog = [
        _item("TR-AH", "Private Transfer — Airport to Hotel"),
        _item("TR-HA", "Private Transfer — Hotel to Airport"),
        _item("TR-OTHER", "Private Transfer — Airport to City Centre"),
    ]
    result = candidates("Private transfer from airport to hotel", catalog, Aliases())
    assert result[0].item_id == "TR-AH"


def test_rank_round_trip_airport_transfer_first():
    catalog = [
        _item("R-1", "Round-Trip Airport Transfer"),
        _item("R-2", "One-Way Airport Transfer"),
        _item("R-3", "Round Trip City Tour"),
    ]
    result = candidates("Round trip transfer to airport", catalog, Aliases())
    assert result[0].item_id == "R-1"


def test_rank_private_car_airport_pickup_first():
    catalog = [
        _item("P-1", "Private Car Airport Pickup"),
        _item("P-2", "Shared Shuttle Airport Pickup"),
        _item("P-3", "Private Car City Tour"),
    ]
    result = candidates("Airport pickup - private car", catalog, Aliases())
    assert result[0].item_id == "P-1"


def test_rank_small_group_walking_tour_rome_first():
    catalog = [
        _item("W-1", "Small Group Walking Tour — Rome"),
        _item("W-2", "Rome Walking Tour — Large Group"),
        _item("W-3", "Small Group Walking Tour — Florence"),
    ]
    result = candidates("Rome walking tour (small group)", catalog, Aliases())
    assert result[0].item_id == "W-1"


def test_rank_pompeii_day_trip_from_rome_first():
    catalog = [
        _item("D-1", "Day Trip to Pompeii from Rome"),
        _item("D-2", "Day Trip to Amalfi from Rome"),
        _item("D-3", "2-Day Rome and Pompeii Tour"),
    ]
    result = candidates("Pompeii day trip from Rome", catalog, Aliases())
    assert result[0].item_id == "D-1"


def test_rank_absent_item_never_auto_accepts():
    # The query's actual service simply isn't in the catalog. Whatever
    # candidates() returns as the closest guesses, none may auto-accept —
    # there is nothing to be identical to, and no alias was ever set.
    catalog = [
        _item("N-1", "Sunrise Catamaran Cruise"),
        _item("N-2", "Full Day Boat Tour"),
        _item("N-3", "Private Yacht Charter"),
    ]
    result = candidates("Segway Tour of the Colosseum", catalog, Aliases())
    assert len(result) > 0
    assert all(c.auto_accept is False for c in result)


# ---------------------------------------------------------------------------
# MUST NOT REGRESS: determinism
# ---------------------------------------------------------------------------

def test_determinism_same_ranking_across_runs():
    result_1 = candidates("tour", ITEMS, Aliases())
    result_2 = candidates("tour", ITEMS, Aliases())
    assert [c.item_id for c in result_1] == [c.item_id for c in result_2]
    assert [c.score for c in result_1] == [c.score for c in result_2]


def test_determinism_independent_of_insertion_order():
    forward = candidates("tour", ITEMS, Aliases())
    reversed_items = list(reversed(ITEMS))
    backward = candidates("tour", reversed_items, Aliases())
    assert [c.item_id for c in forward] == [c.item_id for c in backward]


def test_determinism_tie_break_by_item_id():
    tied = [
        _item("Z-1", "Boat Tour"),
        _item("A-1", "Boat Tour"),
        _item("M-1", "Boat Tour"),
    ]
    result = candidates("Boat Tour", tied, Aliases())
    assert [c.item_id for c in result] == ["A-1", "M-1", "Z-1"]


# ---------------------------------------------------------------------------
# MUST NOT REGRESS: degenerate inputs
# ---------------------------------------------------------------------------

def test_degenerate_empty_catalog():
    assert candidates("Uffizi Gallery private tour", [], Aliases()) == []


def test_degenerate_empty_query():
    result = candidates("", ITEMS, Aliases())
    assert isinstance(result, list)
    assert len(result) <= 3
    assert all(c.auto_accept is False for c in result)


def test_degenerate_pure_punctuation_query():
    result = candidates("!!! --- ...", ITEMS, Aliases())
    assert isinstance(result, list)
    assert len(result) <= 3


def test_degenerate_limit_zero():
    assert candidates("Uffizi Gallery private tour", ITEMS, Aliases(), limit=0) == []


def test_degenerate_limit_beyond_catalog_size():
    result = candidates("Uffizi Gallery private tour", ITEMS, Aliases(), limit=100)
    assert len(result) == len(ITEMS)


def test_returns_at_most_the_limit():
    assert len(candidates("tour", ITEMS, Aliases(), limit=2)) == 2


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------

def test_aliases_roundtrip_and_count_hits(tmp_path):
    aliases = Aliases()
    aliases.add("sunset catamaran", "GR-1")
    aliases.add("sunset catamaran", "GR-1")
    path = tmp_path / "aliases.json"
    aliases.save(path)
    reloaded = Aliases.load(path)
    assert reloaded.lookup("Sunset Catamaran") == "GR-1"
    assert reloaded.entries["sunset catamaran"]["hits"] == 2


def test_aliases_lookup_is_exact_key_on_normalised_phrase():
    aliases = Aliases()
    aliases.add("Half-Day City Tour", "H-1")
    assert aliases.lookup("half day city tour") == "H-1"
    assert aliases.lookup("Half Day City Tour!") == "H-1"
    assert aliases.lookup("Full Day City Tour") is None


def test_corrupted_aliases_json_returns_empty():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "aliases.json"
        path.write_text("{invalid json")
        aliases = Aliases.load(path)
        assert aliases.entries == {}
        assert aliases.load_error is not None
        assert "Corrupted" in aliases.load_error


# Syntactically valid JSON that is the wrong shape must degrade the same
# way, not crash on load or on the first lookup/add. `[1, 2, 3]` breaks
# `dict(entries)` in the constructor; the others raise inside `lookup()`
# when an entry is missing "id" or "hits" is not the expected type.
MALFORMED_BUT_VALID_JSON = [
    "[1, 2, 3]",
    '{"phrase": "GR-1"}',
    '{"phrase": {"hits": 2}}',
    '{"phrase": {"id": "GR-1"}}',
    '{"phrase": {"id": 5, "hits": 2}}',
    '{"phrase": {"id": "GR-1", "hits": "two"}}',
    '"just a string"',
    "42",
]


@pytest.mark.parametrize("raw_json", MALFORMED_BUT_VALID_JSON)
def test_structurally_malformed_aliases_json_degrades_without_crashing(raw_json):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "aliases.json"
        path.write_text(raw_json)
        aliases = Aliases.load(path)
        assert aliases.entries == {}
        assert aliases.load_error is not None
        # Must not crash on subsequent use either.
        assert aliases.lookup("anything") is None
        aliases.add("anything", "X-1")
        assert aliases.lookup("anything") == "X-1"


def test_alias_pointing_at_deleted_item_falls_through_to_scoring():
    aliases = Aliases()
    aliases.add("Uffizi Gallery private tour", "DELETED-ID")
    # DELETED-ID is not in the catalog; must not crash, must fall through
    # to ordinary scoring instead of raising or returning nothing useful.
    result = candidates("Uffizi Gallery private tour", ITEMS, aliases)
    assert result[0].item_id == "IT-1"
    assert result[0].reason == "name similarity"
    assert result[0].auto_accept is False
