# AVIF / HEIF — gain map binding status

## Authority stack

Two specs cooperate. AVIF defers all gain map plumbing to HEIF.

1. **ISO/IEC 23008-12:2025** (HEIF, Image File Format)
   + **Amendment 1:2025** *"Support for tone map derivation and other technologies"*
   https://webstore.iec.ch/en/publication/110118
2. **AV1 Image File Format (AVIF)** — AOMediaCodec community spec
   https://aomediacodec.github.io/av1-avif/

## Status: shipping

- HEIF Amendment 1 published **2025-10**, stage 60.60.
- AVIF normative reference uses HEIF `"ISO/IEC 23008-12:2025/Amd 1"`.
- Reference implementation `libavif` ships encode + decode + `avifgainmaputil`
  since mid-2024, and added Apple JPEG gain map interop in Jan 2026
  (libavif issues #2944, #2960).

## Mechanism — `tmap` derived image item

The gain map lives as its own **image item** in the ISOBMFF container. The
base image and the `tmap` item are tied together with an `altr` entity group.

```
iinf / iloc / iprp entries:
   item 1: av01  base image (primary)
   item 2: av01  gain map   (hidden via 'aux' role or flags)
   item 3: tmap  derived — references items 1 and 2 via 'dimg'

grpl:
   altr entity group { item 1, item 3 }   // player picks one
```

Renderer picks either item 1 (the bare base image) or item 3 (the derived
tone-mapped rendering using the gain map) based on the display's HDR
headroom.

### Normative requirements from av1-avif §4.2.2

> A *tone map derived image item* (`tmap`) as defined in HEIF may be used in an
> AVIF file. When present, the base image item and the `tmap` image item
> should be grouped together by an `altr` entity group as recommended in HEIF.
> When present, the gain map image item should be a hidden image item.

Merged via [AV1-AVIF PR #239](https://github.com/AOMediaCodec/av1-avif/pull/239)
on 2024-09-17 (closes #237).

## Metadata payload

The `tmap` derived item carries an ISO 21496-1 metadata blob in its sample.
All §5 fields (min/max log2 per channel, gamma, offsets, base headroom,
alternate headroom, colorimetry) are encoded normatively. HEIF Amd 1 defines
the exact byte layout; we don't have the free text, but libavif's
`avif/internal.h` + `gainmap.c` (see `audit/libavif-reference.md`) implements
a readable version of the layout.

## Key implementation APIs (libavif, our reference)

- `avifGainMap` struct: per-channel min/max/gamma/base_offset/alt_offset
  as 32-bit rationals (numerator/denominator), base/alternate headroom,
  use_base_colorspace flag, alt_icc, alt_color_primaries, etc.
- `avifGainMapMetadata` — the on-wire form
- `avifImageApplyGainMap` — applies the gain map to produce the alternate
- `avifDecoderFindGainMapItem` — locates the tmap item in the iref graph
- `avifgainmaputil` CLI — convert, combine, extract, apply

## AVIF-specific constraints we've seen in practice

- Gain map grid images are supported but tricky. libavif #2397 tracks
  "Allow creating images with a different grid for the gain map" — the gain
  map can have its own grid dimensions from the base image.
- `avifgainmaputil combine` / `convert` gates the CICP propagation
  (libavif #3110, fixed 2026-03).
- `altICC` leaks if `avifDecoderFindGainMapItem` returns early (libavif #3127,
  fixed 2026-03).
- Gain map channel count: 1 or 3 (ISO 21496-1 §4.3 compliant).
- Gain map bit depth: 8 or 10 typically; HEIF Amd 1 allows more but AVIF
  encoders generally stick to 8.

## Apple JPEG → AVIF interop

libavif #2944 / #2960 landed (Jan 2026) adding:
- read Apple `mpf` / XMP gain map from JPEG
- repackage into AVIF `tmap` form
This is what ties `zenraw`'s Apple DNG/ProRAW gain map parsing to the
AVIF output path.

## Implication for `zenavif` / `zenavif-parse` / `zenavif-serialize`

All three should support:
- Parsing a `tmap` derived image item from `iref`
- Extracting the ISO 21496-1 metadata blob
- Exposing an alt-image primary colour / headroom surface
- Writing a `tmap` + `altr` entity group for the encode path

See `audit/zenavif.md`, `audit/zenavif-parse.md`, `audit/zenavif-serialize.md`.
