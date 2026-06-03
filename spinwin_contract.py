#!/usr/bin/env python3
"""
Algorand Spin & Win - Smart Contract with Randomness Beacon
Version: 2.0

A trustless "Spin the Wheel" game using Algorand's VRF Randomness Beacon.
Separate contract from the lottery - uses the same LOTT token and beacon.

Key Features:
- Dynamic stakes: stake = configurable % of pot (self-sustaining economics)
- Single-spinner lock: Only one player can spin at a time (contract-enforced)
- Player-chosen VRF power level (1-8) = beacon commitment offset
- Shared prize pot model: losses grow the pot, wins pay from it
- Auto-pay on reveal: winners are paid immediately, no claim step
- Spectator-friendly: log events for real-time WebSocket broadcasting

Game Flow:
1. Player calls spin_commit(tier, power) with stake payment
2. Contract locks spinner, commits to future beacon round
3. Backend waits for beacon data, calls spin_reveal()
4. Contract fetches VRF seed, determines color, pays out instantly
5. Lock released for next player
"""

from pyteal import *


# ============================================================================
# GLOBAL STATE KEYS
# ============================================================================

# Prize pot
KEY_POT = Bytes("pot")

# Spin state machine
KEY_SPIN_STATE = Bytes("spin_state")
KEY_COMMIT_ROUND = Bytes("commit_round")
KEY_SPIN_TIER = Bytes("spin_tier")
KEY_SPIN_STAKE = Bytes("spin_stake")
KEY_SPIN_ROUND = Bytes("spin_round")
KEY_SPIN_POWER = Bytes("spin_power")

# Lifetime counters
KEY_TOTAL_SPINS = Bytes("total_spins")
KEY_TOTAL_WON = Bytes("total_won")
KEY_TOTAL_JACKPOTS = Bytes("total_jackpots")

# Configuration
KEY_IS_PAUSED = Bytes("is_paused")
KEY_LOTT_ASSET_ID = Bytes("lott_id")
KEY_MIN_POT_T1 = Bytes("min_pot_t1")
KEY_MIN_POT_T2 = Bytes("min_pot_t2")
KEY_MIN_POT_T3 = Bytes("min_pot_t3")
KEY_EXPIRE_ROUNDS = Bytes("expire_rounds")

# Wallet addresses (bytes)
KEY_ENGINEERING_WALLET = Bytes("eng_wallet")
KEY_LOTT_DIST_WALLET = Bytes("lott_wallet")
KEY_CURRENT_SPINNER = Bytes("spinner")
KEY_BEACON_APP_ID = Bytes("beacon_id")

# Dynamic stake configuration
KEY_STAKE_PCT_T1 = Bytes("pct_t1")       # Tier 1 stake as basis points of pot (100 = 1%)
KEY_STAKE_PCT_T2 = Bytes("pct_t2")       # Tier 2 stake as basis points of pot (200 = 2%)
KEY_STAKE_PCT_T3 = Bytes("pct_t3")       # Tier 3 stake as basis points of pot (500 = 5%)
KEY_MIN_STAKE = Bytes("min_stake")        # Minimum stake in microALGOs
KEY_MAX_STAKE = Bytes("max_stake")        # Maximum stake in microALGOs


# ============================================================================
# CONSTANTS
# ============================================================================

# Spin states
SPIN_IDLE = Int(0)
SPIN_COMMITTED = Int(1)

# Total wheel segments
TOTAL_SEGMENTS = Int(38)

# Color codes
COLOR_BLACK = Int(0)
COLOR_GREEN = Int(1)
COLOR_BLUE = Int(2)
COLOR_GOLD = Int(3)

# Payout percentages (basis points, 10000 = 100%)
PAYOUT_GREEN_BPS = Int(1000)            # 10% of pot
PAYOUT_BLUE_BPS = Int(1800)             # 18% of pot
PAYOUT_GOLD_WINNER_BPS = Int(4500)      # 45% of pot to winner
PAYOUT_GOLD_ROLLOVER_BPS = Int(4500)    # 45% stays as pot seed — keeps the median pot growing
PAYOUT_GOLD_LOTT_BPS = Int(500)         # 5% to LOTT holders
PAYOUT_GOLD_PLATFORM_BPS = Int(500)     # 5% to platform/engineering — charged ONLY on a jackpot

# Fee percentages
# There is NO platform fee on the stake: 100% of every stake feeds the pot. The
# platform/engineering 5% is collected only when a gold jackpot is won (see spin_reveal).
# This keeps the pot self-sustaining (full stake inflow) and transparent to players.
LOTT_REWARD_DIVISOR = Int(10_000_000)   # stake / 10M = 10% of stake as LOTT (0-decimal)

# Beacon constants
REVEAL_WAIT_ROUNDS = Int(4)  # Minimum rounds after commitment for beacon data


# ============================================================================
# STATE SCHEMA DEFINITIONS
# ============================================================================

