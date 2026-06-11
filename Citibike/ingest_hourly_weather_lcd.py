"""Ingest hourly Central Park weather (NOAA LCD v2) into GCS + BigQuery.

The daily weather mart (`nyu-datasets.weather.weather_daily_nyc`) is built from
GHCN-Daily, whose Central Park values are summaries of hourly ASOS
observations. NOAA publishes those parent observations as **Local
Climatological Data v2** — one CSV per station-year at
https://www.ncei.noaa.gov/oa/local-climatological-data/v2/access/ — so this
script ingests the *same station, same instrument* (GHCN `USW00094728`, WBAN
94728, ICAO KNYC) at observation granularity: ~24 routine FM-15 METARs per day
plus FM-16 special observations. Hourly data unlocks exposure-weighted
regressors for ridership models (riding-hours temperature, rain timing,
afternoon wet-bulb) and extends dew point / RH coverage back to 2013, where
the daily mart's GHCN `ADPT`/`RHAV` elements only begin ~2016.

Pipeline (same raw-first shape as the Citibike trips pipeline):

    mirror       NCEI station-year CSVs -> gs://citibike-archive/raw/lcd/
    extract      raw CSVs -> typed Parquet under weather/lcd/parquet/ (SI units)
    load         BigQuery: external `weather.lcd_hourly_nyc`
                 -> view `weather.weather_hourly_nyc` (imperial + local time)
                 -> snapshot `weather.m_weather_hourly_nyc`
    all          everything above, in order

Source facts the transform pins:

* **Time basis.** LCD v2 stamps observations in local *standard* time
  year-round (UTC-5, never DST) — verified by matching identical observations
  against the UTC-stamped ISD record in both January and July (+5h both).
  Citibike trips carry naive local wall-clock (America/New_York, DST-aware),
  so join trips on the view's `obs_time_local` (LST -> UTC -> America/New_York),
  never on `obs_time_lst`, which is an hour behind all summer.
* **Units.** LCD v2 is SI (degC, mm, m/s, km, hPa). Parquet keeps SI; the view
  adds the daily mart's imperial conventions (degF, inches, mph, miles).
* **Value markers.** `T` = trace precipitation -> 0.0 (as GHCN daily treats
  trace); trailing `s` = NCEI "suspect" QC flag -> NULL (the hourly analog of
  the daily mart's `qflag IS NULL` filter); trailing `V` = "variable" -> the
  value stands; `VRB` wind direction -> NULL.
* **Snow.** There is *no hourly accumulation source anywhere* — snowfall and
  snow depth are once-daily manual measurements (use the daily mart). Hourly
  snow appears only as the `is_snowing` present-weather flag.

Auth: Application Default Credentials (`gcloud auth application-default login`
or GOOGLE_APPLICATION_CREDENTIALS) with write access to the bucket and the
`weather` dataset.

    python ingest_hourly_weather_lcd.py all
    python ingest_hourly_weather_lcd.py mirror --years 2025 2026

This is the standalone copy of `src/citibike_pipeline/weather_hourly.py` in
the ipeirotis/citibike-example repo (kept in lockstep; that repo also carries
the unit tests for the marker rules and `sql/weather_hourly_nyc.sql`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

# --- Resources -----------------------------------------------------------------
PROJECT = "nyu-datasets"
LOCATION = "US"
BUCKET = "citibike-archive"
WEATHER_DATASET = "weather"
STATION = "USW00094728"  # NY CITY CENTRAL PARK — same id the daily mart filters on
LCD_BASE_URL = "https://www.ncei.noaa.gov/oa/local-climatological-data/v2/access/"
FIRST_YEAR = 2013        # Citibike era; LCD coverage reaches further back if needed
RAW_PREFIX = "raw/lcd/"
PARQUET_PREFIX = "weather/lcd/parquet/"
EXTERNAL_TABLE = f"{PROJECT}.{WEATHER_DATASET}.lcd_hourly_nyc"
VIEW = f"{PROJECT}.{WEATHER_DATASET}.weather_hourly_nyc"
SNAPSHOT = f"{PROJECT}.{WEATHER_DATASET}.m_weather_hourly_nyc"

# Typed Parquet schema — SI units as published; timestamps are naive LST.
LCD_SCHEMA = pa.schema([
    ("station_id", pa.string()),
    ("obs_time_lst", pa.timestamp("us")),
    ("report_type", pa.string()),
    ("temp_c", pa.float64()),
    ("dewpoint_c", pa.float64()),
    ("wetbulb_c", pa.float64()),
    ("rh_pct", pa.float64()),
    ("precip_mm", pa.float64()),
    ("slp_hpa", pa.float64()),
    ("station_pressure_hpa", pa.float64()),
    ("altimeter_hpa", pa.float64()),
    ("wind_speed_ms", pa.float64()),
    ("wind_gust_ms", pa.float64()),
    ("wind_dir_deg", pa.float64()),
    ("visibility_km", pa.float64()),
    ("sky_conditions", pa.string()),
    ("present_weather", pa.string()),
    ("source_file", pa.string()),
])

# (LCD column, parquet column, treat "T" as trace -> 0.0)
NUMERIC_COLS = [
    ("HourlyDryBulbTemperature", "temp_c", False),
    ("HourlyDewPointTemperature", "dewpoint_c", False),
    ("HourlyWetBulbTemperature", "wetbulb_c", False),
    ("HourlyRelativeHumidity", "rh_pct", False),
    ("HourlyPrecipitation", "precip_mm", True),
    ("HourlySeaLevelPressure", "slp_hpa", False),
    ("HourlyStationPressure", "station_pressure_hpa", False),
    ("HourlyAltimeterSetting", "altimeter_hpa", False),
    ("HourlyWindSpeed", "wind_speed_ms", False),
    ("HourlyWindGustSpeed", "wind_gust_ms", False),
    ("HourlyWindDirection", "wind_dir_deg", False),
    ("HourlyVisibility", "visibility_km", False),
]
STRING_COLS = [
    ("HourlySkyConditions", "sky_conditions"),
    ("HourlyPresentWeatherType", "present_weather"),
]
KEEP_REPORT_TYPES = ("FM-15", "FM-16")  # routine hourly METARs + specials

VIEW_SQL = f"""\
CREATE OR REPLACE VIEW `{VIEW}` AS
WITH obs AS (
  SELECT
    -- The Parquet column physically holds LST wall times, but BigQuery
    -- surfaces external Parquet timestamps as UTC-labeled TIMESTAMPs:
    -- DATETIME() recovers the naive LST wall time, TIMESTAMP(.., 'Etc/GMT+5')
    -- re-anchors it to the fixed UTC-5 zone it really lives in (LST).
    * EXCEPT(obs_time_lst),
    DATETIME(obs_time_lst) AS obs_time_lst,
    TIMESTAMP(DATETIME(obs_time_lst), 'Etc/GMT+5') AS obs_time_utc
  FROM `{EXTERNAL_TABLE}`
)
SELECT
  station_id,
  report_type,
  obs_time_lst,
  obs_time_utc,
  DATETIME(obs_time_utc, 'America/New_York')                    AS obs_time_local,
  DATE(obs_time_utc, 'America/New_York')                        AS date_local,
  EXTRACT(HOUR FROM DATETIME(obs_time_utc, 'America/New_York')) AS hour_local,
  ROUND(temp_c * 9/5 + 32, 1)         AS temp_f,
  ROUND(dewpoint_c * 9/5 + 32, 1)     AS dewpoint_f,
  ROUND(wetbulb_c * 9/5 + 32, 1)      AS wetbulb_f,
  rh_pct,
  ROUND(precip_mm / 25.4, 3)          AS prcp_inches,
  slp_hpa                             AS sea_level_pressure_hpa,
  ROUND(wind_speed_ms * 2.23694, 1)   AS wind_mph,
  ROUND(wind_gust_ms * 2.23694, 1)    AS wind_gust_mph,
  wind_dir_deg,
  ROUND(visibility_km / 1.609344, 1)  AS visibility_miles,
  -- is_foggy/is_thunder/is_hazy mirror the daily mart's WT01/WT03/WT08
  -- semantics (FG not BR). is_raining/is_snowing mean *falling now*; the
  -- daily is_rainy/is_snowy mean "accumulated today" — a different statement.
  IF(REGEXP_CONTAINS(IFNULL(present_weather, ''), r'RA|DZ'), 1, 0)       AS is_raining,
  IF(REGEXP_CONTAINS(IFNULL(present_weather, ''), r'SN|SG|PL|GS'), 1, 0) AS is_snowing,
  IF(REGEXP_CONTAINS(IFNULL(present_weather, ''), r'FG'), 1, 0)          AS is_foggy,
  IF(REGEXP_CONTAINS(IFNULL(present_weather, ''), r'TS'), 1, 0)          AS is_thunder,
  IF(REGEXP_CONTAINS(IFNULL(present_weather, ''), r'HZ'), 1, 0)          AS is_hazy,
  sky_conditions,
  present_weather,
  temp_c, dewpoint_c, wetbulb_c, precip_mm,
  wind_speed_ms, wind_gust_ms, visibility_km,
  source_file
