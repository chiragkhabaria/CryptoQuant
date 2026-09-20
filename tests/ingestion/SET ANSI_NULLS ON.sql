SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [crypto].[market_prices](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[trading_pair_id] [int] NOT NULL,
	[timestamp] [datetime] NOT NULL,
	[open] [numeric](18, 8) NOT NULL,
	[high] [numeric](18, 8) NOT NULL,
	[low] [numeric](18, 8) NOT NULL,
	[close] [numeric](18, 8) NOT NULL,
	[volume] [numeric](18, 8) NOT NULL,
	[data_source] [varchar](50) NOT NULL,
	[created_at] [datetime] NOT NULL
) ON [PRIMARY]
GO
ALTER TABLE [crypto].[market_prices] ADD PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ONLINE = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
ALTER TABLE [crypto].[market_prices] ADD  CONSTRAINT [uq_market_price_pair_timestamp] UNIQUE NONCLUSTERED 
(
	[trading_pair_id] ASC,
	[timestamp] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ONLINE = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
CREATE NONCLUSTERED INDEX [ix_crypto_market_prices_pair_time] ON [crypto].[market_prices]
(
	[trading_pair_id] ASC,
	[timestamp] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
CREATE NONCLUSTERED INDEX [ix_crypto_market_prices_timestamp_desc] ON [crypto].[market_prices]
(
	[timestamp] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
CREATE NONCLUSTERED INDEX [ix_crypto_market_prices_trading_pair_id] ON [crypto].[market_prices]
(
	[trading_pair_id] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, DROP_EXISTING = OFF, ONLINE = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
ALTER TABLE [crypto].[market_prices] ADD  DEFAULT (getutcdate()) FOR [created_at]
GO
ALTER TABLE [crypto].[market_prices]  WITH CHECK ADD FOREIGN KEY([trading_pair_id])
REFERENCES [crypto].[trading_pairs] ([id])
GO
