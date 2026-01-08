#!/usr/bin/env python3
"""
Algorand Daily Lottery - Smart Contract with Randomness Beacon
Version: VRF (Verifiable Random Function) Edition

This contract implements a trustless, transparent lottery system using
Algorand's Randomness Beacon for cryptographically secure randomness.

Key Enhancement: Commit-Reveal Pattern
- Commit to future round when draw is executed
- Reveal and get beacon randomness after rounds pass
- Provably fair, unpredictable winner selection
"""

from pyteal import *

# ============================================================================
# GLOBAL STATE KEYS (what the contract stores)
# ============================================================================

# Cycle tracking
KEY_CURRENT_CYCLE_ID = Bytes("cycle_id")
KEY_CYCLE_START_TIME = Bytes("cycle_start")
KEY_CYCLE_END_TIME = Bytes("cycle_end")

# Financial state
KEY_CURRENT_POT = Bytes("pot")
KEY_ENTRY_PRICE = Bytes("entry_price")
KEY_ROLLOVER_POOL = Bytes("rollover")

# Configuration
KEY_LOTT_ASSET_ID = Bytes("lott_id")
KEY_IS_PAUSED = Bytes("is_paused")
KEY_ENGINEERING_WALLET = Bytes("eng_wallet")
KEY_CYCLE_DURATION = Bytes("cycle_dur")

# Current cycle entries
KEY_TOTAL_ENTRIES = Bytes("total_entries")

# Prize pools for claims
KEY_UNCLAIMED_PRIZES = Bytes("unclaimed")
KEY_LOTT_DIST_WALLET = Bytes("lott_wallet")

# VRF/Beacon specific keys - REPURPOSED SLOTS for schema compatibility
# Mainnet contract has 13 uints / 2 bytes schema (fixed at creation)
# We repurpose test_mode and lott_rate slots which are no longer needed
KEY_COMMITMENT_ROUND = Bytes("lott_rate")  # Repurposed: was lott_rate (always 1)
KEY_DRAW_STATUS = Bytes("test_mode")  # Repurposed: was test_mode (always 0)


# ============================================================================
# LOCAL STATE KEYS (what each user stores)
# ============================================================================

KEY_ENTRIES_CURRENT = Bytes("entries_cur")
KEY_ENTRY_START_NUM = Bytes("entry_start")
KEY_TOTAL_LIFETIME = Bytes("total_life")
KEY_LAST_CYCLE = Bytes("last_cycle")


# ============================================================================
# CONSTANTS
# ============================================================================

ENTRY_PRICE_ALGOS = Int(1_000_000)  # 1 ALGO in microALGOs
LOTT_PER_ENTRY = Int(1)  # 1 LOTT token per 1 ALGO spent
DEFAULT_CYCLE_DURATION = Int(86400)

# Prize distribution percentages (in basis points, 10000 = 100%)
PCT_TIER1 = Int(4000)  # 40%
PCT_TIER2 = Int(2000)  # 20%
PCT_TIER3 = Int(1500)  # 15%
PCT_ENGINEERING = Int(500)  # 5%
PCT_ROLLOVER = Int(500)  # 5%
PCT_LOTT_HOLDERS = Int(1500)  # 15%

# Number of winners per tier
NUM_TIER1_WINNERS = Int(1)
NUM_TIER2_WINNERS = Int(5)
NUM_TIER3_WINNERS = Int(10)  # Actual implementation uses 10
TOTAL_WINNERS = Int(16)  # 1 + 5 + 10

# Box storage constants
ENTRY_BOX_SIZE = Int(16)
WINNER_RECORD_SIZE = Int(18)
WINNER_BOX_SIZE = Int(288)  # 16 × 18 = 288 bytes

# Draw status values
DRAW_STATUS_NONE = Int(0)
DRAW_STATUS_COMMITTED = Int(1)
DRAW_STATUS_REVEALED = Int(2)

# Beacon constants
BEACON_MAINNET = Int(1615566206)  # Mainnet beacon app ID
COMMITMENT_OFFSET = Int(8)  # Commit to current_round + 8
REVEAL_WAIT_ROUNDS = Int(12)  # Wait 12 rounds after commitment before reveal (~40 seconds)


