# -*- coding: utf-8 -*-
"""Functions to call when running the function.

This module should contain a function called `run_module`, that is executed
when the module is run with `python -m MODULE_NAME`.
"""
from datetime import datetime, date, timedelta
from itertools import product
import os
from os.path import join

import pandas as pd
from delphi_utils import read_params

from .geo_maps import (zip_to_msa, zip_to_hrr, zip_to_county, zip_to_state)
from .pull import pull_quidel_covidtest, check_intermediate_file
from .export import export_csv
from .generate_sensor import (generate_sensor_for_states,
                              generate_sensor_for_other_geores)

# global constants
MIN_OBS = 50  # minimum number of observations in order to compute a proportion.
POOL_DAYS = 7  # number of days in the past (including today) to pool over

GEO_RESOLUTIONS = [
    "county",
    "msa",
    "hrr"
]
SENSORS = [
    "wip_smoothed_pct_positive",
    "wip_raw_pct_positive"
]
SMOOTHERS = {
    "wip_smoothed_pct_positive": True,
    "wip_raw_pct_positive": False
}

def run_module():

    params = read_params()
    cache_dir = params["cache_dir"]
    export_dir = params["export_dir"]
    static_file_dir = params["static_file_dir"]

    mail_server = params["mail_server"]
    account = params["account"]
    password = params["password"]
    sender = params["sender"]

    export_start_date = datetime.strptime(params["export_start_date"], '%Y-%m-%d')
    # If no export end date defined, set todya - 5 days
    if params["export_end_date"] == "":
        export_end_date = datetime.today() - timedelta(days=5)
    else:
        export_end_date = datetime.strptime(params["export_end_date"], '%Y-%m-%d')

    # pull new data only that has not been ingested
    pull_start_date = datetime.strptime(params["pull_start_date"], '%Y-%m-%d').date()
    filename, pull_start_date = check_intermediate_file(cache_dir, pull_start_date)

    if params["pull_end_date"] == "":
        pull_end_date = date.today()
    else:
        pull_end_date = datetime.strptime(params["pull_end_date"], '%Y-%m-%d').date()

    if pull_end_date < pull_start_date:
        print("The data is up-to-date. Currently, no new data to be ingested.")
        return

    map_df = pd.read_csv(
        join(static_file_dir, "fips_prop_pop.csv"), dtype={"fips": int}
    )

    # Pull data from the email at 5 digit zipcode level
    # Use _end_date to check the most recent date that we received data
    df, _end_date = pull_quidel_covidtest(pull_start_date, pull_end_date, mail_server,
                               account, sender, password)
    if filename is not None:
        previous_df = pd.read_csv(join(cache_dir, filename), sep=",", parse_dates=["timestamp"])
        df = previous_df.append(df).groupby(["timestamp", "zip"]).sum().reset_index()
        # Save the intermediate file to cache_dir which can be re-used next time
        os.remove(join(cache_dir, filename))
    df.to_csv(join(cache_dir, "pulled_until_%s.csv")%_end_date.strftime("%Y%m%d"), index=False)

    first_date = df["timestamp"].min()
    last_date = df["timestamp"].max()

    # State Level
    data = df.copy()
    state_data = zip_to_state(data, map_df)
    # Compute raw signal
    raw_state_df, state_groups = generate_sensor_for_states(state_data, smooth=False,
                                                            first_date=first_date,
                                                            last_date=last_date)
    export_csv(raw_state_df, "state", "wip_raw_pct_positive", receiving_dir=export_dir,
               start_date=export_start_date, end_date=export_end_date)
    # Compute smoothed signal
    smoothed_state_df, _ = generate_sensor_for_states(state_data, smooth=True,
                                                      first_date=first_date,
                                                      last_date=last_date)
    export_csv(smoothed_state_df, "state", "wip_smoothed_pct_positive", receiving_dir=export_dir,
               start_date=export_start_date, end_date=export_end_date)

    # County/HRR/MSA level
    for geo_res, sensor in product(GEO_RESOLUTIONS, SENSORS):
        print(geo_res, sensor)
        data = df.copy()
        if geo_res == "county":
            data, res_key = zip_to_county(data, map_df)
        elif geo_res == "msa":
            data, res_key = zip_to_msa(data, map_df)
        else:
            data, res_key = zip_to_hrr(data, map_df)

        res_df = generate_sensor_for_other_geores(state_groups, data, res_key,
                                                  smooth=SMOOTHERS[sensor],
                                                  first_date=first_date,
                                                  last_date=last_date)
        export_csv(res_df, geo_res, sensor, receiving_dir=export_dir,
                   start_date=export_start_date, end_date=export_end_date)
