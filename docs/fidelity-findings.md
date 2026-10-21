# Round-trip fidelity findings

**openpyxl version tested:** 3.1.5.
**Pillow version tested:** 12.3.0.

**Dependency status:** as of this revision, `Pillow` is a declared runtime
dependency of this project, alongside `openpyxl` (see `pyproject.toml`:
`dependencies = ["openpyxl>=3.1", "pillow>=10.0"]`). This is a deliberate
change from the project's original stance (see "Why Pillow is now a
dependency" below) and it changes the measured result in this document.

**Machine-readable source of truth:** `docs/fidelity.json` carries the same two booleans (`images_survive_roundtrip`, `conditional_formatting_survives`) plus the exact `openpyxl`/`pillow` versions measured. A later task reads that JSON file, not this prose, to decide whether to warn the operator — `tests/test_roundtrip_fidelity.py::test_fidelity_json_matches_measured_behaviour` enforces that the JSON can never drift from what the round-trip tests actually observe. If you edit the narrative below, it does not change behaviour; edit `docs/fidelity.json` (and let the test catch you if it's wrong).

## What we measured

`tests/test_roundtrip_fidelity.py` builds a synthetic itinerary
(`build_branded_itinerary`) carrying an embedded PNG (standing in for an
agency logo) and a conditional-formatting rule (red fill when net cost is
negative), then puts it through the same path `/cost` will use:
`copy_for_write` (a `shutil.copy2` byte copy) followed by `Workbook`
loading the copy, writing a few cells, and calling `save()`.

## Result: conditional formatting survives

`test_save_roundtrip_preserves_conditional_formatting` passes. The
`CellIsRule` on `E8:E20` is present, unchanged, in the saved copy after
writing cost values into that same range. **Conditional formatting is not
at risk for this project's costing workflow.**

## Result: images now survive, with Pillow installed

`test_save_roundtrip_records_image_behaviour` passes: an embedded PNG
placed at `G1` is present both before and after the full
`copy_for_write` → `Workbook` load → `write` → `save()` path, and a
zip-level check confirms `xl/media/image1.png` and its drawing part are
still present in the saved output, with byte-identical image data to the
source (same length, same bytes). **The embedded image, and by extension
an agency logo, survives the costing round trip.**

## Why Pillow is now a dependency

This project originally pinned runtime dependencies to exactly `openpyxl`,
with no Pillow. Under that constraint, the measured behaviour was that
embedded images never survived the round trip at all — not specifically
because of `save()`, but because openpyxl's own reader silently discards
every embedded image on *read* whenever Pillow is not importable:

```python
# openpyxl/reader/drawings.py
if not PILImage: # Pillow not installed, drop images
```

With no Pillow present, that branch was always taken: the image was
invisible to openpyxl's in-memory model from the moment the file was
opened, well before any write or save ran, so the costed copy handed back
to the operator never carried the source workbook's embedded image (an
agency logo, in practice) even though a plain `shutil.copy2` alone
preserved those bytes exactly.

The project owner ruled that a client-facing, branded document losing its
agency's logo on every quote was unacceptable, and that this outweighs
the goal of dependency minimalism. Pillow was added as a runtime
dependency specifically to close the read-time drop described above, and
the measurement in this document (with Pillow 12.3.0 installed) confirms
that doing so is sufficient: openpyxl now decodes the image on read and
re-emits it unchanged on write.

## The resulting rule for `/cost`

**Images (including the agency logo) survive this tool's costing path,
now that Pillow is a declared dependency.** `/cost` does not need to warn
about lost images, and Phase 0 does not need an operator confirmation
step for this specific concern. The end user must run `git pull` followed
by `uv sync` to pick up the updated `uv.lock` (which now resolves and
pins Pillow) — without that sync step, her environment would still be
missing Pillow and would silently reproduce the old, image-dropping
behaviour described above.

## Verification detail

Beyond the pytest assertions, a direct check was run to rule out silent
re-encoding: the raw PNG bytes inside `xl/media/image1.png` were compared
between the pristine fixture and the file after the full
`copy_for_write` → `Workbook` load → `write` → `save()` path. Both were
70 bytes and identical byte-for-byte.