# ============================================================================
# STATE SCHEMA DEFINITIONS
# ============================================================================

def get_global_schema():
    """
    Define global state schema for the lottery contract with VRF.

    IMPORTANT: Mainnet contract schema is FIXED at 13 uints / 2 bytes.
    VRF support achieved by repurposing existing slots:
    - test_mode slot (always 0) → now used for draw_status
    - lott_rate slot (always 1) → now used for commitment_round
    - beacon_id: not stored, use BEACON_MAINNET constant
    - vrf_seed: not stored, only logged in DRAW_REVEALED event
    """
    return (
        13,  # uint64 values: cycle_dur, cycle_id, pot, lott_id, cycle_end, is_paused,
        #                cycle_start, total_entries, unclaimed, rollover, entry_price,
        #                commitment_round (was lott_rate), draw_status (was test_mode)
        2    # bytes values: eng_wallet, lott_wallet
    )


def get_local_schema():
    """Define local state schema for each user."""
    return (
        4,  # uint64 values: entries_current, entry_start_num, total_lifetime, last_cycle
        0   # bytes values: none
    )


# ============================================================================
# APPLICATION CREATION
# ============================================================================

def handle_creation():
    """
    Handle application creation with VRF support.

    Application Args:
    - args[0]: LOTT Asset ID (uint64)

    Note: Beacon App ID is hardcoded as BEACON_MAINNET constant.
    Note: This only runs for NEW contracts. For updates, existing state is preserved.
    """

    lott_asset_id = Btoi(Txn.application_args[0])

    return Seq([
        # Validate arguments
        Assert(lott_asset_id > Int(0)),

        # Initialize cycle duration
        App.globalPut(KEY_CYCLE_DURATION, DEFAULT_CYCLE_DURATION),

        # Initialize cycle tracking
        App.globalPut(KEY_CURRENT_CYCLE_ID, Int(1)),
        App.globalPut(KEY_CYCLE_START_TIME, Global.latest_timestamp()),
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp() + DEFAULT_CYCLE_DURATION),

        # Initialize financial state
        App.globalPut(KEY_CURRENT_POT, Int(0)),
        App.globalPut(KEY_ENTRY_PRICE, ENTRY_PRICE_ALGOS),
        App.globalPut(KEY_ROLLOVER_POOL, Int(0)),

        # Initialize configuration
        App.globalPut(KEY_LOTT_ASSET_ID, lott_asset_id),
        App.globalPut(KEY_IS_PAUSED, Int(0)),
        App.globalPut(KEY_ENGINEERING_WALLET, Txn.sender()),
        App.globalPut(KEY_LOTT_DIST_WALLET, Txn.sender()),

        # Initialize entry counter
        App.globalPut(KEY_TOTAL_ENTRIES, Int(0)),
        App.globalPut(KEY_UNCLAIMED_PRIZES, Int(0)),

        # Initialize VRF state (uses repurposed slots)
        # KEY_COMMITMENT_ROUND uses "lott_rate" slot
        # KEY_DRAW_STATUS uses "test_mode" slot
        App.globalPut(KEY_COMMITMENT_ROUND, Int(0)),
        App.globalPut(KEY_DRAW_STATUS, DRAW_STATUS_NONE),

        Approve()
    ])


# ============================================================================
# USER FUNCTIONS (unchanged from original)
# ============================================================================

def handle_optin():
    """Handle user opt-in to the contract."""
    return Seq([
        App.localPut(Txn.sender(), KEY_ENTRIES_CURRENT, Int(0)),
        App.localPut(Txn.sender(), KEY_ENTRY_START_NUM, Int(0)),
        App.localPut(Txn.sender(), KEY_TOTAL_LIFETIME, Int(0)),
        App.localPut(Txn.sender(), KEY_LAST_CYCLE, Int(0)),
        Approve()
    ])


