#!/usr/bin/env python3
"""Generate ISO 21496-1:2025 gain map metadata fixtures covering parameter axes.

Emits both wire format variants:

- `<case>_jpeg.bin`  — JpegApp2 / JXL `jhgm` form (no version byte prefix)
- `<case>_avif.bin`  — AVIF `tmap` form (with version byte prefix)

Axes covered:

- direction           sdr-base vs hdr-base (`FLAG_BACKWARD_DIRECTION`)
- channels            1 vs 3 (`FLAG_MULTI_CHANNEL`)
- color-space flag    off vs on (`FLAG_USE_BASE_COLOUR_SPACE`)
- common denom        off vs on (`FLAG_COMMON_DENOMINATOR`)
- value ranges        zero, small, negative, large, extreme
- denominators        1, 10, 64, 1000, 65535, u32::MAX

Layout (full form):

    [version: u8]         // AVIF only
    min_version: u16 BE
    writer_version: u16 BE
    flags: u8
    base_hdr_headroom_n: u32 BE
    base_hdr_headroom_d: u32 BE
    alt_hdr_headroom_n:  u32 BE
    alt_hdr_headroom_d:  u32 BE
    for each channel (1 or 3):
        gain_map_min_n: i32 BE
        gain_map_min_d: u32 BE
        gain_map_max_n: i32 BE
        gain_map_max_d: u32 BE
        gamma_n:        u32 BE
        gamma_d:        u32 BE
        base_offset_n:  i32 BE
        base_offset_d:  u32 BE
        alt_offset_n:   i32 BE
        alt_offset_d:   u32 BE

Layout (common-denominator form, FLAG_COMMON_DENOMINATOR set):

    [version: u8]         // AVIF only
    min_version: u16 BE
    writer_version: u16 BE
    flags: u8
    common_d: u32 BE
    base_hdr_headroom_n: u32 BE
    alt_hdr_headroom_n:  u32 BE
    for each channel:
        gain_map_min_n: i32 BE
        gain_map_max_n: i32 BE
        gamma_n:        u32 BE
        base_offset_n:  i32 BE
        alt_offset_n:   i32 BE
"""

import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

FLAG_MULTI_CHANNEL = 0x80
FLAG_USE_BASE_COLOUR_SPACE = 0x40
FLAG_COMMON_DENOMINATOR = 0x08
FLAG_BACKWARD_DIRECTION = 0x04


@dataclass
class Channel:
    min_n: int
    min_d: int
    max_n: int
    max_d: int
    gamma_n: int
    gamma_d: int
    base_offset_n: int
    base_offset_d: int
    alt_offset_n: int
    alt_offset_d: int


@dataclass
class Metadata:
    is_multichannel: bool
    use_base_colour_space: bool
    backward_direction: bool
    common_denominator: bool
    base_hdr_headroom_n: int
    base_hdr_headroom_d: int
    alt_hdr_headroom_n: int
    alt_hdr_headroom_d: int
    channels: list  # [Channel, ...] length 1 or 3
    writer_version: int = 0


def flags_byte(m: Metadata) -> int:
    f = 0
    if m.is_multichannel:
        f |= FLAG_MULTI_CHANNEL
    if m.use_base_colour_space:
        f |= FLAG_USE_BASE_COLOUR_SPACE
    if m.common_denominator:
        f |= FLAG_COMMON_DENOMINATOR
    if m.backward_direction:
        f |= FLAG_BACKWARD_DIRECTION
    return f


def serialize(m: Metadata, with_version_byte: bool) -> bytes:
    buf = bytearray()
    if with_version_byte:
        buf.append(0)
    buf += struct.pack(">HHB", 0, m.writer_version, flags_byte(m))

    if m.common_denominator:
        # All values share a single denominator. Pick the base_hdr_headroom_d
        # as the common denominator; assert everything else matches.
        common_d = m.base_hdr_headroom_d
        assert all(
            d == common_d
            for d in (
                m.base_hdr_headroom_d,
                m.alt_hdr_headroom_d,
                *(
                    x
                    for ch in m.channels
                    for x in (
                        ch.min_d,
                        ch.max_d,
                        ch.gamma_d,
                        ch.base_offset_d,
                        ch.alt_offset_d,
                    )
                ),
            )
        ), "common_denominator form requires identical denominators"
        buf += struct.pack(">I", common_d)
        buf += struct.pack(">II", m.base_hdr_headroom_n, m.alt_hdr_headroom_n)
        for ch in m.channels:
            buf += struct.pack(
                ">iiIii",
                ch.min_n,
                ch.max_n,
                ch.gamma_n,
                ch.base_offset_n,
                ch.alt_offset_n,
            )
    else:
        buf += struct.pack(
            ">IIII",
            m.base_hdr_headroom_n,
            m.base_hdr_headroom_d,
            m.alt_hdr_headroom_n,
            m.alt_hdr_headroom_d,
        )
        for ch in m.channels:
            buf += struct.pack(
                ">iIiIIIiIiI",
                ch.min_n,
                ch.min_d,
                ch.max_n,
                ch.max_d,
                ch.gamma_n,
                ch.gamma_d,
                ch.base_offset_n,
                ch.base_offset_d,
                ch.alt_offset_n,
                ch.alt_offset_d,
            )
    return bytes(buf)


