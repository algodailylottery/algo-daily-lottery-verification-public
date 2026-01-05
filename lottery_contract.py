#!/usr/bin/env python3
"""
Algorand Daily Lottery - Smart Contract
Phase 1B Part 1: Contract Structure and Application Creation

This contract implements a trustless, transparent lottery system on Algorand.
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
KEY_LOTT_EARN_RATE = Bytes("lott_rate")
KEY_IS_PAUSED = Bytes("is_paused")
KEY_ENGINEERING_WALLET = Bytes("eng_wallet")
KEY_TEST_MODE = Bytes("test_mode")  # 1 = creator can bypass cycle end check, 0 = strict mode
KEY_CYCLE_DURATION = Bytes("cycle_dur")  # Configurable cycle duration in seconds

# Current cycle entries
KEY_TOTAL_ENTRIES = Bytes("total_entries")

# Prize pools for claims (funds held in contract)
KEY_UNCLAIMED_PRIZES = Bytes("unclaimed")  # Total unclaimed prize funds
KEY_LOTT_DIST_WALLET = Bytes("lott_wallet")  # Wallet for LOTT holder distribution


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
LOTT_PER_ENTRY = Int(1)  # 1 LOTT token per 1 ALGO spent (1:1 peg)
DEFAULT_CYCLE_DURATION = Int(86400)  # 24 hours default (86400 seconds) - configurable via admin
# MINIMUM_POT removed - no minimum pot requirement

# Prize distribution percentages (in basis points, 10000 = 100%)
PCT_TIER1 = Int(4000)  # 40%
PCT_TIER2 = Int(2000)  # 20%
PCT_TIER3 = Int(1500)  # 15%
PCT_ENGINEERING = Int(500)  # 5%
PCT_ROLLOVER = Int(500)  # 5% - rolls over to next cycle
PCT_LOTT_HOLDERS = Int(1500)  # 15%

# Number of winners per tier
NUM_TIER1_WINNERS = Int(1)
NUM_TIER2_WINNERS = Int(5)
NUM_TIER3_WINNERS = Int(20)  # Note: Backend implementation uses 10 (went live that way, kept for stability)
TOTAL_WINNERS = Int(26)  # 1 + 5 + 20 (box storage allocated, but only 16 used)

# Box storage constants
# Entry ownership box: "e_{cycle_id}_{address}" = entry_start(8) + entry_count(8) = 16 bytes
ENTRY_BOX_SIZE = Int(16)
# Winner box: "w_{cycle_id}" = 26 winners × 25 bytes each = 650 bytes
# Per winner: entry_num(8) + tier(1) + amount(8) + claimed(1) + claimer(32 optional, stored separately)
WINNER_RECORD_SIZE = Int(18)  # entry_num(8) + tier(1) + amount(8) + claimed(1)
WINNER_BOX_SIZE = Int(468)  # 26 × 18 = 468 bytes


# ============================================================================
# STATE SCHEMA DEFINITIONS
# ============================================================================

def get_global_schema():
    """
    Define global state schema for the lottery contract.

    Returns the number of uint64 and bytes values stored globally.
    """
    return (
        13,  # uint64 values: cycle_id, cycle_start, cycle_end, pot, entry_price,
             # lott_id, lott_rate, is_paused, total_entries, rollover_pool, unclaimed_prizes, test_mode, cycle_dur
        2    # bytes values: engineering_wallet (address), lott_dist_wallet (address)
    )


def get_local_schema():
    """
    Define local state schema for each user.

    Returns the number of uint64 and bytes values stored per user.
    """
    return (
        4,  # uint64 values: entries_current, entry_start_num, total_lifetime, last_cycle
        0   # bytes values: none
    )


# ============================================================================
# APPLICATION CREATION
# ============================================================================

def handle_creation():
    """
    Handle application creation.

    Initializes the lottery contract with:
    - LOTT Asset ID (from application args)
    - Engineering wallet (creator address)
    - Initial cycle configuration
    - Entry price and LOTT earn rate

    Application Args:
    - args[0]: LOTT Asset ID (uint64)
    """

    # Extract application arguments
    lott_asset_id = Btoi(Txn.application_args[0])

    return Seq([
        # Validate that LOTT Asset ID is provided
        Assert(lott_asset_id > Int(0)),

        # Initialize cycle duration (configurable)
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
        App.globalPut(KEY_LOTT_EARN_RATE, LOTT_PER_ENTRY),
        App.globalPut(KEY_IS_PAUSED, Int(0)),  # 0 = active, 1 = paused
        App.globalPut(KEY_ENGINEERING_WALLET, Txn.sender()),  # Creator is engineering wallet
        App.globalPut(KEY_LOTT_DIST_WALLET, Txn.sender()),  # LOTT holders dist wallet (defaults to creator)
        App.globalPut(KEY_TEST_MODE, Int(0)),  # 1 = test mode (creator can bypass cycle check), 0 = strict

        # Initialize entry counter
        App.globalPut(KEY_TOTAL_ENTRIES, Int(0)),

        # Initialize unclaimed prizes pool
        App.globalPut(KEY_UNCLAIMED_PRIZES, Int(0)),

        # Return success
        Approve()
    ])


# ============================================================================
# APPLICATION HANDLERS (placeholders for future implementation)
# ============================================================================

def handle_optin():
    """
    Handle user opt-in to the contract.

    Initializes user's local state.
    """
    return Seq([
        # Initialize user's local state with zeros
        App.localPut(Txn.sender(), KEY_ENTRIES_CURRENT, Int(0)),
        App.localPut(Txn.sender(), KEY_ENTRY_START_NUM, Int(0)),
        App.localPut(Txn.sender(), KEY_TOTAL_LIFETIME, Int(0)),
        App.localPut(Txn.sender(), KEY_LAST_CYCLE, Int(0)),

        Approve()
    ])


def buy_entries():
    """
    Handle entry purchase.

    Users must send a transaction group:
    1. Payment transaction: User -> Application Address (N × 1 ALGO)
    2. Application call: Call this function

    The contract will:
    - Validate payment amount
    - Assign entry numbers
    - Mint LOTT tokens (10 per entry)
    - Update global and local state

    Returns:
        Approval if successful, Reject otherwise
    """

    # Verify this is part of a group transaction
    is_group_txn = Global.group_size() == Int(2)

    # Verify payment transaction (must be first in group)
    payment_txn_idx = Txn.group_index() - Int(1)
    payment_txn = Gtxn[payment_txn_idx]

    # Validate payment transaction
    is_payment = payment_txn.type_enum() == TxnType.Payment
    is_to_app = payment_txn.receiver() == Global.current_application_address()
    is_from_sender = payment_txn.sender() == Txn.sender()

    # Calculate number of entries
    entry_price = App.globalGet(KEY_ENTRY_PRICE)
    payment_amount = payment_txn.amount()
    num_entries = payment_amount / entry_price

    # Validate payment is exact multiple of entry price
    is_exact_amount = payment_amount == (num_entries * entry_price)

    # Validate contract is not paused
    is_not_paused = App.globalGet(KEY_IS_PAUSED) == Int(0)

    # Validate cycle has not ended
    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)
    cycle_is_active = Global.latest_timestamp() < cycle_end_time

    # Validate user has opted in
    user_opted_in = App.optedIn(Txn.sender(), Global.current_application_id())

    # Calculate LOTT tokens to mint
    lott_to_mint = num_entries * App.globalGet(KEY_LOTT_EARN_RATE)

    # Use ScratchVars to store values BEFORE modifying global state
    # This is critical: PyTeal expressions are evaluated at execution time,
    # so we must snapshot values into scratch space before updating global state
    entry_start_scratch = ScratchVar(TealType.uint64)
    cycle_id_scratch = ScratchVar(TealType.uint64)
    lott_asset_scratch = ScratchVar(TealType.uint64)

    current_pot = App.globalGet(KEY_CURRENT_POT)

    # Get user's current local state
    user_current_entries = App.localGet(Txn.sender(), KEY_ENTRIES_CURRENT)
    user_lifetime_entries = App.localGet(Txn.sender(), KEY_TOTAL_LIFETIME)
    user_last_cycle = App.localGet(Txn.sender(), KEY_LAST_CYCLE)

    return Seq([
        # Validate all conditions
        Assert(is_group_txn),
        Assert(is_payment),
        Assert(is_to_app),
        Assert(is_from_sender),
        Assert(is_exact_amount),
        Assert(num_entries > Int(0)),
        Assert(is_not_paused),
        Assert(cycle_is_active),  # Cannot buy entries after cycle ends
        Assert(user_opted_in),

        # FIRST: Store current values in scratch space BEFORE any updates
        entry_start_scratch.store(App.globalGet(KEY_TOTAL_ENTRIES)),
        cycle_id_scratch.store(App.globalGet(KEY_CURRENT_CYCLE_ID)),
        lott_asset_scratch.store(App.globalGet(KEY_LOTT_ASSET_ID)),

        # Update global state
        App.globalPut(KEY_TOTAL_ENTRIES, entry_start_scratch.load() + num_entries),
        App.globalPut(KEY_CURRENT_POT, current_pot + payment_amount),

        # Update user's local state
        # If new cycle, reset current entries; otherwise add to existing
        App.localPut(Txn.sender(), KEY_ENTRIES_CURRENT,
            If(user_last_cycle != cycle_id_scratch.load(),
                num_entries,
                user_current_entries + num_entries
            )
        ),
        # If new cycle, set start to current entry_start; otherwise keep existing
        App.localPut(Txn.sender(), KEY_ENTRY_START_NUM,
            If(user_last_cycle != cycle_id_scratch.load(),
                entry_start_scratch.load(),
                App.localGet(Txn.sender(), KEY_ENTRY_START_NUM)
            )
        ),
        App.localPut(Txn.sender(), KEY_TOTAL_LIFETIME, user_lifetime_entries + num_entries),
        App.localPut(Txn.sender(), KEY_LAST_CYCLE, cycle_id_scratch.load()),

        # Mint LOTT tokens via inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: lott_asset_scratch.load(),
            TxnField.asset_amount: lott_to_mint,
            TxnField.asset_receiver: Txn.sender(),
        }),
        InnerTxnBuilder.Submit(),

        # Log event (for indexing)
        # Format: ENTRY_PURCHASED:cycle=[8 bytes],start=[8 bytes],end=[8 bytes]
        # Uses scratch vars to ensure we log the ORIGINAL values
        Log(Concat(
            Bytes("ENTRY_PURCHASED:"),
            Bytes("cycle="), Itob(cycle_id_scratch.load()),
            Bytes(",start="), Itob(entry_start_scratch.load()),
            Bytes(",end="), Itob(entry_start_scratch.load() + num_entries - Int(1))
        )),

        Approve()
    ])


def admin_opt_in_asset():
    """
    Admin function: Opt the application into the LOTT asset.

    Only the creator can call this function.
    This is required before the app can hold/transfer LOTT tokens.
    """

    is_creator = Txn.sender() == Global.creator_address()
    asset_id_scratch = ScratchVar(TealType.uint64)

    return Seq([
        # Only creator can call this
        Assert(is_creator),

        # Store asset ID in scratch space BEFORE creating inner txn
        asset_id_scratch.store(App.globalGet(KEY_LOTT_ASSET_ID)),

        # Opt-in to LOTT asset via inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id_scratch.load(),  # Load from scratch
            TxnField.asset_amount: Int(0),  # 0 amount = opt-in
            TxnField.asset_receiver: Global.current_application_address(),
        }),
        InnerTxnBuilder.Submit(),

        Approve()
    ])


def admin_end_cycle():
    """
    Admin function: Force end the current cycle (for testing).

    Only the creator can call this function.
    This allows testing execute_draw without waiting 24 hours.
    """

    is_creator = Txn.sender() == Global.creator_address()

    return Seq([
        # Only creator can call this
        Assert(is_creator),

        # Set cycle end time to now
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp()),

        Approve()
    ])


def admin_set_lott_wallet():
    """
    Admin function: Set the LOTT holders distribution wallet address.

    Only the creator can call this function.
    The new wallet address is passed as the second application argument.

    Application Args:
    - args[0]: "admin_set_lott_wallet"
    - args[1]: New wallet address (32 bytes)
    """

    is_creator = Txn.sender() == Global.creator_address()
    new_wallet = Txn.application_args[1]

    return Seq([
        # Only creator can call this
        Assert(is_creator),

        # Validate address length (32 bytes)
        Assert(Len(new_wallet) == Int(32)),

        # Update LOTT distribution wallet
        App.globalPut(KEY_LOTT_DIST_WALLET, new_wallet),

        Approve()
    ])


def admin_set_eng_wallet():
    """
    Admin function: Set the engineering/dev wallet address.

    Only the creator can call this function.
    The new wallet address is passed as the second application argument.

    Application Args:
    - args[0]: "admin_set_eng_wallet"
    - args[1]: New wallet address (32 bytes)
    """

    is_creator = Txn.sender() == Global.creator_address()
    new_wallet = Txn.application_args[1]

    return Seq([
        # Only creator can call this
        Assert(is_creator),

        # Validate address length (32 bytes)
        Assert(Len(new_wallet) == Int(32)),

        # Update engineering wallet
        App.globalPut(KEY_ENGINEERING_WALLET, new_wallet),

        Approve()
    ])


def admin_reset_cycle():
    """
    Admin function: Reset the current cycle (for testing).

    Resets cycle_start to now and cycle_end to now + cycle_duration.
    Does NOT increment cycle_id or modify pot/entries.

    Only the creator can call this function.

    Application Args:
    - args[0]: "admin_reset_cycle"
    """

    cycle_duration = App.globalGet(KEY_CYCLE_DURATION)

    return Seq([
        # Only creator can call this
        Assert(Txn.sender() == Global.creator_address()),

        # Reset cycle timing using stored cycle duration
        App.globalPut(KEY_CYCLE_START_TIME, Global.latest_timestamp()),
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp() + cycle_duration),

        Approve()
    ])


def end_empty_cycle():
    """
    Admin function: End a cycle that has no entries.

    This properly ends an empty cycle by:
    - Verifying the cycle has ended and has 0 entries
    - Incrementing the cycle_id
    - Resetting total_entries to 0
    - Keeping the pot (rollover)
    - Starting a new cycle with fresh timing

    Only the creator can call this function.

    Application Args:
    - args[0]: "end_empty_cycle"
    """

    cycle_duration = App.globalGet(KEY_CYCLE_DURATION)
    current_cycle = App.globalGet(KEY_CURRENT_CYCLE_ID)
    total_entries = App.globalGet(KEY_TOTAL_ENTRIES)
    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)
    test_mode = App.globalGet(KEY_TEST_MODE)

    return Seq([
        # Only creator can call this
        Assert(Txn.sender() == Global.creator_address()),

        # Verify cycle has no entries
        Assert(total_entries == Int(0)),

        # Verify cycle has ended (or test mode is enabled)
        Assert(
            Or(
                Global.latest_timestamp() >= cycle_end_time,
                test_mode == Int(1)
            )
        ),

        # Increment cycle_id
        App.globalPut(KEY_CURRENT_CYCLE_ID, current_cycle + Int(1)),

        # Reset entries (already 0, but be explicit)
        App.globalPut(KEY_TOTAL_ENTRIES, Int(0)),

        # Pot remains unchanged (rollover)

        # Start new cycle timing
        App.globalPut(KEY_CYCLE_START_TIME, Global.latest_timestamp()),
        App.globalPut(KEY_CYCLE_END_TIME, Global.latest_timestamp() + cycle_duration),

        Approve()
    ])


def admin_set_cycle_duration():
    """
    Admin function: Set the cycle duration.

    Only the creator can call this function.
    Minimum 5 minutes (300 seconds), maximum 7 days (604800 seconds).

    Application Args:
    - args[0]: "admin_set_cycle_duration"
    - args[1]: New duration in seconds (uint64)
    """

    new_duration = Btoi(Txn.application_args[1])

    return Seq([
        # Only creator can call this
        Assert(Txn.sender() == Global.creator_address()),

        # Validate duration is reasonable (5 minutes to 7 days)
        Assert(new_duration >= Int(300)),
        Assert(new_duration <= Int(604800)),

        # Update cycle duration
        App.globalPut(KEY_CYCLE_DURATION, new_duration),

        Approve()
    ])


def admin_set_test_mode():
    """
    Admin function: Enable or disable test mode.

    In test mode (1), creator can bypass cycle end check for draws.
    In strict mode (0), draws can only happen after cycle ends.

    IMPORTANT: Set to 0 before mainnet deployment!

    Only the creator can call this function.

    Application Args:
    - args[0]: "admin_set_test_mode"
    - args[1]: 1 (enable) or 0 (disable)
    """

    new_mode = Btoi(Txn.application_args[1])

    return Seq([
        # Only creator can call this
        Assert(Txn.sender() == Global.creator_address()),

        # Validate mode is 0 or 1
        Assert(Or(new_mode == Int(0), new_mode == Int(1))),

        # Update test mode
        App.globalPut(KEY_TEST_MODE, new_mode),

        Approve()
    ])


def execute_draw():
    """
    Execute the lottery draw - Phase 1: Calculate prizes and prepare for winner registration.

    This is a two-phase draw process:
    1. execute_draw() - Calculates prizes, pays engineering fee, logs draw event
    2. register_winners() - Backend calls with winner addresses (separate function)

    This split allows the backend to:
    - Use VRF seed from this transaction to select winners off-chain
    - Register winners with their addresses for on-chain claims

    Only the creator can call this (security: prevents seed manipulation).
    """

    # Get current state
    current_pot = App.globalGet(KEY_CURRENT_POT)
    cycle_end_time = App.globalGet(KEY_CYCLE_END_TIME)
    current_cycle_id = App.globalGet(KEY_CURRENT_CYCLE_ID)
    total_entries = App.globalGet(KEY_TOTAL_ENTRIES)
    engineering_wallet = App.globalGet(KEY_ENGINEERING_WALLET)
    lott_dist_wallet = App.globalGet(KEY_LOTT_DIST_WALLET)

    # Validate conditions
    cycle_has_ended = Global.latest_timestamp() >= cycle_end_time
    has_entries = total_entries > Int(0)
    is_not_paused = App.globalGet(KEY_IS_PAUSED) == Int(0)

    # Get existing rollover pool
    previous_rollover = App.globalGet(KEY_ROLLOVER_POOL)

    # Calculate prize amounts (in microALGOs, using basis points)
    tier1_total = (current_pot * PCT_TIER1) / Int(10000)
    tier2_total = (current_pot * PCT_TIER2) / Int(10000)
    tier3_total = (current_pot * PCT_TIER3) / Int(10000)
    engineering_fee = (current_pot * PCT_ENGINEERING) / Int(10000)
    rollover_amount = (current_pot * PCT_ROLLOVER) / Int(10000)
    lott_holders_amount = (current_pot * PCT_LOTT_HOLDERS) / Int(10000)

    # Total claimable prizes (Tier 1 + 2 + 3, excluding LOTT holder rewards for now)
    total_claimable = tier1_total + tier2_total + tier3_total

    # Generate random seed for winner selection
    # Combining multiple unpredictable on-chain values for fairness
    random_seed = Sha256(Concat(
        Itob(Global.latest_timestamp()),
        Itob(current_pot),
        Itob(total_entries),
        Itob(current_cycle_id),
        Txn.sender(),
        Itob(Global.round())
    ))

    # Security: Only creator can call execute_draw (prevents seed manipulation)
    is_creator = Txn.sender() == Global.creator_address()

    # Test mode: creator can bypass cycle end check
    test_mode_enabled = App.globalGet(KEY_TEST_MODE) == Int(1)
    can_bypass_cycle_check = And(is_creator, test_mode_enabled)

    return Seq([
        # Security: Only creator can call (prevents seed manipulation attack)
        Assert(is_creator),

        # Validate all conditions
        # Cycle must have ended, OR creator can bypass in test mode
        Assert(Or(cycle_has_ended, can_bypass_cycle_check)),
        Assert(has_entries),
        Assert(is_not_paused),

        # Distribute engineering fee immediately
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: engineering_wallet,
            TxnField.amount: engineering_fee,
        }),
        InnerTxnBuilder.Submit(),

        # Send LOTT holders share to distribution wallet
        # Backend will distribute to token holders from this wallet later
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: lott_dist_wallet,
            TxnField.amount: lott_holders_amount,
        }),
        InnerTxnBuilder.Submit(),

        # Track unclaimed prizes (funds stay in contract for claims)
        App.globalPut(KEY_UNCLAIMED_PRIZES,
            App.globalGet(KEY_UNCLAIMED_PRIZES) + total_claimable),

        # Log draw execution event with prize breakdown
        # Note: seed is 32 bytes (VRF output), not 8 bytes like other uint64 fields
        Log(Concat(
            Bytes("DRAW_EXECUTED:"),
            Bytes("cycle="), Itob(current_cycle_id),
            Bytes(",pot="), Itob(current_pot),
            Bytes(",entries="), Itob(total_entries),
            Bytes(",seed="), random_seed,  # 32-byte VRF seed
            Bytes(",t1="), Itob(tier1_total),
            Bytes(",t2="), Itob(tier2_total),
            Bytes(",t3="), Itob(tier3_total),
            Bytes(",lott="), Itob(lott_holders_amount)
        )),

        # Reset cycle state (using stored cycle duration)
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
    Register winners for a completed draw cycle - enables claim-based prize distribution.

    Called by backend after execute_draw() to register winner addresses in box storage.

    Application Args:
    - args[0]: "register_winners"
    - args[1]: cycle_id (uint64)
    - args[2]: winner_data (bytes) - packed winner records

    Winner data format (per winner, 41 bytes):
    - address: 32 bytes
    - tier: 1 byte (1, 2, or 3)
    - amount: 8 bytes (microALGOs)

    Total: 26 winners × 41 bytes = 1066 bytes

    Box name format: "w" + cycle_id (8 bytes) = 9 byte key
    Box stores: winner_data + claimed_bitmap (4 bytes) = 1070 bytes

    Only creator can call this function.
    """

    cycle_id_val = ScratchVar(TealType.uint64)
    winner_data_val = ScratchVar(TealType.bytes)
    box_name_scratch = ScratchVar(TealType.bytes)

    # Claimed bitmap: 4 bytes = 32 bits, we use 26 for winners
    # All zeros initially (no one has claimed)
    initial_claimed_bitmap = Bytes("base16", "00000000")

    # MaybeValue for box length check
    box_length_result = App.box_length(box_name_scratch.load())

    return Seq([
        # Only creator can register winners
        Assert(Txn.sender() == Global.creator_address()),

        # Parse arguments
        cycle_id_val.store(Btoi(Txn.application_args[1])),
        winner_data_val.store(Txn.application_args[2]),

        # Verify winner data length (26 winners × 41 bytes = 1066)
        Assert(Len(winner_data_val.load()) == Int(1066)),

        # Store box name
        box_name_scratch.store(Concat(Bytes("w"), Itob(cycle_id_val.load()))),

        # Check if box already exists (can't re-register)
        # box_length returns MaybeValue - if hasValue() is true, box exists
        box_length_result,
        Assert(Not(box_length_result.hasValue())),

        # Create box and store winner data + claimed bitmap
        App.box_put(box_name_scratch.load(), Concat(winner_data_val.load(), initial_claimed_bitmap)),

        # Log registration
        Log(Concat(
            Bytes("WINNERS_REGISTERED:"),
            Bytes("cycle="), Itob(cycle_id_val.load())
        )),

        Approve()
    ])


