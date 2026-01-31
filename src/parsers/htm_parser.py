"""
HTML Table Parser for MT5 Exports

Parses the HTML table exports from MT5 Manager.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


class HtmlTableParser:
    """Parser for MT5 HTML table exports."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.rows: List[Dict[str, str]] = []
        self.headers: List[str] = []
        
    def parse(self) -> List[Dict[str, str]]:
        """Parse the HTML file and return list of row dictionaries."""
        if not self.file_path.exists():
            logger.warning(f"File not found: {self.file_path}")
            return []
        
        # Try different encodings - MT5 exports are often UTF-16
        content = None
        for encoding in ['utf-16', 'utf-16-le', 'utf-8', 'latin-1']:
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if content is None:
            logger.warning(f"Could not decode file: {self.file_path}")
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            logger.warning(f"No table found in {self.file_path}")
            return []
        
        # Find header row
        header_row = table.find('tr')
        if not header_row:
            return []
        
        self.headers = [
            th.get_text(strip=True).replace('\xa0', ' ') 
            for th in header_row.find_all(['th', 'td'])
        ]
        
        # Parse data rows
        self.rows = []
        for row in table.find_all('tr')[1:]:  # Skip header
            cells = row.find_all('td')
            if len(cells) == len(self.headers):
                row_dict = {}
                for i, cell in enumerate(cells):
                    value = cell.get_text(strip=True).replace('\xa0', ' ')
                    row_dict[self.headers[i]] = value
                self.rows.append(row_dict)
        
        logger.info(f"Parsed {len(self.rows)} rows from {self.file_path.name}")
        return self.rows


def parse_clients(file_path: str) -> List[Dict[str, Any]]:
    """Parse Clients.htm and return structured client data."""
    parser = HtmlTableParser(file_path)
    rows = parser.parse()
    
    clients = []
    for row in rows:
        client = {
            'id': row.get('ID', ''),
            'name': row.get('Name', ''),
            'middle_name': row.get('Middle name', ''),
            'last_name': row.get('Second name', ''),
            'email': row.get('E-mail', '') or row.get('Email', ''),
            'phone': row.get('Phone', ''),
            'country': row.get('Country', ''),
            'city': row.get('City', ''),
            'street': row.get('Street', ''),
            'postcode': row.get('Postcode', ''),
            'state': row.get('State', ''),
            'birth_date': row.get('Birth Date', ''),
            'gender': row.get('Gender', ''),
            'citizenship': row.get('Citizenship', ''),
            'tax_id': row.get('Tax ID', ''),
            'document_type': row.get('Document Type', ''),
            'document_number': row.get('Document Number', ''),
            'status': row.get('Status', ''),
            'kyc_status': row.get('KYC Status', ''),
            'lead_campaign': row.get('Lead Campaign', ''),
            'lead_source': row.get('Lead Source', ''),
            'annual_income': row.get('Annual Income', ''),
            'net_worth': row.get('Net Worth', ''),
            'employment_status': row.get('Employment Status', ''),
            'comment': row.get('Comment', ''),
            '_raw': row
        }
        clients.append(client)
    
    return clients


def parse_accounts(file_path: str) -> List[Dict[str, Any]]:
    """Parse Accounts.htm and return structured account data."""
    parser = HtmlTableParser(file_path)
    rows = parser.parse()
    
    accounts = []
    for row in rows:
        # Parse login (primary key)
        login_str = row.get('Login', '0')
        try:
            login = int(login_str)
        except ValueError:
            login = 0
        
        # Parse numeric fields
        def parse_float(s: str) -> float:
            try:
                # Remove currency symbols and spaces
                s = re.sub(r'[^\d.-]', '', s)
                return float(s) if s else 0.0
            except:
                return 0.0
        
        def parse_int(s: str) -> int:
            try:
                s = re.sub(r'[^\d-]', '', s)
                return int(s) if s else 0
            except:
                return 0
        
        def parse_leverage(s: str) -> int:
            """Parse leverage from format like '1 : 100' -> 100 or plain '100' -> 100."""
            try:
                if ':' in s:
                    # Format is "1 : 100", extract the number after ':'
                    parts = s.split(':')
                    if len(parts) == 2:
                        return int(parts[1].strip())
                # Plain number format
                return int(re.sub(r'[^\d]', '', s)) if s else 100
            except:
                return 100
        
        account = {
            'login': login,
            'name': row.get('Name', ''),
            'last_name': row.get('Last name', ''),
            'middle_name': row.get('Middle name', ''),
            'group': row.get('Group', ''),
            'email': row.get('E-mail', '') or row.get('Email', ''),
            'phone': row.get('Phone', ''),
            'country': row.get('Country', ''),
            'city': row.get('City', ''),
            'state': row.get('State', ''),
            'postcode': row.get('ZIP', '') or row.get('Postcode', ''),
            'address': row.get('Address', ''),
            'balance': parse_float(row.get('Balance', '0')),
            'credit': parse_float(row.get('Credit', '0')),
            'equity': parse_float(row.get('Equity', '0')),
            'margin': parse_float(row.get('Margin', '0')),
            'margin_free': parse_float(row.get('Free Margin', '0')),
            'leverage': parse_leverage(row.get('Leverage', '100')),
            'language': row.get('Language', ''),
            'lead_campaign': row.get('Lead campaign', ''),
            'lead_source': row.get('Lead source', ''),
            'comment': row.get('Comment', ''),
            'registration': row.get('Registration', ''),
            'last_access': row.get('Last Access', ''),
            '_raw': row
        }
        accounts.append(account)
    
    return accounts


