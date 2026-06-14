# MTurk Tracker Dataset

A longitudinal crawl of the public **Amazon Mechanical Turk** marketplace, collected by
[MTurk Tracker](https://www.mturk-tracker.com). The unit of observation is the **HIT group**
(a *batch* of identical tasks posted by one requester), re-observed over time — so the data
captures **how much work was available, at what price, from whom, and how it changed.**

It is market-/requester-side data only: **no worker-level or personally identifiable information.**

## Where the data lives

BigQuery: **`nyu-datasets.mturk_tracker`** (location `US`). Query it from **your own** Google
Cloud project (BigQuery bills scanned bytes to your project); ask the maintainer for
**BigQuery Data Viewer** on the dataset if you don't already have access.

## Start here

**[`MTurk_Tracker_Tutorial.ipynb`](MTurk_Tracker_Tutorial.ipynb)** — a fully documented,
runnable guide: authentication, a data dictionary for every table, example queries with plots,
a worked market-arrival-process example, and the caveats to know before modeling.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ipeirotis-org/datasets/blob/main/MTurk_Tracker/MTurk_Tracker_Tutorial.ipynb)

## Coverage (this copy)

| | |
|---|---|
| Time span | `2014-05-01` → `2015-02-18` (UTC) |
| HIT groups (batches) | 433,156 |
| Requesters | 13,454 |
| Crawl observations | 16,260,725 |

## Tables

| Table | Grain | What |
|---|---|---|
| `hit_groups` | one batch | requester, reward, title, keywords, time allotted, first/last seen |
| `hit_instances` | batch × crawl | HITs available over time (+ per-step diffs) — the time series |
| `hit_content` | one batch | the task's rendered HTML |
| `hit_requesters` | one requester | id → name directory |
| `top_requesters` | requester × snapshot | periodic "largest requesters" rankings |
| `market_statistics` | crawl | market-wide HITs / groups available |
| `arrival_completions` | hour | market-wide HITs / groups / rewards arrived & completed |
| `batch_observations` | view | `hit_instances` ⨝ `hit_groups` ⨝ `hit_requesters` (the modeling panel) |

Each clean table has a lossless `*_raw` companion holding the original Datastore entity JSON.

## Citation

> Djellel Eddine Difallah, Michele Catasta, Gianluca Demartini, Panagiotis G. Ipeirotis,
> Philippe Cudré-Mauroux. *The Dynamics of Micro-Task Crowdsourcing: The Case of Amazon MTurk.*
> WWW 2015.