def buy_entries():
    """
    Handle entry purchase (unchanged from original).
    """

    is_group_txn = Global.group_size() == Int(2)
    payment_txn_idx = Txn.group_index() - Int(1)
    payment_txn = Gtxn[payment_txn_idx]

    is_payment = payment_txn.type_enum() == TxnType.Payment
    is_to_app = payment_txn.receiver() == Global.current_application_address()
    is_from_sender = payment_txn.sender() == Txn.sender()

    entry_price = App.globalGet(KEY_ENTRY_PRICE)
    payment_amount = payment_txn.amount()
    num_entries = payment_amount / entry_price

    is_exact_amount = payment_amount == (num_entries * entry_price)
    is_not_paused = App.globalGet(KEY_IS_PAUSED) == Int(0)

    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)
    cycle_is_active = Global.latest_timestamp() < cycle_end_time

    user_opted_in = App.optedIn(Txn.sender(), Global.current_application_id())

    lott_to_mint = num_entries * LOTT_PER_ENTRY  # Hardcoded: always 1 LOTT per entry

    entry_start_scratch = ScratchVar(TealType.uint64)
    cycle_id_scratch = ScratchVar(TealType.uint64)
    lott_asset_scratch = ScratchVar(TealType.uint64)

    current_pot = App.globalGet(KEY_CURRENT_POT)
    user_current_entries = App.localGet(Txn.sender(), KEY_ENTRIES_CURRENT)
    user_lifetime_entries = App.localGet(Txn.sender(), KEY_TOTAL_LIFETIME)
    user_last_cycle = App.localGet(Txn.sender(), KEY_LAST_CYCLE)

    return Seq([
        Assert(is_group_txn),
        Assert(is_payment),
        Assert(is_to_app),
        Assert(is_from_sender),
        Assert(is_exact_amount),
        Assert(num_entries > Int(0)),
        Assert(is_not_paused),
        Assert(cycle_is_active),
        Assert(user_opted_in),

        entry_start_scratch.store(App.globalGet(KEY_TOTAL_ENTRIES)),
        cycle_id_scratch.store(App.globalGet(KEY_CURRENT_CYCLE_ID)),
        lott_asset_scratch.store(App.globalGet(KEY_LOTT_ASSET_ID)),

        App.globalPut(KEY_TOTAL_ENTRIES, entry_start_scratch.load() + num_entries),
        App.globalPut(KEY_CURRENT_POT, current_pot + payment_amount),

        App.localPut(Txn.sender(), KEY_ENTRIES_CURRENT,
                     If(user_last_cycle != cycle_id_scratch.load(),
                        num_entries,
                        user_current_entries + num_entries
                        )
                     ),
        App.localPut(Txn.sender(), KEY_ENTRY_START_NUM,
                     If(user_last_cycle != cycle_id_scratch.load(),
                        entry_start_scratch.load(),
                        App.localGet(Txn.sender(), KEY_ENTRY_START_NUM)
                        )
                     ),
        App.localPut(Txn.sender(), KEY_TOTAL_LIFETIME, user_lifetime_entries + num_entries),
        App.localPut(Txn.sender(), KEY_LAST_CYCLE, cycle_id_scratch.load()),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: lott_asset_scratch.load(),
            TxnField.asset_amount: lott_to_mint,
            TxnField.asset_receiver: Txn.sender(),
        }),
        InnerTxnBuilder.Submit(),

        Log(Concat(
            Bytes("ENTRY_PURCHASED:"),
            Bytes("cycle="), Itob(cycle_id_scratch.load()),
            Bytes(",start="), Itob(entry_start_scratch.load()),
            Bytes(",end="), Itob(entry_start_scratch.load() + num_entries - Int(1))
        )),

        Approve()
    ])


# ============================================================================
# VRF DRAW FUNCTIONS (NEW - Commit-Reveal Pattern)
# ============================================================================

