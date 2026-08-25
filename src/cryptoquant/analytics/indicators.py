"""
Technical Indicators Calculator

Pure calculation functions for technical analysis indicators.
All functions are deterministic: same input → same output.

Indicators:
- EMA: Exponential Moving Average
- RSI: Relative Strength Index
- MACD: Moving Average Convergence Divergence
- ATR: Average True Range

Design principles:
- No database dependencies
- No side effects
- Returns None during warm-up period (insufficient data)
- Uses Decimal for precision
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from cryptoquant.database.models import MarketPrice

logger = logging.getLogger(__name__)


def calculate_ema(
    closes: List[Decimal],
    period: int
) -> Optional[Decimal]:
    """
    Calculate Exponential Moving Average.
    
    The EMA gives more weight to recent prices using an exponential decay.
    Formula: EMA_today = (Price_today × multiplier) + (EMA_yesterday × (1 - multiplier))
    Where multiplier = 2 / (period + 1)
    
    Args:
        closes: List of closing prices (oldest first)
        period: EMA period (e.g., 200 for EMA 200)
        
    Returns:
        EMA value for the last price, or None if insufficient data
        
    Warm-up: Requires at least `period` candles
    
    Example:
        closes = [Decimal('100'), Decimal('102'), Decimal('101'), ...]  # 200 values
        ema_200 = calculate_ema(closes, period=200)
    """
    if len(closes) < period:
        logger.debug(
            "Insufficient data for EMA %d: %d candles < %d required",
            period,
            len(closes),
            period
        )
        return None
    
    try:
        # Initialize EMA with SMA (Simple Moving Average) of first `period` values
        sma = sum(closes[:period]) / period
        ema = sma
        
        # Calculate multiplier
        multiplier = Decimal(2) / Decimal(period + 1)
        
        # Apply EMA formula to remaining values
        for close in closes[period:]:
            ema = (close * multiplier) + (ema * (Decimal(1) - multiplier))
        
        return ema.quantize(Decimal('0.00000001'))  # 8 decimal places
        
    except Exception as e:
        logger.error("Error calculating EMA %d: %s", period, e)
        return None


def calculate_rsi(
    closes: List[Decimal],
    period: int = 14
) -> Optional[Decimal]:
    """
    Calculate Relative Strength Index.
    
    RSI measures the magnitude of recent price changes to evaluate
    overbought (>70) or oversold (<30) conditions.
    
    Formula:
        RSI = 100 - (100 / (1 + RS))
        Where RS = Average Gain / Average Loss over `period` periods
    
    Args:
        closes: List of closing prices (oldest first)
        period: RSI period (default: 14)
        
    Returns:
        RSI value (0-100), or None if insufficient data
        
    Warm-up: Requires at least `period + 1` candles
    
    Example:
        closes = [Decimal('100'), Decimal('105'), ...]  # 15+ values
        rsi = calculate_rsi(closes, period=14)
    """
    if len(closes) < period + 1:
        logger.debug(
            "Insufficient data for RSI %d: %d candles < %d required",
            period,
            len(closes),
            period + 1
        )
        return None
    
    try:
        # Calculate price changes
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        # Separate gains and losses
        gains = [change if change > 0 else Decimal(0) for change in changes]
        losses = [-change if change < 0 else Decimal(0) for change in changes]
        
        # Calculate initial average gain and loss (SMA)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # Apply Wilder's smoothing to remaining values
        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        
        # Calculate RSI
        if avg_loss == 0:
            rsi = Decimal(100)  # No losses = maximum RSI
        else:
            rs = avg_gain / avg_loss
            rsi = Decimal(100) - (Decimal(100) / (Decimal(1) + rs))
        
        return rsi.quantize(Decimal('0.01'))  # 2 decimal places
        
    except Exception as e:
        logger.error("Error calculating RSI %d: %s", period, e)
        return None


def calculate_macd(
    closes: List[Decimal],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Optional[Tuple[Decimal, Decimal, Decimal]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    MACD shows the relationship between two EMAs of a security's price.
    
    Components:
        - MACD Line = EMA(fast) - EMA(slow)
        - Signal Line = EMA(MACD Line, signal)
        - Histogram = MACD Line - Signal Line
    
    Args:
        closes: List of closing prices (oldest first)
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)
        
    Returns:
        (macd_line, signal_line, histogram) or None if insufficient data
        
    Warm-up: Requires at least `slow + signal` candles (26 + 9 = 35 for defaults)
    
    Example:
        closes = [Decimal('100'), ...]  # 35+ values
        macd, signal, hist = calculate_macd(closes)
    """
    required = slow + signal
    if len(closes) < required:
        logger.debug(
            "Insufficient data for MACD (%d,%d,%d): %d candles < %d required",
            fast,
            slow,
            signal,
            len(closes),
            required
        )
        return None
    
    try:
        # Calculate fast and slow EMAs for all data points
        macd_line_values = []
        
        for i in range(slow - 1, len(closes)):
            # Get window for EMAs
            window = closes[:i+1]
            
            # Calculate EMAs
            ema_fast = calculate_ema(window, period=fast)
            ema_slow = calculate_ema(window, period=slow)
            
            if ema_fast is None or ema_slow is None:
                continue
                
            # MACD line = Fast EMA - Slow EMA
            macd_value = ema_fast - ema_slow
            macd_line_values.append(macd_value)
        
        # Need at least `signal` MACD values to calculate signal line
        if len(macd_line_values) < signal:
            logger.debug(
                "Insufficient MACD values for signal line: %d < %d",
                len(macd_line_values),
                signal
            )
            return None
        
        # Calculate signal line (EMA of MACD line)
        signal_line = calculate_ema(macd_line_values, period=signal)
        
        if signal_line is None:
            return None
        
        # Get final MACD line value
        macd_line = macd_line_values[-1]
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        return (
            macd_line.quantize(Decimal('0.00000001')),
            signal_line.quantize(Decimal('0.00000001')),
            histogram.quantize(Decimal('0.00000001'))
        )
        
    except Exception as e:
        logger.error("Error calculating MACD (%d,%d,%d): %s", fast, slow, signal, e)
        return None


