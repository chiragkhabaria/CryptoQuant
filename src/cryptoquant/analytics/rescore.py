"""
Re-score existing technical_analysis rows.

Applies the current scoring rules to already-stored indicators (no indicator
recalculation, no Coinbase calls). Use after changing scoring rules or to
populate scores for rows computed before scoring existed.
"""

import logging
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from cryptoquant.database.models import MarketPrice, TechnicalAnalysis

from .scoring import DEFAULT_CONFIG, ScoringConfig, calculate_scores, calculate_signal

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def rescore_pair(
    session: Session,
    trading_pair_id: int,
    config: ScoringConfig = DEFAULT_CONFIG,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Re-score all analysis rows of one pair. Returns rows updated."""
    updated = 0
    last_id = 0
    total = session.query(TechnicalAnalysis).filter(TechnicalAnalysis.trading_pair_id == trading_pair_id).count()
    logger.info("pair_id=%d: %d rows to re-score", trading_pair_id, total)
    while True:
        rows = (
            session.query(TechnicalAnalysis, MarketPrice.close)
            .join(MarketPrice, MarketPrice.id == TechnicalAnalysis.market_price_id)
            .filter(TechnicalAnalysis.trading_pair_id == trading_pair_id)
            .filter(TechnicalAnalysis.id > last_id)
            .order_by(TechnicalAnalysis.id)
            .limit(batch_size)
            .all()
        )
        if not rows:
            break

        mappings = []
        for analysis, close in rows:
            indicators = {
                "ema_200": analysis.ema_200,
                "rsi_14": analysis.rsi_14,
                "macd_histogram": analysis.macd_histogram,
                "atr_14": analysis.atr_14,
            }
            scores = calculate_scores(indicators, close=close, config=config)
            mappings.append(
                {
                    "id": analysis.id,
                    **scores,
                    "signal": calculate_signal(scores["technical_score"], config),
                }
            )
        session.bulk_update_mappings(TechnicalAnalysis, mappings)
        session.commit()
        updated += len(mappings)
        last_id = rows[-1][0].id
        logger.info("pair_id=%d: re-scored %d/%d rows", trading_pair_id, updated, total)
    return updated


def rescore_all(
    session: Session,
    trading_pair_ids: Optional[Sequence[int]] = None,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> dict[int, int]:
    """Re-score the given pairs (default: every pair with analysis rows)."""
    if trading_pair_ids is None:
        trading_pair_ids = [
            r[0] for r in session.query(TechnicalAnalysis.trading_pair_id).distinct().all()
        ]
    return {pid: rescore_pair(session, pid, config) for pid in trading_pair_ids}
