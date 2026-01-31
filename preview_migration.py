#!/usr/bin/env python3
"""
Migration Preview - Compare converted MT5 data with TraderVolt format
Shows exactly what will be sent to the API vs what exists in discovery
"""

import json
from pathlib import Path
from src.parsers.htm_parser import parse_accounts, parse_clients, parse_orders, parse_positions

# TraderVolt group IDs
DEMO_GROUP = 'd3c9f1e8-ec2f-421b-8c3f-57eb5a0c3c9f'
REAL_GROUP = 'cfd69018-9475-4ed6-a63f-63e6230d0b68'
ROOT_GROUP = '9c6b651e-bbe6-4b2a-bed3-84aabe05e19b'

def get_group_id(mt5_group: str) -> tuple:
    mt5_group = mt5_group.lower()
    if mt5_group.startswith('demo\\'):
        return DEMO_GROUP, 'demo', 'DEMO'
    elif mt5_group.startswith('real\\'):
        return REAL_GROUP, 'real', 'REAL'
    return ROOT_GROUP, 'real', 'ROOT'


def build_trader_payload(account: dict, client: dict = None) -> dict:
    """Build the EXACT payload that will be sent to POST /api/v1/traders"""
    c = client or {}
    mt5_group = account.get('group', '')
    group_id, trade_type, _ = get_group_id(mt5_group)
    
    # This matches TraderVolt's expected schema exactly
    return {
        "firstName": account.get('name', ''),
        "lastName": account.get('last_name', '') or c.get('last_name', '') or account.get('name', ''),
        "middleName": account.get('middle_name', '') or c.get('middle_name', '') or None,
        "email": account.get('email', ''),
        "phone": account.get('phone', '') or c.get('phone', '') or None,
        "mobile": None,
        "country": account.get('country', '') or c.get('country', '') or None,
        "city": account.get('city', '') or c.get('city', '') or None,
        "state": account.get('state', '') or c.get('state', '') or None,
        "street": account.get('address', '') or c.get('street', '') or None,
        "postcode": account.get('postcode', '') or c.get('postcode', '') or None,
        "leverage": account.get('leverage', 100),
        "tradeType": trade_type.capitalize(),  # "Demo" or "Real"
        "tradersGroupId": group_id,
        "birthDate": c.get('birth_date', '') or None,
        "citizenship": c.get('citizenship', '') or None,
        "taxId": c.get('tax_id', '') or None,
        "documentType": c.get('document_type', '') or "None",
        "leadCampaign": account.get('lead_campaign', '') or c.get('lead_campaign', '') or None,
        "leadSource": account.get('lead_source', '') or c.get('lead_source', '') or None,
        "notes": json.dumps({"mt5_login": account.get('login'), "mt5_group": mt5_group}),
        "password": "TempPass123!",  # Will be set by system
        "isEnabled": True,
    }


