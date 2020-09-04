"""
Functions for creating descriptive tables and graphs.
"""

import csv
from describe import totals_in_out, inheritance
from describe.mobility import geographic, hierarchical
from helpers import helpers


def describe(pop_in_file_path, sampling_scheme, out_dir_tot, out_dir_in_out, out_dir_mob, out_dir_inher,
             profession, start_year, end_year, unit_type=None):
    """
    Generate basic descriptives , and write them to disk.

    :param pop_in_file_path: path to the population-level data file
    :param sampling_scheme: str, what kind of sample we want from the population-level base data
    :param out_dir_tot: string, directory where the descriptive files on total counts will live
    :param out_dir_mob: string, directory where the descriptive files on mobility will live
    :param out_dir_inher: string, directory where the descriptive files on inheritance will live
    :param out_dir_in_out: string, directory where the descriptive files on entries and exits will live
    :param start_year: first year we're considering
    :param end_year: last year we're considering
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: None or list; if list, each entry is, type of unit we want table deaggreagted by,
                      e.g. one table where rows are metrics for each appellate court region,
                           and another where rows are metrics for each hierarchical level of the judicial system
    :return: None
    """

    table = helpers.get_sample(pop_in_file_path, sampling_scheme, profession)

    # make table of total counts per year
    year_counts_table(table, start_year, end_year, profession, out_dir_tot)

    # make tables for entry and exit cohorts, per year per gender
    entry_exit_gender(table, start_year, end_year, profession, out_dir_in_out, entry=True)
    entry_exit_gender(table, start_year, end_year, profession, out_dir_in_out, entry=False)

    # for prosecutors and judges only
    if profession == 'prosecutors' or profession == 'judges':

        # make tables of total counts per year, per level in judicial hierarchy
        year_counts_table(table, start_year, end_year, profession, out_dir_tot, unit_type='nivel')

        # make tables of total counts per year, per appellate region
        year_counts_table(table, start_year, end_year, profession, out_dir_tot, unit_type='ca cod')

        # make tables for entry and exit cohorts, per year, per gender, per level in judicial hierarchy
        entry_exit_gender(table, start_year, end_year, profession, out_dir_in_out, entry=False, unit_type='nivel')
        entry_exit_gender(table, start_year, end_year, profession, out_dir_in_out, entry=True, unit_type='nivel')

        # make table for mobility between appellate court regions
        geographic.inter_unit_mobility_table(table, out_dir_mob, profession, 'ca cod')

        # make table for hierarchical mobility and for career climbers
        hierarchical.hierarchical_mobility_table(table, out_dir_mob, profession)
        hierarchical.career_climbers_table(table, out_dir_mob, profession, use_cohorts=[2006, 2007, 2008, 2009],
                                           first_x_years=10)

        for u_t in unit_type:
            # make tables for entry and exit cohorts, per year per unit type
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_dir_in_out, entry=True)
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_dir_in_out, entry=False)

    # make tables for professional inheritance, for notaries and executori only
    # different professions have different sizes and structures, so different name rank and year window parameters
    if profession in {"notaries", "executori"}:
        prof_name_ranks = {'executori': (2, 5, 6, 0), 'notaries': (3, 7, 14, 15, 0)}
        prof_year_windows = {'executori': 1000, 'notaries': 1000}

        for num_top_names in prof_name_ranks[profession]:
            # one run with, one run without robustness check
            inheritance.prof_inherit_table(out_dir_inher, table, profession, year_window=prof_year_windows[profession],
                                           num_top_names=num_top_names, multi_name_robustness=False)
            inheritance.prof_inherit_table(out_dir_inher, table, profession, year_window=prof_year_windows[profession],
                                           num_top_names=num_top_names, multi_name_robustness=True)


