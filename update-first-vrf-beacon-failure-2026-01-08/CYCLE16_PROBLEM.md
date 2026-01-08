# CYCLE16_PROBLEM1.md

## Problem Description
The VRF draw commit transaction failed with error:
```
TransactionPool.Remember: transaction SA5NB7UIYFSAM4LFIKLHBUKSOHXWED4DOU47AXDSY5TULBGOW5PQ:
logic eval error: store integer count 14 exceeds schema integer count 13
```

## Timeline
- **14:40:30 UTC** - Backend triggered VRF draw for Cycle 16
- **14:40:30 UTC** - Transaction rejected by network with schema error

## Root Cause
The updated contract code attempted to store new global state variables for VRF support:
- `beacon_id` (uint) - Beacon app ID
- `commitment_round` (uint) - Round committed for randomness
- `draw_status` (uint) - Draw state (0=none, 1=committed, 2=revealed)
- `vrf_seed` (bytes) - 32-byte VRF seed

However, the mainnet contract schema is **fixed at creation time** and cannot be changed:
- Mainnet schema: **13 uints, 2 bytes**
- VRF code required: **16 uints, 3 bytes**

When the contract tried to write the 14th uint (`commitment_round`), Algorand rejected the transaction.

## Fix Applied
Repurposed existing unused global state slots instead of adding new ones:

| Original Key | Original Value | New Purpose |
|-------------|----------------|-------------|
| `test_mode` | Always 0 (unused on mainnet) | `draw_status` |
| `lott_rate` | Always 1 (hardcoded) | `commitment_round` |

Additionally:
- `beacon_id` - Not stored, use `BEACON_MAINNET` constant (1615566206)
- `vrf_seed` - Not stored, only logged in DRAW_REVEALED event

## Code Changes
**File:** `contracts/lottery_contract.py`

```python
# Before (new keys that exceeded schema)
KEY_BEACON_APP_ID = Bytes("beacon_id")
KEY_COMMITMENT_ROUND = Bytes("commit_round")
KEY_DRAW_STATUS = Bytes("draw_status")
KEY_VRF_SEED = Bytes("vrf_seed")

# After (repurposed existing keys)
KEY_COMMITMENT_ROUND = Bytes("lott_rate")   # Repurposed
KEY_DRAW_STATUS = Bytes("test_mode")        # Repurposed
# beacon_id and vrf_seed removed - use constants/logs instead
```

## Verification
Contract redeployed successfully:
- TX: `QA6BZRMAVDUGPKWFTXLEZGOWL5J4U6HVMTVSSL3LHLTP24FS3IIA`
- Confirmed round: 57245651
- Schema: 13 uints, 2 bytes (unchanged, compatible)

## Why This Didn't Happen on Testnet
On testnet, we deployed a **fresh contract** with the VRF code, which meant:
- The schema was defined at creation time with the full VRF requirements (16 uints, 3 bytes)
- No schema mismatch because it was a new deployment, not an update

On mainnet, we performed a **contract update** (not a new deployment) because:
- The existing contract had active cycles, user entries, and funds
- Users had already opted in and purchased entries
- Deploying a new contract would require migrating all state and user opt-ins

Contract updates in Algorand only change the **code**, not the **schema**. The schema is permanently fixed at contract creation.

## Lesson Learned
Algorand smart contract schemas are immutable after deployment. Any contract updates must work within the existing schema constraints. Plan state storage carefully during initial deployment, or design for slot reuse.

When adding new features to an existing contract:
1. Check if new state variables fit within the original schema
2. If not, consider repurposing unused slots
3. Alternatively, store data in box storage (which has no schema limits)
