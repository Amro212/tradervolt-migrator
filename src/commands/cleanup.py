"""
Cleanup Command

Removes test entities from TraderVolt.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

from src.tradervolt_client.api import TraderVoltClient

logger = logging.getLogger(__name__)


def run_cleanup(args) -> int:
    """
    Execute the cleanup command.
    
    Removes entities with the MIG_TEST_ prefix from TraderVolt.
    Deletes in reverse dependency order to avoid constraint violations.
    """
    print("\n" + "="*60)
    print("TRADERVOLT CLEANUP")
    print("="*60 + "\n")
    
    prefix = getattr(args, 'prefix', 'MIG_TEST_')
    dry_run = getattr(args, 'dry_run', False)
    
    print(f"🔍 Searching for entities with prefix: '{prefix}'")
    
    if dry_run:
        print(f"   (DRY RUN - no entities will be deleted)")
    
    # Initialize client
    client = TraderVoltClient()
    
    # Authenticate (auto-login if needed)
    print("\n🔐 Authenticating...")
    if not client.token_manager.ensure_authenticated():
        print("❌ ERROR: Authentication failed!")
        print("   Set TRADERVOLT_EMAIL and TRADERVOLT_PASSWORD environment variables.")
        return 1
    
    print("✓ Authenticated successfully\n")
    
    # Delete order (reverse of creation order)
    # Must delete dependent entities before their parents
    DELETE_ORDER = [
        ('deals', 'Deals', 'transactionId'),
        ('positions', 'Positions', 'transactionId'),
        ('orders', 'Orders', 'transactionId'),
        ('traders', 'Traders', 'login'),
        ('traders-groups', 'Trader Groups', 'name'),
        ('symbols', 'Symbols', 'name'),
        ('symbols-groups', 'Symbol Groups', 'name'),
    ]
    
    total_found = 0
    total_deleted = 0
    total_failed = 0
    
    for entity_type, display_name, id_field in DELETE_ORDER:
        print(f"\n{'─'*60}")
        print(f"🗑️  {display_name}")
        print(f"{'─'*60}")
        
        # Fetch all entities of this type
        status, entities = client.list_entities(entity_type)
        
        if status != 200 or not entities:
            print(f"   No {display_name.lower()} found")
            continue
        
        # Filter entities with prefix
        to_delete = []
        for entity in entities:
            name = entity.get('name', '')
            # For traders, check the name field
            if entity_type == 'traders':
                name = entity.get('name', '')
            
            if name.startswith(prefix):
                to_delete.append(entity)
        
        if not to_delete:
            print(f"   No {display_name.lower()} with prefix '{prefix}'")
            continue
        
        print(f"   Found {len(to_delete)} to delete:")
        total_found += len(to_delete)
        
        for entity in to_delete:
            entity_id = entity.get('id') or entity.get('transactionId')
            entity_name = entity.get('name', '') or entity.get(id_field, '')
            
            if not entity_id:
                print(f"   ⚠ Skipping entity without ID: {entity_name}")
                continue
            
            if dry_run:
                print(f"   • Would delete: {entity_name} (id: {entity_id})")
            else:
                status, error = client.delete_entity(entity_type, str(entity_id))
                
                if status in [200, 204]:
                    print(f"   ✓ Deleted: {entity_name}")
                    total_deleted += 1
                else:
                    print(f"   ❌ Failed to delete {entity_name}: {error}")
                    total_failed += 1
    
    # Print summary
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)
    
    if dry_run:
        print(f"""
   Entities found:    {total_found}
   
   This was a dry run. No entities were deleted.
   Run without --dry-run to delete entities:
   
   python migrate.py cleanup --prefix {prefix}
""")
    else:
        print(f"""
   Entities found:    {total_found}
   Deleted:           {total_deleted}
   Failed:            {total_failed}
""")
    
    if total_failed > 0:
        print("⚠️  Some deletions failed. Check output for details.")
        return 1
    
    if total_deleted > 0:
        print("✅ Cleanup completed successfully!")
    
    return 0
