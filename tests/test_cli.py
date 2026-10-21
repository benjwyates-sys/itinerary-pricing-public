"""Tests for pricing.cli — the only surface Claude talks to.

Every invocation must print exactly one JSON object to stdout and nothing
else, regardless of whether the underlying operation succeeded, failed with
a known error, or failed with something unexpected. These tests check both
the happy paths and that invariant.
"""

import json
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from pricing.catalog import fingerprint
from pricing.cli import main
from pricing.config import Config, save_config


def _run(capsys, argv):
    code = main(argv)
    raw = capsys.readouterr().out
    return code, json.loads(raw), raw


def test_doctor_reports_json(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "doctor"])
    assert code == 0 and out["ok"] is True
    # Task 12 added a fifth check (the settings-file check) alongside
    # config/python/openpyxl/workbook/data — do not shrink this back to 4.
    assert len(out["checks"]) == 5
    assert out["ok_all"] is True
    assert raw.count("\n") == 1  # exactly one line: the JSON object


def test_profile_writes_files_and_lists_sheets(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile",
                                   "--workbook", str(rate_sheet)])
    assert code == 0
    assert [s["name"] for s in out["sheets"]] == ["Italy", "Greece"]
    assert (tmp_path / "data" / "profiles" / "Italy.json").exists()
    assert (tmp_path / "data" / "profiles" / "Greece.json").exists()
    assert len(out["written"]) == 2
    assert raw.count("\n") == 1


def test_profile_never_leaks_cell_content(tmp_path, rate_sheet, capsys):
    """The profile artefact is structure-only — see pricing/profile.py's
    module docstring. Assert none of the actual rate-sheet text or numbers
    leak into the CLI's JSON output."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile",
                                   "--workbook", str(rate_sheet)])
    assert code == 0
    assert "Uffizi" not in raw
    assert "285" not in raw


def test_rows_returns_raw_values_for_mapping(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "rows",
                                   "--sheet", "Italy", "--from", "4", "--to", "5"])
    assert code == 0
    assert out["rows"][0]["values"][0] == "Uffizi Gallery — Private Guided Tour"
    assert out["rows"][1]["row"] == 5
    assert raw.count("\n") == 1


def test_rows_without_configured_workbook_is_friendly(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "rows",
                                   "--sheet", "Italy", "--from", "1", "--to", "2"])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()


# --- I2: a renamed/missing sheet gets a plain-English explanation --------
#
# Renaming a tab is the single most likely thing a non-technical operator
# does to her own workbook, and it used to fall through to the generic
# "something went wrong that I don't have a friendly explanation for" --
# no help at all for the one mistake she's most likely to make.
#
# Both messages below are asserted in full, not by substring: openpyxl
# raises KeyError("Worksheet <name> does not exist.") -- a whole sentence,
# not a bare name -- and a substring check on the old, unfixed code let a
# mangled message ("a sheet called 'Worksheet Italia does not exist.'")
# pass silently. Asserting the exact string is what catches that class of
# regression.

def test_rows_against_a_renamed_sheet_is_friendly(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "rows",
                                   "--sheet", "Italia", "--from", "4", "--to", "5"])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert out["error"] == (
        "I can't find a sheet called 'Italia' in your workbook. "
        "Check that the tab name hasn't changed, or run /profile "
        "again to re-read the workbook."
    )


def test_refresh_against_a_renamed_sheet_is_friendly(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    raw_wb = openpyxl.load_workbook(rate_sheet)
    raw_wb["Italy"].title = "Italia"   # the tab got renamed
    renamed = tmp_path / "renamed.xlsx"
    raw_wb.save(renamed)

    save_config(Config(root=tmp_path, costing_workbook=renamed))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "refresh"])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert out["error"] == (
        "I can't find a sheet called 'Italy' in your workbook. "
        "Check that the tab name hasn't changed, or run /profile "
        "again to re-read the workbook."
    )


def test_friendly_only_treats_a_genuine_worksheet_lookup_as_a_sheet_problem():
    """IMPORTANT regression (code review): the old `except KeyError` branch
    in _friendly treated EVERY KeyError as a missing-worksheet lookup and
    said so unconditionally. openpyxl's own KeyError for that case is
    always the sentence `KeyError("Worksheet <name> does not exist.")` --
    a bare KeyError with some other payload (a missing dict key, a role
    name) is a different problem entirely and must fall through to the
    honest generic message instead of a confidently false "I can't find a
    sheet called ..." pointing her at a tab that was never broken."""
    from pricing.cli import _friendly

    assert _friendly(KeyError("Worksheet Italia does not exist.")) == (
        "I can't find a sheet called 'Italia' in your workbook. "
        "Check that the tab name hasn't changed, or run /profile "
        "again to re-read the workbook."
    )

    generic = (
        "Something went wrong that I don't have a friendly explanation for. "
        "The details are saved in the runs folder — please send them on."
    )
    assert _friendly(KeyError("cost")) == generic
    assert _friendly(KeyError()) == generic


