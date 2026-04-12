# ISO 21496-1:2025 — Digital photography — Gain map metadata for image conversion — Part 1: Dynamic range conversion

## Identification

- **Reference:** ISO 21496-1:2025(en), First edition, 2025-07
- **Committee:** ISO/TC 42 (Photography)
- **Stage:** 60.60 (International Standard published)
- **Catalogue:** https://www.iso.org/standard/86775.html
- **Preview (4 pages, free):** https://cdn.standards.iteh.ai/samples/iso/iso-21496-1-2025/68ae6692b5aa4801bfbe336871c47b52/iso-21496-1-2025.pdf

## Why this is the root document

Every other format-specific gain map binding — the HEIF `tmap`, the JXL `jhgm`
box, the UltraHDR XMP schema, the proposed PNG `gMAP` chunk — carries, as its
normative payload, an ISO 21496-1 metadata record. Container specs argue only
about **where** to put the blob and **how** to link it to the base image.

## Table of contents (from free sample)

```
Foreword                                                          iv
Introduction                                                       v
1   Scope                                                          1
2   Normative references                                           1
3   Terms, definitions, and acronyms                               1
4   Gain map requirements                                          2
    4.1 General
    4.2 Gain map dimensions
    4.3 Gain map colour components
    4.4 Gain map quantization
    4.5 Orientation
5   Metadata                                                       4
    5.1 General
    5.2 Gain map metadata
        5.2.1 General
        5.2.2 Dimensions
        5.2.3 Quantization
        5.2.4 Number of gain map components
        5.2.5 Per-component metadata
        5.2.6 Baseline high dynamic range headroom
        5.2.7 Alternate HDR headroom
        5.2.8 Version tag
    5.3 Colorimetry metadata
        5.3.1 General
        5.3.2 Baseline image colorimetry metadata
        5.3.3 Alternate image colorimetry metadata
        5.3.4 Gain map application space colour primaries metadata
6   Gain map application                                           6
    6.1 General
    6.2 Processing the gain map
        6.2.1 Unnormalizing the gain map
        6.2.2 Resampling the gain map
    6.3 Applying the gain map
Annex A (informative) Computing the gain map                       8
Annex B (normative)   Colour conversion                           10
Annex C (normative)   Storing the gain map                        11
Bibliography                                                      15
```

## What each section does

- **§4 Gain map requirements** — data-plane constraints: number of components
  (1 or 3), dimensions relative to base (same, half, quarter, or arbitrary),
  quantization (uint8 or float16), orientation matching the base image.
- **§5 Metadata** — the normative field set that every binding serializes:
  - per-component: `min_log2`, `max_log2`, `gamma`, `base_offset`,
    `alternate_offset`
  - image-global: `base_hdr_headroom`, `alternate_hdr_headroom`, version byte,
    base-is-HDR flag (derived from headroom ordering)
  - colorimetry: base primaries, alternate primaries, *application space*
    primaries (where the multiply happens)
- **§6 Gain map application** — the canonical evaluation function:
  `log_gain = mix(min_log2, max_log2, recovery)`; `gain = 2^log_gain`;
  `alt = (base + base_offset) * gain - alt_offset`. Scale by current display
  headroom ratio in log space before evaluating. See
  [`apply-math-and-banding.md`](apply-math-and-banding.md) for the fully
  verified formula with every field sourced, a discussion of the
  display-weight factor, what the offsets are actually for, and where
  banding enters the pipeline.
- **Annex B (normative)** — colour space conversions to get into the
  application space before the multiply.
- **Annex C (normative)** — container bindings. This is where 21496-1 tells
  JPEG/AVIF/HEIF/JXL implementers how to wrap the metadata. The sample PDF
  truncates before page 11, so the binding details are not public. We derive
  them from the container specs that cite this annex (HEIF Amd 1, libjxl
  `jhgm`, UltraHDR XMP).

## What is deliberately NOT covered

- **No PNG binding in Annex C** — PNG is not in the bibliography of 21496-1:2025.
  W3C is drafting gMAP/gDAT independently (see `specs/png/`).
- **No TIFF binding in Annex C.** No proposal is in flight at ISO TC42 or Adobe.
- **No gain curve** — that is a separate proposal (SMPTE ST 2094-50 / AOM gain
  curves) and is targeted at Part 2 or a separate standard.
- **No patent disclosure text** — 21496-1 lists a known patent (likely the
  Adobe / Google / Apple UltraHDR lineage) without specifying claims.
  Implementers are warned.

## Free excerpt fidelity

The iTeh 4-page sample captured in `raw-pdfs/iso-21496-1-2025-sample.pdf` and
extracted to `extracted.md` (via `pdf-oxide markdown`) covers the foreword and
TOC only. Normative clauses §4–§6 and Annexes A–C are paywalled.

## Current interpretation by container specs

| Binding | Carried as | Fields exposed |
|---|---|---|
| HEIF `tmap` | typed box inside the `tmap` derived item payload | all §5 fields |
| JXL `jhgm` | versioned box: `u8 version | u16 meta_size | <21496-1 blob> | ICC | codestream` | all §5 fields |
| UltraHDR XMP | named XMP properties in `hdrgm:` namespace | subset — older schema, predates 21496-1 naming |
| PNG gMAP (proposed) | chunk with fields matching §5 | all §5, debated |
| TIFF | *(none)* | — |

The UltraHDR v1.0 XMP schema predates 21496-1 and uses slightly different
field names and a different gain range encoding. UltraHDR v1.1 is aligned.
libultrahdr 1.3+ reads both.
