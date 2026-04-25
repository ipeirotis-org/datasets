"""
Munibonds: Python library for analyzing MSRB municipal bond trading data.

This module provides a clean interface to query municipal bond trades stored in
BigQuery (nyu-datasets.munibonds.trades). It replaces the legacy MySQL-based
implementation with BigQuery for better scalability and performance.

Authentication uses Google Cloud Application Default Credentials (ADC).
Set up with: `gcloud auth application-default login`

Example usage:
    from bonds import Munibonds, Munidata

    mb = Munibonds()

    # Get bonds matching activity criteria
    bonds = mb.get_bonds(min_trades=100, min_dates_traded=10)

    # Get trading history for specific CUSIPs
    history = mb.history(['12345678'], column='AVG_PRICE')

    # Find similar bonds
    md = Munidata(['12345678'])
    similar = md.get_similar('12345678', n=5)
"""

import pandas as pd
import matplotlib.pyplot as plt
from google.cloud import bigquery


# Default configuration
DEFAULT_PROJECT = "nyu-datasets"
DEFAULT_DATASET = "munibonds"
DEFAULT_TABLE = "trades_typed"  # Use the typed view (parsed DATE/TIME columns)


class Munibonds:
    """Query interface for MSRB municipal bond trades stored in BigQuery."""

    def __init__(self, project=DEFAULT_PROJECT, dataset=DEFAULT_DATASET,
                 table=DEFAULT_TABLE):
        """
        Initialize the BigQuery client and table reference.

        Args:
            project: GCP project ID (default: nyu-datasets)
            dataset: BigQuery dataset (default: munibonds)
            table: BigQuery table (default: trades)
        """
        self.project = project
        self.dataset = dataset
        self.table = table
        self.table_ref = f"`{project}.{dataset}.{table}`"
        self.client = bigquery.Client(project=project)

    def query(self, sql, params=None):
        """Execute a parameterized BigQuery query and return a DataFrame."""
        job_config = bigquery.QueryJobConfig()
        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(name, type_, value)
                for name, (type_, value) in params.items()
            ]
        return self.client.query(sql, job_config=job_config).to_dataframe()

    def get_bonds(self, min_trades=100, min_dates_traded=10,
                  min_fraction_days_traded=0.1):
        """
        Get bonds matching activity criteria.

        Args:
            min_trades: Minimum number of trades
            min_dates_traded: Minimum number of unique trading dates
            min_fraction_days_traded: Minimum fraction of days with trades

        Returns:
            DataFrame with bond statistics, sorted by NUM_TRADES descending
        """
        sql = f"""
        WITH cusip_stats AS (
            SELECT
                CUSIP,
                ANY_VALUE(SECURITY_DESCRIPTION) AS SECURITY_DESCRIPTION,
                MIN(MATURITY_DATE) AS MATURITY_DATE,
                MIN(DATED_DATE) AS DATED_DATE,
                MIN(COUPON) AS COUPON,
                COUNT(*) AS NUM_TRADES,
                COUNT(DISTINCT TRADE_DATE) AS NUM_DATES_TRADED,
                COUNT(DISTINCT TRADE_DATE) /
                    DATE_DIFF(MAX(TRADE_DATE), MIN(TRADE_DATE), DAY)
                    AS FRACTION_DAYS_TRADED
            FROM {self.table_ref}
            WHERE CUSIP IS NOT NULL
            GROUP BY CUSIP
        )
        SELECT *
        FROM cusip_stats
        WHERE NUM_TRADES > @min_trades
          AND NUM_DATES_TRADED > @min_dates_traded
          AND FRACTION_DAYS_TRADED > @min_fraction_days_traded
        ORDER BY NUM_TRADES DESC
        """

        params = {
            "min_trades": ("INT64", min_trades),
            "min_dates_traded": ("INT64", min_dates_traded),
            "min_fraction_days_traded": ("FLOAT64", min_fraction_days_traded),
        }
        return self.query(sql, params)

    def get_title(self, cusip):
        """Get the security description for a CUSIP."""
        sql = f"""
        SELECT SECURITY_DESCRIPTION
        FROM {self.table_ref}
        WHERE CUSIP = @cusip
        LIMIT 1
        """
        df = self.query(sql, {"cusip": ("STRING", cusip)})
        return df.iloc[0].SECURITY_DESCRIPTION if not df.empty else None

    def securities(self, cusips):
        """
        Get security details for one or more CUSIPs.

        Args:
            cusips: Single CUSIP string or list/tuple of CUSIPs

        Returns:
            DataFrame with bond details
        """
        if isinstance(cusips, str):
            cusips = [cusips]

        sql = f"""
        SELECT DISTINCT
            CUSIP,
            SECURITY_DESCRIPTION,
            DATED_DATE,
            COUPON,
            MATURITY_DATE
        FROM {self.table_ref}
        WHERE CUSIP IN UNNEST(@cusips)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("cusips", "STRING", list(cusips))
            ]
        )
        return self.client.query(sql, job_config=job_config).to_dataframe()

    def history(self, cusips, column='AVG_PRICE'):
        """
        Get daily trading history for one or more CUSIPs.

        Args:
            cusips: Single CUSIP or list of CUSIPs
            column: Column to pivot on - 'AVG_PRICE', 'AVG_YIELD',
                   'STDDEV_PRICE', 'STDDEV_YIELD', 'NUM_TRADES'

        Returns:
            DataFrame indexed by TRADE_DATE, columns are CUSIPs
        """
        if isinstance(cusips, str):
            cusips = [cusips]

        sql = f"""
        SELECT
            CUSIP,
            TRADE_DATE,
            AVG(YIELD) AS AVG_YIELD,
            STDDEV(YIELD) AS STDDEV_YIELD,
            AVG(DOLLAR_PRICE) AS AVG_PRICE,
            STDDEV(DOLLAR_PRICE) AS STDDEV_PRICE,
            COUNT(*) AS NUM_TRADES
        FROM {self.table_ref}
        WHERE CUSIP IN UNNEST(@cusips)
          AND DOLLAR_PRICE IS NOT NULL
          AND TRADE_TYPE_INDICATOR = 'D'
        GROUP BY CUSIP, TRADE_DATE
        ORDER BY CUSIP, TRADE_DATE
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("cusips", "STRING", list(cusips))
            ]
        )
        df = self.client.query(sql, job_config=job_config).to_dataframe()

        return df.pivot_table(
            index='TRADE_DATE',
            columns='CUSIP',
            values=column
        ).sort_index()

    def correlations(self, cusips, column='AVG_PRICE', min_periods=50):
        """
        Compute pairwise Pearson correlations between bond price/yield series.

        Args:
            cusips: List of CUSIPs to compute correlations for
            column: Which series to correlate (AVG_PRICE, AVG_YIELD)
            min_periods: Minimum overlap for correlation calculation

        Returns:
            Correlation matrix as DataFrame
        """
        df = self.history(cusips, column=column)
        return df.corr(method='pearson', min_periods=min_periods)

    def plot_history(self, cusips, column='AVG_PRICE', figsize=(15, 10)):
        """
        Plot trading history for one or more CUSIPs.

        Args:
            cusips: Single CUSIP or list of CUSIPs
            column: Column to plot
            figsize: Figure size tuple

        Returns:
            Matplotlib axes object
        """
        if isinstance(cusips, str):
            cusips = [cusips]

        history = self.history(cusips, column=column)
        fig, ax = plt.subplots(figsize=figsize)

        title_parts = [
            f"{cusip} / {self.get_title(cusip)}"
            for cusip in cusips
        ]
        ax.set_title("\n".join(title_parts))
        history.plot(ax=ax)
        return ax


