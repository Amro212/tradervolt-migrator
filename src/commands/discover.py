"""
Discover Command

Fetches current state from TraderVolt API endpoints and saves response shapes.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.tradervolt_client.api import TraderVoltClient

logger = logging.getLogger(__name__)


def run_discover(args) -> int:
    """
    Execute the discover command.
    
    Fetches GET responses from all TraderVolt endpoints to:
    1. Verify API connectivity
    2. Capture response shapes for mapping
    3. Identify existing entities that might conflict
    """
    print("\n" + "="*60)
    print("TRADERVOLT DISCOVERY")
    print("="*60 + "\n")
    
    # Create output directory
    output_dir = Path("out/discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize client
    client = TraderVoltClient()
    
    # Authenticate (auto-login if needed)
    print("🔐 Authenticating...")
    if not client.token_manager.ensure_authenticated():
        print("❌ ERROR: Authentication failed!")
        print("   Set TRADERVOLT_EMAIL and TRADERVOLT_PASSWORD environment variables.")
        return 1
    
    print("✓ Authenticated successfully")
    
    # Define endpoints to discover
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
    
    # Discover each endpoint
    for entity_type, display_name in endpoints:
        print(f"\n📡 Fetching {display_name}...")
        
        try:
            status_code, data = client.list_entities(entity_type)
            
            result = {
                'status_code': status_code,
                'count': len(data) if data else 0,
                'data': data,
            }
            
            if status_code == 200:
                print(f"   ✓ Found {len(data)} {display_name.lower()}")
                
                # Analyze schema from first item
                if data and len(data) > 0:
                    first_item = data[0]
                    result['sample_keys'] = list(first_item.keys())
                    result['sample'] = first_item
                    
            elif status_code == 204:
                print(f"   ℹ No {display_name.lower()} found (empty)")
            else:
                print(f"   ⚠ Unexpected status: {status_code}")
            
            discovery_results['endpoints'][entity_type] = result
            discovery_results['summary'][entity_type] = len(data) if data else 0
            
            # Save individual endpoint data
            endpoint_file = output_dir / f"{entity_type}.json"
            with open(endpoint_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            discovery_results['endpoints'][entity_type] = {
                'error': str(e),
                'count': 0,
            }
    
    # Save complete discovery results
    discovery_file = output_dir / "discovery_results.json"
    with open(discovery_file, 'w') as f:
        json.dump(discovery_results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*60)
    print("DISCOVERY SUMMARY")
    print("="*60)
    
    total = 0
    for entity_type, display_name in endpoints:
        count = discovery_results['summary'].get(entity_type, 0)
        total += count
        status = "✓" if count > 0 else "○"
        print(f"  {status} {display_name}: {count}")
    
    print(f"\n  Total entities: {total}")
    print(f"\n📁 Results saved to: {output_dir}")
    
    # Show test-mode entities if any
    test_prefix_count = 0
    for entity_type, _ in endpoints:
        data = discovery_results['endpoints'].get(entity_type, {}).get('data', [])
        for item in data:
            name = item.get('name', '')
            if name.startswith('MIG_TEST_'):
                test_prefix_count += 1
    
    if test_prefix_count > 0:
        print(f"\n⚠️  Found {test_prefix_count} entities with MIG_TEST_ prefix")
        print("   Run `python migrate.py cleanup` to remove them")
    
    return 0