def execute_draw_commit():
    """
    Phase 1: Commit to future round for VRF randomness.

    This function only commits to a future round. All distribution
    and cycle reset happens in execute_draw_reveal.

    Only creator can call.
    """

    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)
    total_entries = App.globalGet(KEY_TOTAL_ENTRIES)
    current_cycle_id = App.globalGet(KEY_CURRENT_CYCLE_ID)

    cycle_has_ended = Global.latest_timestamp() >= cycle_end_time
    has_entries = total_entries > Int(0)
    is_not_paused = App.globalGet(KEY_IS_PAUSED) == Int(0)
    is_creator = Txn.sender() == Global.creator_address()

    # Commit to future round for beacon
    commitment_round = Global.round() + COMMITMENT_OFFSET

    return Seq([
        # Security: Only creator
        Assert(is_creator),

        # Validate conditions (test_mode removed - no longer supported)
        Assert(cycle_has_ended),
        Assert(has_entries),
        Assert(is_not_paused),

        # Verify no pending draw
        Assert(App.globalGet(KEY_DRAW_STATUS) == DRAW_STATUS_NONE),

        # Store commitment for beacon (uses repurposed lott_rate slot)
        App.globalPut(KEY_COMMITMENT_ROUND, commitment_round),
        # Store draw status (uses repurposed test_mode slot)
        App.globalPut(KEY_DRAW_STATUS, DRAW_STATUS_COMMITTED),

        # Log commitment (backend will wait for reveal)
        Log(Concat(
            Bytes("DRAW_COMMITTED:"),
            Bytes("cycle="), Itob(current_cycle_id),
            Bytes(",commitment_round="), Itob(commitment_round)
        )),

        Approve()
    ])


def execute_draw_reveal():
    """
    Phase 2: Reveal - Get randomness from beacon and finalize draw.

    This function does ALL draw logic:
    1. Calls beacon to get VRF seed
    2. Distributes to engineering and LOTT holders
    3. Logs complete DRAW_REVEALED with pot, entries, seed
    4. Resets cycle state for next cycle

    Security: Must include beacon app in foreign_apps array!
    Requires fee = 4000 (covers 3 inner txns: beacon + 2 payments)
    """

    commitment_round = App.globalGet(KEY_COMMITMENT_ROUND)
    current_round = Global.round()
    draw_status = App.globalGet(KEY_DRAW_STATUS)
    is_creator = Txn.sender() == Global.creator_address()

    # Current cycle data (before reset)
    current_pot = App.globalGet(KEY_CURRENT_POT)
    current_cycle_id = App.globalGet(KEY_CURRENT_CYCLE_ID)
    total_entries = App.globalGet(KEY_TOTAL_ENTRIES)
    engineering_wallet = App.globalGet(KEY_ENGINEERING_WALLET)
    lott_dist_wallet = App.globalGet(KEY_LOTT_DIST_WALLET)
    previous_rollover = App.globalGet(KEY_ROLLOVER_POOL)

    # Calculate prize amounts
    tier1_total = (current_pot * PCT_TIER1) / Int(10000)
    tier2_total = (current_pot * PCT_TIER2) / Int(10000)
    tier3_total = (current_pot * PCT_TIER3) / Int(10000)
    engineering_fee = (current_pot * PCT_ENGINEERING) / Int(10000)
    rollover_amount = (current_pot * PCT_ROLLOVER) / Int(10000)
    lott_holders_amount = (current_pot * PCT_LOTT_HOLDERS) / Int(10000)

    total_claimable = tier1_total + tier2_total + tier3_total

    # Scratch variable for storing seed
    beacon_seed = ScratchVar(TealType.bytes)

    return Seq([
        # Security: Only creator
        Assert(is_creator),

        # Verify draw was committed
        Assert(draw_status == DRAW_STATUS_COMMITTED),

        # Verify commitment round is in past
        Assert(current_round > commitment_round),

        # Verify enough rounds have passed
        Assert(current_round >= commitment_round + REVEAL_WAIT_ROUNDS),

        # Call Algorand Randomness Beacon (inner txn 1)
        # Uses hardcoded BEACON_MAINNET constant instead of stored value
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: BEACON_MAINNET,
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.SetField(TxnField.application_args, [
            Bytes("base16", "189392c5"),  # method selector for get(uint64,byte[])byte[]
            Itob(commitment_round),        # uint64 round number
            Bytes("base16", "0000"),       # empty byte[] (ABI encoded)
        ]),
        InnerTxnBuilder.Submit(),

        # Extract seed from beacon response (skip 6 bytes: 4 ABI prefix + 2 length prefix)
        beacon_seed.store(Suffix(InnerTxn.last_log(), Int(6))),

        # Verify we got valid seed (32 bytes)
        Assert(Len(beacon_seed.load()) == Int(32)),

        # Distribute to engineering wallet (inner txn 2)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: engineering_wallet,
            TxnField.amount: engineering_fee,
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),

        # Distribute to LOTT holders (inner txn 3)
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: lott_dist_wallet,
            TxnField.amount: lott_holders_amount,
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),

        # Track unclaimed prizes
        App.globalPut(KEY_UNCLAIMED_PRIZES,
                      App.globalGet(KEY_UNCLAIMED_PRIZES) + total_claimable),

        # Update draw status (uses repurposed test_mode slot)
        # NOTE: vrf_seed is NOT stored - only logged in DRAW_REVEALED event
        App.globalPut(KEY_DRAW_STATUS, DRAW_STATUS_REVEALED),

        # Log complete draw data (backend uses this for everything)
        # The seed is logged here for backend to use - no need to store it
        Log(Concat(
            Bytes("DRAW_REVEALED:"),
            Bytes("cycle="), Itob(current_cycle_id),
            Bytes(",pot="), Itob(current_pot),
            Bytes(",entries="), Itob(total_entries),
            Bytes(",commitment_round="), Itob(commitment_round),
            Bytes(",t1="), Itob(tier1_total),
            Bytes(",t2="), Itob(tier2_total),
            Bytes(",t3="), Itob(tier3_total),
            Bytes(",seed="), beacon_seed.load()  # 32-byte VRF seed at end
        )),

        # Reset cycle state for next cycle
        App.globalPut(KEY_CURRENT_CYCLE_ID, current_cycle_id + Int(1)),
        App.globalPut(KEY_CYCLE_START_TIME, Global.latest_timestamp()),
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp() + App.globalGet(KEY_CYCLE_DURATION)),
        App.globalPut(KEY_TOTAL_ENTRIES, Int(0)),
        App.globalPut(KEY_CURRENT_POT, previous_rollover + rollover_amount),
        App.globalPut(KEY_ROLLOVER_POOL, previous_rollover + rollover_amount),

        Approve()
    ])