def get_global_schema():
    """
    Define global state schema for the Spin & Win contract.

    22 uint64: pot, spin_state, commit_round, spin_tier, spin_stake,
               spin_round, spin_power, total_spins, total_won, total_jackpots,
               is_paused, lott_id, min_pot_t1, min_pot_t2, min_pot_t3,
               expire_rounds, beacon_id,
               pct_t1, pct_t2, pct_t3, min_stake, max_stake

    3 bytes:   eng_wallet, lott_wallet, spinner
    """
    return (22, 3)


def get_local_schema():
    """No local state - users don't need to opt-in to the app."""
    return (0, 0)


# ============================================================================
# APPLICATION CREATION
# ============================================================================

def handle_creation():
    """
    Handle application creation.

    Application Args:
    - args[0]: LOTT Asset ID (uint64)
    - args[1]: Beacon App ID (uint64) - VRF randomness beacon
    """
    lott_asset_id = Btoi(Txn.application_args[0])
    beacon_app_id = Btoi(Txn.application_args[1])

    return Seq([
        Assert(lott_asset_id > Int(0)),
        Assert(beacon_app_id > Int(0)),

        # Prize pot starts at 0 (must be seeded by admin)
        App.globalPut(KEY_POT, Int(0)),

        # Spin state machine - IDLE
        App.globalPut(KEY_SPIN_STATE, SPIN_IDLE),
        App.globalPut(KEY_COMMIT_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_TIER, Int(0)),
        App.globalPut(KEY_SPIN_STAKE, Int(0)),
        App.globalPut(KEY_SPIN_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_POWER, Int(0)),
        App.globalPut(KEY_CURRENT_SPINNER, Global.zero_address()),

        # Lifetime counters
        App.globalPut(KEY_TOTAL_SPINS, Int(0)),
        App.globalPut(KEY_TOTAL_WON, Int(0)),
        App.globalPut(KEY_TOTAL_JACKPOTS, Int(0)),

        # Configuration
        App.globalPut(KEY_IS_PAUSED, Int(0)),
        App.globalPut(KEY_LOTT_ASSET_ID, lott_asset_id),
        App.globalPut(KEY_BEACON_APP_ID, beacon_app_id),
        App.globalPut(KEY_ENGINEERING_WALLET, Txn.sender()),
        App.globalPut(KEY_LOTT_DIST_WALLET, Txn.sender()),

        # Minimum pot requirements per tier (microALGOs)
        App.globalPut(KEY_MIN_POT_T1, Int(500_000_000)),     # 500 ALGO
        App.globalPut(KEY_MIN_POT_T2, Int(1_000_000_000)),   # 1000 ALGO
        App.globalPut(KEY_MIN_POT_T3, Int(2_000_000_000)),   # 2000 ALGO

        # Expire timeout: ~5.5 minutes at ~3.3s/round
        App.globalPut(KEY_EXPIRE_ROUNDS, Int(100)),

        # Dynamic stake configuration: stakes are % of pot
        App.globalPut(KEY_STAKE_PCT_T1, Int(300)),             # 3% of pot
        App.globalPut(KEY_STAKE_PCT_T2, Int(600)),             # 6% of pot
        App.globalPut(KEY_STAKE_PCT_T3, Int(1200)),            # 12% of pot
        App.globalPut(KEY_MIN_STAKE, Int(100_000)),            # 0.1 ALGO minimum
        App.globalPut(KEY_MAX_STAKE, Int(1_000_000_000)),      # 1000 ALGO maximum

        Approve()
    ])


# ============================================================================
# TIER BOX SETUP
# ============================================================================

def setup_tier_boxes():
    """
    Create tier configuration boxes with default segment distributions.
    Must be called once after creation with sufficient MBR payment.

    Box format: [green_count(1B), blue_count(1B), gold_count(1B), reserved(1B)]

    Defaults match frontend/src/types/spinwin.ts STAKE_TIERS:
    - Tier 1 (50 ALGO):  1 green, 1 blue, 1 gold  = 3/38 win chance
    - Tier 2 (100 ALGO): 2 green, 2 blue, 2 gold  = 6/38 win chance
    - Tier 3 (200 ALGO): 4 green, 4 blue, 4 gold  = 12/38 win chance
    """
    return Seq([
        Assert(Txn.sender() == Global.creator_address()),

        # Tier 1: 1 green, 1 blue, 1 gold
        App.box_put(Bytes("t1"), Concat(
            Extract(Itob(Int(1)), Int(7), Int(1)),   # green=1
            Extract(Itob(Int(1)), Int(7), Int(1)),   # blue=1
            Extract(Itob(Int(1)), Int(7), Int(1)),   # gold=1
            Extract(Itob(Int(0)), Int(7), Int(1)),   # reserved=0
        )),

        # Tier 2: 2 green, 2 blue, 2 gold
        App.box_put(Bytes("t2"), Concat(
            Extract(Itob(Int(2)), Int(7), Int(1)),
            Extract(Itob(Int(2)), Int(7), Int(1)),
            Extract(Itob(Int(2)), Int(7), Int(1)),
            Extract(Itob(Int(0)), Int(7), Int(1)),
        )),

        # Tier 3: 4 green, 4 blue, 4 gold
        App.box_put(Bytes("t3"), Concat(
            Extract(Itob(Int(4)), Int(7), Int(1)),
            Extract(Itob(Int(4)), Int(7), Int(1)),
            Extract(Itob(Int(4)), Int(7), Int(1)),
            Extract(Itob(Int(0)), Int(7), Int(1)),
        )),

        Log(Bytes("TIER_BOXES_CREATED")),
        Approve()
    ])


