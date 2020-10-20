# -*- coding: utf-8 -*-
"""Functions to call when running the function.

This module should contain a function called `run_module`, that is executed
when the module is run with `python -m MODULE_NAME`.
"""
from datetime import datetime
from itertools import product

import numpy as np
from delphi_utils import read_params, create_export_csv

from .pull import pull_gs_data
from .constants import METRICS, GEO_RESOLUTIONS, SMOOTHERS, SMOOTHERS_MAP


def run_module():

    params = read_params()
    export_start_date = datetime.strptime(params["export_start_date"], "%Y-%m-%d")
    export_dir = params["export_dir"]
    base_url = params["base_url"]

    for geo_res in GEO_RESOLUTIONS:
        df = pull_gs_data(base_url, METRICS, geo_res)
        for metric, smoother in product(METRICS, SMOOTHERS):
            print(geo_res, metric, smoother)
            df["val"] = SMOOTHERS_MAP[smoother][0](df["symptom:"+metric].values)
            df["se"] = np.nan
            df["sample_size"] = np.nan
            # Drop early entries where data insufficient for smoothing
            df = df.loc[~df["val"].isnull(), :]
            sensor_name = "_".join(["wip", smoother, "search"])
            create_export_csv(
                df,
                export_dir=export_dir,
                start_date=SMOOTHERS_MAP[smoother][1](export_start_date),
                metric=metric.lower(),
                geo_res=geo_res,
                sensor=sensor_name,
            )