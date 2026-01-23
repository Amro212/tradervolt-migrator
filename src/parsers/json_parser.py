"""
JSON Parser for MT5 Symbol Configuration

Parses the symbols.json export from MT5.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def parse_symbols_json(file_path: str) -> List[Dict[str, Any]]:
    """Parse symbols.json and return list of symbol configurations."""
    path = Path(file_path)
    
    if not path.exists():
        logger.warning(f"File not found: {file_path}")
        return []
    
    # Try different encodings - MT5 exports are often UTF-16
    content = None
    for encoding in ['utf-16', 'utf-16-le', 'utf-8', 'latin-1']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if content is None:
        logger.error(f"Could not decode file: {file_path}")
        return []
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return []
    
    # Handle various nested structures from MT5 exports
    if isinstance(data, list):
        symbols = data
    elif isinstance(data, dict):
        # MT5 Server export: {"Server": [{"ConfigSymbols": [...]}]}
        if 'Server' in data:
            server_list = data['Server']
            if server_list and len(server_list) > 0:
                symbols = server_list[0].get('ConfigSymbols', [])
            else:
                symbols = []
        # Direct symbols array
        elif 'symbols' in data:
            symbols = data['symbols']
        elif 'ConfigSymbols' in data:
            symbols = data['ConfigSymbols']
        # Single symbol object
        elif 'Symbol' in data or 'Name' in data:
            symbols = [data]
        else:
            symbols = [data]
    else:
        logger.warning(f"Unexpected data format in {file_path}")
        return []
    
    parsed = []
    for sym in symbols:
        symbol = {
            'name': sym.get('Symbol', '') or sym.get('Name', '') or sym.get('symbol', ''),
            'description': sym.get('Description', '') or sym.get('description', ''),
            'path': sym.get('Path', '') or sym.get('path', ''),
            
            # Currency info
            'base_currency': sym.get('CurrencyBase', '') or sym.get('BaseCurrency', 'USD'),
            'quote_currency': sym.get('CurrencyProfit', '') or sym.get('QuoteCurrency', 'USD'),
            'margin_currency': sym.get('CurrencyMargin', ''),
            
            # Precision
            'digits': sym.get('Digits', 5),
            
            # Contract
            'contract_size': sym.get('ContractSize', 100000),
            'tick_size': sym.get('TickSize', 0.00001),
            'tick_value': sym.get('TickValue', 1.0),
            
            # Volume limits
            'volume_min': sym.get('VolumeMin', 0.01),
            'volume_max': sym.get('VolumeMax', 1000),
            'volume_step': sym.get('VolumeStep', 0.01),
            
            # Spread
            'spread': sym.get('Spread', 0),
            'spread_balance': sym.get('SpreadBalance', 0),
            'spread_fixed': sym.get('SpreadFixed', False),
            
            # Swap
            'swap_long': sym.get('SwapLong', 0.0),
            'swap_short': sym.get('SwapShort', 0.0),
            'swap_mode': sym.get('SwapMode', 1),
            
            # Margin
            'margin_initial': sym.get('MarginInitial', 0),
            'margin_maintenance': sym.get('MarginMaintenance', 0),
            'margin_rate_buy': sym.get('MarginRateBuy', 1.0),
            'margin_rate_sell': sym.get('MarginRateSell', 1.0),
            
            # Trading flags
            'trade_mode': sym.get('TradeMode', 4),  # TRADE_MODE_FULL
            'trade_execution': sym.get('TradeExecution', 0),
            
            # Store original for reference
            '_raw': sym
        }
        
        # Extract symbol group from path if available
        path = symbol['path']
        if path and '\\' in path:
            parts = path.split('\\')
            if len(parts) >= 2:
                symbol['group'] = parts[0]  # First path component is typically the group
        
        parsed.append(symbol)
    
    logger.info(f"Parsed {len(parsed)} symbols from {path}")
    return parsed


def get_symbol_groups(symbols: List[Dict[str, Any]]) -> List[str]:
    """Extract unique symbol groups from parsed symbols."""
    groups = set()
    for symbol in symbols:
        group = symbol.get('group', '')
        if group:
            groups.add(group)
        # Also check path for group hierarchy
        path = symbol.get('path', '')
        if path:
            parts = path.split('\\')
            if parts[0]:
                groups.add(parts[0])
    return sorted(list(groups))


def find_symbol_by_name(symbols: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    """Find a symbol by name (case-insensitive)."""
    name_lower = name.lower()
    for symbol in symbols:
        if symbol.get('name', '').lower() == name_lower:
            return symbol
    return {}
