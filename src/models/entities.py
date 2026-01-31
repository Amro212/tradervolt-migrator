"""
Data Models for Migration Entities

These dataclasses represent the entities we're migrating from MT5 to TraderVolt.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EntityType(Enum):
    """Entity types in order of dependency."""
    SYMBOLS_GROUPS = "symbols-groups"
    SYMBOLS = "symbols"
    TRADERS_GROUPS = "traders-groups"
    TRADERS = "traders"
    ORDERS = "orders"
    POSITIONS = "positions"
    DEALS = "deals"


@dataclass
class SymbolsGroup:
    """Symbol group configuration."""
    name: str
    description: Optional[str] = None
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        return {
            "name": self.name,
            "description": self.description or "",
        }


@dataclass
class Symbol:
    """Trading symbol configuration."""
    name: str
    description: str = ""
    baseCurrency: str = "USD"
    quoteCurrency: str = "USD"
    symbolsGroupId: Optional[str] = None
    
    # Additional fields from MT5
    digits: int = 2
    contractSize: float = 100000.0
    tickSize: float = 0.00001
    tickValue: float = 1.0
    spread: float = 0.0
    spreadBalance: float = 0.0
    spreadFixed: bool = False
    minVolume: float = 0.01
    maxVolume: float = 1000.0
    volumeStep: float = 0.01
    swapLong: float = 0.0
    swapShort: float = 0.0
    swapMode: int = 1
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        payload = {
            "name": self.name,
            "description": self.description,
            "baseCurrency": self.baseCurrency,
            "quoteCurrency": self.quoteCurrency,
            "digits": self.digits,
            "contractSize": self.contractSize,
            "tickSize": self.tickSize,
            "tickValue": self.tickValue,
            "spread": self.spread,
            "spreadBalance": self.spreadBalance,
            "spreadFixed": self.spreadFixed,
            "minVolume": self.minVolume,
            "maxVolume": self.maxVolume,
            "volumeStep": self.volumeStep,
            "swapLong": self.swapLong,
            "swapShort": self.swapShort,
            "swapMode": self.swapMode,
        }
        if self.symbolsGroupId:
            payload["symbolsGroupId"] = self.symbolsGroupId
        return payload


@dataclass
class TradersGroup:
    """Trader group configuration."""
    name: str
    description: Optional[str] = None
    leverage: float = 100.0
    marginMode: int = 0
    marginCallLevel: float = 100.0
    stopOutLevel: float = 50.0
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        return {
            "name": self.name,
            "description": self.description or "",
            "leverage": self.leverage,
            "marginMode": self.marginMode,
            "marginCallLevel": self.marginCallLevel,
            "stopOutLevel": self.stopOutLevel,
        }


@dataclass
class Trader:
    """Trader (account) configuration."""
    login: int
    firstName: str = ""
    lastName: str = ""
    email: str = ""
    phone: str = ""
    group: str = ""  # MT5 group path for reference
    tradersGroupId: Optional[str] = None  # TraderVolt UUID
    tradeType: str = "Demo"  # Demo or Real
    country: str = ""
    
    # Account details
    balance: float = 0.0
    credit: float = 0.0
    leverage: int = 100
    password: str = ""  # Will generate if not provided
    investorPassword: str = ""
    
    # Status
    isEnabled: bool = True
    isReadOnly: bool = False
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    # Legacy field for backwards compatibility
    name: str = ""
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        payload = {
            "firstName": self.firstName or self.name,
            "lastName": self.lastName or str(self.login),
            "email": self.email,
            "phone": self.phone,
            "country": self.country,
            "balance": self.balance,
            "credit": self.credit,
            "leverage": self.leverage,
            "tradeType": self.tradeType,
            "isEnabled": self.isEnabled,
            "isReadOnly": self.isReadOnly,
            # Include MT5 login as reference
            "mt5_login": self.login,
            "mt5_group": self.group,
        }
        if self.tradersGroupId:
            payload["tradersGroupId"] = self.tradersGroupId
        if self.password:
            payload["password"] = self.password
        if self.investorPassword:
            payload["investorPassword"] = self.investorPassword
        return payload


class OrderType(Enum):
    """Order types."""
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BUY_STOP_LIMIT = 6
    SELL_STOP_LIMIT = 7


class OrderState(Enum):
    """Order states."""
    STARTED = 0
    PLACED = 1
    CANCELED = 2
    PARTIAL = 3
    FILLED = 4
    REJECTED = 5
    EXPIRED = 6


@dataclass
class Order:
    """Trading order."""
    transactionId: int
    traderId: Optional[str] = None
    login: int = 0
    symbol: str = ""
    symbolId: Optional[str] = None
    
    orderType: int = 0  # OrderType enum value
    state: int = 1  # OrderState enum value
    
    volume: float = 0.0
    volumeCurrent: float = 0.0
    price: float = 0.0
    priceCurrent: float = 0.0
    stopLoss: float = 0.0
    takeProfit: float = 0.0
    
    timeSetup: Optional[str] = None  # ISO timestamp
    timeExpiration: Optional[str] = None
    timeDone: Optional[str] = None
    
    comment: str = ""
    externalId: Optional[str] = None
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        payload = {
            "transactionId": self.transactionId,
            "orderType": self.orderType,
            "state": self.state,
            "volume": self.volume,
            "volumeCurrent": self.volumeCurrent,
            "price": self.price,
            "priceCurrent": self.priceCurrent,
            "stopLoss": self.stopLoss,
            "takeProfit": self.takeProfit,
            "comment": self.comment,
            "symbol": self.symbol,
        }
        if self.traderId:
            payload["traderId"] = self.traderId
        if self.symbolId:
            payload["symbolId"] = self.symbolId
        if self.timeSetup:
            payload["timeSetup"] = self.timeSetup
        if self.timeExpiration:
            payload["timeExpiration"] = self.timeExpiration
        if self.timeDone:
            payload["timeDone"] = self.timeDone
        return payload


@dataclass
class Position:
    """Trading position."""
    transactionId: int
    traderId: Optional[str] = None
    login: int = 0
    symbol: str = ""
    symbolId: Optional[str] = None
    
    positionType: int = 0  # 0 = Long, 1 = Short
    volume: float = 0.0
    priceOpen: float = 0.0
    priceCurrent: float = 0.0
    priceStopLoss: float = 0.0
    priceTakeProfit: float = 0.0
    
    swap: float = 0.0
    profit: float = 0.0
    
    timeOpen: Optional[str] = None  # ISO timestamp
    timeUpdate: Optional[str] = None
    
    comment: str = ""
    externalId: Optional[str] = None
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        payload = {
            "transactionId": self.transactionId,
            "positionType": self.positionType,
            "volume": self.volume,
            "priceOpen": self.priceOpen,
            "priceCurrent": self.priceCurrent,
            "priceStopLoss": self.priceStopLoss,
            "priceTakeProfit": self.priceTakeProfit,
            "swap": self.swap,
            "profit": self.profit,
            "symbol": self.symbol,
            "comment": self.comment,
        }
        if self.traderId:
            payload["traderId"] = self.traderId
        if self.symbolId:
            payload["symbolId"] = self.symbolId
        if self.timeOpen:
            payload["timeOpen"] = self.timeOpen
        if self.timeUpdate:
            payload["timeUpdate"] = self.timeUpdate
        return payload


@dataclass
class Deal:
    """Trading deal (history record)."""
    transactionId: int
    traderId: Optional[str] = None
    login: int = 0
    orderId: Optional[str] = None
    positionId: Optional[str] = None
    symbol: str = ""
    symbolId: Optional[str] = None
    
    dealType: int = 0
    dealEntry: int = 0  # 0 = In, 1 = Out, 2 = InOut
    
    volume: float = 0.0
    price: float = 0.0
    
    swap: float = 0.0
    commission: float = 0.0
    profit: float = 0.0
    
    timeExecuted: Optional[str] = None  # ISO timestamp
    
    comment: str = ""
    externalId: Optional[str] = None
    
    id: Optional[str] = None  # Set by TraderVolt after creation
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to TraderVolt API payload format."""
        payload = {
            "transactionId": self.transactionId,
            "dealType": self.dealType,
            "dealEntry": self.dealEntry,
            "volume": self.volume,
            "price": self.price,
            "swap": self.swap,
            "commission": self.commission,
            "profit": self.profit,
            "symbol": self.symbol,
            "comment": self.comment,
        }
        if self.traderId:
            payload["traderId"] = self.traderId
        if self.orderId:
            payload["orderId"] = self.orderId
        if self.positionId:
            payload["positionId"] = self.positionId
        if self.symbolId:
            payload["symbolId"] = self.symbolId
        if self.timeExecuted:
            payload["timeExecuted"] = self.timeExecuted
        return payload


@dataclass
class MigrationMapping:
    """Mapping from source ID to target ID for an entity."""
    entity_type: str
    source_id: str  # e.g., MT5 ID or name
    target_id: str  # TraderVolt ID
    name: str = ""  # Human-readable name
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationPlan:
    """Complete migration plan with all entities."""
    timestamp: str
    test_mode: bool = False
    test_prefix: str = ""
    
    symbols_groups: List[SymbolsGroup] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    traders_groups: List[TradersGroup] = field(default_factory=list)
    traders: List[Trader] = field(default_factory=list)
    orders: List[Order] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    deals: List[Deal] = field(default_factory=list)
    
    def summary(self) -> Dict[str, int]:
        """Get summary counts."""
        return {
            "symbols_groups": len(self.symbols_groups),
            "symbols": len(self.symbols),
            "traders_groups": len(self.traders_groups),
            "traders": len(self.traders),
            "orders": len(self.orders),
            "positions": len(self.positions),
            "deals": len(self.deals),
        }