FROM obs"""


def clean_value(v, *, trace_zero: bool = False) -> float | None:
    """One LCD measurement string -> float (or None where unusable)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s:
        return None
    if s == "T":
        return 0.0 if trace_zero else None
    if s == "VRB":
        return None
    if s.endswith("s"):  # NCEI "suspect" QC suffix — failed quality control
        return None
    if s.endswith("V"):  # "variable" — the measured value still stands
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def lcd_frame_to_table(df: pd.DataFrame, source_file: str) -> pa.Table:
    """Raw LCD station-year frame (strings) -> typed Arrow table."""
    d = df.loc[df["REPORT_TYPE"].str.strip().isin(KEEP_REPORT_TYPES)].copy()
    out = pd.DataFrame()
    out["station_id"] = pd.Series(STATION, index=d.index)
    out["obs_time_lst"] = pd.to_datetime(d["DATE"])
    out["report_type"] = d["REPORT_TYPE"].str.strip()
    for src, dest, trace in NUMERIC_COLS:
        col = d[src] if src in d.columns else pd.Series(None, index=d.index)
        out[dest] = col.map(lambda v: clean_value(v, trace_zero=trace)).astype("float64")
    for src, dest in STRING_COLS:
        col = d[src] if src in d.columns else pd.Series(None, index=d.index)
        out[dest] = col.map(lambda v: None if pd.isna(v) or not str(v).strip() else str(v).strip())
    out["source_file"] = source_file
    # NCEI files occasionally repeat an observation (re-transmitted METARs).
    out = (out.drop_duplicates(subset=["obs_time_lst", "report_type"], keep="first")
              .sort_values(["obs_time_lst", "report_type"]).reset_index(drop=True))
    return pa.Table.from_pandas(out, schema=LCD_SCHEMA, preserve_index=False)