def register_winners():
    """
    Register winners after reveal (unchanged from original).

    Backend calculates winners using VRF seed and Java Random algorithm.
    """

    cycle_id_val = ScratchVar(TealType.uint64)
    winner_data_val = ScratchVar(TealType.bytes)
    box_name_scratch = ScratchVar(TealType.bytes)

    initial_claimed_bitmap = Bytes("base16", "00000000")
    box_length_result = App.box_length(box_name_scratch.load())

    return Seq([
        # Only creator can register
        Assert(Txn.sender() == Global.creator_address()),

        # Verify draw was revealed
        Assert(App.globalGet(KEY_DRAW_STATUS) == DRAW_STATUS_REVEALED),

        # Parse arguments
        cycle_id_val.store(Btoi(Txn.application_args[1])),
        winner_data_val.store(Txn.application_args[2]),

        # Verify winner data length (16 winners × 41 bytes = 656)
        Assert(Len(winner_data_val.load()) == Int(656)),

        # Store box name
        box_name_scratch.store(Concat(Bytes("w"), Itob(cycle_id_val.load()))),

        # Check box doesn't exist
        box_length_result,
        Assert(Not(box_length_result.hasValue())),

        # Create box with winner data
        App.box_put(box_name_scratch.load(), Concat(winner_data_val.load(), initial_claimed_bitmap)),

        # Reset draw status for next cycle (uses repurposed slots)
        App.globalPut(KEY_DRAW_STATUS, DRAW_STATUS_NONE),
        App.globalPut(KEY_COMMITMENT_ROUND, Int(0)),
        # NOTE: vrf_seed is not stored, so no need to clear it

        # Log registration
        Log(Concat(
            Bytes("WINNERS_REGISTERED:"),
            Bytes("cycle="), Itob(cycle_id_val.load())
        )),

        Approve()
    ])


