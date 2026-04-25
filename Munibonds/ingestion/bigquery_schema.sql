-- BigQuery schema for MSRB Municipal Bonds trades data
-- Dataset: nyu-datasets.munibonds
-- Table: trades
--
-- Source: WRDS MSRB dataset (uploaded to gs://msrb_munibonds_dataset/raw_wrds/)
-- 24 columns matching the source TSV files exactly.

CREATE OR REPLACE TABLE `nyu-datasets.munibonds.trades` (
    -- Trade Identifiers
    RTRS_CONTROL_NUMBER STRING,                 -- MSRB trade control number
    TRADE_TYPE_INDICATOR STRING,                -- D=Dealer, P=Purchase, S=Sale

    -- Bond Identifiers and Characteristics
    CUSIP STRING,                               -- 9-character CUSIP identifier
    SECURITY_DESCRIPTION STRING,                -- Bond description
    DATED_DATE DATE,                            -- Bond dated date
    COUPON FLOAT64,                             -- Coupon rate (%)
    MATURITY_DATE DATE,                         -- Bond maturity date

    -- Trade Type and Settlement
    WHEN_ISSUED_INDICATOR STRING,               -- When-issued indicator (Y/N)
    ASSUMED_SETTLEMENT_DATE DATE,               -- Assumed settlement date
    TRADE_DATE DATE,                            -- Date of the trade
    TIME_OF_TRADE TIME,                         -- Time of trade (HH:MM:SS)
    SETTLEMENT_DATE DATE,                       -- Actual settlement date

    -- Pricing Information
    PAR_TRADED FLOAT64,                         -- Par amount traded
    DOLLAR_PRICE FLOAT64,                       -- Dollar price (% of par)
    YIELD FLOAT64,                              -- Yield to maturity (%)

    -- Trade Metadata
    BROKERS_BROKER_INDICATOR STRING,            -- Brokers' broker indicator (Y/N)
    WEIGHTED_PRICE_INDICATOR STRING,            -- Weighted price indicator (Y/N)
    OFFER_PRICE_TAKEDOWN_INDICATOR STRING,      -- Offer price/takedown indicator (Y/N)

    -- Publication Information
    RTRS_PUBLISH_DATE DATE,                     -- MSRB publication date
    RTRS_PUBLISH_TIME TIME,                     -- MSRB publication time
    VERSION_NUMBER STRING,                      -- Version number

    -- Additional MSRB Indicators (newer columns)
    UV_DOLLAR_PRICE_INDICATOR STRING,           -- Unverified dollar price indicator
    ATS_INDICATOR STRING,                       -- Alternative Trading System indicator
    NTBC_INDICATOR STRING                       -- Non-Transaction-Based Compensation indicator
)
PARTITION BY DATE_TRUNC(TRADE_DATE, YEAR)
CLUSTER BY CUSIP, TRADE_DATE
OPTIONS(
    description="MSRB municipal bond trades from WRDS dataset. One record per trade transaction.",
    labels=[("source", "wrds"), ("dataset", "msrb"), ("type", "trades")]
);

-- Notes:
-- 1. Partitioning by TRADE_DATE year enables efficient querying for date ranges
-- 2. Clustering by CUSIP and TRADE_DATE optimizes typical analytical queries
-- 3. All FLOAT64 fields auto-handle empty strings as NULL during CSV load
-- 4. Date fields use YYYY/MM/DD format from source files (auto-parsed)
