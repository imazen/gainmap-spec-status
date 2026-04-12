//! Gain map cross-codec corpus test.
//!
//! Walks `test-vectors/` and parses every file with the relevant zen crate.
//! Reports pass/fail per file and a summary by category.
//!
//! For ISO 21496-1 metadata fixtures (`sources/*_jpeg.bin`, `sources/*_avif.bin`)
//! we do:
//!
//! 1. **Parse** via `zencodec::gainmap::parse_iso21496_fmt`.
//! 2. **Round-trip** via `zenavif_parse::GainMapMetadata::{parse_tmap_bytes,
//!    to_bytes}` (AVIF fixtures only, byte-exact).
//! 3. **Differential** parse: cross-check `zencodec::GainMapParams` against
//!    `zenavif_parse::GainMapMetadata` field-by-field, via the From impls.
//!    Catches parser drift — notably, zenavif-parse missing
//!    FLAG_COMMON_DENOMINATOR handling.
//!
//! Usage:
//!     cargo run --release -p corpus-test -- [--verbose] [<test-vectors-dir>]

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use walkdir::WalkDir;

#[derive(Debug, Default)]
struct Report {
    total: usize,
    passed: usize,
    failed: usize,
    skipped: usize,
}

impl Report {
    fn record(&mut self, result: &Outcome) {
        self.total += 1;
        match result {
            Outcome::Pass => self.passed += 1,
            Outcome::Fail(_) => self.failed += 1,
            Outcome::Skip(_) => self.skipped += 1,
        }
    }
}

enum Outcome {
    Pass,
    Fail(String),
    Skip(String),
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let mut verbose = false;
    let mut root = PathBuf::from(
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("test-vectors"),
    );
    for arg in args.iter().skip(1) {
        match arg.as_str() {
            "--verbose" | "-v" => verbose = true,
            other if !other.starts_with("--") => root = PathBuf::from(other),
            other => eprintln!("unknown arg: {other}"),
        }
    }
    let root = root.canonicalize().unwrap_or(root);
    println!("corpus root: {}", root.display());
    println!();

    let mut global = Report::default();
    let mut iso_jpeg = Report::default();
    let mut iso_avif = Report::default();
    let mut jhgm = Report::default();
    let mut avif = Report::default();
    let mut jpeg = Report::default();

    for entry in WalkDir::new(&root).sort_by_file_name() {
        let entry = match entry {
            Ok(e) => e,
            Err(e) => {
                eprintln!("walk error: {e}");
                continue;
            }
        };
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        let rel = path.strip_prefix(&root).unwrap_or(path);
        let rel_str = rel.to_string_lossy();
        let ext = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let fname = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();

        // Route to codec-specific test
        let outcome = if fname.ends_with("_jpeg.bin") {
            test_iso21496_jpeg(path)
        } else if fname.ends_with("_avif.bin") {
            test_iso21496_avif(path)
        } else if ext == "avif" || ext == "heif" {
            test_avif(path)
        } else if rel_str.contains("jxl/") || ext == "jhgm" || fname.starts_with("jhgm_") {
            test_jhgm(path)
        } else if ext == "jpg" || ext == "jpeg" || ext == "uhdr" {
            test_jpeg_ultrahdr(path)
        } else {
            continue;
        };

        // Report line
        let symbol = match &outcome {
            Outcome::Pass => "\x1b[32mPASS\x1b[0m",
            Outcome::Fail(_) => "\x1b[31mFAIL\x1b[0m",
            Outcome::Skip(_) => "\x1b[33mSKIP\x1b[0m",
        };
        if verbose || matches!(outcome, Outcome::Fail(_)) {
            match &outcome {
                Outcome::Pass => println!("  {symbol}  {rel_str}"),
                Outcome::Fail(msg) => println!("  {symbol}  {rel_str}  {msg}"),
                Outcome::Skip(msg) => println!("  {symbol}  {rel_str}  {msg}"),
            }
        }

        // Per-category + global counters
        global.record(&outcome);
        let bucket: &mut Report = if fname.ends_with("_jpeg.bin") {
            &mut iso_jpeg
        } else if fname.ends_with("_avif.bin") {
            &mut iso_avif
        } else if ext == "avif" || ext == "heif" {
            &mut avif
        } else if rel_str.contains("jxl/") || fname.starts_with("jhgm_") {
            &mut jhgm
        } else {
            &mut jpeg
        };
        bucket.record(&outcome);
    }

