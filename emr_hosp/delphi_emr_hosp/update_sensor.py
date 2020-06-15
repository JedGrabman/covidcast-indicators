"""
Generate EMR-hosp sensors.

Author: Maria Jahja
Created: 2020-06-01
"""

# standard packages
import logging
from datetime import timedelta
from multiprocessing import Pool, cpu_count

# third party
import numpy as np
import pandas as pd

# first party
from .config import Config, Constants
from .geo_maps import GeoMaps
from .load_data import load_combined_data
from .sensor import EMRHospSensor
from .weekday import Weekday


def write_to_csv(output_dict, out_name, output_path="."):
    """Write sensor values to csv.

    Args:
        output_dict: dictionary containing sensor rates, se, unique dates, and unique geo_id
        output_path: outfile path to write the csv (default is current directory)
    """

    geo_level = output_dict["geo_level"]
    dates = output_dict["dates"]
    geo_ids = output_dict["geo_ids"]
    all_rates = output_dict["rates"]
    all_se = output_dict["se"]
    all_include = output_dict["include"]

    out_n = 0
    for i, d in enumerate(dates):
        filename = "%s/%s_%s_%s.csv" % (
            output_path,
            (d + Config.DAY_SHIFT).strftime("%Y%m%d"),
            geo_level,
            out_name,
        )

        with open(filename, "w") as outfile:
            outfile.write("geo_id,val,se,direction,sample_size\n")

            for geo_id in geo_ids:
                sensor = all_rates[geo_id][i]
                se = all_se[geo_id][i]

                if all_include[geo_id][i]:
                    assert not np.isnan(sensor), "value for included sensor is nan"
                    assert not np.isnan(se), "se for included sensor is nan"
                    assert sensor < 90, f"value suspiciously high, {geo_id}: {sensor}"
                    assert se < 5, f"se suspiciously high, {geo_id}: {se}"

                    # for privacy reasons we will not report the standard error
                    outfile.write(
                        "%s,%f,%s,%s,%s\n" % (geo_id, sensor, "NA", "NA", "NA")
                    )
                    out_n += 1
    logging.debug(f"wrote {out_n} rows for {len(geo_ids)} {geo_level}")


