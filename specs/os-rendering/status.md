# OS / compositor rendering of HDR and gain maps

How the major display stacks surface HDR headroom to apps, and where gain
map reconstruction happens in the compositor pipeline. This is not a format
spec — it's the *application side* of the format specs documented under the
other `specs/` directories.

**Why it belongs in this repo.** ISO 21496-1 §6 defines gain map application
as `alt = (base + base_offset) * gain^w - alt_offset`, where the exponent
`w` is derived from the current display headroom relative to the gain map's
declared `alternate_hdr_headroom`. That display headroom is owned by the
compositor, not the decoder. A conformant encoder cannot predict what a
specific device will do without understanding each platform's headroom
model, so we document each model below.

## Shared mental model

Every modern display stack treats HDR as a **headroom ratio** above SDR
reference white, not as an absolute nits value. Two numbers matter:

- **SDR reference white** (ITU-R BT.2408 convention, 203 nits).
- **HDR headroom** = display peak brightness ÷ SDR reference white. Dynamic;
  it changes with user brightness, ambient light, thermal state, battery.

A gain-map-aware compositor reads the current headroom at composition time,
computes `w = clamp(log2(headroom) / log2(gainmap_max_headroom), 0, 1)`,
and applies the gain map accordingly. If headroom is 1 the viewer sees pure
SDR; if headroom meets or exceeds the gain map's declared max, full HDR.

## Android

Android's HDR and gain map support is the most publicly documented of the
consumer platforms and the most relevant reference for cross-platform work.

### Core gain map primitive — `android.graphics.Gainmap`

The framework's Java-level representation of a gain map.

