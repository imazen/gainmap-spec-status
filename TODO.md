# TODO — gap list

Track active follow-ups from the initial audit (2026-04-11). Update as items
land. **2026-06-11 review pass:** statuses updated below + addendum at the end
(see `REVIEW-2026-06-11-forever-api.md` for the full delta report).

## Code changes in zen crates

### P0 — correctness / fork risk

- [x] **Delete duplicate ISO 21496-1 parser.** *(done — verified 2026-06-11:
  `ultrahdr-core/src/metadata/iso21496.rs` no longer exists; ultrahdr-core
  re-exports `zencodec::GainMapParams` + `parse/serialize_iso21496_fmt`.)*

- [x] **Add HEIF Amd 1 `tmap` support to `heic`.** *(done — verified 2026-06-11:
  `heic/src/lib.rs:809+` has the `tmap` path with `Origin { AppleAux, Tmap }`
  tagging, and the zencodec adapter declares `gain_map` + `reconstructs_hdr`.)*

### P1 — test + verification

- [ ] **Verify AVIF `tmap` item hidden-flag.**
  `zenavif-serialize/src/lib.rs:605+` writes the gain map `av01` item —
  confirm it sets the hidden flag per AVIF §4.2.2. Add a roundtrip test.

- [ ] **Differential test zenjxl-decoder against libjxl-produced `jhgm`.**
  Use `cjxl --ultrahdr-app` against an UltraHDR JPEG, capture the output,
  and parse with `zenjxl-decoder::container::gain_map::GainMapBundle::parse`.
  Compare against `test-vectors/jxl/jhgm_golden.bin` for layout parity.

- [ ] **Differential test zencodec vs ultrahdr-core ISO parsers.**
  While both parsers exist (pre-P0 fix), write a test that parses each
  `test-vectors/jpeg/*.jpg`'s embedded ISO 21496-1 blob with both parsers
  and asserts field-level equality. Catches drift immediately.

- [ ] **Test AVIF gain map grid derivation.**
  `color_grid_gainmap_different_grid.avif` exercises the path where the
  gain map has its own grid dimensions independent of the base. zenavif-parse
  should parse both grids.

### P2 — API + naming

- [ ] **Rename zenraw DNG opcode-9 "GainMap".**
  `~/work/zen/zenraw/src/apple.rs` (HDR), docs/, roadmap.md all use
  "gain map" for two different things. Reserve "gain map" for the HDR
  sense; rename DNG OpcodeList2 opcode-9 to "lens shading table" in
  public API and docs.

- [ ] **Add `zenjxl::compute_and_attach_gain_map` helper.**
  High-level wrapper that computes a gain map via `ultrahdr-core::gainmap::compute_gainmap`,
  serializes the ISO 21496-1 metadata via `zencodec::gainmap::serialize_iso21496_fmt(..., JpegApp2)`,
  wraps in `JxlGainMapBundle`, and attaches via `jxl-encoder::container::append_gain_map_box`.

- [ ] **Bridge `From<&GainMapBundle> for zencodec::GainMapParams`** in zenjxl.
  Lets callers parse jhgm → GainMapParams without crossing crate boundaries.

## Test corpus

### P1 — coverage

- [ ] **Capture HEIC with Apple `urn:com:apple:photo:2020:aux:hdrgainmap`**.
  Smallest way: build with libheif from an SDR source + synthetic gain map,
  or crop an iPhone HEIC to <30 KB. TBD.

- [ ] **Capture HEIC with HEIF Amd 1 `tmap`.**
  Requires libheif with Amd 1 support or an iOS 18+ device. Not yet
  available in our corpus.

- [ ] **Capture a real libjxl `cjxl --ultrahdr-app` output.**
  1-10 KB range. Use the minnie-320x240-yuv.jpg as input.

### P2 — conformance

- [ ] **Add Apple `apple_gainmap_old.jpg` and `apple_gainmap_new.jpg` from
      libavif.** Each is ~50 KB which exceeds the 30 KB rule — need user
      confirmation or a cropped version.

