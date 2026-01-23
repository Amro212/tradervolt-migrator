"""
TraderVolt API Client

Handles authentication, token refresh, rate limiting, and API calls.
Automatically logs in using credentials from environment variables.
"""

import os
import json
import time
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TokenManager:
    """
    Manages access token lifecycle with automatic login and refresh.
    
    Authentication flow:
    1. Try to load cached token from out/token.json
    2. If valid (not expired), use it
    3. If expired, try to refresh using refresh token
    4. If refresh fails or no cached token, login with credentials from env vars
    5. Cache new tokens to out/token.json for next run
    """
    
    BASE_URL = "https://api.tradervolt.com"
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.access_token_expires_at: Optional[datetime] = None
        self.refresh_token_expires_at: Optional[datetime] = None
        
        # Determine token cache path
        self.project_root = Path(__file__).parent.parent.parent
        self.token_cache_path = self.project_root / 'out' / 'token.json'
    
    def _parse_iso_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse ISO timestamp with various formats."""
        if not timestamp_str:
            return None
        try:
            # Handle high-precision timestamps (>6 decimal places)
            timestamp_str = re.sub(r'(\.\d{6})\d+', r'\1', timestamp_str)
            timestamp_str = timestamp_str.replace('Z', '+00:00')
            return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None
    
    def _get_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Get credentials from environment variables."""
        email = os.environ.get('TRADERVOLT_EMAIL')
        password = os.environ.get('TRADERVOLT_PASSWORD')
        return email, password
    
    def _save_token_cache(self) -> None:
        """Save current tokens to cache file."""
        try:
            # Ensure out directory exists
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            cache_data = {
                'accessToken': self.access_token,
                'refreshToken': self.refresh_token,
                'accessTokenExpiresAt': self.access_token_expires_at.isoformat() if self.access_token_expires_at else None,
                'refreshTokenExpiresAt': self.refresh_token_expires_at.isoformat() if self.refresh_token_expires_at else None,
                'cachedAt': datetime.now(timezone.utc).isoformat(),
            }
            
            with open(self.token_cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Saved token cache to {self.token_cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")
    
    def _load_token_cache(self) -> bool:
        """Load tokens from cache file if valid."""
        if not self.token_cache_path.exists():
            return False
        
        try:
            with open(self.token_cache_path, 'r') as f:
                data = json.load(f)
            
            self.access_token = data.get('accessToken')
            self.refresh_token = data.get('refreshToken')
            self.access_token_expires_at = self._parse_iso_timestamp(
                data.get('accessTokenExpiresAt', '')
            )
            self.refresh_token_expires_at = self._parse_iso_timestamp(
                data.get('refreshTokenExpiresAt', '')
            )
            
            # Check if refresh token is still valid
            if self.refresh_token_expires_at:
                if self.refresh_token_expires_at <= datetime.now(timezone.utc):
                    logger.info("Cached refresh token expired, need to re-login")
                    return False
            
            logger.info("Loaded tokens from cache")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to load token cache: {e}")
            return False
    
    def login(self) -> bool:
        """Login using credentials from environment variables."""
        email, password = self._get_credentials()
        
        if not email or not password:
            logger.error("Missing credentials. Set TRADERVOLT_EMAIL and TRADERVOLT_PASSWORD environment variables.")
            return False
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/api/v1/users/login",
                json={
                    "username": email,
                    "password": password,
                    "rememberMe": True
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('accessToken')
                self.refresh_token = data.get('refreshToken')
                self.access_token_expires_at = self._parse_iso_timestamp(
                    data.get('accessTokenExpiresAt', '')
                )
                self.refresh_token_expires_at = self._parse_iso_timestamp(
                    data.get('refreshTokenExpiresAt', '')
                )
                
                # Cache for next run
                self._save_token_cache()
                
                logger.info("Successfully logged in to TraderVolt")
                return True
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('description', response.text)
                except:
                    error_msg = response.text
                logger.error(f"Login failed ({response.status_code}): {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired or will expire within 60 seconds."""
        if not self.access_token or not self.access_token_expires_at:
            return True
        buffer = timedelta(seconds=60)
        return self.access_token_expires_at <= (datetime.now(timezone.utc) + buffer)
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            logger.debug("No refresh token available")
            return False
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/api/v1/users/refresh_token",
                json={"refreshToken": self.refresh_token},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('accessToken')
                self.refresh_token = data.get('refreshToken', self.refresh_token)
                self.access_token_expires_at = self._parse_iso_timestamp(
                    data.get('accessTokenExpiresAt', '')
                )
                
                # Update cache
                self._save_token_cache()
                
                logger.info("Successfully refreshed access token")
                return True
            else:
                logger.debug(f"Token refresh failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.debug(f"Token refresh error: {e}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure we have a valid access token.
        Tries: cached token → refresh → login
        """
        # If we have a valid token, use it
        if self.access_token and not self.is_token_expired():
            return True
        
        # Try to load from cache
        if not self.access_token:
            self._load_token_cache()
        
        # If token is still valid after loading cache, use it
        if self.access_token and not self.is_token_expired():
            return True
        
        # Try to refresh
        if self.refresh_token and self.refresh_access_token():
            return True
        
        # Fall back to login
        return self.login()
    
    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, authenticating if necessary."""
        if self.ensure_authenticated():
            return self.access_token
        return None


class RateLimiter:
    """Simple rate limiter with configurable requests per second."""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()


class TraderVoltClient:
    """TraderVolt REST API client with auth, rate limiting, and retry logic."""
    
    BASE_URL = "https://api.tradervolt.com"
    
    # API endpoints for each entity type
    ENDPOINTS = {
        'symbols-groups': '/api/v1/symbols-groups',
        'symbols': '/api/v1/symbols',
        'traders-groups': '/api/v1/traders-groups',
        'traders': '/api/v1/traders',
        'orders': '/api/v1/orders',
        'positions': '/api/v1/positions',
        'deals': '/api/v1/deals',
    }
    
    def __init__(self, rate_limit: float = 1.0):
        self.token_manager = TokenManager()
        self.rate_limiter = RateLimiter(rate_limit)
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with current access token."""
        token = self.token_manager.get_valid_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an API request with rate limiting and auth."""
        self.rate_limiter.wait()
        
        url = urljoin(self.BASE_URL, endpoint)
        headers = self._get_headers()
        headers.update(kwargs.pop('headers', {}))
        
        logger.debug(f"{method} {url}")
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=30,
            **kwargs
        )
        
        # Log response
        logger.debug(f"Response: {response.status_code}")
        
        return response
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a GET request."""
        return self._request('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, data: Dict[str, Any], **kwargs) -> requests.Response:
        """Make a POST request."""
        return self._request('POST', endpoint, json=data, **kwargs)
    
    def put(self, endpoint: str, data: Dict[str, Any], **kwargs) -> requests.Response:
        """Make a PUT request."""
        return self._request('PUT', endpoint, json=data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a DELETE request."""
        return self._request('DELETE', endpoint, **kwargs)
    
    # Convenience methods for each entity type
    
    def get_endpoint(self, entity_type: str) -> str:
        """Get the API endpoint for an entity type."""
        if entity_type not in self.ENDPOINTS:
            raise ValueError(f"Unknown entity type: {entity_type}")
        return self.ENDPOINTS[entity_type]
    
    def list_entities(self, entity_type: str) -> Tuple[int, List[Dict[str, Any]]]:
        """List all entities of a given type. Returns (status_code, data)."""
        endpoint = self.get_endpoint(entity_type)
        response = self.get(endpoint)
        
        if response.status_code == 200:
            return response.status_code, response.json()
        elif response.status_code == 204:
            return response.status_code, []
        else:
            return response.status_code, []
    
    def get_entity(self, entity_type: str, entity_id: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Get a single entity by ID. Returns (status_code, data)."""
        endpoint = f"{self.get_endpoint(entity_type)}/{entity_id}"
        response = self.get(endpoint)
        
        if response.status_code == 200:
            return response.status_code, response.json()
        else:
            return response.status_code, None
    
    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Tuple[int, Optional[Dict[str, Any]], str]:
        """Create an entity. Returns (status_code, data, error_message)."""
        endpoint = self.get_endpoint(entity_type)
        response = self.post(endpoint, data)
        
        if response.status_code == 201:
            return response.status_code, response.json(), ""
        else:
            try:
                error = response.json()
                error_msg = error.get('title', '') or error.get('detail', '') or str(error)
            except:
                error_msg = response.text
            return response.status_code, None, error_msg
    
    def delete_entity(self, entity_type: str, entity_id: str) -> Tuple[int, str]:
        """Delete an entity by ID. Returns (status_code, error_message)."""
        endpoint = f"{self.get_endpoint(entity_type)}/{entity_id}"
        response = self.delete(endpoint)
        
        if response.status_code in [200, 204]:
            return response.status_code, ""
        else:
            try:
                error = response.json()
                error_msg = error.get('title', '') or error.get('detail', '') or str(error)
            except:
                error_msg = response.text
            return response.status_code, error_msg
    
    def verify_entity(self, entity_type: str, entity_id: str, 
                      expected_fields: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Verify an entity exists and key fields match expectations.
        Returns (success, message, actual_data).
        """
        status_code, actual = self.get_entity(entity_type, entity_id)
        
        if status_code != 200 or actual is None:
            return False, f"Entity not found (status: {status_code})", None
        
        # Check expected fields
        mismatches = []
        for key, expected_value in expected_fields.items():
            actual_value = actual.get(key)
            if actual_value != expected_value:
                mismatches.append(f"{key}: expected '{expected_value}', got '{actual_value}'")
        
        if mismatches:
            return False, f"Field mismatches: {'; '.join(mismatches)}", actual
        
        return True, "Verification passed", actual
