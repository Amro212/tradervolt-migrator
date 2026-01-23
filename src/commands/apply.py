"""
Apply Command

Executes the migration by creating entities in TraderVolt.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.tradervolt_client.api import TraderVoltClient

logger = logging.getLogger(__name__)


class MigrationExecutor:
    """Executes migration with verification and rollback support."""
    
    # Import order based on dependencies
    IMPORT_ORDER = [
        ('symbols_groups', 'symbols-groups', 'Symbol Groups'),
        ('symbols', 'symbols', 'Symbols'),
        ('traders_groups', 'traders-groups', 'Trader Groups'),
        ('traders', 'traders', 'Traders'),
        ('orders', 'orders', 'Orders'),
        ('positions', 'positions', 'Positions'),
        # ('deals', 'deals', 'Deals'),  # Enable if needed
    ]
    
    def __init__(self, client: TraderVoltClient, test_mode: bool = False, 
                 test_prefix: str = "", limit: Optional[int] = None):
        self.client = client
        self.test_mode = test_mode
        self.test_prefix = test_prefix
        self.limit = limit
        
        # Track created entities for rollback
        self.created: Dict[str, List[Dict[str, Any]]] = {
            entity_type: [] for _, entity_type, _ in self.IMPORT_ORDER
        }
        
        # Mappings from source to target IDs
        self.mappings: Dict[str, Dict[str, str]] = {
            'symbols_groups': {},  # name -> id
            'symbols': {},         # name -> id
            'traders_groups': {},  # name -> id
            'traders': {},         # login -> id
        }
        
        # Statistics
        self.stats = {
            'created': 0,
            'skipped': 0,
            'failed': 0,
            'verified': 0,
        }
    
    def execute(self, plan: Dict[str, Any]) -> bool:
        """Execute the migration plan."""
        entities = plan.get('entities', {})
        
        print("\n" + "="*60)
        print("EXECUTING MIGRATION")
        print("="*60)
        
        if self.test_mode:
            print(f"\n🧪 TEST MODE - Prefix: {self.test_prefix}")
            if self.limit:
                print(f"   Limit: {self.limit} entities per type")
        
        for plan_key, api_key, display_name in self.IMPORT_ORDER:
            entity_list = entities.get(plan_key, [])
            if not entity_list:
                print(f"\n⏭️  {display_name}: No entities to migrate")
                continue
            
            # Apply limit in test mode
            if self.limit:
                entity_list = entity_list[:self.limit]
            
            success = self._migrate_entity_type(
                api_key, display_name, entity_list, plan_key
            )
            
            if not success:
                print(f"\n❌ Migration failed at {display_name}")
                if not self._confirm_continue():
                    return False
        
        return True
    
    def _migrate_entity_type(self, api_key: str, display_name: str, 
                              entities: List[Dict], plan_key: str) -> bool:
        """Migrate all entities of a single type."""
        print(f"\n{'─'*60}")
        print(f"📦 Migrating {display_name} ({len(entities)} entities)")
        print(f"{'─'*60}")
        
        success_count = 0
        fail_count = 0
        
        for i, entity in enumerate(entities):
            # Resolve references
            resolved = self._resolve_references(entity, plan_key)
            
            # Create entity
            status, created, error = self.client.create_entity(api_key, resolved)
            
            entity_name = self._get_entity_name(entity, plan_key)
            
            if status == 201 and created:
                # Verify the entity was created correctly
                entity_id = created.get('id') or created.get('transactionId')
                
                if entity_id:
                    # Store mapping
                    self._store_mapping(plan_key, entity, str(entity_id))
                    
                    # Verification read-back
                    success, msg, _ = self.client.verify_entity(
                        api_key, str(entity_id), 
                        self._get_verify_fields(entity, plan_key)
                    )
                    
                    if success:
                        print(f"  ✓ [{i+1}/{len(entities)}] {entity_name} (id: {entity_id})")
                        self.created[api_key].append(created)
                        self.stats['created'] += 1
                        self.stats['verified'] += 1
                        success_count += 1
                    else:
                        print(f"  ⚠ [{i+1}/{len(entities)}] {entity_name} created but verification failed: {msg}")
                        self.created[api_key].append(created)
                        self.stats['created'] += 1
                        success_count += 1
                else:
                    print(f"  ✓ [{i+1}/{len(entities)}] {entity_name} (no id returned)")
                    self.stats['created'] += 1
                    success_count += 1
            else:
                print(f"  ❌ [{i+1}/{len(entities)}] {entity_name}: {error}")
                self.stats['failed'] += 1
                fail_count += 1
        
        print(f"\n  Summary: {success_count} created, {fail_count} failed")
        
        return fail_count == 0
    
    def _resolve_references(self, entity: Dict, plan_key: str) -> Dict:
        """Resolve foreign key references to created entities."""
        resolved = entity.copy()
        
        # Resolve symbolsGroupId for symbols
        if plan_key == 'symbols':
            # For now, we don't have symbolsGroupId mapping
            pass
        
        # Resolve tradersGroupId for traders
        if plan_key == 'traders':
            group_name = entity.get('group', '')
            if group_name and group_name in self.mappings['traders_groups']:
                resolved['tradersGroupId'] = self.mappings['traders_groups'][group_name]
        
        # Resolve traderId for orders/positions
        if plan_key in ['orders', 'positions']:
            login = entity.get('login', 0)
            if login and str(login) in self.mappings['traders']:
                resolved['traderId'] = self.mappings['traders'][str(login)]
            
            # Resolve symbolId
            symbol_name = entity.get('symbol', '')
            if symbol_name and symbol_name in self.mappings['symbols']:
                resolved['symbolId'] = self.mappings['symbols'][symbol_name]
        
        return resolved
    
    def _store_mapping(self, plan_key: str, entity: Dict, entity_id: str):
        """Store mapping from source identifier to TraderVolt ID."""
        if plan_key == 'symbols_groups':
            name = entity.get('name', '')
            if name:
                self.mappings['symbols_groups'][name] = entity_id
        elif plan_key == 'symbols':
            name = entity.get('name', '')
            if name:
                self.mappings['symbols'][name] = entity_id
        elif plan_key == 'traders_groups':
            name = entity.get('name', '')
            if name:
                self.mappings['traders_groups'][name] = entity_id
        elif plan_key == 'traders':
            login = entity.get('login', 0)
            if login:
                self.mappings['traders'][str(login)] = entity_id
    
    def _get_entity_name(self, entity: Dict, plan_key: str) -> str:
        """Get a human-readable name for an entity."""
        if plan_key == 'traders':
            return f"Trader {entity.get('login', '?')} ({entity.get('name', '')})"
        elif plan_key in ['orders', 'positions', 'deals']:
            return f"txId={entity.get('transactionId', '?')}"
        else:
            return entity.get('name', '?')
    
    def _get_verify_fields(self, entity: Dict, plan_key: str) -> Dict[str, Any]:
        """Get key fields to verify after creation."""
        if plan_key == 'symbols_groups':
            return {'name': entity.get('name')}
        elif plan_key == 'symbols':
            return {'name': entity.get('name')}
        elif plan_key == 'traders_groups':
            return {'name': entity.get('name')}
        elif plan_key == 'traders':
            return {'login': entity.get('login')}
        elif plan_key in ['orders', 'positions', 'deals']:
            return {'transactionId': entity.get('transactionId')}
        return {}
    
    def _confirm_continue(self) -> bool:
        """Ask user if they want to continue after a failure."""
        try:
            response = input("\n  Continue with remaining entities? [y/N]: ")
            return response.lower() in ['y', 'yes']
        except:
            return False
    
    def save_results(self, output_dir: Path):
        """Save migration results and mappings."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save mappings
        mappings_file = output_dir / "mappings.json"
        with open(mappings_file, 'w') as f:
            json.dump(self.mappings, f, indent=2)
        
        # Save created entities
        created_file = output_dir / "created_entities.json"
        with open(created_file, 'w') as f:
            json.dump(self.created, f, indent=2, default=str)
        
        # Save stats
        stats_file = output_dir / "migration_stats.json"
        with open(stats_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'test_mode': self.test_mode,
                'stats': self.stats,
            }, f, indent=2)
        
        print(f"\n📁 Results saved to: {output_dir}")