# ============================================================================
# ADMIN FUNCTIONS
# ============================================================================

def admin_opt_in_asset():
    """Opt contract into LOTT asset so it can send LOTT rewards."""
    asset_id_scratch = ScratchVar(TealType.uint64)

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        asset_id_scratch.store(App.globalGet(KEY_LOTT_ASSET_ID)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id_scratch.load(),
            TxnField.asset_amount: Int(0),
            TxnField.asset_receiver: Global.current_application_address(),
        }),
        InnerTxnBuilder.Submit(),
        Approve()
    ])


def seed_pot():
    """
    Admin deposits ALGO to seed or replenish the prize pot.

    Group transaction:
    - Txn[group_index - 1]: Payment to app address
    - Txn[group_index]:     This app call
    """
    payment_txn = Gtxn[Txn.group_index() - Int(1)]
    deposit_amount = payment_txn.amount()
    new_pot = App.globalGet(KEY_POT) + deposit_amount

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(Global.group_size() == Int(2)),
        Assert(payment_txn.type_enum() == TxnType.Payment),
        Assert(payment_txn.receiver() == Global.current_application_address()),
        Assert(payment_txn.sender() == Txn.sender()),
        Assert(deposit_amount > Int(0)),

        App.globalPut(KEY_POT, new_pot),

        Log(Concat(
            Bytes("POT_SEEDED:"),
            Bytes("amount="), Itob(deposit_amount),
            Bytes(",pot="), Itob(new_pot)
        )),

        Approve()
    ])


def pause():
    """Emergency pause - blocks new spins."""
    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        App.globalPut(KEY_IS_PAUSED, Int(1)),
        Log(Bytes("GAME_PAUSED")),
        Approve()
    ])


def unpause():
    """Resume after emergency pause."""
    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        App.globalPut(KEY_IS_PAUSED, Int(0)),
        Log(Bytes("GAME_UNPAUSED")),
        Approve()
    ])


def update_tier_config():
    """
    Update the segment distribution for a tier.

    Application Args:
    - args[1]: tier (1, 2, or 3)
    - args[2]: green_count
    - args[3]: blue_count
    - args[4]: gold_count

    Only allowed when no spin is active.
    """
    tier = Btoi(Txn.application_args[1])
    green = Btoi(Txn.application_args[2])
    blue = Btoi(Txn.application_args[3])
    gold = Btoi(Txn.application_args[4])

    tier_box_name = ScratchVar(TealType.bytes)

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_IDLE),
        Assert(Or(tier == Int(1), tier == Int(2), tier == Int(3))),
        # Total colored segments must be < 38 (need at least 1 black)
        Assert(green + blue + gold < TOTAL_SEGMENTS),
        Assert(green + blue + gold > Int(0)),

        tier_box_name.store(
            If(tier == Int(1), Bytes("t1"),
               If(tier == Int(2), Bytes("t2"), Bytes("t3")))
        ),

        App.box_put(tier_box_name.load(), Concat(
            Extract(Itob(green), Int(7), Int(1)),
            Extract(Itob(blue), Int(7), Int(1)),
            Extract(Itob(gold), Int(7), Int(1)),
            Extract(Itob(Int(0)), Int(7), Int(1)),
        )),

        Log(Concat(
            Bytes("TIER_UPDATED:"),
            Bytes("tier="), Itob(tier),
            Bytes(",green="), Itob(green),
            Bytes(",blue="), Itob(blue),
            Bytes(",gold="), Itob(gold)
        )),

        Approve()
    ])


def update_min_pot():
    """
    Adjust minimum pot threshold for a tier.

    Application Args:
    - args[1]: tier (1, 2, or 3)
    - args[2]: min_pot_amount (microALGOs)
    """
    tier = Btoi(Txn.application_args[1])
    min_pot = Btoi(Txn.application_args[2])

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(Or(tier == Int(1), tier == Int(2), tier == Int(3))),
        Assert(min_pot > Int(0)),

        If(tier == Int(1),
           App.globalPut(KEY_MIN_POT_T1, min_pot),
           If(tier == Int(2),
              App.globalPut(KEY_MIN_POT_T2, min_pot),
              App.globalPut(KEY_MIN_POT_T3, min_pot))
        ),

        Approve()
    ])