def test_cost_with_a_template_missing_the_cost_role_gets_the_generic_message(
        tmp_path, itinerary, rate_sheet, capsys):
    """End-to-end reproduction: a hand-edited (or otherwise corrupted)
    template.json whose `roles` dict is missing "cost" entirely still
    passes template_fits (it only checks columns for roles that ARE
    present) and gets used -- write_costed_workbook's
    `template.roles["cost"]` then raises a bare KeyError('cost') that has
    nothing to do with a worksheet. Before this fix she would have been
    told to check a tab name that was never the problem."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile-itinerary",
                                   "--file", str(itinerary)])
    assert code == 0

    template_path = tmp_path / "data" / "profiles" / "itinerary_template.json"
    data = json.loads(template_path.read_text(encoding="utf-8"))
    del data["roles"]["cost"]
    template_path.write_text(json.dumps(data), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost", "--file", str(itinerary)])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert "sheet" not in out["error"].lower()
    assert out["error"] == (
        "Something went wrong that I don't have a friendly explanation for. "
        "The details are saved in the runs folder — please send them on."
    )


def test_profile_itinerary_writes_template(tmp_path, itinerary, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile-itinerary",
                                   "--file", str(itinerary)])
    assert code == 0
    assert out["template"]["sheet"] == "Itinerary"
    assert out["template"]["roles"]["name"]
    assert out["template"]["roles"]["cost"]
    assert (tmp_path / "data" / "profiles" / "itinerary_template.json").exists()
    assert raw.count("\n") == 1


def test_catalog_add_persists(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    item = tmp_path / "item.json"
    item.write_text(json.dumps({
        "id": "IT-1", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")

    # C2 (code review): no fingerprints, so this must be explicit about
    # being unprotected -- see the dedicated fingerprint tests below.
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(item), "--unprotected"])
    assert code == 0 and out["id"] == "IT-1" and out["count"] == 1
    assert out["unprotected"] is True
    assert raw.count("\n") == 1


# --- C2: catalog-add requires fingerprints, or an explicit opt-out -------

def _unfingerprinted_item_json(**overrides) -> dict:
    payload = {
        "id": "IT-1", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": "", "confirmed_at": "2026-09-03",
    }
    payload.update(overrides)
    return payload


def test_catalog_add_refuses_item_without_fingerprints(tmp_path, capsys):
    """A well-formed item with no fingerprints is silently vulnerable to
    the sheet changing shape underneath it later -- catalog-add must
    refuse to save it without an explicit --unprotected, rather than the
    old behaviour of saving it unprotected by default."""
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "item.json"
    item.write_text(json.dumps(_unfingerprinted_item_json()), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 1
    assert out["ok"] is False
    assert "IT-1" in out["error"]
    assert "--unprotected" in out["error"]
    assert not (tmp_path / "data" / "catalog.json").exists()


def test_catalog_add_succeeds_with_real_fingerprints(tmp_path, rate_sheet, capsys):
    """The realistic path: both fingerprints computed against the live
    workbook, the way map-rate-sheet/SKILL.md's step 5 does it -- no
    --unprotected needed, and the result does not claim it's unprotected."""
    from pricing.catalog import CatalogItem, compute_structure_fingerprint
    from pricing.workbook import Workbook as _Workbook

    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))

    wb = _Workbook(rate_sheet)
    row_fp = fingerprint("Vatican Museums — Skip the Line")
    structure_fp = compute_structure_fingerprint(
        wb, CatalogItem(
            id="IT-1", name="Vatican Museums — Skip the Line",
            name_cell="Italy!A6", region="Italy", currency="EUR",
            unit="per_person",
            pricing={"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
            source_rows=[6]))
    wb.close()

    item = tmp_path / "item.json"
    item.write_text(json.dumps(_unfingerprinted_item_json(
        row_fingerprint=row_fp, structure_fingerprint=structure_fp)), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 0
    assert out["id"] == "IT-1" and out["count"] == 1
    assert "unprotected" not in out


def test_catalog_add_unprotected_flag_works_and_is_reported(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "item.json"
    item.write_text(json.dumps(_unfingerprinted_item_json()), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(item), "--unprotected"])
    assert code == 0
    assert out["ok"] is True
    assert out["unprotected"] is True
    catalog = json.loads((tmp_path / "data" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["items"][0]["id"] == "IT-1"


def test_catalog_add_invalid_json_is_friendly(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "broken.json"
    item.write_text("{not valid json", encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()


def test_catalog_add_rejects_malformed_pricing_cell(tmp_path, capsys):
    """/map is an AI writing these entries, so a malformed cell reference
    is the expected failure mode -- it must be rejected here, before it
    ever reaches catalog.json, not surface as a cryptic error deep inside
    a later costing run."""
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "item.json"
    item.write_text(json.dumps({
        "id": "IT-BAD-1", "name": "Broken Pricing Cell",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "NOT-A-CELL-REF", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 1
    assert out["ok"] is False
    assert "pricing.cell" in out["error"]
    assert "NOT-A-CELL-REF" in out["error"]
    assert not (tmp_path / "data" / "catalog.json").exists()


def test_catalog_add_rejects_malformed_tier_cell(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "item.json"
    item.write_text(json.dumps({
        "id": "IT-BAD-2", "name": "Broken Tier Cell",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "NOT-A-CELL-REF", "last_seen": "240"}]},
        "modifiers": [], "source_rows": [4, 5],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 1
    assert out["ok"] is False
    assert "pricing.tiers[1].cell" in out["error"]
    assert "NOT-A-CELL-REF" in out["error"]
    assert not (tmp_path / "data" / "catalog.json").exists()


def test_catalog_add_rejects_malformed_modifier_cell(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    item = tmp_path / "item.json"
    item.write_text(json.dumps({
        "id": "IT-BAD-3", "name": "Broken Modifier Cell",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D4", "last_seen": "285"},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                        "cell": "NOT-A-CELL-REF", "last_seen": "40"}],
        "source_rows": [4],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 1
    assert out["ok"] is False
    assert "modifiers[0].cell" in out["error"]
    assert "NOT-A-CELL-REF" in out["error"]
    assert not (tmp_path / "data" / "catalog.json").exists()


# --- catalog-add id collisions (Task 15 review, fixed in Task 16) ---
#
# Catalog.upsert() silently REPLACES on an id collision. /map is an AI
# minting ids across sessions, so a reused id is a realistic way to destroy
# a previously confirmed, fingerprinted entry with no warning anywhere. The
# CLI must refuse a colliding save unless the content is identical (a
# harmless, idempotent re-add) or the caller passes --replace to say the
# overwrite is deliberate.

def _vatican_item_json(**overrides) -> dict:
    payload = {
        "id": "IT-1", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": "", "confirmed_at": "2026-09-03",
    }
    payload.update(overrides)
    return payload


def test_catalog_add_refuses_id_collision_with_different_content(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    first = tmp_path / "first.json"
    first.write_text(json.dumps(_vatican_item_json()), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(first), "--unprotected"])
    assert code == 0 and out["count"] == 1

    before = (tmp_path / "data" / "catalog.json").read_text(encoding="utf-8")

    # Same id, different content -- a different item entirely (e.g. the
    # model reused an id it had already used for something else).
    second = tmp_path / "second.json"
    second.write_text(json.dumps(_vatican_item_json(
        name="Colosseum — Underground Tour", name_cell="Italy!A7",
        pricing={"pattern": "flat", "cell": "Italy!D7", "last_seen": "110"},
    )), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(second), "--unprotected"])
    assert code == 1
    assert out["ok"] is False
    assert "IT-1" in out["error"]
    assert "--replace" in out["error"]
    assert "traceback" not in out["error"].lower()

    # The original mapping must be completely untouched.
    assert (tmp_path / "data" / "catalog.json").read_text(encoding="utf-8") == before


def test_catalog_add_replace_flag_overwrites_and_reports_it(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    first = tmp_path / "first.json"
    first.write_text(json.dumps(_vatican_item_json()), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(first), "--unprotected"])
    assert code == 0 and out["count"] == 1

    second = tmp_path / "second.json"
    second.write_text(json.dumps(_vatican_item_json(
        name="Colosseum — Underground Tour", name_cell="Italy!A7",
        pricing={"pattern": "flat", "cell": "Italy!D7", "last_seen": "110"},
    )), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(second), "--replace", "--unprotected"])
    assert code == 0
    assert out["ok"] is True
    assert out["replaced"] is True
    assert out["count"] == 1  # still one item -- replaced, not appended

    catalog = json.loads((tmp_path / "data" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["items"][0]["name"] == "Colosseum — Underground Tour"


def test_catalog_add_identical_re_add_succeeds_without_replace(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    first = tmp_path / "first.json"
    first.write_text(json.dumps(_vatican_item_json()), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(first), "--unprotected"])
    assert code == 0 and out["count"] == 1

    # Byte-for-byte the same content, saved again (e.g. a re-run after a
    # dropped connection) -- nothing changed, so nothing to refuse.
    again = tmp_path / "again.json"
    again.write_text(json.dumps(_vatican_item_json()), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(again), "--unprotected"])
    assert code == 0
    assert out["ok"] is True
    assert out["count"] == 1
    assert "replaced" not in out


def test_cost_prices_writes_workbook_and_serialises_decimal_as_string(
        tmp_path, itinerary, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))

    uffizi_item = tmp_path / "uffizi.json"
    uffizi_item.write_text(json.dumps({
        "id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR", "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                        "cell": "Italy!F4", "last_seen": "40"}],
        "source_rows": [4, 5],
        "row_fingerprint": fingerprint("Uffizi Gallery — Private Guided Tour"),
        "confirmed_at": "2026-09-03"}), encoding="utf-8")

    vatican_item = tmp_path / "vatican.json"
    vatican_item.write_text(json.dumps({
        "id": "IT-ROM-0001", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR", "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": fingerprint("Vatican Museums — Skip the Line"),
        "confirmed_at": "2026-09-03"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(uffizi_item), "--unprotected"])
    assert code == 0 and out["count"] == 1
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(vatican_item), "--unprotected"])
    assert code == 0 and out["count"] == 2

    # "Uffizi Gallery private tour" (itinerary phrasing) is NOT identical to
    # the catalog's phrasing after normalisation (see pricing/match.py's
    # module docstring), so it needs an explicit operator resolution — via
    # a file, per the "arguments are always paths" rule.
    resolutions = tmp_path / "resolutions.json"
    resolutions.write_text(json.dumps({"8": "IT-FLR-0032"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(itinerary),
                                   "--resolutions", str(resolutions)])
    assert code == 0
    assert out["ok"] is True
    assert raw.count("\n") == 1

    assert out["summary"]["priced"] == 2
    assert out["summary"]["unmatched"] == 1
    assert out["summary"]["totals_by_currency"]["EUR"] == "1680.00"

    uffizi_line = next(l for l in out["lines"] if l["row"] == 8)
    assert uffizi_line["status"] == "priced"
    assert uffizi_line["total"] == "1300.00"  # Decimal serialised losslessly as a string
    assert isinstance(uffizi_line["total"], str)

    vatican_line = next(l for l in out["lines"] if l["row"] == 9)
    assert vatican_line["status"] == "priced"
    assert vatican_line["total"] == "380.00"

    assert Path(out["output"]).exists()
    assert Path(out["output"]).name != Path(itinerary).name  # never overwrites the original
    assert Path(out["run_log"]).exists()

    # The original itinerary is untouched.
    logged = json.loads(Path(out["run_log"]).read_text(encoding="utf-8"))
    assert logged["output"] == out["output"]


# --- C3(b): a stale saved template must not silently misalign a
# differently-shaped file ---------------------------------------------
#
# data/profiles/itinerary_template.json is a single global file, reused
# for every itinerary /cost is ever pointed at. Reproduced by the review:
# saving a template from the flat `itinerary` fixture (header row 7) and
# then costing the differently-shaped `day_grouped_itinerary` (header row
# 5, day headings interleaved) with it silently priced only 1 of 2 real
# lines and dropped the other -- no error, no warning. `_cost` must detect
# that the saved template does not fit this file and fall back to a fresh
# proposal for it instead.

def test_stale_template_falls_back_instead_of_dropping_lines(
        tmp_path, day_grouped_itinerary, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))

    # Profile a template from a DIFFERENTLY-SHAPED itinerary and save it
    # as the global template -- this is the stale state the review found.
    from tests.fixtures import build
    flat_itinerary = build.build_itinerary(tmp_path / "Trip_Flat.xlsx")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile-itinerary",
                                   "--file", str(flat_itinerary)])
    assert code == 0 and out["template"]["header_row"] == 7

    uffizi_item = tmp_path / "uffizi.json"
    uffizi_item.write_text(json.dumps({
        "id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR", "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                        "cell": "Italy!F4", "last_seen": "40"}],
        "source_rows": [4, 5],
        "row_fingerprint": fingerprint("Uffizi Gallery — Private Guided Tour"),
        "confirmed_at": "2026-09-03"}), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(uffizi_item), "--unprotected"])
    assert code == 0

    vatican_item = tmp_path / "vatican.json"
    vatican_item.write_text(json.dumps({
        "id": "IT-ROM-0001", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR", "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": fingerprint("Vatican Museums — Skip the Line"),
        "confirmed_at": "2026-09-03"}), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(vatican_item), "--unprotected"])
    assert code == 0

    # Now cost the DAY-GROUPED itinerary (header row 5) WITHOUT ever
    # re-running /profile-itinerary for it -- the stale template from the
    # flat itinerary is all that's on file.
    resolutions = tmp_path / "resolutions.json"
    resolutions.write_text(json.dumps({"7": "IT-FLR-0032"}), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(day_grouped_itinerary),
                                   "--resolutions", str(resolutions)])
    assert code == 0

    # Both real lines must be priced -- neither the Uffizi line (row 7)
    # nor the Vatican line (row 9) may silently vanish.
    assert out["summary"]["priced"] == 2
    uffizi_line = next(l for l in out["lines"] if l["row"] == 7)
    assert uffizi_line["status"] == "priced"
    assert uffizi_line["total"] == "1300.00"
    vatican_line = next(l for l in out["lines"] if l["row"] == 9)
    assert vatican_line["status"] == "priced"
    assert vatican_line["total"] == "380.00"


# --- C4: default_pax can be set, and a low-confidence template refuses
# to run silently empty -----------------------------------------------

def test_cost_refuses_when_no_pax_column_and_no_default(tmp_path, wide_itinerary, rate_sheet, capsys):
    """wide_itinerary states the party size once for the whole trip, not
    per line -- propose_template finds no pax column (confidence "low"),
    and without a default_pax the ONLY thing parse_itinerary can do is
    drop every single line. Reproduced by the review: a completely empty
    quote, no error, no warning. Must refuse instead."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost", "--file", str(wide_itinerary)])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert "party size" in out["error"].lower() or "party-size" in out["error"].lower()


def test_cost_default_pax_flag_fixes_the_wide_itinerary(tmp_path, wide_itinerary, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(wide_itinerary), "--default-pax", "4"])
    assert code == 0
    assert out["ok"] is True
    # Both lines now have a party size and are at least attempted (not
    # silently dropped) -- neither is "unmatched with 0 candidates from an
    # empty parse", they're real unmatched-with-candidates lines.
    assert len(out["lines"]) == 2
    assert out["summary"]["priced"] + out["summary"]["needs_quote"] + \
        out["summary"]["unmatched"] == 2


def test_profile_itinerary_no_longer_accepts_default_pax(tmp_path, wide_itinerary, capsys):
    """CRITICAL regression (code review): --default-pax used to live on
    `profile-itinerary` too, persisting a party size into the single
    global data/profiles/itinerary_template.json -- a template describes
    a SHAPE and is deliberately reused across files with different
    identities (see test_template_fits_the_same_shape_reused_on_a_different_file),
    but a party size is data about one client's booking. The flag is
    removed from this subcommand entirely; the only place it can be
    given now is `cost`, for one run."""
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile-itinerary",
                                   "--file", str(wide_itinerary), "--default-pax", "4"])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    # argparse rejects the unknown flag before anything runs -- no
    # template.json is written at all, let alone one carrying a pax value.
    assert not (tmp_path / "data" / "profiles" / "itinerary_template.json").exists()


def test_second_clients_itinerary_never_inherits_the_first_clients_party_size(
        tmp_path, rate_sheet, capsys):
    """The reviewer's exact regression, end to end through the CLI:
    Trip A's itinerary states its party size once for the whole trip (no
    pax column -- confidence "low"), so it's costed with
    `--default-pax 2`. Trip B is a DIFFERENT client's itinerary, laid out
    exactly the same way (same shape -- template_fits matches on shape,
    not identity, deliberately), but its real party size is 4. Before the
    fix, `profile-itinerary --default-pax` persisted Trip A's 2 into the
    single global template.json, and costing Trip B with no --default-pax
    of its own silently reused it: `ok: true`, `status: "priced"`,
    total "190.00" (95 x 2) instead of the correct "380.00" (95 x 4), no
    warning anywhere. Trip B must now either refuse for want of its own
    --default-pax, or price correctly when one is actually given for that
    run -- never Trip A's number."""
    from tests.fixtures import build

    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    vatican = tmp_path / "vatican.json"
    vatican.write_text(json.dumps(_vatican_item_json()), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(vatican), "--unprotected"])
    assert code == 0

    trip_a = build.build_wide_itinerary(tmp_path / "Trip_A.xlsx")   # party size 2
    trip_b = build.build_wide_itinerary(tmp_path / "Trip_B.xlsx")   # different client, same shape, party size 4

    # Profiling and costing Trip A never touches the saved template's
    # default_pax -- profile-itinerary no longer accepts the flag at all,
    # and cost's --default-pax is this-run-only.
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile-itinerary", "--file", str(trip_a)])
    assert code == 0 and out["template"]["default_pax"] is None

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(trip_a), "--default-pax", "2"])
    assert code == 0
    vatican_a = next(l for l in out["lines"] if l["raw_name"] == "Vatican Museums skip the line")
    assert vatican_a["status"] == "priced"
    assert vatican_a["total"] == "190.00"   # 95 x 2 -- correct for Trip A

    saved = json.loads((tmp_path / "data" / "profiles" / "itinerary_template.json")
                        .read_text(encoding="utf-8"))
    assert saved["default_pax"] is None   # Trip A's 2 was never written back

    # Trip B, costed with no --default-pax of its own: must refuse, not
    # silently reuse Trip A's 2.
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost", "--file", str(trip_b)])
    assert code == 1
    assert out["ok"] is False
    assert "party size" in out["error"].lower() or "party-size" in out["error"].lower()

    # And when Trip B's own party size (4) is supplied for that run, it
    # prices correctly on its own number -- never on Trip A's.
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(trip_b), "--default-pax", "4"])
    assert code == 0
    vatican_b = next(l for l in out["lines"] if l["raw_name"] == "Vatican Museums skip the line")
    assert vatican_b["status"] == "priced"
    assert vatican_b["total"] == "380.00"   # 95 x 4 -- Trip B's own party size, not Trip A's 2


