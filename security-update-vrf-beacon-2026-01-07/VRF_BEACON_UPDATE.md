# Security Update: Algorand VRF Beacon Integration

**Date:** January 2026
**Type:** Major Security Upgrade
**Impact:** Enhanced randomness - cryptographically provable

---

## What Changed

The smart contract now uses **Algorand's official Randomness Beacon** instead of deriving seed from blockchain data.

**Before (Blockchain-Derived Seed):**
```python
# Seed generated from blockchain data
seed = SHA256(timestamp + pot + entries + round + sender)
```

**After (VRF Beacon):**
```python
# Seed from Algorand's cryptographic Randomness Beacon
seed = beacon.get(commitment_round)  # 32-byte VRF output
```

---

## Why This Upgrade

### Previous Method
The old seed was derived from:
- Block timestamp
- Pot total
- Total entries
- Block round
- Transaction sender

While verifiable, this had theoretical limitations since values could be partially predicted.

### New Method: VRF Beacon
Algorand's Randomness Beacon provides:
- **Cryptographically secure** randomness via Verifiable Random Functions
- **Unpredictable** - no one can know the output until it's revealed
- **Verifiable** - anyone can verify the beacon output is legitimate
- **Commit-reveal pattern** - prevents any manipulation

---

## How It Works

### Commit-Reveal Flow

```
    CYCLE ENDS                    ~40 seconds later
         |                              |
         v                              v
  +--------------+              +--------------+
  |    COMMIT    |              |    REVEAL    |
  +--------------+              +--------------+
         |                              |
         v                              v
  +----------------+            +------------------+
  | Lock in future |            | Beacon generates |
  | round number   |            | VRF for that     |
  | (current + 8)  |            | round            |
  +----------------+            +------------------+
         |                              |
         |      BLOCKCHAIN ROUNDS       |
         |   ========================>  |
         |   Round N    ...    Round N+8|
         |                              |
         v                              v
  +----------------+            +------------------+
  | Nobody knows   |            | Seed revealed    |
  | what seed will |            | Winners selected |
  | be             |            | deterministically|
  +----------------+            +------------------+


  WHY THIS IS SECURE:
  +----------------------------------------------------------+
  |  At COMMIT time:  Beacon output for round N+8 doesn't    |
  |                   exist yet - impossible to predict      |
  |                                                          |
  |  At REVEAL time:  Round N+8 already passed - impossible  |
  |                   to change the committed round          |
  +----------------------------------------------------------+
```

### Two-Phase Draw Process

**Phase 1: Commit** (`execute_draw_commit`)
- Commits to future round (current + 8)
- Stores commitment on-chain
- Logs: `DRAW_COMMITTED`

**Phase 2: Reveal** (`execute_draw_reveal`, after ~40 seconds)
- Calls Algorand Randomness Beacon for committed round
- Gets 32-byte VRF seed
- Distributes fees, logs seed, resets cycle

### Beacon Details

| Network | Beacon App ID |
|---------|---------------|
| Mainnet | 1615566206 |
| Testnet | 600011887 |

---

## Verification

The lottery remains fully verifiable:

```bash
python3 verify_draw.py <cycle_id>
```

**What's verified:**
- VRF seed retrieved from blockchain logs
- Winners calculated deterministically from seed
- Registered winners match calculated winners

---

## Seed Conversion: VRF to JavaRandom

The VRF beacon returns a **32-byte (256-bit)** seed, but JavaRandom expects a **64-bit** seed.

### Conversion Method

```
VRF Seed (32 bytes):
  a1b2c3d4 e5f6a7b8 c9d0e1f2 a3b4c5d6 ...  (64 hex chars)
  |________|
  First 8 bytes

JavaRandom Seed (8 bytes):
  a1b2c3d4e5f6a7b8  →  int64 (big-endian)
```

### Code

```python
def convert_vrf_seed_to_random_seed(vrf_seed_hex):
    """
    Convert 32-byte VRF seed to JavaRandom seed.
    Takes first 8 bytes as big-endian int64.
    """
    seed_bytes = bytes.fromhex(vrf_seed_hex)
    return int.from_bytes(seed_bytes[:8], byteorder='big')
```

### Why First 8 Bytes?

- VRF output is uniformly random across all 32 bytes
- First 8 bytes contain 64 bits of entropy (sufficient for JavaRandom)
- Consistent, deterministic conversion everyone can verify
- JavaRandom internally uses only 48 bits anyway

### Example

```
VRF Seed (hex): 7f3a9b2c8d1e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
First 8 bytes:  7f3a9b2c8d1e4f5a
As int64:       9150747060186992474
```

---

## Security Improvements

| Aspect | Before | After |
|--------|--------|-------|
| Randomness source | Blockchain data | VRF Beacon |
| Predictability | Partially predictable | Cryptographically unpredictable |
| Manipulation | Theoretical attack vectors | No known attack vectors |
| Verification | Verifiable | Verifiable |

---

## Summary

This upgrade moves from blockchain-derived randomness to Algorand's official VRF Beacon, providing cryptographically secure and provably fair winner selection.

**Don't trust, verify!**
