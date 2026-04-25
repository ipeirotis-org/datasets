#!/usr/bin/env python3
"""
Split multi-year MSRB TSV.GZ files into one file per year.

Reads from: gs://msrb_munibonds_dataset/raw_wrds/msrb_*.tsv.gz
Writes to: gs://msrb_munibonds_dataset/raw_wrds/trades_YYYY.tsv.gz

Handles different schemas across files:
- Some files have lowercase columns, some uppercase
- Some have extra columns (like cusip6)
- Different column orderings

All output files use the same canonical column order (uppercase, 24 columns).

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    python3 split_by_year.py [--delete-source]
"""

import argparse
import gzip
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from google.cloud import storage


# Canonical column order (matches BigQuery schema)
CANONICAL_COLUMNS = [
    'RTRS_CONTROL_NUMBER',
    'TRADE_TYPE_INDICATOR',
    'CUSIP',
    'SECURITY_DESCRIPTION',
    'DATED_DATE',
    'COUPON',
    'MATURITY_DATE',
    'WHEN_ISSUED_INDICATOR',
    'ASSUMED_SETTLEMENT_DATE',
    'TRADE_DATE',
    'TIME_OF_TRADE',
    'SETTLEMENT_DATE',
    'PAR_TRADED',
    'DOLLAR_PRICE',
    'YIELD',
    'BROKERS_BROKER_INDICATOR',
    'WEIGHTED_PRICE_INDICATOR',
    'OFFER_PRICE_TAKEDOWN_INDICATOR',
    'RTRS_PUBLISH_DATE',
    'RTRS_PUBLISH_TIME',
    'VERSION_NUMBER',
    'UV_DOLLAR_PRICE_INDICATOR',
    'ATS_INDICATOR',
    'NTBC_INDICATOR',
]


def build_column_mapping(file_columns):
    """
    Build mapping from canonical position to file column index.
    Returns: list where output[i] = file_index for CANONICAL_COLUMNS[i], or None if missing.
    """
    upper_to_idx = {col.upper(): i for i, col in enumerate(file_columns)}
    mapping = []
    for canonical_col in CANONICAL_COLUMNS:
        mapping.append(upper_to_idx.get(canonical_col))
    return mapping


