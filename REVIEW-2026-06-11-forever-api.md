# HDR forever-API review — 2026-06-11

Four-front research pass (internal spec digest · consumer inventory · live external
deltas · invariants/stress analysis) commissioned before committing to the zenpixels
HDR plan ([zenpixels#39](https://github.com/imazen/zenpixels/issues/39) omnibus,
closed #16's `HdrProvenance` design, zencodec#24 gain-map encode pipeline). Baseline:
this repo's 2026-04-11 snapshot. Every external claim below was live-checked
2026-06-10/11 with primary sources; internal claims cite files/issues.

**Verdict up front:** the #39 ladder and #16 shape survive review, with five concrete
amendments (§7). The single most important structural finding: **gain maps are not
the only adaptation payload anymore** — parametric gain *curves* (SMPTE ST 2094-50 /
AOM "AGTM") are live experimental code in Skia m145 and Chromium — so the permanent
API models *adaptation payloads* as an extensible enum, never a struct named after
gain maps. The second: **Android 16 ships HDR-base direction reversal and
application-color-space get/set in production**, promoting two "hypothetical" ISO
axes to shipping reality.

---

## 1. External deltas vs the 2026-04-11 snapshot

Confirmed unchanged: ISO 21496-1:2025 stable (no amendments, **no Part 2 in any
catalogue**); HEIF Amd 1:2025-10 published; libultrahdr stalled at 1.4.0
(2025-01-10); PNG `gMAP`/`gDAT` (w3c/png#380) still blocked on ISO paywall; Firefox
still has no HDR image path; BT.2446-1 still latest; 203-nit anchor reinforced
(Android dev blog 2025-08); Windows still no native gain-map stills.

Changed / new (full citations in the agent transcript, key ones inline):

| Finding | Consequence for us |
|---|---|
| **Safari 26** (fall 2025) renders gain maps: ISO 21496-1 JPEG, legacy Apple/Android JPEG, AVIF ±ISO map, HEIF ±Apple map, PQ PNG; **not** JXL-jhgm. CSS `dynamic-range-limit` now cross-engine (Chrome 133 + Safari 26). | Web delivery of gain-map HDR is real on 2 of 3 engines; our encoders' output is directly user-visible. |
| **JXL `jhgm` standardized**: ISO/IEC 18181-2:2026 (3rd ed) includes the ISO 21496-1 gain-map box (arXiv:2506.05987; jpeg.org workplan). Chrome 145 Canary re-added JXL via jxl-rs behind a flag — *without* gain-map support. | README "ISO status unclear" row corrected. zenjxl's jhgm path is on a published standard now. |
| **Android 16**: PNG HDR screenshots with **private chunks `gmAP`+`gdAT`** (PNG-in-PNG gain map, not the W3C proposal); `HEIC_ULTRAHDR`; get/set **gain-map application color space**; **HDR-encoded base + SDR gain map** (direction reversal) shipping; AVIF UltraHDR "in development" (source.android.com HDR-screenshots; Android 16 features). | Direction reversal and application-space are no longer paper features. Decoders will meet `gmAP`/`gdAT` PNGs in the wild years before W3C lands public chunks. |
| **AGTM / gain curves**: Skia m145 ships `skhdr::Agtm` (parse/serialize/tone-map ST 2094-50); Chromium `kHdrAgtm` feature flag exists (default off); PNG WG tracks "awaiting AOM version" (free twin). | The "Part 2 / gain curve" thread landed as SMPTE+AOM, not ISO 21496-2. Adaptation payloads must be modeled extensibly (§7-A1). |
| **Adobe converged on ISO** (since Oct 2024, ACR 17 era): ISO 21496-1 gain maps written in **JPG, AVIF, JXL and TIF** exports. | De-facto TIFF gain-map files exist in the wild despite "no TIFF track" — zentiff/zenraw should expect them. |
| **ISO 22028-5:2026** published as full IS (May 2026): PQ/HLG still-image encodings + diffuse-white/viewing metadata; PNG WG proposing `dWLm` (diffuse white luminance) and `rWTm` chunks on top of it; libheif 1.23.0 added ambient-viewing-environment + nominal-diffuse-white APIs. | "Headroom" is becoming a **tuple** (peak, diffuse white, ambient), not a scalar ratio (§7-A4). Grounds the `encode_pq16` parameter naming (§7-A3). |
| **libavif 1.2.0 → 1.4.2**: gain-map API stabilized (1.2.0), Apple-JPEG→ISO conversion (1.4.0), gain-map CICP fixes (1.4.1), NaN bypass in tone mapping (1.4.2). | libavif is the working ISO↔Apple reference implementation. |
| **libheif (1.23.0) and Nokia heif (3.7.1) still have zero `tmap` support**; libheif#1685 unanswered. | Our `heic` crate is currently the only non-Apple HEIC gain-map reader we know of — leverage, and an interop-testing obligation. |
| **BT.2408 → -9 (03/2026), BT.2390 → -12 (03/2025)** — both revved under our local notes (-8/-11). | `specs/itu-r-bt2408-bt2390/` must be re-verified before zentone EETF work (TODO addendum). |
| **CTA-861 current edition is -I** (2023, free); MaxCLL/MaxFALL text unchanged from 861.3-A. **PNG-3 normatively answers the stills convention**: cLLI per CTA-861.3-A, "each frame is analyzed" — for a still, frame-average = that image's average (w3.org/TR/png-3 §11.3.2.8). | This is the citable ground truth for `compute_content_light_level` (zenpixels#39 Rung 2): MaxCLL = brightest pixel's max(R,G,B) in nits; MaxFALL = the single image's average of per-pixel max. Exactly what `hdr-corpus-convert::render_pq16` computes today. |
| **Apple iOS 18→26**: ImageIO `kCGImageAuxiliaryDataTypeISOGainMap`; **RGB (3-channel) gain maps since iOS 18** (with aux-data API pitfalls; Core Image workaround); camera HEIC still uses the proprietary aux item on disk; iOS 26 HDR screenshots are yet another dual-layer HEIC layout. | 3-channel maps ship in volume now → `GainMapChannels::Rgb` is a launch requirement, not future-proofing. The Apple-aux ↔ ISO converter remains permanently load-bearing. |

## 2. Theory anchors (correct behavior)

- **Apply math** (verified UltraHDR v1.1 + libavif):
  `HDR = (SDR + base_offset) · exp2(log_gain · w) − alternate_offset`, per-pixel
  `log_gain = lerp(min, max, recovery^(1/γ))`, display weight
  `w = clamp(log2(display_headroom)/log2(alternate_headroom), 0, 1)` — multiply in
  **linear light** in the declared application space. Offsets linear; gains/headrooms
  log2. (specs/iso-21496-1/apply-math-and-banding.md)
- **Round-trip theory**: BT.2446 Method A is psychophysically verified
  (HDR→SDR→HDR p=0.167, n.s.); Method C has a **closed-form inverse** — the natural
  detection target for zentone's `detect_standard()` and the only exact-round-trip
  curve. EETF (BT.2408 Annex 5 Hermite) is display adaptation, not a storage curve.
- **Reference white**: 203 cd/m² (PQ 58%, HLG 75%@1000) is the anchor every
  platform's headroom math assumes; ISO 22028-5/PNG `dWLm` make the diffuse-white
  *explicit and overridable* — which is why our APIs must parameterize it rather
  than hardcode it.
- **Compositor inputs** (Android/Apple/Skia/Windows §3 of the digest): everything a
  display needs is (ISO param block, alternate headroom, colorimetry, direction
  flag). Platform tone curves are applied display-side and are **not** ours to bake.

## 3. Consumer inventory (who needs what)

Requirements ranked by consumer count (full matrix in the agent transcript):
`GainMapParams` (8: zenjpeg, zenavif, zenjxl, zenpipe, ultrahdr-rs, zencodec,
zentone, roundtrip tools) · `ContentLightLevel` (6) · transfer+headroom (5) ·
`MasteringDisplay` (4) · explicit direction (4) · gain-map dims/bit-depth (3/2) ·
application space (2, now Android-16-live) · tone-curve provenance (1–2, future).

Pipeline truths, **corrected by source verification (2026-06-11 scope audit)**:
- ~~CLL/MDCV are lost between decode and encode~~ — **wrong for zenpipe**: it
  carries them end-to-end on the `zencodec::Metadata` channel
  (`zenpipe/src/job.rs:887` "Keep content_light_level and mastering_display",
  re-attached at `:1015`). The gap exists only for bare-`PixelBuffer` library
  flows that bypass the Metadata channel — a far weaker case for a
  `ColorContext` break than #16's motivation stated.
- The "zenpipe parks gain maps as an RGB8_SRGB sidecar" claim from the consumer
  inventory cited a nonexistent path and is **unconfirmed** — verify in
  `zenpipe/src/{job,session,orchestrate}.rs` before letting it justify work.
- `finalize_for_output_with` hardcodes `hdr: None` today (verified).
- CLL **computation** (scan pixels → MaxCLL/MaxFALL) has exactly **one** consumer
  today: hdr-corpus-convert's `render_pq16`. zenjxl maps `intensity_target`→CLL
  and zenpng moves chunk bytes — transport, not computation. The earlier
  "6 consumers" count conflated the two.
- imageflow has zero HDR surface (decision needed eventually, out of scope here).
- zensim/zenmetrics run their own HDR feeding paths and do **not** need pixel-side
  provenance — consistent with keeping luminance/IQA fields out of zenpixels (#34
  rescope).

## 4. Invariants register (what a forever-API must encode)

1. Two independent headrooms (base + alternate), both log2 — the *range* drives the
   display-weight interpolation; never collapse to one peak.
2. Direction is the explicit `backward_direction` flag, carried verbatim; headroom
   ordering is fallback only. (Android 16 ships reversed files.)
3. Per-channel ×3 with single-channel collapse; 3-channel is **shipping** (iOS 18).
4. Offsets linear, gains log2 — domains never converted in storage.
5. `minimum_version`/`writer_version` preserved verbatim for round-trip (zenavif-parse
   currently drops writer_version on re-serialize — known gap).
6. Apple headroom is a lossy projection of ISO params; conversions live codec-side,
   never on the pixel context.
7. CLL/MDCV are optional and orthogonal to headroom; never folded together.
8. No absolute-luminance/IQA fields on pixel provenance (zensim's domain) — but the
   *diffuse-white parameter* of output encoders is explicit (22028-5 direction).
9. Gray content: H.273 primaries contribute only the white point; **HLG-gray ICC is
   a verified signaling dead-end** (no cicpTag allowed on GRAY; hash tolerance
   exceeded) → container CICP mandatory for single-channel HLG.
10. PQ `curv`-LUT ICC is ~8% off at ~1 nit → CICP-native signaling first, ICC as
    compatibility fallback, everywhere we emit PQ.

## 5. Stress tests of the #16 `HdrProvenance` shape

Holds (given `#[non_exhaustive]` on every public struct/enum): multi-channel ISO
maps · f16 pixels (orthogonal to provenance) · future ISO field additions (version
byte + tolerant tail parsing) · native-PQ and tone-mapped origins.

Gaps to absorb additively (do NOT block 0.3.0; do require non_exhaustive):
- **application-space colorimetry** on `GainMapProvenance` — promoted in urgency by
  Android 16's get/set API; add as `Option<_>` field when zencodec#24 Phase 2 needs it.
- **double provenance** (tone-mapped FROM gain-map-reconstructed) — optional
  back-pointer on the `ToneMapped` variant, Phase-4 territory.
- **AGTM / gain curves** — a future `HdrOrigin`/payload variant; semantic naming
  (`ToneCurveSet`, not SDO numbers) per the paywall-twin pattern.
- **multiple alternates / sequences** — HEIF `altr` allows >2 renditions; APNG/avis
  per-frame maps will come; don't structure around exactly one (base, alternate).

## 6. Future-evolution risk list (condensed)

Payloads beyond per-pixel maps (AGTM) · N-channel + application-space axes live ·
bidirectional base · headroom → tuple (peak, diffuse white, ambient; 22028-5/dWLm) ·
container-binding fragmentation incl. private chunks (`gmAP`/`gdAT`) · metadata
placement/offset fragility (XMP vs binary vs MPF — retain raw payloads + which
bindings were present for re-emit) · in-record version churn (parse unknown tails
tolerantly, preserve bytes) · paywall politics producing free AOM twins of ISO/SMPTE
semantics.

## 7. What this changes in the plan (amendments)

**A1 — Model the payload enum, not a gain-map struct.** zencodec#24 Phase 1's
`GainMapEncodeSource` and #16's `HdrOrigin` stay, but both must be
`#[non_exhaustive]` enums whose docs name the next variants (gain curve set,
sequence maps) so AGTM lands additively. *(Doc/shape requirement, no new work.)*

**A2 — Promote 3-channel + direction-reversal from "edge" to launch tests.** iOS 18
RGB maps and Android 16 HDR-base files are mainstream inputs; Rung-4/Phase-2 test
matrices must include both from day one (we already parse both; the tests pin it).

**A3 — Rung 2 parameter semantics resolved**: name it `diffuse_white_nits`
(default 203.0), defined as "nits of linear 1.0" — aligned with BT.2408 and the
22028-5/`dWLm` direction, and the open `nits_per_unit` ambiguity is closed: pixels
are relative-linear, the parameter anchors them. MaxCLL/MaxFALL per CTA-861.3-A with
the PNG-3 stills reading (single frame = the image). `encode_pq16` outputs carry
`PixelDescriptor::RGB16_BT2100_PQ` + container-CICP-first signaling (+ optional
`synthesize_icc_for_cicp(Cicp::BT2100_PQ)` fallback with the documented toe caveat).

**A4 — Rung 3 (EETF) gains a precondition**: re-verify `specs/itu-r-bt2408-bt2390/`
against BT.2408-9 (03/2026) and BT.2390-12 (03/2025) before implementing anything
from those notes.

**A5 — 0.3.0 consumer gate re-affirmed and sharpened**: ship `HdrProvenance` only
with zencodec#24 Phase 2/3 consuming it; include the #29 endianness evaluation and
the `#[non_exhaustive]` sweep in the same batch; keep luminance/IQA out (zensim);
carry raw ISO payload bytes (provenance of bindings) for byte-faithful re-emit.

Safe regardless (unchanged): Rung 1 test hardening; Rung 2 helpers under A3
semantics; all of zencodec#24 Phase 0/1 additive types.

## 7b. Same-day scope audit (anti-overscope / anti-YAGNI pass)

A deliberate adversarial pass over this review's own conclusions, with source
verification of the agent claims that justified API work. Outcomes:

**Wrong-problem corrections**
- **Layer transit, not mirror-split, is the demand-backed transcode model.** The
  ecosystem norm is per-layer handling — gain maps are routinely sub-resolution,
  so independent base/map resampling is standard practice; a resize/crop/format
  CDN never needs reconstruct-then-resplit. Mirror-split (and therefore most of
  #16's `HdrProvenance`-on-pixels rationale) only matters for ops that must run
  on *merged* HDR pixels, and no such consumer exists today. zencodec#24
  Phase 4's `Components → with_gain_map` passthrough — using already-existing
  types — covers the real use case with **zero zenpixels breaking change**.
- **The CLL/MDCV pipeline-loss premise was falsified** (see §3 corrections).

**Demotions (gates hardened)**
- zenpixels 0.3.0 / `HdrProvenance`: from "gated rung" to **hypothesis** — needs
  a named use case that layer transit + the Metadata channel cannot serve. The
  `#[non_exhaustive]`/endianness batch waits with it; no break without a driver.
- zencodec#24: **Phase 0 only** (prove native HDR with tests — zero new API) is
  unconditional. Phases 1–4 wait for a named encode/transcode consumer.
  "Additive" is not free on a freshly-published crate.
- zenavif/zenjxl `GainMapRender` wiring: neither declares the caps (no
  dishonesty exists) and no consumer decodes HDR avif/jxl in our flows — defer.
- Rung 2 helpers ship **small and honest**: one real consumer; the value is
  deleting hand-rolled copies + pinning CTA-861.3-A/PNG-3 semantics, not
  serving an imagined fleet. No SIMD until profiled.

**Baked-ignorance ledger**
- ISO 21496-1 / 22028-5 / HEIF Amd 1 / ST 2094-50 normative text is paywalled;
  our parameter tables are reverse-engineered from libavif/libultrahdr.
  **Recommendation: purchase the specs before freezing any "forever" shape.**
  Until then, the differential tests against libavif/libultrahdr (already in
  TODO) are the authoritative oracle — they, not prose, are the anti-drift
  mechanism.
- Secondary-source items (Adobe convergence details, libultrahdr roadmap)
  remain labeled as such; they inform watches, never gates.
- Process rule adopted: any agent-sourced claim that justifies API work gets
  spot-verified in source first (two such claims failed verification in this
  audit; one had already propagated into this doc's §3).

**Kept without reservation** (defends existing shipped behavior): hdr.rs test
hardening (Rung 1); zenjpeg#144; zenwebp#58; zenpipe#38/#39/#40; the
differential-test and fixture TODOs.

## 8. Repo refresh done with this review

README snapshot rows corrected (JXL spec status; PNG ref-impl reality; TIFF
de-facto Adobe files) and TODO addendum appended (done items checked, new watches:
AGTM/ST 2094-50 + AOM twin, BT.2408-9/BT.2390-12 re-verification, ISO
22028-5:2026 + PNG `dWLm`/`rWTm`, Android private `gmAP`/`gdAT`, libheif tmap gap,
zenavif-parse writer_version preservation, libavif 1.4.x as Apple↔ISO reference).