- [ ] **Mark every fixture as `{strict_rejects, lenient_accepts, expected}`.**
  Decoder strictness is a configurable axis in zenjpeg; we should label
  each fixture against the four levels.

## Spec watches

Check quarterly:

- [ ] **ITU-R BT.2408** — any new revision (currently -8, 11/2024)
- [ ] **ITU-R BT.2446** — check for revisions beyond -1 (03/2021). Read
      and documented in `specs/itu-r-bt2408-bt2390/bt2446.md`.
- [ ] **w3c/png#380, #536** — 4th edition gain map proposal status
- [ ] **libjxl** — is there an ISO/IEC 18181 Amendment adding `jhgm`?
- [ ] **Adobe DNG spec page** — any 1.8 draft with gain map tags?
- [ ] **ISO 21496-1 Amendment 1** — if announced, refetch iTeh sample and
      re-extract Annex C bindings.
- [ ] **HEIF Amendment 1 free excerpt** — if a summary or reference code
      surfaces, capture it.
- [ ] **AOSP `libtonemap` `Android13` algorithm** — read the full Hermite
      formulation in
      [`frameworks/native/libs/tonemap/tonemap.cpp`](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/main/libs/tonemap/tonemap.cpp)
      and note the curve family in
      [`specs/os-rendering/status.md`](specs/os-rendering/status.md).
      Currently we've only verified it references BT.2100 and uses
      Hermite interpolation.
- [ ] **Android 16/17 HDR headroom APIs** — check whether
      `Window.setDesiredHdrHeadroom` gains per-region or more granular
      negotiation beyond the API 35 shape.
- [ ] **Windows native UltraHDR support** — currently cross-platform via
      Skia `SkGainmapShader`. Watch for a first-party Windows codec API.

## zentone follow-ups (design, not yet coded)

- [ ] **Detect a standard curve in an adaptive fit.** Design in
      [`audit/zentone.md`](audit/zentone.md) §"Open design: detect a
      standard curve in an adaptive fit". Unlocks storing curve + params
      instead of a 16 KB LUT in gain map metadata.
- [ ] **Differential test `Bt2408Tonemapper::make_luma_scale` against
      libultrahdr's BT.2408.** Both should agree bitwise on identical
      inputs. Add to `test-vectors/` once implemented.
- [ ] **Verify EETF Hermite spline matches BT.2408 Annex 5 step-by-step.**
      Check KS = 1.5*maxLum - 0.5, the (1-E2)^4 black level taper, and
      the Hermite knot structure. Document in `audit/zentone.md`.
      See `specs/itu-r-bt2408-bt2390/status.md` §2.
- [ ] **Document EETF application color space.**
      zentone currently applies tone mapping in R'G'B' per-channel — confirm
      this is the intended choice for gain map SDR base generation and
      document the tradeoffs vs ICTCP/maxRGB. See BT.2408 Annex 5 §A5.1.
- [ ] **Add OOTF gamma adjustment (1.15-1.16) as an SDR→HDR option.**
      BT.2408 §5.1.3.2 documents this for preserving subjective SDR
      appearance when scaling 100→203 cd/m2. Useful for display-referred
      SDR base generation. See `specs/itu-r-bt2408-bt2390/status.md` §4.
- [ ] **Add 203↔100 cd/m2 gamma correction (1/1.08).**
      BT.2408 Annex 11: when SDR base targets 100 cd/m2 but the gain map
      system assumes 203 cd/m2 (or vice versa), this optional gamma
      preserves shadow detail at the perceivable black threshold of
      0.02 cd/m2. See `specs/itu-r-bt2408-bt2390/status.md` §7.
- [ ] **Add HLG system gamma and OOTF support to zentone.**
      BT.2390 defines `gamma = 1.2 + 0.42*log10(Lw/1000)` and the
      luminance-preserving OOTF `alpha * Ys^(gamma-1) * E`. Needed for
      HLG↔PQ conversion and any future HLG gain map support.
      See `specs/itu-r-bt2408-bt2390/status.md` §8-9.