def set_wallets():
    """
    Update engineering and LOTT distribution wallet addresses.

    Accounts array:
    - accounts[1]: new engineering wallet
    - accounts[2]: new LOTT distribution wallet
    """
    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        App.globalPut(KEY_ENGINEERING_WALLET, Txn.accounts[1]),
        App.globalPut(KEY_LOTT_DIST_WALLET, Txn.accounts[2]),
        Approve()
    ])


def withdraw_excess():
    """
    Admin withdraws ALGO from contract, but never below pot + 1 ALGO buffer.

    Application Args:
    - args[1]: amount to withdraw (microALGOs)
    """
    amount = Btoi(Txn.application_args[1])
    pot = App.globalGet(KEY_POT)
    min_balance = pot + Int(1_000_000)  # pot + 1 ALGO MBR buffer

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_IDLE),
        Assert(amount > Int(0)),
        Assert(Balance(Global.current_application_address()) - amount >= min_balance),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: Txn.sender(),
            TxnField.amount: amount,
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),

        Approve()
    ])


def update_expire_rounds():
    """
    Update the expire timeout for stuck spins.

    Application Args:
    - args[1]: new expire_rounds value
    """
    new_expire = Btoi(Txn.application_args[1])

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(new_expire >= Int(20)),   # Minimum ~1 minute
        Assert(new_expire <= Int(500)),  # Maximum ~28 minutes
        App.globalPut(KEY_EXPIRE_ROUNDS, new_expire),
        Approve()
    ])


def update_stake_config():
    """
    Update dynamic stake configuration (percentages and bounds).

    Application Args:
    - args[1]: pct_t1 (basis points, e.g. 100 = 1% of pot)
    - args[2]: pct_t2 (basis points, e.g. 200 = 2% of pot)
    - args[3]: pct_t3 (basis points, e.g. 500 = 5% of pot)
    - args[4]: min_stake (microALGOs)
    - args[5]: max_stake (microALGOs)

    Only allowed when no spin is active.
    """
    pct_t1 = Btoi(Txn.application_args[1])
    pct_t2 = Btoi(Txn.application_args[2])
    pct_t3 = Btoi(Txn.application_args[3])
    min_stake = Btoi(Txn.application_args[4])
    max_stake = Btoi(Txn.application_args[5])

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_IDLE),

        # Validate percentages (1-5000 bps = 0.01% to 50% of pot)
        Assert(pct_t1 >= Int(1)),
        Assert(pct_t1 <= Int(5000)),
        Assert(pct_t2 >= Int(1)),
        Assert(pct_t2 <= Int(5000)),
        Assert(pct_t3 >= Int(1)),
        Assert(pct_t3 <= Int(5000)),

        # Validate bounds
        Assert(min_stake >= Int(1000)),       # At least 0.001 ALGO
        Assert(max_stake >= min_stake),
        Assert(max_stake <= Int(10_000_000_000)),  # Max 10000 ALGO

        App.globalPut(KEY_STAKE_PCT_T1, pct_t1),
        App.globalPut(KEY_STAKE_PCT_T2, pct_t2),
        App.globalPut(KEY_STAKE_PCT_T3, pct_t3),
        App.globalPut(KEY_MIN_STAKE, min_stake),
        App.globalPut(KEY_MAX_STAKE, max_stake),

        Log(Concat(
            Bytes("STAKE_CONFIG_UPDATED:"),
            Bytes("pct_t1="), Itob(pct_t1),
            Bytes(",pct_t2="), Itob(pct_t2),
            Bytes(",pct_t3="), Itob(pct_t3),
            Bytes(",min="), Itob(min_stake),
            Bytes(",max="), Itob(max_stake)
        )),

        Approve()
    ])


# ============================================================================
# CORE GAME: SPIN COMMIT (Phase 1)
# ============================================================================

