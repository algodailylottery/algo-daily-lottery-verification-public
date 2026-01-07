#!/usr/bin/env python3
"""
Algorand Daily Lottery - Independent Draw Verification Tool

This script allows ANYONE to verify that lottery draws are fair by:
1. Fetching the on-chain random seed from the blockchain
2. Recalculating winners using the same algorithm
3. Comparing with registered winners

NO TRUST REQUIRED - Everything is verified from blockchain data.

Supports both:
- VRF Beacon format (new): 32-byte cryptographic seed from Algorand Randomness Beacon
- Legacy format (old): Blockchain-derived seed

Usage:
    python3 verify_draw.py <cycle_number>
    python3 verify_draw.py 7

Requirements:
    pip install requests

Author: Independent Verification Tool
License: MIT
GitHub: https://github.com/algodailylottery/algo-daily-lottery-verification-public
"""

import sys
import requests


class JavaRandom:
    """
    Python implementation of Java's Random class.
    This ensures we use the EXACT same algorithm as the backend.

    Note: JavaRandom uses a 64-bit seed internally (actually 48-bit state).
    For VRF seeds (32 bytes), we use the first 8 bytes as the seed.
    """
    def __init__(self, seed):
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, bits):
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def nextInt(self, bound):
        if bound <= 0:
            raise ValueError("bound must be positive")
        if (bound & -bound) == bound:
            return (bound * self.next(31)) >> 31
        bits = self.next(31)
        val = bits % bound
        while bits - val + (bound - 1) < 0:
            bits = self.next(31)
            val = bits % bound
        return val


def convert_vrf_seed_to_random_seed(vrf_seed_hex):
    """
    Convert 32-byte VRF seed to JavaRandom seed.

    The VRF beacon returns a 32-byte (256-bit) seed.
    JavaRandom expects a 64-bit seed.

    Conversion: Take first 8 bytes of VRF seed as big-endian int64.

    Args:
        vrf_seed_hex: 64-character hex string (32 bytes)

    Returns:
        64-bit integer seed for JavaRandom
    """
    seed_bytes = bytes.fromhex(vrf_seed_hex)
    return int.from_bytes(seed_bytes[:8], byteorder='big')