def update_sensor(
        emr_filepath,
        claims_filepath,
        outpath,
        staticpath,
        startdate,
        enddate,
        dropdate,
        geo,
        parallel,
        weekday):
    """Generate sensor values, and write to csv format.

    Args:
        emr_filepath: path to the aggregated EMR data
        claims_filepath: path to the aggregated claims data
        outpath: output path for the csv results
        staticpath: path for the static geographic files
        startdate: first sensor date (YYYY-mm-dd)
        enddate: last sensor date (YYYY-mm-dd)
        dropdate: data drop date (YYYY-mm-dd)
        geo: geographic resolution, one of ["county", "state", "msa", "hrr"]
        parallel: boolean to run the sensor update in parallel
        weekday: boolean to adjust for weekday effects
    """

    # handle dates
    startdate, enddate, dropdate = map(pd.to_datetime, [startdate, enddate, dropdate])
    assert (startdate > (Config.FIRST_DATA_DATE + Config.BURN_IN_PERIOD)
            ), f"not enough data to produce estimates starting {startdate}"
    assert startdate < enddate, "start date >= end date"
    assert enddate <= dropdate, "end date > drop date"

    # we will shift estimates one day forward to account for a 1 day lag, e.g.
    # we want to produce estimates for the time range May 2 to May 20, inclusive
    # given a drop on May 20, we have data up until May 19.
    # we then train on data from Jan 1 until May 19, storing only the sensors
    # on May 1 to May 19. we then shift the dates forward by 1, giving us sensors
    # on May 2 to May 20. therefore, we will move the startdate back by one day
    # in order to get the proper estimate at May 1
    drange = lambda s, e: np.array([s + timedelta(days=x) for x in range((e - s).days)])
    startdate = startdate - Config.DAY_SHIFT
    burnindate = startdate - Config.BURN_IN_PERIOD
    fit_dates = drange(Config.FIRST_DATA_DATE, dropdate)
    burn_in_dates = drange(burnindate, dropdate)
    sensor_dates = drange(startdate, enddate)
    final_sensor_idxs = np.where(
        (burn_in_dates >= startdate) & (burn_in_dates <= enddate))

    # load data
    base_geo = "hrr" if geo == "hrr" else "fips"
    data = load_combined_data(emr_filepath, claims_filepath, dropdate, base_geo)

    # get right geography
    geo_map = GeoMaps(staticpath)
    if geo.lower() == "county":
        data_frame = geo_map.county_to_megacounty(data)
    elif geo.lower() == "state":
        data_frame = geo_map.county_to_state(data)
    elif geo.lower() == "msa":
        data_frame = geo_map.county_to_msa(data)
    elif geo.lower() == "hrr":
        data_frame = data  # data is already adjusted in aggregation step above
    else:
        logging.error(f"{geo} is invalid, pick one of 'county', 'state', 'msa', 'hrr'")
        return False
    unique_geo_ids = list(sorted(np.unique(data_frame.index.get_level_values(0))))

    # for each location, fill in all missing dates with 0 values
    print(len(unique_geo_ids), len(fit_dates))
    multiindex = pd.MultiIndex.from_product((unique_geo_ids, fit_dates),
                                            names=[geo, "date"])
    assert (len(multiindex) <= (Constants.MAX_GEO[geo] * len(fit_dates))
            ), "more loc-date pairs than maximum number of geographies x number of dates"

    # fill dataframe with missing dates using 0
    data_frame = data_frame.reindex(multiindex, fill_value=0)
    data_frame.fillna(0, inplace=True)

    # handle if we need to adjust by weekday
    params = Weekday.get_params(data_frame) if weekday else None

    # run sensor fitting code (maybe in parallel)
    sensor_rates = {}
    sensor_se = {}
    sensor_include = {}
    if not parallel:
        for geo_id in unique_geo_ids:
            sub_data = data_frame.loc[geo_id].copy()
            if weekday:
                sub_data = Weekday.calc_adjustment(params, sub_data)

            res = EMRHospSensor.fit(sub_data, burn_in_dates, geo_id)
            sensor_rates[geo_id] = res["rate"][final_sensor_idxs]
            sensor_se[geo_id] = res["se"][final_sensor_idxs]
            sensor_include[geo_id] = res["incl"][final_sensor_idxs]

    else:
        n_cpu = min(10, cpu_count())
        logging.debug(f"starting pool with {n_cpu} workers")

        with Pool(n_cpu) as pool:
            pool_results = []
            for geo_id in unique_geo_ids:
                sub_data = data_frame.loc[geo_id].copy()
                if weekday:
                    sub_data = Weekday.calc_adjustment(params, sub_data)

                pool_results.append(
                    pool.apply_async(
                        EMRHospSensor.fit, args=(sub_data, burn_in_dates, geo_id,),
                    )
                )
            pool_results = [proc.get() for proc in pool_results]

            for res in pool_results:
                geo_id = res["geo_id"]
                sensor_rates[geo_id] = res["rate"][final_sensor_idxs]
                sensor_se[geo_id] = res["se"][final_sensor_idxs]
                sensor_include[geo_id] = res["incl"][final_sensor_idxs]

    unique_geo_ids = list(sensor_rates.keys())
    output_dict = {
        "rates": sensor_rates,
        "se": sensor_se,
        "dates": sensor_dates,
        "geo_ids": unique_geo_ids,
        "geo_level": geo,
        "include": sensor_include,
    }

    # write out results
    wip_string = "wip_XXXXX_"
    out_name = "smoothed_adj_cli" if weekday else "smoothed_cli"
    write_to_csv(output_dict, wip_string + out_name, outpath)
    logging.debug(f"wrote files to {outpath}")
    return True