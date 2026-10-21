"""The only surface Claude talks to. One JSON object per invocation.

An AI assistant runs every one of these commands via Bash and parses stdout
as JSON. That is the whole contract, so it is enforced everywhere in this
module: exactly one line, exactly one JSON object, on every path — success,
a known/friendly failure, or something completely unexpected.

Nothing here decides a price or reads a rate; it only wires the other
`pricing` modules together and translates their results (and their
failures) into that one JSON object. In particular: `pricing/match.py` was
redesigned, after three failed tuning rounds, so that a similarity score
never gates a pricing decision — only `Candidate.auto_accept` does, and
`pricing/cost.py` already honours that. This module must never re-introduce
a score threshold of its own; it just calls `price_lines` and reports what
comes back.
"""

from __future__ import annotations

import argparse
import json
import traceback
from datetime import date
from pathlib import Path

from pricing import profile as profile_mod
from pricing.catalog import Catalog, CatalogItem
from pricing.config import Config, load_config, save_config
from pricing.cost import parse_itinerary, price_lines
from pricing.doctor import run_checks
from pricing.itinerary_profile import (
    ItineraryTemplate,
    MissingRoleError,
    load_template,
    propose_template,
    save_template,
    template_fits,
)
from pricing.match import Aliases
from pricing.report import summarize, write_costed_workbook, write_run_log
from pricing.workbook import CellRef, Workbook, WorkbookLockedError, missing_sheet_name


class ConfigurationError(Exception):
    """A setup problem this module already knows how to explain.

    Unlike a bare exception caught at the top level, the message here is
    already the plain-English text shown to the operator — _friendly()
    passes it through unchanged.
    """


class _ArgumentParsingError(Exception):
    """Raised in place of argparse's default sys.exit(2)+stderr behaviour.

    argparse's default error path prints usage text to stderr and calls
    sys.exit(2) directly, bypassing our try/except and — more importantly —
    printing nothing to stdout at all. The AI assistant only ever reads
    stdout, so a malformed invocation (an unknown flag, a missing required
    argument, a bad subcommand) has to stay inside the same one-JSON-object
    contract as every other failure, not fall outside it.
    """


class _JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # noqa: D102 — matches base signature
        raise _ArgumentParsingError(message)


