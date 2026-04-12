# ultrahdr — JPEG UltraHDR encode/decode

## Status: **partially compliant**, duplicate ISO parser

`ultrahdr` (the crate family at `~/work/zen/ultrahdr/`) is our safe-Rust
re-implementation of Google's `libultrahdr` for reading and writing
UltraHDR JPEGs. It predates `zencodec::gainmap` and ships its own copy of the
ISO 21496-1 parser.

## Layout

```
ultrahdr/
├── ultrahdr-core/        low-level: gainmap math, ISO parser, XMP, MPF
│   └── src/
│       ├── gainmap/       compute.rs, apply.rs, apply_simd.rs, streaming.rs
│       ├── color/         tonemap.rs, transfer.rs
│       └── metadata/
│           ├── iso21496.rs  ← duplicate of zencodec::gainmap ISO parser
│           ├── mpf.rs
│           ├── xmp.rs
│           └── container.rs
├── ultrahdr-rs/          high-level encode/decode API, jpeg glue
├── fuzz/                 fuzz_targets/{parse_iso21496, parse_xmp, parse_mpf, decode, apply_gainmap, tonemap, parse_jpeg_segments}
└── wasm-bench/
```

## ISO 21496-1 parser duplication

**Red flag.** `ultrahdr-core/src/metadata/iso21496.rs` (1671 lines) is a
hand-rolled parser with its own `GainMapMetadata`, flag constants, and
header-size constants. These match `zencodec::gainmap` symbol-for-symbol:

| Constant | zencodec | ultrahdr-core |
|---|---|---|
| `FLAG_MULTI_CHANNEL` | 0x80 | 0x80 |
| `FLAG_USE_BASE_COLOUR_SPACE` | 0x40 | 0x40 |
| `FLAG_BACKWARD_DIRECTION` | 0x04 | 0x04 |
| `FLAG_COMMON_DENOMINATOR` | 0x08 | 0x08 |
| `HEADER_SIZE` (AVIF) | 6 | 6 |
| `JPEG_HEADER_SIZE` | 5 | 5 |
| `FRACTION_SIZE` | 8 | 8 |
| `HEADROOM_FRACTIONS` | *(implicit)* | 2 |
| `FRACTIONS_PER_CHANNEL` | *(implicit)* | 5 |

Both accept the `Iso21496Format` enum (JpegApp2 / AvifTmap) and produce
equivalent output.

**Risk:** field drift. If ISO 21496-1 Amendment 1 adds a field or flag,
we must edit both files. The odds of one being updated and not the other
are high.

**Recommendation:** delete `ultrahdr-core/src/metadata/iso21496.rs` and
have `ultrahdr-core` depend on `zencodec::gainmap` for the parser, keeping
only the ultrahdr-specific wrapper helpers (`JpegIsoMarkers`,
`create_iso_app2_marker`, `create_jpeg_iso_markers`,
`create_version_only_iso_app2`) in its own module.

## Public ultrahdr-core types (currently consumed by zenjpeg)

```rust
pub struct GainMapMetadata { /* ISO 21496-1 fields, owned */ }
pub struct GainMap         { /* pixel data + metadata */ }
pub enum GainMapEncodingFormat { /* base8, base10, ... */ }
pub struct Iso21496Format  /* re-exported, matches zencodec */
pub struct UnsignedFraction { num: u32, den: u32 }
pub struct RawImage        { /* image buffer for gain map compute */ }
pub enum PixelFormat       { /* subset, tonemap input formats */ }
pub enum ColorGamut        { /* sRGB, DisplayP3, BT.2020 */ }
pub enum ColorTransfer     { /* sRGB, Linear, PQ, HLG */ }

pub mod color::tonemap     { AdaptiveTonemapper, FitConfig, FitMode, FitStats, ToneMapConfig }
pub mod gainmap            { GainMapConfig, HdrOutputFormat, compute_gainmap, apply_gainmap,
                              RowDecoder, RowEncoder, StreamDecoder, StreamEncoder }
pub mod metadata::iso21496 { parse_iso21496, serialize_iso21496,
                              JpegIsoMarkers, create_iso_app2_marker,
                              create_jpeg_iso_markers, create_version_only_iso_app2 }
pub mod metadata::xmp      { parse_xmp, generate_xmp, generate_primary_xmp,
                              generate_gainmap_xmp }
```

## Known deviations from libultrahdr (from `zenjpeg/CLAUDE.md`)

| Behavior | libultrahdr | ultrahdr-core |
|---|---|---|
| `BaseRenditionIsHDR="True"` | Rejected | Accepted (documented bug) |
| Required XMP fields validation | Strict | Lenient |
| JPEG boundary detection | JpegScanner | MPF + SOI/EOI fallback |

These are **over-spec relative to strictness**: we accept files libultrahdr
would reject. That is usually fine for a decoder (be lenient on input), but
the BaseRenditionIsHDR acceptance can lead to backwards-direction gain maps
being applied in the wrong direction. Track in `known-bugs.md`.

## Fuzz targets (good)

- `parse_iso21496.rs` — wire format fuzzing
- `parse_xmp.rs` — XMP hdrgm parsing
- `parse_mpf.rs` — MPF directory parsing
- `parse_jpeg_segments.rs` — JPEG APPn walking
- `decode.rs` — full decode path
- `apply_gainmap.rs` — compute + apply
- `tonemap.rs` — tonemap math

## Gaps

1. **Duplicate ISO parser** (see above).
2. **No cross-format interop test.** Given both zencodec and ultrahdr-core
   parse the same bytes, we should have a differential test: pick a corpus
   of real UltraHDR JPEGs, parse the ISO blob both ways, assert the parsed
   struct is identical. If any mismatch, one of them is wrong.
3. **XMP hdrgm validation leniency.** Track which fields are optional
   vs mandatory per UltraHDR v1.1 + ISO 21496-1 §5.2.
4. **No ISO 21496-1:2025 conformance against Apple MPF gain maps.**
   `zenraw::apple::GainMapInfo` produces raw Apple gain map bytes that may
   not have an ISO 21496-1 metadata blob at all. The Apple→ISO conversion
   path needs a test vector.

## No over-spec in wire format

The parser accepts only fields ISO 21496-1 defines. Bit positions match.
No private extensions.
