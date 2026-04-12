# Encoder-side audit — who writes gain map bytes

## Status: **metadata ownership is upstream**, no encoder-only bugs found

Unlike the parser audit, encoders in the zen workspace don't each build
their own ISO 21496-1 metadata. They take **pre-serialized bytes** and
wrap them in the container. The serializer question is pushed one layer
up — to whoever calls into the encoder.

This document traces who actually emits each kind of gain map byte sequence.

## Scope

| Crate | Role in encode | What it emits |
|---|---|---|
| `ravif` | higher-level AVIF encoder wrapping zenrav1e + zenavif-serialize | delegates |
| `zenrav1e` | AV1 still-image encoder | plain AV1 bitstream (no gain map concept) |
| `zenavif-serialize` | ISOBMFF muxer for AVIF | `tmap` item + `altr` group, payload is caller-provided |
| `zenavif` | high-level AVIF wrapper | calls ravif, uses zencodec presence flag |
| `ultrahdr-core` | UltraHDR compute + encode | **serializes ISO 21496-1 + hdrgm XMP** |
| `zenjpeg::ultrahdr` | JPEG UltraHDR encoder | **delegates to ultrahdr-core for metadata**, wraps in JPEG container |
| `jxl-encoder` | JPEG XL encoder | appends `jhgm` box with caller-provided payload |
| `zenjxl` | JXL wrapper | passes `jhgm_payload: Vec<u8>` through |
| `heic` (encode?) | n/a — decode-only at the moment | — |

## Metadata ownership chain

### JPEG UltraHDR encode

```
zenjpeg::ultrahdr::encode
    └─ ultrahdr_core::gainmap::compute_gainmap
    └─ ultrahdr_core::metadata::iso21496::serialize_iso21496  ← SERIALIZER HERE
    └─ ultrahdr_core::metadata::xmp::generate_gainmap_xmp     ← XMP HERE
    └─ ultrahdr_core::metadata::iso21496::create_iso_app2_marker
    └─ zenjpeg::encode → writes APP2 ISO + APP1 XMP + MPF + JPEG
```

