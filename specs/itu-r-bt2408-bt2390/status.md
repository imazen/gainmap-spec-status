# ITU-R BT.2408-8 and BT.2390-11 — HDR production practices and transfer functions

## Identification

- **BT.2408-8:** Report ITU-R BT.2408-8 (11/2024) — "Suggested guidance for
  operational practices in high dynamic range television production"
- **BT.2390-11:** Report ITU-R BT.2390-11 (10/2023) — "High dynamic range
  television for production and international programme exchange"
- Both are freely downloadable from ITU-R.

## Why these matter for gain maps

Gain map encoders must produce an SDR base from an HDR master (or vice versa).
The ISO 21496-1 spec defines how to *store and apply* a gain map, but not how
to *generate* the SDR base or HDR alternate — that's a tone mapping question.
BT.2408 and BT.2390 are the ITU's normative-adjacent guidance on how that tone
mapping should work, and they define the specific formulas that platform
implementations (Android's `libtonemap`, Apple's EDR pipeline) reference or
approximate.

Additionally, the gain map `weight_factor` derives from display headroom, and
BT.2408 defines the reference white levels and display adaptation that inform
what "headroom" means physically.

## BT.2408-8 key content for gain map work

### 1. Reference white: 203 cd/m2 = 58% PQ = 75% HLG

BT.2408 §2.2 establishes the HDR Reference White at 203 cd/m2 for both PQ
and HLG production. This is the luminance of a diffuse 100% reflectance
white card:

- **PQ:** 58% signal level → `EOTF_PQ(0.58) = 203 cd/m2`
- **HLG:** 75% signal level → 203 cd/m2 on a 1000 cd/m2 display

This is the anchor for the gain map `weight_factor` computation: when the
display's SDR reference white is at 203 cd/m2 and the display's peak is
at `203 * max_display_boost`, the gain map scales by `w` in log space.

### 2. EETF — Electrical-Electrical Transfer Function (Annex 5)

The core tone mapping curve for adapting PQ content to displays with lower
dynamic range. Five steps:

**Step 1 — Normalize** PQ values to the mastering display's range:

```
E1 = (E' - PQ(LB)) / (PQ(LW) - PQ(LB))
```

Where `LB`, `LW` are mastering display black/white luminance. If unknown,
use `LB=0`, `LW=10000`.

**Step 2 — Compute target display normalized values and knee start:**

```
minLum = (PQ(Lmin) - PQ(LB)) / (PQ(LW) - PQ(LB))
maxLum = (PQ(Lmax) - PQ(LB)) / (PQ(LW) - PQ(LB))
KS = 1.5 * maxLum - 0.5
b = minLum
```

**Step 3 — Apply EETF:**

```
E2 = E1               for E1 < KS        (1:1 pass-through)
E2 = P[E1]            for KS <= E1 <= 1   (Hermite knee roll-off)
E3 = E2 + b*(1-E2)^4  for 0 <= E2 <= 1    (black level lift with taper)
```

