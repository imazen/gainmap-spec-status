# gainmap-spec-status

A living map of gain map (HDR headroom) support across image format specifications,
cross-referenced with the zen family of image codecs.

## What is a gain map?

A **gain map** is an auxiliary per-pixel image that reconstructs an HDR rendering of
a baseline image by applying a per-pixel multiplier. It lets a single image file carry
both SDR and HDR representations with minimal size overhead, and lets the display
pick an interpolation point based on its available HDR headroom.

The canonical schema for gain map metadata (ratios, gamma, offsets, headroom,
color primaries) is **ISO 21496-1:2025**. Each image container is responsible only
for *how* to store the gain map pixel data, its metadata payload, and the association
between the base and alternate images.

## Status snapshot (2026-04-11; reviewed 2026-06-11 — see [REVIEW-2026-06-11-forever-api.md](REVIEW-2026-06-11-forever-api.md) for the full delta report)

| Format | Authority | Mechanism | Spec status | Ref impl |
|---|---|---|---|---|
| **JPEG / UltraHDR** | Google + Adobe (de-facto); ISO 21496-1 Annex C | XMP + MPF + appended JPEG gain map image | Shipping (UltraHDR v1.1) | `libultrahdr` 1.4.0 (stalled since 2025-01) |
| **AVIF** | AOM + ISO/IEC 23008-12 Amd 1 | HEIF `tmap` derived image item + `altr` entity group | Shipping (HEIF Amd 1:2025-10) | `libavif` 1.4.2 (Apple↔ISO conversion since 1.4.0) |
| **HEIC / HEIF** | ISO/IEC 23008-12 Amd 1 | same as AVIF; Apple camera files still use the proprietary aux item | Shipping (2025-10) | Apple only — libheif/Nokia have **no tmap** as of 1.23.0/3.7.1 |
| **JPEG XL** | JPEG WG1 / ISO 18181 | `jhgm` box (21496-1 blob + alt ICC + JXL codestream) | **Standardized: ISO/IEC 18181-2:2026 (3rd ed)** | `libjxl` ≥ 0.11 (Chrome 145 jxl-rs decodes JXL but not jhgm) |
| **PNG** | W3C PNG WG | `gMAP` + `gDAT` chunks (proposed) | Proposal still blocked on free 21496-1 text — but **Android 16 ships private `gmAP`+`gdAT`** (PNG-in-PNG) for HDR screenshots | Android 16 (private chunks) |
| **TIFF / DNG** | Adobe (DNG), ISO TC42 (TIFF/EP) | *(no standards track)* | No track — but Adobe writes de-facto ISO 21496-1 gain maps in TIF exports since Oct 2024 | Adobe ACR 17+ |

See [`specs/`](specs/) for per-format spec trace notes.
See [`specs/itu-r-bt2408-bt2390/`](specs/itu-r-bt2408-bt2390/) for the
ITU-R tone mapping and HDR production guidance that informs gain map
encoding: the BT.2408 EETF (Hermite spline), SDR-HDR mapping formulas,
reference white levels, HLG system gamma, and display adaptation.
See [`specs/os-rendering/`](specs/os-rendering/) for how platform
compositors (Android, Apple, Skia/Chrome, Windows) surface HDR headroom
and render gain maps at display time.
See [`audit/`](audit/) for the compliance audit against our zen crates,
including [`audit/zentone.md`](audit/zentone.md) for the tone mapping crate.
See [`test-vectors/`](test-vectors/) for cross-codec sample files and provenance.

## Layout

```
specs/
  iso-21496-1/     ISO 21496-1:2025 extracted text + field tables
  itu-r-bt2408-bt2390/  BT.2408 EETF, SDR-HDR mapping, ref white;
                        BT.2390 HLG gamma, OOTF, surround compensation
  png/             w3c/png#380, gMAP/gDAT proposal, #366 liaison
  avif-heif/       HEIF Amd 1, av1-avif tmap section, altr grouping
  jxl/             jhgm box, libjxl gain_map.h API
  tiff-dng/        status: no track + evidence
  apple/           APPLEDNG / AMPF / MakerNote variant
  adobe/           Camera Raw HDR / UltraHDR whitepaper lineage
  os-rendering/    display-side: Android libtonemap / Gainmap, Apple EDR,
                   Skia SkGainmapShader, Windows SDR content brightness
audit/
  compliance-matrix.md
  <crate>.md       per-zen-crate findings (including zentone)
test-vectors/
  jpeg/  avif/  jxl/  png/  tiff/
  sources/         upstream corpora + provenance
  manifest.toml    SHA256 + license + source per file
tools/
  generate-test-vectors.sh
  fetch-specs.sh
raw-pdfs/          downloaded PDFs (gitignored if >30kb)
```

## Why this repo exists

1. **Pin a moving target.** Every major format is in mid-flight on gain map
   support. This repo records the 2026-04 state so future sessions do not re-derive it.
2. **Drive zen compliance.** Our zen codec family (zenjpeg, zenavif, zenjxl,
   zenpng, zentiff, zenraw, ultrahdr, imageflow) ships or plans gain map
   support. The audit finds gaps and over-spec deviations.
3. **Shared test corpus.** Bug reproducers and interop tests need the same
   tiny files across codecs. This repo owns them once.

## Non-goals

- Not a spec itself. We cite, we do not propose.
- Not a tutorial. See the [UltraHDR overview](https://developer.android.com/media/platform/hdr-image-format) or
  [Greg Benz's write-up](https://gregbenzphotography.com/hdr-photos/iso-21496-1-gain-maps-share-hdr-photos/) for background.
- Not a benchmark. Sibling `codec-eval` and `zenbench` own that.
