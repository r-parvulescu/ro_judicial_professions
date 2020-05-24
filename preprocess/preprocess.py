"""
Functions for augmenting  person-period table with extra columns.
infile headers: nume, prenume, instanță/parchet, an, lună
"""

import os
import csv
import pandas as pd
from preprocess import standardise
from preprocess import sample
from preprocess import pids
from preprocess.workplace import workplace
from preprocess.gender import gender


def preprocess(in_directory, out_path, std_log_path, pids_log_path, profession):
    """
    Standardise data from person-period tables at different levels of time granularity (year and month levels),
    sample person-months to get person-years, combine this sample with the original year-level data, clean the
    combined table, assign every person-year a row ID gender, institution profile, and unique (row) ID, and finally
     assign each row a person-level unique ID. Write the combined, cleaned, and augmented person-year table to disk.

    :param in_directory: string, directory where the data files lives
    :param out_path: path where we want the person-period table(s) to live
    :param std_log_path: path where we want the logs from the standardisation to live
    :param pids_log_path: path where we want the logs from the unique-person-ID-giver to live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    ppts = {'year': [[], '_year.csv'], 'month': [[], '_month.csv']}

    # load csv's into tables, per time granularity
    for subdir, dirs, files in os.walk(in_directory):
        for f in files:
            file_path = subdir + os.sep + f
            period = 'month' if 'month' in file_path else 'year'
            table_as_list = pd.read_csv(file_path).values.tolist()
            ppts[period][0] = table_as_list

    # initialise the dictionary in which we keep track of changes
    change_dict = {'overview': []}

    # if there are month-level data, sample one month from the person-month data to get year-level data,
    # then combine the sample with the original year data
    # NB: the sampler drops the month column -- this is necessary for row deduplication to work properly
    if ppts['month'][0]:
        sm = sample.get_sampling_month(profession)
        year_sampled_from_months = sample.person_years(ppts['month'][0], sm, change_dict)
        ppts['year'][0].extend(year_sampled_from_months)

    # run name standardiser on the combined table
    year_range, year = 30, True
    ppts['year'][0] = standardise.clean(ppts['year'][0], change_dict, year_range, year, profession)
    standardise.make_log_file(profession, change_dict, std_log_path)

    # add gender and unit info
    ppts['year'][0] = add_rowid_gender(ppts['year'][0])

    if profession == 'judges' or profession == 'prosecutors':
        ppts['year'][0] = add_workplace_profile(ppts['year'][0], profession)

    # remove overlaps (i.e. when two people are in the same place at once), interpolate years (when they're missing
    # for spurious reasons) and add unique IDs
    ppts['year'][0] = pids.pids(ppts['year'][0], profession, pids_log_path)

    # write the preprocessed table to disk
    with open(out_path, 'w') as out_file:
        writer = csv.writer(out_file)
        [writer.writerow(row) for row in ppts['year'][0]]


def add_rowid_gender(person_period_table):
    """
    Add columns for row ID, gender and workplace profile to the person-period table.
    :param person_period_table: a person-period table, as a list of lists
    :return: a person-period table (as list of lists) with new columns
    """

    # load gender dictionary
    gender_dict = gender.get_gender_dict()

    # initialise the person-period table with columns for row IDs and gender
    with_new_cols = []

    # add columns for person gender and unit profile
    for idx, row in enumerate(person_period_table):
        gend = gender.get_gender(row[1], row, gender_dict)
        new_row = [idx] + row[:2] + [gend] + row[2:]
        with_new_cols.append(new_row)

    return with_new_cols


def add_workplace_profile(person_period_table, profession):
    """
    For judges and prosecutors we need to add a code for where their workplace (i.e. court or parquet) falls in
    the larger judicial hierarchy -- e.g. if you're at a local court, what appellate region do you fall in?
    :param person_period_table: a person-period table, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a person-period table (as list of lists) with columns for the workplace profile
    """
    # load dictionary of workplace codes
    workplace_codes_dict = workplace.get_unit_codes(profession)

    # initialise the person-period table with workplace profiles
    ppt_with_wp = []

    # add the workplace profile and level to each person-period
    for row in person_period_table:
        ppt_with_wp.append(row + workplace.get_workplace_profile(row[2], workplace_codes_dict))  # workplace = row[2]

    return ppt_with_wp
