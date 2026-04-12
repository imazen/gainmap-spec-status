# Adobe / Google UltraHDR — de-facto JPEG gain map binding

## Status: shipping widely, pre-standard, now aligned with ISO 21496-1

UltraHDR is the JPEG + gain map format that Google, Adobe, and Samsung ship
on Android 14+, macOS Sonoma, Chrome 116+, and Lightroom / Camera Raw.

The lineage:

1. **2023-08** Adobe publishes the "HDR Gain Map" white paper.
2. **2023-11** Google ships UltraHDR v1.0 on Pixel 8 (Android 14).
3. **2024-01-05** Google publishes the Ultra HDR Image Format specification
   on developer.android.com: https://developer.android.com/media/platform/hdr-image-format
4. **2024-08** libultrahdr 1.1.0 — multi-channel gain maps.
5. **2024-11** libultrahdr 1.3.0 — half-float support.
6. **2025-01** libultrahdr 1.4.0 — per-channel content boost, alt-colorspace
   support, low-light fixes.
7. **2025-07** ISO 21496-1:2025 published — Annex C defines the normative
   JPEG binding that UltraHDR v1.1+ follows.

## Mechanism — JPEG + GContainer + MPF

An UltraHDR JPEG file is a standard JFIF JPEG whose XMP APP1 segment carries
`GContainer` metadata describing one or more secondary media files appended
to the primary image. One of those secondary files is the gain map, itself
encoded as a JPEG.

```
+-----------------------------+  SOI
| APP1 XMP (primary GContainer)|  <item>gainmap  mime=image/jpeg  length=N</item>
| APP1 XMP (hdrgm: metadata)   |  min, max, gamma, offsets, headroom
| APP2 MPF                     |  references secondary image offset
|                              |
|         primary JPEG         |
|                              |
|                              |
+-----------------------------+  EOI  (primary ends)
|         gain map JPEG        |  (secondary, appended bytes)
+-----------------------------+  EOI
```

Legacy JPEG readers see only the primary image. Gain-map-aware readers
follow the `GContainer` pointer, decode the secondary JPEG, combine.

## Metadata namespaces

- `hdrgm:` — original Adobe/Google UltraHDR metadata
  (https://helpx.adobe.com/camera-raw/using/gain-map.html)
- `Item:` / `Container:` — Google GContainer XMP namespace
  (https://developer.android.com/media/platform/hdr-image-format)

As of UltraHDR v1.1, the `hdrgm:` field names are aligned with ISO 21496-1
§5.2 field names. v1.0 had subtly different encodings for the gain range.

## Field mapping (hdrgm → ISO 21496-1)

| hdrgm XMP key | ISO 21496-1 §5.2 field |
|---|---|
| `Version` | version tag |
| `BaseRenditionIsHDR` | derived from `BaseHDRHeadroom > AlternateHDRHeadroom` |
| `HDRCapacityMin` | `base_hdr_headroom` (log2) |
| `HDRCapacityMax` | `alternate_hdr_headroom` (log2) |
| `GainMapMin` | `min_log2` (per channel) |
| `GainMapMax` | `max_log2` (per channel) |
| `Gamma` | `gamma` (per channel) |
| `OffsetSDR` | `base_offset` (per channel) |
| `OffsetHDR` | `alternate_offset` (per channel) |

## Reference implementations we use

- `libultrahdr` (Google, Apache-2.0) — C++
- `ultrahdr-rs` / `zen/ultrahdr/` — our safe Rust wrapper + CLI
- `libjxl` `cjxl --ultrahdr-app` — convert to JXL `jhgm`
- `libavif` `avifgainmaputil` — convert to AVIF `tmap`

## Interop constraints

1. **The gain map JPEG inside the primary JPEG is a JFIF JPEG.** Some
   readers assume YCbCr, some expect grayscale. libultrahdr uses 1-channel
   for single-channel maps.
2. **XMP parsing is finicky.** The `hdrgm:` namespace must be declared in
   the XMP packet header or readers silently ignore the fields.
3. **Order matters:** primary XMP must come before MPF APP2.
4. **Byte offsets in GContainer are absolute** from the start of the
   primary image (i.e., from SOI), not from the end of primary's EOI.
5. **Transfer function:** primary is typically sRGB or DisplayP3; gain map
   is `linear` or `gamma-encoded` per the `Gamma` field.

## Implication for `ultrahdr`, `zenjpeg`, and `imageflow`

- `ultrahdr` (our wrapper): must expose both the v1.0 and v1.1 hdrgm field
  encodings. See `audit/ultrahdr.md`.
- `zenjpeg`: should detect a UltraHDR-bearing JPEG via XMP sniffing and
  expose `GainMap` metadata without forcing a decode of the secondary JPEG.
- `imageflow`: when resizing/transforming a UltraHDR JPEG, the gain map
  must be resampled in lockstep, or stripped with a warning.
