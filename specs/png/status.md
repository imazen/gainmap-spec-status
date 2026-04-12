# PNG — gain map proposal status

## Authority

- **W3C PNG Working Group** (drafts at https://w3c.github.io/PNG-spec/)
- Liaison with **ISO TC 42 / WG 23** (the group that authored ISO 21496-1)

## Summary

PNG has **no merged gain map support** as of the June 2025 3rd edition. The
feature is deferred to the 4th edition, tracked in issue #536 as **unchecked**
with the explicit reason:

> `ISO 21496-1` is not yet free. Liaison established (see #366).

## Key issues

| # | Title | State | Role |
|---|---|---|---|
| [#380](https://github.com/w3c/png/issues/380) | Proposal: gain maps for PNG | open | main design thread, 53 comments |
| [#366](https://github.com/w3c/png/issues/366) | Liaison letter from ISO TC 42/WG 23 on Gain Maps | open | inbound request from ISO |
| [#536](https://github.com/w3c/png/issues/536) | 4th edition meta-issue | open | blocks-list tracker |
| [#493](https://github.com/w3c/png/issues/493) | Adding generic image-type data chunk(s) | open | enables gain map as one of many auxiliary channels |
| [#494](https://github.com/w3c/png/issues/494) | Add `iEXt` chunk | open | related: extensible auxiliary |
| [#495](https://github.com/w3c/png/issues/495) | Add `iEId` chunk | open | related: image identifier |

## The proposal (as of #380)

Two new chunks:

- **`gMAP`** — per-image metadata, mirrors ISO 21496-1 §5 field-for-field,
  ordered **after** `IHDR` but **before** `IDAT`. Would be the first PNG chunk
  with a floating-point value. Marked ancillary, public, unsafe-to-copy.
- **`gDAT`** — per-pixel gain data. Goes **after** `IDAT` (like APNG's `fcTL`
  /`fdAT`) so legacy decoders can display the base image without parsing the
  gain map.

The original proposal body explicitly says it **relates to an earlier version
of the ISO gain map specification** and is outdated. The 2025 draft needs to
be rebased onto ISO 21496-1:2025 once the normative reference becomes
available.

## Open design questions

These are the debates that stall the proposal:

1. **Alternate-image metadata.** The HDR alternate image can carry its own
   `cICP`, `iCCP`, `mDCv`, `cLLI`. Where do they live? (Cameron, 2024-09-02.)
   - **Option A:** Nest sub-chunks inside `gMAP`.
   - **Option B:** Embed a PNG inside the PNG (Google's approach).
   - **Option C:** Introduce `alt-cICP`, `alt-iCCP`, etc. sibling chunks.
2. **Ordering relative to IDAT.** The PNG 1.2 rule *"IDATs must appear
   consecutively with no other intervening chunks"* rules out interleaving
   `gDAT` with `IDAT`. (fintelia, 2024-08-30.)
3. **PNG-in-PNG vs generic aux channels.** Generic aux channels (#493)
   subsume the use case but require larger architectural work.
4. **Why use PNG for lossy content at all.** `palemieux` (MPEG liaison) asks
   the question repeatedly. `svgeesus` (W3C PNG WG chair) argues portability
   and US Library of Congress archival preference trump lossy/lossless
   concerns (`ProgramMax`, 2024-08-29).

## What blocks progress

1. **ISO 21496-1 paywall.** W3C process prefers normative references that
   are freely available. A liaison request to ISO is pending.
2. **No consensus on sub-chunks vs PNG-in-PNG vs new color-type route.**
3. **Rebase to 21496-1:2025.** The field list in the current proposal lags
   the published spec.

## Reference chunk skeleton (from #380, pre-21496-1:2025)

```
gMAP chunk (proposed):
  Baseline HDR Headroom        (float16 or uint)
  Alternate HDR Headroom       (float16 or uint)
  Gain Map Min                 (per-channel, up to 3)
  Gain Map Max                 (per-channel, up to 3)
  Gain Map Gamma               (per-channel)
  Base Offset                  (per-channel)
  Alternate Offset             (per-channel)
  Alternate Colour Primaries   (cICP-like)
  Alternate Transfer Function
  Alternate Matrix Coefficients
  [sub-chunks TBD for mDCv/cLLi/iCCP of alternate]
```

```
gDAT chunk (proposed):
  same compression method as IHDR
  same filter method
  1 or 3 channels, 8 or 16 bpp (float16 disallowed)
  dimensions: subsample from IHDR
```

## When to revisit

Watch for:
- ISO 21496-1 becoming freely available (no current timeline)
- A merged PR to `w3c/png` with a `gMAP`/`gDAT` specification draft
- An update to the [4th edition meta-issue #536](https://github.com/w3c/png/issues/536)

## Implication for `zenpng`

`zenpng` currently does **not** expose any gain map API, correctly matching
the spec. When 4th edition lands we will add `gMAP` / `gDAT` chunk parsing
and expose a `GainMap` struct. See `audit/zenpng.md`.