def claim_prize():
    """
    Claim a prize from a completed lottery draw.

    Application Args:
    - args[0]: "claim_prize"
    - args[1]: cycle_id (uint64)
    - args[2]: winner_index (uint64) - index in winner list (0-25)

    The contract will:
    1. Read winner data from box storage
    2. Verify caller's address matches winner at given index
    3. Verify prize not already claimed
    4. Send prize payment to caller
    5. Mark as claimed in bitmap

    Users pay their own transaction fee for claiming.
    """

    cycle_id_val = ScratchVar(TealType.uint64)
    winner_index_val = ScratchVar(TealType.uint64)

    # Scratch variables
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

    # MaybeValue for box get
    box_get_result = App.box_get(box_name.load())

    return Seq([
        # Parse arguments
        cycle_id_val.store(Btoi(Txn.application_args[1])),
        winner_index_val.store(Btoi(Txn.application_args[2])),

        # Verify winner_index is valid (0-25)
        Assert(winner_index_val.load() < Int(26)),

        # Build box name: "w" + cycle_id
        box_name.store(Concat(Bytes("w"), Itob(cycle_id_val.load()))),

        # Read box data (execute MaybeValue first, then get value)
        box_get_result,
        Assert(box_get_result.hasValue()),  # Box must exist
        box_data.store(box_get_result.value()),

        # Calculate offset for this winner (41 bytes per winner)
        winner_offset.store(winner_index_val.load() * Int(41)),

        # Extract winner address (32 bytes starting at offset)
        winner_address.store(Extract(box_data.load(), winner_offset.load(), Int(32))),

        # Extract tier (1 byte at offset + 32)
        winner_tier.store(Btoi(Extract(box_data.load(), winner_offset.load() + Int(32), Int(1)))),

        # Extract amount (8 bytes at offset + 33)
        winner_amount.store(Btoi(Extract(box_data.load(), winner_offset.load() + Int(33), Int(8)))),

        # Extract claimed bitmap (last 4 bytes of box, at position 1066)
        claimed_bitmap.store(Extract(box_data.load(), Int(1066), Int(4))),

        # Check if already claimed
        byte_index.store(winner_index_val.load() / Int(8)),
        bit_mask.store(Int(1) << (winner_index_val.load() % Int(8))),
        current_byte.store(Btoi(Extract(claimed_bitmap.load(), byte_index.load(), Int(1)))),
        is_claimed.store(BitwiseAnd(current_byte.load(), bit_mask.load())),

        # Verify caller is the winner
        Assert(Txn.sender() == winner_address.load()),

        # Verify not already claimed
        Assert(is_claimed.load() == Int(0)),

        # Verify prize amount is valid
        Assert(winner_amount.load() > Int(0)),

        # Send prize payment to caller
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: Txn.sender(),
            TxnField.amount: winner_amount.load(),
        }),
        InnerTxnBuilder.Submit(),

        # Update claimed bitmap - set the bit for this winner
        new_byte.store(BitwiseOr(current_byte.load(), bit_mask.load())),

        # Reconstruct bitmap with updated byte
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

        # Update box with new bitmap
        App.box_put(box_name.load(), Concat(
            Extract(box_data.load(), Int(0), Int(1066)),  # Winner data unchanged
            new_bitmap.load()  # Updated bitmap
        )),

        # Update unclaimed prizes tracker
        App.globalPut(KEY_UNCLAIMED_PRIZES,
            App.globalGet(KEY_UNCLAIMED_PRIZES) - winner_amount.load()),

        # Log claim
        Log(Concat(
            Bytes("PRIZE_CLAIMED:"),
            Bytes("cycle="), Itob(cycle_id_val.load()),
            Bytes(",winner="), Txn.sender(),
            Bytes(",tier="), Itob(winner_tier.load()),
            Bytes(",amount="), Itob(winner_amount.load())
        )),

        Approve()
    ])