def _bucket():
    from google.cloud import storage

    return storage.Client(project=PROJECT).bucket(BUCKET)


def _bq():
    from google.cloud import bigquery

    return bigquery.Client(project=PROJECT, location=LOCATION)


def _raw_name(year: int) -> str:
    return f"LCD_{STATION}_{year}.csv"


def mirror(years: list[int], *, overwrite: bool = False) -> int:
    """Freeze NCEI station-year CSVs under raw/lcd/, byte-for-byte. Idempotent:
    skipped when GCS already holds the file at the remote's Content-Length."""
    bucket = _bucket()
    errors = 0
    for i, year in enumerate(years, 1):
        name = _raw_name(year)
        url = f"{LCD_BASE_URL}{year}/{name}"
        dest = f"{RAW_PREFIX}{name}"
        try:
            head = requests.head(url, timeout=60)
            if head.status_code == 404:
                print(f"[{i:>2}/{len(years)}] absent {name} (404 at NCEI)", flush=True)
                continue
            head.raise_for_status()
            remote_size = int(head.headers.get("Content-Length", -1))
            blob = bucket.get_blob(dest)
            if not overwrite and remote_size > 0 and blob is not None and blob.size == remote_size:
                print(f"[{i:>2}/{len(years)}] skip   {name}", flush=True)
                continue
            with requests.get(url, stream=True, timeout=(10, 600)) as r:
                r.raise_for_status()
                r.raw.decode_content = True
                bucket.blob(dest, chunk_size=40 * 1024 * 1024).upload_from_file(
                    r.raw, content_type="text/csv")
            print(f"[{i:>2}/{len(years)}] mirror {name} ({remote_size/1e6:.1f} MB)", flush=True)
        except Exception as e:
            errors += 1
            print(f"[{i:>2}/{len(years)}] ERROR  {name}: {e}", flush=True)
    return errors