# ─── Curated parameter matrix ─────────────────────────────────────────────────


def ch(
    min_f=(0, 1),
    max_f=(0, 1),
    gamma=(1, 1),
    base_off=(1, 64),
    alt_off=(1, 64),
) -> Channel:
    return Channel(
        min_n=min_f[0], min_d=min_f[1],
        max_n=max_f[0], max_d=max_f[1],
        gamma_n=gamma[0], gamma_d=gamma[1],
        base_offset_n=base_off[0], base_offset_d=base_off[1],
        alt_offset_n=alt_off[0], alt_offset_d=alt_off[1],
    )


def meta(**kwargs):
    defaults = dict(
        is_multichannel=False,
        use_base_colour_space=False,
        backward_direction=False,
        common_denominator=False,
        base_hdr_headroom_n=0,
        base_hdr_headroom_d=1,
        alt_hdr_headroom_n=13,
        alt_hdr_headroom_d=10,
        channels=[ch(min_f=(0, 1), max_f=(13, 10))],
        writer_version=0,
    )
    defaults.update(kwargs)
    return Metadata(**defaults)


I32_MAX = 2**31 - 1
I32_MIN = -(2**31)
U32_MAX = 2**32 - 1


def build_matrix() -> dict[str, Metadata]:
    cases = {}

    # ── direction ──────────────────────────────────────────────────────────
    cases["01_sdr_base_1ch"] = meta()
    cases["02_hdr_base_1ch"] = meta(backward_direction=True)

    # ── channels ───────────────────────────────────────────────────────────
    cases["03_multi_channel_3"] = meta(
        is_multichannel=True,
        channels=[
            ch(min_f=(0, 1), max_f=(13, 10)),
            ch(min_f=(0, 1), max_f=(15, 10)),
            ch(min_f=(0, 1), max_f=(12, 10)),
        ],
    )

    # ── use_base_colour_space flag ─────────────────────────────────────────
    cases["04_use_base_colour_space"] = meta(use_base_colour_space=True)

    # ── common denominator form ────────────────────────────────────────────
    cases["05_common_denom_1ch"] = meta(
        common_denominator=True,
        base_hdr_headroom_n=0, base_hdr_headroom_d=1000,
        alt_hdr_headroom_n=1300, alt_hdr_headroom_d=1000,
        channels=[ch(
            min_f=(0, 1000),
            max_f=(1300, 1000),
            gamma=(1000, 1000),
            base_off=(16, 1000),   # ~1/64 scaled to 1000 denom
            alt_off=(16, 1000),
        )],
    )
    cases["06_common_denom_3ch"] = meta(
        is_multichannel=True,
        common_denominator=True,
        base_hdr_headroom_n=0, base_hdr_headroom_d=1000,
        alt_hdr_headroom_n=1300, alt_hdr_headroom_d=1000,
        channels=[
            ch(min_f=(0, 1000), max_f=(1300, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
            ch(min_f=(-500, 1000), max_f=(1500, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
            ch(min_f=(0, 1000), max_f=(1200, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
        ],
    )

    # ── negative min ───────────────────────────────────────────────────────
    cases["07_negative_min"] = meta(
        channels=[ch(min_f=(-1, 1), max_f=(3, 1))],
    )
    cases["08_large_negative_min"] = meta(
        channels=[ch(min_f=(-8, 1), max_f=(8, 1))],
    )

    # ── large max (big HDR headroom) ───────────────────────────────────────
    cases["09_max_4x"] = meta(
        alt_hdr_headroom_n=2, alt_hdr_headroom_d=1,
        channels=[ch(max_f=(2, 1))],
    )
    cases["10_max_16x"] = meta(
        alt_hdr_headroom_n=4, alt_hdr_headroom_d=1,
        channels=[ch(max_f=(4, 1))],
    )

    # ── varied denominators ────────────────────────────────────────────────
    cases["11_denom_1"] = meta(
        base_hdr_headroom_d=1,
        alt_hdr_headroom_n=2, alt_hdr_headroom_d=1,
        channels=[ch(min_f=(0, 1), max_f=(2, 1), gamma=(1, 1), base_off=(0, 1), alt_off=(0, 1))],
    )
    cases["12_denom_10"] = meta(
        base_hdr_headroom_d=10,
        alt_hdr_headroom_n=13, alt_hdr_headroom_d=10,
        channels=[ch(min_f=(0, 10), max_f=(13, 10), gamma=(10, 10), base_off=(2, 10), alt_off=(2, 10))],
    )
    cases["13_denom_1000"] = meta(
        base_hdr_headroom_d=1000,
        alt_hdr_headroom_n=1300, alt_hdr_headroom_d=1000,
        channels=[ch(min_f=(0, 1000), max_f=(1300, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000))],
    )
    cases["14_denom_65535"] = meta(
        base_hdr_headroom_d=65535,
        alt_hdr_headroom_n=85196, alt_hdr_headroom_d=65535,  # ~1.3
        channels=[ch(min_f=(0, 65535), max_f=(85196, 65535), gamma=(65535, 65535), base_off=(1024, 65535), alt_off=(1024, 65535))],
    )
    # denom = U32_MAX constrains every numerator to ≤ U32_MAX, so we can only
    # express ratios up to 1.0. Use log2=0.5 (UFraction) = half of max.
    cases["15_denom_umax"] = meta(
        base_hdr_headroom_d=U32_MAX,
        alt_hdr_headroom_n=U32_MAX // 2, alt_hdr_headroom_d=U32_MAX,  # = 0.5
        channels=[ch(
            min_f=(0, U32_MAX),
            max_f=(U32_MAX // 2, U32_MAX),  # = 0.5 log2
            gamma=(U32_MAX, U32_MAX),        # = 1.0
            base_off=(67108864, U32_MAX),    # = ~1/64
            alt_off=(67108864, U32_MAX),
        )],
    )

    # ── gamma variations ───────────────────────────────────────────────────
    cases["16_gamma_half"] = meta(
        channels=[ch(gamma=(1, 2))],
    )
    cases["17_gamma_quarter"] = meta(
        channels=[ch(gamma=(1, 4))],
    )
    cases["18_gamma_large"] = meta(
        channels=[ch(gamma=(100, 1))],
    )

    # ── i32 boundary ───────────────────────────────────────────────────────
    cases["19_i32_max_numerators"] = meta(
        channels=[ch(
            min_f=(I32_MIN + 1, U32_MAX),
            max_f=(I32_MAX, U32_MAX),
            gamma=(U32_MAX, U32_MAX),
            base_off=(I32_MIN + 1, U32_MAX),
            alt_off=(I32_MAX, U32_MAX),
        )],
    )

    # ── zero offsets (omitted default) ─────────────────────────────────────
    cases["20_zero_offsets"] = meta(
        channels=[ch(
            min_f=(0, 1), max_f=(13, 10),
            gamma=(1, 1),
            base_off=(0, 1), alt_off=(0, 1),
        )],
    )

    # ── writer version != 0, minimum_version still 0 (forward compat) ──────
    cases["21_writer_version_nonzero"] = meta(writer_version=1)

    # ── all flags combined ─────────────────────────────────────────────────
    cases["22_all_flags"] = meta(
        is_multichannel=True,
        use_base_colour_space=True,
        backward_direction=True,
        common_denominator=True,
        base_hdr_headroom_n=1300, base_hdr_headroom_d=1000,
        alt_hdr_headroom_n=0, alt_hdr_headroom_d=1000,
        channels=[
            ch(min_f=(-1000, 1000), max_f=(0, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
            ch(min_f=(-500, 1000), max_f=(0, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
            ch(min_f=(-1500, 1000), max_f=(0, 1000), gamma=(1000, 1000), base_off=(16, 1000), alt_off=(16, 1000)),
        ],
    )

    return cases


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gen-iso21496.py <output_dir>", file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = build_matrix()
    print(f"emitting {len(matrix) * 2} fixtures to {out_dir}")
    for name, m in matrix.items():
        jpeg_blob = serialize(m, with_version_byte=False)
        avif_blob = serialize(m, with_version_byte=True)
        (out_dir / f"{name}_jpeg.bin").write_bytes(jpeg_blob)
        (out_dir / f"{name}_avif.bin").write_bytes(avif_blob)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
