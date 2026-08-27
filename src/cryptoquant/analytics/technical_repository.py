"""
Technical Analysis Repository

Handles database persistence for technical analysis results.

Responsibilities:
- Insert/update TechnicalAnalysis records
- Handle duplicate key errors (UPSERT logic)
- Query latest analysis results
- Manage transaction rollback on errors
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cryptoquant.database.models import TechnicalAnalysis

logger = logging.getLogger(__name__)


def save_technical_analysis(
    session: Session,
    market_price_id: int,
    trading_pair_id: int,
    timestamp: datetime,
    indicators: Dict[str, Optional[Decimal]],
    scores: Dict[str, Optional[Decimal]],
    signal: Optional[str],
    calculation_version: str = 'v1'
) -> Optional[TechnicalAnalysis]:
    """
    Insert or update technical analysis result.
    
    Uses UPSERT logic:
    - If market_price_id already exists: UPDATE
    - If not: INSERT
    
    Args:
        session: SQLAlchemy session
        market_price_id: Foreign key to market_prices (authoritative relationship)
        trading_pair_id: Denormalized for query performance
        timestamp: Denormalized for query performance
        indicators: Dictionary from calculate_all_indicators()
        scores: Dictionary from calculate_scores()
        signal: Output from calculate_signal() ('BUY', 'HOLD', 'AVOID', or None)
        calculation_version: Version string (default: 'v1')
        
    Returns:
        TechnicalAnalysis object if successful, None on error
        
    Example:
        analysis = save_technical_analysis(
            session,
            market_price_id=12345,
            trading_pair_id=1,
            timestamp=datetime(2026, 8, 24, 10, 0),
            indicators={'ema_200': Decimal('104500'), ...},
            scores={'ema_score': None, ...},
            signal=None
        )
    """
    try:
        # Check if analysis already exists for this market_price_id
        existing = session.query(TechnicalAnalysis).filter(
            TechnicalAnalysis.market_price_id == market_price_id
        ).first()
        
        if existing:
            # UPDATE existing record
            existing.trading_pair_id = trading_pair_id
            existing.timestamp = timestamp
            existing.ema_200 = indicators.get('ema_200')
            existing.rsi_14 = indicators.get('rsi_14')
            existing.macd = indicators.get('macd')
            existing.macd_signal = indicators.get('macd_signal')
            existing.macd_histogram = indicators.get('macd_histogram')
            existing.atr_14 = indicators.get('atr_14')
            existing.ema_score = scores.get('ema_score')
            existing.rsi_score = scores.get('rsi_score')
            existing.macd_score = scores.get('macd_score')
            existing.atr_score = scores.get('atr_score')
            existing.technical_score = scores.get('technical_score')
            existing.signal = signal
            existing.calculation_version = calculation_version
            # calculated_at updates automatically via onupdate
            
            logger.debug(
                "Updated technical analysis for market_price_id=%d",
                market_price_id
            )
            
            return existing
        else:
            # INSERT new record
            analysis = TechnicalAnalysis(
                market_price_id=market_price_id,
                trading_pair_id=trading_pair_id,
                timestamp=timestamp,
                ema_200=indicators.get('ema_200'),
                rsi_14=indicators.get('rsi_14'),
                macd=indicators.get('macd'),
                macd_signal=indicators.get('macd_signal'),
                macd_histogram=indicators.get('macd_histogram'),
                atr_14=indicators.get('atr_14'),
                ema_score=scores.get('ema_score'),
                rsi_score=scores.get('rsi_score'),
                macd_score=scores.get('macd_score'),
                atr_score=scores.get('atr_score'),
                technical_score=scores.get('technical_score'),
                signal=signal,
                calculation_version=calculation_version
            )
            
            session.add(analysis)
            
            logger.debug(
                "Inserted technical analysis for market_price_id=%d",
                market_price_id
            )
            
            return analysis
            
    except IntegrityError as e:
        session.rollback()
        logger.error(
            "Integrity error saving technical analysis for market_price_id=%d: %s",
            market_price_id,
            e
        )
        return None
    except Exception as e:
        session.rollback()
        logger.error(
            "Error saving technical analysis for market_price_id=%d: %s",
            market_price_id,
            e
        )
        return None


def get_latest_analysis(
    session: Session,
    trading_pair_id: int,
    limit: int = 100
) -> List[TechnicalAnalysis]:
    """
    Get most recent technical analysis results for a trading pair.
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Trading pair to query
        limit: Maximum number of results to return
        
    Returns:
        List of TechnicalAnalysis objects ordered by timestamp DESC
        
    Example:
        latest = get_latest_analysis(session, trading_pair_id=1, limit=10)
        for analysis in latest:
            print(f"{analysis.timestamp}: EMA={analysis.ema_200}, RSI={analysis.rsi_14}")
    """
    try:
        results = (
            session.query(TechnicalAnalysis)
            .filter(TechnicalAnalysis.trading_pair_id == trading_pair_id)
            .order_by(TechnicalAnalysis.timestamp.desc())
            .limit(limit)
            .all()
        )
        
        logger.debug(
            "Retrieved %d analysis results for trading_pair_id=%d",
            len(results),
            trading_pair_id
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "Error retrieving latest analysis for trading_pair_id=%d: %s",
            trading_pair_id,
            e
        )
        return []


def get_analysis_by_timestamp(
    session: Session,
    trading_pair_id: int,
    timestamp: datetime
) -> Optional[TechnicalAnalysis]:
    """
    Get technical analysis for a specific timestamp.
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Trading pair to query
        timestamp: Exact timestamp to lookup
        
    Returns:
        TechnicalAnalysis object or None if not found
        
    Example:
        analysis = get_analysis_by_timestamp(
            session,
            trading_pair_id=1,
            timestamp=datetime(2026, 8, 24, 10, 0)
        )
    """
    try:
        result = (
            session.query(TechnicalAnalysis)
            .filter(TechnicalAnalysis.trading_pair_id == trading_pair_id)
            .filter(TechnicalAnalysis.timestamp == timestamp)
            .first()
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Error retrieving analysis for trading_pair_id=%d at %s: %s",
            trading_pair_id,
            timestamp,
            e
        )
        return None


def delete_analysis_for_version(
    session: Session,
    calculation_version: str
) -> int:
    """
    Delete all technical analysis records for a specific calculation version.
    
    Used when migrating from one version to another (e.g., v1 → v2).
    
    Args:
        session: SQLAlchemy session
        calculation_version: Version to delete (e.g., 'v1')
        
    Returns:
        Number of records deleted
        
    Warning: This is a destructive operation. Use carefully.
    
    Example:
        # Migrate to v2: delete all v1 records
        deleted_count = delete_analysis_for_version(session, 'v1')
        logger.info(f"Deleted {deleted_count} v1 records")
        # Then recalculate with v2 logic
    """
    try:
        count = (
            session.query(TechnicalAnalysis)
            .filter(TechnicalAnalysis.calculation_version == calculation_version)
            .delete()
        )
        
        session.commit()
        
        logger.warning(
            "Deleted %d technical analysis records for version='%s'",
            count,
            calculation_version
        )
        
        return count
        
    except Exception as e:
        session.rollback()
        logger.error(
            "Error deleting analysis for version='%s': %s",
            calculation_version,
            e
        )
        return 0


def count_analysis_records(
    session: Session,
    trading_pair_id: Optional[int] = None
) -> int:
    """
    Count total technical analysis records.
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Optional filter by trading pair
        
    Returns:
        Total count of records
        
    Example:
        total = count_analysis_records(session)
        btc_count = count_analysis_records(session, trading_pair_id=1)
    """
    try:
        query = session.query(TechnicalAnalysis)
        
        if trading_pair_id:
            query = query.filter(TechnicalAnalysis.trading_pair_id == trading_pair_id)
        
        count = query.count()
        
        return count
        
    except Exception as e:
        logger.error("Error counting analysis records: %s", e)
        return 0
