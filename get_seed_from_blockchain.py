#!/usr/bin/env python3
"""
Retrieve lottery draw seed directly from Algorand blockchain.
No API needed - goes straight to blockchain data!
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
        Seed value (integer) or None if not found
    """
    print(f"🔍 Fetching seed for Cycle {cycle_id} from Algorand blockchain...")
    print(f"   App ID: {app_id}")
    print(f"   Querying Algorand Indexer...\n")

    # Use Algorand's public indexer
    indexer_url = "https://mainnet-idx.algonode.cloud"

    # Query for application transactions
    url = f"{indexer_url}/v2/transactions"
    params = {
        "application-id": app_id,
        "tx-type": "appl",  # Application call
        "limit": 100
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        transactions = data.get("transactions", [])
        print(f"✅ Found {len(transactions)} application transactions")

        # Look for execute_draw transaction with matching cycle
        for txn in transactions:
            # Check if this is an execute_draw call
            app_args = txn.get("application-transaction", {}).get("application-args", [])
            if not app_args:
                continue

            # First arg should be "execute_draw"
            try:
                method = base64.b64decode(app_args[0]).decode('utf-8')
                if method != "execute_draw":
                    continue
            except:
                continue

            # Check logs for this cycle
            logs = txn.get("logs", [])
            for log_b64 in logs:
                try:
                    log = base64.b64decode(log_b64).decode('utf-8', errors='ignore')

                    if "DRAW_EXECUTED:" in log and f"cycle={cycle_id}" in log:
                        print(f"\n🎯 Found draw transaction!")
                        print(f"   Transaction ID: {txn['id']}")
                        print(f"   Block: {txn.get('confirmed-round', 'N/A')}")
                        print(f"   Time: {txn.get('round-time', 'N/A')}")

                        # Extract seed from logs
                        # Log format: DRAW_EXECUTED:cycle=X,pot=Y,entries=Z,seed=<32 bytes>,t1=...

                        # The seed is embedded in the log as raw bytes
                        # We need to parse the binary log data
                        log_bytes = base64.b64decode(log_b64)

                        # Find "seed=" marker
                        seed_marker = b"seed="
                        seed_idx = log_bytes.find(seed_marker)

                        if seed_idx != -1:
                            # Seed starts after "seed=" and is 32 bytes
                            seed_start = seed_idx + len(seed_marker)
                            seed_bytes = log_bytes[seed_start:seed_start + 32]

                            # Convert to integer (big-endian)
                            seed = int.from_bytes(seed_bytes, byteorder='big')

                            print(f"\n✅ SEED RETRIEVED FROM BLOCKCHAIN:")
                            print(f"   Seed (integer): {seed}")
                            print(f"   Seed (hex): {seed_bytes.hex()}")
                            print(f"\n🔗 View on blockchain:")
                            print(f"   https://allo.info/tx/{txn['id']}")

                            return seed, txn['id']

                except Exception as e:
                    continue

        print(f"\n❌ No draw found for Cycle {cycle_id}")
        print(f"   This cycle may not have been drawn yet.")
        return None, None

    except Exception as e:
        print(f"❌ Error querying blockchain: {e}")
        return None, None


def get_seed_simple(cycle_id):
    """
    Simpler method: Query the app's global state for recent draws.
    Note: This only works if the app stores recent seeds.
    """
    print(f"🔍 Alternative method: Checking app global state...")

    indexer_url = "https://mainnet-idx.algonode.cloud"
    app_id = 3380359414

    url = f"{indexer_url}/v2/applications/{app_id}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check global state
        global_state = data.get("application", {}).get("params", {}).get("global-state", [])

        print(f"✅ Retrieved app global state ({len(global_state)} keys)")

        # Note: The app doesn't store historical seeds in global state
        # Only current cycle info
        print("ℹ️  Note: Seeds are not stored in global state")
        print("   Use transaction logs method instead (see above)")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("🔗 RETRIEVE LOTTERY SEED FROM ALGORAND BLOCKCHAIN")
    print("=" * 80)
    print("\nThis tool fetches the random seed directly from blockchain data.")
    print("No API needed - pure blockchain verification!\n")

    if len(sys.argv) < 2:
        print("Usage: python3 get_seed_from_blockchain.py <cycle_id>")
        print("Example: python3 get_seed_from_blockchain.py 7")
        sys.exit(1)

    try:
        cycle_id = int(sys.argv[1])
        seed, txn_id = get_seed_from_blockchain(cycle_id)

        if seed:
            print("\n" + "=" * 80)
            print("✅ SUCCESS - SEED RETRIEVED FROM BLOCKCHAIN")
            print("=" * 80)
            print(f"\nYou can now use this seed to verify the draw:")
            print(f"python3 verify_with_seed.py {cycle_id} {seed}")
        else:
            print("\n" + "=" * 80)
            print("❌ SEED NOT FOUND")
            print("=" * 80)

    except ValueError:
        print("❌ Invalid cycle ID. Must be a number.")
        sys.exit(1)
