# JPEG XL — `jhgm` gain map box status

## Authority

- **Reference implementation:** `libjxl` (https://github.com/libjxl/libjxl)
- **Standard:** ISO/IEC 18181 — JPEG XL (managed by JPEG WG1 = ISO/IEC JTC 1/SC 29/WG 1)
- **Metadata payload:** ISO 21496-1:2025 binary blob (same as HEIF / AVIF)

## Status: reference-impl-first

`libjxl` merged `jhgm` box support on **2024-06-04** via
[PR #3552 "add jhgm box and basic gain map support"](https://github.com/libjxl/libjxl/pull/3552).
A reader was added to `jxlinfo` via
[PR #3654](https://github.com/libjxl/libjxl/pull/3654).
DisplayP3 + ultrahdr_app interop followed via
[PR #4210](https://github.com/libjxl/libjxl/pull/4210) (2025-04).

Whether the ISO/IEC 18181 series has a published amendment adding `jhgm` is
not clear from public sources. The libjxl code is the de-facto reference.

## `jhgm` box layout (from libjxl public API)

From `lib/include/jxl/gain_map.h`:

```c
typedef struct {
    // Version number of the gain map bundle
    uint8_t  jhgm_version;

    // ISO 21496-1 metadata (binary blob)
    uint16_t gain_map_metadata_size;
    const uint8_t* gain_map_metadata;     // § of 21496-1

    // Optional alternate color encoding (pre-ICC hint)
    JXL_BOOL          has_color_encoding;
    JxlColorEncoding  color_encoding;

    // Optional compressed alternate ICC profile
    uint32_t       alt_icc_size;
    const uint8_t* alt_icc;

    // Gain map as a naked JPEG XL codestream
    uint32_t       gain_map_size;
    const uint8_t* gain_map;
} JxlGainMapBundle;
```

Public entry points:
- `JxlGainMapGetBundleSize` — compute serialized length
- `JxlGainMapWriteBundle`  / `JxlGainMapReadBundle` — serialize / parse

The gain map itself is a **naked JXL codestream** (not a full ISOBMFF-wrapped
JXL file). libjxl reuses its decoder with a narrow entry point.

## Key fields

| Field | Meaning | Source |
|---|---|---|
| `jhgm_version` | bundle format version (currently 1) | libjxl |
| `gain_map_metadata` | ISO 21496-1 §5 binary encoding | 21496-1 Annex C |
| `has_color_encoding` | whether inline `JxlColorEncoding` present | libjxl opt |
| `alt_icc` | compressed alt ICC profile (zlib? brotli? check impl) | libjxl opt |
| `gain_map` | JXL codestream carrying the gain map pixels | libjxl |

## Container placement

The `jhgm` box goes alongside the other JXL container boxes (`jxlc`, `jxli`,
`xml `, etc.) in the JXL ISOBMFF-style container. It is **not** nested inside
the `jxlc` codestream.

## Interop path: UltraHDR → JXL

`cjxl` supports reading an UltraHDR JPEG and producing a JXL with a `jhgm`
box whose metadata is populated from the source JPEG's XMP. See libjxl
[#4210 "output in DisplayP3, add option for producing ultrahdr_app input"](https://github.com/libjxl/libjxl/pull/4210).

## Outstanding items

- libjxl #4588 "UltraHDR jpeg with gain map doesn't convert properly?" — open
  bug on the conversion path, last updated 2026-02.
- ISO 18181 amendment status: unknown. No public pointer to an ISO SC29/WG1
  document describing `jhgm` as a normative extension.

## Implication for `zenjxl` / `zenjxl-decoder` / `jxl-encoder`

- `zenjxl-decoder` (pure Rust, BSD-3) needs a `jhgm` box parser producing a
  `GainMapBundle` struct analogous to libjxl.
- `jxl-encoder` (pure Rust, AGPL) needs a `jhgm` writer for the encode path.
- `zenjxl` (the wrapper) should expose a unified `GainMap` type that aligns
  with the one in `audit/compliance-matrix.md`.

See `audit/zenjxl*.md`.
