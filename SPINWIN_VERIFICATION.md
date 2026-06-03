# Spin & Win — Verification Guide

**Spin & Win** is the instant-play wheel game that runs alongside the daily lottery. Like the
lottery, every result is decided by **Algorand VRF randomness** and is fully verifiable from the
blockchain — don't trust, verify.

## What makes a spin fair?

1. **Commit** — when you spin, the contract locks in a *future* Algorand round. The VRF beacon
   output for that round does not exist yet, so neither the player nor the operator can know or
   choose the outcome in advance.
2. **Reveal** — once that round passes, the contract reads the beacon's 32-byte VRF seed and
   derives the winning segment:

   ```
   winning_segment = first_8_bytes_of_seed (big-endian) % 38
   ```
3. The segment maps to a **colour** (and payout) using the chosen tier's segment counts.
4. The seed, segment, colour, payout and resulting pot are written to the blockchain in an
   immutable, public **`SPIN_REVEALED`** log.

Same seed → same segment, always. Any manipulation is immediately detectable.

## Verify a spin

```bash
pip install requests
python3 verify_spin.py <reveal_tx_id>
```

Find the reveal transaction id via the **"Verify"** link next to any spin in the app's
**Spin History** (or on the block explorer). On testnet, add `--network testnet`.

The tool, using only on-chain data:
1. Reads the `SPIN_REVEALED` log from the reveal transaction.
2. Recomputes `segment = first8(seed) % 38` and checks it matches the recorded segment.
3. Recomputes the colour from the segment + the tier's segment counts and checks it matches.

If both match, the spin is **provably fair**.

### Verifying the colour (`--tier`)

The reveal log records the **tier**, so the tool re-derives the **colour** automatically from the
chain — no extra input needed. (Some early spins predate the tier being logged and read `0`; for
those, pass the tier explicitly:)

```bash
python3 verify_spin.py <reveal_tx_id> --tier 1     # 1, 2 or 3 — only needed for legacy spins
```

The **segment** check is the fairness-critical step and never needs the tier — the colour is just
a deterministic label on top of the segment.

## Payouts (% of the pot)

| Colour | Payout |
|---|---|
| ⚫ Black | none — your stake grows the pot |
| 🟢 Green | 10% |
| 🔵 Blue | 18% |
| 🟡 Gold (JACKPOT) | 45% |

A **gold** jackpot is split **45% to the winner / 45% rolled into the next pot / 5% to LOTT
holders / 5% to the platform**. There is **no fee on your stake** — 100% of every stake feeds the
pot, and the platform's 5% is charged only when a jackpot is won. Higher tiers stake more
(3% / 6% / 12% of the pot) and have more winning segments.

## Example output

```
🎡 SPIN & WIN — FAIRNESS VERIFICATION

📊 On-chain SPIN_REVEALED log:
   App ID:        <spinwin app id>
   Spin #:        15
   VRF seed:      fa8870b8c78fbaae...99ca52451a0995d2
   Segment:       0
   Colour:        gold
   Payout:        0.872495 ALGO

🎲 Recomputing from the VRF seed...
   segment = first 8 bytes of seed % 38 = 0
   Segment check: ✅ MATCH (recomputed 0 vs on-chain 0)
   Tier 1 segments: gold=1, blue=1, green=1 (rest of 38 are black)
   colour for segment 0 = gold
   Colour check:  ✅ MATCH (recomputed gold vs on-chain gold)
   Payout rate:   gold = 45% of pot

✅ ✅ ✅  SPIN IS FAIR AND VALID  ✅ ✅ ✅
```

## Smart contract

The Spin & Win contract source is included as **[`spinwin_contract.py`](spinwin_contract.py)**
(PyTeal). The winning-segment derivation and colour mapping are in `spin_reveal()`; the VRF
commit logic is in `spin_commit()`.

---

**Remember: a fair game is a verifiable game. Don't trust, verify!** 🔐
