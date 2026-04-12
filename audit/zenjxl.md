# zenjxl / zenjxl-decoder / jxl-encoder — JXL jhgm box binding

## Status: **compliant (parser)**, **compliant (writer)**, verify wire layout

Three crates:

- **zenjxl-decoder** — parses `jhgm` container boxes; produces `GainMapBundle`
  with raw metadata bytes, optional JXL ColorEncoding, optional Brotli-
  compressed alt ICC, and the bare JXL codestream of the gain map.
- **jxl-encoder** — writes `jhgm` container boxes via
  `container::append_gain_map_box(jxl_data, jhgm_payload)`.
- **zenjxl** — wraps both; exposes `GainMapBundle` for decode and
  `GainMapData` for encode.

## zenjxl-decoder

`~/work/zen/zenjxl-decoder/zenjxl-decoder/src/container/gain_map.rs`:

```rust
const JHGM_VERSION: u8 = 0x00;

pub struct GainMapBundle {
    /// ISO 21496-1 metadata blob (unparsed — caller uses ultrahdr-core / zencodec).
    pub metadata: Vec<u8>,
    /// JXL ColorEncoding (raw bit-packed JXL native), optional.
    pub color_encoding: Option<Vec<u8>>,
    /// Brotli-compressed ICC profile for the alternate rendition, optional.
    pub alt_icc_compressed: Option<Vec<u8>>,
    /// Bare JXL codestream of the gain map image (no container wrapper).
    pub gain_map_codestream: Vec<u8>,
}

impl GainMapBundle {
    pub fn parse(data: &[u8]) -> Result<Self>;  // consumes jhgm box payload
    pub fn serialize(&self) -> Vec<u8>;
}
```

### Wire format (from parser comment)

```
jhgm_version:            u8       // must be 0x00
gain_map_metadata_size:  u16 BE   // size of ISO 21496-1 metadata
gain_map_metadata:       [u8; N]  // ISO 21496-1 binary metadata
color_encoding_size:     u8       // 0 = absent; else byte count
color_encoding:          [u8; M]  // JXL ColorEncoding (optional)
alt_icc_size:            u32 BE   // size of Brotli-compressed ICC
alt_icc:                 [u8; K]  // Brotli-compressed ICC (optional)
gain_map:                [u8; *]  // remaining bytes = bare JXL codestream
```

### Compliance notes

The parser matches what libjxl's `jhgm` reader accepts *in practice*. Two
open points:

1. **`color_encoding_size: u8` framing.** libjxl's public API exposes
   `JxlColorEncoding` as a struct, and internally libjxl writes it with JXL
   native bit-packing. We carry it as a length-prefixed byte blob and re-read
   it verbatim. Verify against a real libjxl-produced `jhgm` box (see
   `test-vectors/jxl/`).
2. **No explicit `gain_map_size` prefix.** We compute the gain map size
   from the box length minus header. This matches libjxl's implicit
   end-of-box encoding.

### Gaps

- **No cross-impl test** against libjxl's native `JxlGainMapWriteBundle` /
  `JxlGainMapReadBundle`. Needed for byte-level conformance.
- **Box-at-end assumption.** `append_gain_map_box` only appends — if a
  producer places `jhgm` mid-file, the decoder should still find it. Confirm
  the box parser scans the full file, not just the tail.
- **No test of the `alt_icc` Brotli decompression** — we store compressed
  bytes but never decompress in-crate; consumers must call `brotli-decompress`
  themselves. Document this explicitly.

## jxl-encoder

`~/work/zen/jxl-encoder/jxl-encoder/src/container.rs:219`:

```rust
/// Append a `jhgm` box to JXL data (container or bare codestream).
pub fn append_gain_map_box(jxl_data: &[u8], jhgm_payload: &[u8]) -> Vec<u8>;
```

Behavior:

- If `jxl_data` is already an ISOBMFF-style JXL container: appends a new
  `jhgm` box at the end with `size = 8 + payload_len`, 4-byte type `jhgm`.
- If `jxl_data` is a bare codestream: wraps it in a container first, then
  appends the `jhgm` box.

### Compliance

- 4-byte box type `jhgm` matches libjxl convention.
- 8-byte header (size + type) matches ISOBMFF.
- No validation of the `jhgm_payload` content — caller must supply the
  correct wire format. This is correct separation of concerns.

### Gaps

- **No support for the box-with-extended-size (64-bit length) variant.**
  Gain map payloads of >2 GB (unlikely but possible for high-res float
  gain maps) would need large-box encoding. Not implemented.
- **No deduplication** — appending twice produces two `jhgm` boxes. Should
  either fail loudly or replace.

## zenjxl

`~/work/zen/zenjxl/src/codec.rs` exposes:

```rust
pub struct GainMapData {
    pub jhgm_payload: Vec<u8>,  // serialized jhgm box payload
}

pub struct JxlEncoderConfig {
    gain_map: Option<Arc<GainMapData>>,
    ...
}

impl JxlEncoderConfig {
    pub fn with_gain_map(self, gm: Option<Arc<GainMapData>>) -> Self;
}
```

Decode path exposes `JxlInfo::gain_map: Option<GainMapBundle>` via
`take_gain_map()` on the inner decoder.

### Compliance

- Encode path takes a pre-serialized blob, so it cannot introduce wire-format
  bugs of its own — correctness is delegated to whoever builds the payload.
- Decode path returns the raw metadata blob to the caller for separate ISO
  21496-1 parsing via `zencodec::gainmap::parse_iso21496_fmt(_, JpegApp2)`.

### Gaps

- **No built-in gain map compute.** zenjxl cannot produce a gain map from
  an HDR+SDR pair on its own; the caller must use `ultrahdr-core::gainmap::compute_gainmap`
  first, then wrap the result. Consider exposing a `zenjxl::compute_and_attach_gain_map`
  convenience.
- **No `zencodec::GainMapParams` bridge.** zenjxl returns
  `GainMapBundle { metadata: Vec<u8>, ... }` — to get parsed fields the
  caller has to cross the zencodec boundary manually. A `TryFrom<&GainMapBundle>
  for zencodec::GainMapParams` would be ergonomic.

## No over-spec

All three crates restrict themselves to fields the libjxl `jhgm` layout
defines. No JXL-private extensions. The "base image is HDR" direction
assumption documented in `zenjxl/src/decode.rs:178` is the
`FLAG_BACKWARD_DIRECTION` bit and is correct per ISO 21496-1.
