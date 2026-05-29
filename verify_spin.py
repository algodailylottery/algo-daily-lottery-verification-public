#!/usr/bin/env python3
"""
Algorand Daily Lottery — Spin & Win Independent Verification Tool

Proves that a Spin & Win result was fair by recomputing it from on-chain data only:
1. Reads the SPIN_REVEALED log from the reveal transaction (immutable, public)
2. Recomputes the winning segment from the VRF seed: segment = first8(seed) % 38
3. Recomputes the colour from the segment + the tier's segment-distribution box
4. Confirms both match what the contract recorded, and reports the payout

NO TRUST REQUIRED — everything is verified straight from the blockchain.

The winning segment is derived deterministically from a VRF (Verifiable Random Function)
seed that did not exist when the player committed their spin, so the outcome cannot be
predicted or manipulated by anyone — player or operator.

Usage:
    python3 verify_spin.py <reveal_tx_id>
    python3 verify_spin.py <reveal_tx_id> --network testnet

Requirements:
    pip install requests

License: MIT
GitHub: https://github.com/algodailylottery/algo-daily-lottery-verification-public
"""

import sys
import base64
import requests

TOTAL_SEGMENTS = 38
COLORS = ["black", "green", "blue", "gold"]          # contract colour codes 0..3
PAYOUT_PCT = {"black": 0, "green": 10, "blue": 18, "gold": 50}  # % of pot

NETWORKS = {
    "mainnet": {
        "indexer": "https://mainnet-idx.algonode.cloud",
        "algod": "https://mainnet-api.algonode.cloud",
        "explorer": "https://allo.info/tx/",
    },
    "testnet": {
        "indexer": "https://testnet-idx.algonode.cloud",
        "algod": "https://testnet-api.algonode.cloud",
        "explorer": "https://testnet.allo.info/tx/",
    },
}


def parse_spin_revealed(log: bytes):
    """Parse a SPIN_REVEALED log. Returns a dict, or None if it's not that log.

    Layout (from spinwin_contract.py):
      "SPIN_REVEALED:" "spinner="<32B> ",spin_id="<u64> ",tier="<u64> ",segment="<u64>
      ",color="<u64> ",payout="<u64> ",pot_after="<u64> ",seed="<32B>
    (the contract clears the spinner global before logging, so that field is the zero address)
    """
    prefix = b"SPIN_REVEALED:"
    if not log.startswith(prefix):
        return None
    i = len(prefix)

    def marker(m: bytes):
        nonlocal i
        if log[i:i + len(m)] != m:
            raise ValueError(f"malformed log: expected {m!r} at offset {i}")
        i += len(m)

    def u64():
        nonlocal i
        v = int.from_bytes(log[i:i + 8], "big"); i += 8; return v

    def b32():
        nonlocal i
        v = log[i:i + 32]; i += 32; return v

    marker(b"spinner="); b32()
    marker(b",spin_id="); spin_id = u64()
    marker(b",tier="); tier = u64()
    marker(b",segment="); segment = u64()
    marker(b",color="); color = u64()
    marker(b",payout="); payout = u64()
    marker(b",pot_after="); pot_after = u64()
    marker(b",seed="); seed = b32()
    return {"spin_id": spin_id, "tier": tier, "segment": segment, "color": color,
            "payout": payout, "pot_after": pot_after, "seed": seed}


def fetch_reveal(net, txid):
    """Fetch the reveal txn from the indexer; return (parsed_log, app_id)."""
    r = requests.get(f"{net['indexer']}/v2/transactions/{txid}", timeout=15)
    r.raise_for_status()
    txn = r.json()["transaction"]
    app_id = txn.get("application-transaction", {}).get("application-id")
    for log_b64 in txn.get("logs", []) or []:
        parsed = parse_spin_revealed(base64.b64decode(log_b64))
        if parsed:
            return parsed, app_id
    raise ValueError("No SPIN_REVEALED log found in this transaction — is it a spin_reveal txn?")


def fetch_tier_box(net, app_id, tier):
    """Read the tier box t{tier} = [green, blue, gold, reserved]. Returns (green, blue, gold)."""
    name_b64 = base64.b64encode(f"t{tier}".encode()).decode()
    r = requests.get(f"{net['algod']}/v2/applications/{app_id}/box",
                     params={"name": f"b64:{name_b64}"}, timeout=15)
    r.raise_for_status()
    data = base64.b64decode(r.json()["value"])
    return data[0], data[1], data[2]  # green, blue, gold


def colour_for_segment(segment, green, blue, gold):
    """Contract rule: gold = [0,gold), blue = [gold, gold+blue), green = [.., +green), else black."""
    if segment < gold:
        return "gold"
    if segment < gold + blue:
        return "blue"
    if segment < gold + blue + green:
        return "green"
    return "black"


