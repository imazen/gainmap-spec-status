# TIFF / DNG — gain map binding status

## Status: no active track

**There is no gain map specification for TIFF or DNG as of 2026-04.** This
document exists to record what we checked and where the gap is.

## Authorities checked

| Spec | Responsible | Gain map? |
|---|---|---|
| TIFF 6.0 (1992) | Aldus → Adobe | No — predates HDR gain maps |
| TIFF/EP (ISO 12234-2) | ISO TC 42 | No — camera-raw focused |
| BigTIFF | community (LibTIFF) | No |
| DNG 1.7.1 (Sep 2024) | Adobe | No gain map tags defined |
| Adobe Camera Raw HDR | Adobe | JPEG/AVIF/HEIF only, not DNG |
| ISO 21496-1:2025 Annex C | ISO TC 42 | **TIFF not listed** as a container target |

## Evidence

1. **DNG 1.7.1 spec.** The Adobe DNG 1.7.1 specification (Sep 2024) does not
   define any gain map tags. No `GainMap*` entries in its tag table.
2. **ISO 21496-1 Annex C.** The normative storage annex lists JPEG, HEIF,
   AVIF, JXL bindings. TIFF is absent. (Confirmed indirectly: no TIFF refs in
   the free sample PDF's bibliography or TOC; format bindings in container
   specs all cite the same annex without mentioning TIFF.)
3. **No Adobe Camera Raw path.** ACR will read a gain map from a JPEG or
   AVIF but exports HDR *without* a gain map to DNG. Source: Greg Benz
   writeups (https://gregbenzphotography.com/hdr-photos/iso-21496-1-gain-maps-share-hdr-photos/).
4. **No open issues in LibTIFF or tiff-tools** tracking gain map storage.
5. **ImageMagick issue #6377** "Add support for HDR gain maps" explicitly
   scopes JPEG/AVIF/HEIF, not TIFF.

## What people do today

For TIFF they do one of:

1. **Sidecar JPEG/AVIF.** Store the HDR rendering in a separate file.
2. **Private IFD tags.** Adobe stores `DNGPrivateData` in DNG with arbitrary
   Adobe-defined blobs. Some experimental gain map storage schemes pack an
   ISO 21496-1 metadata record here, but there is no agreed shape.
3. **SubIFD with a raw gain map image.** Some ExpertRAW-style Android raws
   (Samsung Galaxy Z Fold7, iPhone ProRAW) ship a gain map *semantically*,
   either as Apple's MakerNote blob (iPhone) or as an undocumented Samsung
   private IFD. Neither is a spec; both are reverse-engineered.

`zenraw` parses the Apple MakerNote path in `src/apple.rs` — that's the
closest any zen crate comes to TIFF-adjacent gain map handling.

## The actual gap

For TIFF to support gain maps via a canonical binding, one of the following
needs to happen:

- **Adobe** publishes a DNG 1.8 with `GainMap*` tags mirroring ISO 21496-1.
- **ISO TC 42** amends 21496-1 Annex C to add a TIFF IFD binding.
- **LibTIFF** community assigns tag range and ships a reference encoder/decoder.

None of these are in flight as of 2026-04. The feature is effectively
orphaned.

## Implication for `zentiff` / `image-tiff` / `zenraw`

- `zentiff` and `image-tiff`: no gain map API. Correct — matches the spec
  state. Do **not** invent private tags.
- `zenraw`: continue parsing Apple MakerNote gain map fields as vendor
  metadata. Mark them as *Apple-specific* in the type system, not as
  canonical ISO 21496-1 records, until a spec binding exists.
- `zenpipe` and `zencodec`: the `GainMap` type should deliberately omit a
  TIFF binding. Do not carry TIFF pseudo-support forward.

See `audit/zentiff.md`, `audit/zenraw.md`, `audit/image-tiff.md`.
