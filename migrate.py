#!/usr/bin/env python3
"""
TraderVolt Migration Tool

Migrates trading data from MT5 exports to TraderVolt via REST API.
Implements strict safety controls: discovery, test-mode, and sequential execution.

Usage:
    python migrate.py discover               # Fetch all endpoint data
    python migrate.py plan --source ./migration_files  # Generate migration plan
    python migrate.py validate               # Validate migration plan
    python migrate.py apply --test --limit 1 # Safe test with MIG_TEST_ prefix
    python migrate.py cleanup --prefix MIG_TEST_  # Clean up test entities
"""

import argparse
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def main():
    parser = argparse.ArgumentParser(
        description='TraderVolt Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Migration Order (dependencies):
  1. symbols-groups    Symbol groupings (e.g., Forex, Crypto)
  2. symbols           Trading instruments (e.g., EURUSD, BTCUSD)
  3. traders-groups    Account groupings (e.g., demo, real)
  4. traders           Trading accounts
  5. orders            Trade orders
  6. positions         Open positions
  7. deals             Executed deals

Examples:
  # Step 1: Discover existing data in TraderVolt
  python migrate.py discover

  # Step 2: Generate migration plan from source files
  python migrate.py plan --source ./migration_files

  # Step 3: Validate the plan
  python migrate.py validate

  # Step 4a: Test with a single entity (safe)
  python migrate.py apply --test --limit 1

  # Step 4b: Full migration (CAUTION!)
  python migrate.py apply --apply --i-understand-this-will-write-to-tradervolt

  # Clean up test entities
  python migrate.py cleanup --prefix MIG_TEST_
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Discover command
    discover_parser = subparsers.add_parser(
        'discover', 
        help='Fetch existing data from TraderVolt API endpoints'
    )
    
    # Plan command
    plan_parser = subparsers.add_parser(
        'plan', 
        help='Generate migration plan from source files (no writes)'
    )
    plan_parser.add_argument(
        '--source', '-s', 
        default='./migration_files', 
        help='Directory containing MT5 export files (default: ./migration_files)'
    )
    plan_parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Generate plan in test mode with MIG_TEST_ prefix'
    )
    plan_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit entities per type (for test mode)'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate', 
        help='Validate migration plan and check for conflicts'
    )
    
    # Apply command
    apply_parser = subparsers.add_parser(
        'apply', 
        help='Execute migration (creates entities in TraderVolt)'
    )
    apply_parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test mode: create entities with MIG_TEST_ prefix'
    )
    apply_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit entities per type'
    )
    apply_parser.add_argument(
        '--apply',
        action='store_true',
        help='Required flag to enable writes (safety check)'
    )
    apply_parser.add_argument(
        '--i-understand-this-will-write-to-tradervolt',
        action='store_true',
        help='Required confirmation for production writes'
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser(
        'cleanup', 
        help='Delete entities matching a prefix'
    )
    cleanup_parser.add_argument(
        '--prefix', '-p',
        default='MIG_TEST_',
        help='Prefix to match for deletion (default: MIG_TEST_)'
    )
    cleanup_parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be deleted without deleting'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Import commands here to avoid circular imports
    from commands.discover import run_discover
    from commands.plan import run_plan
    from commands.validate import run_validate
    from commands.apply import run_apply
    from commands.cleanup import run_cleanup
    
    try:
        if args.command == 'discover':
            sys.exit(run_discover(args))
            
        elif args.command == 'plan':
            sys.exit(run_plan(args))
            
        elif args.command == 'validate':
            sys.exit(run_validate(args))
            
        elif args.command == 'apply':
            sys.exit(run_apply(args))
            
        elif args.command == 'cleanup':
            sys.exit(run_cleanup(args))
            
        else:
            parser.print_help()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
