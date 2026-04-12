# zenpng, zentiff, image-tiff — correctly absent

## Status: **compliant (no-op)**

Three crates correctly have **zero gain map code**:

- `zenpng` — PNG encoder/decoder
- `zenextras/zentiff` — TIFF wrapper around image-tiff
- `image-tiff` — pure Rust TIFF decode/encode

## Why this is the right state

### zenpng

PNG 3rd edition (W3C REC June 2025) has no `gMAP` chunk. PNG 4th edition
is still drafting — see `specs/png/status.md`. Until a merged PR in
`w3c/png` adds `gMAP`/`gDAT` chunks, there is nothing for `zenpng` to
implement. Inventing chunks ahead of the spec would create
forwards-incompatibility risk if the final chunk name or layout differs.

Confirmed by grep: `zenpng` only matches "gain map" in downloaded spec
HTML files (`specs/png-3e-rec-spec.html`, `specs/png-4e-draft-spec.html`),
not in any Rust source.

### zentiff / image-tiff

TIFF has no gain map binding at any spec authority — see
`specs/tiff-dng/status.md`. Adobe DNG 1.7.1 (Sep 2024) has no gain map
tags. ISO 21496-1:2025 Annex C does not list TIFF as a target container.
`image-tiff` and `zentiff` correctly do not expose a `GainMap` type.

## What to do when (if) the specs land

### PNG 4th edition ships with gMAP

1. Add a `GainMap` read path to `zenpng` that parses `gMAP` + `gDAT`
   chunks and returns `zencodec::GainMapParams` + gain map pixels.
2. Add a write path that accepts `zencodec::GainMapParams` and emits the
   chunks in their spec-defined order (`gMAP` before `IDAT`, `gDAT` after).
3. Propagate the `alternate-cICP` / `alternate-iCCP` / `alternate-mDCv`
   / `alternate-cLLi` chunk structure if the final spec goes with "Option C"
   (sibling alt chunks) instead of nested sub-chunks.

### TIFF/DNG

**Do nothing until a spec binding exists.** Ad-hoc private tags will
conflict with whatever Adobe or ISO eventually assigns. If a user needs to
carry ISO 21496-1 metadata in a TIFF today, they can use `tiff:Artist` or
a custom `tiff:UniqueCameraModel`-adjacent private tag in their own app,
but we will not standardize that pattern in `zentiff`.

## Gap watch

Track these for periodic re-audit:

- `w3c/png#380` state
- `w3c/png#536` 4th edition meta-issue
- New Adobe DNG spec versions (check quarterly)
- ISO 21496-1 Amendment 1 (if announced)

## No over-spec

These crates cannot over-spec because they implement nothing.
