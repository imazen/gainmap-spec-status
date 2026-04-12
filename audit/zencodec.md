# zencodec — ISO 21496-1 canonical implementation

## Status: **compliant (canonical)**

`zencodec::gainmap` is the cross-codec canonical implementation of ISO 21496-1
binary metadata parsing and serialization. It is the authority all other zen
crates should defer to for wire-format compliance.

## Files

- `~/work/zen/zencodec/src/gainmap.rs` (2176 lines) — canonical impl

## Public surface

```rust
// Wire format selection
pub enum Iso21496Format {
    JpegApp2,  // no version byte — JPEG APP2 and JXL jhgm
    AvifTmap,  // with version(u8) prefix — AVIF tmap item
}

// Core types
pub struct GainMapChannel {
    pub min: f64,              // log2 domain
    pub max: f64,              // log2 domain
    pub gamma: f64,            // linear
    pub base_offset: f64,      // linear
    pub alternate_offset: f64, // linear
}
pub struct GainMapParams { /* channels, headroom, direction, color space */ }
pub enum GainMapDirection { BaseIsSdr, BaseIsHdr }
pub struct GainMapInfo     { /* high-level per-image summary */ }
pub enum GainMapPresence   { None, Detected, Parsed(GainMapParams) }
pub struct GainMapSource   { /* reference to gain map pixel data */ }
pub struct DecodedGainMap  { /* base + gain map + params, post-decode */ }

// Wire fractions (ISO 21496-1 §5.2.5)
pub struct Fraction  { numerator: i32, denominator: u32 }
pub struct UFraction { numerator: u32, denominator: u32 }

// Parse / serialize
pub fn parse_iso21496_fmt(data: &[u8], format: Iso21496Format) -> Result<GainMapParams, _>;
pub fn serialize_iso21496_fmt(params: &GainMapParams, format: Iso21496Format) -> Vec<u8>;
```

## Flag bits implemented (match ISO 21496-1 §5.2.4/§5.2.5)

| Bit | Constant | Meaning |
|---|---|---|
| 7 (0x80) | `FLAG_MULTI_CHANNEL` | three channels vs one |
| 6 (0x40) | `FLAG_USE_BASE_COLOUR_SPACE` | gain map lives in base image colour space |
| 3 (0x08) | `FLAG_COMMON_DENOMINATOR` | compact form: shared denominator for all fractions |
| 2 (0x04) | `FLAG_BACKWARD_DIRECTION` | base is HDR, alt is SDR (libultrahdr direction) |

Bits 0, 1, 4, 5 are reserved per ISO 21496-1 and correctly ignored/zeroed.

## Header sizes (match spec)

- `AVIF_HEADER_SIZE = 6`: `version(1) + min_version(2) + writer_version(2) + flags(1)`
- `JPEG_HEADER_SIZE = 5`: `min_version(2) + writer_version(2) + flags(1)` — AVIF minus the version byte
- `FRACTION_SIZE = 8`: `numerator(4) + denominator(4)`

## Two payload encodings

- **Full (default):** each value has its own denominator → `5 × fraction_size` per channel
- **Common denominator:** shared denominator for all values → shorter encoding, used by libultrahdr

Both are implemented in `parse_payload_full` and `parse_payload_common_denom`,
with matching writers.

## Deprecated legacy entry points

`parse_iso21496(data)` and `serialize_iso21496(params)` are deprecated
since 0.1.12. They were AVIF-format in 0.1.11 and changed to JPEG-format
in 0.1.12 — a silent breaking change. The deprecation forces callers to
`parse_iso21496_fmt` / `serialize_iso21496_fmt` with an explicit format.

**Compliance note:** any code still calling the deprecated path against an
AVIF `tmap` blob will misparse by 1 byte (the missing version prefix). Grep
all zen crates for the bare names to confirm no stragglers.

## Gaps / followups

1. **Colorimetry fields** — `GainMapParams` includes colorimetry members but
   the parser/serializer in `gainmap.rs` focuses on the §5.2 metadata block.
   Verify that the alt-image `Cicp` / alt-image primaries from §5.3 are
   plumbed through. (Follow-up in `audit/compliance-matrix.md`.)
2. **No `Annex B` colour conversion helpers.** §6 "Gain map application"
   requires working in an application colour space. The actual per-pixel
   evaluation lives in `ultrahdr-core::gainmap::apply` — not here. Should be
   moved or aliased into `zencodec::gainmap::apply` for discoverability.
3. **Single reference impl.** There is a second copy of this parser in
   `ultrahdr-core::metadata::iso21496`. See `audit/ultrahdr.md` — the copies
   must be kept in sync or one deleted.

## No over-spec

zencodec does not expose fields ISO 21496-1 doesn't define. The `GainMapInfo`
and `DecodedGainMap` wrappers are convenience types for pipeline plumbing,
not added wire-format fields.