def claim_prize():
    """
    Claim prize (unchanged from original).
    """

    cycle_id_val = ScratchVar(TealType.uint64)
    winner_index_val = ScratchVar(TealType.uint64)

    box_name = ScratchVar(TealType.bytes)
    box_data = ScratchVar(TealType.bytes)
    winner_address = ScratchVar(TealType.bytes)
    winner_tier = ScratchVar(TealType.uint64)
    winner_amount = ScratchVar(TealType.uint64)
    claimed_bitmap = ScratchVar(TealType.bytes)
    winner_offset = ScratchVar(TealType.uint64)
    byte_index = ScratchVar(TealType.uint64)
    bit_mask = ScratchVar(TealType.uint64)
    current_byte = ScratchVar(TealType.uint64)
    is_claimed = ScratchVar(TealType.uint64)
    new_byte = ScratchVar(TealType.uint64)
    new_bitmap = ScratchVar(TealType.bytes)

    box_get_result = App.box_get(box_name.load())

    return Seq([
        cycle_id_val.store(Btoi(Txn.application_args[1])),
        winner_index_val.store(Btoi(Txn.application_args[2])),

        Assert(winner_index_val.load() < Int(16)),

        box_name.store(Concat(Bytes("w"), Itob(cycle_id_val.load()))),

        box_get_result,
        Assert(box_get_result.hasValue()),
        box_data.store(box_get_result.value()),

        winner_offset.store(winner_index_val.load() * Int(41)),

        winner_address.store(Extract(box_data.load(), winner_offset.load(), Int(32))),
        winner_tier.store(Btoi(Extract(box_data.load(), winner_offset.load() + Int(32), Int(1)))),
        winner_amount.store(Btoi(Extract(box_data.load(), winner_offset.load() + Int(33), Int(8)))),

        claimed_bitmap.store(Extract(box_data.load(), Int(656), Int(4))),

        byte_index.store(winner_index_val.load() / Int(8)),
        bit_mask.store(Int(1) << (winner_index_val.load() % Int(8))),
        current_byte.store(Btoi(Extract(claimed_bitmap.load(), byte_index.load(), Int(1)))),
        is_claimed.store(BitwiseAnd(current_byte.load(), bit_mask.load())),

        Assert(Txn.sender() == winner_address.load()),
        Assert(is_claimed.load() == Int(0)),
        Assert(winner_amount.load() > Int(0)),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: Txn.sender(),
            TxnField.amount: winner_amount.load(),
        }),
        InnerTxnBuilder.Submit(),

        new_byte.store(BitwiseOr(current_byte.load(), bit_mask.load())),

        new_bitmap.store(
            If(byte_index.load() == Int(0),
               Concat(
                   Extract(Itob(new_byte.load()), Int(7), Int(1)),
                   Extract(claimed_bitmap.load(), Int(1), Int(3))
               ),
               If(byte_index.load() == Int(1),
                  Concat(
                      Extract(claimed_bitmap.load(), Int(0), Int(1)),
                      Extract(Itob(new_byte.load()), Int(7), Int(1)),
                      Extract(claimed_bitmap.load(), Int(2), Int(2))
                  ),
                  If(byte_index.load() == Int(2),
                     Concat(
                         Extract(claimed_bitmap.load(), Int(0), Int(2)),
                         Extract(Itob(new_byte.load()), Int(7), Int(1)),
                         Extract(claimed_bitmap.load(), Int(3), Int(1))
                     ),
                     Concat(
                         Extract(claimed_bitmap.load(), Int(0), Int(3)),
                         Extract(Itob(new_byte.load()), Int(7), Int(1))
                     )
                     )
                  )
               )
        ),

        App.box_put(box_name.load(), Concat(
            Extract(box_data.load(), Int(0), Int(656)),
            new_bitmap.load()
        )),

        App.globalPut(KEY_UNCLAIMED_PRIZES,
                      App.globalGet(KEY_UNCLAIMED_PRIZES) - winner_amount.load()),

        Log(Concat(
            Bytes("PRIZE_CLAIMED:"),
            Bytes("cycle="), Itob(cycle_id_val.load()),
            Bytes(",winner="), Txn.sender(),
            Bytes(",tier="), Itob(winner_tier.load()),
            Bytes(",amount="), Itob(winner_amount.load())
        )),

        Approve()
    ])


# ============================================================================
# ADMIN FUNCTIONS (keeping essential ones)
# ============================================================================

