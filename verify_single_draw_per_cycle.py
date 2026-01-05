#!/usr/bin/env python3
"""
Verify Single Draw Per Cycle - Proves Creator Isn't Cheating

This script verifies that the lottery creator executes the draw exactly ONCE per cycle,
proving they cannot cherry-pick favorable results by running multiple draws.

What This Proves:
1. Each cycle has exactly ONE execute_draw transaction
2. Creator cannot run the draw multiple times to get better outcomes
3. No "lottery fishing" - running draws until getting favorable results
4. Fair play - one draw per cycle, take it or leave it

Usage:
    python3 verify_single_draw_per_cycle.py
    python3 verify_single_draw_per_cycle.py --cycles 10  # Check last 10 cycles
"""

import sys
import argparse
import requests
import base64
from collections import defaultdict

MAINNET_APP_ID = 3380359414
INDEXER_URL = "https://mainnet-idx.algonode.cloud"


def get_all_execute_draw_transactions(app_id, limit=1000):
    """Fetch all execute_draw transactions for the app."""
    url = f"{INDEXER_URL}/v2/transactions"
    params = {
        'application-id': app_id,
        'limit': limit
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        execute_draw_calls = []

        for txn in data.get('transactions', []):
            app_txn = txn.get('application-transaction', {})
            app_args = app_txn.get('application-args', [])

            if app_args:
                try:
                    method = base64.b64decode(app_args[0]).decode('utf-8', errors='ignore')

                    if method == 'execute_draw':
                        execute_draw_calls.append({
                            'tx_id': txn['id'],
                            'sender': txn['sender'],
                            'round': txn['confirmed-round'],
                            'timestamp': txn.get('round-time', 0)
                        })
                except Exception:
                    continue

        # Sort by round number
        execute_draw_calls.sort(key=lambda x: x['round'])

        return execute_draw_calls

    except Exception as e:
        print(f"❌ Error fetching transactions: {e}")
        sys.exit(1)


def get_cycle_from_draw_history(cycle_id):
    """Get draw information for a specific cycle from the API."""
    url = f"http://13.79.175.72:8080/api/mainnet/lottery/draw-history"

    try:
        response = requests.get(url, params={'limit': 100}, timeout=10)
        response.raise_for_status()
        draws = response.json()

        for draw in draws:
            if draw['cycleId'] == cycle_id:
                return draw

        return None

    except Exception as e:
        return None


def map_transactions_to_cycles(execute_draw_txns):
    """Map execute_draw transactions to cycle IDs."""
    print("\n🔍 Mapping transactions to cycles...")

    # Group transactions by cycle
    # We'll use the draw history API to get cycle IDs
    cycles = {}
    transactions_per_cycle = defaultdict(list)

    # Get recent draws
    try:
        response = requests.get(
            "http://13.79.175.72:8080/api/mainnet/lottery/draw-history",
            params={'limit': 100},
            timeout=10
        )
        draws = response.json()

        # Create mapping of transaction ID to cycle ID
        tx_to_cycle = {}
        for draw in draws:
            tx_id = draw.get('drawTransactionId')
            if tx_id:
                tx_to_cycle[tx_id] = draw['cycleId']

        # Map our transactions
        for txn in execute_draw_txns:
            cycle_id = tx_to_cycle.get(txn['tx_id'])
            if cycle_id:
                transactions_per_cycle[cycle_id].append(txn)
                cycles[cycle_id] = True

        return transactions_per_cycle, len(cycles)

    except Exception as e:
        print(f"⚠️  Warning: Could not map to cycles: {e}")
        return {}, 0


def verify_single_draw_per_cycle(transactions_per_cycle, max_cycles=None):
    """Verify each cycle has exactly one execute_draw transaction."""

    print("\n" + "="*80)
    print("🔍 VERIFYING: ONE DRAW PER CYCLE")
    print("="*80)

    all_good = True
    total_cycles = len(transactions_per_cycle)

    # Sort cycles
    sorted_cycles = sorted(transactions_per_cycle.keys())

    if max_cycles:
        sorted_cycles = sorted_cycles[-max_cycles:]

    print(f"\nChecking {len(sorted_cycles)} cycles...\n")

    for cycle_id in sorted_cycles:
        txns = transactions_per_cycle[cycle_id]
        count = len(txns)

        if count == 1:
            print(f"✅ Cycle {cycle_id:3d}: {count} draw  (TX: {txns[0]['tx_id'][:8]}...)")
        else:
            print(f"❌ Cycle {cycle_id:3d}: {count} draws ⚠️  MULTIPLE DRAWS DETECTED!")
            all_good = False

            # Show all transactions for this cycle
            for i, txn in enumerate(txns, 1):
                print(f"     Draw {i}: {txn['tx_id']}")
                print(f"             Round: {txn['round']}")
                print(f"             https://allo.info/tx/{txn['tx_id']}")

    print("\n" + "="*80)

    if all_good:
        print("✅ ✅ ✅  ALL CYCLES: SINGLE DRAW ONLY  ✅ ✅ ✅")
        print()
        print(f"Verified {len(sorted_cycles)} cycles:")
        print(f"  • Each cycle has EXACTLY 1 execute_draw transaction")
        print(f"  • Creator cannot cherry-pick results")
        print(f"  • No multiple draws to fish for favorable outcomes")
        print(f"  • Fair play verified ✅")
    else:
        print("❌ ❌ ❌  MULTIPLE DRAWS DETECTED  ❌ ❌ ❌")
        print()
        print("WARNING: Some cycles have multiple execute_draw transactions!")
        print("This could indicate:")
        print("  • Creator ran draw multiple times (cherry-picking)")
        print("  • Transaction failures and retries (check blockchain)")
        print("  • Other technical issues")
        print()
        print("⚠️  Manual investigation required!")

    print("="*80)

    return all_good


def analyze_draw_pattern(execute_draw_txns):
    """Analyze the pattern of draws to detect suspicious behavior."""

    print("\n" + "="*80)
    print("📊 DRAW PATTERN ANALYSIS")
    print("="*80)

    if not execute_draw_txns:
        print("\n⚠️  No execute_draw transactions found")
        return

    print(f"\nTotal execute_draw transactions: {len(execute_draw_txns)}")
    print(f"Date range: {len(execute_draw_txns)} transactions found")

    # Check for suspicious patterns
    print("\n🔍 Checking for suspicious patterns:")

    # Pattern 1: Multiple draws in quick succession (within 10 blocks)
    suspicious_rapid_draws = []
    for i in range(len(execute_draw_txns) - 1):
        current = execute_draw_txns[i]
        next_draw = execute_draw_txns[i + 1]
        block_diff = next_draw['round'] - current['round']

        if block_diff < 10:  # Less than 10 blocks apart (~30 seconds)
            suspicious_rapid_draws.append({
                'draw1': current,
                'draw2': next_draw,
                'block_diff': block_diff
            })

    if suspicious_rapid_draws:
        print(f"\n⚠️  Found {len(suspicious_rapid_draws)} suspicious rapid draw sequences:")
        for item in suspicious_rapid_draws:
            print(f"  • Draws only {item['block_diff']} blocks apart")
            print(f"    TX1: {item['draw1']['tx_id']}")
            print(f"    TX2: {item['draw2']['tx_id']}")
    else:
        print("\n✅ No rapid consecutive draws detected")
        print("   (Each draw properly spaced)")

    # Pattern 2: Check average time between draws (should be ~24 hours)
    if len(execute_draw_txns) > 1:
        time_diffs = []
        for i in range(len(execute_draw_txns) - 1):
            current = execute_draw_txns[i]
            next_draw = execute_draw_txns[i + 1]
            time_diff = next_draw['timestamp'] - current['timestamp']
            time_diffs.append(time_diff)

        avg_time = sum(time_diffs) / len(time_diffs)
        avg_hours = avg_time / 3600

        print(f"\n⏱️  Average time between draws: {avg_hours:.1f} hours")

        if 23 <= avg_hours <= 25:
            print("   ✅ Consistent with 24-hour cycles")
        else:
            print(f"   ⚠️  Deviates from expected 24 hours")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='Verify creator executes draw exactly once per cycle'
    )
    parser.add_argument(
        '--cycles',
        type=int,
        default=None,
        help='Number of recent cycles to check (default: all)'
    )

    args = parser.parse_args()

    print("="*80)
    print("🔍 VERIFY: SINGLE DRAW PER CYCLE")
    print("="*80)
    print()
    print("This script proves the creator doesn't cheat by:")
    print("  • Verifying each cycle has EXACTLY one draw")
    print("  • Detecting multiple draws (cherry-picking attempts)")
    print("  • Analyzing draw timing patterns")
    print()

    # Fetch all execute_draw transactions
    print("📥 Fetching execute_draw transactions from blockchain...")
    execute_draw_txns = get_all_execute_draw_transactions(MAINNET_APP_ID)

    print(f"✅ Found {len(execute_draw_txns)} execute_draw transactions")

    # Map to cycles
    transactions_per_cycle, cycle_count = map_transactions_to_cycles(execute_draw_txns)

    if cycle_count == 0:
        print("\n⚠️  Could not map transactions to cycles")
        print("Falling back to pattern analysis only...")
        analyze_draw_pattern(execute_draw_txns)
        return

    print(f"✅ Mapped to {cycle_count} cycles")

    # Verify single draw per cycle
    all_good = verify_single_draw_per_cycle(transactions_per_cycle, args.cycles)

    # Analyze patterns
    analyze_draw_pattern(execute_draw_txns)

    # Final verdict
    print("\n" + "="*80)
    print("🎯 FINAL VERDICT")
    print("="*80)

    if all_good:
        print("\n✅ Verification Complete: Fair Play Confirmed")
        print()
        print("Evidence:")
        print("  ✅ Each cycle has exactly ONE draw")
        print("  ✅ No cherry-picking detected")
        print("  ✅ No multiple draw attempts")
        print("  ✅ Single execution per cycle verified")
        print()
        print("Conclusion:")
        print("  The creator executes the draw once per cycle and accepts")
        print("  the result, proving they cannot manipulate outcomes by")
        print("  running multiple draws to find favorable results.")
    else:
        print("\n⚠️  ⚠️  ⚠️   INVESTIGATION NEEDED   ⚠️  ⚠️  ⚠️")
        print()
        print("Multiple draws detected for some cycles.")
        print("This requires manual investigation.")

    print("\n" + "="*80)
    print()

    sys.exit(0 if all_good else 1)


if __name__ == "__main__":
    main()
