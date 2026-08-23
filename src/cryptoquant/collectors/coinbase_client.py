"""
Coinbase API Client

Production-ready client for Coinbase Advanced API with Ed25519 JWT authentication,
rate limiting, and error handling.
"""

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from requests.adapters import HTTPAdapter, Retry

from cryptoquant.collectors.models import Candle, CandleGranularity, Product, ProductsResponse
from cryptoquant.config.settings import get_settings

logger = logging.getLogger(__name__)


class CoinbaseAPIError(Exception):
    """Base exception for Coinbase API errors."""

    pass


class CoinbaseAuthenticationError(CoinbaseAPIError):
    """Raised when authentication fails."""

    pass


class CoinbaseRateLimitError(CoinbaseAPIError):
    """Raised when rate limit is exceeded."""

    pass


class CoinbaseClient:
    """
    Client for Coinbase Advanced API.

    Handles authentication, rate limiting, and provides methods for
    fetching market data.

    Example:
        >>> client = CoinbaseClient()
        >>> products = client.get_products()
        >>> candles = client.get_candles("BTC-USD", CandleGranularity.ONE_DAY, days=30)
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Coinbase API client with Ed25519 JWT authentication.

        Args:
            api_key: Coinbase API key name (e.g., organizations/.../apiKeys/...)
            api_secret: Base64-encoded Ed25519 private key
        """
        settings = get_settings()
        self.api_key = api_key or settings.coinbase_api_key
        self.api_secret = api_secret or settings.coinbase_api_secret
        self.base_url = settings.coinbase_base_url

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        logger.info("Coinbase client initialized with Ed25519 JWT authentication")

    def _build_jwt(self, request_method: str, request_path: str) -> str:
        """
        Generate JWT token for Ed25519 authentication.

        Args:
            request_method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path with query params

        Returns:
            JWT token string
        """
        import base64
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        # Generate unique request ID
        request_id = secrets.token_hex(16)
        
        # Create JWT claims - API v3 format
        uri = f"{request_method} {self.base_url.replace('https://', '').replace('http://', '')}{request_path}"
        
        payload = {
            "sub": self.api_key,
            "iss": "coinbase-cloud",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,
            "aud": ["cdp_service"],
            "uri": uri,
        }
        
        try:
            # Decode the base64-encoded Ed25519 private key (32 bytes)
            private_key_bytes = base64.b64decode(self.api_secret)
            
            # Extract the 32-byte seed
            private_key_seed = private_key_bytes[:32]
            
            # Create Ed25519 private key from seed
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_seed)
            
            # Serialize to PEM format (PyJWT requires PEM for EdDSA)
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')  # Decode to string
            
            # Create JWT token
            token = jwt.encode(
                payload,
                private_key_pem,
                algorithm="EdDSA",
                headers={"kid": self.api_key, "nonce": request_id},
            )
            
            # Ensure token is a string (PyJWT 2.x returns str, but be safe)
            if isinstance(token, bytes):
                token = token.decode('utf-8')
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to build JWT token: {e}", exc_info=True)
            raise CoinbaseAuthenticationError(f"Failed to build JWT token: {e}") from e

    def _make_request(self, method: str, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make authenticated request to Coinbase API using JWT.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "/api/v3/brokerage/products")
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            CoinbaseAuthenticationError: If authentication fails
            CoinbaseRateLimitError: If rate limit is exceeded
            CoinbaseAPIError: For other API errors
        """
        url = urljoin(self.base_url, endpoint)

        # Generate JWT token - DO NOT include query params in the JWT URI
        # Query params are sent separately in the request
        jwt_token = self._build_jwt(method.upper(), endpoint)

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                logger.error(f"Authentication failed: {response.text}")
                raise CoinbaseAuthenticationError(f"Invalid API credentials: {response.text}")

            if response.status_code == 429:
                logger.warning("Rate limit exceeded")
                raise CoinbaseRateLimitError("API rate limit exceeded")

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise CoinbaseAPIError(f"Request failed: {e}") from e

    def get_products(self, active_only: bool = True) -> list[Product]:
        """
        Get all tradeable products (trading pairs).

        Args:
            active_only: If True, only return active products

        Returns:
            List of Product objects

        Example:
            >>> client = CoinbaseClient()
            >>> products = client.get_products()
            >>> btc_usd = next(p for p in products if p.product_id == "BTC-USD")
            >>> print(f"{btc_usd.base_currency_id}-{btc_usd.quote_currency_id}")
        """
        logger.info("Fetching products from Coinbase API")
        endpoint = "/api/v3/brokerage/products"

        try:
            response_data = self._make_request("GET", endpoint)
            products_response = ProductsResponse(**response_data)

            products = products_response.products
            if active_only:
                products = [p for p in products if p.status == "online" and not p.trading_disabled]

            logger.info(f"Retrieved {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"Failed to fetch products: {e}")
            raise

    def get_candles(
        self,
        product_id: str,
        granularity: CandleGranularity = CandleGranularity.ONE_DAY,
        days: int = 30,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[Candle]:
        """
        Get historical candle data (OHLCV) for a product.

        Automatically chunks large requests to stay within Coinbase API limits (~300 candles per request).

        Args:
            product_id: Trading pair symbol (e.g., "BTC-USD")
            granularity: Candle time interval
            days: Number of days of historical data (if start/end not provided)
            start: Start timestamp (optional)
            end: End timestamp (optional)

        Returns:
            List of Candle objects

        Example:
            >>> client = CoinbaseClient()
            >>> candles = client.get_candles(
            ...     "BTC-USD",
            ...     CandleGranularity.ONE_HOUR,
            ...     days=7
            ... )
            >>> print(f"Latest close: {candles[-1].close}")
        """
        logger.info(f"Fetching candles for {product_id} ({granularity.value}, {days} days)")
        
        # Calculate time range
        if not end:
            end = datetime.now(timezone.utc)
        if not start:
            start = end - timedelta(days=days)

        # Determine max candles per request based on granularity
        # Coinbase API limit is ~300 candles per request
        granularity_limits = {
            CandleGranularity.ONE_MINUTE: 200,      # ~3.3 hours
            CandleGranularity.FIVE_MINUTE: 250,     # ~20.8 hours
            CandleGranularity.FIFTEEN_MINUTE: 280,  # ~2.9 days
            CandleGranularity.THIRTY_MINUTE: 280,   # ~5.8 days
            CandleGranularity.ONE_HOUR: 280,        # ~11.7 days
            CandleGranularity.TWO_HOUR: 280,        # ~23.3 days
            CandleGranularity.SIX_HOUR: 300,        # ~75 days
            CandleGranularity.ONE_DAY: 300,         # ~300 days
        }
        
        max_candles = granularity_limits.get(granularity, 300)
        
        # Calculate chunk size in seconds based on granularity
        granularity_seconds = {
            CandleGranularity.ONE_MINUTE: 60,
            CandleGranularity.FIVE_MINUTE: 300,
            CandleGranularity.FIFTEEN_MINUTE: 900,
            CandleGranularity.THIRTY_MINUTE: 1800,
            CandleGranularity.ONE_HOUR: 3600,
            CandleGranularity.TWO_HOUR: 7200,
            CandleGranularity.SIX_HOUR: 21600,
            CandleGranularity.ONE_DAY: 86400,
        }
        
        interval_seconds = granularity_seconds.get(granularity, 86400)
        chunk_duration_seconds = max_candles * interval_seconds
        
        # Check if we need to chunk the request
        total_duration = int((end - start).total_seconds())
        needs_chunking = total_duration > chunk_duration_seconds
        
        all_candles = []
        
        if needs_chunking:
            logger.info(f"Request spans {total_duration}s, chunking into {chunk_duration_seconds}s segments")
            current_start = start
            
            while current_start < end:
                current_end = min(current_start + timedelta(seconds=chunk_duration_seconds), end)
                
                logger.info(f"Fetching chunk: {current_start.date()} to {current_end.date()}")
                chunk_candles = self._fetch_candles_chunk(
                    product_id, granularity, current_start, current_end
                )
                all_candles.extend(chunk_candles)
                
                current_start = current_end
                
                # Small delay between chunks to avoid rate limiting
                if current_start < end:
                    time.sleep(0.5)
        else:
            all_candles = self._fetch_candles_chunk(product_id, granularity, start, end)
        
        # Sort by timestamp (oldest first) and remove duplicates
        all_candles.sort(key=lambda c: c.start)
        
        # Remove duplicates (can happen at chunk boundaries)
        unique_candles = []
        seen_timestamps = set()
        for candle in all_candles:
            if candle.start not in seen_timestamps:
                unique_candles.append(candle)
                seen_timestamps.add(candle.start)
        
        logger.info(f"Retrieved {len(unique_candles)} candles for {product_id}")
        return unique_candles
    
    def _fetch_candles_chunk(
        self,
        product_id: str,
        granularity: CandleGranularity,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """
        Fetch a single chunk of candles from the API.
        
        Args:
            product_id: Trading pair symbol
            granularity: Candle time interval
            start: Start timestamp
            end: End timestamp
            
        Returns:
            List of Candle objects
        """
        endpoint = f"/api/v3/brokerage/products/{product_id}/candles"
        
        params = {
            "granularity": granularity.value,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
        }

        try:
            response_data = self._make_request("GET", endpoint, params=params)

            # Parse candles from response
            candles = []
            for candle_data in response_data.get("candles", []):
                candle = Candle(
                    start=candle_data["start"],
                    low=candle_data["low"],
                    high=candle_data["high"],
                    open=candle_data["open"],
                    close=candle_data["close"],
                    volume=candle_data["volume"],
                )
                candles.append(candle)

            return candles

        except Exception as e:
            logger.error(f"Failed to fetch candles chunk for {product_id}: {e}")
            raise