def test_cost_on_a_normal_itinerary_is_unaffected_by_the_default_pax_guard(
        tmp_path, itinerary, rate_sheet, capsys):
    """A normal itinerary has a real pax column (confidence "high"), so
    the new guard must never fire for it -- no --default-pax needed."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost", "--file", str(itinerary)])
    assert code == 0
    assert out["ok"] is True


def test_cost_without_configured_workbook_is_friendly(tmp_path, itinerary, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost", "--file", str(itinerary)])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()


# --- I3: a corrupted aliases.json is surfaced, never destroyed -----------
#
# Aliases.load() already degrades a corrupted file to an empty in-memory
# store with load_error set (pricing/match.py). The bug was that `cost`
# called aliases.save() unconditionally afterwards -- silently overwriting
# the broken file with `{}` and permanently destroying every confirmation
# the operator has ever made, reported back as `ok: true` with nothing to
# say about it.

def test_corrupted_aliases_file_produces_a_warning_and_is_never_overwritten(
        tmp_path, itinerary, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    aliases_path = tmp_path / "data" / "aliases.json"
    aliases_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_bytes = b"{not valid json at all"
    aliases_path.write_bytes(corrupt_bytes)

    resolutions = tmp_path / "resolutions.json"
    resolutions.write_text(json.dumps({"8": "IT-FLR-0032"}), encoding="utf-8")

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "cost",
                                   "--file", str(itinerary),
                                   "--resolutions", str(resolutions)])
    assert code == 0
    assert out["ok"] is True

    # The line still priced normally -- a corrupted alias store degrades
    # to "no saved aliases", not a hard failure.
    uffizi_line = next(l for l in out["lines"] if l["row"] == 8)
    assert uffizi_line["status"] == "priced"

    # A warning names the problem...
    assert any("confirmation" in w.lower() or "alias" in w.lower()
               for w in out["summary"]["warnings"])

    # ...and the original file is completely untouched, byte for byte --
    # not overwritten with `{}`, not renamed away, just left alone so it
    # can still be recovered or repaired.
    assert aliases_path.exists()
    assert aliases_path.read_bytes() == corrupt_bytes


def _add_uffizi_item(tmp_path, capsys):
    item = tmp_path / "uffizi.json"
    item.write_text(json.dumps({
        "id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR", "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                        "cell": "Italy!F4", "last_seen": "40"}],
        "source_rows": [4, 5],
        "row_fingerprint": fingerprint("Uffizi Gallery — Private Guided Tour"),
        "confirmed_at": "2026-09-03"}), encoding="utf-8")
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "catalog-add",
                                   "--file", str(item), "--unprotected"])
    assert code == 0 and out["ok"] is True


def test_verify_cli_reports_a_match(tmp_path, itinerary, rate_sheet, capsys):
    """`verify` re-costs a trip she already priced by hand and diffs it --
    the only acceptance test that can exist, since the real spreadsheets
    never leave her machine. Exercised end-to-end through the CLI JSON
    contract, not just pricing.verify directly."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    raw_wb = openpyxl.load_workbook(itinerary)
    raw_wb["Itinerary"]["E8"] = 1300
    hand = tmp_path / "hand.xlsx"
    raw_wb.save(hand)

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "verify", "--file", str(hand)])
    assert code == 0 and out["ok"] is True
    assert out["summary"]["matches"] == 1
    row8 = next(d for d in out["diffs"] if d["row"] == 8)
    assert row8["status"] == "match"
    assert raw.count("\n") == 1


