# zenavif / zenavif-parse / zenavif-serialize — AVIF tmap binding

## Status: **compliant**, structurally correct

Three crates cooperate on the AVIF `tmap` binding:

- **zenavif-parse** — demuxes an AVIF file and extracts gain map data from
  `tmap` derived image items.
- **zenavif-serialize** — muxes a `tmap` derived item + `av01` gain map item +
  `altr` entity group back into an AVIF file.
- **zenavif** — high-level wrapper using `rav1d-safe` for AV1 decode and
  `zenrav1e` for AV1 encode, stitching parse/serialize with actual pixel data.

## zenavif-parse

`zenavif-parse/src/lib.rs` defines:

```rust
pub struct GainMapChannel {
    pub gain_map_min_n: i32,   gain_map_min_d: u32,
    pub gain_map_max_n: i32,   gain_map_max_d: u32,
    pub gamma_n: u32,          gamma_d: u32,
    pub base_offset_n: i32,    base_offset_d: u32,
    pub alternate_offset_n: i32, alternate_offset_d: u32,
}
pub struct GainMapMetadata {
    pub is_multichannel: bool,
    pub use_base_color_space: bool,
    pub backward_direction: bool,
    pub base_hdr_headroom_n: u32, base_hdr_headroom_d: u32,
    pub alternate_hdr_headroom_n: u32, alternate_hdr_headroom_d: u32,
    pub channels: [GainMapChannel; 3],
}
impl GainMapMetadata {
    pub fn parse_tmap_bytes(data: &[u8]) -> Result<Self>;
    pub fn serialize_tmap_bytes(&self) -> Vec<u8>;
}
impl From<&GainMapMetadata> for zencodec::GainMapParams { ... }
impl From<&zencodec::GainMapParams> for GainMapMetadata { ... }
```

This is an **independent representation using raw integer fractions** (more
faithful to the wire format than zencodec's f64-converted form) with explicit
`From` conversions to/from zencodec. Good separation — avoids lossy f64
roundtrip for byte-exact serialization.

### Compliance

- Accepts only fields ISO 21496-1 §5.2 defines.
- Uses the AVIF (`tmap`) wire variant with the `version(u8)` byte prefix.
- Round-trips via zencodec::GainMapParams for pipeline consumers.

### Gaps

- **Byte-exact round-trip test exists** (see `zenavif-parse/CHANGELOG.md`
  "Gain map byte-exact and backward_direction parity tests"). Good.
- **Gain map grid items not tested.** libavif #2397 allows gain map items
  with their own `grid` derivation. We should add a parse test for a
  multi-tile gain map.
- **No `altr` group test** — verify the parser reads the base ↔ tmap entity
  group pairing correctly.

## zenavif-serialize

`zenavif-serialize/src/lib.rs` defines an internal `GainMapConfig`:

```rust
struct GainMapConfig {
    av1_data: Vec<u8>,   // AV1-encoded gain map image
    width: u32, height: u32, bit_depth: u8,
    metadata: Vec<u8>,   // pre-serialized ISO 21496-1 tmap payload
    alt_colr: Option<ColrBox>,
    chroma_subsampling: ChromaSubsampling,
    monochrome: bool,
}
```

Exposed via the builder:

```rust
impl Aviffy {
    pub fn set_gain_map(&mut self, av1: Vec<u8>, w: u32, h: u32, bit_depth: u8, metadata: Vec<u8>) -> &mut Self;
    pub fn set_gain_map_alt_colr(&mut self, colr: ColrBox) -> &mut Self;
    pub fn set_gain_map_chroma_subsampling(&mut self, s: ChromaSubsampling) -> &mut Self;
    pub fn set_gain_map_monochrome(&mut self, m: bool) -> &mut Self;
}
```

On serialize (`lib.rs:605+`):

1. Assigns a new item ID to the gain map `av01` item.
2. Assigns a new item ID to the `tmap` derived item.
3. Writes the `av01` item with its `ispe`, `av1C`, `pixi`, `colr` properties
   (optional `alt_colr` on the tmap item).
4. Writes the `tmap` item whose payload is the raw `metadata` blob provided
   by the caller.
5. Writes an `iref` `dimg` entry from the `tmap` item pointing to the
   primary image + gain map image.
6. Writes an `altr` entity group pairing the primary with the `tmap` item.
7. Writes the gain map AV1 data to `iloc` alongside the primary image data.

### Compliance with HEIF Amendment 1 + av1-avif §4.2.2

| Requirement | Implementation |
|---|---|
| `tmap` derived item present | ✅ item 2 in the builder |
| `tmap` references base + gain via `dimg` | ✅ `iref.dimg` with two entries |
| `altr` entity group pairs base + `tmap` | ✅ `grpl.altr` |
| Gain map item hidden | ⚠️ **verify** — check the `iinf.hidden` flag setting |
| ISO 21496-1 payload is `tmap` item data | ✅ `metadata: Vec<u8>` passed through |
| CICP on `tmap` or alt-image | ✅ optional `alt_colr` → ColrBox property on tmap |

### Gaps

- **Verify the gain map image item is marked hidden.** AVIF spec §4.2.2
  says "the gain map image item should be a hidden image item". Need to
  grep `iinf.hidden` or the flags byte to confirm.
- **No `clli` / `mdcv` on the alt image item** — if the HDR side carries
  mastering display + content light-level metadata, the tmap-side properties
  should propagate. Track as a follow-up.
- **Multi-channel gain map writing** — confirm `is_multichannel` flag in
  the serialized metadata matches whether the caller provided a monochrome
  or 3-channel gain map image.

## zenavif

`zenavif/src/codec.rs` wraps the decode/encode pipeline and plumbs
`GainMapMetadata` from `zenavif-parse` to zenpipe. No additional wire-format
logic lives here.

## No over-spec

None of the three crates expose private gain map fields beyond ISO 21496-1 /
HEIF Amd 1 / av1-avif. The `GainMapConfig` struct's `alt_colr`,
`chroma_subsampling`, and `monochrome` fields are all legitimate HEIF item
properties, not AVIF-private extensions.
