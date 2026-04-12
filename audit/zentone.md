# zentone — HDR → SDR tone mapping

## Status: **v0.1.0, not yet wired into gain map producers**

`zentone` (at `~/work/zen/zentone/`, git repo, uncommitted to any
workspace yet) is the extracted home for classical and experimental
HDR→SDR tone mapping math. Extracted from `ultrahdr-core/src/color/` in
2026-04 to let zen codecs (and eventually `zenpipe`) consume tone mapping
without pulling the UltraHDR gain map container and its XMP/MPF parsers.

## Layout

```
zentone/
├── src/
│   ├── lib.rs              ToneMap trait, LUMA_BT709/BT2020 constants
│   ├── tone_map.rs         ToneMap trait + map_row_cn/map_into_cn helpers
│   ├── curves.rs           ToneMapCurve enum (Reinhard, Uncharted2, ACES,
│   │                       Narkowicz, AgX, BT.2390, clamp) + free fns
│   ├── bt2408.rs           Bt2408Tonemapper — PQ-domain Hermite spline
│   ├── filmic_spline.rs    CompiledFilmicSpline (darktable/Blender filmic)
│   ├── error.rs            Error + Result
│   ├── math.rs             libm wrappers for no_std f32 transcendentals
│   └── experimental/       behind `experimental` feature
│       ├── adaptive.rs     AdaptiveTonemapper, fit_luminance/per_channel
│       ├── streaming.rs    StreamingTonemapper, pull API, local adaptation
│       └── profile.rs      ProfileToneCurve (DNG), per_channel/luminance
│                           views
└── Cargo.toml              AGPL-3.0 + commercial, no_std + alloc, libm
```

## Relationship to gain maps

`zentone` does not know about gain maps; ultrahdr-core owns that. The
interaction points are:

1. **SDR base generation** for a gain map encode. When computing a gain
   map from an HDR master, the encoder must first choose the SDR base
   image. `ultrahdr-core::gainmap::compute_gainmap` currently gets the
   SDR base as an input argument — it does not generate one. A future
   zen crate (imageflow-side?) that wants to offer "give me HDR master,
   get back (SDR base, gain map)" should call a zentone tonemapper to
   produce the base. `Bt2408Tonemapper::new(content_nits, display_nits)`
   is the right default for a PQ input.

2. **Intent preservation on UltraHDR re-encodes.** When a consumer edits
   an UltraHDR file (eg. a crop or filter in imageflow) and needs to
   re-encode, `AdaptiveTonemapper::fit_luminance(&hdr_original,
   &sdr_original, channels, &FitConfig::default())` captures whatever
   curve the original encoder used. The edited HDR can then be run
   through the fitted tonemapper to produce a new SDR base that
   preserves the original artistic intent. `fit_per_channel` is the
   higher-fidelity variant for exact round-trip cases.

3. **Preview rendering fallback.** On platforms where the OS compositor
   does not natively support gain maps (older browsers, server-side
   rendering for image CDNs), zentone's `Bt2408Tonemapper` or
   `CompiledFilmicSpline` can be used to produce an SDR preview from a
   PQ or HLG HDR master without a round-trip through libultrahdr. This
   is a stopgap; the correct answer remains "ship gain maps and let the
   display stack reconstruct" — see
   [`specs/os-rendering/status.md`](../specs/os-rendering/status.md).

## Verified no-allocation-in-hot-path

From the zentone commit messages at `dbaabc5` and `fb79a91`:

- **Classical core** — `curves`, `bt2408`, `filmic_spline` — stack-only,
  in-place row API via `ToneMap::map_row(&mut [f32], channels)`.
- **StreamingTonemapper** — flat `Vec<f32>` ring buffer of
  `lookahead_rows * width * channels` pre-allocated in `new()`; push
  copies into the ring with `copy_from_slice`, pull writes the
  tonemapped row directly into the caller's slice. No per-row heap
  allocation in steady state. Dispatches to const-generic inner loops
  (`tonemap_row_impl::<3>` / `::<4>`) via `match channels` so the alpha
  branch and stride are compile-time folded.