def spin_commit():
    """
    Phase 1: Player pays stake, contract locks spinner, commits to beacon round.

    Application Args:
    - args[0]: "spin_commit"
    - args[1]: tier (uint64: 1, 2, or 3)
    - args[2]: power (uint64: 1-8, beacon commitment offset)

    Group transaction:
    - Txn[group_index - 1]: Payment of exact stake to app address
    - Txn[group_index]:     This app call

    Inner transactions:
    1. LOTT reward (10% of stake as LOTT tokens) to spinner

    No platform fee is taken on the stake — 100% of the stake feeds the pot. The
    platform's 5% is collected only on a gold jackpot (see spin_reveal).

    Fee: 2000 (1 base + 1 inner txn)
    """
    tier = Btoi(Txn.application_args[1])
    power = Btoi(Txn.application_args[2])
    payment_txn = Gtxn[Txn.group_index() - Int(1)]

    stake_amount = ScratchVar(TealType.uint64)
    raw_stake = ScratchVar(TealType.uint64)
    tier_pct = ScratchVar(TealType.uint64)
    min_pot = ScratchVar(TealType.uint64)
    lott_reward = ScratchVar(TealType.uint64)
    commitment_round = ScratchVar(TealType.uint64)
    next_spin_id = ScratchVar(TealType.uint64)
    current_pot = ScratchVar(TealType.uint64)

    return Seq([
        # === VALIDATIONS ===
        Assert(App.globalGet(KEY_IS_PAUSED) == Int(0)),

        # Validate tier (1, 2, or 3)
        Assert(Or(tier == Int(1), tier == Int(2), tier == Int(3))),

        # Validate power (1-8)
        Assert(power >= Int(1)),
        Assert(power <= Int(8)),

        # Cache pot value
        current_pot.store(App.globalGet(KEY_POT)),

        # Determine minimum pot for this tier
        min_pot.store(
            If(tier == Int(1), App.globalGet(KEY_MIN_POT_T1),
               If(tier == Int(2), App.globalGet(KEY_MIN_POT_T2),
                  App.globalGet(KEY_MIN_POT_T3)))
        ),

        # Verify pot meets minimum for chosen tier
        Assert(current_pot.load() >= min_pot.load()),

        # === DYNAMIC STAKE CALCULATION ===
        # Stake = pot * tier_percentage_bps / 10000, clamped to [min_stake, max_stake]
        # Overflow guard: pot * 500 overflows uint64 at ~36.9 billion ALGO
        # (entire Algorand supply is ~10B ALGO, so this is safe)
        tier_pct.store(
            If(tier == Int(1), App.globalGet(KEY_STAKE_PCT_T1),
               If(tier == Int(2), App.globalGet(KEY_STAKE_PCT_T2),
                  App.globalGet(KEY_STAKE_PCT_T3)))
        ),

        raw_stake.store(
            (current_pot.load() * tier_pct.load()) / Int(10000)
        ),

        # Clamp to [min_stake, max_stake]
        stake_amount.store(
            If(raw_stake.load() < App.globalGet(KEY_MIN_STAKE),
               App.globalGet(KEY_MIN_STAKE),
               If(raw_stake.load() > App.globalGet(KEY_MAX_STAKE),
                  App.globalGet(KEY_MAX_STAKE),
                  raw_stake.load()))
        ),

        # Round down to nearest 1000 microALGOs (0.001 ALGO) for clean amounts
        stake_amount.store(
            (stake_amount.load() / Int(1000)) * Int(1000)
        ),

        # Group transaction validation
        Assert(Global.group_size() == Int(2)),
        Assert(payment_txn.type_enum() == TxnType.Payment),
        Assert(payment_txn.receiver() == Global.current_application_address()),
        Assert(payment_txn.sender() == Txn.sender()),
        Assert(payment_txn.amount() == stake_amount.load()),

        # === SINGLE SPINNER LOCK ===
        # Critical: atomic check ensures only one spinner at a time
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_IDLE),

        # Calculate values
        lott_reward.store(stake_amount.load() / LOTT_REWARD_DIVISOR),
        commitment_round.store(Global.round() + power),
        next_spin_id.store(App.globalGet(KEY_TOTAL_SPINS) + Int(1)),

        # === LOCK THE SPINNER ===
        App.globalPut(KEY_SPIN_STATE, SPIN_COMMITTED),
        App.globalPut(KEY_CURRENT_SPINNER, Txn.sender()),
        App.globalPut(KEY_SPIN_TIER, tier),
        App.globalPut(KEY_SPIN_STAKE, stake_amount.load()),
        App.globalPut(KEY_SPIN_ROUND, Global.round()),
        App.globalPut(KEY_SPIN_POWER, power),
        App.globalPut(KEY_COMMIT_ROUND, commitment_round.load()),

        # === SEND LOTT REWARD (10% of stake as LOTT) ===
        # 50 ALGO stake / 10_000_000 = 5 LOTT (0-decimal token)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: App.globalGet(KEY_LOTT_ASSET_ID),
            TxnField.asset_amount: lott_reward.load(),
            TxnField.asset_receiver: Txn.sender(),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),

        # === LOG EVENT ===
        Log(Concat(
            Bytes("SPIN_STARTED:"),
            Bytes("spinner="), Txn.sender(),
            Bytes(",tier="), Itob(tier),
            Bytes(",stake="), Itob(stake_amount.load()),
            Bytes(",power="), Itob(power),
            Bytes(",commit_round="), Itob(commitment_round.load()),
            Bytes(",spin_id="), Itob(next_spin_id.load())
        )),

        Approve()
    ])


# ============================================================================
# CORE GAME: SPIN REVEAL (Phase 2)
# ============================================================================

