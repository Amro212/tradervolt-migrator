"""
Plan Command

Parses source data files, loads discovery data, and generates a comprehensive
migration plan with side-by-side comparison of MT5 source vs TraderVolt target.

Migration Order (per requirement):
1. Symbol Groups
2. Symbols
3. Traders (Accounts) - Clients/Users auto-generated
4. Orders
5. Deals
6. Positions
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.parsers.htm_parser import (
    parse_clients, parse_accounts, parse_orders, parse_positions,
    get_unique_groups_from_accounts, get_unique_symbols
)
from src.parsers.json_parser import parse_symbols_json, get_symbol_groups
from src.models.entities import (
    SymbolsGroup, Symbol, TradersGroup, Trader, Order, Position,
    MigrationPlan
)

logger = logging.getLogger(__name__)

# TraderVolt Group Mappings (loaded from discovery)
TRADERVOLT_TRADER_GROUPS = {
    'DEMO': 'd3c9f1e8-0fd5-4f42-95e2-1bb34c829ba5',
    'REAL': 'cfd69018-604d-4a94-a46d-1bb22e72a6e0',
    'ROOT': '9c6b651e-e6fc-4146-a850-6518dd5d2357',
}


def load_discovery_data(discovery_dir: Path) -> Dict[str, Any]:
    """Load all discovery data from JSON files."""
    discovery = {
        'symbols_groups': [],
        'symbols': [],
        'traders_groups': [],
        'traders': [],
        'orders': [],
        'deals': [],
        'positions': [],
    }
    
    files = {
        'symbols_groups': 'symbols-groups.json',
        'symbols': 'symbols.json',
        'traders_groups': 'traders-groups.json',
        'traders': 'traders.json',
        'orders': 'orders.json',
        'deals': 'deals.json',
        'positions': 'positions.json',
    }
    
    for key, filename in files.items():
        filepath = discovery_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                data = json.load(f)
                discovery[key] = data.get('data', [])
    
    return discovery


def build_lookup_tables(discovery: Dict[str, Any]) -> Dict[str, Dict]:
    """Build name/id lookup tables from discovery data."""
    lookups = {
        'symbol_name_to_id': {},
        'symbol_group_name_to_id': {},
        'trader_email_to_id': {},
        'trader_login_to_id': {},
        'traders_group_name_to_id': {},
    }
    
    # Symbol name -> ID
    for sym in discovery.get('symbols', []):
        name = sym.get('name', '')
        if name:
            lookups['symbol_name_to_id'][name.upper()] = sym.get('id')
    
    # Symbol group name -> ID
    for sg in discovery.get('symbols_groups', []):
        name = sg.get('name', '')
        if name:
            lookups['symbol_group_name_to_id'][name.upper()] = sg.get('id')
    
    # Trader email -> ID
    for t in discovery.get('traders', []):
        email = t.get('email', '')
        if email:
            lookups['trader_email_to_id'][email.lower()] = t.get('id')
    
    # Traders group name -> ID
    for tg in discovery.get('traders_groups', []):
        name = tg.get('name', '')
        if name:
            lookups['traders_group_name_to_id'][name.upper()] = tg.get('id')
    
    return lookups


def map_mt5_group_to_tradervolt(mt5_group: str, lookups: Dict) -> Tuple[str, str]:
    """
    Map MT5 group path to TraderVolt group ID and trade type.
    
    Returns: (tradersGroupId, tradeType)
    """
    group_lower = mt5_group.lower()
    
    if group_lower.startswith('demo'):
        return (
            lookups['traders_group_name_to_id'].get('DEMO', TRADERVOLT_TRADER_GROUPS['DEMO']),
            'Demo'
        )
    elif group_lower.startswith('real'):
        return (
            lookups['traders_group_name_to_id'].get('REAL', TRADERVOLT_TRADER_GROUPS['REAL']),
            'Real'
        )
    elif group_lower.startswith('managers') or group_lower in ['preliminary', 'other']:
        # Map managers and other accounts to ROOT group
        return (
            lookups['traders_group_name_to_id'].get('ROOT', TRADERVOLT_TRADER_GROUPS['ROOT']),
            'Demo'  # Use Demo as tradeType (can be adjusted if needed)
        )
    else:
        # Default to ROOT for any other unknown groups
        return (
            lookups['traders_group_name_to_id'].get('ROOT', TRADERVOLT_TRADER_GROUPS['ROOT']),
            'Demo'
        )


def parse_leverage(leverage_val) -> int:
    """Parse MT5 leverage string like '1 : 100' to integer 100."""
    if leverage_val is None:
        return 100
    
    # If already an integer, return it
    if isinstance(leverage_val, int):
        return leverage_val
    
    # Convert to string for parsing
    leverage_str = str(leverage_val)
    
    if ':' in leverage_str:
        parts = leverage_str.split(':')
        if len(parts) == 2:
            try:
                return int(parts[1].strip())
            except ValueError:
                return 100
    
    try:
        return int(leverage_str)
    except ValueError:
        return 100


def map_symbol_group_name(mt5_path: str, lookups: Dict) -> Optional[str]:
    """Map MT5 symbol path to TraderVolt symbols group ID."""
    if not mt5_path:
        return None
    
    # Extract first part of path (e.g., 'Forex' from 'Forex\\Majors')
    parts = mt5_path.split('\\')
    if parts:
        group_name = parts[0].upper()
        return lookups['symbol_group_name_to_id'].get(group_name)
    
    return None


def run_plan(args) -> int:
    """
    Execute the plan command.
    
    Parses all source data files, loads discovery data, compares source vs target,
    and generates a comprehensive migration plan.
    """
    print("\n" + "=" * 80)
    print("MIGRATION PLAN GENERATION")
    print("=" * 80)
    
    # Source directory
    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}")
        return 1
    
    # Discovery directory
    discovery_dir = Path("out/discovery")
    if not discovery_dir.exists():
        print(f"[WARNING] Discovery data not found. Run 'python migrate.py discover' first.")
        print(f"   Proceeding without comparison data...")
        discovery = {k: [] for k in ['symbols_groups', 'symbols', 'traders_groups', 'traders', 'orders', 'deals', 'positions']}
    else:
        print(f"\n[INFO] Loading discovery data from: {discovery_dir}")
        discovery = load_discovery_data(discovery_dir)
    
    # Build lookup tables
    lookups = build_lookup_tables(discovery)
    
    print(f"\n[INFO] Source directory: {source_dir}")
    
    # =========================================================================
    # PHASE 1: Parse Source Files
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 1: Parsing MT5 Source Files")
    print("-" * 80)
    
    clients_data: List[Dict] = []
    accounts_data: List[Dict] = []
    orders_data: List[Dict] = []
    positions_data: List[Dict] = []
    symbols_data: List[Dict] = []
    
    # Parse each file
    clients_file = source_dir / "Clients.htm"
    if clients_file.exists():
        clients_data = parse_clients(str(clients_file))
        print(f"  [OK] Clients.htm: {len(clients_data)} clients")
    
    accounts_file = source_dir / "Accounts.htm"
    if accounts_file.exists():
        accounts_data = parse_accounts(str(accounts_file))
        print(f"  [OK] Accounts.htm: {len(accounts_data)} accounts")
    
    orders_file = source_dir / "Orders.htm"
    if orders_file.exists():
        orders_data = parse_orders(str(orders_file))
        print(f"  [OK] Orders.htm: {len(orders_data)} orders")
    
    positions_file = source_dir / "Positions.htm"
    if positions_file.exists():
        positions_data = parse_positions(str(positions_file))
        print(f"  [OK] Positions.htm: {len(positions_data)} positions")
    
    symbols_file = source_dir / "symbols.json"
    if symbols_file.exists():
        symbols_data = parse_symbols_json(str(symbols_file))
        print(f"  [OK] symbols.json: {len(symbols_data)} symbols")
    
    # =========================================================================
    # PHASE 2: Analyze & Classify Accounts
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 2: Analyzing MT5 Accounts")
    print("-" * 80)
    
    # Categorize accounts by group type
    demo_accounts = [a for a in accounts_data if a.get('group', '').lower().startswith('demo')]
    real_accounts = [a for a in accounts_data if a.get('group', '').lower().startswith('real')]
    manager_accounts = [a for a in accounts_data if a.get('group', '').lower().startswith('managers')]
    other_accounts = [a for a in accounts_data if a not in demo_accounts + real_accounts + manager_accounts]
    
    # Include ALL accounts for migration
    all_accounts = accounts_data
    
    print(f"  demo\\* accounts: {len(demo_accounts)} -> DEMO group")
    print(f"  real\\* accounts: {len(real_accounts)} -> REAL group")
    print(f"  managers\\* accounts: {len(manager_accounts)} -> ROOT group")
    print(f"  other accounts: {len(other_accounts)} -> ROOT group")
    print(f"\n  [SUMMARY] All accounts to migrate: {len(all_accounts)}")
    
    # Check email availability
    accounts_with_email = [a for a in all_accounts if a.get('email', '').strip()]
    accounts_without_email = [a for a in all_accounts if not a.get('email', '').strip()]
    
    print(f"     - With email: {len(accounts_with_email)}")
    print(f"     - Without email: {len(accounts_without_email)}")
    
    if accounts_without_email:
        print(f"\n  [WARNING] {len(accounts_without_email)} accounts missing email (will attempt migration anyway)")
    
    # =========================================================================
    # PHASE 3: Build Migration Plan (Following Required Order)
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 3: Building Migration Plan")
    print("-" * 80)
    print("\n  Migration Order:")
    print("  1. Symbol Groups")
    print("  2. Symbols")
    print("  3. Traders (from Accounts)")
    print("  4. Orders")
    print("  5. Deals")
    print("  6. Positions")
    
    plan = MigrationPlan(
        timestamp=datetime.now().isoformat(),
        test_mode=False,
        test_prefix="",
    )
    
    # Track what exists vs what's new
    plan_stats = {
        'symbols_groups': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
        'symbols': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
        'traders': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
        'orders': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
        'deals': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
        'positions': {'total': 0, 'existing': 0, 'new': 0, 'skipped': 0},
    }
    
    # -------------------------------------------------------------------------
    # 1. SYMBOL GROUPS
    # -------------------------------------------------------------------------
    print("\n  [1/6] Processing Symbol Groups...")
    
    mt5_symbol_groups: Set[str] = set()
    for sym in symbols_data:
        path = sym.get('path', '')
        if path and '\\' in path:
            parts = path.split('\\')
            if parts[0]:
                mt5_symbol_groups.add(parts[0])
        elif path:
            mt5_symbol_groups.add(path)
    
    # Also get from symbol group parser
    for group in get_symbol_groups(symbols_data):
        mt5_symbol_groups.add(group)
    
    existing_sg_names = set(lookups['symbol_group_name_to_id'].keys())
    
    for group_name in sorted(mt5_symbol_groups):
        plan_stats['symbols_groups']['total'] += 1
        
        if group_name.upper() in existing_sg_names:
            plan_stats['symbols_groups']['existing'] += 1
            # Skip - already exists
        else:
            plan_stats['symbols_groups']['new'] += 1
            plan.symbols_groups.append(SymbolsGroup(
                name=group_name,
                description=f"Migrated from MT5: {group_name}"
            ))
    
    print(f"       MT5 groups: {len(mt5_symbol_groups)}, TraderVolt existing: {len(discovery.get('symbols_groups', []))}")
    print(f"       -> New to create: {plan_stats['symbols_groups']['new']}, Skip (existing): {plan_stats['symbols_groups']['existing']}")
    
    # -------------------------------------------------------------------------
    # 2. SYMBOLS
    # -------------------------------------------------------------------------
    print("\n  [2/6] Processing Symbols...")
    
    existing_symbol_names = set(lookups['symbol_name_to_id'].keys())
    
    for sym in symbols_data:
        name = sym.get('name', '')
        if not name:
            continue
        
        plan_stats['symbols']['total'] += 1
        
        if name.upper() in existing_symbol_names:
            plan_stats['symbols']['existing'] += 1
            # Skip - already exists
        else:
            plan_stats['symbols']['new'] += 1
            
            # Map symbol group
            symbol_group_id = map_symbol_group_name(sym.get('path', ''), lookups)
            
            plan.symbols.append(Symbol(
                name=name,
                description=sym.get('description', ''),
                symbolsGroupId=symbol_group_id,
                baseCurrency=sym.get('base_currency', 'USD'),
                quoteCurrency=sym.get('quote_currency', 'USD'),
                digits=sym.get('digits', 5),
                contractSize=sym.get('contract_size', 100000),
                tickSize=sym.get('tick_size', 0.00001),
                tickValue=sym.get('tick_value', 1.0),
                minVolume=sym.get('volume_min', 0.01),
                maxVolume=sym.get('volume_max', 1000),
                volumeStep=sym.get('volume_step', 0.01),
                spread=sym.get('spread', 0),
                spreadBalance=sym.get('spread_balance', 0),
                spreadFixed=sym.get('spread_fixed', False),
                swapLong=sym.get('swap_long', 0.0),
                swapShort=sym.get('swap_short', 0.0),
                swapMode=sym.get('swap_mode', 1),
            ))
    
    print(f"       MT5 symbols: {len(symbols_data)}, TraderVolt existing: {len(discovery.get('symbols', []))}")
    print(f"       -> New to create: {plan_stats['symbols']['new']}, Skip (existing): {plan_stats['symbols']['existing']}")
    
    # -------------------------------------------------------------------------
    # 3. TRADERS (from all accounts)
    # -------------------------------------------------------------------------
    print("\n  [3/6] Processing Traders (from Accounts)...")
    
    # Build login -> trader mapping for later use (orders/positions)
    login_to_planned_trader: Dict[int, Dict] = {}
    
    for acc in all_accounts:
        login = acc.get('login', 0)
        if not login:
            continue
        
        plan_stats['traders']['total'] += 1
        
        email = acc.get('email', '').strip()
        
        # Check if trader already exists by email
        if email and email.lower() in lookups['trader_email_to_id']:
            plan_stats['traders']['existing'] += 1
            # Store existing trader ID for reference
            login_to_planned_trader[login] = {
                'id': lookups['trader_email_to_id'][email.lower()],
                'exists': True,
                'email': email,
            }
        else:
            plan_stats['traders']['new'] += 1
            
            # Map MT5 group to TraderVolt group
            mt5_group = acc.get('group', '')
            traders_group_id, trade_type = map_mt5_group_to_tradervolt(mt5_group, lookups)
            
            # Parse leverage
            leverage = parse_leverage(acc.get('leverage', '100'))
            
            trader = Trader(
                login=login,
                firstName=acc.get('name', f'Trader'),
                lastName=acc.get('last_name', str(login)),
                email=email if email else f"trader_{login}@migration.local",
                phone=acc.get('phone', ''),
                group=mt5_group,
                tradersGroupId=traders_group_id,
                tradeType=trade_type,
                balance=acc.get('balance', 0.0),
                credit=acc.get('credit', 0.0),
                leverage=leverage,
                country=acc.get('country', ''),
            )
            plan.traders.append(trader)
            
            login_to_planned_trader[login] = {
                'id': None,  # Will be assigned after creation
                'exists': False,
                'email': email,
                'trader': trader,
            }
    
    print(f"       All accounts: {len(all_accounts)}")
    print(f"       -> New to create: {plan_stats['traders']['new']}, Existing (by email): {plan_stats['traders']['existing']}")
    
    if accounts_without_email:
        print(f"       [WARNING] Accounts without email will use placeholder: trader_<login>@migration.local")
    
    # -------------------------------------------------------------------------
    # 4. ORDERS
    # -------------------------------------------------------------------------
    print("\n  [4/6] Processing Orders...")
    
    for ord in orders_data:
        order_id = ord.get('order_id', 0)
        if not order_id:
            continue
        
        plan_stats['orders']['total'] += 1
        plan_stats['orders']['new'] += 1
        
        # Resolve trader ID from login
        login = ord.get('login', 0)
        trader_info = login_to_planned_trader.get(login, {})
        trader_id = trader_info.get('id')  # May be None for new traders
        
        # Resolve symbol ID
        symbol_name = ord.get('symbol', '').upper()
        symbol_id = lookups['symbol_name_to_id'].get(symbol_name)
        
        plan.orders.append(Order(
            transactionId=order_id,
            login=login,
            traderId=trader_id,  # Will be resolved during apply
            symbol=ord.get('symbol', ''),
            symbolId=symbol_id,
            orderType=ord.get('order_type', 0),
            state=ord.get('state', 1),
            volume=ord.get('volume', 0.0),
            volumeCurrent=ord.get('volume_current', 0.0),
            price=ord.get('price', 0.0),
            priceCurrent=ord.get('price_current', 0.0),
            stopLoss=ord.get('stop_loss', 0.0),
            takeProfit=ord.get('take_profit', 0.0),
            timeSetup=ord.get('time_setup'),
            timeExpiration=ord.get('time_expiration'),
            timeDone=ord.get('time_done'),
            comment=ord.get('comment', ''),
        ))
    
    print(f"       MT5 orders: {len(orders_data)}")
    print(f"       -> To create: {plan_stats['orders']['new']}")
    
    # -------------------------------------------------------------------------
    # 5. DEALS (placeholder - may come from order history)
    # -------------------------------------------------------------------------
    print("\n  [5/6] Processing Deals...")
    print(f"       Deals: Will be created from order execution history")
    print(f"       -> TraderVolt existing deals: {len(discovery.get('deals', []))}")
    
    # -------------------------------------------------------------------------
    # 6. POSITIONS
    # -------------------------------------------------------------------------
    print("\n  [6/6] Processing Positions...")
    
    for pos in positions_data:
        position_id = pos.get('position_id', 0)
        if not position_id:
            continue
        
        plan_stats['positions']['total'] += 1
        plan_stats['positions']['new'] += 1
        
        # Resolve trader ID from login
        login = pos.get('login', 0)
        trader_info = login_to_planned_trader.get(login, {})
        trader_id = trader_info.get('id')
        
        # Resolve symbol ID
        symbol_name = pos.get('symbol', '').upper()
        symbol_id = lookups['symbol_name_to_id'].get(symbol_name)
        
        plan.positions.append(Position(
            transactionId=position_id,
            login=login,
            traderId=trader_id,
            symbol=pos.get('symbol', ''),
            symbolId=symbol_id,
            positionType=pos.get('position_type', 0),
            volume=pos.get('volume', 0.0),
            priceOpen=pos.get('price_open', 0.0),
            priceCurrent=pos.get('price_current', 0.0),
            priceStopLoss=pos.get('stop_loss', 0.0),
            priceTakeProfit=pos.get('take_profit', 0.0),
            swap=pos.get('swap', 0.0),
            profit=pos.get('profit', 0.0),
            timeOpen=pos.get('time_open'),
            comment=pos.get('comment', ''),
        ))
    
    print(f"       MT5 positions: {len(positions_data)}")
    print(f"       -> To create: {plan_stats['positions']['new']}")
    
    # =========================================================================
    # PHASE 4: Save Migration Plan
    # =========================================================================
    output_dir = Path("out")
    output_dir.mkdir(exist_ok=True)
    
    plan_file = output_dir / "migration_plan.json"
    
    # Build comprehensive plan data
    plan_data = {
        'timestamp': plan.timestamp,
        'generated_at': datetime.now().isoformat(),
        'migration_order': [
            '1. Symbol Groups',
            '2. Symbols', 
            '3. Traders (Accounts)',
            '4. Orders',
            '5. Deals',
            '6. Positions',
        ],
        'comparison': {
            'symbol_groups': {
                'mt5_source': len(mt5_symbol_groups),
                'tradervolt_existing': len(discovery.get('symbols_groups', [])),
                'to_create': plan_stats['symbols_groups']['new'],
                'to_skip': plan_stats['symbols_groups']['existing'],
            },
            'symbols': {
                'mt5_source': len(symbols_data),
                'tradervolt_existing': len(discovery.get('symbols', [])),
                'to_create': plan_stats['symbols']['new'],
                'to_skip': plan_stats['symbols']['existing'],
            },
            'traders': {
                'mt5_total_accounts': len(accounts_data),
                'mt5_all_accounts': len(all_accounts),
                'mt5_demo': len(demo_accounts),
                'mt5_real': len(real_accounts),
                'mt5_skipped_managers': len(manager_accounts),
                'mt5_skipped_other': len(other_accounts),
                'tradervolt_existing': len(discovery.get('traders', [])),
                'to_create': plan_stats['traders']['new'],
                'already_exist': plan_stats['traders']['existing'],
            },
            'orders': {
                'mt5_source': len(orders_data),
                'tradervolt_existing': len(discovery.get('orders', [])),
                'to_create': plan_stats['orders']['new'],
            },
            'deals': {
                'tradervolt_existing': len(discovery.get('deals', [])),
                'note': 'Deals created from order execution',
            },
            'positions': {
                'mt5_source': len(positions_data),
                'tradervolt_existing': len(discovery.get('positions', [])),
                'to_create': plan_stats['positions']['new'],
            },
        },
        'group_mapping': {
            'mt5_demo_pattern': 'demo\\*',
            'tradervolt_demo_id': lookups['traders_group_name_to_id'].get('DEMO', TRADERVOLT_TRADER_GROUPS['DEMO']),
            'mt5_real_pattern': 'real\\*',
            'tradervolt_real_id': lookups['traders_group_name_to_id'].get('REAL', TRADERVOLT_TRADER_GROUPS['REAL']),
        },
        'warnings': [],
        'entities': {
            'symbols_groups': [sg.to_api_payload() for sg in plan.symbols_groups],
            'symbols': [s.to_api_payload() for s in plan.symbols],
            'traders': [t.to_api_payload() for t in plan.traders],
            'orders': [o.to_api_payload() for o in plan.orders],
            'positions': [p.to_api_payload() for p in plan.positions],
        }
    }
    
    # Add warnings
    if accounts_without_email:
        plan_data['warnings'].append(f"{len(accounts_without_email)} accounts without email - using placeholder emails")
    
    # Check for unresolved symbols in orders/positions
    unresolved_symbols = set()
    for o in plan.orders:
        if not o.symbolId and o.symbol:
            unresolved_symbols.add(o.symbol)
    for p in plan.positions:
        if not p.symbolId and p.symbol:
            unresolved_symbols.add(p.symbol)
    
    if unresolved_symbols:
        plan_data['warnings'].append(f"{len(unresolved_symbols)} symbols referenced in orders/positions not found in TraderVolt: {list(unresolved_symbols)[:10]}")
    
    with open(plan_file, 'w') as f:
        json.dump(plan_data, f, indent=2, default=str)
    
    # =========================================================================
    # Print Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("MIGRATION PLAN SUMMARY")
    print("=" * 80)
    
    print("\n  COMPARISON: MT5 Source vs TraderVolt Existing")
    print("  " + "-" * 76)
    print(f"  {'Entity':<20} {'MT5 Source':<15} {'TV Existing':<15} {'To Create':<15} {'Skip':<10}")
    print("  " + "-" * 76)
    print(f"  {'Symbol Groups':<20} {len(mt5_symbol_groups):<15} {len(discovery.get('symbols_groups', [])):<15} {plan_stats['symbols_groups']['new']:<15} {plan_stats['symbols_groups']['existing']:<10}")
    print(f"  {'Symbols':<20} {len(symbols_data):<15} {len(discovery.get('symbols', [])):<15} {plan_stats['symbols']['new']:<15} {plan_stats['symbols']['existing']:<10}")
    print(f"  {'Traders':<20} {len(all_accounts):<15} {len(discovery.get('traders', [])):<15} {plan_stats['traders']['new']:<15} {plan_stats['traders']['existing']:<10}")
    print(f"  {'Orders':<20} {len(orders_data):<15} {len(discovery.get('orders', [])):<15} {plan_stats['orders']['new']:<15} {'-':<10}")
    print(f"  {'Positions':<20} {len(positions_data):<15} {len(discovery.get('positions', [])):<15} {plan_stats['positions']['new']:<15} {'-':<10}")
    print("  " + "-" * 76)
    
    total_to_create = (
        plan_stats['symbols_groups']['new'] +
        plan_stats['symbols']['new'] +
        plan_stats['traders']['new'] +
        plan_stats['orders']['new'] +
        plan_stats['positions']['new']
    )
    print(f"\n  [TOTAL] ENTITIES TO CREATE: {total_to_create}")
    
    print("\n  GROUP MAPPING:")
    demo_id = lookups['traders_group_name_to_id'].get('DEMO', 'N/A')
    real_id = lookups['traders_group_name_to_id'].get('REAL', 'N/A')
    root_id = lookups['traders_group_name_to_id'].get('ROOT', 'N/A')
    print(f"    demo\\* ({len(demo_accounts)} accounts) -> DEMO: {demo_id[:36] if len(demo_id) > 36 else demo_id}...")
    print(f"    real\\* ({len(real_accounts)} accounts) -> REAL: {real_id[:36] if len(real_id) > 36 else real_id}...")
    print(f"    managers\\* + other ({len(manager_accounts) + len(other_accounts)} accounts) -> ROOT: {root_id[:36] if len(root_id) > 36 else root_id}...")
    
    if plan_data['warnings']:
        print("\n  [WARNINGS]:")
        for w in plan_data['warnings']:
            print(f"    - {w}")
    
    print(f"\n[SAVED] Plan saved to: {plan_file}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
  1. Review the plan: out/migration_plan.json
  
  2. Validate the plan:
     python migrate.py validate
  
  3. Apply the migration:
     python migrate.py apply --apply --i-understand-this-will-write-to-tradervolt
""")
    
    return 0
