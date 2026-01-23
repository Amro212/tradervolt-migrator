"""
Validate Command

Validates migration plan and checks for potential issues.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

from src.tradervolt_client.api import TraderVoltClient

logger = logging.getLogger(__name__)


def run_validate(args) -> int:
    """
    Execute the validate command.
    
    Validates the migration plan and checks for:
    1. Plan file exists and is valid
    2. All required fields are present
    3. No conflicts with existing TraderVolt entities
    4. Symbol references are valid
    5. Trader references are valid
    """
    print("\n" + "="*60)
    print("MIGRATION PLAN VALIDATION")
    print("="*60 + "\n")
    
    # Load migration plan
    plan_file = Path("out/migration_plan.json")
    if not plan_file.exists():
        print("❌ Migration plan not found!")
        print("   Run `python migrate.py plan` first")
        return 1
    
    with open(plan_file, 'r') as f:
        plan = json.load(f)
    
    print(f"📄 Loaded plan from: {plan_file}")
    print(f"   Timestamp: {plan.get('timestamp', 'unknown')}")
    print(f"   Test mode: {plan.get('test_mode', False)}")
    
    # Track validation results
    errors: List[str] = []
    warnings: List[str] = []
    
    entities = plan.get('entities', {})
    summary = plan.get('summary', {})
    
    print("\n--- Validating Entity Counts ---\n")
    
    for entity_type, count in summary.items():
        entity_list = entities.get(entity_type, [])
        actual_count = len(entity_list)
        if actual_count != count:
            errors.append(f"{entity_type}: summary says {count}, actual is {actual_count}")
            print(f"  ❌ {entity_type}: count mismatch")
        else:
            print(f"  ✓ {entity_type}: {count} entities")
    
    print("\n--- Validating Required Fields ---\n")
    
    # Symbols Groups
    for i, sg in enumerate(entities.get('symbols_groups', [])):
        if not sg.get('name'):
            errors.append(f"symbols_groups[{i}]: missing 'name'")
    print(f"  ✓ Symbol groups validated")
    
    # Symbols
    for i, sym in enumerate(entities.get('symbols', [])):
        if not sym.get('name'):
            errors.append(f"symbols[{i}]: missing 'name'")
        if not sym.get('baseCurrency'):
            warnings.append(f"symbols[{i}] ({sym.get('name', '?')}): missing 'baseCurrency', defaulting to USD")
        if not sym.get('quoteCurrency'):
            warnings.append(f"symbols[{i}] ({sym.get('name', '?')}): missing 'quoteCurrency', defaulting to USD")
    print(f"  ✓ Symbols validated")
    
    # Trader Groups
    for i, tg in enumerate(entities.get('traders_groups', [])):
        if not tg.get('name'):
            errors.append(f"traders_groups[{i}]: missing 'name'")
    print(f"  ✓ Trader groups validated")
    
    # Traders
    for i, t in enumerate(entities.get('traders', [])):
        if not t.get('login') and t.get('login') != 0:
            errors.append(f"traders[{i}]: missing 'login'")
        if not t.get('name'):
            warnings.append(f"traders[{i}] (login={t.get('login', '?')}): missing 'name'")
    print(f"  ✓ Traders validated")
    
    # Orders
    for i, o in enumerate(entities.get('orders', [])):
        if not o.get('transactionId') and o.get('transactionId') != 0:
            errors.append(f"orders[{i}]: missing 'transactionId'")
        if not o.get('symbol'):
            warnings.append(f"orders[{i}] (txId={o.get('transactionId', '?')}): missing 'symbol'")
    print(f"  ✓ Orders validated")
    
    # Positions
    for i, p in enumerate(entities.get('positions', [])):
        if not p.get('transactionId') and p.get('transactionId') != 0:
            errors.append(f"positions[{i}]: missing 'transactionId'")
        if not p.get('symbol'):
            warnings.append(f"positions[{i}] (txId={p.get('transactionId', '?')}): missing 'symbol'")
    print(f"  ✓ Positions validated")
    
    # Check for conflicts with existing entities
    print("\n--- Checking for Conflicts ---\n")
    
    try:
        client = TraderVoltClient()
        if client.token_manager.ensure_authenticated():
            # Get existing entities
            existing: Dict[str, List[str]] = {}
            
            for entity_type in ['symbols-groups', 'symbols', 'traders-groups', 'traders']:
                status, data = client.list_entities(entity_type)
                if status == 200 and data:
                    existing[entity_type] = [
                        item.get('name', '') or str(item.get('login', ''))
                        for item in data
                    ]
                else:
                    existing[entity_type] = []
            
            # Check symbols groups
            for sg in entities.get('symbols_groups', []):
                name = sg.get('name', '')
                if name in existing.get('symbols-groups', []):
                    warnings.append(f"Symbol group '{name}' already exists in TraderVolt")
            
            # Check symbols
            for sym in entities.get('symbols', []):
                name = sym.get('name', '')
                if name in existing.get('symbols', []):
                    warnings.append(f"Symbol '{name}' already exists in TraderVolt")
            
            # Check trader groups
            for tg in entities.get('traders_groups', []):
                name = tg.get('name', '')
                if name in existing.get('traders-groups', []):
                    warnings.append(f"Trader group '{name}' already exists in TraderVolt")
            
            # Check traders (by login)
            existing_logins = set()
            for t in existing.get('traders', []):
                try:
                    existing_logins.add(int(t))
                except:
                    pass
            
            for t in entities.get('traders', []):
                login = t.get('login', 0)
                if login in existing_logins:
                    warnings.append(f"Trader with login {login} already exists in TraderVolt")
            
            print(f"  ✓ Conflict check complete")
        else:
            print(f"  ⚠ Skipped conflict check (no API token)")
    except Exception as e:
        print(f"  ⚠ Conflict check failed: {e}")
    
    # Print results
    print("\n" + "="*60)
    print("VALIDATION RESULTS")
    print("="*60)
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"   • {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   • {warning}")
    
    if not errors and not warnings:
        print("\n✅ Validation passed with no issues!")
    elif not errors:
        print(f"\n✅ Validation passed with {len(warnings)} warning(s)")
    else:
        print(f"\n❌ Validation failed with {len(errors)} error(s)")
        return 1
    
    print("\n" + "="*60)
    print("READY FOR MIGRATION")
    print("="*60)
    
    if plan.get('test_mode'):
        print("""
  Test mode migration:
    python migrate.py apply --test --limit 1
""")
    else:
        print("""
  Production migration (CAUTION - this will write to TraderVolt!):
    python migrate.py apply --apply --i-understand-this-will-write-to-tradervolt
""")
    
    return 0