def extract(years: list[int]) -> int:
    """Raw LCD CSVs in GCS -> typed Parquet (one file per station-year)."""
    bucket = _bucket()
    errors = 0
    for i, year in enumerate(years, 1):
        raw = f"{RAW_PREFIX}{_raw_name(year)}"
        blob = bucket.get_blob(raw)
        if blob is None:
            print(f"[{i:>2}/{len(years)}] absent {raw} — run mirror first", flush=True)
            continue
        try:
            df = pd.read_csv(io.BytesIO(blob.download_as_bytes()), dtype=str, low_memory=False)
            table = lcd_frame_to_table(df, raw)
            sink = io.BytesIO()
            pq.write_table(table, sink, compression="snappy")
            sink.seek(0)
            dest = f"{PARQUET_PREFIX}lcd_hourly_nyc_{year}.parquet"
            bucket.blob(dest).upload_from_file(sink, content_type="application/octet-stream")
            print(f"[{i:>2}/{len(years)}] extract {dest} ({table.num_rows:,} obs)", flush=True)
        except Exception as e:
            errors += 1
            print(f"[{i:>2}/{len(years)}] ERROR  {raw}: {e}", flush=True)
    return errors


def load() -> None:
    """External table over the Parquet -> view -> materialized snapshot."""
    client = _bq()
    uri = f"gs://{BUCKET}/{PARQUET_PREFIX}*.parquet"
    client.query(
        f"CREATE OR REPLACE EXTERNAL TABLE `{EXTERNAL_TABLE}`\n"
        f"OPTIONS (format = 'PARQUET', uris = ['{uri}'])",
        location=LOCATION,
    ).result()
    print(f"  + {EXTERNAL_TABLE}  ->  {uri}")
    client.query(VIEW_SQL, location=LOCATION).result()
    print(f"  deployed view {VIEW}")
    client.query(
        f"CREATE OR REPLACE TABLE `{SNAPSHOT}` AS SELECT * FROM `{VIEW}`",
        location=LOCATION,
    ).result()
    print(f"  materialized {SNAPSHOT}: {client.get_table(SNAPSHOT).num_rows:,} rows")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest NOAA LCD v2 hourly weather for Central Park.")
    ap.add_argument("command", choices=["mirror", "extract", "load", "all"])
    ap.add_argument("--years", nargs="*", type=int,
                    help=f"station-years to process (default {FIRST_YEAR}..current)")
    ap.add_argument("--overwrite", action="store_true", help="re-mirror even if size matches")
    args = ap.parse_args(argv)

    years = sorted(args.years) if args.years else list(range(FIRST_YEAR, dt.date.today().year + 1))
    errors = 0
    if args.command in ("mirror", "all"):
        errors += mirror(years, overwrite=args.overwrite)
    if args.command in ("extract", "all"):
        errors += extract(years)
    if args.command in ("load", "all"):
        load()
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