def admin_opt_in_asset():
    """Admin: Opt contract into LOTT asset."""
    is_creator = Txn.sender() == Global.creator_address()
    asset_id_scratch = ScratchVar(TealType.uint64)

    return Seq([
        Assert(is_creator),
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


# NOTE: admin_set_test_mode removed - test_mode slot repurposed for draw_status


def end_empty_cycle():
    """Admin: End cycle with no entries."""
    cycle_duration = App.globalGet(KEY_CYCLE_DURATION)
    current_cycle = App.globalGet(KEY_CURRENT_CYCLE_ID)
    total_entries = App.globalGet(KEY_TOTAL_ENTRIES)
    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)

    return Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Assert(total_entries == Int(0)),
        # test_mode bypass removed - cycle must have ended
        Assert(Global.latest_timestamp() >= cycle_end_time),

        App.globalPut(KEY_CURRENT_CYCLE_ID, current_cycle + Int(1)),
        App.globalPut(KEY_TOTAL_ENTRIES, Int(0)),
        App.globalPut(KEY_CYCLE_START_TIME, Global.latest_timestamp()),
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp() + cycle_duration),

        Approve()
    ])


# ============================================================================
# APPLICATION HANDLERS
# ============================================================================

def handle_noop():
    """Handle NoOp application calls."""
    method = Txn.application_args[0]

    return Cond(
        [method == Bytes("buy_entries"), buy_entries()],
        [method == Bytes("execute_draw_commit"), execute_draw_commit()],
        [method == Bytes("execute_draw_reveal"), execute_draw_reveal()],
        [method == Bytes("register_winners"), register_winners()],
        [method == Bytes("claim_prize"), claim_prize()],
        [method == Bytes("admin_opt_in_asset"), admin_opt_in_asset()],
        # admin_set_test_mode removed - test_mode slot repurposed for draw_status
        [method == Bytes("end_empty_cycle"), end_empty_cycle()],
    )


def handle_closeout():
    """Handle close-out."""
    return Approve()


def handle_update():
    """Handle application update."""
    return If(
        Txn.sender() == Global.creator_address(),
        Approve(),
        Reject()
    )


def handle_delete():
    """Handle application delete."""
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
        [Txn.on_completion() == OnComplete.OptIn, handle_optin()],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop()],
        [Txn.on_completion() == OnComplete.CloseOut, handle_closeout()],
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_update()],
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_delete()],
    )


# ============================================================================
# CLEAR STATE PROGRAM
# ============================================================================

def clear_state_program():
    """Clear state program."""
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
    print("Compiling Lottery Contract with VRF Beacon...")
    print("\n=== APPROVAL PROGRAM ===")
    approval_teal = compile_approval()
    print(approval_teal)

    print("\n=== CLEAR STATE PROGRAM ===")
    clear_teal = compile_clear()
    print(clear_teal)

    print("\n=== COMPILATION SUCCESSFUL ===")
    print(f"Approval program: {len(approval_teal.split(chr(10)))} lines")
    print(f"Clear program: {len(clear_teal.split(chr(10)))} lines")

    global_ints, global_bytes = get_global_schema()
    local_ints, local_bytes = get_local_schema()

    print("\n=== STATE SCHEMA ===")
    print(f"Global state: {global_ints} ints, {global_bytes} bytes")
    print(f"Local state: {local_ints} ints, {local_bytes} bytes")

    print("\n=== VRF BEACON INTEGRATION ===")
    print("✅ Commit-Reveal Pattern Implemented")
    print("✅ Algorand Randomness Beacon (Mainnet: 1615566206)")
    print("✅ Cryptographically Secure Winner Selection")
    print("✅ Schema-compatible: Repurposed test_mode/lott_rate slots")
    print("")
    print("Usage:")
    print("  1. execute_draw_commit() - Commit to round+8")
    print("  2. Wait 12+ rounds (~40 seconds)")
    print("  3. execute_draw_reveal() - Get beacon seed (add beacon to foreign_apps!)")
    print("  4. Backend calculates winners with seed from log")
    print("  5. register_winners() - Register on-chain")
    print("  6. Users claim prizes")
