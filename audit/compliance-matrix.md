# Compliance matrix — zen crates vs gain map specs

**Date:** 2026-04-11
**Specs covered:** ISO 21496-1:2025, HEIF Amd 1:2025, av1-avif §4.2.2,
libjxl `jhgm`, UltraHDR v1.1 (de-facto), W3C PNG `gMAP` proposal

## Legend

- ✅ compliant and tested
- ⚠️ partially compliant or compliance claim untested
- ❌ gap: spec says something exists and we do not implement it
- ➖ N/A: spec does not require this from this crate
- 🔁 duplicate implementation across crates (risk of drift)

## Summary matrix

Updated 2026-04-11 after 22-fixture matrix differential test. See
[`encoders.md`](encoders.md) for encode-path specifics.

| Crate | Parse 21496-1 | Serialize 21496-1 | Container binding | Alt ICC | Multi-channel | Common denom (read) | Common denom (write) | Backward dir | Test vectors |
|---|---|---|---|---|---|---|---|---|---|
| **zencodec** (canonical) | ✅ JpegApp2 + AvifTmap | ✅ full form only | ➖ | ➖ | ✅ | ✅ | ❌ | ✅ | ✅ 22-case matrix |
| **ultrahdr-core** | 🔁 duplicate | 🔁 full form only | JPEG APP2 marker | via ICC profile box | ✅ | ✅ | ❌ | ✅ | ⚠️ unit only |
| **zenjpeg** (ultrahdr) | via ultrahdr-core | via ultrahdr-core | JPEG + MPF + XMP | via APP2 ICC | ✅ | ✅ | ❌ | ✅ | ⚠️ synthetic |
| **zenavif-parse** | ⚠️ bugs — see #3 | ⚠️ drops writer_version | AVIF `tmap` read | `alt_colr` property | ✅ | ❌ **bug** | ❌ | ✅ | ✅ 18/22 pass |
| **zenavif-serialize** | ➖ (accepts blob) | ➖ (accepts blob) | AVIF `tmap` + `altr` write | ✅ via ColrBox | ⚠️ monochrome flag | ➖ | ➖ | ➖ | ⚠️ unit |
| **zenavif** | via zenavif-parse | via zenavif-serialize | full round-trip | ✅ | ✅ | inherits bug | ❌ | ✅ | ❌ real-file |
| **zenjxl-decoder** | ➖ (returns blob) | ➖ (round-trips blob) | JXL `jhgm` read | Brotli-compressed | ➖ | ➖ | ➖ | ➖ | ❌ real-file |
| **jxl-encoder** | ➖ | ➖ | JXL `jhgm` append | ➖ | ➖ | ➖ | ➖ | ➖ | ⚠️ unit only |
| **zenjxl** | via zenjxl-decoder | via jxl-encoder | JXL full pipeline | ✅ | ✅ via zencodec | ✅ via zencodec | ❌ | ✅ | ❌ real-file |
| **ravif** | ➖ | ➖ (accepts blob) | AVIF via zenavif-serialize | via caller | ➖ | ➖ | ➖ | ➖ | ⚠️ unit |
| **zenrav1e** | ➖ (not its role) | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ by design |
| **heic** | ➖ | ➖ | Apple aux item only | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ real-file |
| **heic** (HEIF `tmap`) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **zenraw** | ➖ (Apple vendor) | ➖ | Apple MPF in APPLEDNG | ➖ | ➖ | ➖ | ➖ | ➖ | ⚠️ synthetic |
| **zenpng** | ➖ | ➖ | ➖ (spec not merged) | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| **zentiff** | ➖ | ➖ | ➖ (no spec) | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| **image-tiff** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |

**Common-denom writer column is uniformly ❌ across all serializers.** No
zen crate can emit libultrahdr-canonical common-denom form. Documented in
`audit/encoders.md` finding #1 as a compliance gap (not a bug — full form
is universally readable).

## Findings

### 1. Three duplicate ISO 21496-1 parsers 🔁 (high priority)

**Updated 2026-04-11:** initial audit found two duplicates; the corpus
differential test found a third and proved drift has already happened.

- `zencodec/src/gainmap.rs` (2176 lines) — canonical
- `ultrahdr/ultrahdr-core/src/metadata/iso21496.rs` (1671 lines) — known duplicate
- `zenavif-parse/src/lib.rs::parse_tone_map_image` (~70 LOC at line 3758) — **third duplicate**