def parse_orders(file_path: str) -> List[Dict[str, Any]]:
    """Parse Orders.htm and return structured order data."""
    parser = HtmlTableParser(file_path)
    rows = parser.parse()
    
    orders = []
    for row in rows:
        def parse_float(s: str) -> float:
            try:
                s = re.sub(r'[^\d.-]', '', s)
                return float(s) if s else 0.0
            except:
                return 0.0
        
        def parse_int(s: str) -> int:
            try:
                s = re.sub(r'[^\d-]', '', s)
                return int(s) if s else 0
            except:
                return 0
        
        def parse_timestamp(s: str) -> Optional[str]:
            """Convert MT5 timestamp to ISO format."""
            if not s or s == '1970.01.01 00:00:00':
                return None
            try:
                # MT5 format: 2024.01.15 14:30:00
                dt = datetime.strptime(s, '%Y.%m.%d %H:%M:%S')
                return dt.isoformat() + 'Z'
            except:
                return s
        
        # Map order type from MT5 string
        type_str = row.get('Type', '').lower()
        order_type_map = {
            'buy': 0, 'sell': 1,
            'buy limit': 2, 'sell limit': 3,
            'buy stop': 4, 'sell stop': 5,
            'buy stop limit': 6, 'sell stop limit': 7,
        }
        order_type = order_type_map.get(type_str, 0)
        
        # Map state from MT5 string
        state_str = row.get('State', '').lower()
        state_map = {
            'started': 0, 'placed': 1, 'canceled': 2,
            'partial': 3, 'filled': 4, 'rejected': 5, 'expired': 6,
        }
        state = state_map.get(state_str, 1)
        
        order = {
            'order_id': parse_int(row.get('Order', '0')),
            'login': parse_int(row.get('Login', '0')),
            'position_id': parse_int(row.get('Position', '0')),
            'external_id': row.get('ID', ''),
            'symbol': row.get('Symbol', ''),
            'order_type': order_type,
            'state': state,
            'volume_initial': parse_float(row.get('Initial volume', '0')),
            'volume_current': parse_float(row.get('Current volume', '0')),
            'price': parse_float(row.get('Price', '0')),
            'trigger_price': parse_float(row.get('Trigger', '0')),
            'stop_loss': parse_float(row.get('S / L', '0') or row.get('Stop Loss', '0')),
            'take_profit': parse_float(row.get('T / P', '0') or row.get('Take Profit', '0')),
            'time_setup': parse_timestamp(row.get('Time', '')),
            'time_expiration': parse_timestamp(row.get('Expiration', '')),
            'reason': row.get('Reason', ''),
            'dealer': row.get('Dealer', ''),
            'comment': row.get('Comment', ''),
            '_raw': row
        }
        orders.append(order)
    
    return orders


def parse_positions(file_path: str) -> List[Dict[str, Any]]:
    """Parse Positions.htm and return structured position data."""
    parser = HtmlTableParser(file_path)
    rows = parser.parse()
    
    positions = []
    for row in rows:
        def parse_float(s: str) -> float:
            try:
                s = re.sub(r'[^\d.-]', '', s)
                return float(s) if s else 0.0
            except:
                return 0.0
        
        def parse_int(s: str) -> int:
            try:
                s = re.sub(r'[^\d-]', '', s)
                return int(s) if s else 0
            except:
                return 0
        
        def parse_timestamp(s: str) -> Optional[str]:
            """Convert MT5 timestamp to ISO format."""
            if not s or s == '1970.01.01 00:00:00':
                return None
            try:
                dt = datetime.strptime(s, '%Y.%m.%d %H:%M:%S')
                return dt.isoformat() + 'Z'
            except:
                return s
        
        # Map position type from MT5 string
        type_str = row.get('Type', '').lower()
        position_type = 0 if 'buy' in type_str else 1
        
        position = {
            'position_id': parse_int(row.get('Position', '0')),
            'login': parse_int(row.get('Login', '0')),
            'external_id': row.get('ID', ''),
            'symbol': row.get('Symbol', ''),
            'position_type': position_type,
            'volume': parse_float(row.get('Volume', '0')),
            'gateway_volume': parse_float(row.get('Gateway Volume', '0')),
            'price_open': parse_float(row.get('Price', '0')),
            'price_current': parse_float(row.get('Current Price', '0')),
            'stop_loss': parse_float(row.get('Stop Loss', '0')),
            'take_profit': parse_float(row.get('Take Profit', '0')),
            'swap': parse_float(row.get('Swap', '0')),
            'profit': parse_float(row.get('Profit', '0')),
            'reason': row.get('Reason', ''),
            'time_open': parse_timestamp(row.get('Time', '')),
            'comment': row.get('Comment', ''),
            '_raw': row
        }
        positions.append(position)
    
    return positions


def get_unique_groups_from_accounts(accounts: List[Dict[str, Any]]) -> List[str]:
    """Extract unique group names from accounts."""
    groups = set()
    for account in accounts:
        group = account.get('group', '')
        if group:
            groups.add(group)
    return sorted(list(groups))


def get_unique_symbols(orders: List[Dict[str, Any]], 
                       positions: List[Dict[str, Any]]) -> List[str]:
    """Extract unique symbol names from orders and positions."""
    symbols = set()
    for order in orders:
        symbol = order.get('symbol', '')
        if symbol:
            symbols.add(symbol)
    for position in positions:
        symbol = position.get('symbol', '')
        if symbol:
            symbols.add(symbol)
    return sorted(list(symbols))
