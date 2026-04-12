# Gain map application math and banding

What the gain map formula actually computes, where the offsets come from,
where banding enters the pipeline, and what the spec says about mitigating
it. Kept separate from [`status.md`](status.md) because it mixes normative
spec text (ISO 21496-1, UltraHDR v1.1) with reference-implementation
behavior (libultrahdr, libavif, our `ultrahdr-core`) and practical notes.

## Scope and sources

This file is strict about citing because the naive answer ("gain maps are
just `HDR = SDR * gain`") is wrong in several ways and each correction
matters for banding. Primary sources:

- **ISO 21496-1:2025** — the root spec. We only have the 4-page free
  sample at
  [iteh.ai](https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025)
  which ends before the formula text; see
  [`extracted.md`](extracted.md). The full body we infer from the
  UltraHDR and libavif implementations which are explicitly conformant.
- **Google Ultra HDR Image Format v1.1** — the JPEG-specific binding,
  published at
  [`developer.android.com/media/platform/hdr-image-format`](https://developer.android.com/media/platform/hdr-image-format).
  This page is the most complete public source for the actual math.
- **libavif gain map reference** —
  [`github.com/AOMediaCodec/libavif/blob/main/src/gainmap.c`](https://github.com/AOMediaCodec/libavif/blob/main/src/gainmap.c)
  shows the AVIF binding's defaults and data shapes. The
  `avifGainMap` struct uses signed/unsigned rational fractions for the
  on-wire metadata and converts to float during apply.
- **Our own implementation** — `~/work/zen/ultrahdr/ultrahdr-core/src/gainmap/apply.rs`
  is directly inspectable; the LUT build at `:26–57` and the per-pixel
  apply at `:316–324` are the ground truth for how zen decodes.

## Two levels: ISO 21496-1 vs UltraHDR v1.1

These are frequently conflated in casual writing, including in my own
first pass at answering this question. They are not the same.

- **ISO 21496-1** is the general framework: it defines per-component
  metadata (min/max log2, gamma, offsets), baseline and alternate
  colorimetry, *and a third concept* — a "gain map application space
  colour primaries" (§5.3.4 in the TOC; body unverified from the free
  sample). In the general model, the multiply can happen in a color
  space that is neither the base's nor the alternate's, requiring
  conversion in and out.
- **UltraHDR v1.1** is the JPEG-specific binding. It collapses the
  application space back onto the base's color space:

  > "The color profile of the SDR image defines the color space of the
  > HDR image."

  So for a sRGB/Display-P3 JPEG UltraHDR file, the multiply happens in
  linearized RGB of the base's primaries, and the reconstructed HDR is
  *in the same primaries*. This is simpler than the ISO case but also
  less flexible.

Practical implication: if you're reading UltraHDR JPEGs (the common
case), the simpler UltraHDR formula is enough. If you're reading an AVIF
or HEIC `tmap` item that declares a distinct application space, you must
convert into it before the multiply and out of it after. Our `ultrahdr-core`
currently implements the UltraHDR-level simplification — verify against
your AVIF test vectors if you need the fully general case.

## The formula, verified

From [UltraHDR v1.1](https://developer.android.com/media/platform/hdr-image-format):

```
HDR(x, y) = (SDR(x, y) + offset_sdr) * exp2(log_boost(x, y) * weight_factor) - offset_hdr
```

where

```
log_boost(x, y) = gain_map_min * (1 - log_recovery(x, y))
                + gain_map_max *      log_recovery(x, y)

log_recovery(x, y) = pow(encoded_recovery(x, y) / 255.0, 1.0 / map_gamma)
```

and on the encode side:

```
pixel_gain(x, y)  = (Yhdr(x, y) + offset_hdr) / (Ysdr(x, y) + offset_sdr)
map_min_log2      = log2(min_content_boost)
map_max_log2      = log2(max_content_boost)
log_recovery(x, y) = (log2(pixel_gain(x, y)) - map_min_log2)
                   / (map_max_log2 - map_min_log2)
clamped            = clamp(log_recovery, 0.0, 1.0)
recovery(x, y)     = pow(clamped, map_gamma)
encoded_recovery(x, y) = floor(recovery(x, y) * 255.0 + 0.5)
```

Every variable, with verified origin:

| Name | Type | Per-channel? | Default | Source |
|---|---|---|---|---|
| `offset_sdr` | signed fraction | yes (1 or 3 values) | 1/64 ≈ 0.015625 | UltraHDR v1.1 doc; libavif `baseOffset[i]` |
| `offset_hdr` | signed fraction | yes | 1/64 | same |
| `map_min_log2` / `gain_map_min` | signed real | yes | encoder-chosen | ISO 21496-1 §5.2.5 (per TOC) |
| `map_max_log2` / `gain_map_max` | signed real | yes | encoder-chosen | same |
| `map_gamma` | positive real | yes | 1.0 | libavif `gainMapGamma[i] = 1/1`; UltraHDR doc says "use 1.0 unless distribution is uneven" |
| `weight_factor` | float in `[0, 1]` | no (image-global) | runtime-derived | see below |
| `encoded_recovery` | uint8 (JPEG) or codec-dependent (AVIF/HEIC) | all channels | — | §4.4 quantization; binding-specific |
| `BaseRenditionIsHDR` | bool | no | false | UltraHDR v1.1 XMP field |

`offset_sdr` and `offset_hdr` are called `base_offset` and
`alternate_offset` in ISO 21496-1 and in our `ultrahdr-core` code; the
UltraHDR XMP schema uses `hdrgm:OffsetSDR` / `hdrgm:OffsetHDR`. Same
values, different field names depending on which spec you're reading.

## The weight factor is not a user slider — it comes from the display

The `weight_factor` is the link between the gain map (which has a
content-specified range) and the display (which has a dynamic headroom).
UltraHDR v1.1 defines it:

> When `hdrgm:BaseRenditionIsHDR` is "False":
> ```
> unclamped_weight_factor = (log2(max_display_boost) - hdr_capacity_min)
>                         / (hdr_capacity_max - hdr_capacity_min)
> weight_factor = clamp(unclamped_weight_factor, 0.0, 1.0)
> ```
>
> When `hdrgm:BaseRenditionIsHDR` is "True":
> ```
> weight_factor = 1.0 - clamp(unclamped_weight_factor, 0.0, 1.0)
> ```

`max_display_boost` is the display's current headroom — e.g.
`Display.getHdrSdrRatio()` on Android, or an `NSScreen` EDR value on
Apple, as documented in
[`specs/os-rendering/status.md`](../os-rendering/status.md).

The `BaseRenditionIsHDR` flag inverts the direction. When the stored
base is already HDR (e.g. a PQ JPEG with a gain map that *attenuates*
to SDR), a display with no headroom gets the maximally-attenuated
version (weight → 1), and a display with full headroom gets the base
itself unchanged (weight → 0). This is how a single file can carry
HDR-as-primary for HDR-capable readers and fall back to SDR on legacy
ones without a separate preview.

At weight_factor = 0, the formula collapses to:

```
HDR(x, y) = (SDR(x, y) + offset_sdr) * 1.0 - offset_hdr
          = SDR(x, y) + (offset_sdr - offset_hdr)
```

For the recommended defaults of 1/64 for both offsets, that is exactly
SDR. For asymmetric offsets, there's a small constant bias.

At weight_factor = 1, the full declared `gain_map_max` range applies.
Between, the gain exponent interpolates linearly in log space, which
means the multiplicative gain interpolates geometrically.

## The offsets: what they do and why

**Direct quote from UltraHDR v1.1** on the purpose of the offsets:

> The purpose of these values is to balance the ability to raise near
> blacks with the ability to precisely encode smaller gain values.
> Increasing these offset values increases the ability to recover near
> blacks, while maintaining a reasonable value for `map_max_log2`.
> Increasing the values too high can reduce precision of the map.

Two failure modes the offsets prevent:

1. **Pure zero stays zero under a pure-multiplicative gain.** If
   `SDR = 0` and we compute `HDR = SDR * gain`, the result is zero
   regardless of the gain, so you can never lift a pixel that the SDR
   encoder quantized to black up to HDR-bright. With the offset,
   `HDR = (0 + offset_sdr) * gain - offset_hdr` can land anywhere in a
   useful range.

2. **Near-zero SDR values make `pixel_gain` explode at encode.** The
   encode formula is `pixel_gain = (Yhdr + offset_hdr) / (Ysdr + offset_sdr)`.
   Without the denominator offset, a tiny `Ysdr` from JPEG rounding
   next to a non-trivial `Yhdr` produces a huge ratio. Either the
   encoder clamps and loses detail, or it stretches `map_max_log2` to
   absurd values and sacrifices precision across the whole image just
   to fit the shadow spikes. The offset sets a floor on the denominator
   that's much larger than JPEG's 1-LSB linearized value (~3×10⁻⁴ for
   sRGB 1/255), so the ratio stays bounded.

The offsets are *per channel*, which matters: encoders can pick different
shadow-lift characteristics for R/G/B if the HDR master has structured
color noise (most encoders use the same value across all three — it's
rarely worth the extra metadata bytes for a quality gain).

What the offsets do **not** fix: banding from base image quantization.
The formula is `(base + offset) * gain − offset`. The `+ offset` smooths
the very lowest codes but doesn't do anything to 8×8 JPEG DCT blocking or
chroma subsampling in the base. See the banding section below.

## Color space: linear light in the right primaries

A detail that matters for both correctness and for banding: the multiply
happens in **linear light** in the base's color primaries, not in
gamma-encoded values.

The decoder path is:

1. Decode the base (sRGB-encoded JPEG, or PQ-encoded 10-bit AVIF, …) to
   its native encoded form.
2. Apply the base's EOTF to get linear light in the base's primaries
   (linear sRGB / linear Display-P3 / linear BT.2020 / etc.).
3. Compute `HDR = (base_linear + offset_sdr) * gain − offset_hdr`.
4. Output `HDR` as linear in the *same primaries as the base*, which the
   compositor then converts to the display's native space and applies
   its own OETF.

The multiply is *not* in gamma space. Doing it there silently
misbehaves: gamma-encoded values are perceptually non-linear, and a
multiplicative gain in that space creates hue shifts and crushes shadows
differently per channel. This is the #1 decoder bug I'd expect to find
in the wild and is worth double-checking in any new implementation.

UltraHDR v1.1 does not say this in so many words in the body text we
could retrieve, but it's implied by "the color profile of the SDR image
defines the color space of the HDR image" and by the `exp2` operator's
semantics. Our `apply_gainmap` in `ultrahdr-core` linearizes with
`srgb_eotf` before the multiply and `srgb_oetf` after when writing sRGB
outputs.

## Channel count — 1 vs 3

ISO 21496-1 §4.3 (per TOC) allows gain maps with 1 or 3 channels.
UltraHDR v1.1 says:

> Use a single-channel gain map whenever possible.

With a single-channel gain map, the same gain is applied to R, G, and B,
which preserves hue exactly. Per-channel gain maps allow color shifts
(intentional or incidental) and double the metadata plus gain-map bytes,
but can be necessary when the HDR master's R/G/B have structurally
different dynamic range. The metadata fields (`GainMapMin`, `GainMapMax`,
`Gamma`, `OffsetSDR`, `OffsetHDR`) can all be single values or 3-element
arrays independently — e.g. a 3-channel gain map with per-channel
gain_map_min but a single shared `map_gamma`.

In zen crate terms, the metadata struct carries three-element arrays in
all cases but replicates a single authored value across channels.

## Quantization and banding

Four distinct sources. Only the first two are about the gain map itself;
the other two are about the base image (amplified by the gain multiply)
and about the resampling path.

### (1) Gain map value quantization

UltraHDR v1.1 JPEG stores `encoded_recovery` as an 8-bit JPEG, so 256
discrete values across `[map_min_log2, map_max_log2]`. The step size in
log-gain space is:

```
step_stops = (map_max_log2 - map_min_log2) / 255
```

Rough numbers, assuming `map_gamma = 1.0`:

| Declared range | Log2 range | Step (stops) | Comment |
|---|---|---|---|
| 4× (`log2` = 2) | 2 | 0.0078 | Well below any reasonable threshold |
| 8× (`log2` = 3) | 3 | 0.0118 | Near the Weber threshold for smooth gradients (~1%) |
| 16× (`log2` = 4) | 4 | 0.0157 | Visible on wide smooth regions with high contrast sensitivity |
| 256× (`log2` = 8) | 8 | 0.0314 | Clearly visible on smooth HDR-sky gradients |

Caveats on reading these numbers:

- "Visible" is viewing-condition dependent. The eye's contrast sensitivity
  peaks near ~3–5 cycles per degree and is much lower at both higher
  and lower spatial frequencies. A 0.015-stop step is visible on a
  large smooth gradient viewed up close but imperceptible on a noisy,
  textured, or peripheral region.
- Weber's law (~1% perceptual threshold) only applies at mid-range
  luminances and is itself an approximation. Near black and near peak
  the threshold is worse.
- Dithering, display noise, and ambient illumination all raise the
  effective visible threshold.

The numbers above are a rough ballpark; they suggest that 8-bit gain
maps are marginal above ~4-stop declared headroom and unsuitable above
~8-stop, which matches practical reports from UltraHDR encoder tuning.

**`map_gamma` is the mitigation knob.** The encoder can warp the
encoded-recovery → log-recovery mapping non-uniformly, e.g. by choosing
`map_gamma = 2.2` to put more precision into the dark end of the log
range. The UltraHDR v1.1 doc recommends 1.0 and calls gamma-based
warping a last resort "if your gain map has a very uneven distribution
of `log_recovery(x, y)` values." libavif and our `ultrahdr-core` default
to 1.0.

**AVIF/HEIC gain maps are not restricted to 8-bit.** libavif ships
gain map support via AV1-coded image items whose depth inherits from
the AV1 profile — 8, 10, or 12 bit. A 10-bit gain map at an 8-stop
range gives 8/1023 ≈ 0.0078 stops/code (4× finer than 8-bit) and
kills this source of banding for practical headrooms. UltraHDR's
8-bit restriction is a consequence of using JPEG as the gain map
container, not an ISO 21496-1 limit. The ISO spec's §4.4 on
quantization is not in our extracted sample, so we don't have the
full picture of what the spec normatively permits — but libavif's
multi-bit-depth implementation is at least evidence that more than
8 bits is allowed by the ISO binding through the AVIF/HEIF spec.

### (2) `map_gamma` warp

The gamma warp is a trade, not a free precision gain: more bits for
one end means fewer for the other. Used naively it can shift where
banding appears without reducing it, or introduce its own artifact
at the warp "hinge" if the decoder and encoder disagree on precision.

### (3) Base image quantization amplified by the gain multiply

The more common banding source in practice. The base JPEG has:

- 8-bit gamma-encoded per channel → linear LSBs unevenly spaced (fine
  at black, coarse at white).
- 8×8 DCT blocking at low Q factors.
- 4:2:0 chroma subsampling in most defaults.
- Quantization of DC and AC coefficients.

Every one of these is a source of per-pixel error in the linearized
base. The gain map formula *multiplies* that error by the current gain
— a 4× gain at a highlight produces 4× the absolute per-pixel error
there. In perceptual terms this is roughly the same contrast, but at
higher absolute luminance, where the eye's contrast sensitivity is
also higher.

The offsets do not help here. `(base + offset_sdr) * gain` amplifies
base noise proportionally to gain regardless of offset.

Practical mitigations:

- Higher-Q base JPEG, or a 10-bit AVIF base with a 10-bit coded gain
  map.
- Dithering during base encode (most JPEG encoders do not do this by
  default).
- Encoder-side chroma upsampling before tone mapping, so chroma bands
  aren't locked into the 4:2:0 grid.

### (4) Resampling of a sub-sampled gain map

ISO 21496-1 §6.2.2 allows the gain map to be smaller than the base.
Half or quarter resolution is typical — the gain map is a low-frequency
signal, so downsampling loses little and saves significant bytes.

At decode time, the gain map is upsampled back to base resolution.
**Bilinear upsample actively reduces gain map banding** because it
creates new intermediate gain values between the coded ones:

- A gain map coded with 0.03 stops/code, bilinearly upsampled 2×, has
  effective 0.015 stops between samples along linear axes (the halfway
  interpolant sits between two discrete codes).
- Edge-aware upsamples (Lanczos, bicubic) do better still but can
  overshoot.

This is a *feature* of the spec, not a side effect. Encoders should
not pick nearest-neighbor upsampling even if the spec allows it.

## Interaction of weight factor with perceived banding

Worth calling out because it's non-obvious: at low `weight_factor`, gain
map banding is proportionally smaller in the final output.

Because `exp2(log_boost * w)` interpolates the log gain by `w`, the
effective output gain range when the display has partial headroom is
`(gain_max)^w`. An 8-stop gain range at `w = 0.25` behaves like a
2-stop range for the purposes of per-code step size in the *output*
— the 0.031-stop-per-code gain map banding becomes 0.008-stop-per-code
in the reconstructed HDR. As the display dims or the user has less
HDR capacity, banding silently becomes less visible.

Conversely, banding is worst when the display has *full* headroom,
exactly when the HDR impact is meant to be dramatic. Encoders and
reviewers should validate on high-headroom displays to catch banding
that hides on the author's own dimmer panel.

This interaction does not help with base quantization banding, which
scales with the same `w` — 4× gain on a banded base at `w = 1.0`
becomes 1.7× gain at `w = 0.5`, still amplifying the base noise by
that factor.

## Per-format gain map storage depth

| Format | Gain map container | Max gain map bit depth | Source |
|---|---|---|---|
| UltraHDR JPEG (v1.1) | secondary JPEG image | 8 bits | UltraHDR v1.1 doc: *"must be encoded using 8-bit, unsigned integer values"* |
| AVIF | AV1-coded `tmap` image item | 8 / 10 / 12 bits (AV1 profiles) | libavif `gainmap.c`; no 8-bit restriction visible |
| HEIC | HEVC-coded `tmap` image item | Inherits HEVC profile (8–16 bit theoretically) | Unverified — follow the HEIF Amd 1 body text |
| JXL | `jhgm` box around JXL codestream | Inherits JXL capabilities | Unverified |
| PNG (proposed) | `gDAT` chunk | Proposal; TBD | w3c/png#380 |

Only the UltraHDR v1.1 JPEG number is fully verified from a primary
source. The others follow the underlying codec's capabilities but are
worth direct verification when we encounter a file that exercises them.

## Unverified claims and open questions

Items I could not verify from authoritative sources in this session and
should not be stated as fact elsewhere:

1. **ISO 21496-1 §4.4 allowing float16 gain map pixel storage.** I
   claimed this in an earlier conversation based on memory; the free
   sample PDF does not include §4.4 body text and I can't confirm it.
   The libavif and UltraHDR evidence is about integer bit-depth via
   AV1 / JPEG, not float16. The repo's
   [`status.md`](status.md) for ISO 21496-1 shows only the TOC entry
   "4.4 Gain map quantization". Treat float16 as an open question.

2. **Per-channel `map_gamma` being different across R/G/B in any
   shipping encoder.** The field is per-channel in libavif and in our
   own metadata struct, but every default I've seen is uniform. Worth
   surveying real encoders' outputs to confirm whether anyone actually
   uses non-uniform gamma.

3. **The exact perceptual threshold for gain map banding under
   different viewing conditions.** I cited 0.01 stops as a rough Weber
   ballpark, but the real threshold depends on spatial frequency,
   adaptation state, and display surround luminance. Anyone claiming a
   specific threshold (including me in earlier prose) is
   oversimplifying. If the question matters for an encoder decision,
   run a DSIS-style study on target displays rather than trusting the
   ballpark.

4. **Android libtonemap's per-layer interaction with gain map
   reconstruction.** The Hermite-based `Android13` algorithm in
   [`libs/tonemap/tonemap.cpp`](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/main/libs/tonemap/tonemap.cpp)
   runs when content exceeds display capacity, but it's not clear from
   just the source whether the gain map reconstruction path in
   `SkGainmapShader` passes through it on Chromium/Android or bypasses
   it. Empirical test needed.

5. **HEIC's gain map bit-depth behavior.** Listed as "inherits HEVC" in
   the table above based on analogy to AVIF; we haven't captured a
   HEIC test vector with a >8-bit gain map yet. See the HEIC test
   corpus capture item in [`TODO.md`](../../TODO.md).

## The one-line summary, stripped of oversimplification

Gain maps apply an affine transform `(base + offset_sdr) * gain(w) − offset_hdr`
in linearized base-color-space light, where `gain(w)` is a per-channel
display-adaptive scale derived from a 256-level log2-quantized recovery
map, interpolated to base resolution, optionally warped by a per-channel
`map_gamma`, and scaled by a display-headroom-driven weight `w`. The
offsets exist to balance shadow lift against `map_max_log2` budget, not
to prevent banding. Banding comes from gain map quantization (worst at
wide headrooms on 8-bit UltraHDR JPEG, mitigated by higher bit-depth AVIF
gain maps and by bilinear gain-map upsampling) and from base image
quantization amplified by the gain multiply (mitigated only by raising
base quality). The weight factor partially masks gain map banding at
reduced display headroom; it does not help base banding.