- **AdaptiveTonemapper fit** — two-pass bucket-as-you-scan, no transient
  pair vectors, no `sort_by`. Pass 1 finds `max_hdr` (+ optional
  saturation detection), pass 2 buckets directly into a `Box<[f32;
  4096]>` LUT. MAE diagnostic is opt-in via `FitConfig::compute_mae`
  (third pass, default off). Per-channel fit returns
  `Err(Error::EmptyChannel { channel })` instead of fabricating an
  identity LUT when a channel has no valid samples.
- **ProfileToneCurve** — 4097-entry `Vec<f32>` LUT built once at
  construction; `per_channel()` / `luminance(luma)` views are zero-cost
  `&self` wrappers that implement `ToneMap`.

All four feature combinations build clean: default, experimental,
no-default, no-default + experimental. 46 unit tests + 2 doctests pass.

## Open design: detect a standard curve in an adaptive fit

After `AdaptiveTonemapper::fit_luminance` produces a `LuminanceCurve`
with a 4096-entry LUT, in many cases the underlying SDR base was
produced by a known classical curve (Reinhard, Uncharted 2, ACES AP1,
Narkowicz, BT.2408 at specific nits values). A **detection pass** could
recognize these and return the canonical parameters instead of the LUT,
unlocking:

- **Gain map metadata compression.** If the SDR base comes from
  `Bt2408(4000 nits, 203 nits)`, storing those two floats (or a curve
  enum + params) is dramatically smaller than a 16 KB LUT. Relevant for
  round-trip metadata round-tripping in gain map files — see the
  `FlagCommonDenominator` / per-channel compression fields in ISO
  21496-1 §5.
- **Exact round-trip.** Detected → analytic apply is faster and has no
  LUT-interpolation rounding compared to LUT apply, making repeated
  re-encodes bit-stable.
- **Provenance / corpus analysis.** Classify which tonemap was used on
  each image in a corpus; useful for camera/phone/workflow fingerprinting.

### Proposed shape

```rust
impl LuminanceCurve {
    pub fn detect_standard(&self) -> Option<DetectedCurve>;
}

pub enum DetectedCurve {
    Reinhard       { residual: f32 },
    Narkowicz      { residual: f32 },
    Uncharted2     { residual: f32 },
    AcesAp1        { residual: f32 },
    Clamp          { residual: f32 },
    ExtendedReinhard { l_max: f32, residual: f32 },
    TunedReinhard    { content_max_nits: f32, display_max_nits: f32, residual: f32 },
    Bt2408           { content_max_nits: f32, display_max_nits: f32, residual: f32 },
    Agx              { look: AgxLook, residual: f32 },
}
```

### Implementation cost

- **Parameterless curves** (Reinhard, Narkowicz, Uncharted 2, ACES AP1,
  Clamp): precompute reference LUTs once, RMS-compare. ≈100 LOC.
- **1-D parametric** (`ExtendedReinhard` over `l_max`): bisection on a
  bounded interval. ≈40 LOC.
- **2-D parametric** (`Bt2408`, `TunedReinhard` over content/display
  nits): log-scale grid search (~35 evals) followed by a local
  Nelder-Mead refine (~20 LOC). ≈150 LOC with the optimizer.
- **AgX with named look**: match each of Default/Punchy/Golden as a
  fixed case; custom look is out of scope for v1. ≈50 LOC.

Total: ~350 LOC for a first cut, gated behind `experimental`.

### Open questions

1. **Residual threshold calibration.** What residual separates "clean
   algorithmic curve" from "algorithmic + post-edit"? Need a corpus of
   known-clean encodes (libultrahdr reference outputs) and known-dirty
   ones (darktable Ansel exports) to pick a threshold.
