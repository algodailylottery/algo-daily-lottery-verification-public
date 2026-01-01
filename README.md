# Algorand Daily Lottery - Verification Tools

**Provably Fair Lottery Verification System**

Don't trust, verify! This repository contains everything you need to independently verify that our Algorand-based daily lottery is fair and transparent.

## Quick Start

```bash
# Download the verification script
wget https://raw.githubusercontent.com/algodailylottery/algo-daily-lottery-verification-public/main/verify_draw.py

# Install requirements
pip install requests

# Verify any cycle
python3 verify_draw.py 7
```

## What Gets Verified

- **Tier 1 Winner** (40% of pot) - Exact entry match
- **Tier 2 Winners** (20% of pot) - All 5 winning entries
- **Tier 3 Winners** (15% of pot) - All 10 winning entries

## How It Works

### 1. On-Chain Seed Generation
The smart contract generates a random seed using blockchain data:
- Block timestamp (unpredictable)
- Pot total
- Total entries
- Block round number (unpredictable)
- Transaction sender

This seed is logged on the Algorand blockchain and **cannot be changed**.

### 2. Deterministic Winner Selection
Using the blockchain seed, winners are selected with Java's Random algorithm.

**Key principle**: Same seed = Same winners (always)

This makes any manipulation immediately detectable.

### 3. Independent Verification
Anyone can:
1. Get the seed from blockchain
2. Run the same algorithm
3. Compare results with registered winners

If they match ✅ = Fair
If they don't ❌ = Suspicious

## Tools Included

### 🔧 `verify_draw.py`
Main verification script - compares calculated winners with registered winners.

**Usage:**
```bash
python3 verify_draw.py <cycle_number>
```

**Example:**
```bash
python3 verify_draw.py 7
```

### 🔗 `get_seed_from_blockchain.py`
Retrieves the random seed directly from Algorand blockchain (no API needed).

**Usage:**
```bash
python3 get_seed_from_blockchain.py 7
```

### 🧪 `test_determinism.py`
Demonstrates that the same seed always produces identical results.

**Usage:**
```bash
python3 test_determinism.py
```

## Documentation

- **[VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md)** - Complete user guide
- **[VERIFICATION_DIAGRAM.md](VERIFICATION_DIAGRAM.md)** - Visual diagrams explaining the process
- **[BLOCKCHAIN_SEED_RETRIEVAL.md](BLOCKCHAIN_SEED_RETRIEVAL.md)** - How to get seed from blockchain

## Smart Contract

- **App ID**: 3380359414
- **Network**: Algorand Mainnet
- **View on Explorer**: https://allo.info/app/3380359414

## Example Verification

```bash
$ python3 verify_draw.py 7

🔍 ALGORAND DAILY LOTTERY - FAIRNESS VERIFICATION

📋 Verifying Cycle 7...
✅ Draw data loaded successfully

📊 Draw Information:
   Cycle ID:      7
   Random Seed:   5352984041323284126
   Pot Total:     3515.96 ALGO
   Total Entries: 3411

🎲 Calculating winners from on-chain seed...

🥇 TIER 1: ✅ MATCH
🥈 TIER 2: ✅ SAME ENTRIES
🥉 TIER 3: ✅ SAME ENTRIES

✅ ✅ ✅  DRAW IS FAIR AND VALID  ✅ ✅ ✅
```

## Why This Matters

**Traditional Lottery:**
```
Operator → Secret Draw → Winners
```
❌ You must trust the operator

**Our Lottery:**
```
Blockchain → Public Seed → Verifiable Winners
```
✅ No trust needed - pure math

## Security

The lottery uses:
- ✅ On-chain seed generation (immutable)
- ✅ Deterministic algorithm (verifiable)
- ✅ Public blockchain logs (transparent)
- ✅ Open source tools (auditable)

**Can the admin cheat?**
No. If registered winners don't match the blockchain seed, this script will immediately detect it.

**Note on Tier 3 Winners:**
The smart contract was designed for 20 Tier 3 winners, but the implementation selects 10. We went live with 10 and decided to keep it stable rather than risk changes to the live system. The lottery is still provably fair - all prize money is distributed correctly. See [SECURITY.md](SECURITY.md#known-issues) for full details.

## Verify Historical Draws

All past cycles can be verified anytime:

| Cycle | Date | Status | Blockchain TX |
|-------|------|--------|---------------|
| 7 | Latest | ✅ Verified | [View](https://allo.info/tx/L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q) |
| 6 | - | ✅ Verified | [View](https://allo.info/tx/Q55YMZURJA3KZ3EVUGHRSXCU6JZGXBP3TF5GCEXQOMAAMVZW34RA) |
| 5 | - | ✅ Verified | [View](https://allo.info/tx/ZLS7DVA5A4BOZL2TFEF6SQAU373P6TV725V23CGUZ7JZWOD2VMPA) |
| 4 | - | ✅ Verified | [View](https://allo.info/tx/IAG77ASU6ED7SLGOCBK33PXPTDP2SXOIR577CLHHRXZS372CNS7A) |
| 3 | - | ✅ Verified | [View](https://allo.info/tx/NAMQKCP25Y4DGYKKGCKY6WSIDP5NXYS3MIFGE5GHZULEMCZRUYCA) |
| 1 | - | ✅ Verified | [View](https://allo.info/tx/Y6TGLFRFEPTCMRTEO2YRAED62MJ6ZGE4PVFHFE3QOFEX34KPGP4Q) |

## Requirements

- Python 3.6+
- `requests` library: `pip install requests`

## Contributing

Found an issue? Open a GitHub issue or submit a pull request.

## License

MIT License - Free to use and modify.

## Support

- 📧 **Email**: info@algodailylottery.com
- 🐦 **Twitter**: [@algodailylottery](https://twitter.com/algodailylottery)
- 🐛 **GitHub Issues**: [Open an issue](https://github.com/algodailylottery/algo-daily-lottery-verification-public/issues)

---

**Remember: A fair lottery is a verifiable lottery. Don't trust, verify!** 🔐
