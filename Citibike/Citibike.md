# Citibike Archive dataset on Google Cloud 

* Create a Google Bucket to store the data 

* Create a service account and give IAM access (Storage Object Admin) permissions. Get the JSON key.

* Create a Google Function that reads the API and writes the output in the Google Bucket. For Citibike we write in date-partitioned parquet

* Create a Google Scheduler call that connects to the API call every 5 mins, and triggers the write to the parquet.

* Create an instance on Google BigQuery.
* * Create an _tablename_\_external table for each Google Bucket dataset (that is mainly for debug/visibility
* * Create a Data Transfer job that reads the external Google Bucket and writes a native Google BigQuery table (with raw suffix)
