#!/usr/bin/env python3
"""
Retrieve lottery draw seed directly from Algorand blockchain.
No API needed - goes straight to blockchain data!

Updated for VRF Beacon - supports both old (DRAW_EXECUTED) and new (DRAW_REVEALED) formats.
"""

import requests
import base64
import sys


def get_seed_from_blockchain(cycle_id, app_id=3380359414):
    """
    Fetch the random seed for a cycle directly from Algorand blockchain.

    Args:
        cycle_id: Cycle number to query
        app_id: Lottery application ID

    Returns:
        Tuple of (seed_int, seed_hex, txn_id) or (None, None, None) if not found
    """
    print(f"🔍 Fetching seed for Cycle {cycle_id} from Algorand blockchain...")
    print(f"   App ID: {app_id}")
    print(f"   Querying Algorand Indexer...\n")

    indexer_url = "https://mainnet-idx.algonode.cloud"

    url = f"{indexer_url}/v2/transactions"
    params = {
        "application-id": app_id,
        "tx-type": "appl",
        "limit": 200
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        transactions = data.get("transactions", [])
        print(f"✅ Found {len(transactions)} application transactions")

        for txn in transactions:
            app_args = txn.get("application-transaction", {}).get("application-args", [])
            if not app_args:
                continue

            try:
                method = base64.b64decode(app_args[0]).decode('utf-8')
            except:
                continue

            # Check for new VRF format (execute_draw_reveal)
            if method == "execute_draw_reveal":
                seed_result = parse_draw_revealed_log(txn, cycle_id)
                if seed_result:
                    return seed_result

            # Check for old format (execute_draw) - backwards compatibility
            if method == "execute_draw":
                seed_result = parse_draw_executed_log(txn, cycle_id)
                if seed_result:
                    return seed_result

        print(f"\n❌ No draw found for Cycle {cycle_id}")
        print(f"   This cycle may not have been drawn yet.")
        return None, None, None

    except Exception as e:
        print(f"❌ Error querying blockchain: {e}")
        return None, None, None


def parse_draw_revealed_log(txn, cycle_id):
    """
    Parse DRAW_REVEALED log format (VRF Beacon).

    Log format:
    DRAW_REVEALED:cycle=<8B>,pot=<8B>,entries=<8B>,commitment_round=<8B>,t1=<8B>,t2=<8B>,t3=<8B>,seed=<32B>
    """
    logs = txn.get("logs", [])

    for log_b64 in logs:
        try:
            log_bytes = base64.b64decode(log_b64)

            # Check if this is a DRAW_REVEALED log
            if not log_bytes.startswith(b"DRAW_REVEALED:"):
                continue

            # Parse cycle ID (after "DRAW_REVEALED:cycle=")
            prefix = b"DRAW_REVEALED:cycle="
            if not log_bytes.startswith(prefix):
                continue

            offset = len(prefix)
            log_cycle_id = int.from_bytes(log_bytes[offset:offset+8], byteorder='big')

            if log_cycle_id != cycle_id:
                continue

            # Found matching cycle - extract seed
            # Seed is last 32 bytes after ",seed="
            seed_marker = b",seed="
            seed_idx = log_bytes.rfind(seed_marker)

            if seed_idx == -1:
                continue

            seed_start = seed_idx + len(seed_marker)
            seed_bytes = log_bytes[seed_start:seed_start + 32]

            if len(seed_bytes) != 32:
                continue

            # Convert to integer (first 8 bytes for JavaRandom compatibility)
            seed_for_random = int.from_bytes(seed_bytes[:8], byteorder='big')
            seed_hex = seed_bytes.hex()

            print(f"\n🎯 Found VRF draw transaction!")
            print(f"   Transaction ID: {txn['id']}")
            print(f"   Block: {txn.get('confirmed-round', 'N/A')}")
            print(f"   Format: VRF Beacon (DRAW_REVEALED)")
            print(f"\n✅ SEED RETRIEVED FROM BLOCKCHAIN:")
            print(f"   VRF Seed (hex):     {seed_hex}")
            print(f"   VRF Seed (first 8B): {seed_for_random}")
            print(f"\n🔗 View on blockchain:")
            print(f"   https://allo.info/tx/{txn['id']}")

            return seed_for_random, seed_hex, txn['id']

        except Exception as e:
            continue

    return None


def parse_draw_executed_log(txn, cycle_id):
    """
    Parse old DRAW_EXECUTED log format (pre-VRF).
    Kept for backwards compatibility with historical draws.
    """
    logs = txn.get("logs", [])

    for log_b64 in logs:
        try:
            log_bytes = base64.b64decode(log_b64)
            log_text = log_bytes.decode('utf-8', errors='ignore')

            if "DRAW_EXECUTED:" not in log_text:
                continue

            if f"cycle={cycle_id}" not in log_text:
                continue

            # Find seed in old format
            seed_marker = b"seed="
            seed_idx = log_bytes.find(seed_marker)

            if seed_idx == -1:
                continue

            seed_start = seed_idx + len(seed_marker)
            seed_bytes = log_bytes[seed_start:seed_start + 32]

            seed_int = int.from_bytes(seed_bytes, byteorder='big')
            seed_hex = seed_bytes.hex()

            print(f"\n🎯 Found legacy draw transaction!")
            print(f"   Transaction ID: {txn['id']}")
            print(f"   Block: {txn.get('confirmed-round', 'N/A')}")
            print(f"   Format: Legacy (DRAW_EXECUTED)")
            print(f"\n✅ SEED RETRIEVED FROM BLOCKCHAIN:")
            print(f"   Seed (integer): {seed_int}")
            print(f"   Seed (hex): {seed_hex}")
            print(f"\n🔗 View on blockchain:")
            print(f"   https://allo.info/tx/{txn['id']}")

            return seed_int, seed_hex, txn['id']

        except Exception as e:
            continue

    return None


if __name__ == "__main__":
    print("=" * 80)
    print("🔗 RETRIEVE LOTTERY SEED FROM ALGORAND BLOCKCHAIN")
    print("=" * 80)
    print("\nThis tool fetches the random seed directly from blockchain data.")
    print("Supports both VRF Beacon (new) and legacy (old) formats.\n")

    if len(sys.argv) < 2:
        print("Usage: python3 get_seed_from_blockchain.py <cycle_id>")
        print("Example: python3 get_seed_from_blockchain.py 7")
        sys.exit(1)

    try:
        cycle_id = int(sys.argv[1])
        seed_int, seed_hex, txn_id = get_seed_from_blockchain(cycle_id)

        if seed_int is not None:
            print("\n" + "=" * 80)
            print("✅ SUCCESS - SEED RETRIEVED FROM BLOCKCHAIN")
            print("=" * 80)
            print(f"\nYou can now use this seed to verify the draw:")
            print(f"python3 verify_draw.py {cycle_id}")
        else:
            print("\n" + "=" * 80)
            print("❌ SEED NOT FOUND")
            print("=" * 80)

    except ValueError:
        print("❌ Invalid cycle ID. Must be a number.")
        sys.exit(1)
