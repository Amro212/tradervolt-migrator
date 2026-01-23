"""
TraderVolt API Client

Handles authentication, token refresh, rate limiting, and API calls.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
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
    """Manages access token lifecycle with automatic refresh."""
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.access_token_expires_at: Optional[datetime] = None
        self.refresh_token_expires_at: Optional[datetime] = None
        self.base_url = "https://api.tradervolt.com"
        
    def _parse_iso_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse ISO timestamp with various formats."""
        if not timestamp_str:
            return None
        try:
            # Handle high-precision timestamps like '2026-01-22T20:30:13.6607010+00:00'
            # Python's fromisoformat can't handle more than 6 decimal places
            import re
            # Truncate microseconds to 6 digits
            timestamp_str = re.sub(r'(\.\d{6})\d+', r'\1', timestamp_str)
            # Handle Z suffix
            timestamp_str = timestamp_str.replace('Z', '+00:00')
            return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None
    
    def load_token(self) -> bool:
        """Load token from environment variable or token.json file."""
        # Try environment variable first
        token = os.environ.get('TRADERVOLT_ACCESS_TOKEN')
        if token:
            self.access_token = token
            # Assume 5 min validity if loaded from env (will refresh on 401)
            self.access_token_expires_at = datetime.now(timezone.utc)
            logger.info("Loaded access token from TRADERVOLT_ACCESS_TOKEN env var")
            return True
        
        # Try token.json file in project root
        project_root = Path(__file__).parent.parent.parent
        token_file = project_root / 'token.json'
        if token_file.exists():
            try:
                with open(token_file, 'r') as f:
                    data = json.load(f)
                self.access_token = data.get('accessToken')
                self.refresh_token = data.get('refreshToken')
                self.access_token_expires_at = self._parse_iso_timestamp(
                    data.get('accessTokenExpiresAt', '')
                )
                self.refresh_token_expires_at = self._parse_iso_timestamp(
                    data.get('refreshTokenExpiresAt', '')
                )
                logger.info("Loaded tokens from token.json")
                return True
            except Exception as e:
                logger.warning(f"Failed to load token.json: {e}")
        
        # Try migration_files/api_v1_users_login_test.json as fallback
        test_token_file = project_root / 'migration_files' / 'api_v1_users_login_test.json'
        if test_token_file.exists():
            try:
                with open(test_token_file, 'r') as f:
                    data = json.load(f)
                self.access_token = data.get('accessToken')
                self.refresh_token = data.get('refreshToken')
                self.access_token_expires_at = self._parse_iso_timestamp(
                    data.get('accessTokenExpiresAt', '')
                )
                self.refresh_token_expires_at = self._parse_iso_timestamp(
                    data.get('refreshTokenExpiresAt', '')
                )
                logger.info("Loaded tokens from migration_files/api_v1_users_login_test.json")
                return True
            except Exception as e:
                logger.warning(f"Failed to load test token file: {e}")
        
        return False
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired or will expire within 60 seconds."""
        if not self.access_token_expires_at:
            return True
        # Add 60 second buffer for safety
        buffer_time = datetime.now(timezone.utc)
        return self.access_token_expires_at <= buffer_time
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/users/refresh_token",
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
                logger.info("Successfully refreshed access token")
                return True
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        if self.is_token_expired():
            if not self.refresh_access_token():
                # If refresh fails, return current token anyway (might still work)
                logger.warning("Using potentially expired token")
        return self.access_token


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
        
        # Load token
        if not self.token_manager.load_token():
            logger.warning("No token loaded - API calls will fail until token is provided")
    
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