def main():
    # Load discovery data
    discovery_path = Path('out/discovery/traders.json')
    discovery_data = json.loads(discovery_path.read_text())
    existing_traders = discovery_data.get('data', [])
    
    # Parse MT5 data
    accounts = parse_accounts('migration_files/Accounts.htm')
    clients = parse_clients('migration_files/Clients.htm')
    
    # Filter out managers
    accounts = [a for a in accounts if not a.get('group', '').startswith('managers\\')]
    
    # Build client lookup
    client_by_id = {str(c.get('id', '')): c for c in clients}
    
    print("=" * 70)
    print("MIGRATION PREVIEW - TraderVolt API Payload Comparison")
    print("=" * 70)
    
    # Show existing traders in TraderVolt
    print(f"\n📋 EXISTING TRADERS IN TRADERVOLT ({len(existing_traders)} total):")
    print("-" * 70)
    for t in existing_traders:
        print(f"  • {t.get('firstName', '')} {t.get('lastName', '')} | {t.get('email', '')} | {t.get('tradeType', '')}")
    
    # Build payloads for new traders
    payloads = []
    for acc in accounts:
        login = str(acc.get('login', ''))
        client = client_by_id.get(login, {})
        payload = build_trader_payload(acc, client)
        payload['_mt5_login'] = acc.get('login')
        payload['_mt5_balance'] = acc.get('balance', 0)
        payloads.append(payload)
    
    print(f"\n📤 NEW TRADERS TO MIGRATE ({len(payloads)} total):")
    print("-" * 70)
    
    # Group by trade type
    demo_traders = [p for p in payloads if p['tradeType'] == 'Demo']
    real_traders = [p for p in payloads if p['tradeType'] == 'Real' and p['tradersGroupId'] == REAL_GROUP]
    root_traders = [p for p in payloads if p['tradersGroupId'] == ROOT_GROUP]
    
    print(f"\n  DEMO GROUP ({len(demo_traders)} traders):")
    for p in demo_traders[:5]:
        print(f"    → {p['firstName']} {p['lastName']} | {p['email']} | Lev:{p['leverage']} | Bal:${p['_mt5_balance']:.2f}")
    if len(demo_traders) > 5:
        print(f"    ... and {len(demo_traders) - 5} more")
    
    print(f"\n  REAL GROUP ({len(real_traders)} traders):")
    for p in real_traders:
        print(f"    → {p['firstName']} {p['lastName']} | {p['email']} | Lev:{p['leverage']} | Bal:${p['_mt5_balance']:.2f}")
    
    if root_traders:
        print(f"\n  ROOT GROUP ({len(root_traders)} traders):")
        for p in root_traders:
            print(f"    → {p['firstName']} {p['lastName']} | {p['email']} | Lev:{p['leverage']} | Bal:${p['_mt5_balance']:.2f}")
    
    # Show sample payload
    print("\n" + "=" * 70)
    print("📝 SAMPLE API PAYLOAD (what will be sent to POST /api/v1/traders):")
    print("=" * 70)
    
    sample = payloads[0].copy()
    del sample['_mt5_login']
    del sample['_mt5_balance']
    print(json.dumps(sample, indent=2))
    
    # Compare with discovery schema
    print("\n" + "=" * 70)
    print("🔍 SCHEMA COMPARISON:")
    print("=" * 70)
    
    if existing_traders:
        discovery_fields = set(existing_traders[0].keys())
        our_fields = set(sample.keys())
        
        # Fields we send that exist in discovery
        valid_fields = our_fields & discovery_fields
        print(f"\n  ✅ Valid fields we send ({len(valid_fields)}):")
        print(f"     {', '.join(sorted(valid_fields))}")
        
        # Fields we send that DON'T exist in discovery (could be rejected)
        unknown_fields = our_fields - discovery_fields
        if unknown_fields:
            print(f"\n  ⚠️  Fields not in discovery (may be creation-only):")
            print(f"     {', '.join(sorted(unknown_fields))}")
        
        # Required fields from discovery we're NOT sending
        # These are typically set by the system
        system_fields = {'id', 'userId', 'traderNumber', 'traderPath', 'financialStatus', 
                        'loginId', 'status', 'kycVerificationStatus', 'lastLogin', 
                        'lastTradeDate', 'createdAt', 'updatedAt', 'currencyDigits',
                        'liquidationType', 'complianceApprovedBy', 'complianceApprovalDate'}
        
        optional_not_sent = discovery_fields - our_fields - system_fields
        if optional_not_sent:
            print(f"\n  ℹ️  Optional fields we're not sending:")
            print(f"     {', '.join(sorted(optional_not_sent))}")
    
    # Save preview files
    output_dir = Path('out/preview')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save clean payloads (without internal fields)
    clean_payloads = []
    for p in payloads:
        clean = {k: v for k, v in p.items() if not k.startswith('_')}
        clean_payloads.append(clean)
    
    (output_dir / 'traders_to_create.json').write_text(json.dumps(clean_payloads, indent=2))
    
    print(f"\n💾 Preview saved to: out/preview/traders_to_create.json")
    print("\n" + "=" * 70)
    print("Review the payload above. If it looks correct, run the actual migration.")
    print("=" * 70)


if __name__ == '__main__':
    main()