- [ ] **Implement BT.2446 Method A TMO/ITMO as `ToneMapCurve::Bt2446A`.**
      Piecewise polynomial with perceptual linearization, 1000→100 cd/m2.
      Psychophysically verified round-trip. ~50 LOC per direction.
      See `specs/itu-r-bt2408-bt2390/bt2446.md`.
- [ ] **Add BT.2446 Method C parametric curve to `detect_standard`.**
      The k1-k4 parameter derivation (from skin tones + inflection point)
      is a detection target for `AdaptiveTonemapper`. Parametric form
      enables exact round-trip via analytic inverse.
- [ ] **Evaluate BT.2408 EETF vs BT.2446 Method A for 1000→100 cd/m2.**
      Both are reference tone mappers for the same conversion but use
      different math (Hermite spline vs piecewise polynomial). Compare
      output on the same inputs and document which zentone should default to.

## Repo hygiene

- [ ] **Add `fetch-specs.sh`** that downloads public specs into `raw-pdfs/`
  (gitignored) and re-runs `pdf-oxide markdown` into `specs/*/extracted.md`.
- [ ] **CI**: once the repo lands in a workspace, add a CI job that
  regenerates synthetic fixtures via `tools/*.py` and diffs against the
  committed bytes. If the generator drifts, CI breaks.
- [ ] **Licenses directory**: copy LICENSE files from libavif, awesome-gain-maps,
  and libultrahdr-testdata so downstream users of this repo don't have to
  chase them.

## Tracked bugs

- [ ] **ultrahdr-core accepts `BaseRenditionIsHDR="True"`** where libultrahdr
  rejects. This can swap the direction of gain map application if the
  sibling headroom fields disagree. Documented in `zenjpeg/CLAUDE.md`.
  Decide: align with libultrahdr or document as intentional.

---

## Addendum — 2026-06-11 review pass

New/updated watches and gaps from `REVIEW-2026-06-11-forever-api.md`:

### Spec-watch updates
- [ ] **Re-verify `specs/itu-r-bt2408-bt2390/` against BT.2408-9 (03/2026) and
  BT.2390-12 (03/2025)** — both revved under our -8/-11 notes. Precondition for
  any zentone EETF implementation (zenpixels#39 Rung 3).
- [x] **JXL `jhgm` ISO status resolved** — standardized in ISO/IEC 18181-2:2026
  (3rd ed); next edition (JXL-in-ISOBMFF/HEIF) at CD stage.
- [ ] **AGTM / gain curves (SMPTE ST 2094-50 + forthcoming free AOM twin)** —
  Skia m145 ships `skhdr::Agtm`; Chromium has `kHdrAgtm` (default off); PNG WG
  blocked awaiting the AOM version. Watch quarterly; permanent-API consequence:
  adaptation payloads are an extensible enum, never gain-map-only.
- [ ] **ISO 22028-5:2026 published (May 2026, full IS)** + PNG `dWLm`/`rWTm`
  chunk proposals + libheif 1.23 ambient/diffuse-white APIs — "headroom becomes
  a tuple (peak, diffuse white, ambient)". Track for encode_pq16 semantics.
- [ ] **Android 16 private PNG chunks `gmAP`+`gdAT`** (PNG-in-PNG gain map,
  HDR screenshots) — decoders will meet these in the wild; W3C public chunks
  still blocked. Decide whether zenpng should *read* the private form.
- [ ] **libheif/Nokia still have zero `tmap` support** (libheif 1.23.0,
  heif 3.7.1; libheif#1685 unanswered) — our `heic` crate is the only
  non-Apple HEIC gain-map reader; keep interop tests authoritative.

### Code gaps (new)
- [ ] **zenavif-parse: preserve `writer_version` on round-trip** — parsed +
  validated but not stored; re-serialize always emits 0. ~10 LOC.
- [ ] **3-channel gain maps + HDR-base direction reversal are mainstream**
  (iOS 18 RGB maps; Android 16 reversed files) — promote both from edge cases
  to required rows in zencodec#24 Phase-2 and zenpixels 0.3.0 test matrices.
- [ ] **Expect de-facto ISO 21496-1 gain maps in TIFF** (Adobe ACR 17+ since
  Oct 2024) — zentiff/zenraw probe behavior should at least not mangle them.