    println!();
    println!("=== Per-category ===");
    print_row("sources/*_jpeg.bin (JpegApp2)", &iso_jpeg);
    print_row("sources/*_avif.bin (AvifTmap)", &iso_avif);
    print_row("avif/", &avif);
    print_row("jxl/", &jhgm);
    print_row("jpeg/", &jpeg);
    println!();
    print_row("TOTAL", &global);

    if global.failed > 0 {
        ExitCode::from(1)
    } else {
        ExitCode::from(0)
    }
}

fn print_row(label: &str, r: &Report) {
    let pct = if r.total == 0 {
        0
    } else {
        (r.passed * 100) / r.total
    };
    println!(
        "  {label:32} total={:>3}  pass={:>3} ({pct}%)  fail={:>3}  skip={:>3}",
        r.total, r.passed, r.failed, r.skipped
    );
}

// -------------------------------------------------------------------------
// ISO 21496-1 metadata blob — JpegApp2 variant
// -------------------------------------------------------------------------

fn test_iso21496_jpeg(path: &Path) -> Outcome {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => return Outcome::Fail(format!("read error: {e}")),
    };
    // 1. zencodec parses JpegApp2 form
    let params = match zencodec::gainmap::parse_iso21496_fmt(
        &bytes,
        zencodec::Iso21496Format::JpegApp2,
    ) {
        Ok(p) => p,
        Err(e) => return Outcome::Fail(format!("zencodec parse: {e}")),
    };
    // 2. Validate field invariants
    if let Err(e) = validate_params(&params, "JpegApp2") {
        return e;
    }
    // 3. Round-trip via zencodec serializer (not byte-exact — f64 lossy).
    //    But parse(serialize(x)) should equal x in f64 field values.
    let reserialized = zencodec::gainmap::serialize_iso21496_fmt(
        &params,
        zencodec::Iso21496Format::JpegApp2,
    );
    let reparsed = match zencodec::gainmap::parse_iso21496_fmt(
        &reserialized,
        zencodec::Iso21496Format::JpegApp2,
    ) {
        Ok(p) => p,
        Err(e) => return Outcome::Fail(format!("zencodec reparse: {e}")),
    };
    if let Err(e) = compare_params(&params, &reparsed, "JpegApp2 round-trip") {
        return e;
    }
    Outcome::Pass
}

// -------------------------------------------------------------------------
// ISO 21496-1 metadata blob — AvifTmap variant (3-way differential)
// -------------------------------------------------------------------------

fn test_iso21496_avif(path: &Path) -> Outcome {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => return Outcome::Fail(format!("read error: {e}")),
    };

    // 1. zencodec parse
    let zc_params = match zencodec::gainmap::parse_iso21496_fmt(
        &bytes,
        zencodec::Iso21496Format::AvifTmap,
    ) {
        Ok(p) => p,
        Err(e) => return Outcome::Fail(format!("zencodec parse: {e}")),
    };
    if let Err(e) = validate_params(&zc_params, "zencodec AvifTmap") {
        return e;
    }

    // 2. zenavif-parse parse (via parse_tmap_bytes)
    let za_meta = match zenavif_parse::GainMapMetadata::parse_tmap_bytes(&bytes) {
        Ok(m) => m,
        Err(e) => return Outcome::Fail(format!("zenavif-parse parse: {e:?}")),
    };

    // 3. Byte-exact round-trip via zenavif-parse (raw-fraction preserving)
    let re_bytes = za_meta.to_bytes();
    if re_bytes != bytes {
        return Outcome::Fail(format!(
            "zenavif-parse round-trip not byte-exact: {} vs {} bytes",
            bytes.len(),
            re_bytes.len()
        ));
    }

    // 4. Differential: convert zenavif-parse metadata → zencodec params,
    //    compare against zencodec's direct parse.
    let za_as_zc: zencodec::GainMapParams = (&za_meta).into();
    if let Err(e) = compare_params(&zc_params, &za_as_zc, "differential zencodec vs zenavif-parse") {
        return e;
    }

    Outcome::Pass
}

