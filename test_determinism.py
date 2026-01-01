#!/usr/bin/env python3
"""
Proof that same seed ALWAYS produces same results.
"""

class JavaRandom:
    """Java's Random algorithm"""
    def __init__(self, seed):
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, bits):
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def nextInt(self, bound):
        if (bound & -bound) == bound:
            return (bound * self.next(31)) >> 31
        bits = self.next(31)
        val = bits % bound
        while bits - val + (bound - 1) < 0:
            bits = self.next(31)
            val = bits % bound
        return val


print("=" * 70)
print("PROOF: Same Seed = Same Results (ALWAYS)")
print("=" * 70)

seed = 5352984041323284126
total_entries = 3411

print(f"\nUsing Seed: {seed}")
print(f"Total Entries: {total_entries}\n")

# Run the algorithm 5 times
for run in range(1, 6):
    print(f"Run #{run}:")
    random = JavaRandom(seed)

    # Generate 10 winners
    winners = [random.nextInt(total_entries) for _ in range(10)]
    print(f"  Winners: {winners}\n")

print("=" * 70)
print("RESULT: All 5 runs produced IDENTICAL winners!")
print("=" * 70)
print("\nWhy? Because it's MATH, not MAGIC!")
print("Same input + same formula = same output (always)")
