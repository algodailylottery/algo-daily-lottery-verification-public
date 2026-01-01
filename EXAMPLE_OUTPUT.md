# Example Verification Output

This is what you'll see when you run the verification script.

## Command

```bash
python3 verify_draw.py 7
```

## Output

```
================================================================================
🔍 ALGORAND DAILY LOTTERY - FAIRNESS VERIFICATION
================================================================================

📋 Verifying Cycle 7...

Fetching draw data from API...
✅ Draw data loaded successfully

================================================================================
📊 DRAW INFORMATION
================================================================================

   Cycle ID:      7
   Random Seed:   5352984041323284126
   Pot Total:     3515.96 ALGO
   Total Entries: 3411
   Draw Tx:       L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q

   🔗 View on blockchain:
   https://allo.info/tx/L4BGKKTSTB3NGZF6WPXIBF2DBTY72X5G3UKOJFCB3H4XROLVYX2Q

🎲 Calculating winners from on-chain seed...
   Using Java Random algorithm with blockchain seed

================================================================================
📊 VERIFICATION RESULTS
================================================================================

🥇 TIER 1 (40% of pot - 1 winner):
   Prize:      1406.38 ALGO
   Calculated: Entry #729
   Registered: Entry #729
   Status:     ✅ MATCH

🥈 TIER 2 (20% of pot - 5 winners):
   Prize:      703.19 ALGO (total)
   Calculated: [394, 405, 560, 2216, 2778]
   Registered: [394, 405, 560, 2216, 2778]
   Status:     ✅ SAME ENTRIES
   Note:       Entry order may differ due to database sorting

🥉 TIER 3 (15% of pot - 10 winners):
   Prize:      527.39 ALGO (total)
   Calculated: 10 unique entries
   Registered: 10 unique entries
   Status:     ✅ SAME ENTRIES
   Note:       Entry order may differ due to database sorting

================================================================================
🏁 FINAL VERDICT
================================================================================

✅ ✅ ✅  DRAW IS FAIR AND VALID  ✅ ✅ ✅

All winners were correctly selected from the on-chain random seed.
The lottery system is PROVABLY FAIR - no manipulation detected.

================================================================================
```

## What This Means

- **Tier 1 MATCH**: The exact winning entry matches perfectly
- **Tier 2/3 SAME ENTRIES**: All winning entries match (order doesn't matter)
- **Blockchain seed**: This is the immutable random number from the smart contract
- **Verifiable**: You can run this as many times as you want - same result every time

## Try It Yourself!

```bash
# Install requirements
pip install requests

# Run verification
python3 verify_draw.py 7

# Or verify other cycles
python3 verify_draw.py 6
python3 verify_draw.py 5
python3 verify_draw.py 4
```

All cycles should show ✅ FAIR status!
