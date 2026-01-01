# How to Retrieve Lottery Seed from Blockchain

## 🎯 Why Retrieve from Blockchain?

**True Trustlessness:** Don't rely on any API - go straight to the source!

The random seed is logged in the smart contract transaction logs and is:
- ✅ Public (anyone can read)
- ✅ Immutable (cannot be changed)
- ✅ Verifiable (on Algorand blockchain forever)

---

## 📋 **Method 1: Using Blockchain Explorer (Easiest)**

### Step 1: Find the Draw Transaction

**Option A - Via App Page:**
1. Go to https://allo.info/app/3380359414
2. Click "Transactions" tab
3. Look for transaction with note "execute_draw"
4. Find the one matching your cycle

**Option B - Direct Transaction (if you know the TX ID):**
1. Get the draw transaction ID from your backend or frontend
2. Go to: `https://allo.info/tx/<TRANSACTION_ID>`

**Example for Cycle 7:**
https://allo.info/tx/L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q

### Step 2: Find the Logs

On the transaction page:
1. Scroll to "Logs" section
2. Look for log entry containing "DRAW_EXECUTED"
3. The log format is:
   ```
   DRAW_EXECUTED:cycle=7,pot=3515962890,entries=3411,seed=<32 bytes>,t1=...,t2=...,t3=...
   ```

### Step 3: Extract the Seed

The seed is embedded in the log as 32 bytes. You'll see it in hex format.

**Example from Cycle 7:**
- The logs show the seed as raw bytes
- Convert to integer for use in verification

---

## 📋 **Method 2: Using Algorand Indexer API**

Query the indexer for the application's transactions:

```bash
# Get recent transactions for the lottery app
curl "https://mainnet-idx.algonode.cloud/v2/transactions?application-id=3380359414&tx-type=appl&limit=100"
```

Then parse the response to find:
1. Transactions with "execute_draw" in application-args
2. Check the logs for "DRAW_EXECUTED"
3. Extract the seed from the logs

---

## 📋 **Method 3: Using AlgoSDK (Python)**

```python
from algosdk.v2client import indexer
import base64

# Connect to public indexer
indexer_client = indexer.IndexerClient(
    "",
    "https://mainnet-idx.algonode.cloud"
)

# Query transactions
app_id = 3380359414
response = indexer_client.search_transactions(
    application_id=app_id,
    txn_type="appl",
    limit=100
)

# Find execute_draw transactions
for txn in response['transactions']:
    # Check logs for DRAW_EXECUTED
    if 'logs' in txn:
        for log_b64 in txn['logs']:
            log = base64.b64decode(log_b64)
            if b'DRAW_EXECUTED:' in log:
                # Parse log to extract seed
                # Seed is after "seed=" marker, 32 bytes
                print(f"Found draw: {txn['id']}")
                print(f"Logs: {log}")
```

---

## 📋 **Method 4: Manual Inspection (Most Trustless)**

### Using algod or goal CLI:

```bash
# Get transaction details
goal clerk inspect <TX_ID> -d <data_directory>
```

### The seed is in transaction logs:

```
Logs:
  [0]: "DRAW_EXECUTED:cycle=..."
```

Parse the log bytes to extract the seed.

---

## 🔍 **Understanding the Log Format**

The smart contract logs this data when executing a draw:

```python
Log(Concat(
    Bytes("DRAW_EXECUTED:"),
    Bytes("cycle="), Itob(current_cycle_id),      # 8 bytes
    Bytes(",pot="), Itob(current_pot),            # 8 bytes
    Bytes(",entries="), Itob(total_entries),      # 8 bytes
    Bytes(",seed="), random_seed,                  # 32 bytes ← HERE!
    Bytes(",t1="), Itob(tier1_total),             # 8 bytes
    Bytes(",t2="), Itob(tier2_total),             # 8 bytes
    Bytes(",t3="), Itob(tier3_total),             # 8 bytes
    Bytes(",lott="), Itob(lott_holders_amount)    # 8 bytes
))
```

**The seed is a 32-byte value** embedded in the log after "seed="

---

## 💡 **Quick Reference: Draw Transaction IDs**

| Cycle | Transaction ID | Link |
|-------|---------------|------|
| 1 | Y6TGLFRFEPTCMRTEO2YRAED62MJ6ZGE4PVFHFE3QOFEX34KPGP4Q | [View](https://allo.info/tx/Y6TGLFRFEPTCMRTEO2YRAED62MJ6ZGE4PVFHFE3QOFEX34KPGP4Q) |
| 3 | NAMQKCP25Y4DGYKKGCKY6WSIDP5NXYS3MIFGE5GHZULEMCZRUYCA | [View](https://allo.info/tx/NAMQKCP25Y4DGYKKGCKY6WSIDP5NXYS3MIFGE5GHZULEMCZRUYCA) |
| 4 | IAG77ASU6ED7SLGOCBK33PXPTDP2SXOIR577CLHHRXZS372CNS7A | [View](https://allo.info/tx/IAG77ASU6ED7SLGOCBK33PXPTDP2SXOIR577CLHHRXZS372CNS7A) |
| 5 | ZLS7DVA5A4BOZL2TFEF6SQAU373P6TV725V23CGUZ7JZWOD2VMPA | [View](https://allo.info/tx/ZLS7DVA5A4BOZL2TFEF6SQAU373P6TV725V23CGUZ7JZWOD2VMPA) |
| 6 | Q55YMZURJA3KZ3EVUGHRSXCU6JZGXBP3TF5GCEXQOMAAMVZW34RA | [View](https://allo.info/tx/Q55YMZURJA3KZ3EVUGHRSXCU6JZGXBP3TF5GCEXQOMAAMVZW34RA) |
| 7 | L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q | [View](https://allo.info/tx/L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q) |

---

## 🛠️ **Example: Complete Verification Without APIs**

```bash
# Step 1: Get draw transaction from blockchain explorer
# Visit: https://allo.info/tx/<TX_ID>

# Step 2: Extract seed from logs (manual or script)
# Seed is in the "Logs" section

# Step 3: Verify draw
python3 verify_draw.py 7

# The verification script will fetch the seed from your API
# But you can compare it with what you see on the blockchain!
```

---

## ✅ **Verification Checklist**

To fully verify a draw without trusting anyone:

- [ ] Get draw transaction ID
- [ ] View transaction on Allo.info or Algoexplorer
- [ ] Confirm transaction was signed by app (not EOA)
- [ ] Check logs contain "DRAW_EXECUTED"
- [ ] Extract seed from logs (32 bytes after "seed=")
- [ ] Run verification with that seed
- [ ] Compare results with registered winners

If everything matches → **Draw is provably fair!**

---

## 🔐 **Why This Matters**

**Traditional Verification:**
```
Your App → Your API → Your Seed
```
*Must trust your API*

**Blockchain Verification:**
```
Algorand Blockchain → Transaction Logs → Seed
```
*No trust needed - pure blockchain data*

This is **true trustlessness**! 🎉

---

## 📚 **Further Reading**

- Algorand Indexer API: https://algonode.io/api/
- Algorand Transaction Format: https://developer.algorand.org/docs/
- AlgoSDK Documentation: https://py-algorand-sdk.readthedocs.io/

---

**Remember:** The blockchain never lies! 🔗