class Munidata:
    """Helper class for similarity analysis on bond price/yield data."""

    def __init__(self, cusips, column='AVG_PRICE'):
        """
        Load history for given CUSIPs.

        Args:
            cusips: List of CUSIPs to analyze
            column: Column to use - AVG_PRICE or AVG_YIELD
        """
        self.column = column
        self.data = Munibonds().history(cusips, column)

    def get_similar(self, cusip, n, min_overlap=0.25, min_periods=100):
        """
        Find n most similar bonds to the given CUSIP based on price correlation.

        Args:
            cusip: Reference CUSIP
            n: Number of similar bonds to return
            min_overlap: Minimum fraction of overlap required
            min_periods: Absolute minimum periods for correlation

        Returns:
            DataFrame with similarity scores and bond details
        """
        timeseries = self.data[cusip]
        periods = len(timeseries)
        threshold = max(int(periods * min_overlap), min_periods)

        similarity = lambda x: x.corr(timeseries, min_periods=threshold)
        corr = (
            self.data.apply(similarity)
            .sort_values(ascending=False)
            [1:n+1]
            .to_frame(name='Similarity')
        )

        # Augment with bond details
        query_cusips = list(corr.index) + [cusip]
        results = (
            Munibonds()
            .securities(query_cusips)
            .drop_duplicates(subset='CUSIP')
            .set_index('CUSIP')
            .join(corr)
        )
        # Self-similarity = 1
        results.loc[cusip, 'Similarity'] = 1
        return results.sort_values('Similarity', ascending=False)


# Backwards compatibility aliases (lowercase class names from original API)
munibonds = Munibonds
munidata = Munidata