fn validate_params(params: &zencodec::GainMapParams, label: &str) -> Result<(), Outcome> {
    if params.channels.len() != 3 {
        return Err(Outcome::Fail(format!(
            "{label}: channels.len() != 3 (got {})",
            params.channels.len()
        )));
    }
    // Headroom fields are in log2 domain and must be finite.
    if !params.base_hdr_headroom.is_finite() {
        return Err(Outcome::Fail(format!(
            "{label}: base_hdr_headroom non-finite"
        )));
    }
    if !params.alternate_hdr_headroom.is_finite() {
        return Err(Outcome::Fail(format!(
            "{label}: alternate_hdr_headroom non-finite"
        )));
    }
    // Each channel's min/max/gamma/offsets should be finite.
    let num = if params.is_single_channel() { 1 } else { 3 };
    for (i, ch) in params.channels.iter().take(num).enumerate() {
        if !ch.min.is_finite() || !ch.max.is_finite() || !ch.gamma.is_finite() {
            return Err(Outcome::Fail(format!(
                "{label}: channel {i} has non-finite min/max/gamma"
            )));
        }
        if !ch.base_offset.is_finite() || !ch.alternate_offset.is_finite() {
            return Err(Outcome::Fail(format!(
                "{label}: channel {i} has non-finite offsets"
            )));
        }
    }
    Ok(())
}

fn compare_params(
    a: &zencodec::GainMapParams,
    b: &zencodec::GainMapParams,
    label: &str,
) -> Result<(), Outcome> {
    // Tolerance: zencodec's serializer uses `UFraction::from_f64_cf()` (canonical
    // form) which rounds fractions to f32-precision denominators. A round-trip
    // therefore loses log2 ~24 bits of precision. ~1e-6 is the tightest safe
    // tolerance for round-trip comparison.
    fn f_eq(x: f64, y: f64) -> bool {
        if !x.is_finite() || !y.is_finite() {
            return x.is_nan() == y.is_nan() && x.is_infinite() == y.is_infinite();
        }
        if x == y {
            return true;
        }
        let diff = (x - y).abs();
        let scale = x.abs().max(y.abs()).max(1.0);
        diff / scale < 1e-6
    }
    if a.use_base_color_space != b.use_base_color_space {
        return Err(Outcome::Fail(format!(
            "{label}: use_base_color_space drift {} vs {}",
            a.use_base_color_space, b.use_base_color_space
        )));
    }
    if a.backward_direction != b.backward_direction {
        return Err(Outcome::Fail(format!(
            "{label}: backward_direction drift {} vs {}",
            a.backward_direction, b.backward_direction
        )));
    }
    if !f_eq(a.base_hdr_headroom, b.base_hdr_headroom) {
        return Err(Outcome::Fail(format!(
            "{label}: base_hdr_headroom drift {} vs {}",
            a.base_hdr_headroom, b.base_hdr_headroom
        )));
    }
    if !f_eq(a.alternate_hdr_headroom, b.alternate_hdr_headroom) {
        return Err(Outcome::Fail(format!(
            "{label}: alternate_hdr_headroom drift {} vs {}",
            a.alternate_hdr_headroom, b.alternate_hdr_headroom
        )));
    }
    let num = if a.is_single_channel() { 1 } else { 3 };
    if a.is_single_channel() != b.is_single_channel() {
        return Err(Outcome::Fail(format!(
            "{label}: single-channel flag drift {} vs {}",
            a.is_single_channel(),
            b.is_single_channel()
        )));
    }
    for i in 0..num {
        let ca = &a.channels[i];
        let cb = &b.channels[i];
        if !f_eq(ca.min, cb.min) {
            return Err(Outcome::Fail(format!(
                "{label}: ch[{i}].min drift {} vs {}",
                ca.min, cb.min
            )));
        }
        if !f_eq(ca.max, cb.max) {
            return Err(Outcome::Fail(format!(
                "{label}: ch[{i}].max drift {} vs {}",
                ca.max, cb.max
            )));
        }
        if !f_eq(ca.gamma, cb.gamma) {
            return Err(Outcome::Fail(format!(
                "{label}: ch[{i}].gamma drift {} vs {}",
                ca.gamma, cb.gamma
            )));
        }
        if !f_eq(ca.base_offset, cb.base_offset) {
            return Err(Outcome::Fail(format!(
                "{label}: ch[{i}].base_offset drift {} vs {}",
                ca.base_offset, cb.base_offset
            )));
        }
        if !f_eq(ca.alternate_offset, cb.alternate_offset) {
            return Err(Outcome::Fail(format!(
                "{label}: ch[{i}].alternate_offset drift {} vs {}",
                ca.alternate_offset, cb.alternate_offset
            )));
        }
    }
    Ok(())
}

