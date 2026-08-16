-- Seed tracked pairs for Phase II
-- This table controls which trading pairs to actively monitor and collect data for
-- Add/remove pairs by modifying INSERT statements below

-- Initial tracked pairs: BTC-USD, ETH-USD, XRP-USD, SOL-USD
INSERT INTO crypto.tracked_pairs (product_id, symbol, is_tracking_active) 
VALUES 
    ('BTC-USD', 'BTC-USD', 1),
    ('ETH-USD', 'ETH-USD', 1),
    ('XRP-USD', 'XRP-USD', 1),
    ('SOL-USD', 'SOL-USD', 1);

-- Examples for adding more pairs:
-- INSERT INTO crypto.tracked_pairs (product_id, symbol, is_tracking_active) 
-- VALUES ('AVAX-USD', 'AVAX-USD', 1);

-- To temporarily stop tracking a pair (without deleting):
-- UPDATE crypto.tracked_pairs SET is_tracking_active = 0 WHERE product_id = 'XRP-USD';

-- To remove a pair completely:
-- DELETE FROM crypto.tracked_pairs WHERE product_id = 'XRP-USD';
