# TODO: Datasets ETL

> **Goal**: Maintain and expand the dataset ETL pipelines for course use at NYU Stern.
>
> Last reviewed: 2026-02-15.

---

## Active / High Priority

- [ ] Add US top 100 chart to Shazam dataset
  - Existing TODO in `Shazam/shazam.ipynb`
  - Currently only has non-US charts

- [ ] Verify all Citibike ETL still works with latest trip data format
  - Schema changed in Feb 2021; confirm post-2021 notebook handles current months
  - Check if any new columns have been added since last run

- [ ] Update Flight_Stats data for current semester
  - Ensure BTS and DB1B data covers recent quarters
  - Verify timezone mapping gist is still available

---

## Improvements

- [ ] Add a master README documenting all available datasets
  - Current root README is minimal ("Code for fetching and cleaning datasets")
  - List each dataset with: source, BigQuery table name, refresh frequency, notebook link

- [ ] Automate Flight_Stats ETL
  - Currently manual notebook execution
  - Consider Cloud Function + Scheduler (similar to Citibike pattern)

- [ ] Add data freshness checks
  - Script or notebook that queries BigQuery to report last-loaded date per dataset
  - Flag datasets that are stale for the current semester

---

## Maintenance

- [ ] Audit GCP credentials and service account permissions
  - Ensure notebooks reference correct project and service accounts
  - Document required IAM roles for new collaborators

- [ ] Review Cybersyn/Snowflake example for credential security
  - Ensure no hardcoded credentials in notebook outputs

---

## Future / Low Priority

- [ ] Refactor large notebooks into Python modules with proper tests
  - Restaurant Inspections and Citibike are the most complex
  - Would enable CI/CD for data validation

- [ ] Expand static_datasets with additional reference datasets for assignments

---

_Last updated: 2026-02-15_