def year_counts_table(person_year_table, start_year, end_year, profession, out_dir, unit_type=None):
    """
    Makes a table of yearly population counts, and optionally breaks down total counts by unit_type.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param out_dir: directory where the table will live
    :param unit_type: None, or if provided, a string indicating the type of unit (e.g. appellate court region)
    :return: None
    """

    if unit_type:
        out_path = out_dir + profession + '_' + unit_type + '_year_totals.csv'
        fieldnames = ["unit"] + ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        year_metrics = totals_in_out.pop_cohort_counts(person_year_table, start_year, end_year,
                                                       profession, cohorts=False, unit_type=unit_type)
    else:
        out_path = out_dir + profession + '_year_totals.csv'
        fieldnames = ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        year_metrics = totals_in_out.pop_cohort_counts(person_year_table, start_year, end_year,
                                                       profession, cohorts=False)

    # make table and write to disk
    with open(out_path, 'w') as o_file:
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        if unit_type:
            # iterate over units
            for unit, years in year_metrics.items():
                if unit != 'grand_total':
                    # iterate over years:
                    for year, metrics in years.items():
                        if start_year <= int(year) <= end_year:  # stay within bounds
                            writer.writerow({"unit": unit, "year": year, "female": metrics['f'], "male": metrics["m"],
                                             "don't know": metrics['dk'], "total count": metrics['total_size'],
                                             "percent female": metrics['percent_female']})

        else:  # no units, just straight years
            for year, metrics in year_metrics['grand_total'].items():
                writer.writerow({"year": year, "female": metrics['f'], "male": metrics["m"],
                                 "don't know": metrics['dk'], "total count": metrics['total_size'],
                                 "percent female": metrics['percent_female']})


def entry_exit_gender(person_year_table, start_year, end_year, profession, out_dir, entry=True, unit_type=None):
    """
    Make a table that shows the count and percentage of entry and exit cohorts for each gender, and for each
    unit if applicable.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param out_dir: directory where the table will live
    :param unit_type: None, or if provided, a string indicating the type of unit (e.g. appellate court region)
    :param entry: bool, True if entry cohorts, False if exit cohorts (i.e. everyone who left in year X)
    :return: None
    """

    type_of_cohort = 'entry' if entry else 'departure'

    if unit_type:
        out_path = out_dir + profession + '_' + unit_type + '_' + type_of_cohort + '_cohorts_gender.csv'
        fieldnames = ["unit"] + ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        cohorts = totals_in_out.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                  cohorts=True, unit_type=unit_type, entry=entry)
    else:
        out_path = out_dir + profession + '_' + type_of_cohort + '_cohorts_gender.csv'
        fieldnames = ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        cohorts = totals_in_out.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                  cohorts=True, unit_type=None, entry=entry)

    # write table to disc
    with open(out_path, 'w') as o_file:
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        # if we're given unit types
        if unit_type:
            # iterate over units
            for unit, years in cohorts.items():
                if unit != 'grand_total':
                    # iterate over the years:
                    for year, metrics in years.items():
                        if start_year <= int(year) <= end_year - 1:  # stay within bounds
                            writer.writerow({"unit": unit, "year": year, "female": metrics['f'], "male": metrics["m"],
                                             "don't know": metrics['dk'], "total count": metrics['total_size'],
                                             "percent female": metrics['percent_female']})

        else:  # no units, just straight years
            for year, metrics in cohorts['grand_total'].items():
                writer.writerow(
                    {"year": year, "female": metrics['f'], "male": metrics["m"], "don't know": metrics['dk'],
                     "total count": metrics['total_size'], "percent female": metrics['percent_female']})


def entry_exit_unit_table(person_year_table, start_year, end_year, profession, unit_type, out_dir, entry=True):
    """
    Make two csv tables, where the rows are units and the columns are years. For one table the cells are
    the total number of departures from that unit, for that year; for the other table, the cells are the percent
    of departures, relative to all people in that unit, in that year.

    NB: units can be geographic regions (e.g. notary "camera") or hierarchical level (e.g. tribunal level for judges)

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table (e.g. "camera")
    :param entry: bool, True if entry cohorts, False if exit cohorts (i.e. everyone who left in year X)
    :param out_dir: directory where the table will live
    :return: None
    """
    # if we look at entry cohorts avoid left censor and include right censor (which function ignores by default)
    if entry:
        start_year += 1
        end_year += 1

    # get data on cohorts by year and unit
    cohorts_per_unit = totals_in_out.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                       cohorts=True, unit_type=unit_type, entry=entry)
    # write the table to disk
    type_of_cohort = 'entry' if entry else 'departure'
    out_path = out_dir + profession + '_' + type_of_cohort + '_' + unit_type + '_rates.csv'
    with open(out_path, 'w') as o_file:
        fieldnames = ['unit'] + list(range(start_year, end_year))  # omit last year: all leave in right censor year
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        # iterate over units
        for unit, years in cohorts_per_unit.items():
            percent_row = {'unit': unit}
            count_row = {'unit': ''}
            # iterate over the years:
            for year, measures in years.items():
                if start_year <= int(year) <= end_year - 1:  # stay within bounds
                    percent_row.update({year: measures['chrt_prcnt_of_pop']})
                    count_row.update({year: '(' + str(measures['total_size']) + ')'})
            # display the count row under the percent row
            writer.writerow(percent_row)
            writer.writerow(count_row)
