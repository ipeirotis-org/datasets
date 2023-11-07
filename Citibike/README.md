# Citibike Archive dataset on Google Cloud 

### Create a Google Bucket to store the data

```
gsutil mb gs://citibike-archive
```

### Create a service account and give IAM access (Storage Object Admin) permissions. Get the JSON key.

```
gcloud iam service-accounts create citibike-sa --display-name "Citibike Service Account"
gcloud projects add-iam-policy-binding nyu-datasets --member "serviceAccount:citibike-sa@nyu-datasets.iam.gserviceaccount.com" --role "roles/storage.objectAdmin"
gcloud iam service-accounts keys create ~/citibike-sa-key.json --iam-account citibike-sa@nyu-datasets.iam.gserviceaccount.com
```

### Create a Google Function that reads the API and writes the output in the Google Bucket. For Citibike we write in date-partitioned parquet

```
gcloud functions deploy citibike --runtime python39 --trigger-http --entry-point citibike --memory 128MB --timeout 540s --service-account citibike-sa@nyu-datasets.iam.gserviceaccount.com
```

### Create a Google Scheduler call that connects to the API call every 5 mins, and triggers the write to the parquet.

```
gcloud scheduler jobs create http citibike-scheduler --schedule "*/5 * * * *" --uri "https://us-central1-nyu-datasets.cloudfunctions.net/citibike-station-information" --http-method GET
```

### Create an instance on Google BigQuery.

```
bq mk --location=US --dataset citibike
```

* * Create an _tablename_\_external table for each Google Bucket dataset (that is mainly for debug/visibility
* * Create a Data Transfer job that reads the external Google Bucket and writes a native Google BigQuery table (with raw suffix)
