#!/usr/bin/env python3
"""Generate a golden `jhgm` box bundle matching libjxl's gain_map_test.cc layout.

Produces a byte-exact reproduction of `GoldenTestGainMap(has_icc=True, has_color_encoding=True)`
from libjxl/lib/extras/gain_map_test.cc so zenjxl-decoder can differential-test
against it.

Wire layout (from libjxl source):

  u8   jhgm_version              = 0x00
  u16  gain_map_metadata_size    BE
  [u8] placeholder_metadata                  // libjxl placeholder string
  u8   color_encoding_size                    // 0 or 3
  [u8] color_encoding                         // 3-byte libjxl bit-packed
  u32  icc_size                  BE          // 0 or compressed ICC size
  [u8] icc_data                               // compressed ICC profile
  [u8] jxl_codestream                         // naked codestream placeholder

No deps. Writes to the given path.

Usage:
    python3 gen-jhgm-golden.py out.jhgm.bin
"""
import struct
import sys
from pathlib import Path


PLACEHOLDER_METADATA = (
    b"placeholder gain map metadata, fill with actual example after (ISO "
    b"21496-1) is finalized"
)
PLACEHOLDER_CODESTREAM = b"placeholder for an actual naked JPEG XL codestream"

# 3-byte "JXL bit-packed linear sRGB (not gray)" from libjxl test, placeholder.
# See lib/extras/gain_map_test.cc:30 — `{0x50, 0xb4, 0x00}`.
COLOR_ENCODING_LINEAR_SRGB = bytes([0x50, 0xB4, 0x00])

# A minimal non-empty "compressed ICC" blob. libjxl uses a real brotli-compressed
# ICC profile (~136 bytes from `GetCompressedIccTestProfile`). For our test vector
# we just write a 16-byte placeholder so parsers exercise the length field without
# depending on real ICC bytes.
PLACEHOLDER_COMPRESSED_ICC = b"FAKEBROTLIICCXX!"


def build_jhgm_payload(
    *,
    jhgm_version: int = 0,
    metadata: bytes = PLACEHOLDER_METADATA,
    color_encoding: bytes | None = COLOR_ENCODING_LINEAR_SRGB,
    compressed_icc: bytes | None = PLACEHOLDER_COMPRESSED_ICC,
    codestream: bytes = PLACEHOLDER_CODESTREAM,
) -> bytes:
    buf = bytearray()
    buf.append(jhgm_version)
    buf += struct.pack(">H", len(metadata))
    buf += metadata
    if color_encoding is None:
        buf.append(0)
    else:
        assert len(color_encoding) <= 255
        buf.append(len(color_encoding))
        buf += color_encoding
    if compressed_icc is None:
        buf += struct.pack(">I", 0)
    else:
        buf += struct.pack(">I", len(compressed_icc))
        buf += compressed_icc
    buf += codestream
    return bytes(buf)


def wrap_in_isobmff_box(fourcc: bytes, payload: bytes) -> bytes:
    """Wrap `payload` in an ISOBMFF box with the given 4-char type."""
    assert len(fourcc) == 4
    size = 8 + len(payload)
    assert size < 2**32
    return struct.pack(">I4s", size, fourcc) + payload


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gen-jhgm-golden.py <output.jhgm.bin>", file=sys.stderr)
        return 2
    out_path = Path(argv[1])
    payload = build_jhgm_payload()
    box = wrap_in_isobmff_box(b"jhgm", payload)
    out_path.write_bytes(box)
    print(f"wrote {out_path} ({len(box)} bytes)")

    # Also write the no-color-encoding, no-icc variants for testing fallback paths.
    minimal = build_jhgm_payload(
        color_encoding=None,
        compressed_icc=None,
    )
    minimal_box = wrap_in_isobmff_box(b"jhgm", minimal)
    minimal_path = out_path.with_suffix(".minimal.bin")
    minimal_path.write_bytes(minimal_box)
    print(f"wrote {minimal_path} ({len(minimal_box)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
