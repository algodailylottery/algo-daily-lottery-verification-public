# Security Update: Execute Draw Restriction

**Date:** January 2026
**Type:** Security Enhancement
**Impact:** No user impact - backend only

---

## What Changed

The smart contract has been updated to restrict `execute_draw()` to only the contract creator.

**Before:**
```python
# Anyone could call execute_draw()
return Seq([
    Assert(cycle_has_ended),
    # ... rest of function
])
```

**After:**
```python
# Only creator can call execute_draw()
return Seq([
    Assert(is_creator),  # ← Security fix
    Assert(cycle_has_ended),
    # ... rest of function
])
```

---

## Why This Change

### The Vulnerability (Theoretical)

Before this update, anyone could call `execute_draw()` when a cycle ended. While the draw is still verifiable and fair, this created a theoretical attack vector:

**Last-Actor Manipulation Attack:**
1. Attacker waits for cycle to end
2. Attacker creates multiple Algorand accounts (free)
3. For each account, attacker simulates what seed would be generated
4. Attacker chooses the account that produces the most favorable seed
5. Attacker calls `execute_draw()` from that account

**Why this matters:**
- The seed includes `Txn.sender()` (the caller's address)
- Different senders → different seeds → different winners
- Attacker could increase their odds by testing multiple accounts

### Why No One Exploited It

- ✅ Backend was fast (executed draw immediately when cycle ended)
- ✅ Small/new lottery (low visibility)
- ✅ Small pots (not worth the effort)
- ✅ Requires technical knowledge
- ✅ **We caught it before exploitation!**

**Verification:** You can verify only the creator called execute_draw:
```bash
python3 monitor_execute_draw.py
```

---

## Why This Update is SAFE

### 1. Fairness Preserved ✅

**Before and After:**
- ✅ Seed is still generated on-chain (public, immutable)
- ✅ Seed is still deterministic (same seed = same winners)
- ✅ Winners are still verifiable with `verify_draw.py`
- ✅ Blockchain transparency unchanged

**The only difference:** WHO can trigger the draw, not HOW winners are selected.

### 2. Backend Already Used Creator Account ✅

**Important:** The backend was already calling `execute_draw()` using the creator account!

This means:
- ✅ No functional change for normal operation
- ✅ Backend continues to work exactly as before
- ✅ Only prevents theoretical attacks by others

---

## How to Verify the Lottery is Still Fair

### Verification 1: Draw Fairness (Unchanged)

**Verifies:** Winners were correctly selected from the on-chain seed

```bash
python3 verify_draw.py <cycle_id>
```

**What it checks:**
- Fetches the random seed from blockchain
- Recalculates winners using the same algorithm
- Compares with registered winners
- If they match → Draw is fair ✅

**Example:**
```bash
$ python3 verify_draw.py 13

✅ ✅ ✅  DRAW IS FAIR AND VALID  ✅ ✅ ✅

All winners were correctly selected from the on-chain random seed.
```

This verification **hasn't changed** - draws are still provably fair!

### Verification 2: Single Draw Per Cycle (NEW)

**Verifies:** Creator doesn't run multiple draws to cherry-pick results

```bash
python3 verify_single_draw_per_cycle.py
```

**What it checks:**
- Fetches all execute_draw transactions from blockchain
- Groups them by cycle
- Verifies each cycle has EXACTLY one draw
- Detects any cherry-picking attempts

**Example:**
```bash
$ python3 verify_single_draw_per_cycle.py

✅ Cycle 1: 1 draw
✅ Cycle 2: 1 draw
✅ Cycle 3: 1 draw
...
✅ Cycle 13: 1 draw

Each cycle has exactly ONE draw - no cherry-picking detected.
```

This proves the creator accepts whatever result they get (fair play)!

### Verification 3: Only Creator Calls (NEW)

**Verifies:** No one else is trying to manipulate the draw

```bash
python3 monitor_execute_draw.py
```

**What it checks:**
- All execute_draw transactions
- Who called them (should be creator only)
- Alerts if non-creator calls detected

---

## Why This Update is in the Public Repo

This repository exists for **transparency and verification**. The security update demonstrates:

### 1. Transparency ✅
- We openly discuss the vulnerability
- We explain the fix clearly
- We provide verification tools
- We don't hide security issues

### 2. Continuous Improvement ✅
- We identified a theoretical vulnerability
- We fixed it proactively (before exploitation)
- We improved security while maintaining fairness
- We documented everything publicly

### 3. Trust Through Verification ✅
- Users don't need to trust us
- Users can verify everything themselves
- The math doesn't lie
- The blockchain doesn't lie

---

## Timeline

**Discovery:** January 2026 (Security audit)
**Status:** Vulnerability existed but was never exploited
**Fix Applied:** January 2026 (Mainnet contract updated)
**Verification:**
- All historical draws remain verifiable ✅
- Only creator called execute_draw (verified) ✅
- No exploitation detected ✅

---

## Technical Details

### What the Fix Prevents

**Attack Scenario (Before Fix):**
```python
# Attacker simulates from multiple accounts
Account1: seed = SHA256(... + Account1 + ...)  → Winners: [Entry #500, #2010, ...]
Account2: seed = SHA256(... + Account2 + ...)  → Winners: [Entry #750, #1500, ...]  ← I win!
Account3: seed = SHA256(... + Account3 + ...)  → Winners: [Entry #320, #890, ...]

# Attacker calls from Account2 (they win)
```

**After Fix:**
```python
# Only creator can call - attacker rejected
Assert(is_creator)  # ← Attacker's transaction rejected
```

### Why Verification Still Works

The verification works by:
1. Fetching the seed from the draw transaction (public on blockchain)
2. Running the same deterministic algorithm
3. Comparing calculated winners with registered winners

**The fix doesn't change this!** The seed is still:
- ✅ Generated on-chain
- ✅ Publicly visible
- ✅ Deterministically used
- ✅ Fully verifiable

---

## Conclusion

This security update:
- ✅ Eliminates a theoretical vulnerability
- ✅ Maintains complete verifiability
- ✅ Preserves fairness guarantees
- ✅ Demonstrates commitment to security
- ✅ Enhances trust through transparency

**The lottery is now more secure AND remains fully verifiable.**

**Don't trust, verify!** 🔐

---

## Resources

- **Verify Draws:** `python3 verify_draw.py <cycle_id>`
- **Verify Single Draw:** `python3 verify_single_draw_per_cycle.py`
- **Monitor Security:** `python3 monitor_execute_draw.py`
- **Smart Contract:** `lottery_contract.py`
- **GitHub:** https://github.com/algodailylottery/algo-daily-lottery-verification-public

**Questions?** Open an issue on GitHub or reach out to support.
