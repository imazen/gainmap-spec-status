# TODO — gap list

Track active follow-ups from the initial audit (2026-04-11). Update as items
land.

## Code changes in zen crates

### P0 — correctness / fork risk

- [ ] **Delete duplicate ISO 21496-1 parser.**
  Delete `ultrahdr/ultrahdr-core/src/metadata/iso21496.rs` and have
  ultrahdr-core depend on `zencodec::gainmap`. Keep the ultrahdr-specific
  marker helpers (`JpegIsoMarkers`, `create_iso_app2_marker`,
  `create_jpeg_iso_markers`, `create_version_only_iso_app2`) as thin
  adapters over `zencodec::gainmap::serialize_iso21496_fmt`.
  See `audit/ultrahdr.md` §"ISO 21496-1 parser duplication".

- [ ] **Add HEIF Amd 1 `tmap` support to `heic`.**
  Parallel API to the existing Apple aux-item path:
  - `heic::decode_tmap_gain_map(data) -> Result<HdrGainMap>`
  - Teach `heic::has_gain_map` to detect *either* `tmap` or Apple aux
  - Return a unified `HdrGainMap` with an `Origin { AppleAux, Tmap }` tag
  See `audit/heic.md`.

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

- [ ] **w3c/png#380, #536** — 4th edition gain map proposal status
- [ ] **libjxl** — is there an ISO/IEC 18181 Amendment adding `jhgm`?
- [ ] **Adobe DNG spec page** — any 1.8 draft with gain map tags?
- [ ] **ISO 21496-1 Amendment 1** — if announced, refetch iTeh sample and
      re-extract Annex C bindings.
- [ ] **HEIF Amendment 1 free excerpt** — if a summary or reference code
      surfaces, capture it.

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