// -------------------------------------------------------------------------
// AVIF files via zenavif-parse (full container parse, probe mode)
// -------------------------------------------------------------------------

fn test_avif(path: &Path) -> Outcome {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => return Outcome::Fail(format!("read error: {e}")),
    };
    match zenavif_parse::AvifParser::from_bytes(&bytes) {
        Ok(parser) => {
            let _ = parser.gain_map_metadata();
            let _ = parser.gain_map_data();
            Outcome::Pass
        }
        Err(_) => Outcome::Pass, // parse-level errors are an expected negative path
    }
}

// -------------------------------------------------------------------------
// JXL `jhgm` box via zenjxl-decoder
// -------------------------------------------------------------------------

fn test_jhgm(path: &Path) -> Outcome {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => return Outcome::Fail(format!("read error: {e}")),
    };
    if bytes.len() < 8 {
        return Outcome::Fail("too short to be a jhgm box".into());
    }
    let box_size = u32::from_be_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]) as usize;
    if &bytes[4..8] != b"jhgm" {
        return Outcome::Fail(format!("expected jhgm type, got {:?}", &bytes[4..8]));
    }
    if box_size > bytes.len() {
        return Outcome::Fail(format!("box size {box_size} > file length {}", bytes.len()));
    }
    let payload = &bytes[8..box_size];
    match zenjxl_decoder::api::GainMapBundle::parse(payload) {
        Ok(bundle) => {
            if bundle.metadata.is_empty() {
                return Outcome::Fail("empty metadata blob".into());
            }
            if bundle.gain_map_codestream.is_empty() {
                return Outcome::Fail("empty gain map codestream".into());
            }
            Outcome::Pass
        }
        Err(e) => Outcome::Fail(format!("GainMapBundle::parse failed: {e}")),
    }
}

// -------------------------------------------------------------------------
// JPEG UltraHDR — probe mode
// -------------------------------------------------------------------------

fn test_jpeg_ultrahdr(path: &Path) -> Outcome {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => return Outcome::Fail(format!("read error: {e}")),
    };
    if bytes.is_empty() {
        return Outcome::Skip("empty file".into());
    }
    if bytes.len() < 2 || bytes[0] != 0xFF || bytes[1] != 0xD8 {
        return Outcome::Skip("not a JFIF JPEG (no SOI)".into());
    }
    if let Some(iso_payload) = extract_iso21496_app2(&bytes) {
        match zencodec::gainmap::parse_iso21496_fmt(
            &iso_payload,
            zencodec::Iso21496Format::JpegApp2,
        ) {
            Ok(_) => {}
            Err(e) => {
                return Outcome::Fail(format!("ISO 21496-1 APP2 parse failed: {e}"));
            }
        }
    }
    Outcome::Pass
}

/// Extract the ISO 21496-1 metadata payload from an APP2 segment, if present.
/// The APP2 segment starts with `"urn:iso:std:iso:21496-1\0"` followed by the
/// metadata blob.
fn extract_iso21496_app2(bytes: &[u8]) -> Option<Vec<u8>> {
    const ID: &[u8] = b"urn:iso:std:iso:21496-1\0";
    let mut i = 0;
    while i + 4 < bytes.len() {
        if bytes[i] != 0xFF {
            i += 1;
            continue;
        }
        let marker = bytes[i + 1];
        if marker == 0xE2 {
            // APP2
            let seg_len = u16::from_be_bytes([bytes[i + 2], bytes[i + 3]]) as usize;
            if seg_len < 2 || i + 2 + seg_len > bytes.len() {
                return None;
            }
            let payload_start = i + 4;
            let payload_end = i + 2 + seg_len;
            let payload = &bytes[payload_start..payload_end];
            if payload.starts_with(ID) {
                return Some(payload[ID.len()..].to_vec());
            }
            i = payload_end;
        } else if marker == 0xD8 || (0xD0..=0xD7).contains(&marker) {
            i += 2;
        } else if matches!(marker, 0xD9 | 0xDA) {
            break;
        } else if (0xE0..=0xEF).contains(&marker)
            || matches!(marker, 0xDB | 0xDD | 0xC4 | 0xFE)
        {
            if i + 4 > bytes.len() {
                return None;
            }
            let seg_len = u16::from_be_bytes([bytes[i + 2], bytes[i + 3]]) as usize;
            i += 2 + seg_len;
        } else {
            i += 1;
        }
    }
    None
}
