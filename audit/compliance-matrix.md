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

| Crate | Parse 21496-1 | Serialize 21496-1 | Container binding | Alt ICC | Multi-channel | Common denom | Backward dir | Test vectors |
|---|---|---|---|---|---|---|---|---|
| **zencodec** (canonical) | ✅ JpegApp2 + AvifTmap | ✅ both variants | ➖ | ➖ | ✅ | ✅ | ✅ | ⚠️ unit only |
| **ultrahdr-core** | 🔁 duplicate of zencodec | 🔁 | JPEG APP2 marker | via ICC profile box | ✅ | ✅ | ✅ | ⚠️ unit only |
| **zenjpeg** (ultrahdr) | delegated to ultrahdr-core | delegated | JPEG + MPF + XMP | via APP2 ICC | ✅ | ✅ | ✅ | ⚠️ synthetic |
| **zenavif-parse** | ✅ native, via `parse_tmap_bytes` | ✅ `serialize_tmap_bytes` | AVIF `tmap` read | `alt_colr` property | ✅ | ✅ | ✅ | ⚠️ byte-exact unit |
| **zenavif-serialize** | ➖ (accepts blob) | ➖ (accepts blob) | AVIF `tmap` + `altr` write | ✅ via ColrBox | ⚠️ monochrome flag | ➖ | ➖ | ⚠️ unit |
| **zenavif** | via zenavif-parse | via zenavif-serialize | full round-trip | ✅ | ✅ | ✅ | ✅ | ❌ real-file |
| **zenjxl-decoder** | ➖ (returns blob) | ➖ (round-trips blob) | JXL `jhgm` read | Brotli-compressed | ➖ | ➖ | ➖ | ❌ real-file |
| **jxl-encoder** | ➖ | ➖ | JXL `jhgm` append | ➖ | ➖ | ➖ | ➖ | ⚠️ unit only |
| **zenjxl** | via zenjxl-decoder | via jxl-encoder | JXL full pipeline | ✅ | ✅ via zencodec | ✅ | ✅ | ❌ real-file |
| **heic** | ➖ | ➖ | Apple aux item only | ➖ | ➖ | ➖ | ➖ | ❌ real-file |
| **heic** (HEIF `tmap`) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **zenraw** | ➖ (Apple vendor) | ➖ | Apple MPF in APPLEDNG | ➖ | ➖ | ➖ | ➖ | ⚠️ synthetic |
| **zenpng** | ➖ | ➖ | ➖ (spec not merged) | ➖ | ➖ | ➖ | ➖ | ➖ |
| **zentiff** | ➖ | ➖ | ➖ (no spec) | ➖ | ➖ | ➖ | ➖ | ➖ |
| **image-tiff** | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |

## Findings

### 1. Duplicate ISO 21496-1 parser 🔁 (high priority)

- `zencodec/src/gainmap.rs` (2176 lines) and
  `ultrahdr/ultrahdr-core/src/metadata/iso21496.rs` (1671 lines) are
  independent implementations of the same ISO 21496-1 parser.
- They share constant values, header sizes, and flag definitions by
  coincidence of correctness, not by sharing code.
- **Risk:** a spec amendment (e.g. Amendment 1 adding a flag) will
  require editing both. Drift between them would corrupt one pipeline
  without breaking the other.
- **Action:** delete `ultrahdr-core/src/metadata/iso21496.rs` and depend
  on `zencodec::gainmap`. Keep ultrahdr-core-specific helpers
  (`JpegIsoMarkers`, `create_iso_app2_marker`) as thin wrappers.

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

1. **P0** — delete ultrahdr-core ISO parser, depend on zencodec::gainmap
2. **P0** — add HEIF `tmap` support to `heic`
3. **P1** — populate `test-vectors/` with upstream samples (avif, jxl, jpeg, heic)
4. **P1** — verify AVIF `tmap` item hidden flag
5. **P1** — differential test zenjxl-decoder against libjxl-produced `jhgm`
6. **P2** — rename zenraw's DNG OpcodeList2 GainMap to "lens shading table"
7. **P2** — test gain map grid derivation path in zenavif-parse
8. **P3** — Apple→ISO metadata conversion helper (shared between zenraw,
   heic, ultrahdr-core)
