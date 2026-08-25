"""
Scoring Engine

Converts technical indicators into component scores and aggregate signals.

Phase 2: All scoring functions return None (placeholder)
Phase 3: Implement actual scoring rules and signal logic

Design:
- Scoring rules are NOT finalized yet
- This module provides the interface for Phase 3 implementation
- Do not invent arbitrary thresholds without domain expert input
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def calculate_scores(
    indicators: Dict[str, Optional[Decimal]]
) -> Dict[str, Optional[Decimal]]:
    """
    Calculate component scores from technical indicators.
    
    Args:
        indicators: Dictionary from calculate_all_indicators() containing:
            - ema_200
            - rsi_14
            - macd, macd_signal, macd_histogram
            - atr_14
        
    Returns:
        Dictionary with component scores:
        {
            'ema_score': Decimal or None,
            'rsi_score': Decimal or None,
            'macd_score': Decimal or None,
            'atr_score': Decimal or None,
            'technical_score': Decimal or None
        }
        
    Phase 2 Implementation:
        Returns None for all scores (placeholder for Phase 3)
        
    Phase 3 TODO:
        Implement scoring rules, e.g.:
        - ema_score: Compare price to EMA 200 (above = bullish, below = bearish)
        - rsi_score: Overbought/oversold scoring (>70 = -1, <30 = +1)
        - macd_score: Crossover detection (positive histogram = bullish)
        - atr_score: Volatility scoring (high volatility = risky)
        - technical_score: Weighted average of component scores
    """
    # Placeholder: Return None for all scores until Phase 3
    scores: Dict[str, Optional[Decimal]] = {
        'ema_score': None,
        'rsi_score': None,
        'macd_score': None,
        'atr_score': None,
        'technical_score': None
    }
    
    logger.debug("Scoring not implemented (Phase 3) - returning None for all scores")
    
    return scores


def calculate_signal(
    technical_score: Optional[Decimal]
) -> Optional[str]:
    """
    Determine BUY/HOLD/AVOID signal from technical score.
    
    Args:
        technical_score: Aggregate technical score (output from calculate_scores)
        
    Returns:
        Signal string: 'BUY', 'HOLD', or 'AVOID'
        Or None if scoring not implemented / score unavailable
        
    Phase 2 Implementation:
        Returns None (placeholder for Phase 3)
        
    Phase 3 TODO:
        Implement signal logic, e.g.:
        - BUY: technical_score > 0.5 (strong bullish)
        - HOLD: -0.5 <= technical_score <= 0.5 (neutral)
        - AVOID: technical_score < -0.5 (strong bearish)
    """
    # Placeholder: Return None until Phase 3
    logger.debug("Signal logic not implemented (Phase 3) - returning None")
    
    return None