def handle_noop():
    """
    Handle NoOp application calls.

    Routes to appropriate function based on application arguments.
    """

    # Check if first argument exists and determine which function to call
    method = Txn.application_args[0]

    return Cond(
        [method == Bytes("buy_entries"), buy_entries()],
        [method == Bytes("admin_opt_in_asset"), admin_opt_in_asset()],
        [method == Bytes("admin_end_cycle"), admin_end_cycle()],
        [method == Bytes("admin_set_lott_wallet"), admin_set_lott_wallet()],
        [method == Bytes("admin_set_eng_wallet"), admin_set_eng_wallet()],
        [method == Bytes("admin_reset_cycle"), admin_reset_cycle()],
        [method == Bytes("admin_set_cycle_duration"), admin_set_cycle_duration()],
        [method == Bytes("admin_set_test_mode"), admin_set_test_mode()],
        [method == Bytes("execute_draw"), execute_draw()],
        [method == Bytes("register_winners"), register_winners()],
        [method == Bytes("claim_prize"), claim_prize()],
        [method == Bytes("end_empty_cycle"), end_empty_cycle()],
    )


def handle_closeout():
    """
    Handle close-out (user wants to remove local state).
    """
    return Approve()


def handle_update():
    """
    Handle application update.

    Only creator can update.
    """
    return If(
        Txn.sender() == Global.creator_address(),
        Approve(),
        Reject()
    )


