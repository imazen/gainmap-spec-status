# Apple HDR Gain Map — vendor-specific binding

## Status: Apple-only, not a spec

Apple ships HDR photos with gain maps from iPhone cameras since iOS 14+ in
two flavours. Neither is normative, but both are widely deployed and we parse
them in `zenraw` and `zenjpeg`.

## 1. Apple HDR Gain Map in JPEG (iOS 14+)

- **Container:** Plain JFIF JPEG with multi-picture format (`MPF`) APP2
  segments *plus* XMP APP1 extension segments.
- **MPF entries:** Primary image (SDR) and a second image item containing
  the gain map, packed inline.
- **XMP namespace:** `http://ns.apple.com/Photo/1.0/` — carries `HDRGain`,
  `AppleMakerNote`, and related keys.
- **Metadata shape:** A variant of the Adobe/Google UltraHDR schema; Apple
  uses its own transfer function and hdr_capacity encoding.

## 2. Apple HDR in AMPF (iPhone 17 Pro, 2025)

- **Container:** DNG-like `APPLEDNG` / `AMPF` (`AMPF` = Apple Media Photo
  Format) — a private ISOBMFF-style wrapper around a JPEG + HDR gain map.
- **Path:** iPhone 17 Pro `.DNG` files that are *not* raw Bayer but a full
  rendered JPEG + gain map pair, compressed with JPEG per tile.
- **Signal:** Apple MakerNote blob in the EXIF IFD carries gain map metadata.

## 3. Apple ProRAW (iPhone 12 Pro+)

- **Container:** DNG 1.6, LinearRaw, LJPEG predictor 7.
- **Gain map:** Not in the raw data path. If HDR is wanted, the rendered
  AMPF JPEG is used instead (case 2).

## Where we parse this

- `~/work/zen/zenraw/src/apple.rs` — feature `apple` — extracts:
  - Apple MakerNote (`IFD/MakerNote` = tag 37500 in EXIF)
  - DNG preview extraction
  - Semantic matte SubIFDs
  - Gain map signal detection
  See `audit/zenraw.md` for compliance.
- `~/work/zen/ultrahdr/` — Safe Rust wrapper around libultrahdr for reading
  Apple JPEG + gain map files as a UltraHDR-compatible path (lossy conversion
  at ingest). See `audit/ultrahdr.md`.

## Relationship to ISO 21496-1

Apple's internal gain map metadata is **similar but not identical** to
ISO 21496-1. Conversion requires:

1. Mapping Apple's per-channel log gain range to 21496-1 `min_log2`/`max_log2`.
2. Mapping Apple's `HDRGainMapHeadroom` to 21496-1 `alternate_hdr_headroom`.
3. Handling Apple's single-channel gain map (the common case) vs 21496-1's
   per-channel allowance.
4. Assuming Apple's "base" colour space is Display P3 and the alternate
   is BT.2020 PQ, which should be recorded explicitly in the 21496-1
   colorimetry fields.

libavif did this conversion in #2944/#2960. We follow the same formulas.

## Do not extend beyond what Apple ships

There is no published Apple spec. We **do not** guess at fields Apple hasn't
shipped. If a field is not present in an Apple file, treat it as missing, not
as a default. Over-spec here means silently fabricating metadata that will
fail to round-trip through Apple's own tools.
