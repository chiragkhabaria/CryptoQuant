"""
Technical Analysis Pipeline

Orchestrates the end-to-end technical analysis workflow.

Workflow:
1. Query market data with lookback window
2. Calculate indicators (EMA, RSI, MACD, ATR)
3. Calculate scores and signal (Phase 3 placeholders)
4. Persist to technical_analysis table

Modes:
- Historical: Backfill analysis for a date range
- Incremental: Process new candles since last calculation
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from cryptoquant.database.models import MarketPrice, TechnicalAnalysis, TradingPair
from cryptoquant.database.session import get_session

from .indicators import calculate_all_indicators
from .market_data_reader import (
    get_candles_for_calculation,
    get_candles_range,
    get_last_analysis_timestamp,
    has_sufficient_data,
)
from .scoring import calculate_scores, calculate_signal
from .technical_repository import save_technical_analysis

logger = logging.getLogger(__name__)

# Warm-up configuration
MAX_LOOKBACK_PERIODS = 200  # EMA 200 requires 200 candles
GRANULARITY_ONE_HOUR = '3600'  # Seconds (1 hour)


def run_technical_analysis(
    trading_pair_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    incremental: bool = False,
    calculation_version: str = 'v1',
    session: Optional[Session] = None
) -> dict:
    """
    Run technical analysis for a trading pair.
    
    Modes:
        1. Historical backfill: Specify start_date and end_date
        2. Incremental: Set incremental=True (processes since last calculated)
        
    Args:
        trading_pair_id: Trading pair to analyze
        start_date: Start timestamp (historical mode)
        end_date: End timestamp (historical mode)
        incremental: Use incremental mode (default: False)
        calculation_version: Version string (default: 'v1')
        session: Optional SQLAlchemy session (creates new if None)
        
    Returns:
        Dictionary with summary statistics:
        {
            'mode': 'historical' or 'incremental',
            'trading_pair_id': int,
            'start_date': datetime,
            'end_date': datetime,
            'candles_processed': int,
            'candles_skipped_warmup': int,
            'analyses_saved': int,
            'errors': int,
            'success': bool
        }
        
    Example:
        # Historical backfill (30 days)
        result = run_technical_analysis(
            trading_pair_id=1,
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31)
        )
        
        # Incremental (process new candles)
        result = run_technical_analysis(
            trading_pair_id=1,
            incremental=True
        )
    """
    # Create session if not provided
    own_session = session is None
    if own_session:
        session = get_session()
    
    try:
        # Determine mode
        if incremental:
            return _run_incremental(
                session,
                trading_pair_id,
                calculation_version
            )
        else:
            if not start_date or not end_date:
                raise ValueError("start_date and end_date required for historical mode")
            
            return _run_historical(
                session,
                trading_pair_id,
                start_date,
                end_date,
                calculation_version
            )
    
    finally:
        if own_session:
            session.close()


def _run_historical(
    session: Session,
    trading_pair_id: int,
    start_date: datetime,
    end_date: datetime,
    calculation_version: str
) -> dict:
    """
    Historical backfill mode: Process all candles in date range.
    
    Algorithm:
    1. Fetch all candles in [start_date, end_date]
    2. For each candle:
        a. Fetch lookback window (up to 200 prior candles)
        b. Calculate indicators
        c. Calculate scores/signal (Phase 3 placeholder)
        d. Save to database
    3. Return summary statistics
    """
    logger.info(
        "Starting historical analysis: trading_pair_id=%d, range=%s to %s",
        trading_pair_id,
        start_date,
        end_date
    )
    
    stats = {
        'mode': 'historical',
        'trading_pair_id': trading_pair_id,
        'start_date': start_date,
        'end_date': end_date,
        'candles_processed': 0,
        'candles_skipped_warmup': 0,
        'analyses_saved': 0,
        'errors': 0,
        'success': False
    }
    
    try:
        # Fetch all candles in target range
        target_candles = get_candles_range(
            session,
            trading_pair_id,
            start_date,
            end_date
        )
        
        if not target_candles:
            logger.warning("No candles found in date range")
            stats['success'] = True  # No errors, just no data
            return stats
        
        logger.info("Found %d candles to process", len(target_candles))
        
        # Process each candle
        for target_candle in target_candles:
            try:
                stats['candles_processed'] += 1
                
                # Fetch lookback window for this candle
                lookback_candles = get_candles_for_calculation(
                    session,
                    trading_pair_id,
                    target_candle.timestamp,
                    lookback_periods=MAX_LOOKBACK_PERIODS,
                    granularity=GRANULARITY_ONE_HOUR
                )
                
                # Check if we have sufficient data for indicators
                if not has_sufficient_data(lookback_candles, MAX_LOOKBACK_PERIODS):
                    logger.debug(
                        "Skipping %s: insufficient lookback data (%d < %d)",
                        target_candle.timestamp,
                        len(lookback_candles),
                        MAX_LOOKBACK_PERIODS
                    )
                    stats['candles_skipped_warmup'] += 1
                    continue
                
                # Calculate indicators
                indicators = calculate_all_indicators(lookback_candles)
                
                # Calculate scores and signal (Phase 3 placeholders)
                scores = calculate_scores(indicators)
                signal = calculate_signal(scores.get('technical_score'))
                
                # Save to database
                analysis = save_technical_analysis(
                    session,
                    market_price_id=target_candle.id,
                    trading_pair_id=trading_pair_id,
                    timestamp=target_candle.timestamp,
                    indicators=indicators,
                    scores=scores,
                    signal=signal,
                    calculation_version=calculation_version
                )
                
                if analysis:
                    stats['analyses_saved'] += 1
                    
                    # Commit every 100 records for progress persistence
                    if stats['analyses_saved'] % 100 == 0:
                        session.commit()
                        logger.info(
                            "Progress: %d/%d processed, %d saved",
                            stats['candles_processed'],
                            len(target_candles),
                            stats['analyses_saved']
                        )
                else:
                    stats['errors'] += 1
                    logger.warning(
                        "Failed to save analysis for timestamp %s",
                        target_candle.timestamp
                    )
            
            except Exception as e:
                stats['errors'] += 1
                logger.error(
                    "Error processing candle at %s: %s",
                    target_candle.timestamp,
                    e
                )
        
        # Final commit
        session.commit()
        
        stats['success'] = True
        logger.info(
            "Historical analysis complete: %d processed, %d saved, %d skipped, %d errors",
            stats['candles_processed'],
            stats['analyses_saved'],
            stats['candles_skipped_warmup'],
            stats['errors']
        )
        
        return stats
    
    except Exception as e:
        session.rollback()
        logger.error("Historical analysis failed: %s", e)
        stats['success'] = False
        return stats


def _run_incremental(
    session: Session,
    trading_pair_id: int,
    calculation_version: str
) -> dict:
    """
    Incremental mode: Process only new candles since last calculation.
    
    Algorithm:
    1. Find last calculated timestamp
    2. Fetch all candles after that timestamp
    3. For each new candle:
        a. Fetch lookback window
        b. Calculate indicators
        c. Calculate scores/signal (Phase 3 placeholder)
        d. Save to database
    4. Return summary statistics
    """
    logger.info(
        "Starting incremental analysis: trading_pair_id=%d",
        trading_pair_id
    )
    
    stats = {
        'mode': 'incremental',
        'trading_pair_id': trading_pair_id,
        'start_date': None,
        'end_date': None,
        'candles_processed': 0,
        'candles_skipped_warmup': 0,
        'analyses_saved': 0,
        'errors': 0,
        'success': False
    }
    
    try:
        # Find last calculated timestamp
        last_timestamp = get_last_analysis_timestamp(session, trading_pair_id)
        
        if last_timestamp:
            logger.info("Last analysis timestamp: %s", last_timestamp)
            # Start from next hour after last calculation
            start_date = last_timestamp + timedelta(hours=1)
        else:
            logger.info("No prior analysis found - will process all available data")
            # Get first candle timestamp
            first_candle = (
                session.query(MarketPrice)
                .filter(MarketPrice.trading_pair_id == trading_pair_id)
                .order_by(MarketPrice.timestamp.asc())
                .first()
            )
            
            if not first_candle:
                logger.warning("No candles found for trading pair")
                stats['success'] = True
                return stats
            
            start_date = first_candle.timestamp
        
        # Get current time as end date
        end_date = datetime.utcnow()
        
        stats['start_date'] = start_date
        stats['end_date'] = end_date
        
        # Fetch new candles
        new_candles = get_candles_range(
            session,
            trading_pair_id,
            start_date,
            end_date
        )
        
        if not new_candles:
            logger.info("No new candles to process")
            stats['success'] = True
            return stats
        
        logger.info("Found %d new candles to process", len(new_candles))
        
        # Process each new candle (use same logic as historical)
        for target_candle in new_candles:
            try:
                stats['candles_processed'] += 1
                
                # Fetch lookback window
                lookback_candles = get_candles_for_calculation(
                    session,
                    trading_pair_id,
                    target_candle.timestamp,
                    lookback_periods=MAX_LOOKBACK_PERIODS,
                    granularity=GRANULARITY_ONE_HOUR
                )
                
                # Check warm-up
                if not has_sufficient_data(lookback_candles, MAX_LOOKBACK_PERIODS):
                    logger.debug(
                        "Skipping %s: insufficient lookback data",
                        target_candle.timestamp
                    )
                    stats['candles_skipped_warmup'] += 1
                    continue
                
                # Calculate indicators
                indicators = calculate_all_indicators(lookback_candles)
                
                # Calculate scores and signal
                scores = calculate_scores(indicators)
                signal = calculate_signal(scores.get('technical_score'))
                
                # Save to database
                analysis = save_technical_analysis(
                    session,
                    market_price_id=target_candle.id,
                    trading_pair_id=trading_pair_id,
                    timestamp=target_candle.timestamp,
                    indicators=indicators,
                    scores=scores,
                    signal=signal,
                    calculation_version=calculation_version
                )
                
                if analysis:
                    stats['analyses_saved'] += 1
                else:
                    stats['errors'] += 1
            
            except Exception as e:
                stats['errors'] += 1
                logger.error(
                    "Error processing candle at %s: %s",
                    target_candle.timestamp,
                    e
                )
        
        # Commit all changes
        session.commit()
        
        stats['success'] = True
        logger.info(
            "Incremental analysis complete: %d processed, %d saved, %d skipped, %d errors",
            stats['candles_processed'],
            stats['analyses_saved'],
            stats['candles_skipped_warmup'],
            stats['errors']
        )
        
        return stats
    
    except Exception as e:
        session.rollback()
        logger.error("Incremental analysis failed: %s", e)
        stats['success'] = False
        return stats


def analyze_all_pairs(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    incremental: bool = False,
    calculation_version: str = 'v1'
) -> dict:
    """
    Run technical analysis for all tracked trading pairs.
    
    Args:
        start_date: Start date for historical mode
        end_date: End date for historical mode
        incremental: Use incremental mode
        calculation_version: Version string
        
    Returns:
        Dictionary with summary for all pairs:
        {
            'total_pairs': int,
            'successful_pairs': int,
            'failed_pairs': int,
            'total_analyses_saved': int,
            'pair_results': [result1, result2, ...]
        }
        
    Example:
        # Backfill all pairs for July 2026
        results = analyze_all_pairs(
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31)
        )
        print(f"Analyzed {results['total_pairs']} pairs")
    """
    session = get_session()
    
    try:
        # Get all tracked pairs
        tracked_pairs = (
            session.query(TradingPair)
            .filter(TradingPair.is_tracked == True)
            .all()
        )
        
        if not tracked_pairs:
            logger.warning("No tracked trading pairs found")
            return {
                'total_pairs': 0,
                'successful_pairs': 0,
                'failed_pairs': 0,
                'total_analyses_saved': 0,
                'pair_results': []
            }
        
        logger.info("Analyzing %d tracked pairs", len(tracked_pairs))
        
        summary = {
            'total_pairs': len(tracked_pairs),
            'successful_pairs': 0,
            'failed_pairs': 0,
            'total_analyses_saved': 0,
            'pair_results': []
        }
        
        # Analyze each pair
        for pair in tracked_pairs:
            logger.info("Processing %s", pair.symbol)
            
            result = run_technical_analysis(
                trading_pair_id=pair.id,
                start_date=start_date,
                end_date=end_date,
                incremental=incremental,
                calculation_version=calculation_version,
                session=session
            )
            
            summary['pair_results'].append(result)
            
            if result['success']:
                summary['successful_pairs'] += 1
                summary['total_analyses_saved'] += result['analyses_saved']
            else:
                summary['failed_pairs'] += 1
        
        logger.info(
            "All pairs complete: %d successful, %d failed, %d total analyses",
            summary['successful_pairs'],
            summary['failed_pairs'],
            summary['total_analyses_saved']
        )
        
        return summary
    
    finally:
        session.close()
