#!/usr/bin/env python3
"""
Migrate MSRB trades data from ipeirotis-hrd.msrb_munibonds to
nyu-datasets.msrb_munibonds_dataset bucket using service account auth.

Authentication:
    Set GOOGLE_APPLICATION_CREDENTIALS to service account JSON key file path.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    python3 migrate_direct.py
"""

import os
import sys
from pathlib import Path

from google.cloud import storage


def migrate_data(source_project="ipeirotis-hrd",
                target_project="nyu-datasets"):
    """Migrate MSRB data from source to target bucket."""

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║  MSRB Munibonds GCS Migration                                  ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("✗ GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        print("  Set it to the path of your service account JSON key file.")
        return False

    # Setup clients
    print("[1/4] Connecting to GCS...")
    source_client = storage.Client(project=source_project)
    target_client = storage.Client(project=target_project)

    source_bucket_name = "msrb_munibonds"
    target_bucket_name = "msrb_munibonds_dataset"

    source_bucket = source_client.bucket(source_bucket_name)
    target_bucket = target_client.bucket(target_bucket_name)

    if not source_bucket.exists():
        print(f"✗ Source bucket {source_bucket_name} not found")
        return False
    print(f"✓ Source bucket: gs://{source_bucket_name}/")

    if not target_bucket.exists():
        print(f"Creating target bucket {target_bucket_name}...")
        target_bucket.create(location="US")
        print(f"✓ Created: gs://{target_bucket_name}/")
    else:
        print(f"✓ Target bucket exists: gs://{target_bucket_name}/")

    # List source files
    print("\n[2/4] Listing source files...")
    blobs = list(source_bucket.list_blobs())
    tsv_files = [b for b in blobs if b.name.endswith('.tsv.gz')]
    print(f"Found {len(tsv_files)} TSV.GZ files")

    if not tsv_files:
        print("✗ No TSV.GZ files found!")
        return False

    # Copy files
    print(f"\n[3/4] Copying files to gs://{target_bucket_name}/raw_wrds/\n")

    for i, source_blob in enumerate(tsv_files, 1):
        filename = Path(source_blob.name).name
        target_path = f"raw_wrds/{filename}"
        target_blob = target_bucket.blob(target_path)

        size_mb = source_blob.size / (1024 * 1024) if source_blob.size else 0
        print(f"  [{i}/{len(tsv_files)}] Copying {filename} ({size_mb:.1f} MB)...")

        # Use Blob.rewrite for large file support
        rewrite_token = None
        while True:
            rewrite_token, bytes_rewritten, total_bytes = target_blob.rewrite(
                source_blob, token=rewrite_token
            )
            if rewrite_token is None:
                break

        print(f"           ✓ Copied to {target_path}")

    # Verify
    print(f"\n[4/4] Verification...")
    target_files = list(target_bucket.list_blobs(prefix="raw_wrds/"))
    print(f"✓ Target bucket contains {len(target_files)} files in raw_wrds/\n")

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║  Migration Complete! ✓                                         ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")

    print(f"Data location: gs://{target_bucket_name}/raw_wrds/")
    print("\nNext steps:")
    print("  1. Verify files: gcloud storage ls gs://msrb_munibonds_dataset/raw_wrds/")
    print("  2. Split by year: python3 scripts/split_by_year.py")
    print("  3. Load to BigQuery: python3 1_ingestion/load_trades_to_bigquery.py")

    return True


def main():
    try:
        success = migrate_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
