"""
Plan Command

Parses source data files and generates a migration plan.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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


def run_plan(args) -> int:
    """
    Execute the plan command.
    
    Parses all source data files and generates a migration plan.
    """
    print("\n" + "="*60)
    print("MIGRATION PLAN GENERATION")
    print("="*60 + "\n")
    
    # Source directory
    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return 1
    
    print(f"📂 Source directory: {source_dir}")
    
    # Initialize containers
    clients_data: List[Dict] = []
    accounts_data: List[Dict] = []
    orders_data: List[Dict] = []
    positions_data: List[Dict] = []
    symbols_data: List[Dict] = []
    
    # Parse source files
    print("\n--- Parsing Source Files ---\n")
    
    # Clients.htm
    clients_file = source_dir / "Clients.htm"
    if clients_file.exists():
        clients_data = parse_clients(str(clients_file))
        print(f"  ✓ Clients.htm: {len(clients_data)} clients")
    else:
        print(f"  ⚠ Clients.htm not found")
    
    # Accounts.htm
    accounts_file = source_dir / "Accounts.htm"
    if accounts_file.exists():
        accounts_data = parse_accounts(str(accounts_file))
        print(f"  ✓ Accounts.htm: {len(accounts_data)} accounts")
    else:
        print(f"  ⚠ Accounts.htm not found")
    
    # Orders.htm
    orders_file = source_dir / "Orders.htm"
    if orders_file.exists():
        orders_data = parse_orders(str(orders_file))
        print(f"  ✓ Orders.htm: {len(orders_data)} orders")
    else:
        print(f"  ⚠ Orders.htm not found")
    
    # Positions.htm
    positions_file = source_dir / "Positions.htm"
    if positions_file.exists():
        positions_data = parse_positions(str(positions_file))
        print(f"  ✓ Positions.htm: {len(positions_data)} positions")
    else:
        print(f"  ⚠ Positions.htm not found")
    
    # symbols.json
    symbols_file = source_dir / "symbols.json"
    if symbols_file.exists():
        symbols_data = parse_symbols_json(str(symbols_file))
        print(f"  ✓ symbols.json: {len(symbols_data)} symbols")
    else:
        print(f"  ⚠ symbols.json not found")
    
    # Check test mode
    test_mode = hasattr(args, 'test') and args.test
    limit = getattr(args, 'limit', None)
    test_prefix = ""
    
    if test_mode:
        test_prefix = f"MIG_TEST_{datetime.now().strftime('%Y%m%d')}_"
        print(f"\n🧪 TEST MODE ENABLED")
        print(f"   Prefix: {test_prefix}")
        if limit:
            print(f"   Limit: {limit} entities per type")
    
    # Build migration plan
    print("\n--- Building Migration Plan ---\n")
    
    plan = MigrationPlan(
        timestamp=datetime.now().isoformat(),
        test_mode=test_mode,
        test_prefix=test_prefix,
    )
    
    # 1. Symbol Groups (from symbols.json paths or accounts groups)
    symbol_groups = set()
    if symbols_data:
        for group in get_symbol_groups(symbols_data):
            symbol_groups.add(group)
    
    # Also infer groups from symbol paths
    for sym in symbols_data:
        path = sym.get('path', '')
        if path and '\\' in path:
            parts = path.split('\\')
            if parts[0]:
                symbol_groups.add(parts[0])
    
    for group_name in sorted(symbol_groups):
        name = f"{test_prefix}{group_name}" if test_mode else group_name
        plan.symbols_groups.append(SymbolsGroup(
            name=name,
            description=f"Migrated from MT5: {group_name}"
        ))
    
    if limit and test_mode:
        plan.symbols_groups = plan.symbols_groups[:limit]
    
    print(f"  • Symbol Groups: {len(plan.symbols_groups)}")
    
    # 2. Symbols (from symbols.json)
    for sym in symbols_data:
        name = sym.get('name', '')
        if not name:
            continue
        
        symbol_name = f"{test_prefix}{name}" if test_mode else name
        plan.symbols.append(Symbol(
            name=symbol_name,
            description=sym.get('description', ''),
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
    
    if limit and test_mode:
        plan.symbols = plan.symbols[:limit]
    
    print(f"  • Symbols: {len(plan.symbols)}")
    
    # 3. Trader Groups (from account groups)
    trader_groups = get_unique_groups_from_accounts(accounts_data)
    for group_name in trader_groups:
        name = f"{test_prefix}{group_name}" if test_mode else group_name
        # Parse leverage from group name if present (e.g., "demo\forex-net-usd-01")
        plan.traders_groups.append(TradersGroup(
            name=name,
            description=f"Migrated from MT5: {group_name}",
            leverage=100.0,
        ))
    
    if limit and test_mode:
        plan.traders_groups = plan.traders_groups[:limit]
    
    print(f"  • Trader Groups: {len(plan.traders_groups)}")
    
    # 4. Traders (from accounts)
    for acc in accounts_data:
        login = acc.get('login', 0)
        if not login:
            continue
        
        name = acc.get('name', f"Trader_{login}")
        if test_mode:
            name = f"{test_prefix}{name}"
        
        plan.traders.append(Trader(
            login=login,
            name=name,
            email=acc.get('email', ''),
            group=acc.get('group', ''),
            balance=acc.get('balance', 0.0),
            credit=acc.get('credit', 0.0),
            leverage=acc.get('leverage', 100),
        ))
    
    if limit and test_mode:
        plan.traders = plan.traders[:limit]
    
    print(f"  • Traders: {len(plan.traders)}")
    
    # 5. Orders (from orders)
    for ord in orders_data:
        order_id = ord.get('order_id', 0)
        if not order_id:
            continue
        
        plan.orders.append(Order(
            transactionId=order_id,
            login=ord.get('login', 0),
            symbol=ord.get('symbol', ''),
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
    
    if limit and test_mode:
        plan.orders = plan.orders[:limit]
    
    print(f"  • Orders: {len(plan.orders)}")
    
    # 6. Positions (from positions)
    for pos in positions_data:
        position_id = pos.get('position_id', 0)
        if not position_id:
            continue
        
        plan.positions.append(Position(
            transactionId=position_id,
            login=pos.get('login', 0),
            symbol=pos.get('symbol', ''),
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
    
    if limit and test_mode:
        plan.positions = plan.positions[:limit]
    
    print(f"  • Positions: {len(plan.positions)}")
    
    # Save migration plan
    output_dir = Path("out")
    output_dir.mkdir(exist_ok=True)
    
    plan_file = output_dir / "migration_plan.json"
    plan_data = {
        'timestamp': plan.timestamp,
        'test_mode': plan.test_mode,
        'test_prefix': plan.test_prefix,
        'summary': plan.summary(),
        'entities': {
            'symbols_groups': [sg.to_api_payload() for sg in plan.symbols_groups],
            'symbols': [s.to_api_payload() for s in plan.symbols],
            'traders_groups': [tg.to_api_payload() for tg in plan.traders_groups],
            'traders': [t.to_api_payload() for t in plan.traders],
            'orders': [o.to_api_payload() for o in plan.orders],
            'positions': [p.to_api_payload() for p in plan.positions],
        }
    }
    
    with open(plan_file, 'w') as f:
        json.dump(plan_data, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*60)
    print("MIGRATION PLAN SUMMARY")
    print("="*60)
    
    summary = plan.summary()
    total = sum(summary.values())
    
    print(f"\n  Entity Type        Count")
    print(f"  {'-'*30}")
    for entity_type, count in summary.items():
        print(f"  {entity_type.replace('_', ' ').title():20} {count:>5}")
    print(f"  {'-'*30}")
    print(f"  {'TOTAL':20} {total:>5}")
    
    if test_mode:
        print(f"\n  🧪 Test mode: entities will be prefixed with '{test_prefix}'")
    
    print(f"\n📁 Plan saved to: {plan_file}")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
  1. Review the plan: out/migration_plan.json
  
  2. Run discovery to check existing TraderVolt entities:
     python migrate.py discover
  
  3. Validate the plan:
     python migrate.py validate
  
  4. Apply the migration:
     python migrate.py apply --apply --i-understand-this-will-write-to-tradervolt
     
     Or in test mode first:
     python migrate.py apply --test --limit 1
""")
    
    return 0