2. **Saturation adjustment interaction.** If the source applied a
   saturation tweak on top of the curve, the fitted LuminanceCurve
   holds it as `saturation != 1.0`. Detection should ignore that (it's
   an orthogonal parameter) or incorporate it (it's part of the style).
   Current plan: match on the raw LUT, report `saturation_ratio`
   separately in `FitStats`.
3. **Per-channel detection.** A `PerChannelLut` has three LUTs that
   may or may not share a curve shape. Detection is 3× the cost and
   has to decide between "same curve per channel" (common for
   algorithmic encodes) and "three different curves" (edits). Phase 2.
4. **Detection in the presence of sub-sampling.** Default fit uses
   `max_samples = 100k` — residual floor is ~`1/sqrt(100k)` ≈ 0.003.
   That's fine for parameterless matching but marginal for 2-D
   parametric fits. Users who want high-confidence detection may need
   to raise `max_samples`.

### Dependency on verified platform behavior

Because the target use case ("detect Bt2408, store nits, regenerate
exactly") is only valuable if the platform that *rendered* the gain map
also uses a matching curve, this work depends on the OS rendering notes
in [`specs/os-rendering/status.md`](../specs/os-rendering/status.md).
Android's `libtonemap` is Hermite-based and does not explicitly name
BT.2408 in its source — matching a fitted curve to BT.2408 is only a
good guess for content that was *encoded* with BT.2408, not for content
that will be *displayed* through Android's libtonemap. Decoupling
"encoding curve recognition" from "rendering curve prediction" is
important here.

## BT.2408 / BT.2390 reference (2026-04-12)

The full BT.2408-8 (11/2024) and BT.2390-11 (10/2023) have been read and
the relevant tone mapping math is documented in
[`specs/itu-r-bt2408-bt2390/status.md`](../specs/itu-r-bt2408-bt2390/status.md).

Key items for zentone:

1. **EETF Hermite spline (BT.2408 Annex 5):** Five-step algorithm with
   `KS = 1.5*maxLum - 0.5`, cubic Hermite knee, and `(1-E2)^4` tapered
   black lift. This is what `Bt2408Tonemapper` should match.
2. **EETF application color spaces:** Five options (ICTCP, Y'Cb'Cr',
   YRGB, R'G'B', maxRGB) with documented tradeoffs. zentone currently
   applies in R'G'B' per-channel — this avoids out-of-gamut colors but
   over-desaturates bright saturated colors and can shift hue. For gain
   map SDR base generation this is a reasonable default. ICTCP or a
   blend of R'G'B' + maxRGB would give better perceptual results.
3. **1.15-1.16 OOTF gamma adjustment (BT.2408 §5.1.3.2):** Compensates
   for the subjective appearance change when scaling SDR 100→203 cd/m2.
   BBC and ARIB subjective tests confirmed independently.
4. **HLG system gamma (BT.2390 §6.2):**
   `gamma = 1.2 + 0.42*log10(Lw/1000)`. zentone doesn't support HLG
   yet but this is the formula needed for HLG↔PQ conversion.
5. **Surround compensation (BT.2390 §6.2):**
   `gamma_bright = gamma_ref - 0.076*log10(L_amb/5)`. Display gamma
   depends on viewing environment, not just panel peak.
6. **1/1.08 gamma for 203↔100 cd/m2 (BT.2408 Annex 11):** Preserves
   shadow detail at the perceivable black threshold (0.02 cd/m2) when
   converting between the two SDR reference white standards.

## Follow-ups for this repo

- [ ] After `experimental::detect` lands in zentone, re-visit this audit
      with a compliance matrix: "for each fixture in
      `test-vectors/jpeg/`, does detection find the curve?"
- [ ] Add a section to
      [`specs/os-rendering/status.md`](../specs/os-rendering/status.md)
      once we've read the `Android13` tonemap algorithm in full and can
      describe its curve family (currently we only know it's Hermite
      and defaulted from Android 13+).
- [ ] Cross-check `Bt2408Tonemapper::make_luma_scale` against libultrahdr's
      own BT.2408 implementation (`libultrahdr/lib/src/`) — they should
      agree bitwise on identical inputs. Differential test belongs in
      `test-vectors/`.
- [ ] Verify the EETF five steps (normalize, KS, Hermite, taper, denorm)
      match zentone's implementation line-by-line against the BT.2408
      Annex 5 formulas documented in
      `specs/itu-r-bt2408-bt2390/status.md` §2.
- [ ] Evaluate whether zentone should offer ICTCP or maxRGB-blend
      application spaces in addition to per-channel R'G'B', for better
      perceptual results on bright saturated content. BT.2408 recommends
      blending R'G'B' + maxRGB as a middle ground.