def calculate_atr(
    highs: List[Decimal],
    lows: List[Decimal],
    closes: List[Decimal],
    period: int = 14
) -> Optional[Decimal]:
    """
    Calculate Average True Range.
    
    ATR measures market volatility by decomposing the entire range of an asset
    price for that period. Higher ATR = higher volatility.
    
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = EMA of True Range
    
    Args:
        highs: List of high prices (oldest first)
        lows: List of low prices (oldest first)
        closes: List of closing prices (oldest first)
        period: ATR period (default: 14)
        
    Returns:
        ATR value, or None if insufficient data
        
    Warm-up: Requires at least `period + 1` candles
    
    Example:
        highs = [Decimal('105'), Decimal('108'), ...]
        lows = [Decimal('95'), Decimal('98'), ...]
        closes = [Decimal('100'), Decimal('105'), ...]  # 15+ values
        atr = calculate_atr(highs, lows, closes, period=14)
    """
    if len(highs) != len(lows) or len(highs) != len(closes):
        logger.error(
            "Mismatched data lengths: highs=%d, lows=%d, closes=%d",
            len(highs),
            len(lows),
            len(closes)
        )
        return None
    
    if len(closes) < period + 1:
        logger.debug(
            "Insufficient data for ATR %d: %d candles < %d required",
            period,
            len(closes),
            period + 1
        )
        return None
    
    try:
        # Calculate true ranges
        true_ranges = []
        
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i-1]
            
            # True Range = max of three values
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Calculate ATR as EMA of true ranges
        atr = calculate_ema(true_ranges, period=period)
        
        return atr.quantize(Decimal('0.00000001')) if atr else None
        
    except Exception as e:
        logger.error("Error calculating ATR %d: %s", period, e)
        return None


def calculate_all_indicators(
    candles: List[MarketPrice]
) -> Dict[str, Optional[Decimal]]:
    """
    Calculate all Phase 2 technical indicators for a candle set.
    
    This is the main entry point for indicator calculation. It extracts
    OHLCV data from candles and calculates all indicators.
    
    Args:
        candles: List of MarketPrice objects (oldest first)
        
    Returns:
        Dictionary with indicator values:
        {
            'ema_200': Decimal or None,
            'rsi_14': Decimal or None,
            'macd': Decimal or None,
            'macd_signal': Decimal or None,
            'macd_histogram': Decimal or None,
            'atr_14': Decimal or None
        }
        
    Note: Returns None for indicators where insufficient data exists (warm-up period)
    
    Example:
        candles = get_candles_for_calculation(session, pair_id, timestamp, lookback=200)
        indicators = calculate_all_indicators(candles)
        if indicators['ema_200']:
            print(f"EMA 200: {indicators['ema_200']}")
    """
    indicators: Dict[str, Optional[Decimal]] = {
        'ema_200': None,
        'rsi_14': None,
        'macd': None,
        'macd_signal': None,
        'macd_histogram': None,
        'atr_14': None
    }
    
    if not candles:
        logger.warning("No candles provided for indicator calculation")
        return indicators
    
    try:
        # Extract OHLCV data
        closes = [candle.close for candle in candles]
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        
        # Calculate EMA 200
        indicators['ema_200'] = calculate_ema(closes, period=200)
        
        # Calculate RSI 14
        indicators['rsi_14'] = calculate_rsi(closes, period=14)
        
        # Calculate MACD (12,26,9)
        macd_result = calculate_macd(closes, fast=12, slow=26, signal=9)
        if macd_result:
            indicators['macd'], indicators['macd_signal'], indicators['macd_histogram'] = macd_result
        
        # Calculate ATR 14
        indicators['atr_14'] = calculate_atr(highs, lows, closes, period=14)
        
        # Log summary
        valid_count = sum(1 for v in indicators.values() if v is not None)
        logger.debug(
            "Calculated indicators: %d/%d valid",
            valid_count,
            len(indicators)
        )
        
        return indicators
        
    except Exception as e:
        logger.error("Error calculating indicators: %s", e)
        return indicators