- **Source:** [`frameworks/base/graphics/java/android/graphics/Gainmap.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/graphics/java/android/graphics/Gainmap.java)
- **Fields observed** (per the AOSP source): per-component ratio min/max,
  gamma, epsilon SDR, epsilon HDR, display-ratio-for-full-HDR, minimum
  display ratio, alternative image primaries (ColorSpace), direction
  (SDR↔HDR). This maps directly onto the ISO 21496-1 §5 field set.
- **Attached to a Bitmap** via `Bitmap.getGainmap()` / `setGainmap(Gainmap)`.
  `Bitmap.hasGainmap()` is the detection call on Android 14+; see the
  [Display Ultra HDR images](https://developer.android.com/media/grow/ultra-hdr/display)
  developer guide.

### Reading a gain map JPEG

`ImageDecoder` on Android 14+ automatically parses the UltraHDR XMP/MPF
blob and exposes the gain map through `Bitmap.getGainmap()`. The developer
guide at [`developer.android.com/media/grow/ultra-hdr/display`](https://developer.android.com/media/grow/ultra-hdr/display)
documents this.

### Display headroom query — `Display.getHdrSdrRatio()`

Added in API level 34 (Android 14). Returns the current ratio
`targetHdrPeakBrightnessInNits / targetSdrWhitePointInNits` as a float; if
`isHdrSdrRatioAvailable()` is false the method returns `1.0f`.
See [`android.view.Display` on developer.android.com](https://developer.android.com/reference/android/view/Display)
(search the class page for `getHdrSdrRatio`).

### App-side HDR headroom request

- **API 34 (Android 14):** `ASurfaceTransaction_setExtendedRangeBrightness`
  (NDK). Surface-level control for how much extended-range brightness a
  layer wants.
- **API 35 (Android 15):** `Window.setDesiredHdrHeadroom(float)` (SDK) and
  `ASurfaceTransaction_setDesiredHdrHeadroom` (NDK). The
  [Android 15 features page](https://developer.android.com/about/versions/15/features)
  documents this:

  > Android 15 chooses HDR headroom that is appropriate for the underlying
  > device capabilities and bit-depth of the panel. For pages that have lots
  > of SDR content, such as a messaging app displaying a single HDR
  > thumbnail, this behavior can end up adversely influencing the perceived
  > brightness of the SDR content. Android 15 lets you control the HDR
  > headroom with `setDesiredHdrHeadroom` to strike a balance between SDR
  > and HDR content.

  When both are called, the one called *last* wins — the later call
  overrides the earlier value (NDK doc).

### SDR dimming and composition

The AOSP platform integrator doc at
[`source.android.com/docs/core/display/mixed-sdr-hdr`](https://source.android.com/docs/core/display/mixed-sdr-hdr)
defines Android's mixed-composition model. Key quote:

> When HDR content is on screen, the screen brightness is increased to
> accommodate the increased luminance range of the HDR content. Any SDR
> content that is also on screen is seamlessly dimmed as the screen
> brightness increases so that the perceptual brightness of the SDR
> content doesn't change.

The pipeline is: OEM supplies an `sdrHdrRatioMap` look-up table (a
per-backlight-level SDR white point curve). `DisplayManagerService`
computes the current SDR white point from this table and passes it to
`SurfaceFlinger`, which sends per-layer dimming ratios to the Hardware
Composer (HWC). A `minimumHdrPercentOfScreen` parameter gates when the
panel enters high-brightness mode to avoid flashing for tiny thumbnails.

### Compositor tone mapper — `libtonemap`

**Source:** [`frameworks/native/libs/tonemap/tonemap.cpp`](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/main/libs/tonemap/tonemap.cpp)

- Two algorithms co-exist in the file:
  - **`AndroidO`** — original Android 8 era tonemap, piecewise Hermite.
  - **`Android13`** — current default at head, set via
    `kToneMapAlgorithm = ToneMapAlgorithm::Android13`.
- Source comments reference ITU-R BT.2100 / ST.2084 transfer functions. No
  explicit reference to BT.2408 or BT.2390 was found in the file.
- The library emits both a **CPU implementation** (`lookupTonemapGain`)
  and a **GPU SkSL shader** (`generateTonemapGainShaderSkSL`). Same math,
  two code paths, so RenderEngine composition and direct CPU paths stay
  consistent.
- Hermite interpolation is visible in the source
  (`y1 * (1.0 + 2.0 * t) + h12 * m1 * t`-shaped expression inside the
  `AndroidO` path).

This is the code that runs when SurfaceFlinger has to compress HDR content
beyond the available display headroom, *not* the gain map reconstruction
itself — reconstruction is a separate shader path driven from the
`Gainmap` metadata.

### Detection and capability reporting

- `Display.HdrCapabilities` — [developer.android.com](https://developer.android.com/reference/android/view/Display.HdrCapabilities)
  lists supported HDR types (HDR10, HDR10+, HLG, Dolby Vision).
- `Display.isHdrSdrRatioAvailable()` — API 34 gate for the headroom query.
- `Bitmap.hasGainmap()` — detection for gain-mapped content on API 34+.

## Apple (iOS / iPadOS / macOS)

Apple's model is **Extended Dynamic Range (EDR)**: content renders into an
extended-range color space where pixel values above 1.0 represent
above-SDR-white luminance. The display system tone-maps to the panel at
composition time.

### EDR headroom APIs

- **macOS — [`NSScreen.maximumExtendedDynamicRangeColorComponentValue`](https://developer.apple.com/documentation/appkit/nsscreen/maximumextendeddynamicrangecolorcomponentvalue)**
  returns the current EDR ceiling as a float ≥ 1.0, where 1.0 is SDR
  reference white. It's **dynamic** — a 500-nit MacBook Pro panel at full
  brightness returns ~1.25, rising toward the panel's theoretical peak as
  the user dims the backlight (because more HDR headroom becomes
  available).
- **macOS — [`NSScreen.maximumPotentialExtendedDynamicRangeColorComponentValue`](https://developer.apple.com/documentation/appkit/nsscreen/maximumpotentialextendeddynamicrangecolorcomponentvalue)**
  is the theoretical ceiling, used for capability queries ("can this
  display show HDR at all?"), not for runtime tonemap decisions.
- **iOS — `UIScreen.potentialEDRHeadroom`** and `currentEDRHeadroom` are
  the equivalent on iOS/iPadOS; see Apple's [WWDC22 session 10113
  "Explore EDR on iOS"](https://developer.apple.com/videos/play/wwdc2022/10113/)
  for the introduction.

Both values depend on display backlight, ambient light, thermal state, and
battery — the OS decides how much EDR headroom to grant an app on each
frame. Apps are expected to re-query per frame (or observe change
notifications).

### Opting a layer into EDR

- `CAMetalLayer.wantsExtendedDynamicRangeContent` enables above-1.0 pixel
  values on a Metal-drawn layer. Without it, Metal output is clamped to SDR.
- `CALayer` has equivalent hooks for non-Metal content.
- See [Apple's "Displaying HDR video in an app" and EDR topic pages](https://developer.apple.com/documentation/metal/hdr_content/)
  and the Apple Developer Forums [EDR tag](https://developer.apple.com/forums/tags/edr).

### Gain map / Ultra HDR reading on Apple

Apple added ISO 21496-1-style gain map support across their image APIs
over iOS 17 and 18:

- **WWDC23 session 10181** —
  [*Support HDR images in your app*](https://developer.apple.com/videos/play/wwdc2023/10181/).
  Introduces `UIImageReader` with an HDR preference, `CIImage(expandToHDR:)`,
  `CGImageSourceCreateImageAtIndex` with the `decodeRequest: .decodeToHDR`
  key, and the SwiftUI `allowedDynamicRange(.high)` modifier.
- **WWDC24 session 10177** —
  [*Use HDR for dynamic image experiences in your app*](https://developer.apple.com/videos/play/wwdc2024/10177/).
  Builds on the WWDC23 APIs for animation and compositing.
- **Detection:** `CGColorSpaceUsesITUR_2100TF()`, `UIImage.isHighDynamicRange`.
- WWDC23 also references **ISO/TS 22028-5** as an additional HDR image
  path distinct from gain maps — a native HDR encoding for newer HEIF
  files. See [ISO/TS 22028-5:2023](https://www.iso.org/standard/81863.html)
  for the spec catalogue entry.

### Apple's own gain map variants

`specs/apple/status.md` in this repo already documents the Apple JPEG MPF
+ XMP gain map format (iOS 14+) and the AMPF/APPLEDNG variant. Apple's
in-process decoders handle these natively in Photos and the system image
pipeline, and third-party apps can access them via the WWDC23/24 APIs
above. There is no public Apple-authored spec for either variant; the
interop formulas in `libavif` #2944 / #2960 are the working reference.

## Windows

Less relevant to gain maps (no native UltraHDR support as of Windows 11
23H2, based on public docs), but the SDR/HDR composition model matters for
cross-platform expectations.

- **[HDR settings in Windows](https://support.microsoft.com/en-us/windows/hdr-settings-in-windows-2d767185-38ec-7fdc-6f97-bbc6c5ef24e6)**
  — Microsoft Support page. Documents the *SDR content brightness* slider
  that controls where SDR reference white maps on HDR displays.
- **[Set up Surface devices for SDR & HDR display measurements](https://learn.microsoft.com/en-us/surface/configure-sdr-and-hdr-display)**
  — Microsoft Learn. Gives the nits values for the SDR content brightness
  slider on a representative display: 0% ≈ 81 nits, 50% ≈ 287 nits, 100%
  ≈ 498 nits. (Vendor quotes; actual values are per-display.)
- Gain map rendering on Windows is effectively Chrome's Skia path; see
  below.

## Skia — the cross-platform gain map renderer

Where Chrome, Edge, Firefox-via-Skia, Flutter, and ChromeOS all converge.

- **Source:** [`skia/src/shaders/SkGainmapShader.cpp`](https://skia.googlesource.com/skia/+/refs/heads/main/src/shaders/SkGainmapShader.cpp)
  (BSD-3-Clause, Google LLC 2023).
- Implements a **runtime SkSL shader** (`gGainmapSKSL`) that applies a
  gain map to a base image. Supports single-channel and three-channel
  gain maps and an Apple-variant code path.
- `SkGainmapShader::Make(...)` is the construction entry point. It:
  1. Computes source→destination transform matrices.
  2. Computes the weight `w` from the current HDR display ratio versus the
     gain map's declared min/max display ratios.
  3. Wires the base image and gain map image as child shaders of a
     `SkRuntimeEffect`.
- This is the path Chrome uses to display UltraHDR / Apple JPEG gain maps
  on any platform whose OS compositor does not natively support them.
- Skia's companion types: `SkGainmapInfo` (metadata), `SkGainmapMetadata`
  (serialization). The shader reads `SkGainmapInfo` and produces the
  tone-adapted output.

Chrome surfaces the current display HDR ratio to the shader through its
own color pipeline (driven by Windows `DXGI_OUTPUT_DESC1`, macOS
`NSScreen` EDR, Android `Display.getHdrSdrRatio`, etc.) so the same
SkGainmapShader renders identically across platforms given the same
ratio.

## Implications for the zen codec family and imageflow

1. **Generate gain map pairs, do not tonemap eagerly.** The platforms
   unanimously prefer `(SDR base + gain map)` to a pre-tonemapped SDR
   image. Encoders should write SDR + gain map; decoders / display paths
   should reconstruct HDR at the compositor, using whatever headroom is
   currently available. This is the gain map spec's entire point.
2. **`zentone` is the SDR-base generator**, not an OS tonemap
   replacement. Its classical curves are a reasonable starting set for
   producing an SDR rendering alongside an HDR master before computing a
   gain map; the compositor's own tone mapper never runs unless the
   display lacks headroom.
3. **Adaptive fit as provenance.** When re-encoding a
   previously-UltraHDR'd image, fitting a `zentone::experimental::AdaptiveTonemapper`
   on the existing (base, alt) pair recovers whatever curve the original
   encoder used, including hand-edited ones. Detection of a standard
   curve (ongoing work, see `audit/zentone.md`) is the fast path for
   known-encoder outputs.
4. **Match-the-spec is cheaper than match-the-OS.** Android's libtonemap,
   Apple's internal EDR tonemap, and Skia's SkGainmapShader all differ in
   detail but all converge on "read display headroom at composition time,
   reconstruct via the gain map." A correct gain map encode is
   approximately platform-neutral; a baked tonemap is not.

## What this file does not cover

- **HDR10 / HLG video playback pipelines.** `source.android.com/devices/tech/display/hdr`
  and Apple's HDR video topic cover those separately; gain maps are
  specifically an image-domain mechanism.
- **Dolby Vision.** Parallel track, not covered by ISO 21496-1.
- **Exact compositor shader math per platform.** For Android, read
  `libs/tonemap/tonemap.cpp` directly; for Skia, read `SkGainmapShader.cpp`
  directly. Both are short and self-describing.

## Open questions and follow-ups

- Verify whether Android 16 / 17 introduce finer-grained per-surface
  headroom negotiation beyond `setDesiredHdrHeadroom` (API 35 landed the
  first version).
- Capture a minimal test vector per platform showing correct display-side
  reconstruction for inclusion in `test-vectors/`. This is hard because
  the *output* of the pipeline is display pixels, not a file — requires
  screen capture on a real device.
- Verify whether Windows 11 25H2 or Windows 12 adds native UltraHDR
  support (currently we rely on Skia on Windows).