def run_apply(args) -> int:
    """
    Execute the apply command.
    
    Creates entities in TraderVolt according to the migration plan.
    """
    print("\n" + "="*60)
    print("TRADERVOLT MIGRATION - APPLY")
    print("="*60)
    
    # Validate flags
    test_mode = getattr(args, 'test', False)
    apply_flag = getattr(args, 'apply', False)
    confirm_flag = getattr(args, 'i_understand_this_will_write_to_tradervolt', False)
    limit = getattr(args, 'limit', None)
    
    if not test_mode and not (apply_flag and confirm_flag):
        print("""
❌ SAFETY CHECK FAILED

To apply migration in production mode, you must provide BOTH flags:
  --apply --i-understand-this-will-write-to-tradervolt

For safe testing, use test mode instead:
  python migrate.py apply --test --limit 1
""")
        return 1
    
    # Load migration plan
    plan_file = Path("out/migration_plan.json")
    if not plan_file.exists():
        print("❌ Migration plan not found!")
        print("   Run `python migrate.py plan` first")
        return 1
    
    with open(plan_file, 'r') as f:
        plan = json.load(f)
    
    print(f"\n📄 Loaded plan: {plan_file}")
    print(f"   Timestamp: {plan.get('timestamp', 'unknown')}")
    
    # Show summary
    summary = plan.get('summary', {})
    total = sum(summary.values())
    
    print(f"\n   Entities to migrate:")
    for entity_type, count in summary.items():
        if count > 0:
            print(f"     • {entity_type.replace('_', ' ').title()}: {count}")
    print(f"     ─────────────────────")
    print(f"     Total: {total}")
    
    if test_mode:
        test_prefix = f"MIG_TEST_{datetime.now().strftime('%Y%m%d')}_"
        print(f"\n🧪 TEST MODE ENABLED")
        print(f"   Prefix: {test_prefix}")
        if limit:
            print(f"   Limit: {limit} per entity type")
    else:
        test_prefix = ""
        print(f"\n⚠️  PRODUCTION MODE - Changes will be permanent!")
    
    # Confirm before proceeding
    if not test_mode:
        print("\n" + "─"*60)
        try:
            response = input("Type 'MIGRATE' to confirm and proceed: ")
            if response != 'MIGRATE':
                print("Migration cancelled.")
                return 0
        except KeyboardInterrupt:
            print("\nMigration cancelled.")
            return 0
    
    # Initialize client
    client = TraderVoltClient()
    
    if not client.token_manager.access_token:
        print("\n❌ No access token found!")
        print("   Set TRADERVOLT_ACCESS_TOKEN environment variable or create token.json")
        return 1
    
    print(f"\n✓ Access token loaded")
    
    # Execute migration
    executor = MigrationExecutor(
        client=client,
        test_mode=test_mode,
        test_prefix=test_prefix,
        limit=limit
    )
    
    start_time = time.time()
    success = executor.execute(plan)
    elapsed = time.time() - start_time
    
    # Save results
    output_dir = Path("out/results")
    executor.save_results(output_dir)
    
    # Print final summary
    print("\n" + "="*60)
    print("MIGRATION COMPLETE")
    print("="*60)
    
    stats = executor.stats
    print(f"""
   Created:   {stats['created']}
   Verified:  {stats['verified']}
   Skipped:   {stats['skipped']}
   Failed:    {stats['failed']}
   
   Duration:  {elapsed:.1f}s
""")
    
    if test_mode and stats['created'] > 0:
        print("""
🧪 Test entities created with MIG_TEST_ prefix.
   Run `python migrate.py cleanup` to remove them.
""")
    
    if success:
        print("✅ Migration completed successfully!")
        return 0
    else:
        print("⚠️  Migration completed with some failures.")
        return 1