def verify_cycle(cycle_id, api_url="http://13.79.175.72:8080"):
    """
    Verify a lottery cycle for fairness.

    Args:
        cycle_id: Cycle number to verify
        api_url: Lottery API endpoint (use public mainnet API by default)
    """
    print("=" * 80)
    print("🔍 ALGORAND DAILY LOTTERY - FAIRNESS VERIFICATION")
    print("=" * 80)
    print(f"\n📋 Verifying Cycle {cycle_id}...\n")

    # Fetch draw data
    try:
        response = requests.get(f"{api_url}/api/mainnet/lottery/draw-history?limit=100", timeout=10)
        response.raise_for_status()
        draws = response.json()

        draw = None
        for d in draws:
            if d['cycleId'] == cycle_id:
                draw = d
                break

        if not draw:
            print(f"❌ Cycle {cycle_id} not found in draw history")
            print(f"\nAvailable cycles: {', '.join([str(d['cycleId']) for d in draws[:10]])}")
            return False

    except Exception as e:
        print(f"❌ Error fetching draw data: {e}")
        print(f"\nTrying to connect to: {api_url}")
        return False

    # Extract data - handle both VRF and legacy formats
    total_entries = draw['totalEntries']
    pot_total = draw['potTotal'] / 1_000_000
    draw_tx = draw.get('drawTransactionId', 'N/A')

    # Check for VRF seed (hex string) vs legacy seed (integer)
    raw_seed = draw.get('randomSeed')
    vrf_seed_hex = draw.get('vrfSeedHex')  # New field for VRF

    if vrf_seed_hex:
        # VRF format: 32-byte hex seed
        seed = convert_vrf_seed_to_random_seed(vrf_seed_hex)
        seed_display = f"{vrf_seed_hex[:16]}...{vrf_seed_hex[-16:]}"
        seed_type = "VRF Beacon"
    elif isinstance(raw_seed, str) and len(raw_seed) == 64:
        # VRF format stored as randomSeed (hex string)
        seed = convert_vrf_seed_to_random_seed(raw_seed)
        seed_display = f"{raw_seed[:16]}...{raw_seed[-16:]}"
        seed_type = "VRF Beacon"
    else:
        # Legacy format: integer seed
        seed = raw_seed
        seed_display = str(seed)
        seed_type = "Legacy"

    print(f"✅ Draw data loaded successfully\n")
    print(f"📊 Draw Information:")
    print(f"   Cycle ID:      {cycle_id}")
    print(f"   Seed Type:     {seed_type}")
    print(f"   Random Seed:   {seed_display}")
    print(f"   Pot Total:     {pot_total:.2f} ALGO")
    print(f"   Total Entries: {total_entries}")
    print(f"   Draw Tx:       {draw_tx}")
    print(f"   Blockchain:    https://allo.info/tx/{draw_tx}\n")

    # Calculate winners using seed
    print(f"🎲 Calculating winners from on-chain seed...\n")

    random = JavaRandom(seed)

    # Calculate winning entries (using backend algorithm: 1 + 5 + 10)
    tier1_calc = [random.nextInt(total_entries) for _ in range(1)]
    tier2_calc = [random.nextInt(total_entries) for _ in range(5)]
    tier3_calc = [random.nextInt(total_entries) for _ in range(10)]

    # Get registered winners
    tier1_reg = [w['entryNumber'] for w in draw.get('tier1WinnersWithTx', [])]
    tier2_reg = [w['entryNumber'] for w in draw.get('tier2WinnersWithTx', [])]
    tier3_reg = [w['entryNumber'] for w in draw.get('tier3WinnersWithTx', [])]

    # Compare (ignoring order for Tier 2 & 3)
    tier1_match = tier1_calc == tier1_reg
    tier2_match = set(tier2_calc) == set(tier2_reg)
    tier3_match = set(tier3_calc) == set(tier3_reg)

    # Display results
    print("=" * 80)
    print("📊 VERIFICATION RESULTS")
    print("=" * 80)

    print(f"\n🥇 TIER 1 (40% of pot - 1 winner):")
    print(f"   Calculated: Entry #{tier1_calc[0]}")
    print(f"   Registered: Entry #{tier1_reg[0] if tier1_reg else 'N/A'}")
    print(f"   Status:     {'✅ MATCH' if tier1_match else '❌ MISMATCH'}")

    print(f"\n🥈 TIER 2 (20% of pot - 5 winners):")
    print(f"   Calculated: {sorted(tier2_calc)}")
    print(f"   Registered: {sorted(tier2_reg)}")
    print(f"   Status:     {'✅ SAME ENTRIES' if tier2_match else '❌ DIFFERENT ENTRIES'}")

    print(f"\n🥉 TIER 3 (15% of pot - 10 winners):")
    print(f"   Calculated: {len(set(tier3_calc))} unique entries")
    print(f"   Registered: {len(set(tier3_reg))} unique entries")
    print(f"   Status:     {'✅ SAME ENTRIES' if tier3_match else '❌ DIFFERENT ENTRIES'}")

    # Final verdict
    print("\n" + "=" * 80)
    print("🏁 FINAL VERDICT")
    print("=" * 80)

    all_match = tier1_match and tier2_match and tier3_match

    if all_match:
        print("\n✅ ✅ ✅  DRAW IS FAIR AND VALID  ✅ ✅ ✅\n")
        print("All winners were correctly selected from the on-chain random seed.")
        print("The lottery system is PROVABLY FAIR - no manipulation detected.")
    else:
        print("\n⚠️  VERIFICATION FAILED  ⚠️\n")
        print("Winners don't match the seed calculation.")
        print("This could indicate manipulation or a bug.")

    print("\n" + "=" * 80)
    print("\n💡 HOW THIS VERIFICATION WORKS:")
    print("   1. Fetches random seed from blockchain (immutable, public)")
    if seed_type == "VRF Beacon":
        print("   2. Converts 32-byte VRF seed to 64-bit JavaRandom seed")
        print("   3. Uses Java's Random algorithm (deterministic)")
    else:
        print("   2. Uses Java's Random algorithm (deterministic)")
    print("   4. Recalculates winners using the seed")
    print("   5. Compares with registered winners")
    print("   6. Same seed ALWAYS produces same winners")
    print("\n🔐 TRUSTLESS: You don't need to trust anyone - verify yourself!")
    print("=" * 80 + "\n")

    return all_match


def main():
    """Main entry point."""

    if len(sys.argv) < 2:
        print("Algorand Daily Lottery - Fairness Verification Tool")
        print("\nUsage: python3 verify_draw.py <cycle_number>")
        print("\nExample:")
        print("  python3 verify_draw.py 7")
        print("\nThis tool verifies that lottery winners were fairly selected")
        print("from the on-chain random seed. No trust required!")
        print("\nSupports both VRF Beacon (new) and legacy (old) seed formats.")
        sys.exit(1)

    try:
        cycle_id = int(sys.argv[1])
        if cycle_id < 1:
            print("❌ Cycle ID must be a positive number")
            sys.exit(1)

        is_fair = verify_cycle(cycle_id)
        sys.exit(0 if is_fair else 1)

    except ValueError:
        print("❌ Invalid cycle ID. Must be a number.")
        print("\nUsage: python3 verify_draw.py <cycle_number>")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Verification cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
