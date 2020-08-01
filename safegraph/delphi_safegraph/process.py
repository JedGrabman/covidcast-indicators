# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from .geo import FIPS_TO_STATE

# Magic number for modular arithmetic; CBG -> FIPS
MOD = 10000000

def construct_signals(cbg_df, signal_names):
    '''Construct Census-block level signals.

    In its current form, we prepare the following signals in addition to those
    already available in raw form from Safegraph:

    - completely_home_prop, defined as:
        completely_home_device_count / device_count
    - full_time_work_prop, defined as:
        full_time_work_behavior_devices / device_count
    - part_time_work_prop, defined as:
        part_time_work_behavior_devices / device_count

    Documentation for the social distancing metrics:
    https://docs.safegraph.com/docs/social-distancing-metrics

    Parameters
    ----------
    cbg_df: pd.DataFrame
        Census block group-level dataframe with raw social distancing
        indicators from Safegraph.
    signal_names: List[str]
        Names of signals to be exported.

    Returns
    -------
    pd.DataFrame
        Dataframe with columns: timestamp, county_fips, and
        {each signal described above}.
    '''
    # Preparation
    cbg_df['timestamp'] = cbg_df['date_range_start'].apply(
                    lambda x: str(x).split('T')[0])
    cbg_df['county_fips'] = (cbg_df['origin_census_block_group'] // MOD).apply(
                            lambda x: f'{int(x):05d}')
    # Transformation: create signal not available in raw data
    cbg_df['completely_home_prop'] = (cbg_df['completely_home_device_count']
                                        / cbg_df['device_count'])
    cbg_df['full_time_work_prop'] =  (cbg_df['full_time_work_behavior_devices']
                                        / cbg_df['device_count'])
    cbg_df['part_time_work_prop'] =  (cbg_df['part_time_work_behavior_devices']
                                        / cbg_df['device_count'])
    # Subsetting
    return cbg_df[['timestamp', 'county_fips'] + signal_names]

def aggregate(df, signal_names, geo_resolution='county'):
    '''Aggregate signals to appropriate resolution and produce standard errors.

    Parameters
    ----------
    df: pd.DataFrame
        County block group-level data with prepared signals (output of
        construct_signals().
    signal_names: List[str]
        Names of signals to be exported.
    geo_resolution: str
        One of ('county', 'state')

    Returns
    -------
    pd.DataFrame:
        DataFrame with one row per geo_id, with columns for the individual
        signals, standard errors, and sample sizes.
    '''
    # Prepare geo resolution
    GEO_RESOLUTION = ('county', 'state')
    if geo_resolution == 'county':
        df['geo_id'] = df['county_fips']
    elif geo_resolution == 'state':
        df['geo_id'] = df['county_fips'].apply(lambda x:
                FIPS_TO_STATE[x[:2]])
    else:
        raise ValueError(f'`geo_resolution` must be one of {GEO_RESOLUTION}.')

    # Aggregation and signal creation
    df_mean = df.groupby(['geo_id', 'timestamp'])[
            signal_names
           ].mean()
    df_sd = df.groupby(['geo_id', 'timestamp'])[
            signal_names
           ].std()
    df_n = df.groupby(['geo_id', 'timestamp'])[
            signal_names
           ].count()
    agg_df = pd.DataFrame.join(df_mean, df_sd,
            lsuffix='_mean', rsuffix='_sd')
    agg_df = pd.DataFrame.join(agg_df, df_n.rename({
               signal: signal+'_n' for signal in signal_names
           }, axis=1))
    for signal in signal_names:
        agg_df[f'{signal}_se'] = (agg_df[f'{signal}_sd']
                                 /np.sqrt(agg_df[f'{signal}_n']))
    return agg_df.reset_index()

def process(fname, signals, geo_resolutions, export_dir):
    '''Process an input census block group-level CSV and export it.  Assumes
    that the input file has _only_ one date of data.

    Parameters
    ----------
    fname: str
        Input filename.
    signals: List[Tuple[str, bool]]
        List of (signal_name, wip).
    geo_resolutions: List[str]
        List of geo resolutions to export the data.

    Returns
    -------
    None
    '''
    signal_names, wip = (list(x) for x in zip(*signals))
    cbg_df = construct_signals(pd.read_csv(fname), signal_names)
    unique_date = cbg_df['timestamp'].unique()
    if len(unique_date) != 1:
        raise ValueError(f'More than one timestamp found in input file {fname}.')
    date = unique_date[0].replace('-', '')
    for geo_res in geo_resolutions:
        df = aggregate(cbg_df, signal_names, geo_res)
        for signal, wip in signals:
            df_export = df[
                    ['geo_id']
                    + [f'{signal}_{x}' for x in ('mean', 'se', 'n')]
                    ].rename({
                        f'{signal}_mean': 'val',
                        f'{signal}_se': 'se',
                        f'{signal}_n': 'sample_size',
                    }, axis=1)
            if wip:
                signal = 'wip_' + signal
            df_export.to_csv(f'{export_dir}/{date}_{geo_res}_{signal}.csv',
                    na_rep='NA',
                    index=False,)
    return