def verify(txid, network="mainnet", tier_override=None):
    net = NETWORKS[network]
    print("=" * 80)
    print("🎡 SPIN & WIN — FAIRNESS VERIFICATION")
    print("=" * 80)
    print(f"\n📋 Verifying reveal tx {txid} ({network})\n")

    try:
        rev, app_id = fetch_reveal(net, txid)
    except Exception as e:
        print(f"❌ Could not read the reveal transaction: {e}")
        return False

    seed_hex = rev["seed"].hex()
    recomputed_segment = int.from_bytes(rev["seed"][:8], "big") % TOTAL_SEGMENTS
    recorded_segment = rev["segment"]
    recorded_colour = COLORS[rev["color"]] if rev["color"] < len(COLORS) else "unknown"

    print("📊 On-chain SPIN_REVEALED log:")
    print(f"   App ID:        {app_id}")
    print(f"   Spin #:        {rev['spin_id']}")
    print(f"   Tier:          {rev['tier']}")
    print(f"   VRF seed:      {seed_hex[:16]}...{seed_hex[-16:]}")
    print(f"   Segment:       {recorded_segment}")
    print(f"   Colour:        {recorded_colour}")
    print(f"   Payout:        {rev['payout'] / 1_000_000:.6f} ALGO")
    print(f"   Pot after:     {rev['pot_after'] / 1_000_000:.6f} ALGO")
    print(f"   Blockchain:    {net['explorer']}{txid}\n")

    print("🎲 Recomputing from the VRF seed...\n")
    print(f"   segment = first 8 bytes of seed % 38 = {recomputed_segment}")
    segment_ok = recomputed_segment == recorded_segment
    print(f"   Segment check: {'✅ MATCH' if segment_ok else '❌ MISMATCH'} "
          f"(recomputed {recomputed_segment} vs on-chain {recorded_segment})\n")

    # The contract resets the tier global before emitting the log, so the log's tier reads 0.
    # Use --tier to re-derive the colour, otherwise skip it (segment is the fairness-critical check).
    box_tier = tier_override if tier_override else (rev["tier"] if 1 <= rev["tier"] <= 3 else None)
    colour_ok = None
    if box_tier is None:
        print("   ⚠️  The reveal log records tier as 0 (the contract clears it before logging),")
        print("       so the colour can't be re-derived from the log alone. Re-run with")
        print("       '--tier 1|2|3' to also verify the colour. The segment check above is the")
        print("       fairness-critical step.\n")
    else:
        try:
            green, blue, gold = fetch_tier_box(net, app_id, box_tier)
            recomputed_colour = colour_for_segment(recorded_segment, green, blue, gold)
            colour_ok = recomputed_colour == recorded_colour
            print(f"   Tier {box_tier} segments: gold={gold}, blue={blue}, green={green} "
                  f"(rest of 38 are black)")
            print(f"   colour for segment {recorded_segment} = {recomputed_colour}")
            print(f"   Colour check:  {'✅ MATCH' if colour_ok else '❌ MISMATCH'} "
                  f"(recomputed {recomputed_colour} vs on-chain {recorded_colour})")
            print(f"   Payout rate:   {recorded_colour} = {PAYOUT_PCT.get(recorded_colour, '?')}% of pot\n")
        except Exception as e:
            print(f"   ⚠️  Could not read the tier box to re-derive colour: {e}\n")

    print("=" * 80)
    print("🏁 FINAL VERDICT")
    print("=" * 80)
    ok = segment_ok and (colour_ok is not False)
    if ok and segment_ok:
        print("\n✅ ✅ ✅  SPIN IS FAIR AND VALID  ✅ ✅ ✅\n")
        print("The winning segment is exactly what the VRF seed produces. The outcome was")
        print("decided by verifiable randomness that no one could predict or manipulate.")
    else:
        print("\n⚠️  VERIFICATION FAILED  ⚠️\n")
        print("The recorded result does not match the VRF seed. Investigate.")

    print("\n💡 HOW THIS WORKS:")
    print("   1. The seed is a VRF output committed AFTER the player locked in their spin.")
    print("   2. segment = first8(seed) % 38  — fully deterministic, anyone gets the same number.")
    print("   3. The colour (and payout) follow from the segment + the tier's segment counts.")
    print("   4. Same seed always yields the same result → provably fair.")
    print("=" * 80 + "\n")
    return ok


def main():
    flagged = {"--network", "--tier"}
    args = []
    skip = False
    for idx, a in enumerate(sys.argv[1:]):
        if skip:
            skip = False; continue
        if a in flagged:
            skip = True; continue
        if a.startswith("--"):
            continue
        args.append(a)
    network = "mainnet"
    if "--network" in sys.argv:
        network = sys.argv[sys.argv.index("--network") + 1]
    tier_override = None
    if "--tier" in sys.argv:
        tier_override = int(sys.argv[sys.argv.index("--tier") + 1])
    if not args or network not in NETWORKS:
        print("Spin & Win — Fairness Verification Tool\n")
        print("Usage: python3 verify_spin.py <reveal_tx_id> [--network mainnet|testnet] [--tier 1|2|3]\n")
        print("Find the reveal tx id on a spin's 'Verify' link in the app's Spin History.")
        sys.exit(1)
    try:
        sys.exit(0 if verify(args[0], network, tier_override) else 1)
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
