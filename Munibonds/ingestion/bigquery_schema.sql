-- BigQuery schema for MSRB Municipal Bonds trades data
-- Dataset: nyu-datasets.munibonds
-- Tables:
--   trades       - raw load with STRING date/time columns (matches source format)
--   trades_typed - VIEW with parsed DATE/TIME columns (use for analysis)
--
-- Source: WRDS MSRB dataset at gs://msrb_munibonds_dataset/raw_wrds/
-- 24 columns matching the source TSV files exactly.
--
-- IMPORTANT: Date/time columns are STRING in the raw table because source
-- files mix YYYY/MM/DD (older files) and YYYY-MM-DD (newer files), neither
-- of which BigQuery's DATE type accepts directly during CSV load. The
-- trades_typed view (created by load_trades_to_bigquery.py) parses both
-- formats with COALESCE(SAFE.PARSE_DATE(...), SAFE.PARSE_DATE(...)).

CREATE TABLE IF NOT EXISTS `nyu-datasets.munibonds.trades` (
    -- Trade Identifiers
    RTRS_CONTROL_NUMBER STRING,                 -- MSRB trade control number
    TRADE_TYPE_INDICATOR STRING,                -- D=Dealer, P=Purchase, S=Sale

    -- Bond Identifiers and Characteristics
    CUSIP STRING,                               -- 9-character CUSIP identifier
    SECURITY_DESCRIPTION STRING,                -- Bond description
    DATED_DATE STRING,                          -- Bond dated date (YYYY/MM/DD or YYYY-MM-DD)
    COUPON FLOAT64,                             -- Coupon rate (%)
    MATURITY_DATE STRING,                       -- Bond maturity date

    -- Trade Type and Settlement
    WHEN_ISSUED_INDICATOR STRING,               -- When-issued indicator (Y/N)
    ASSUMED_SETTLEMENT_DATE STRING,             -- Assumed settlement date
    TRADE_DATE STRING,                          -- Date of the trade
    TIME_OF_TRADE STRING,                       -- Time of trade (HH:MM:SS)
    SETTLEMENT_DATE STRING,                     -- Actual settlement date

    -- Pricing Information
    PAR_TRADED FLOAT64,                         -- Par amount traded
    DOLLAR_PRICE FLOAT64,                       -- Dollar price (% of par)
    YIELD FLOAT64,                              -- Yield to maturity (%)

    -- Trade Metadata
    BROKERS_BROKER_INDICATOR STRING,            -- Brokers' broker indicator (Y/N)
    WEIGHTED_PRICE_INDICATOR STRING,            -- Weighted price indicator (Y/N)
    OFFER_PRICE_TAKEDOWN_INDICATOR STRING,      -- Offer price/takedown indicator (Y/N)

    -- Publication Information
    RTRS_PUBLISH_DATE STRING,                   -- MSRB publication date
    RTRS_PUBLISH_TIME STRING,                   -- MSRB publication time
    VERSION_NUMBER STRING,                      -- Record version number

    -- Additional MSRB Indicators (newer columns post-2020)
    UV_DOLLAR_PRICE_INDICATOR STRING,           -- Unverified dollar price indicator
    ATS_INDICATOR STRING,                       -- Alternative Trading System indicator
    NTBC_INDICATOR STRING                       -- Non-Transaction-Based Compensation indicator
)
CLUSTER BY CUSIP
OPTIONS(
    description="MSRB municipal bond trades from WRDS dataset (raw, STRING dates). See trades_typed view for parsed dates.",
    labels=[("source", "wrds"), ("dataset", "msrb"), ("type", "trades")]
);

-- Notes:
-- 1. Clustering by CUSIP optimizes per-bond analytical queries
-- 2. Cannot partition on STRING TRADE_DATE; date-range queries should
--    use the trades_typed view, which has TRADE_DATE as a parsed DATE
-- 3. FLOAT64 fields handle empty strings as NULL during CSV load
-- 4. The trades_typed view normalizes mixed YYYY/MM/DD and YYYY-MM-DD
--    formats from different source-file vintages
