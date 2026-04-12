# heic — HEIF/HEIC decoder (Apple gain map path only)

## Status: **partially compliant** — Apple-only, missing HEIF Amd 1 `tmap`

The `heic` crate decodes HEIC files via its own pure-Rust ISOBMFF parser.
It reads Apple's HDR gain map auxiliary image but **does not yet support
the HEIF Amendment 1 `tmap` derived image item**, which is the canonical
HEIF gain map mechanism and also the one AVIF uses.

## Files

- `~/work/zen/heic/src/decode.rs:1800-1886` — Apple gain map extraction
- `~/work/zen/heic/src/heif/parser.rs` — ISOBMFF / HEIF box parser
- `~/work/zen/heic/README.md` — "HDR gain map extraction (Apple
  `urn:com:apple:photo:2020:aux:hdrgainmap`)"

## What it implements

```rust
pub(crate) fn decode_gain_map(data: &[u8]) -> Result<HdrGainMap>;
pub(crate) fn has_gain_map(data: &[u8]) -> Result<bool>;
```

Both search for HEIC auxiliary items with `aux_type =
"urn:com:apple:photo:2020:aux:hdrgainmap"`. When found, the auxiliary item
is decoded as a grayscale HEVC image and returned along with any XMP
metadata associated with that item.

## What is missing

### HEIF Amendment 1 `tmap` support

The HEIF binding for ISO 21496-1 uses the `tmap` derived image item
(see `specs/avif-heif/status.md`). `heic` has **no code** that:

- Looks up `tmap` in the `iinf` entries
- Extracts the tmap item payload (the ISO 21496-1 metadata blob)
- Reads the `dimg` references from `tmap` to the base image and gain map image
- Reads the `altr` entity group that pairs the base with the `tmap` item

This is a **compliance gap** relative to HEIF Amd 1:2025 and AVIF §4.2.2.

### HEIC vs HEIF Amd 1 — why both matter

| Container | Gain map mechanism | Shipped by |
|---|---|---|
| Apple HEIC (iOS 14+) | Auxiliary image with `urn:com:apple:photo:2020:aux:hdrgainmap` aux type | iPhone cameras, Photos.app |
| HEIF Amd 1 (2025) | `tmap` derived image item + `altr` entity group | New Apple code? libheif? libavif reads both. |

Apple's iOS 14-iOS 17 HEIC files use the auxiliary-item path. iOS 18+ may
migrate to `tmap`. Either way, a HEIF reader that only handles one path
will silently drop gain maps from the other.

## Recommendation

1. Add `decode_tmap_gain_map(data)` as a sibling to `decode_gain_map(data)`.
2. Teach `has_gain_map` to return true when **either** an Apple aux item or
   a `tmap` item is present.
3. Return a unified `HdrGainMap` struct whose origin field distinguishes
   Apple aux from `tmap`-derived — consumers may need to know because the
   two paths carry different metadata shapes (Apple uses its own MakerNote
   fields, `tmap` carries an ISO 21496-1 blob).
4. Add a test vector for each variant under `test-vectors/avif/` and
   `test-vectors/heic/` (the `heic` crate currently uses HEIC; AVIF lives
   in `zenavif` but the same `tmap` machinery applies).

## Gaps

1. **HEIF Amd 1 `tmap`** — missing entirely. High priority.
2. **Apple HDR HEIC metadata conversion.** `decode_gain_map` returns an
   `HdrGainMap` with raw gain map pixels plus XMP. We do not convert the
   Apple-native metadata schema into ISO 21496-1 fields. Consumers who want
   to route the result into `zenavif-serialize::set_gain_map` must do that
   conversion themselves — and the conversion is not trivial (Apple's
   log-space headroom encoding differs from ISO).
3. **No conformance test against Apple sample HEICs.** We need real iPhone
   HEIC files in `test-vectors/heic/` with known gain map parameters.

## No over-spec

`heic` does not invent HEIF boxes or properties. The Apple `aux_type` URN
it reads is real and documented in the iOS CoreImage headers.