def test_verify_cli_reports_a_mismatch_with_delta(tmp_path, itinerary, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    raw_wb = openpyxl.load_workbook(itinerary)
    raw_wb["Itinerary"]["E8"] = 1250
    hand = tmp_path / "hand.xlsx"
    raw_wb.save(hand)

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "verify", "--file", str(hand)])
    assert code == 0 and out["ok"] is True
    row8 = next(d for d in out["diffs"] if d["row"] == 8)
    assert row8["status"] == "mismatch"
    assert row8["delta"] == "50.00"  # Decimal serialised as a string, never a float
    assert out["summary"]["mismatches"] == 1


def test_verify_without_configured_workbook_is_friendly(tmp_path, itinerary, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "verify", "--file", str(itinerary)])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert raw.count("\n") == 1


def test_refresh_cli_separates_price_changes_from_broken_items(tmp_path, rate_sheet, capsys):
    """A PRICE CHANGE is informational (the catalog reads live cells, so
    quotes are already correct); a BROKEN ITEM cannot be priced until
    re-mapped. They must never be mixed into one list."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    raw_wb = openpyxl.load_workbook(rate_sheet)
    raw_wb["Italy"]["D4"] = 310
    changed = tmp_path / "changed.xlsx"
    raw_wb.save(changed)

    save_config(Config(root=tmp_path, costing_workbook=changed))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "refresh"])
    assert code == 0 and out["ok"] is True
    assert out["checked"] == 1
    assert out["broken_items"] == []
    assert out["price_changes"][0]["id"] == "IT-FLR-0032"
    assert out["price_changes"][0]["now"] == "310"
    assert out["price_changes"][0]["was"] == "285"
    assert raw.count("\n") == 1


def test_refresh_cli_reports_broken_items_separately_from_price_changes(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)

    raw_wb = openpyxl.load_workbook(rate_sheet)
    raw_wb["Italy"].insert_rows(4)
    raw_wb["Italy"]["A4"] = "Colosseum — Underground Tour"
    shifted = tmp_path / "shifted.xlsx"
    raw_wb.save(shifted)

    save_config(Config(root=tmp_path, costing_workbook=shifted))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "refresh"])
    assert code == 0 and out["ok"] is True
    assert out["price_changes"] == []
    assert out["broken_items"][0]["id"] == "IT-FLR-0032"


def test_refresh_lists_unprotected_items_separately(tmp_path, rate_sheet, capsys):
    """C2 (code review): an item with no fingerprints is silently exposed
    to structural drift. It resolves rates just fine right now (nothing
    broken, no price change) but /refresh must still call it out, in its
    own list -- distinct from broken_items (cannot price at all) and
    price_changes (purely informational)."""
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    _add_uffizi_item(tmp_path, capsys)   # saved via --unprotected, no structure_fingerprint

    code, out, raw = _run(capsys, ["--root", str(tmp_path), "refresh"])
    assert code == 0 and out["ok"] is True
    assert out["broken_items"] == []
    assert out["unprotected_items"] == [
        {"id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour"}
    ]


def test_refresh_without_configured_workbook_is_friendly(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "refresh"])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert raw.count("\n") == 1


def test_errors_are_plain_english_json(tmp_path, capsys):
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile",
                                   "--workbook", str(tmp_path / "missing.xlsx")])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
    assert raw.count("\n") == 1


def test_uncaught_exception_writes_traceback_to_runs_dir(tmp_path, capsys):
    save_config(Config(root=tmp_path, costing_workbook=None))
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile",
                                   "--workbook", str(tmp_path / "missing.xlsx")])
    assert code == 1
    assert (tmp_path / "data" / "runs" / "last-error.txt").exists()
    log_text = (tmp_path / "data" / "runs" / "last-error.txt").read_text(encoding="utf-8")
    assert "Traceback" in log_text  # the real traceback lives in the file, not stdout


def test_bad_arguments_still_produce_a_single_json_object(tmp_path, capsys):
    """Even a malformed invocation (a missing/unknown flag) must never let
    argparse print usage text to stderr and exit without JSON on stdout —
    the AI parses stdout, so this path has to stay inside the JSON contract
    too."""
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "profile"])  # missing --workbook
    assert code == 1
    assert out["ok"] is False
    assert raw.count("\n") == 1


def test_unknown_subcommand_produces_a_single_json_object(tmp_path, capsys):
    code, out, raw = _run(capsys, ["--root", str(tmp_path), "not-a-real-command"])
    assert code == 1
    assert out["ok"] is False
    assert raw.count("\n") == 1
