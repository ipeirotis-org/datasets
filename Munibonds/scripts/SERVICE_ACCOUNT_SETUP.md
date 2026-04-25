# Service Account Setup for MSRB Pipeline

A dedicated service account `msrb-pipeline@nyu-datasets.iam.gserviceaccount.com` handles all GCS and BigQuery operations for the munibonds pipeline.

## Why Service Account?

- ✅ **No expiration** - Keys don't expire like access tokens (1 hour)
- ✅ **Reproducible** - Anyone with the key can run the pipeline
- ✅ **Auditable** - All actions logged under SA identity
- ✅ **Least privilege** - Only the permissions needed, nothing more

## Service Account Details

| Field | Value |
|-------|-------|
| Name | `msrb-pipeline` |
| Project | `nyu-datasets` |
| Email | `msrb-pipeline@nyu-datasets.iam.gserviceaccount.com` |
| Display Name | MSRB Munibonds Pipeline |

## Permissions

### `nyu-datasets` project (target)
- `roles/storage.admin` - Manage buckets, read/write objects
- `roles/bigquery.admin` - Create datasets, tables, run queries

### `ipeirotis-hrd` project (source)
- `roles/storage.objectViewer` - Read source MSRB files

## Creating the Service Account

If the service account doesn't exist yet, create it from Cloud Shell:

```bash
# 1. Create service account
gcloud iam service-accounts create msrb-pipeline \
    --project=nyu-datasets \
    --display-name="MSRB Munibonds Pipeline"

# 2. Grant target permissions (nyu-datasets)
SA_EMAIL="msrb-pipeline@nyu-datasets.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding nyu-datasets \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin" \
    --condition=None

gcloud projects add-iam-policy-binding nyu-datasets \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.admin" \
    --condition=None

# 3. Grant source read permissions (ipeirotis-hrd)
gcloud projects add-iam-policy-binding ipeirotis-hrd \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectViewer" \
    --condition=None

# 4. Create JSON key
gcloud iam service-accounts keys create msrb-pipeline-key.json \
    --iam-account=${SA_EMAIL}
```

## Using the Service Account

Set the credential file path:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/msrb-pipeline-key.json
```

All Python scripts that use `google-cloud-storage` or `google-cloud-bigquery` will automatically pick this up.

### Examples

```bash
# Migrate data
python3 scripts/migrate_direct.py

# Split by year
python3 scripts/split_by_year.py

# Load to BigQuery
python3 ingestion/load_trades_to_bigquery.py --overwrite
```

## Security Best Practices

⚠️ **Never commit the JSON key file to Git!**

Add to `.gitignore`:
```
msrb-pipeline-key.json
*.json.key
service-account-*.json
```

### Storing the Key

- **Local development**: Save in `~/.config/msrb-pipeline-key.json` with `chmod 600`
- **CI/CD**: Use GitHub Secrets or GCP Secret Manager
- **Production**: Use Workload Identity Federation (no key files needed)

### Rotating Keys

Keys should be rotated regularly:

```bash
# 1. List existing keys
gcloud iam service-accounts keys list \
    --iam-account=msrb-pipeline@nyu-datasets.iam.gserviceaccount.com

# 2. Create new key
gcloud iam service-accounts keys create new-key.json \
    --iam-account=msrb-pipeline@nyu-datasets.iam.gserviceaccount.com

# 3. Update applications to use new key

# 4. Delete old key
gcloud iam service-accounts keys delete <KEY_ID> \
    --iam-account=msrb-pipeline@nyu-datasets.iam.gserviceaccount.com
```

## Verification

Test the service account works:

```bash
# Test storage access
python3 -c "
from google.cloud import storage
client = storage.Client(project='nyu-datasets')
bucket = client.bucket('msrb_munibonds_dataset')
print(f'Bucket exists: {bucket.exists()}')
print('Files:')
for blob in bucket.list_blobs(max_results=5):
    print(f'  - {blob.name}')
"

# Test BigQuery access
python3 -c "
from google.cloud import bigquery
client = bigquery.Client(project='nyu-datasets')
print(f'Datasets in nyu-datasets:')
for ds in client.list_datasets():
    print(f'  - {ds.dataset_id}')
"
```

## Troubleshooting

### "Permission denied" errors

Verify the SA has the necessary roles:
```bash
gcloud projects get-iam-policy nyu-datasets \
    --flatten="bindings[].members" \
    --filter="bindings.members:msrb-pipeline*"
```

### "Cannot create key"

You may have hit the SA key quota (10 max). List and delete old keys:
```bash
gcloud iam service-accounts keys list \
    --iam-account=msrb-pipeline@nyu-datasets.iam.gserviceaccount.com
```

### Token expired errors

If using `gcloud auth print-access-token` instead of SA key, tokens expire after 1 hour.
**Switch to using the SA key** for long-running operations.