All three are independent implementations. They agree on the basic layout
but not on the edges: the corpus parameter-matrix test
([tools/corpus-test](../tools/corpus-test)) found zenavif-parse **silently
ignores `FLAG_COMMON_DENOMINATOR` (bit 3)** and **drops `writer_version`
on parse**. 4/22 AvifTmap fixtures fail as a result. See
[imazen/zenavif-parse#3](https://github.com/imazen/zenavif-parse/issues/3).

- **Risk:** drift is not hypothetical — it's already present. Every spec
  amendment that adds a flag or field will require editing all three.
- **Actions:**
  - P0: fix the two zenavif-parse bugs (tracked in issue #3)
  - P0: delete `ultrahdr-core/src/metadata/iso21496.rs` (tracked in
    [imazen/ultrahdr#4](https://github.com/imazen/ultrahdr/issues/4))
  - P1: decide whether zenavif-parse should keep its own parser (needed
    for byte-exact raw-fraction round-trip — zencodec's f64 form is lossy)
    or should delegate to zencodec and add a `to_bytes_exact()` helper
    that preserves the original wire bytes verbatim via a parsed-bytes
    tag.

### 1a. zencodec serializer is lossy by design ⚠️

`zencodec::gainmap::serialize_iso21496_fmt` uses `UFraction::from_f64_cf()`
/ `Fraction::from_f64_cf()` — the "canonical form" picks a denominator
matching f32 resolution (~2^-24). Parse-serialize-parse round-trip
preserves **values** within ~1e-7 but does **not** preserve the original
numerator/denominator.

**Consequence:** zencodec cannot be used for byte-exact re-muxing of AVIF
`tmap` items where the producer's exact fractions must be preserved.
That path requires zenavif-parse (which has bugs — see above) or a new
exact-preserving API on zencodec.

**Action:** document in `zencodec/CLAUDE.md` as a design choice. Track
whether a `GainMapParams::from_bytes_exact()` + `to_bytes_exact()` API
that round-trips the raw wire bytes should be added.

### 2. HEIF Amendment 1 `tmap` gap in `heic` ❌ (high priority)

- `heic` reads Apple's HEIC auxiliary-item gain map path via
  `urn:com:apple:photo:2020:aux:hdrgainmap`.
- `heic` does **not** read HEIF Amendment 1 `tmap` derived image items.
- `libavif` and `libheif` both handle `tmap`; any HEIC file produced by
  iOS 18+ (speculative) or a `libheif`-based encoder using the 2025 path
  will be silently mis-decoded by `heic`.
- **Action:** add `decode_tmap_gain_map(data)` alongside existing
  `decode_gain_map`; teach `has_gain_map` to recognise both paths.

### 3. No cross-impl real-file test coverage ❌ (medium priority)

- All existing gain map tests are unit tests against synthetic fixtures or
  byte-exact round-trip of pre-existing payloads.
- We have no test vectors from:
  - libultrahdr's reference JPEG samples
  - libavif's `testFiles/` (has AVIF `tmap` samples)
  - libjxl's `testdata/` (has `jhgm` box samples, if any shipped)
  - Apple iPhone sample HEIC / JPEG files with real gain maps
- **Action:** populate `test-vectors/` with upstream samples under their
  original licenses and add roundtrip tests per codec. Where upstreams do
  not ship samples, generate tiny synthetic ones via each crate's encode
  path, committed with reproducibility metadata.

### 4. Alt ICC profile handling varies per codec ⚠️ (low priority)

- zenjpeg: APP2 ICC profile for alt colour space
- zenavif-serialize: `ColrBox` property on `tmap` item
- zenjxl-decoder: Brotli-compressed bytes, passthrough only
- **Action:** document each crate's alt-ICC contract, and ensure
  cross-codec transcode preserves the alt ICC (or drops it with a warning,
  never silently).

### 5. Terminology collision in `zenraw` ⚠️ (low priority)

- DNG OpcodeList2 GainMap (opcode 9, lens shading) and Apple MPF HDR gain
  map are both called "gain map" in source + docs.
- **Action:** rename the DNG opcode to "lens shading table" in public API,
  reserve "gain map" for the HDR sense.

### 6. AVIF `tmap` item hidden-flag ⚠️ (needs verification)

- AVIF spec §4.2.2 says the gain map image item should be a hidden image
  item. `zenavif-serialize/src/lib.rs:605+` writes the item but needs a
  spot-check that `iinf.hidden` (or the equivalent flag) is set.
- **Action:** add an assertion in a roundtrip test.

### 7. libjxl `jhgm` wire format not independently verified ⚠️

- zenjxl-decoder's `GainMapBundle::parse` works in practice but its
  byte layout was reverse-engineered from libjxl. We have not run a
  byte-exact roundtrip against a libjxl-produced file.
- **Action:** add a libjxl-produced sample to `test-vectors/jxl/` and a
  differential test.

## Over-spec check: do we expose fields specs don't define?

Grepping `pub struct GainMap*` across all crates and comparing to ISO
21496-1 §5.2 + HEIF Amd 1 tmap + libjxl jhgm + UltraHDR hdrgm:

| Crate | Private fields? | Notes |
|---|---|---|
| zencodec | ✅ none | all fields trace to ISO 21496-1 |
| ultrahdr-core | ✅ none | same |
| zenavif-parse | ✅ none | raw numerator/denominator form |
| zenavif-serialize | ✅ none | monochrome + chroma_subsampling are legit HEIF item props |
| zenjxl-decoder | ✅ none | matches libjxl struct members |
| heic | ⚠️ `HdrGainMap` carries XMP passthrough | OK — Apple puts metadata in XMP |
| zenraw | ⚠️ Apple vendor fields | isolated in `apple::GainMapInfo`, not claimed as ISO |

**No over-spec.** No crate advertises fields the spec doesn't define.

## Gap check: do the specs define fields we don't expose?

Per ISO 21496-1 §5.2 (from the free TOC):

- `minimum_version`, `writer_version`, `flags` — ✅ all crates
- per-channel `gain_map_min/max`, `gamma`, `base_offset`, `alternate_offset` — ✅
- `base_hdr_headroom`, `alternate_hdr_headroom` — ✅
- `multi_channel`, `use_base_colour_space`, `backward_direction`,
  `common_denominator` flags — ✅ zencodec and ultrahdr-core, ⚠️ zenavif-parse
  doesn't parse common_denominator form explicitly (needs verification)

Per HEIF Amd 1 (derived from av1-avif §4.2.2 + libavif implementation):

- `tmap` derived item payload = ISO 21496-1 metadata — ✅ zenavif-serialize, parse
- `altr` entity group linking base + tmap — ✅ zenavif-serialize
- hidden gain map image item — ⚠️ verify in zenavif-serialize
- Optional `ColrBox` property on tmap item for alt colour space — ✅
- Gain map may have its own `grid` derivation — ⚠️ not tested

Per libjxl `jhgm` box (from libjxl header file):

- `jhgm_version` byte (must be 0) — ✅ zenjxl-decoder checks this
- metadata size + blob — ✅
- optional `JxlColorEncoding` — ⚠️ stored as raw bytes; libjxl's actual
  bit-packed layout not independently verified
- optional Brotli-compressed alt ICC — ✅
- bare JXL codestream — ✅

Per UltraHDR v1.1 hdrgm: namespace:

- `Version`, `BaseRenditionIsHDR` — ✅
- `HDRCapacityMin`, `HDRCapacityMax` — ✅
- `GainMapMin`, `GainMapMax`, `Gamma`, `OffsetSDR`, `OffsetHDR` — ✅
- v1.0 legacy field encoding — ⚠️ ultrahdr-core's leniency covers this

## Action list (prioritized)

1. **P0** — [imazen/zenavif-parse#3](https://github.com/imazen/zenavif-parse/issues/3) — fix FLAG_COMMON_DENOMINATOR + writer_version handling
2. **P0** — [imazen/ultrahdr#4](https://github.com/imazen/ultrahdr/issues/4) — delete ultrahdr-core ISO parser, depend on zencodec::gainmap
3. **P0** — migrate `zenjpeg::ultrahdr::encode` from ultrahdr-core's serializer to `zencodec::gainmap::serialize_iso21496_fmt` (blocked on #4; see `audit/encoders.md` finding #2)
4. **P0** — [imazen/heic#8](https://github.com/imazen/heic/issues/8) — add HEIF Amd 1 `tmap` support
5. **P1** — bump `ultrahdr-core::generate_gainmap_xmp` from hardcoded `hdrgm:Version="1.0"` to v1.1 by default (`audit/encoders.md` finding #3)
6. **P1** — [imazen/zenraw#2](https://github.com/imazen/zenraw/issues/2) — rename DNG opcode-9 GainMap terminology
7. **P1** — populate `test-vectors/heic/` with Apple + HEIF Amd 1 samples
8. **P1** — verify AVIF `tmap` item hidden flag (zenavif-serialize)
9. **P1** — differential test zenjxl-decoder against real `cjxl --ultrahdr` output
10. **P2** — test gain map grid derivation path in zenavif-parse
11. **P2** — consider exact-preserving ISO 21496-1 API in zencodec (see finding 1a)
12. **P2** — add common-denominator writer to zencodec (optional; for libultrahdr-canonical output — see `audit/encoders.md` finding #1)
13. **P2** — encoder golden tests: zenjpeg UltraHDR + zenavif `tmap` + zenjxl `jhgm` against libultrahdr/libavif/libjxl reference (`audit/encoders.md` §Differential test gaps)
14. **P3** — Apple → ISO metadata conversion helper (shared between zenraw,
    heic, ultrahdr-core)

## Test coverage — 2026-04-11

After expanding `tools/corpus-test` to run against a 22-case parameter
matrix covering direction / multichannel / common-denom / boundary
fractions / varied denominators / gamma / i32 extremes / writer_version:

| Category | Fixtures | Pass | Fail |
|---|---|---|---|
| sources/*_jpeg.bin (zencodec JpegApp2 round-trip) | 22 | 22 (100%) | 0 |
| sources/*_avif.bin (zencodec + zenavif-parse differential) | 22 | 18 (82%) | **4** |
| avif/ (libavif fixtures) | 5 | 5 | 0 |
| jxl/ (synthetic jhgm) | 2 | 2 | 0 |
| jpeg/ (ultrahdr-conformance subset) | 5 | 5 | 0 |
| **Total** | **56** | **52 (93%)** | **4** |

Parameter axes exercised: see `tools/gen-iso21496.py` for the matrix.

**Scale sweeps (no fixture-matrix-level failures, probe mode):**
- `libavif/tests/data/`: 69/69 pass (56 AVIFs + 13 JPEGs)
- `codec-corpus/ultrahdr-conformance/`: 49/51 pass (2 intentional skips)
