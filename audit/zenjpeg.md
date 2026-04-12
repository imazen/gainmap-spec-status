# zenjpeg — JPEG UltraHDR layout + encode/decode

## Status: **compliant (ultrahdr path)**

`zenjpeg` integrates `ultrahdr-core` for UltraHDR JPEG encode/decode and
adds its own MPF-layout helpers for transform-preserving resize
(imageflow-style).

## Files

- `zenjpeg/zenjpeg/src/ultrahdr/mod.rs` — re-exports ultrahdr-core types
- `zenjpeg/zenjpeg/src/ultrahdr/encode.rs` (493 lines) — encode pipeline
- `zenjpeg/zenjpeg/src/ultrahdr/decode.rs` (279 lines) — streaming decode
- `zenjpeg/zenjpeg/src/layout/gainmap.rs` (268 lines) — MPF-based layout helpers
- `zenjpeg/zenjpeg/tests/ultrahdr_gainmap_decode.rs` — decode test
- `zenjpeg/zenjpeg/tests/ultrahdr_roundtrip.rs` — encode/decode roundtrip

## What it implements

- **Streaming encode**: `UltraHdrRowEncoder` that pushes SDR + gain map rows
  and emits a JPEG with ISO 21496-1 APP2 + hdrgm XMP + MPF APP2 + appended
  gain map JPEG.
- **Streaming decode**: `UltraHdrReader` that parses primary JPEG, extracts
  gain map metadata from XMP/APP2, locates the secondary JPEG via MPF, and
  exposes the gain map either as memory (`GainMapMemory::Cached`) or as a
  second streaming decoder.
- **Layout-aware resize**: `find_secondary_jpeg`, `assemble_ultrahdr`,
  `compute_gainmap_target` (`layout/gainmap.rs:181-268`) keep the gain map
  spatially locked to the primary during resize.
- **Hdrgm XMP detection**: `is_ultrahdr_xmp` (`layout/gainmap.rs:12`) tests
  for `hdrgm:Version` and `hdrgm:GainMapMax`.

## Compliance points

| ISO 21496-1 / UltraHDR | Status |
|---|---|
| APP2 marker with `urn:iso:std:iso:21496-1` | via `create_iso_app2_marker` |
| hdrgm XMP schema (v1.0 + v1.1) | via `ultrahdr-core::metadata::xmp` |
| MPF APP2 secondary image pointer | via `encode/extras.rs` MPF writer |
| Version byte (ISO 21496-1 §5.2.8) | `parse_iso21496_fmt(JpegApp2)` — no version byte prefix; OK |
| Primary JPEG precedes gain map JPEG | yes (libultrahdr order) |
| Absolute vs relative byte offsets | GContainer-style absolute offsets |

## Layout preservation during resize

The novel behaviour here is resize-preserving gain maps. `zenjpeg` can
decode an UltraHDR JPEG, resize the primary and gain map independently
(using `compute_gainmap_target` to keep spatial registration), and
re-assemble with a rewritten MPF directory. Imageflow uses this for on-the-fly
CDN resize of HDR photos.

**Compliance risk:** if the caller supplies mismatched scale factors, the
gain map can drift relative to the primary. The `compute_gainmap_target`
helper returns the correct target dimensions for proportional resize, but
there is no runtime check that the caller actually used them.

## Delegation to ultrahdr-core

`zenjpeg` does not re-implement ISO 21496-1 parsing or hdrgm XMP parsing —
it delegates to `ultrahdr-core`. This means it inherits both the correctness
and the duplication gap documented in `audit/ultrahdr.md`.

## Gaps

1. **Depends on ultrahdr-core ISO parser**, not `zencodec::gainmap`. When
   the duplication is resolved, `zenjpeg` must be updated to use the single
   canonical path.
2. **No conformance test against Google's reference UltraHDR samples** from
   libultrahdr testdata. `tests/ultrahdr_gainmap_decode.rs` uses synthetic
   fixtures. Cross-codec round-trip via `test-vectors/jpeg/` is the right
   next step.
3. **No XMP v1.0 vs v1.1 schema discrimination.** Current code accepts both;
   we should confirm v1.0 fields (old range encoding) are converted to v1.1
   semantics before handing off to gain map application.

## No over-spec

`zenjpeg::ultrahdr` accepts only ISO 21496-1 / hdrgm fields. No private
extensions, no undocumented magic. The known `BaseRenditionIsHDR="True"`
acceptance is inherited from ultrahdr-core and tracked there.