The `(1-E2)^4` tapering factor is critical — without it, the black level
lift raises midtones/highlights on PQ's perceptually uniform code space
(unlike gamma curves where it's negligible).

**Step 4 — Hermite spline:**

```
T[A] = (A - KS) / (1 - KS)
P[B] = (2T^3 - 3T^2 + 1)*KS + (T^3 - 2T^2 + T)*(1-KS) + (-2T^3 + 3T^2)*maxLum
```

Standard cubic Hermite from KS to maxLum. The 1:1 central region
transitions smoothly into the compressed highlights.

**Step 5 — Denormalize** back to PQ:

```
E4 = E3 * (PQ(LW) - PQ(LB)) + PQ(LB)
```

### 3. EETF application color spaces

The EETF can be applied in five color representations, each with different
tradeoffs for hue preservation, saturation behavior, and gamut safety:

| Space | Out-of-gamut risk? | Desaturation | Hue preservation |
|---|---|---|---|
| ICTCP | Yes → needs gamut mapping | Natural (perceptual) | Good (ICTCP hue) |
| Y'Cb'Cr' | Yes → needs gamut mapping | Natural | Approximate |
| YRGB | Yes → needs gamut mapping | None (preserves chromaticity) | Exact chromaticity |
| R'G'B' | No | Excessive for bright saturated | Some hue shifts |
| maxRGB | No (for highlight compression) | None (preserves chromaticity) | Exact chromaticity |

BT.2408 notes that blending R'G'B' with maxRGB can control desaturation
and hue changes without requiring gamut mapping. For gain map SDR base
generation, R'G'B' is the simplest safe choice; ICTCP gives the best
perceptual results but requires a gamut mapping pass.

**Formulas for each application space:**

- **ICTCP:** Apply EETF to I, scale CT/CP by `min(I2/I1, I1/I2)`
- **Y'Cb'Cr':** Apply EETF to Y', scale Cb'/Cr' by `min(Y'2/Y'1, Y'1/Y'2)`
- **YRGB:** `Y = 0.2627R + 0.6780G + 0.0593B`; EETF on Y; scale RGB by `Y2/Y1`
- **R'G'B':** Apply EETF independently per channel
- **maxRGB:** `M = max(R,G,B)`; EETF on M; scale RGB by `M2/M1`

### 4. SDR→HDR mapping (§5.1): display-referred vs scene-referred

Two fundamental approaches to producing an SDR↔HDR pair:

**Display-referred** (§5.1.1–5.1.3): preserves the *appearance* of SDR
content on an HDR display. The standard path for including graded SDR
content in HDR programmes.

```
SDR_linear = BT1886_EOTF(V) * 2.03      // scale 100→203 cd/m2
HDR = PQ_inverse_EOTF(SDR_linear)        // or HLG inverse EOTF
```

The 2.03x factor maps SDR peak white (100 cd/m2) to HDR reference white
(203 cd/m2). This is a pure linear scaling in display light.

A 2.03x linear scaling does NOT maintain subjective SDR appearance on a
203 cd/m2 HDR display because the eye's response is nonlinear. To
preserve the perceptual look of 100 cd/m2 SDR, an OOTF gamma adjustment
of **1.15–1.16** is applied to the scaled display light (BBC and ARIB
subjective tests, §5.1.3.2).

**Scene-referred** (§5.1.4): preserves *camera signals*, not display
appearance. Used when mixing SDR and HDR cameras in live production.
The SDR signal is treated as scene light (inverse OETF → linear scene),
scaled to the HDR signal level, then re-encoded.

For gain map work, **display-referred** is the standard choice — it
produces an SDR base that visually matches what the viewer would see on
an SDR display, which is what the gain map formula reconstructs from.

### 5. HDR→SDR down-mapping (§5.2)

Two approaches:

- **Hard clipping** at HDR reference white (or other threshold). Simple,
  preserves lowlights/midtones exactly, discards highlights.
- **Tone-mapped down-mapping** with a compressing knee. Preserves
  highlight detail at the cost of midtone shifts. BT.2446 describes
  three specific methods.

For gain map encoding, the SDR base is effectively a tone-mapped
down-mapping of the HDR master. The gain map stores the per-pixel
difference so the HDR can be reconstructed.

### 6. Round-trip considerations (§7.7)

SDR→HDR→SDR round-tripping is inherently lossy. BT.2408 notes:

- Direct-mapping (no highlight expansion) is preferred for live production
  where round-trip fidelity matters.
- The "hybrid-linear" down-mapper (inverse of 2.03x up-mapping) minimizes
  round-trip losses by placing HDR highlights in the SDR super-white range
  (signals above nominal 100%), mapping HDR reference white to ~95% SDR.
- Non-linear down-mapping (with OOTF gamma) cannot perfectly round-trip
  with non-linear up-mapping — the optimum is still under investigation.

This matters for gain map re-encode: if an image is decoded (SDR + gain
map → HDR), edited, and re-encoded (HDR → new SDR + new gain map), the
round-trip characteristics of the tone mapping choice affect whether the
re-encoded SDR base matches the original.

### 7. Annex 11 — 203↔100 cd/m2 SDR conversion

When SDR content is produced at 203 cd/m2 peak white (the NBCU workflow
from Annex 10) and needs to be displayed on a 100 cd/m2 reference
monitor (BT.2035), a gamma correction of **1/1.08** preserves shadow
detail near black. The inverse (1.08) handles 100→203.

The derivation preserves luminance at an assumed perceivable black level
of 0.02 cd/m2: `(0.02/203)^(1/1.08) * 100 ≈ 0.02`.

This is relevant because the gain map's SDR base may be mastered for
either 100 or 203 cd/m2 reference white, and downstream consumers
expecting the other level need this correction.

## BT.2390-11 key content for gain map work

### 8. HLG system gamma formula

The HLG display gamma adapts to the monitor's peak luminance:

**Simple model** (400–2000 cd/m2):
```
gamma = 1.2 + 0.42 * log10(LW / 1000)
```

**Extended model** (all luminances):
```
gamma = 1.2 * 1.111^(log2(LW / 1000))
```

| Peak luminance | Gamma |
|---|---|
| 400 cd/m2 | 1.03 |
| 600 cd/m2 | 1.11 |
| 800 cd/m2 | 1.16 |
| 1000 cd/m2 | 1.20 |
| 1500 cd/m2 | 1.27 |
| 2000 cd/m2 | 1.33 |

### 9. HLG OOTF — luminance-preserving gamma

Unlike SDR (which applies gamma independently to R, G, B, boosting
saturation), HLG applies gamma to the luminance component only:

```
Y_s = 0.2627*R_s + 0.6780*G_s + 0.0593*B_s

R_D = alpha * Y_s^(gamma-1) * R_s
G_D = alpha * Y_s^(gamma-1) * G_s
B_D = alpha * Y_s^(gamma-1) * B_s
```

This preserves scene chromaticity through the display rendering. The
"traditional colour reproduction" (SDR-like saturated look) can be
achieved by applying gamma=1.2 per-channel then dividing by
Y_s^(1.2-1) — a post-process, not a change to the OOTF.

### 10. Surround compensation

Display gamma needs further adjustment for non-reference viewing:

```
gamma_bright = gamma_ref - 0.076 * log10(L_amb / 5)
```

Where `L_amb` is ambient luminance (reference = 5 cd/m2). A typical
bright studio at 64 cd/m2 reduces gamma by ~0.08.

This matters for gain map display because the "correct" SDR rendering
depends on the viewing environment, not just the display peak.

### 11. Black level lift (HLG)

```
beta = sqrt(3 * (L_B / L_W)^(1/gamma))
```

Applied to the HLG EOTF as `max(0, (1 - beta) * E' + beta)` before
the inverse OETF chain. Adapts the signal to the display's actual
black level. `L_B = 0` (reference condition) gives `beta = 0`
(no lift).

### 12. PQ↔HLG conversion at 1000 cd/m2 (from BT.2408 §6)

The reference conversion uses a common peak luminance of 1000 cd/m2:

- **PQ→HLG:** PQ_EOTF → display light → HLG_inverse_EOTF
  (with LW=1000, LB=0, gamma=1.2)
- **HLG→PQ:** HLG_EOTF → display light → PQ_inverse_EOTF

For PQ content exceeding 1000 cd/m2, three options:
1. Clip to 1000 (simple, idempotent across round-trips)
2. Static EETF mapping to 1000 (avoids hard clip, not round-trip safe)
3. Dynamic mapping to 1000 (adaptive, survives round-trips after first pass)

### 13. 8-bit content warning (§5.5)

When up-mapping 8-bit SDR content to HDR, highlight expansion amplifies
quantization artifacts. BT.2408 warns that 8-bit resolution "will limit
the amount of highlight expansion that can be applied before banding and
other artefacts become visible." This directly parallels the gain map
banding analysis in [`apply-math-and-banding.md`](../iso-21496-1/apply-math-and-banding.md).

## Follow-ups for zentone and the audit

- [ ] Verify `zentone::Bt2408Tonemapper::make_luma_scale` matches the EETF
  Hermite spline from Annex 5 step by step. The KS, tapering, and
  denormalization must match.
- [ ] Document which EETF application space zentone uses (R'G'B' per-channel
  is the current default — confirm this matches expected behavior for gain
  map SDR base generation).
- [ ] Add the 1.15–1.16 OOTF gamma adjustment as an option in zentone's
  display-referred SDR→HDR path, for producing an SDR base that
  preserves subjective appearance at 203 cd/m2.
- [ ] Consider the 1/1.08 gamma correction (Annex 11) as a post-process
  option when the SDR base targets a 100 cd/m2 reference display but
  the gain map system assumes 203 cd/m2.
- [ ] Read Android `libtonemap` `Android13` algorithm in full and compare
  to the BT.2408 Annex 5 EETF — document whether they're the same
  curve family or just both Hermite-based.
- [ ] Verify the BT.2390 surround compensation formula against Apple's
  EDR headroom model — is the dynamic headroom already accounting
  for ambient conditions, making this moot for gain map applications?
