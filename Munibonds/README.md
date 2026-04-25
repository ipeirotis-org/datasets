# MSRB Municipal Bonds Trading Data

Municipal bond trade-level data from the MSRB (Municipal Securities Rulemaking Board) EMMA system, sourced via WRDS. Contains every reported trade in the U.S. municipal bond market.

## Dataset Overview

| Property | Value |
|----------|-------|
| **Source** | WRDS MSRB dataset |
| **Coverage** | 2005-01-03 to 2025-12-31 (21 years) |
| **Total trades** | 215,789,928 |
| **Unique CUSIPs** | 3,411,819 |
| **Update frequency** | Yearly batch (manual download from WRDS) |
| **GCS bucket** | `gs://msrb_munibonds_dataset/raw_wrds/` |
| **BigQuery dataset** | `nyu-datasets.munibonds` |
| **Tables** | `trades` (raw), `trades_typed` (parsed dates) |

## Quick Start

### Query the data in BigQuery

Use `trades_typed` for analysis (proper DATE/TIME parsing):

```sql
-- Recent trades for a specific bond
SELECT TRADE_DATE, YIELD, DOLLAR_PRICE, PAR_TRADED
FROM `nyu-datasets.munibonds.trades_typed`
WHERE CUSIP = '12345678X'
  AND TRADE_DATE >= '2024-01-01'
ORDER BY TRADE_DATE DESC
LIMIT 100;
```

```sql
-- Yield curve aggregation by maturity
SELECT
    DATE_DIFF(MATURITY_DATE, TRADE_DATE, YEAR) AS years_to_maturity,
    AVG(YIELD) AS avg_yield,
    COUNT(*) AS num_trades
FROM `nyu-datasets.munibonds.trades_typed`
WHERE TRADE_DATE = '2024-12-31'
  AND YIELD IS NOT NULL
GROUP BY years_to_maturity
HAVING years_to_maturity BETWEEN 0 AND 30
ORDER BY years_to_maturity;
```

### Use the Python library

```python
from bonds import Munibonds

mb = Munibonds()  # uses Application Default Credentials

# Get most active bonds
bonds = mb.get_bonds(min_trades=1000, min_dates_traded=100)

# Get trade history for a specific CUSIP
history = mb.history(['12345678X'], column='AVG_PRICE')

# Find similar bonds
from bonds import Munidata
md = Munidata(['12345678X'])
similar = md.get_similar('12345678X', n=10)
```

## Schema

The `trades_typed` view has 24 columns:

### Trade Identifiers
| Column | Type | Description |
|--------|------|-------------|
| `RTRS_CONTROL_NUMBER` | STRING | MSRB trade control number |
| `TRADE_TYPE_INDICATOR` | STRING | D=Dealer, P=Purchase, S=Sale |

### Bond Characteristics
| Column | Type | Description |
|--------|------|-------------|
| `CUSIP` | STRING | 9-character CUSIP identifier |
| `SECURITY_DESCRIPTION` | STRING | Bond description |
| `DATED_DATE` | DATE | Bond dated date |
| `COUPON` | FLOAT64 | Coupon rate (%) |
| `MATURITY_DATE` | DATE | Bond maturity date |

### Trade Details
| Column | Type | Description |
|--------|------|-------------|
| `TRADE_DATE` | DATE | Date of the trade |
| `TIME_OF_TRADE` | TIME | Time of trade (HH:MM:SS) |
| `SETTLEMENT_DATE` | DATE | Actual settlement date |
| `ASSUMED_SETTLEMENT_DATE` | DATE | Expected settlement date |
| `WHEN_ISSUED_INDICATOR` | STRING | Y/N - traded before issuance |
| `PAR_TRADED` | FLOAT64 | Par amount traded |
| `DOLLAR_PRICE` | FLOAT64 | Price as % of par |
| `YIELD` | FLOAT64 | Yield to maturity (%) |

### Trade Metadata
| Column | Type | Description |
|--------|------|-------------|
| `BROKERS_BROKER_INDICATOR` | STRING | Y/N - inter-dealer broker trade |
| `WEIGHTED_PRICE_INDICATOR` | STRING | Y/N - weighted price |
| `OFFER_PRICE_TAKEDOWN_INDICATOR` | STRING | Y/N - takedown price |
| `RTRS_PUBLISH_DATE` | DATE | MSRB publication date |
| `RTRS_PUBLISH_TIME` | TIME | MSRB publication time |
| `VERSION_NUMBER` | STRING | Record version |