def handle_delete():
    return If(
        Txn.sender() == Global.creator_address(),
        Approve(),
        Reject()
    )


# ============================================================================
# MAIN APPROVAL PROGRAM
# ============================================================================

def approval_program():
    """
    Main approval program for the lottery contract.

    Routes transactions based on OnComplete action.
    """

    return Cond(
        # Application creation
        [Txn.application_id() == Int(0), handle_creation()],

        # User opt-in
        [Txn.on_completion() == OnComplete.OptIn, handle_optin()],

        # NoOp (normal application calls)
        [Txn.on_completion() == OnComplete.NoOp, handle_noop()],

        # Close-out
        [Txn.on_completion() == OnComplete.CloseOut, handle_closeout()],

        # Update application
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_update()],

        # Delete application
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_delete()],
    )


# ============================================================================
# CLEAR STATE PROGRAM
# ============================================================================

def clear_state_program():
    """
    Clear state program.

    Always succeeds - allows users to clear their local state at any time.
    """
    return Approve()


# ============================================================================
# COMPILATION FUNCTIONS
# ============================================================================

def compile_approval():
    """Compile the approval program."""
    return compileTeal(approval_program(), mode=Mode.Application, version=8)


def compile_clear():
    """Compile the clear state program."""
    return compileTeal(clear_state_program(), mode=Mode.Application, version=8)


# ============================================================================
# MAIN (for testing compilation)
# ============================================================================

if __name__ == "__main__":
    print("Compiling Lottery Contract...")
    print("\n=== APPROVAL PROGRAM ===")
    approval_teal = compile_approval()
    print(approval_teal)

    print("\n=== CLEAR STATE PROGRAM ===")
    clear_teal = compile_clear()
    print(clear_teal)

    print("\n=== COMPILATION SUCCESSFUL ===")
    print(f"Approval program: {len(approval_teal.split(chr(10)))} lines")
    print(f"Clear program: {len(clear_teal.split(chr(10)))} lines")

    # Display state schema
    global_ints, global_bytes = get_global_schema()
    local_ints, local_bytes = get_local_schema()

    print("\n=== STATE SCHEMA ===")
    print(f"Global state: {global_ints} ints, {global_bytes} bytes")
    print(f"Local state: {local_ints} ints, {local_bytes} bytes")
