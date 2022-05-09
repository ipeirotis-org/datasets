[![Build Status](https://travis-ci.org/ipeirotis/datasets.svg?branch=master)](https://travis-ci.org/ipeirotis/datasets)

# Datasets

This repository contains the code that creates the Google Storage Bucket at https://console.cloud.google.com/storage/browser/datasets_nyu

Other projects can then download or use the datasets from the source above.

The code runs periodically to fetch new data from data sources that update over time. The scripts also perform data cleaning operations.


## Setup

* We follow the instructions at https://cloud.google.com/storage/docs/reference/libraries to fetch the client-secrets.json file
* We encrypt the client-secrets.json file as described in https://docs.travis-ci.com/user/encrypting-files/
* We use the code snippet at https://cloud.google.com/storage/docs/uploading-objects to upload the generated files and make them public

* We use the `travis encrypt` to add the encrypted password for MYSQL (`travis encrypt MYSQL_PASSWORD='XXXXXXXXX' --add`)

* TODO: Figure out how to create the bucket with code, and make the bucket public with code.

## NYPD

* **Source**: [NYPD Complaint Data Historic](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i)
* Output: MySQL database, SQLite db file

## Citibike

## Bike Sharing

## Restaurants 

* **Source**: [NYPD Complaint Data Historic](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i)
* Output: MySQL database, SQLite db file

## Baseball

## ERCOT data

## Flight data: DB1BTicket

From BTS: https://transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FKF&QO_fu146_anzr=b4vtv0%20n0q%20Qr56v0n6v10%20f748rB

## Misc files

| Data Set                    | Source    | Static?   |
|-----------------------------|-----------|-----------|
| acc-deaths.txt              |   | |
| bank-names.txt              |   | |
| lake-huron.txt              |   | |
| routes.csv                  |   | |
| us-population.txt           |   | |
| airlines.csv                |   | | 
| baseball.csv                |   | | 
| origin-of-species.txt       |   | | 
| sample.txt                  |   | | 
| airports.csv                |   | | 
| bike_sharing_daily.csv      |   | | 
| pride_and_prejudice.txt     |   | | 
| tips.csv                    |   | | 
| article.txt                 |   | | 
| bike_sharing_hourly.csv     |   | | 
| rand-terrorism-dataset.txt  |   | | 
| uniquenames.txt             |   | | 
| australian-wine-sales.txt   |   | | 
| cohort-analysis-rewards.csv |   | | 
| restaurant-names.txt        |   | | 
| us-population2.txt |   | | 