### Newer Indicators (post-2020)
| Column | Type | Description |
|--------|------|-------------|
| `UV_DOLLAR_PRICE_INDICATOR` | STRING | Unverified dollar price |
| `ATS_INDICATOR` | STRING | Alternative Trading System |
| `NTBC_INDICATOR` | STRING | Non-Transaction-Based Compensation |

## Data Pipeline

```
WRDS MSRB Dataset
        ↓ (manual download)
gs://msrb_munibonds_dataset/raw_wrds/msrb_*.tsv.gz
        ↓ (scripts/split_by_year.py)
gs://msrb_munibonds_dataset/raw_wrds/trades_{year}.tsv.gz
        ↓ (ingestion/load_trades_to_bigquery.py)
nyu-datasets.munibonds.trades  (raw, STRING dates)
        ↓ (auto-created VIEW)
nyu-datasets.munibonds.trades_typed  ← USE THIS
```

## Setup (One-time)

### 1. Create the GCS bucket

```bash
gsutil mb -p nyu-datasets -c STANDARD -l US gs://msrb_munibonds_dataset
```

### 2. Create service account

```bash
gcloud iam service-accounts create msrb-pipeline \
    --project=nyu-datasets \
    --display-name="MSRB Munibonds Pipeline"

SA_EMAIL="msrb-pipeline@nyu-datasets.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding nyu-datasets \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin" \
    --condition=None

gcloud projects add-iam-policy-binding nyu-datasets \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.admin" \
    --condition=None

# Get the JSON key
gcloud iam service-accounts keys create msrb-pipeline-key.json \
    --iam-account=${SA_EMAIL}

export GOOGLE_APPLICATION_CREDENTIALS=$PWD/msrb-pipeline-key.json
```

See `scripts/SERVICE_ACCOUNT_SETUP.md` for full details.

### 3. Create the BigQuery dataset

```bash
bq mk --location=US --dataset nyu-datasets:munibonds
```

## Yearly Update Process

When new MSRB data is available from WRDS:

### 1. Download from WRDS

Download the new TSV.GZ files and upload to GCS:

```bash
gsutil cp msrb_YYYY.tsv.gz gs://msrb_munibonds_dataset/raw_wrds/
```

### 2. Split by year

Files from WRDS may span multiple years - split them:

```bash
python3 scripts/split_by_year.py
```

This creates `trades_{year}.tsv.gz` files (or merges with existing).

### 3. Load to BigQuery

```bash
python3 ingestion/load_trades_to_bigquery.py
```

Use `--overwrite` to recreate the table from scratch:

```bash
python3 ingestion/load_trades_to_bigquery.py --overwrite
```

## File Format Notes

Source files have evolved over time:

- **Older files (2005-2019)**: 24 columns, uppercase column names, dates in `YYYY/MM/DD` format
- **Newer files (2020-2025)**: 25 columns (includes `cusip6`), lowercase names, dates in `YYYY-MM-DD` format

The `split_by_year.py` script normalizes all to a canonical 24-column uppercase format.
The `trades_typed` view handles both date formats via `COALESCE(SAFE.PARSE_DATE(...))`.

## Files in This Directory

| Path | Purpose |
|------|---------|
| `bonds.py` | Python library for analyzing trades (BigQuery-based) |
| `ingestion/load_trades_to_bigquery.py` | Load TSV.GZ files into BigQuery |
| `ingestion/bigquery_schema.sql` | Schema DDL (informational) |
| `scripts/migrate_direct.py` | Copy files between GCS buckets (used for migration) |
| `scripts/split_by_year.py` | Split multi-year files into yearly files |
| `scripts/SERVICE_ACCOUNT_SETUP.md` | Service account creation/management |

## Sources

- **WRDS**: https://wrds-www.wharton.upenn.edu/
- **MSRB EMMA**: https://www.msrb.org/
- **Original repository**: https://github.com/ipeirotis/munibonds (legacy)

## Citation

If using this data in research, please cite:
- WRDS MSRB Dataset: https://wrds-www.wharton.upenn.edu/pages/get-data/msrb/
- MSRB EMMA: https://www.msrb.org/