def split_tsv_by_year(source_blob, target_bucket, project="nyu-datasets", temp_dir=None):
    """Stream a multi-year TSV.GZ file and split by year, normalizing columns."""
    print(f"\n📥 Processing {source_blob.name}...", flush=True)
    size_mb = source_blob.size / (1024 * 1024) if source_blob.size else 0
    print(f"   Size: {size_mb:.1f} MB", flush=True)

    # Download
    local_file = os.path.join(temp_dir, Path(source_blob.name).name)
    print(f"   Downloading...", flush=True)
    source_blob.download_to_filename(local_file)
    print(f"   ✓ Downloaded", flush=True)

    year_files = {}
    year_paths = {}
    year_counts = defaultdict(int)
    rows_processed = 0

    print(f"   Splitting by year...", flush=True)
    canonical_header = '\t'.join(CANONICAL_COLUMNS)

    with gzip.open(local_file, 'rt') as f:
        # Read header and build column mapping
        header = f.readline().strip()
        file_columns = header.split('\t')
        column_map = build_column_mapping(file_columns)

        # Find indices in source
        try:
            trade_date_canonical_idx = CANONICAL_COLUMNS.index('TRADE_DATE')
        except ValueError:
            print(f"   ✗ TRADE_DATE not in canonical schema", flush=True)
            return False

        trade_date_src_idx = column_map[trade_date_canonical_idx]
        if trade_date_src_idx is None:
            print(f"   ✗ TRADE_DATE column not found in source: {file_columns}", flush=True)
            return False

        print(f"   Source has {len(file_columns)} columns; TRADE_DATE at index {trade_date_src_idx}", flush=True)
        missing = [c for c, m in zip(CANONICAL_COLUMNS, column_map) if m is None]
        extra = [c for c in file_columns if c.upper() not in [cc.upper() for cc in CANONICAL_COLUMNS]]
        if missing:
            print(f"   Missing columns (will be empty): {missing}", flush=True)
        if extra:
            print(f"   Extra columns (will be dropped): {extra}", flush=True)

        # Process each line
        for line in f:
            try:
                parts = line.rstrip('\n').split('\t')
                if len(parts) <= trade_date_src_idx:
                    continue

                trade_date = parts[trade_date_src_idx].strip()
                if not trade_date or len(trade_date) < 4:
                    continue

                # Parse year (YYYY/MM/DD format)
                year_str = trade_date[:4]
                if not year_str.isdigit():
                    continue
                year = int(year_str)
                if year < 1990 or year > 2100:
                    continue

                # Reorder columns to canonical order
                normalized_parts = []
                for canonical_idx, src_idx in enumerate(column_map):
                    if src_idx is not None and src_idx < len(parts):
                        normalized_parts.append(parts[src_idx])
                    else:
                        normalized_parts.append('')
                normalized_line = '\t'.join(normalized_parts) + '\n'

                # Open year file if needed
                if year not in year_files:
                    year_path = os.path.join(temp_dir, f"trades_{year}.tsv.gz")
                    year_paths[year] = year_path
                    year_files[year] = gzip.open(year_path, 'wt')
                    year_files[year].write(canonical_header + '\n')
                    print(f"     Started year file: trades_{year}.tsv.gz", flush=True)

                year_files[year].write(normalized_line)
                year_counts[year] += 1
                rows_processed += 1

                if rows_processed % 1_000_000 == 0:
                    print(f"     ...processed {rows_processed:,} rows so far", flush=True)

            except (ValueError, IndexError):
                continue

    print(f"\n   Total rows processed: {rows_processed:,}", flush=True)
    print(f"   Years found: {sorted(year_counts.keys())}", flush=True)

    for year, fh in year_files.items():
        fh.close()
        print(f"     trades_{year}.tsv.gz: {year_counts[year]:,} rows", flush=True)

    # Upload year files (merging with existing if present)
    print(f"\n   Uploading year files to gs://{target_bucket.name}/raw_wrds/...", flush=True)

    for year in sorted(year_paths.keys()):
        year_path = year_paths[year]
        target_path = f"raw_wrds/trades_{year}.tsv.gz"
        target_blob = target_bucket.blob(target_path)

        # Merge with existing if needed
        if target_blob.exists():
            print(f"     Merging with existing trades_{year}.tsv.gz...", flush=True)
            existing_path = os.path.join(temp_dir, f"existing_{year}.tsv.gz")
            target_blob.download_to_filename(existing_path)

            # Dedupe by RTRS_CONTROL_NUMBER (column 0 of canonical schema).
            # Without this, rerunning split_by_year.py duplicates trades.
            merged_path = os.path.join(temp_dir, f"merged_{year}.tsv.gz")
            seen_ctrl = set()
            with gzip.open(merged_path, 'wt') as out:
                # Stream existing file - keep first occurrence of each RTRS_CONTROL_NUMBER
                with gzip.open(existing_path, 'rt') as f:
                    out.write(f.readline())  # header
                    for line in f:
                        ctrl = line.split('\t', 1)[0]
                        if ctrl not in seen_ctrl:
                            seen_ctrl.add(ctrl)
                            out.write(line)
                # Append new rows - skip header, skip already-seen control numbers
                with gzip.open(year_path, 'rt') as f:
                    f.readline()  # skip header
                    for line in f:
                        ctrl = line.split('\t', 1)[0]
                        if ctrl not in seen_ctrl:
                            seen_ctrl.add(ctrl)
                            out.write(line)
            print(f"     Merged with dedup: {len(seen_ctrl):,} unique trades", flush=True)

            os.remove(existing_path)
            os.remove(year_path)
            os.rename(merged_path, year_path)

        size_mb = os.path.getsize(year_path) / (1024 * 1024)
        target_blob.upload_from_filename(year_path)
        print(f"     ✓ Uploaded trades_{year}.tsv.gz ({size_mb:.1f} MB)", flush=True)

        os.remove(year_path)

    os.remove(local_file)
    print(f"   ✓ Cleaned up local files", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="Split multi-year MSRB files into yearly files")
    parser.add_argument("--bucket", default="msrb_munibonds_dataset")
    parser.add_argument("--project", default="nyu-datasets")
    parser.add_argument("--delete-source", action="store_true")
    parser.add_argument("--source-pattern", default="raw_wrds/msrb_")
    parser.add_argument("--only", help="Process only files matching this substring (e.g. '2020_2025')")

    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════════════╗", flush=True)
    print("║  Split MSRB Multi-Year Files into Yearly Files                ║", flush=True)
    print("╚════════════════════════════════════════════════════════════════╝\n", flush=True)

    print("[1/4] Setting up authentication...", flush=True)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("✗ GOOGLE_APPLICATION_CREDENTIALS not set", flush=True)
        sys.exit(1)
    client = storage.Client(project=args.project)
    print(f"✓ Authenticated\n", flush=True)

    print("[2/4] Connecting to bucket...", flush=True)
    bucket = client.bucket(args.bucket)
    if not bucket.exists():
        print(f"✗ Bucket {args.bucket} not found", flush=True)
        sys.exit(1)
    print(f"✓ Connected to gs://{args.bucket}/\n", flush=True)

    print("[3/4] Finding multi-year source files...", flush=True)
    all_blobs = list(bucket.list_blobs(prefix=args.source_pattern))
    multi_year_blobs = [b for b in all_blobs if b.name.endswith('.tsv.gz')
                       and 'msrb_' in b.name and 'trades_' not in b.name]

    if args.only:
        multi_year_blobs = [b for b in multi_year_blobs if args.only in b.name]

    if not multi_year_blobs:
        print(f"✗ No matching multi-year files found", flush=True)
        sys.exit(1)

    print(f"✓ Found {len(multi_year_blobs)} files to process:", flush=True)
    for blob in multi_year_blobs:
        size_mb = blob.size / (1024 * 1024) if blob.size else 0
        print(f"  • {blob.name} ({size_mb:.1f} MB)", flush=True)

    print(f"\n[4/4] Splitting files by year...", flush=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        successful = []
        failed = []

        for blob in multi_year_blobs:
            try:
                if split_tsv_by_year(blob, bucket, args.project, temp_dir=temp_dir):
                    successful.append(blob.name)
                else:
                    failed.append(blob.name)
            except Exception as e:
                print(f"   ✗ Error processing {blob.name}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                failed.append(blob.name)

    print(f"\n{'='*70}", flush=True)
    print(f"Splitting Complete!", flush=True)
    print(f"  Successful: {len(successful)}/{len(multi_year_blobs)}", flush=True)
    print(f"  Failed: {len(failed)}", flush=True)

    if args.delete_source and not failed:
        print(f"\nDeleting original multi-year files...", flush=True)
        for blob in multi_year_blobs:
            blob.delete()
            print(f"  ✓ Deleted {blob.name}", flush=True)

    print(f"\nFinal trades files in gs://{args.bucket}/raw_wrds/:", flush=True)
    final_blobs = list(bucket.list_blobs(prefix="raw_wrds/trades_"))
    for blob in sorted(final_blobs, key=lambda x: x.name):
        size_mb = blob.size / (1024 * 1024) if blob.size else 0
        print(f"  • {blob.name} ({size_mb:.1f} MB)", flush=True)

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
