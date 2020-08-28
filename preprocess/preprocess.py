"""
Functions for augmenting  person-period table with extra columns.
infile headers: nume, prenume, instanță/parchet, an, lună
"""

import os
import csv
import operator
import pandas as pd
from preprocess import standardise
from preprocess import sample
from preprocess import pids
from preprocess.workplace import workplace
from preprocess.gender import gender
from preprocess.inheritance import inheritance
from helpers import helpers


def preprocess(in_directory, prep_table_out_path, std_log_path, pids_log_path, profession):
    """
    Standardise data from person-period tables at different levels of time granularity (year and month levels),
    sample person-months to get person-years, combine this sample with the original year-level data, clean the
    combined table, assign every person-year a row ID gender, institution profile, and unique (row) ID, and finally
     assign each row a person-level unique ID. Write the combined, cleaned, and augmented person-year table to disk.

    :param in_directory: string, directory where the "collected" data files live
    :param prep_table_out_path: path where we want the preprocessed person-period table(s) to live
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
    # NB: deduplicates because some person-years in both year- and month-level (sampled) data
    if ppts['month'][0]:
        sm = sample.get_sampling_month(profession)
        year_sampled_from_months = sample.person_years(ppts['month'][0], sm, change_dict)
        ppts['year'][0].extend(year_sampled_from_months)
        # deduplicate; limit all rows to first four entries, for unknown reason sometimes nan's appear in fifth position
        ppts['year'][0] = helpers.deduplicate_list_of_lists([row[:4] for row in ppts['year'][0]])

    # reshape the notaries table from person to person-years
    # standardisation, deduplication, assigning person-ids, can all be ignored for notaries; just add gender info
    if profession == 'notaries':
        # reshape
        ppts['year'][0] = reshape_to_person_years(ppts['year'][0], profession)
        # add gender column; py = person-year; py[3] == given names
        # load gender dict
        gender_dict = gender.get_gender_dict()
        ppts['year'][0] = [py[:4] + [gender.get_gender(py[3], py, gender_dict)] + py[4:] for py in ppts['year'][0]]

    else:  # all other professions already come in person-year format

        # run name standardiser on the combined table
        year_range, year = 30, True
        ppts['year'][0] = standardise.clean(ppts['year'][0], change_dict, year_range, year, profession)
        standardise.make_log_file(profession, change_dict, std_log_path)

        # add gender and row id
        ppts['year'][0] = add_rowid_gender(ppts['year'][0])

        # if we're dealing with judges or prosecutors, add workplace codes
        if profession == 'judges' or profession == 'prosecutors':
            ppts['year'][0] = add_workplace_profile(ppts['year'][0], profession)

        # remove overlaps (i.e. when two people are in the same place at once), interpolate years (when they're missing
        # for spurious reasons) and add unique IDs
        ppts['year'][0] = pids.pids(ppts['year'][0], profession, pids_log_path)

    # add column indicating whether a person inherited their profession; for now only for executori and notaries
    if profession == 'notaries' or profession == 'executori':
        ppts['year'][0] = add_inheritance_status(ppts['year'][0], profession, year_window=1000)

    # write the preprocessed table to disk
    write_preprocessed_to_disk(ppts['year'][0], prep_table_out_path, profession)


def write_preprocessed_to_disk(person_year_table, out_path, profession):
    """
    Write a table of preprocessed person-years to disk.

    :param person_year_table: a table of person-years, as a list of lists
    :param out_path: where to write the preprocessed table
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return:
    """
    with open(out_path, 'w') as out_file:
        writer = csv.writer(out_file)
        writer.writerow(helpers.get_header(profession, 'preprocess'))  # put in header
        [writer.writerow(row) for row in sorted(person_year_table, key=operator.itemgetter(1))]  # sort by unique ID


def add_rowid_gender(person_period_table):
    """
    Add columns for row ID, gender and workplace profile to the person-period table.
    :param person_period_table: a person-period table, as a list of lists
    :return: a person-period table (as list of lists) with new columns
    """
    # load gender dict
    gender_dict = gender.get_gender_dict()

    # initialise the person-period table with columns for row IDs and gender
    with_new_cols = []

    # assign gender and row ID for every person-year
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
    workplace_codes_dict = workplace.get_workplace_codes(profession)

    # initialise the person-period table with workplace profiles
    ppt_with_wp = []

    # add the workplace profile and level to each person-period
    for row in person_period_table:
        ppt_with_wp.append(
            row[:6] + workplace.get_workplace_profile(row[4], workplace_codes_dict))  # workplace = row[4]

    return ppt_with_wp


def add_inheritance_status(person_period_table, profession, year_window=1000):
    """
    Add column indicating whether or not an individual (i.e. at the person-ID level) inherited their profession.

    :param person_period_table: a person-period table, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param year_window: int, how many years back we look for matches, e.g. "6" means we look for matches in six years
                        prior to your joining the profession; default is "1000", i.e. look back to beginning of data
    :return: a person-period table (as list of lists) with an column for workplace profile inheritor status
    """

    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # get the set of inheritors
    inheritor_set = inheritance.profession_inheritance(person_period_table, profession, year_window=year_window)

    # initialise new person-period table with inheritance values
    ppt_with_inher = []

    # now append the inheritance value/column to each person-period
    for pers_year in person_period_table:
        ppt_with_inher.append(pers_year + [1]) if pers_year[pid_col_idx] in inheritor_set \
            else ppt_with_inher.append(pers_year + [0])

    return ppt_with_inher


def reshape_to_person_years(person_table, profession):
    """
    Takes a table of persons (with columns for entry and exit year) and reshapes it to a table of person-years.

    NB: this function assumes that no details (notably name and place of practice) change from the time when the
        person entered the profession to when they left

    NB: header for person-table is [nume, prenume, camera, localitatea, intrat, ieşit]

    :param person_table: a table of persons, NOT person-years (each person is one row)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return:
    """

    # initialise a list of person-years
    person_years = []

    # the last year before right censor
    max_year = max({int(row[4]) for row in person_table})  # row[4] == year

    # each person is a row -- so give each row/person a unique, person-level ID
    pt_with_pids = [[idx] + row for idx, row in enumerate(person_table)]

    # for each person
    for person in pt_with_pids:
        entry_year = int(person[5])  # entry year == person[5]

        # if departure year is '-88', observation was right censored; set departure year to max year
        exit_year = max_year if str(person[6]) == '-88' else int(person[6])  # exit year == person[6]

        # for each year in the range from entry year to exit year, add one person-year
        [person_years.append(person[:3] + [i] + person[3:5]) for i in range(entry_year, exit_year + 1)]

    # give every person-year row a unique ID
    py_with_row_ids = [[idx] + row for idx, row in enumerate(person_years)]

    # now re-order names so surnames and given names are (each separately) in alphabetical order;
    # this function also acts as a row deduplicator
    py_with_row_ids = standardise.name_order(py_with_row_ids, profession)

    return py_with_row_ids