def main(argv: list[str] | None = None) -> int:
    config: Config | None = None
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        config = load_config(Path(args.root) if args.root else None)
        payload = _dispatch(args, config)
    except Exception as exc:  # noqa: BLE001 — the boundary converts everything
        _log_traceback(config)
        print(json.dumps({"ok": False, "error": _friendly(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **payload}, ensure_ascii=False, default=str))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = _JSONArgumentParser(prog="pricing")
    parser.add_argument("--root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")

    p = sub.add_parser("profile")
    p.add_argument("--workbook", required=True)

    p = sub.add_parser("rows")
    p.add_argument("--sheet", required=True)
    p.add_argument("--from", dest="start", type=int, required=True)
    p.add_argument("--to", dest="end", type=int, required=True)

    p = sub.add_parser("profile-itinerary")
    p.add_argument("--file", required=True)

    p = sub.add_parser("catalog-add")
    p.add_argument("--file", required=True)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--unprotected", action="store_true")

    p = sub.add_parser("cost")
    p.add_argument("--file", required=True)
    p.add_argument("--resolutions")
    p.add_argument("--default-pax", type=int)

    p = sub.add_parser("verify")
    p.add_argument("--file", required=True)

    sub.add_parser("refresh")

    return parser


def _dispatch(args: argparse.Namespace, config: Config) -> dict:
    if args.command == "doctor":
        return _doctor(config)
    if args.command == "profile":
        return _profile(args, config)
    if args.command == "rows":
        return _rows(args, config)
    if args.command == "profile-itinerary":
        return _profile_itinerary(args, config)
    if args.command == "catalog-add":
        return _catalog_add(args, config)
    if args.command == "cost":
        return _cost(args, config)
    if args.command == "verify":
        return _verify(args, config)
    if args.command == "refresh":
        return _refresh(config)
    raise ValueError(f"unknown command {args.command!r}")


def _doctor(config: Config) -> dict:
    checks = run_checks(config)
    return {"ok_all": all(c.ok for c in checks),
            "checks": [vars(c) for c in checks]}


def _profile(args: argparse.Namespace, config: Config) -> dict:
    workbook_path = Path(args.workbook)
    wb = Workbook(workbook_path)
    try:
        profiles = profile_mod.profile_workbook(wb)
    finally:
        wb.close()

    config.profiles_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sheet_profile in profiles:
        path = config.profiles_dir / f"{sheet_profile.name}.json"
        path.write_text(
            json.dumps(profile_mod.to_dict([sheet_profile]), indent=2, ensure_ascii=False),
            encoding="utf-8")
        written.append(str(path))

    config.costing_workbook = workbook_path
    save_config(config)
    return {"sheets": profile_mod.to_dict(profiles)["sheets"], "written": written}


def _rows(args: argparse.Namespace, config: Config) -> dict:
    workbook_path = _require_costing_workbook(config)
    wb = Workbook(workbook_path)
    try:
        return {"rows": [{"row": r, "values": wb.read_row(args.sheet, r)}
                         for r in range(args.start, args.end + 1)]}
    finally:
        wb.close()


def _profile_itinerary(args: argparse.Namespace, config: Config) -> dict:
    # CRITICAL regression fix (code review): --default-pax used to live
    # here too, and would be written into the single global
    # data/profiles/itinerary_template.json. That file is reused for
    # every itinerary /cost is ever pointed at that happens to be shaped
    # the same (see itinerary_profile.template_fits -- deliberately
    # shape-based, not identity-based). A party size is data about ONE
    # client's booking, not about the shape of the sheet, so persisting
    # it there meant a second, differently-sized client's itinerary could
    # silently inherit the first client's party size with no warning.
    # default_pax can now only ever be supplied per run, on `cost`.
    wb = Workbook(Path(args.file))
    try:
        template = propose_template(wb, wb.sheet_names()[0])
    finally:
        wb.close()
    save_template(template, config.template_path)
    return {"template": vars(template)}


def _catalog_add(args: argparse.Namespace, config: Config) -> dict:
    item = CatalogItem.from_dict(json.loads(Path(args.file).read_text(encoding="utf-8")))
    _validate_catalog_item_cells(item)
    unprotected = _check_fingerprints(item, args.unprotected)
    catalog = Catalog.load(config.catalog_path)

    try:
        existing = catalog.get(item.id)
    except KeyError:
        existing = None

    # /map is an AI minting ids across sessions, so a reused id is a
    # realistic way to silently destroy a previously confirmed, fingerprinted
    # entry -- Catalog.upsert replaces on collision with no warning of its
    # own. Refuse here unless the incoming item is byte-for-byte identical to
    # what's already saved (a harmless, idempotent re-add) or the caller
    # explicitly passed --replace to say this is a deliberate re-map.
    replaced = False
    if existing is not None and existing.to_dict() != item.to_dict():
        if not args.replace:
            raise ConfigurationError(
                f"An item with id {item.id!r} already exists in the catalog "
                f"(currently mapped to {existing.name!r}) and this save would "
                "overwrite it with different content. If you mean to "
                "deliberately re-map this item, pass --replace."
            )
        replaced = True

    catalog.upsert(item)
    catalog.save(config.catalog_path)
    result = {"id": item.id, "count": len(catalog.items)}
    if replaced:
        result["replaced"] = True
    if unprotected:
        result["unprotected"] = True
    return result


def _check_fingerprints(item: CatalogItem, allow_unprotected: bool) -> bool:
    """C2 (code review): structural-drift protection used to be entirely
    opt-in -- _verify_fingerprint skips both checks when the fingerprint
    fields are empty, and catalog-add never required them. /map is an AI
    writing these files across sessions, and the fingerprint step lives in
    a hand-run `python -c` snippet (map-rate-sheet/SKILL.md step 5) --
    skipping it is realistic, and a well-formed but unprotected item is
    silently vulnerable to the sheet changing shape underneath it later
    (see catalog.FingerprintMismatch's docstring).

    Refuses to save an item missing either fingerprint unless the caller
    explicitly passes --unprotected to say this is a deliberate exception.
    Returns whether the saved item is unprotected, so the caller can
    report it.
    """
    missing = not item.row_fingerprint or not item.structure_fingerprint
    if missing and not allow_unprotected:
        raise ConfigurationError(
            f"{item.id!r} has no row_fingerprint or structure_fingerprint "
            "computed yet, so it would be saved unprotected against the "
            "sheet changing shape underneath it later (rows inserted or "
            "deleted, columns moved). Compute both first -- see step 5 of "
            "map-rate-sheet/SKILL.md -- or pass --unprotected if you "
            "really mean to save it without them."
        )
    return missing


def _validate_catalog_item_cells(item: CatalogItem) -> None:
    """Every cell reference an item carries must parse before it is ever
    written to catalog.json. /map is an AI writing these entries, so a
    malformed reference (a typo, a stray label instead of a cell address)
    is the expected failure mode, not a rare one -- and it should fail
    here, in plain English naming the offending field, rather than as a
    generic error deep inside a later costing run.
    """
    pricing = item.pricing
    pattern = pricing.get("pattern")
    if pattern == "flat":
        _check_cell_ref("pricing.cell", pricing.get("cell"))
    elif pattern == "tiered_by_pax":
        for index, tier in enumerate(pricing.get("tiers", [])):
            _check_cell_ref(f"pricing.tiers[{index}].cell", tier.get("cell"))

    for index, modifier in enumerate(item.modifiers):
        if "cell" in modifier:
            _check_cell_ref(f"modifiers[{index}].cell", modifier.get("cell"))


def _check_cell_ref(field: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"{field} is missing a cell reference (got {value!r}).")
    try:
        CellRef.parse(value)
    except ValueError:
        raise ConfigurationError(
            f"{field} is not a valid cell reference: {value!r}. "
            "Expected a form like 'SheetName!A1'."
        )


def _cost(args: argparse.Namespace, config: Config) -> dict:
    workbook_path = _require_costing_workbook(config)

    src = Path(args.file)
    wb_itinerary = Workbook(src)
    try:
        template = _template_for_file(wb_itinerary, config)
        if args.default_pax is not None:
            # This-run-only. There is no way to persist a party size
            # against the saved template.json any more, and deliberately
            # so -- see the CRITICAL regression fix in _profile_itinerary
            # above.
            template.default_pax = args.default_pax

        # C4 (code review): confidence == "low" means propose_template
        # never found a pax column at all -- with no default_pax either,
        # every row's pax cell is blank, so the ONLY case parse_itinerary
        # can produce is "no default configured, drop it" for every
        # single line. That is a completely empty quote with no error and
        # no warning (reproduced on the wide-itinerary fixture, built
        # specifically for this shape). Refuse before that happens.
        if template.confidence == "low" and not template.default_pax:
            raise ConfigurationError(
                "I can't tell how many travellers this itinerary is for — "
                "there's no party-size column. Tell me the party size and "
                "I'll use it for every line."
            )

        lines, skipped_rows = parse_itinerary(wb_itinerary, template)
    finally:
        wb_itinerary.close()

    resolutions: dict[int, str] = {}
    if args.resolutions:
        raw = json.loads(Path(args.resolutions).read_text(encoding="utf-8"))
        resolutions = {int(k): v for k, v in raw.items()}

    catalog = Catalog.load(config.catalog_path)
    aliases = Aliases.load(config.aliases_path)

    wb_rates = Workbook(workbook_path)
    try:
        priced, changes = price_lines(lines, catalog, aliases, wb_rates, resolutions)
    finally:
        wb_rates.close()

    for row, item_id in resolutions.items():
        matched_line = next((line for line in lines if line.row == row), None)
        if matched_line:
            aliases.add(matched_line.raw_name, item_id)

    # I3 (code review): a corrupted aliases.json degrades to an empty,
    # in-memory Aliases() with load_error set (see pricing/match.py), but
    # this used to call save() unconditionally -- silently overwriting a
    # genuinely broken file with `{}` and permanently destroying every
    # confirmation the operator has ever made, with `ok: true`. Never
    # write over a file that failed to load; the original stays exactly
    # as it was so it can be inspected or repaired, and this run's
    # confirmations just aren't remembered until it is.
    if aliases.load_error is None:
        aliases.save(config.aliases_path)

    output = write_costed_workbook(src, template, priced, date.today())
    summary = summarize(priced, changes)
    summary["skipped_rows"] = skipped_rows
    if aliases.load_error is not None:
        summary["warnings"].append(
            f"Your saved confirmations couldn't be read ({aliases.load_error}). "
            "I haven't overwritten the file, so nothing is lost, but I won't "
            "remember any choices from this run until it's fixed."
        )
    log = write_run_log(config.runs_dir, {
        "input": str(src), "output": str(output),
        "summary": summary, "lines": [vars(p) for p in priced]})

    return {"output": str(output), "summary": summary,
            "lines": [vars(p) for p in priced], "run_log": str(log)}


def _template_for_file(wb: Workbook, config: Config) -> ItineraryTemplate:
    """C3 (code review): the saved template describes ONE itinerary shape,
    but data/profiles/itinerary_template.json is a single global file
    reused for every file /cost is ever pointed at. If this workbook
    isn't shaped like the one the template was confirmed on (different
    sheet name, or the mapped columns no longer line up with a real
    header row), reusing it silently misaligns every role and can drop
    real lines with no error (see itinerary_profile.template_fits).
    Falls back to a fresh proposal for THIS file rather than trusting
    stale column letters.
    """
    if config.template_path.exists():
        saved = load_template(config.template_path)
        if template_fits(wb, saved):
            return saved
    return propose_template(wb, wb.sheet_names()[0])


def _verify(args: argparse.Namespace, config: Config) -> dict:
    from pricing.verify import verify_itinerary

    workbook_path = _require_costing_workbook(config)
    src = Path(args.file)
    wb_itinerary = Workbook(src)
    try:
        # Same stale-template guard as _cost (C3, code review) -- verify
        # is the trust-building step, so it must not silently misread the
        # very file it's meant to be checking either.
        template = _template_for_file(wb_itinerary, config)
    finally:
        wb_itinerary.close()

    catalog = Catalog.load(config.catalog_path)
    aliases = Aliases.load(config.aliases_path)

    wb_rates = Workbook(workbook_path)
    try:
        diffs, summary = verify_itinerary(src, template, catalog, aliases, wb_rates)
    finally:
        wb_rates.close()

    return {"diffs": [vars(d) for d in diffs], "summary": summary}


def _refresh(config: Config) -> dict:
    from pricing.verify import refresh

    workbook_path = _require_costing_workbook(config)
    catalog = Catalog.load(config.catalog_path)

    wb_rates = Workbook(workbook_path)
    try:
        return refresh(catalog, wb_rates)
    finally:
        wb_rates.close()


def _require_costing_workbook(config: Config) -> Path:
    if config.costing_workbook is None:
        raise ConfigurationError(
            "I don't know where your costing workbook is yet. "
            "Run profile and point me at it first."
        )
    return config.costing_workbook


def _friendly(exc: Exception) -> str:
    if isinstance(exc, ConfigurationError):
        return str(exc)
    if isinstance(exc, _ArgumentParsingError):
        return f"I didn't understand that command: {exc}"
    if isinstance(exc, WorkbookLockedError):
        return str(exc)
    if isinstance(exc, MissingRoleError):
        return str(exc)
    if isinstance(exc, json.JSONDecodeError):
        return ("That file doesn't look like valid JSON — it may have been "
                "edited by hand and broken. Please check it, or regenerate it.")
    if isinstance(exc, FileNotFoundError):
        name = Path(getattr(exc, "filename", "") or "that file").name
        return f"I couldn't find {name}. Has it been moved or renamed?"
    if isinstance(exc, KeyError):
        # I2 (code review): renaming a tab is the single most likely thing
        # a non-technical operator does to her own workbook, and it used
        # to fall all the way through to the generic "something went
        # wrong" message -- the one failure mode she's most likely to hit
        # got no help at all. openpyxl raises exactly
        # KeyError("Worksheet <name> does not exist.") when a sheet
        # lookup misses -- missing_sheet_name() recognises exactly that
        # shape and extracts the bare name.
        #
        # I2-regression (code review): this branch used to treat EVERY
        # KeyError as a sheet-lookup miss and quote exc.args[0] straight
        # into the sentence unchanged. That was wrong twice over: (a) a
        # KeyError from somewhere else entirely (e.g. a hand-edited
        # template.json missing the "cost" role -- see
        # report.py/verify.py's `template.roles["cost"]`) got the false
        # instruction to go check a tab name that was never the problem;
        # and (b) even the genuine sheet-lookup case quoted openpyxl's
        # whole sentence ("Worksheet Italia does not exist.") instead of
        # just the sheet name, reading back as
        # "a sheet called 'Worksheet Italia does not exist.'". Only a
        # real worksheet-lookup KeyError gets this message now; anything
        # else falls through to the honest generic wording below.
        sheet = missing_sheet_name(exc)
        if sheet is not None:
            return (f"I can't find a sheet called {sheet!r} in your workbook. "
                    "Check that the tab name hasn't changed, or run /profile "
                    "again to re-read the workbook.")
    return ("Something went wrong that I don't have a friendly explanation for. "
            "The details are saved in the runs folder — please send them on.")


def _log_traceback(config: Config | None) -> None:
    if config is None:
        return
    try:
        config.runs_dir.mkdir(parents=True, exist_ok=True)
        (config.runs_dir / "last-error.txt").write_text(
            traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass
