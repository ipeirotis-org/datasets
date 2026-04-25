#!/usr/bin/env python3
"""
Load MSRB trades data from GCS into BigQuery.

This script:
1. Lists TSV.GZ files from gs://msrb_munibonds_dataset/raw_wrds/
2. Creates BigQuery dataset and table
3. Loads each year's data into the trades table
4. Performs data type conversions and validation

Usage:
    python3 load_trades_to_bigquery.py [--project nyu-datasets] [--overwrite]
"""

import argparse
import logging
import sys
from datetime import datetime

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradesDataLoader:
    def __init__(self, project_id, dataset_id="munibonds", table_id="trades"):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.client = bigquery.Client(project=project_id)
        self.dataset_ref = f"{project_id}.{dataset_id}"
        self.table_ref = f"{self.dataset_ref}.{table_id}"

    def create_dataset(self):
        """Create BigQuery dataset if it doesn't exist."""
        try:
            self.client.get_dataset(self.dataset_id)
            logger.info(f"✓ Dataset {self.dataset_id} already exists")
            return True
        except NotFound:
            logger.info(f"Creating dataset {self.dataset_id}...")
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = "US"
            dataset.description = "MSRB Municipal Bonds Trading Data from WRDS"

            dataset = self.client.create_dataset(dataset)
            logger.info(f"✓ Created dataset {self.dataset_ref}")
            return True

    def get_schema(self):
        """
        Define the raw trades table schema.

        Note: Date/time columns are STRING in raw table because source uses
        YYYY/MM/DD format which BigQuery DATE type doesn't accept.
        A typed VIEW (trades_typed) is created on top with proper conversions.
        """
        return [
            bigquery.SchemaField("RTRS_CONTROL_NUMBER", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("TRADE_TYPE_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("CUSIP", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("SECURITY_DESCRIPTION", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("DATED_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("COUPON", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("MATURITY_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("WHEN_ISSUED_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ASSUMED_SETTLEMENT_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("TRADE_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("TIME_OF_TRADE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("SETTLEMENT_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("PAR_TRADED", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("DOLLAR_PRICE", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("YIELD", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("BROKERS_BROKER_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("WEIGHTED_PRICE_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("OFFER_PRICE_TAKEDOWN_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("RTRS_PUBLISH_DATE", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("RTRS_PUBLISH_TIME", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("VERSION_NUMBER", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("UV_DOLLAR_PRICE_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ATS_INDICATOR", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("NTBC_INDICATOR", "STRING", mode="NULLABLE"),
        ]

    def create_table(self, overwrite=False):
        """Create or recreate the trades table."""
        try:
            if overwrite:
                logger.info(f"Deleting existing table {self.table_ref}...")
                self.client.delete_table(self.table_ref)

            self.client.get_table(self.table_ref)
            logger.info(f"✓ Table {self.table_ref} already exists")
            return True
        except NotFound:
            logger.info(f"Creating table {self.table_ref}...")

            table = bigquery.Table(self.table_ref, schema=self.get_schema())
            # Cluster by CUSIP for typical analytical queries
            # (Cannot partition on STRING TRADE_DATE; use trades_typed view for date queries)
            table.clustering_fields = ["CUSIP"]
            table.description = ("MSRB municipal bond trades from WRDS MSRB dataset. "
                                 "Raw schema with STRING dates. See trades_typed view for parsed dates.")

            table = self.client.create_table(table)
            logger.info(f"✓ Created table {self.table_ref}")
            return True

    def list_source_files(self, bucket="msrb_munibonds_dataset"):
        """List trades TSV.GZ files available in GCS (only trades_*.tsv.gz)."""
        from google.cloud import storage as gcs_storage

        storage_client = gcs_storage.Client(project=self.project_id)
        bucket_obj = storage_client.bucket(bucket)
        blobs = bucket_obj.list_blobs(prefix="raw_wrds/trades_")

        files = [blob.name for blob in blobs if blob.name.endswith(".tsv.gz")]
        logger.info(f"Found {len(files)} trades files in gs://{bucket}/raw_wrds/")
        return sorted(files)

    def load_gcs_file(self, gcs_uri, overwrite_partition=False):
        """Load a single GCS file into BigQuery."""
        logger.info(f"Loading {gcs_uri}...")

        # BigQuery auto-detects gzip compression from file extension (.gz)
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            allow_quoted_newlines=True,
            field_delimiter="\t",
            write_disposition=(
                bigquery.WriteDisposition.WRITE_TRUNCATE
                if overwrite_partition
                else bigquery.WriteDisposition.WRITE_APPEND
            ),
            autodetect=False,
            schema=self.get_schema(),
            allow_jagged_rows=True,
            ignore_unknown_values=True,
            max_bad_records=1000,
        )

        load_job = self.client.load_table_from_uri(
            gcs_uri,
            self.table_ref,
            job_config=job_config,
            timeout=600
        )

        result = load_job.result()
        logger.info(
            f"✓ Loaded {load_job.output_rows} rows from {gcs_uri} "
            f"(output_bytes: {load_job.output_bytes})"
        )
        return result

    def load_all_files(self, bucket="msrb_munibonds_dataset", overwrite=False):
        """Load all TSV files from GCS."""
        files = self.list_source_files(bucket)

        if not files:
            logger.warning("No source files found!")
            return False

        for i, file_path in enumerate(files, 1):
            try:
                gcs_uri = f"gs://{bucket}/{file_path}"
                logger.info(f"[{i}/{len(files)}] {file_path}")
                self.load_gcs_file(gcs_uri)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                # Continue with next file
                continue

        return True

    def validate_data(self):
        """Run validation queries on loaded data."""
        logger.info("\nValidating loaded data...")

        queries = [
            (
                "Row count",
                f"SELECT COUNT(*) as cnt FROM `{self.table_ref}`"
            ),
            (
                "Years in data",
                f"""SELECT SUBSTR(TRADE_DATE, 1, 4) as year, COUNT(*) as cnt
                    FROM `{self.table_ref}`
                    WHERE TRADE_DATE IS NOT NULL AND TRADE_DATE != ''
                    GROUP BY year ORDER BY year"""
            ),
            (
                "Unique CUSIPs",
                f"SELECT COUNT(DISTINCT CUSIP) as cnt FROM `{self.table_ref}`"
            ),
            (
                "Date range",
                f"SELECT MIN(TRADE_DATE) as min_date, MAX(TRADE_DATE) as max_date FROM `{self.table_ref}`"
            ),
            (
                "Null counts",
                f"""SELECT
                   COUNTIF(YIELD IS NULL) as null_yields,
                   COUNTIF(DOLLAR_PRICE IS NULL) as null_prices,
                   COUNTIF(CUSIP IS NULL) as null_cusips
                   FROM `{self.table_ref}`"""
            ),
        ]

        for name, query in queries:
            try:
                result = list(self.client.query(query).result())
                if name == "Years in data":
                    logger.info(f"{name}:")
                    for row in result:
                        logger.info(f"  {row['year']}: {row['cnt']:,} rows")
                else:
                    row = result[0]
                    formatted = ", ".join(f"{k}={v}" for k, v in row.items())
                    logger.info(f"{name}: {formatted}")
            except Exception as e:
                logger.warning(f"Validation query '{name}' failed: {e}")

    def create_typed_view(self):
        """Create a view with properly typed dates parsed from STRING columns.

        Handles both YYYY/MM/DD (older files) and YYYY-MM-DD (newer files) formats.
        """
        view_id = f"{self.dataset_ref}.trades_typed"
        # COALESCE both formats - SAFE.PARSE_DATE returns NULL on failure
        parse_date = lambda c: (
            f"COALESCE("
            f"SAFE.PARSE_DATE('%Y/%m/%d', {c}), "
            f"SAFE.PARSE_DATE('%Y-%m-%d', {c})"
            f") AS {c}"
        )
        parse_time = lambda c: (
            f"COALESCE("
            f"SAFE.PARSE_TIME('%H:%M:%S', {c}), "
            f"SAFE.PARSE_TIME('%H:%M:%E*S', {c})"
            f") AS {c}"
        )
        view_query = f"""
        SELECT
            RTRS_CONTROL_NUMBER,
            TRADE_TYPE_INDICATOR,
            CUSIP,
            SECURITY_DESCRIPTION,
            {parse_date('DATED_DATE')},
            COUPON,
            {parse_date('MATURITY_DATE')},
            WHEN_ISSUED_INDICATOR,
            {parse_date('ASSUMED_SETTLEMENT_DATE')},
            {parse_date('TRADE_DATE')},
            {parse_time('TIME_OF_TRADE')},
            {parse_date('SETTLEMENT_DATE')},
            PAR_TRADED,
            DOLLAR_PRICE,
            YIELD,
            BROKERS_BROKER_INDICATOR,
            WEIGHTED_PRICE_INDICATOR,
            OFFER_PRICE_TAKEDOWN_INDICATOR,
            {parse_date('RTRS_PUBLISH_DATE')},
            {parse_time('RTRS_PUBLISH_TIME')},
            VERSION_NUMBER,
            UV_DOLLAR_PRICE_INDICATOR,
            ATS_INDICATOR,
            NTBC_INDICATOR
        FROM `{self.table_ref}`
        """

        view = bigquery.Table(view_id)
        view.view_query = view_query
        view.description = "Typed view of trades with parsed DATE/TIME columns from STRING raw"

        try:
            self.client.delete_table(view_id, not_found_ok=True)
            self.client.create_table(view)
            logger.info(f"✓ Created view {view_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create view: {e}")
            return False

    def load(self, overwrite=False):
        """Execute the full loading pipeline."""
        logger.info("=" * 70)
        logger.info("MSRB Trades Data Loader - BigQuery")
        logger.info("=" * 70)
        logger.info(f"Target: {self.table_ref}")
        logger.info(f"Overwrite: {overwrite}")
        logger.info("=" * 70)

        # Step 1: Create dataset
        if not self.create_dataset():
            return False

        # Step 2: Create table
        if not self.create_table(overwrite=overwrite):
            return False

        # Step 3: Load data
        logger.info("\nLoading data from GCS...")
        if not self.load_all_files(overwrite=overwrite):
            return False

        # Step 4: Create typed view
        logger.info("\nCreating typed view...")
        self.create_typed_view()

        # Step 5: Validate
        self.validate_data()

        logger.info("\n" + "=" * 70)
        logger.info("Loading Complete! ✓")
        logger.info("=" * 70)
        logger.info(f"Raw data: {self.table_ref}")
        logger.info(f"Typed view: {self.dataset_ref}.trades_typed (use this for analysis)")
        logger.info("=" * 70)

        return True


def main():
    parser = argparse.ArgumentParser(description="Load MSRB trades data to BigQuery")
    parser.add_argument(
        "--project",
        default="nyu-datasets",
        help="GCP project ID"
    )
    parser.add_argument(
        "--dataset",
        default="munibonds",
        help="BigQuery dataset ID"
    )
    parser.add_argument(
        "--table",
        default="trades",
        help="BigQuery table ID"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing table"
    )

    args = parser.parse_args()

    loader = TradesDataLoader(
        project_id=args.project,
        dataset_id=args.dataset,
        table_id=args.table
    )

    success = loader.load(overwrite=args.overwrite)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
