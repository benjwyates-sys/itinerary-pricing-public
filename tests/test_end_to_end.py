"""The full journey, exercised the way the skills exercise it: CLI only.

Every skill talks to the engine exclusively through `pricing.cli.main`,
parsing one line of JSON per call -- so that is exactly how this test talks
to it too. It walks profile -> profile-itinerary -> map (catalog-add) ->
cost -> refresh -> verify -> doctor, the same order the commands are meant
to be run in, and checks the numbers the operator would actually see.

The second test guards this project's single most important safety
property: whatever else `/cost` does, the operator's original itinerary
file must come out byte-for-byte identical to how it went in. Every write
in this system lands on a copy (see pricing/workbook.py's copy_for_write
and pricing/report.py's module docstring) -- this test is the end-to-end
proof that the promise holds all the way from the CLI down.
"""

from __future__ import annotations

import json

from pricing.catalog import fingerprint
from pricing.cli import main


def _run(capsys, argv):
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def _uffizi_item_json() -> dict:
    return {
        "id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                       "cell": "Italy!F4", "last_seen": "40"}],
        "source_rows": [4, 5],
        "row_fingerprint": fingerprint("Uffizi Gallery — Private Guided Tour"),
        "confirmed_at": "2026-09-03",
    }


def test_profile_map_cost_refresh_verify_doctor(tmp_path, rate_sheet, itinerary, capsys):
    root = ["--root", str(tmp_path)]

    # /profile -- reads the costing workbook's structure and remembers where
    # it lives, for every later command that needs it.
    code, out = _run(capsys, root + ["profile", "--workbook", str(rate_sheet)])
    assert code == 0
    assert [s["name"] for s in out["sheets"]] == ["Italy", "Greece"]

    # /profile-itinerary -- learns which column in this itinerary layout is
    # the cost column /cost will fill in.
    code, out = _run(capsys, root + ["profile-itinerary", "--file", str(itinerary)])
    assert code == 0
    assert out["template"]["roles"]["cost"] == "E"

    # /map -- one confirmed catalog entry, written the way the mapping
    # skill writes it (see .claude/skills/map-rate-sheet/SKILL.md).
    item = tmp_path / "uffizi.json"
    item.write_text(json.dumps(_uffizi_item_json()), encoding="utf-8")
    code, out = _run(capsys, root + ["catalog-add", "--file", str(item), "--unprotected"])
    assert code == 0
    assert out["id"] == "IT-FLR-0032"
    assert out["count"] == 1

    # /cost -- the itinerary's phrasing ("Uffizi Gallery private tour") is
    # NOT identical to the catalog's ("Uffizi Gallery — Private Guided
    # Tour") after normalisation (pricing/match.py), so there is no
    # threshold that would auto-accept it -- an explicit operator
    # resolution is required the first time. This also seeds an alias, so
    # the same phrasing prices itself silently from here on.
    resolutions = tmp_path / "resolutions.json"
    resolutions.write_text(json.dumps({"8": "IT-FLR-0032"}), encoding="utf-8")
    code, out = _run(capsys, root + ["cost", "--file", str(itinerary),
                                      "--resolutions", str(resolutions)])
    assert code == 0
    assert out["summary"]["priced"] == 1
    assert out["summary"]["unmatched"] == 2

    uffizi = next(l for l in out["lines"] if l["row"] == 8)
    assert uffizi["status"] == "priced"
    # Decimal serialises losslessly as a string, never a float -- (285 + 40
    # PM supplement) x 4 pax = 1300.00.
    assert uffizi["total"] == "1300.00"
    assert isinstance(uffizi["total"], str)

    costed_copy = out["output"]

    # /refresh -- sweeps the one confirmed item against the live rate
    # sheet; nothing has moved, so nothing to report.
    code, out = _run(capsys, root + ["refresh"])
    assert code == 0
    assert out["checked"] == 1
    assert out["price_changes"] == []
    assert out["broken_items"] == []

    # /verify -- re-costs the costed copy and diffs it against the cost
    # column /cost just wrote. Row 8 now resolves via the alias /cost
    # seeded a moment ago, so it comes back as a confident match; rows 9
    # and 10 were never mapped, so their cost cells hold "NOT MATCHED --"
    # text rather than a number -- nothing to compare against.
    code, out = _run(capsys, root + ["verify", "--file", costed_copy])
    assert code == 0
    row8 = next(d for d in out["diffs"] if d["row"] == 8)
    assert row8["status"] == "match"
    assert row8["match_confidence"] == "auto_accept"
    assert row8["item_id"] == "IT-FLR-0032"
    assert out["summary"]["matches"] == 1
    assert out["summary"]["no_expected"] == 2

    # /doctor -- last thing the operator runs when everything is set up:
    # settings, Python, openpyxl, the workbook, and the data folder all
    # check out.
    code, out = _run(capsys, root + ["doctor"])
    assert code == 0
    assert out["ok_all"] is True
    assert len(out["checks"]) == 5


def test_original_itinerary_is_never_modified(tmp_path, rate_sheet, itinerary, capsys):
    before = itinerary.read_bytes()
    root = ["--root", str(tmp_path)]

    _run(capsys, root + ["profile", "--workbook", str(rate_sheet)])
    _run(capsys, root + ["profile-itinerary", "--file", str(itinerary)])

    item = tmp_path / "uffizi.json"
    item.write_text(json.dumps(_uffizi_item_json()), encoding="utf-8")
    _run(capsys, root + ["catalog-add", "--file", str(item), "--unprotected"])

    resolutions = tmp_path / "resolutions.json"
    resolutions.write_text(json.dumps({"8": "IT-FLR-0032"}), encoding="utf-8")
    _run(capsys, root + ["cost", "--file", str(itinerary),
                          "--resolutions", str(resolutions)])

    _run(capsys, root + ["verify", "--file", str(itinerary)])

    assert itinerary.read_bytes() == before
