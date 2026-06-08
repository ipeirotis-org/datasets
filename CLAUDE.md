# CLAUDE.md — ipeirotis-org/datasets

## Purpose

ETL pipeline hub for fetching, cleaning, and loading public datasets into Google BigQuery. Primarily used for Panos Ipeirotis's courses at NYU Stern (AI/ML Product Management and related courses).

## Architecture

Each dataset lives in its own directory with one or more **Jupyter notebooks** (designed for Google Colab). The general pipeline pattern:

1. **Download** from public API / S3 / Open Data portal
2. **Clean** with pandas (normalize columns, handle schema changes, fix data quality)
3. **Convert** to Parquet via PyArrow
4. **Upload** to Google Cloud Storage (staging)
5. **Load** into BigQuery (external or native tables)
6. **Validate** with assertions on nulls, ranges, consistency

## Repo Structure

```
datasets/
├── Citibike/               # NYC Citibike trips (2013–present, schema change at Feb 2021)
├── Collisions/             # NYC traffic collision data
├── ERCOT/                  # Texas power grid demand/supply
├── Flight_Stats/           # BTS flight delays, DB1B market data, FAA
├── Music/                  # Music streaming data
├── NYPD_Complaint/         # NYPD crime complaint records
├── Real_Estate/            # NYC real estate transactions
├── Restaurant_Inspections/ # NYC DOH restaurant inspections (normalized into 4 tables)
├── Shapefiles/             # US Census shapefiles → BigQuery geography
├── Shazam/                 # Shazam music charts
├── Weather/                # Historical weather data
├── Baseball/               # Static CSV files (Pitching, Salaries, Teams)
├── static_datasets/        # Reusable reference CSVs, SQL dumps (Northwind, IMDB, etc.)
├── Cybersyn_example.ipynb  # Snowflake integration example
└── NYC_Traffic_Data.ipynb  # Root-level notebook
```

## Tech Stack

- **Python 3** — all ETL logic
- **Jupyter Notebooks** (.ipynb) — primary dev environment (Google Colab)
- **pandas / PyArrow** — data manipulation and Parquet serialization
- **Google Cloud Platform** — BigQuery, GCS, Cloud Functions, Cloud Scheduler, IAM
- **GeoPandas / Shapely** — geospatial data (Shapefiles)
- **SQLAlchemy** — MySQL connections (some datasets)
- **SQL** — BigQuery DDL/DML, MySQL views (Flight_Stats)

## Key Design Decisions

- **Parquet as intermediate format** — efficient compression, schema preservation
- **Date-partitioned GCS uploads** — especially Citibike (daily/monthly archives)
- **Normalized schemas** — e.g., DOH Restaurant Inspections creates 4 relational tables
- **Google Colab as runtime** — easy sharing, no local setup, browser-based execution
- **Citibike has two notebooks** — pre-2021 and post-2021 handle different column schemas

## Dataset-Specific Notes

- **Citibike**: Schema changed Feb 2021. `Copy_Citibike_Trips.ipynb` handles pre-2021; `Copy_Citibike_Trips_After_2021.ipynb` handles post-2021.
- **Flight_Stats**: Localizes times to airport timezones (not UTC). Handles cross-midnight flights.
- **Restaurant Inspections**: Removes ~31% of raw data for quality. Creates restaurants, inspections, violations, violation_codes tables.
- **Shazam**: Has a TODO to add US top 100 chart.

## Working With This Repo

- Notebooks are self-documenting with markdown cells explaining each step.
- Most notebooks assume Google Colab runtime with GCP credentials.
- Static datasets in `static_datasets/` are standalone and don't need cloud infrastructure.
- The `Flight_Stats/` directory includes `.sql` files for creating BigQuery views.

## Cloud Credentials

This repo is paired with Google Cloud via the **cloud-bootstrap** skill (`.claude/skills/cloud-bootstrap/`), which stores encrypted service-account credentials in the repo so they persist across Claude Code sessions.

- **Provider / Project:** GCP, project `nyu-datasets`
- **Service account:** `claude-agent@nyu-datasets.iam.gserviceaccount.com`
- **Roles granted:**
  - `roles/bigquery.admin` — create/manage datasets and tables, load data, configure external tables
  - `roles/bigquery.jobUser` — run load and query jobs
  - `roles/storage.objectAdmin` — read/write GCS staging buckets used in the ETL pipeline

### Multi-user setup
Each team member has their own encrypted credentials file, `.cloud-credentials.<git-email>.enc`, decryptable only with that person's own passphrase. Passphrases are never shared or committed — each user sets one of `GCP_CREDENTIALS_KEY` / `CLOUD_CREDENTIALS_KEY` as an environment variable in Claude Code on the Web.

### Authentication
Automatic. The `SessionStart` hook (`.claude/hooks/cloud-auth.sh`, wired up in `.claude/settings.json`) installs `gcloud` if missing, decrypts your credentials, and activates the service account at the start of every session. No manual steps.

### New team members
Ask the agent to "add me to cloud access" — it runs the cloud-bootstrap **Add Team Member** flow, which creates a new key for the existing service account and encrypts it with your passphrase. (Requires Service Account Key Admin on the project.)

### Escalating permissions
If a cloud command fails with a 403, ask the agent to add the needed role — it runs the cloud-bootstrap **Permission Escalation** flow and tells you which role to grant.

## TODO.md

This repo's TODO.md feeds into the `Teaching: Datasets ETL` section of the main tasks repo (`ipeirotis/tasks`).