def spin_reveal():
    """
    Phase 2: Fetch VRF seed from beacon, determine result, pay out instantly.

    Only callable by creator (the backend).

    Must include in transaction:
    - foreign_apps: [beacon_app_id from global state]
    - boxes: [tier box for the active tier, e.g. (0, "t1")]

    Inner transactions (up to 4):
    1. Beacon call (always)
    2. Winner payout (if green/blue/gold)
    3. LOTT holder payment (if gold)
    4. Extra platform fee (if gold)

    Fee: 5000 (covers worst case)
    """
    commitment_round = App.globalGet(KEY_COMMIT_ROUND)
    spinner = App.globalGet(KEY_CURRENT_SPINNER)
    spin_tier = App.globalGet(KEY_SPIN_TIER)
    spin_stake = App.globalGet(KEY_SPIN_STAKE)
    current_pot = App.globalGet(KEY_POT)

    beacon_seed = ScratchVar(TealType.bytes)
    winning_segment = ScratchVar(TealType.uint64)
    winning_color = ScratchVar(TealType.uint64)
    payout_amount = ScratchVar(TealType.uint64)
    new_pot = ScratchVar(TealType.uint64)
    net_stake = ScratchVar(TealType.uint64)

    # Tier box reading
    tier_box_name = ScratchVar(TealType.bytes)
    tier_box_data = ScratchVar(TealType.bytes)
    green_count = ScratchVar(TealType.uint64)
    blue_count = ScratchVar(TealType.uint64)
    gold_count = ScratchVar(TealType.uint64)

    # Jackpot amounts
    lott_holder_amount = ScratchVar(TealType.uint64)
    jackpot_platform_amount = ScratchVar(TealType.uint64)

    current_spin_id = ScratchVar(TealType.uint64)
    revealed_tier = ScratchVar(TealType.uint64)

    return Seq([
        # === VALIDATIONS ===
        Assert(Txn.sender() == Global.creator_address()),
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_COMMITTED),
        Assert(Global.round() > commitment_round),
        Assert(Global.round() >= commitment_round + REVEAL_WAIT_ROUNDS),

        # Capture the spin tier BEFORE the spin state is reset below, so the SPIN_REVEALED
        # log records the real tier instead of 0 (off-chain verification reads it from the log).
        revealed_tier.store(spin_tier),

        # === GET VRF SEED FROM BEACON ===
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: App.globalGet(KEY_BEACON_APP_ID),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.SetField(TxnField.application_args, [
            Bytes("base16", "189392c5"),  # method selector for get(uint64,byte[])byte[]
            Itob(commitment_round),
            Bytes("base16", "0000"),      # empty byte[] (ABI encoded)
        ]),
        InnerTxnBuilder.Submit(),

        # Extract 32-byte VRF seed (skip 6 bytes: 4 ABI prefix + 2 length)
        beacon_seed.store(Suffix(InnerTxn.last_log(), Int(6))),
        Assert(Len(beacon_seed.load()) == Int(32)),

        # === DETERMINE WINNING SEGMENT ===
        # First 8 bytes of seed -> uint64 -> mod 38 -> segment 0-37
        winning_segment.store(
            Btoi(Extract(beacon_seed.load(), Int(0), Int(8))) % TOTAL_SEGMENTS
        ),

        # === READ TIER CONFIG BOX ===
        tier_box_name.store(
            If(spin_tier == Int(1), Bytes("t1"),
               If(spin_tier == Int(2), Bytes("t2"), Bytes("t3")))
        ),
        tier_box_data.store(App.box_extract(tier_box_name.load(), Int(0), Int(4))),

        # Parse segment counts from box [green(1B), blue(1B), gold(1B), reserved(1B)]
        green_count.store(Btoi(Extract(tier_box_data.load(), Int(0), Int(1)))),
        blue_count.store(Btoi(Extract(tier_box_data.load(), Int(1), Int(1)))),
        gold_count.store(Btoi(Extract(tier_box_data.load(), Int(2), Int(1)))),

        # === MAP SEGMENT TO COLOR ===
        # Cumulative ranges: [0, gold) = GOLD, [gold, gold+blue) = BLUE,
        # [gold+blue, gold+blue+green) = GREEN, [gold+blue+green, 38) = BLACK
        winning_color.store(
            If(winning_segment.load() < gold_count.load(),
                COLOR_GOLD,
                If(winning_segment.load() < gold_count.load() + blue_count.load(),
                    COLOR_BLUE,
                    If(winning_segment.load() < gold_count.load() + blue_count.load() + green_count.load(),
                        COLOR_GREEN,
                        COLOR_BLACK
                    )
                )
            )
        ),

        # === CALCULATE NET STAKE ===
        # No stake fee — 100% of the stake feeds the pot.
        net_stake.store(spin_stake),

        # === CALCULATE PAYOUT & NEW POT ===
        # Initialize jackpot-specific scratch vars (must be stored before any load)
        lott_holder_amount.store(Int(0)),
        jackpot_platform_amount.store(Int(0)),

        If(winning_color.load() == COLOR_BLACK,
            # LOSS: net stake added to pot, no payout
            Seq([
                payout_amount.store(Int(0)),
                new_pot.store(current_pot + net_stake.load()),
            ]),
        If(winning_color.load() == COLOR_GREEN,
            # GREEN: 15% of pot to winner
            Seq([
                payout_amount.store((current_pot * PAYOUT_GREEN_BPS) / Int(10000)),
                new_pot.store(current_pot - payout_amount.load() + net_stake.load()),
            ]),
        If(winning_color.load() == COLOR_BLUE,
            # BLUE: 25% of pot to winner
            Seq([
                payout_amount.store((current_pot * PAYOUT_BLUE_BPS) / Int(10000)),
                new_pot.store(current_pot - payout_amount.load() + net_stake.load()),
            ]),
            # GOLD (JACKPOT): 45% winner, 45% rollover, 5% LOTT, 5% platform
            Seq([
                payout_amount.store((current_pot * PAYOUT_GOLD_WINNER_BPS) / Int(10000)),
                lott_holder_amount.store((current_pot * PAYOUT_GOLD_LOTT_BPS) / Int(10000)),
                jackpot_platform_amount.store((current_pot * PAYOUT_GOLD_PLATFORM_BPS) / Int(10000)),
                new_pot.store(
                    (current_pot * PAYOUT_GOLD_ROLLOVER_BPS) / Int(10000)
                    + net_stake.load()
                ),
            ]),
        ))),

        # Update pot
        App.globalPut(KEY_POT, new_pot.load()),

        # === INNER TRANSACTIONS FOR PAYOUTS ===

        # Pay winner (if any payout)
        If(payout_amount.load() > Int(0),
            Seq([
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields({
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.receiver: spinner,
                    TxnField.amount: payout_amount.load(),
                    TxnField.fee: Int(0),
                }),
                InnerTxnBuilder.Submit(),
            ])
        ),

        # Jackpot-specific payments: LOTT holders + platform
        If(winning_color.load() == COLOR_GOLD,
            Seq([
                # 5% to LOTT holders
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields({
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.receiver: App.globalGet(KEY_LOTT_DIST_WALLET),
                    TxnField.amount: lott_holder_amount.load(),
                    TxnField.fee: Int(0),
                }),
                InnerTxnBuilder.Submit(),

                # 5% platform/engineering fee — charged ONLY on a jackpot
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields({
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.receiver: App.globalGet(KEY_ENGINEERING_WALLET),
                    TxnField.amount: jackpot_platform_amount.load(),
                    TxnField.fee: Int(0),
                }),
                InnerTxnBuilder.Submit(),
            ])
        ),

        # === UPDATE COUNTERS ===
        current_spin_id.store(App.globalGet(KEY_TOTAL_SPINS) + Int(1)),
        App.globalPut(KEY_TOTAL_SPINS, current_spin_id.load()),

        If(payout_amount.load() > Int(0),
            App.globalPut(KEY_TOTAL_WON, App.globalGet(KEY_TOTAL_WON) + payout_amount.load())
        ),

        If(winning_color.load() == COLOR_GOLD,
            App.globalPut(KEY_TOTAL_JACKPOTS, App.globalGet(KEY_TOTAL_JACKPOTS) + Int(1))
        ),

        # === RELEASE LOCK ===
        App.globalPut(KEY_SPIN_STATE, SPIN_IDLE),
        App.globalPut(KEY_CURRENT_SPINNER, Global.zero_address()),
        App.globalPut(KEY_COMMIT_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_TIER, Int(0)),
        App.globalPut(KEY_SPIN_STAKE, Int(0)),
        App.globalPut(KEY_SPIN_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_POWER, Int(0)),

        # === LOG EVENT ===
        Log(Concat(
            Bytes("SPIN_REVEALED:"),
            Bytes("spinner="), spinner,
            Bytes(",spin_id="), Itob(current_spin_id.load()),
            Bytes(",tier="), Itob(revealed_tier.load()),
            Bytes(",segment="), Itob(winning_segment.load()),
            Bytes(",color="), Itob(winning_color.load()),
            Bytes(",payout="), Itob(payout_amount.load()),
            Bytes(",pot_after="), Itob(new_pot.load()),
            Bytes(",seed="), beacon_seed.load()
        )),

        Approve()
    ])


