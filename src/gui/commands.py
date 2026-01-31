"""
GUI-compatible wrappers for migration commands.

These functions wrap the CLI commands to support callbacks for progress updates
and return structured data instead of printing to stdout.
"""

import json
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime

from src.tradervolt_client.api import TraderVoltClient


def log(callback: Optional[Callable], message: str):
    """Send a log message via callback or print."""
    if callback:
        callback(message)
    else:
        print(message)


def run_discovery(callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Execute discovery and return results.
    
    Args:
        callback: Optional function to receive log messages
        
    Returns:
        Dictionary with discovery results including entity counts
    """
    log(callback, "Starting TraderVolt Discovery...")
    
    output_dir = Path("out/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize client
    client = TraderVoltClient()
    
    log(callback, "Authenticating...")
    if not client.token_manager.ensure_authenticated():
        raise Exception("Authentication failed - check credentials")
    
    log(callback, "✓ Authenticated successfully")
    
    endpoints = [
        ('symbols-groups', 'Symbol Groups'),
        ('symbols', 'Symbols'),
        ('traders-groups', 'Trader Groups'),
        ('traders', 'Traders'),
        ('orders', 'Orders'),
        ('positions', 'Positions'),
        ('deals', 'Deals'),
    ]
    
    discovery_results: Dict[str, Any] = {
        'timestamp': datetime.now().isoformat(),
        'endpoints': {},
        'summary': {}
    }
    
    for entity_type, display_name in endpoints:
        log(callback, f"Fetching {display_name}...")
        
        try:
            status_code, data = client.list_entities(entity_type)
            
            result = {
                'status_code': status_code,
                'count': len(data) if data else 0,
                'data': data,
            }
            
            if status_code == 200:
                log(callback, f"  ✓ Found {len(data)} {display_name.lower()}")
                if data and len(data) > 0:
                    result['sample_keys'] = list(data[0].keys())
            elif status_code == 204:
                log(callback, f"  ℹ No {display_name.lower()} found")
            else:
                log(callback, f"  ⚠ Unexpected status: {status_code}")
            
            discovery_results['endpoints'][entity_type] = result
            discovery_results['summary'][entity_type] = len(data) if data else 0
            
            # Save individual endpoint data
            endpoint_file = output_dir / f"{entity_type}.json"
            with open(endpoint_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
                
        except Exception as e:
            log(callback, f"  ✗ Error fetching {display_name}: {e}")
            discovery_results['endpoints'][entity_type] = {'error': str(e), 'count': 0}
    
    # Save complete discovery results
    discovery_file = output_dir / "discovery_results.json"
    with open(discovery_file, 'w') as f:
        json.dump(discovery_results, f, indent=2, default=str)
    
    # Summary
    total = sum(discovery_results['summary'].values())
    log(callback, f"\n✓ Discovery complete. Found {total} total entities.")
    log(callback, f"Results saved to: {output_dir}")
    
    return discovery_results


def run_plan(source_dir: str = "./migration_files", 
             callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Generate migration plan and return results.
    
    Args:
        source_dir: Path to directory containing migration files
        callback: Optional function to receive log messages
        
    Returns:
        Dictionary with plan data including comparison and entities
    """
    from src.commands.plan import run_plan as _run_plan
    import argparse
    
    log(callback, f"Generating migration plan from: {source_dir}")
    
    # Create args object to match CLI interface
    args = argparse.Namespace(source=source_dir)
    
    # Capture the result by running the plan command
    result_code = _run_plan(args)
    
    if result_code != 0:
        raise Exception("Plan generation failed")
    
    # Load the generated plan
    plan_path = Path("out/migration_plan.json")
    if not plan_path.exists():
        raise Exception("Plan file not created")
    
    with open(plan_path, 'r') as f:
        plan_data = json.load(f)
    
    log(callback, "✓ Plan generated successfully")
    
    # Build comparison summary for GUI
    comparison = {}
    entities = plan_data.get('entities', {})
    
    for entity_type in ['symbols_groups', 'symbols', 'traders_groups', 'traders', 'orders', 'positions']:
        entity_list = entities.get(entity_type, [])
        comparison[entity_type] = {
            'to_create': len(entity_list),
            'source': len(entity_list),
            'existing': 0,
            'skipped': 0
        }
    
    plan_data['comparison'] = comparison
    
    # Re-save with comparison data
    with open(plan_path, 'w') as f:
        json.dump(plan_data, f, indent=2, default=str)
    
    return plan_data


def run_validate(callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Validate the migration plan.
    
    Args:
        callback: Optional function to receive log messages
        
    Returns:
        Dictionary with validation results including errors and warnings
    """
    log(callback, "Validating migration plan...")
    
    plan_path = Path("out/migration_plan.json")
    if not plan_path.exists():
        raise Exception("No migration plan found. Run plan first.")
    
    with open(plan_path, 'r') as f:
        plan = json.load(f)
    
    errors = []
    warnings = []
    
    entities = plan.get('entities', {})
    
    # Validate traders have required fields
    for trader in entities.get('traders', []):
        if not trader.get('email'):
            errors.append(f"Trader missing email: {trader.get('firstName', 'Unknown')}")
        if not trader.get('tradersGroupId'):
            warnings.append(f"Trader missing group: {trader.get('email', 'Unknown')}")
    
    # Validate symbols have required fields
    for symbol in entities.get('symbols', []):
        if not symbol.get('name'):
            errors.append(f"Symbol missing name")
        if not symbol.get('symbolsGroupId'):
            warnings.append(f"Symbol missing group: {symbol.get('name', 'Unknown')}")
    
    result = {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'entity_counts': {
            entity_type: len(entity_list)
            for entity_type, entity_list in entities.items()
        }
    }
    
    if errors:
        log(callback, f"✗ Validation failed with {len(errors)} errors")
        for e in errors[:5]:  # Show first 5
            log(callback, f"  - {e}")
    else:
        log(callback, "✓ Plan is valid")
    
    if warnings:
        log(callback, f"⚠ {len(warnings)} warnings")
    
    return result


def run_apply(test_mode: bool = True, 
              limit: Optional[int] = None,
              confirm: bool = False,
              callback: Optional[Callable[[str, Optional[float]], None]] = None) -> Dict[str, Any]:
    """
    Execute the migration.
    
    Args:
        test_mode: If True, prefix entities with MIG_TEST_
        limit: Maximum entities per type (None for unlimited)
        confirm: Must be True to proceed
        callback: Optional function receiving (message, progress_percent)
        
    Returns:
        Dictionary with migration results including created counts
    """
    if not confirm:
        raise Exception("Migration not confirmed")
    
    log_msg = lambda msg: callback(msg, None) if callback else print(msg)
    
    # Load plan
    plan_path = Path("out/migration_plan.json")
    if not plan_path.exists():
        raise Exception("No migration plan found")
    
    with open(plan_path, 'r') as f:
        plan = json.load(f)
    
    # Initialize client
    client = TraderVoltClient()
    
    log_msg("Authenticating...")
    if not client.token_manager.ensure_authenticated():
        raise Exception("Authentication failed")
    
    # Test prefix
    test_prefix = ""
    if test_mode:
        test_prefix = f"MIG_TEST_{datetime.now().strftime('%Y%m%d')}_"
        log_msg(f"Test mode enabled. Prefix: {test_prefix}")
    
    # Import order
    IMPORT_ORDER = [
        ('symbols_groups', 'symbols-groups', 'Symbol Groups'),
        ('symbols', 'symbols', 'Symbols'),
        ('traders_groups', 'traders-groups', 'Trader Groups'),
        ('traders', 'traders', 'Traders'),
        ('orders', 'orders', 'Orders'),
        ('positions', 'positions', 'Positions'),
    ]
    
    entities = plan.get('entities', {})
    
    # Calculate total for progress
    total_entities = sum(len(entities.get(k, [])) for k, _, _ in IMPORT_ORDER)
    if limit:
        total_entities = min(total_entities, limit * len(IMPORT_ORDER))
    
    processed = 0
    stats = {'created': 0, 'skipped': 0, 'failed': 0}
    created_entities = {}
    
    for plan_key, api_key, display_name in IMPORT_ORDER:
        entity_list = entities.get(plan_key, [])
        if not entity_list:
            log_msg(f"⏭️ {display_name}: No entities")
            continue
        
        if limit:
            entity_list = entity_list[:limit]
        
        log_msg(f"\n📦 Migrating {display_name} ({len(entity_list)} entities)")
        created_entities[plan_key] = []
        
        for i, entity in enumerate(entity_list):
            # Apply test prefix to name fields
            if test_mode:
                for field in ['name', 'firstName']:
                    if field in entity and entity[field]:
                        if not entity[field].startswith('MIG_TEST_'):
                            entity[field] = test_prefix + entity[field]
            
            # Create entity
            try:
                status_code, response = client.create_entity(api_key, entity)
                
                if status_code in [200, 201]:
                    stats['created'] += 1
                    created_entities[plan_key].append(response)
                    log_msg(f"  ✓ Created: {entity.get('name', entity.get('email', 'entity'))}")
                elif status_code == 409:
                    stats['skipped'] += 1
                    log_msg(f"  ⏭️ Exists: {entity.get('name', entity.get('email', 'entity'))}")
                else:
                    stats['failed'] += 1
                    log_msg(f"  ✗ Failed ({status_code}): {entity.get('name', entity.get('email', 'entity'))}")
                    
            except Exception as e:
                stats['failed'] += 1
                log_msg(f"  ✗ Error: {e}")
            
            processed += 1
            if callback:
                progress = (processed / total_entities) * 100 if total_entities > 0 else 100
                callback(None, progress)
    
    # Save results
    results_dir = Path("out/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'test_mode': test_mode,
        'stats': stats,
        'created_entities': created_entities
    }
    
    with open(results_dir / 'migration_results.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    log_msg(f"\n✓ Migration complete!")
    log_msg(f"  Created: {stats['created']}")
    log_msg(f"  Skipped: {stats['skipped']}")
    log_msg(f"  Failed: {stats['failed']}")
    
    return result