**Serializer used:** `ultrahdr-core`'s own ISO 21496-1 writer. **Not**
zencodec's. This means deleting `ultrahdr-core/src/metadata/iso21496.rs`
(imazen/ultrahdr#4) requires migrating the encoder path to
`zencodec::gainmap::serialize_iso21496_fmt(_, JpegApp2)` at the same time
or the encode breaks.

**hdrgm XMP schema version:** hardcoded to `hdrgm:Version="1.0"` in
`generate_gainmap_xmp` (ultrahdr-core/src/metadata/xmp.rs:100). UltraHDR
v1.1 may use different semantics for some fields. Verify against libultrahdr
v1.4 output.

### AVIF `tmap` encode

```
user code / ultrahdr-core
    └─ serialize ISO 21496-1 metadata  (caller picks serializer)
           ↓
caller → ravif::Encoder::with_gain_map(GainMapData {
             av1_data,     // pre-encoded AV1 bitstream (via zenrav1e)
             width, height, bit_depth,
             metadata,     // pre-serialized ISO 21496-1 bytes
         })
    └─ zenavif_serialize::Aviffy::set_gain_map(av1_data, w, h, bit_depth, metadata)
    └─ writes `av01` gain map item + `tmap` derived item + `iref`/`grpl`
```

**Serializer used:** whatever the caller pre-computed. Today that's
ultrahdr-core for UltraHDR-derived files and `zenavif_parse::GainMapMetadata::to_bytes()`
for re-mux (which has the bugs documented in
[audit/zenavif.md](zenavif.md)).

### JXL `jhgm` encode

```
user code / ultrahdr-core
    └─ build JxlGainMapBundle-compatible byte sequence (caller's job)
           ↓
caller → zenjxl::codec::GainMapData { jhgm_payload: Vec<u8> }
    └─ jxl_encoder::container::append_gain_map_box(jxl_data, jhgm_payload)
    └─ writes ISOBMFF `jhgm` box at the end of the container
```

**Serializer used:** none in zen — caller builds the full `jhgm` payload
(version + metadata + color_encoding + alt_icc + gain_map_codestream)
themselves. Current callers either craft it manually or call libjxl via
FFI.

## Findings

### 1. No zen crate writes common-denominator ISO 21496-1 form ⚠️

Both `zencodec::gainmap::write_payload` and `ultrahdr-core::metadata::iso21496::write_payload`
always emit the full form. Common-denom is purely a space optimization
(libultrahdr uses it to save ~40 bytes per channel) and all readers that
handle common-denom also handle full form — so our output is interoperable,
just not byte-identical to libultrahdr output.

**Consequence:** we can't produce canonical libultrahdr-style bytes. If
a downstream test compares our AVIF `tmap` item bytes to a libultrahdr
golden, it will mismatch on the common-denom bit even when the metadata
is semantically equivalent. Document this in `audit/compliance-matrix.md`
as "read-only support for common-denom; writes full form".

**Tracked as compliance gap, not a bug.**

### 2. Metadata serializer switch needed when ultrahdr-core parser is deleted 🔁

[imazen/ultrahdr#4](https://github.com/imazen/ultrahdr/issues/4) deletes
`ultrahdr-core/src/metadata/iso21496.rs`. The parser AND the writer go
away together. zenjpeg's UltraHDR encoder (`zenjpeg/src/ultrahdr/encode.rs`)
currently consumes `ultrahdr_core::metadata::iso21496::serialize_iso21496`.

**Action:** when issue #4 lands, update `zenjpeg::ultrahdr::encode` to use
`zencodec::gainmap::serialize_iso21496_fmt(&params, Iso21496Format::JpegApp2)`
and preserve the existing `create_iso_app2_marker` as a thin wrapper that
prepends the `urn:iso:std:iso:21496-1\0` APP2 identifier.

### 3. hdrgm XMP schema version hardcoded to 1.0 ⚠️

`ultrahdr-core/src/metadata/xmp.rs:100` hardcodes `hdrgm:Version="1.0"`.
UltraHDR v1.1 (libultrahdr 1.1.0+, Aug 2024) aligned its field names with
ISO 21496-1 §5.2. The v1.0 schema and the v1.1 schema use the same field
*names* but the v1.1 schema is explicitly aligned with ISO 21496-1's
wire-level semantics.

**Question to resolve:** do we still emit v1.0 by choice, or because nobody
updated the constant? Check libultrahdr 1.4's output to see which version
it writes.

**Action:** add a `hdrgm_version: enum { V1_0, V1_1 }` parameter to
`generate_gainmap_xmp`, default to v1.1 for new encodes, keep v1.0 as a
legacy-compat option.

### 4. Writer does not propagate `FLAG_COMMON_DENOMINATOR` from parsed input ⚠️

If a caller parses a common-denom AVIF `tmap` via zencodec (which correctly
reads common-denom and expands to f64), then re-serializes, the output is
full-form regardless. The original wire-byte form is lost.

For pure re-mux (e.g., imageflow transforming a gain map JPEG into an AVIF
container), this is fine because the caller's going to a different container
anyway. For lossless round-trip (parse-then-reserialize the same file for
validation or transcode to same format), it's a wire-level data loss.

**Tracked as finding #1a in compliance-matrix.md:** consider adding a
raw-preserving encoder API to zencodec.

### 5. `zenrav1e` has no gain map awareness — correct ✅

zenrav1e is an AV1 still-image encoder. It encodes whatever grayscale or RGB
image you give it. The "gain map-ness" of that image is a property of the
container (AVIF's `tmap` + `iref` / JPEG's appended secondary), not the
AV1 codec. `zenrav1e` correctly treats a gain map image as a plain AV1 input.

**No action.** Keep it this way.

### 6. Encoder chain correctly keeps metadata upstream ✅

All three encoder paths (JPEG UltraHDR, AVIF tmap, JXL jhgm) correctly
separate "compute the gain map pixel data + metadata values" from "wrap
them in a container". The wrappers take pre-serialized bytes and don't
care what's inside. This means:

- Fixing the serializer (zencodec / ultrahdr-core) automatically fixes
  what all three encoders emit.
- Switching serializers is a one-line change at the caller, not a
  container-by-container rewrite.
- No encoder-layer drift risk — the serializer question is settled once
  per format at the caller layer.

This is the right design. Preserve it.

## Differential test gaps (encoder side)

We have parser round-trip tests via the 22-fixture matrix. We do **not**
have:

- **Encoder golden test**: encode a canned SDR+HDR pair via zenjpeg and
  compare the ISO 21496-1 APP2 + hdrgm XMP against a libultrahdr 1.4 output
  for the same input.
- **Encode then parse with libavif**: emit a `tmap` AVIF via zenavif and
  verify `avifgainmaputil` can decode it byte-for-byte.
- **Encode then parse with libjxl**: emit a `jhgm` JXL via jxl-encoder +
  `append_gain_map_box` and verify `djxl --ultrahdr-app` recovers the
  original HDR pair.

**Action:** add encoder golden test entries to
`gainmap-spec-status/test-vectors/encoder-golden/` with instructions for
producing them via libultrahdr / libavif / libjxl. Run them in CI once
the parser-side fixes land.

## Summary matrix — encoder side

| Crate | Serializer used | Writes common-denom? | hdrgm version | Status |
|---|---|---|---|---|
| zenjpeg::ultrahdr | ultrahdr-core | no | hardcoded 1.0 | ⚠️ needs migration post-ultrahdr#4 |
| zenavif / ravif | caller-provided | caller's choice | n/a | ✅ correct |
| zenavif-serialize | caller-provided blob | n/a | n/a | ✅ correct |
| zenjxl / jxl-encoder | caller-provided blob | n/a | n/a | ✅ correct |
| zenrav1e | n/a (AV1 codec only) | n/a | n/a | ✅ correct by design |

No over-spec: no encoder emits fields the ISO 21496-1 / UltraHDR v1.1 /
HEIF Amd 1 / libjxl `jhgm` specs don't define.

No dead code: every serializer / marker helper in ultrahdr-core has a
consumer in zenjpeg's encode path.

**The encoder side is in better shape than the parser side.** The only
active concerns are (a) migrating the serializer call site when ultrahdr-core's
parser is deleted, and (b) bumping the hdrgm XMP schema version to 1.1.