# ============================================================================
# EXPIRE SPIN (Timeout Handler)
# ============================================================================

def expire_spin():
    """
    Clean up a stuck spin. Callable by anyone after timeout.

    Forfeits the full stake to the pot — the stake is NOT refunded.
    (There is no platform fee on the stake.)

    Forfeiting (rather than refunding) closes the abort-on-loss exploit:
    if a player could observe the VRF beacon for their commit round and
    then expire-and-refund losing spins, they'd selectively skip losses.
    With forfeit-to-pot, the player bears the risk that an unrevealed
    spin loses the stake entirely.

    Also consumes a spin_id (increments total_spins) exactly like spin_reveal,
    so an expired spin claims a unique id. Otherwise the next spin reuses the
    id and its reveal would overwrite the expired play's off-chain record.

    Fee: 1000 (1 base, no inner txn)
    """
    spin_round = App.globalGet(KEY_SPIN_ROUND)
    expire_limit = App.globalGet(KEY_EXPIRE_ROUNDS)
    spinner = App.globalGet(KEY_CURRENT_SPINNER)
    spin_stake = App.globalGet(KEY_SPIN_STAKE)

    net_stake = ScratchVar(TealType.uint64)
    expired_spin_id = ScratchVar(TealType.uint64)

    return Seq([
        # Verify there IS an active committed spin
        Assert(App.globalGet(KEY_SPIN_STATE) == SPIN_COMMITTED),

        # Verify it has expired
        Assert(Global.round() > spin_round + expire_limit),

        # Forfeit the full stake (no platform fee is taken on the stake)
        net_stake.store(spin_stake),

        # Forfeit the stake to the pot (closes abort-on-loss exploit)
        App.globalPut(KEY_POT, App.globalGet(KEY_POT) + net_stake.load()),

        # === CONSUME A SPIN ID ===
        # Increment total_spins so this expired spin claims a unique spin_id, just like a
        # revealed spin does. Without this the next spin reuses total_spins+1 and its reveal
        # overwrites the expired play's off-chain record (two plays collapse into one row).
        expired_spin_id.store(App.globalGet(KEY_TOTAL_SPINS) + Int(1)),
        App.globalPut(KEY_TOTAL_SPINS, expired_spin_id.load()),

        # Reset all spin state to IDLE
        App.globalPut(KEY_SPIN_STATE, SPIN_IDLE),
        App.globalPut(KEY_CURRENT_SPINNER, Global.zero_address()),
        App.globalPut(KEY_COMMIT_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_TIER, Int(0)),
        App.globalPut(KEY_SPIN_STAKE, Int(0)),
        App.globalPut(KEY_SPIN_ROUND, Int(0)),
        App.globalPut(KEY_SPIN_POWER, Int(0)),

        Log(Concat(
            Bytes("SPIN_EXPIRED:"),
            Bytes("spinner="), spinner,
            Bytes(",spin_id="), Itob(expired_spin_id.load()),
            Bytes(",forfeit="), Itob(net_stake.load())
        )),

        Approve()
    ])


