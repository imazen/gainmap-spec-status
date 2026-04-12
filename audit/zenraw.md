# zenraw — Apple HDR gain map in DNG/AMPF (+ terminology collision)

## Status: **partially compliant** (Apple path parsed as vendor metadata)

`zenraw` reads Apple's HDR gain map embedded in APPLEDNG / AMPF files via
an MPF structure. It deliberately does **not** treat the Apple gain map as
a canonical ISO 21496-1 record — because it isn't one. Apple ships a
vendor-specific metadata schema and the Apple→ISO conversion is lossy.

## Terminology collision

**Two different things in `zenraw` are called "gain map":**

1. **DNG OpcodeList2 GainMap (opcode 9)** — a spatially-varying gain grid
   used for lens shading correction, defined by Adobe DNG 1.3+. It has
   nothing to do with HDR and predates ISO 21496-1.
2. **Apple MPF HDR gain map** — the SDR→HDR reconstruction image inside
   APPLEDNG / AMPF files.

Both are referred to as "gain maps" in the codebase and documentation.
This is a source of bugs waiting to happen. We should rename one of them
in the public API:

- Keep "gain map" for the HDR sense (the ISO 21496-1 meaning).
- Rename the DNG opcode-9 thing to "lens shading map" or "gain table"
  (Adobe's DNG spec sometimes calls it a gain table, sometimes gain map).

## Files

- `~/work/zen/zenraw/src/apple.rs:275+` — `GainMapInfo` struct (HDR gain map)
- `~/work/zen/zenraw/src/apple.rs:3` — doc: "Parses Apple MakerNote, HDR
  gain map metadata, semantic segmentation"
- `~/work/zen/zenraw/src/tiff_ifd.rs:118` — "ProfileGainTableMap — used by
  Apple ProRAW for Smart HDR"
- `~/work/zen/zenraw/src/dng_render.rs` — ProfileGainTableMap, ProfileHueSatMap processing
- `~/work/zen/zenraw/docs/roadmap.md:26-32` — DNG OpcodeList2 GainMap
  (opcode 9) for lens shading
- `~/work/zen/zenraw/docs/lens-corrections.md:9-12` — DNG GainMap semantics
- `~/work/zen/zenraw/docs/dng-format.md:104` — "9 = GainMap (spatially-
  varying gain — heavy smartphone use)"

## What is implemented

### Apple HDR gain map (`src/apple.rs:275+`)

```rust
pub struct GainMapInfo {
    /// Raw JPEG bytes of the gain map image.
    pub jpeg: Vec<u8>,
    /// ... additional metadata
}
```

Reads from Apple APPLEDNG/AMPF files via MPF (Multi-Picture Format)
structure. Produces raw gain map JPEG bytes plus whatever Apple metadata
we can parse (MakerNote, XMP).

### DNG OpcodeList2 GainMap (documented, partially implemented)

See `docs/roadmap.md` — acknowledges this is needed for smartphone DNG
correctness but does not define HDR behavior.

### ProfileGainTableMap (`src/tiff_ifd.rs:118`)

Adobe DNG 1.6+ tag used for Apple ProRAW Smart HDR profile adjustments.
Parsed but not applied in the current render pipeline.

## Compliance w.r.t. ISO 21496-1

`zenraw` does **not** claim ISO 21496-1 compliance for the Apple gain map.
It treats Apple's output as an opaque vendor blob and leaves conversion to
ISO 21496-1 form up to a higher layer (ultrahdr-core or zenavif-serialize).

This is the right choice. Apple's metadata encoding for gain maps pre-dates
ISO 21496-1 and uses different field names, different ranges, and assumes
Display P3 + BT.2020 PQ as the source/destination colour spaces. Forcing it
into ISO 21496-1 fields would either be lossy or fabricate fields Apple
never published.

## Gaps

1. **Rename DNG opcode-9 gain map** to "lens shading table" in public API
   and docs. Keep the term "gain map" for the HDR sense.
2. **No Apple → ISO 21496-1 conversion path.** When a caller wants to
   transcode an APPLEDNG to an AVIF with a `tmap`, they need:
   - `zenraw::apple::GainMapInfo` extraction (DONE)
   - Apple metadata → ISO 21496-1 field mapping (MISSING)
   - Gain map pixel data → AV1 encoding (via `zenrav1e`)
   - `zenavif-serialize::set_gain_map` wrapping (DONE)
   The middle step is unimplemented. A helper in `ultrahdr-core` or a new
   `gainmap-interop` crate would host it.
3. **DNG OpcodeList2 GainMap** (lens shading) is on the roadmap but not
   implemented. Smartphone DNGs render with dark corners without it.
4. **ProfileGainTableMap** (Apple ProRAW Smart HDR) is parsed but not
   applied. Not directly an HDR-gain-map spec issue but adjacent and causes
   confusion.

## No over-spec

`zenraw` does not pretend Apple's fields are ISO 21496-1 fields. No
fabricated metadata.
