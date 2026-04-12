#!/usr/bin/env python3
"""Generate ISO 21496-1:2025 gain map metadata test blobs.

Produces two variants matching the zencodec::gainmap wire format:

- ``iso21496_jpeg.bin``: JpegApp2 / JXL `jhgm` format (no version byte prefix)
- ``iso21496_avif.bin``: AVIF `tmap` format (with version byte prefix)

Both encode a single-channel gain map with placeholder values. These are the
canonical parser-test fixtures for byte-exact compliance.

Layout:

  [version: u8]          // AVIF only
   min_version: u16 BE   = 0
   writer_version: u16 BE = 0
   flags: u8             = 0x00 (single-channel, full form, SDR base, not common denom)
   base_hdr_headroom_n:  u32 BE
   base_hdr_headroom_d:  u32 BE
   alt_hdr_headroom_n:   u32 BE
   alt_hdr_headroom_d:   u32 BE
   // per channel (1 or 3 channels):
   gain_map_min_n:       i32 BE
   gain_map_min_d:       u32 BE
   gain_map_max_n:       i32 BE
   gain_map_max_d:       u32 BE
   gamma_n:              u32 BE
   gamma_d:              u32 BE
   base_offset_n:        i32 BE
   base_offset_d:        u32 BE
   alt_offset_n:         i32 BE
   alt_offset_d:         u32 BE

Values used (one channel):

  base_hdr_headroom   = 0 / 1    (log2, 0 = SDR)
  alt_hdr_headroom    = 13 / 10  (log2, 1.3 ≈ 2.46x peak brightness)
  gain_map_min        = 0 / 1    (log2)
  gain_map_max        = 13 / 10  (log2)
  gamma               = 1 / 1
  base_offset         = 1 / 64   (ISO default)
  alternate_offset    = 1 / 64   (ISO default)
"""
import struct
import sys
from pathlib import Path


def pack_ufrac(num: int, den: int) -> bytes:
    return struct.pack(">II", num, den)


def pack_frac(num: int, den: int) -> bytes:
    return struct.pack(">iI", num, den)


def build_metadata_full(with_version_byte: bool) -> bytes:
    buf = bytearray()
    if with_version_byte:
        buf.append(0x00)  # AVIF version byte
    # common header
    buf += struct.pack(">HHB",
        0,        # min_version
        0,        # writer_version
        0x00,     # flags — single-channel, full form, SDR base
    )
    # headroom (two UFractions)
    buf += pack_ufrac(0, 1)    # base_hdr_headroom  = 0.0 (SDR)
    buf += pack_ufrac(13, 10)  # alt_hdr_headroom   = 1.3 (~2.46x)
    # one channel (5 fractions: min, max [signed]; gamma [unsigned]; offsets [signed])
    buf += pack_frac(0, 1)     # gain_map_min
    buf += pack_frac(13, 10)   # gain_map_max
    buf += pack_ufrac(1, 1)    # gamma
    buf += pack_frac(1, 64)    # base_offset
    buf += pack_frac(1, 64)    # alternate_offset
    return bytes(buf)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gen-iso21496.py <output_dir>", file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    jpeg_blob = build_metadata_full(with_version_byte=False)
    avif_blob = build_metadata_full(with_version_byte=True)

    (out_dir / "iso21496_jpeg.bin").write_bytes(jpeg_blob)
    (out_dir / "iso21496_avif.bin").write_bytes(avif_blob)

    print(f"iso21496_jpeg.bin: {len(jpeg_blob)} bytes")
    print(f"iso21496_avif.bin: {len(avif_blob)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