# ============================================================================
# APPLICATION HANDLERS
# ============================================================================

def handle_noop():
    """Route NoOp application calls to the correct method."""
    method = Txn.application_args[0]

    return Cond(
        # Core game
        [method == Bytes("spin_commit"), spin_commit()],
        [method == Bytes("spin_reveal"), spin_reveal()],
        [method == Bytes("expire_spin"), expire_spin()],
        # Admin: pot & config
        [method == Bytes("seed_pot"), seed_pot()],
        [method == Bytes("setup_tier_boxes"), setup_tier_boxes()],
        [method == Bytes("update_tier_config"), update_tier_config()],
        [method == Bytes("update_min_pot"), update_min_pot()],
        [method == Bytes("update_expire_rounds"), update_expire_rounds()],
        # Admin: wallets, assets & stake config
        [method == Bytes("set_wallets"), set_wallets()],
        [method == Bytes("admin_opt_in_asset"), admin_opt_in_asset()],
        [method == Bytes("withdraw_excess"), withdraw_excess()],
        [method == Bytes("update_stake_config"), update_stake_config()],
        # Admin: emergency
        [method == Bytes("pause"), pause()],
        [method == Bytes("unpause"), unpause()],
    )


def handle_update():
    """Allow creator to update the application."""
    return If(
        Txn.sender() == Global.creator_address(),
        Approve(),
        Reject()
    )


def handle_delete():
    """Allow creator to delete the application."""
    return If(
        Txn.sender() == Global.creator_address(),
        Approve(),
        Reject()
    )


# ============================================================================
# MAIN APPROVAL PROGRAM
# ============================================================================

def approval_program():
    """Main approval program."""
    return Cond(
        [Txn.application_id() == Int(0), handle_creation()],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop()],
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_update()],
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_delete()],
        # No OptIn or CloseOut - this contract has no local state
    )


# ============================================================================
# CLEAR STATE PROGRAM
# ============================================================================

def clear_state_program():
    """Clear state program - always approve (no local state to clear)."""
    return Approve()


# ============================================================================
# COMPILATION FUNCTIONS
# ============================================================================

def compile_approval():
    """Compile the approval program."""
    return compileTeal(approval_program(), mode=Mode.Application, version=10)


def compile_clear():
    """Compile the clear state program."""
    return compileTeal(clear_state_program(), mode=Mode.Application, version=10)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import os

    # Write approval program
    approval_teal = compile_approval()
    with open("spinwin_approval.teal", "w") as f:
        f.write(approval_teal)
    print(f"Approval program written to spinwin_approval.teal ({len(approval_teal)} bytes)")

    # Write clear program
    clear_teal = compile_clear()
    with open("spinwin_clear.teal", "w") as f:
        f.write(clear_teal)
    print(f"Clear program written to spinwin_clear.teal ({len(clear_teal)} bytes)")

    # Print schema info
    g_ints, g_bytes = get_global_schema()
    l_ints, l_bytes = get_local_schema()
    print(f"\nGlobal schema: {g_ints} uint64, {g_bytes} bytes")
    print(f"Local schema: {l_ints} uint64, {l_bytes} bytes")
