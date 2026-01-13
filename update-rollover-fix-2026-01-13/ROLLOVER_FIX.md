# Rollover Accumulation Bug Fix

**Date:** January 13, 2025
**TX ID:** [WOMBSZZTS3QP7DGTPELYSYDEKRZABY4Q27GKDW53ZUXQWGCKPCPQ](https://allo.info/tx/WOMBSZZTS3QP7DGTPELYSYDEKRZABY4Q27GKDW53ZUXQWGCKPCPQ)
**Confirmed Round:** 57390482

## Issue

The rollover calculation was incorrectly accumulating across cycles:

```python
# Before (bug)
App.globalPut(KEY_CURRENT_POT, previous_rollover + rollover_amount)
```

This caused the pot to be seeded with `previous_rollover + 5%` instead of just `5%`, inflating the pot variable over time.

## Fix

```python
# After (fixed)
App.globalPut(KEY_CURRENT_POT, rollover_amount)
```

Now each cycle's pot is correctly seeded with only 5% of the previous cycle's pot.

## Funds Status

- **No user funds were lost**
- Contract shortfall was covered by the Engineering wallet
- All prizes remain fully claimable
- Fix prevents recurrence in future cycles
