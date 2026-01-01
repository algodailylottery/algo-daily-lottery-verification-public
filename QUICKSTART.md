# Quick Start Guide

Get up and running in 60 seconds!

## Installation

```bash
# 1. Clone this repository
git clone https://github.com/algodailylottery/algorand-lottery-verification.git
cd algorand-lottery-verification

# 2. Install requirements
pip install -r requirements.txt
```

## Verify a Draw

```bash
# Verify Cycle 7
python3 verify_draw.py 7
```

That's it! You'll see:
- ✅ if the draw is fair
- ❌ if something is suspicious

## What You'll See

```
🔍 ALGORAND DAILY LOTTERY - FAIRNESS VERIFICATION

📋 Verifying Cycle 7...
✅ Draw data loaded successfully

📊 Draw Information:
   Cycle ID:      7
   Random Seed:   5352984041323284126
   Pot Total:     3515.96 ALGO
   Total Entries: 3411

🥇 TIER 1: ✅ MATCH
🥈 TIER 2: ✅ SAME ENTRIES
🥉 TIER 3: ✅ SAME ENTRIES

✅ ✅ ✅  DRAW IS FAIR AND VALID  ✅ ✅ ✅
```

## Advanced: Verify from Blockchain

Want maximum trustlessness? Get the seed directly from Algorand blockchain:

```bash
# Get seed from blockchain (no API needed)
python3 get_seed_from_blockchain.py 7
```

## Test Determinism

See proof that same seed = same winners:

```bash
python3 test_determinism.py
```

This runs the algorithm 5 times with the same seed and shows identical results every time.

## Need Help?

- Read [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) for detailed explanations
- Check [VERIFICATION_DIAGRAM.md](VERIFICATION_DIAGRAM.md) for visual diagrams
- See [BLOCKCHAIN_SEED_RETRIEVAL.md](BLOCKCHAIN_SEED_RETRIEVAL.md) for blockchain methods

## Smart Contract

The PyTeal smart contract source code is in `lottery_contract.py`.

View it live on Algorand:
- **App ID**: 3380359414
- **Explorer**: https://allo.info/app/3380359414

---

**Questions?** Open an issue on GitHub!
