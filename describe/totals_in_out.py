"""
Functions for calculating counts of different mobility events, across different units.
"""

import itertools
import natsort
import csv
from copy import deepcopy
from operator import itemgetter
from helpers import helpers
from preprocess import sample


# FUNCTIONS FOR COUNTS FOR WHOLE SAMPLE AS WELL AS ENTRY AND EXIT COHORTS #


def pop_cohort_counts(person_year_table, start_year, end_year, profession, cohorts=True, unit_type=None, entry=True):
    """
    For each year in the range from start_year to end_year, return a dict of counts of women, men, don't knows,
    cohort size, and percent women for that cohort.

    If units are provided (e.g. geographic areas) it calculates the metrics per each unit, so e.g. cohort size per
    year, for each geographic area.

    NB: there can be entry cohorts (those that joined the profession in year X) and exit cohorts (those that left
    the profession in year Y).

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param cohorts: bool, True if we want counts for entry and exit cohorts (e.g. all who entered the profession in 
                          2012), False if we want counts for whole population (e.g. all professionals in 2012)
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :param entry: bool, True if we're getting data for entry cohorts, False if for exit cohorts
    :return: a dict of years, where each value is a dict with gender metrics
    """

    pop_counts = {'grand_total': metrics_dict(start_year, end_year)}
    units = None

    # if we have units, initialise a dict of years for each unit
    if unit_type:
        unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)
        units = {person_year[unit_col_idx] for person_year in person_year_table}
        pop_counts.update({unit: metrics_dict(start_year, end_year) for unit in natsort.natsorted(list(units))})

    # make an identical dict for cohorts
    cohort_counts = deepcopy(pop_counts)

    # get total counts
    for person_year in person_year_table:
        update_size_gender(pop_counts, person_year, start_year, end_year, profession, units, unit_type=unit_type)
    percent_female(pop_counts, units, unit_type=unit_type)

    # then get cohort counts

    # sort table by people and year, then group person-years by person
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    person_year_table.sort(key=itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]
    for person in people:
        # if describing entry cohorts we want the first person-year, else the last person-year (i.e. exit cohorts)
        edge_person_year = person[0] if entry else person[-1]
        update_size_gender(cohort_counts, edge_person_year, start_year, end_year, profession,
                           units, unit_type=unit_type)
    percent_female(cohort_counts, units, unit_type=unit_type)
    update_cohort_of_population(cohort_counts, pop_counts, entry=entry, units=units)

    return cohort_counts if cohorts else pop_counts


def metrics_dict(start_year, end_year):
    """
    Make an empty dict where keys are years and values are dicts of metrics, most related to gender.
    :param start_year: int, year we start looking
    :param end_year: int, year we stop looking at
    :return: dict
    """
    m_dict = {year: {'f': 0, 'm': 0, 'dk': 0, 'total_size': 0, 'chrt_prcnt_of_pop': 0, 'percent_female': 0}
              for year in range(start_year, end_year + 1)}
    return m_dict


def update_size_gender(count_dict, row, start_year, end_year, profession, units, unit_type=None):
    """
    Counts the number of people per year; if unit is given, gives the count of person per year, per unit

    :param count_dict: a dictionary of counts -- for format, see function metrics_dict
    :param row: a person-year as a list; first or last row, depending on whether we want entry or exit cohorts
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param units: a set of unit categories, each a string
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :return: None
    """
    # if describing entry cohorts we want the first person-year, else the last person-year (i.e. exit cohorts)
    dict_row = helpers.row_to_dict(row, profession, 'preprocess')
    gendr = dict_row['sex']
    year = int(dict_row['an'])
    unit = dict_row[unit_type] if units else None

    # stay within bounds
    if start_year <= year <= end_year:

        # increment cohort sizes and cohort gender counters
        count_dict['grand_total'][year]['total_size'] += 1
        count_dict['grand_total'][year][gendr] += 1
        if unit_type:
            count_dict[unit][year]['total_size'] += 1
            count_dict[unit][year][gendr] += 1


def percent_female(count_dict, units, unit_type=None):
    """
    Update the percent_female value in the count_dict

    :param count_dict: a dictionary of counts -- for format, see function metrics_dict
    :param units: a set of unit categories, each a string
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :return: None
    """
    # now get percent female per cohort, and per unit if applicable
    for year in count_dict['grand_total']:
        if count_dict['grand_total'][year]['total_size'] != 0:
            count_dict['grand_total'][year]['percent_female'] = helpers.percent(
                count_dict['grand_total'][year]['f'], count_dict['grand_total'][year]['total_size'])
        if unit_type:
            for u in units:
                if count_dict[u][year]['total_size'] != 0:
                    count_dict[u][year]['percent_female'] = helpers.percent(
                        count_dict[u][year]['f'], count_dict[u][year]['total_size'])


def update_cohort_of_population(cohorts_dict, population_dict, entry=True, units=None):
    """
    Updates the value that shows how big a yearly cohort is relative to all the people in that year.

    NB: for entry cohorts, we compare cohort sizes to all people in the PREVIOUS year. For exit cohorts, we
        compare cohort sizes to all people in the CURRENT year.

    :param cohorts_dict: a dictionary of cohorts, where each key is a year and values are metrics for that cohort
    :param population_dict: a dictionary for the whole population, where each key is a year, and values are metrics
                            for all population members for that year
    :param entry: bool, True if we're getting data for entry cohorts, False if for exit cohorts
    :param units: a set of unique units of a certain type, e.g. towns
    :return: None
    """
    for year in cohorts_dict['grand_total']:

        # for entry cohorts, compare with preceding year, unless it's the first year
        if entry and year - 1 in cohorts_dict:
            yearly_pop = population_dict['grand_total'][year - 1]['total_size']
        else:
            yearly_pop = population_dict['grand_total'][year]['total_size']

        if cohorts_dict['grand_total'][year]['total_size'] != 0:
            cohorts_dict['grand_total'][year]['chrt_prcnt_of_pop'] = helpers.percent(
                cohorts_dict['grand_total'][year]['total_size'], yearly_pop)

        if units:
            for u in units:
                # for entry cohorts, compare with preceding year, unless it's the first year
                if entry and year - 1 in cohorts_dict:
                    yearly_unit_pop = population_dict[u][year - 1]['total_size']
                else:
                    yearly_unit_pop = population_dict[u][year]['total_size']

                if cohorts_dict[u][year]['total_size'] != 0:
                    cohorts_dict[u][year]['chrt_prcnt_of_pop'] = helpers.percent(cohorts_dict[u][year]['total_size'],
                                                                                 yearly_unit_pop)


# MISCELLANEOUS FUNCTIOS FOR RETRIEVING CERTAIN DISTRIBUTIONS OF INTEREST

def make_percent_pre_1990_table(person_year_table, profession, out_dir, out_dir_area_samp=None, area_sample=False):
    """
    Make a table that shows for for every given year the percentage of people in the system who entered the system prior
    to 1990. This is meant to show rate of decrease of socialist-era judges. Percentages are disaggregated by judicial
    level, and dump them in a csv table.

    NB: when running this metric on the sample, this function assumes that entries and departures of pre-1990 people
        into the sample balance out, so that the sampling itself doesn't influence the before-to-after 1990 ratio.

    :param person_year_table: a table of person-years, as a list of lists; assumes no header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param area_sample: bool, True if you want to exclusively use data from Alba, Iași, Craiova, and Ploiești
                        appeals areas/regions; False by default
    :param out_dir: str, directory where we want the non-area-sampled results table to live
    :param out_dir_area_samp: str, if given it's where we want the sample-area results table to live
    :return None
    """
    if area_sample:
        appellate_areas_to_sample = ["CA1", "CA7", "CA9", "CA12"]  # I hard code this in since it changes very rarely
        person_year_table = sample.appellate_area_sample(person_year_table, profession, appellate_areas_to_sample)
        out_dir = out_dir_area_samp

    # get handy column indexes
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort table by person and year, then group table by persons
    person_year_table = sorted(person_year_table, key=itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # get the span of years
    years = sorted(list({int(py[yr_col_idx]) for py in person_year_table}))

    # initialise the nested dict holding the data, in three layers: hierarchical levels, list of counts
    b4_1990_year_dict = {i: {yr: {"before 1990": 0, "total count": 0} for yr in years} for i in range(1, 5)}

    for person in people:
        first_career_year = int(person[0][yr_col_idx])
        for pers_yr in person:
            current_year = int(pers_yr[yr_col_idx])
            current_level = int(pers_yr[lvl_col_idx])
            b4_1990_year_dict[current_level][current_year]["total count"] += 1
            if first_career_year <= 1990:
                b4_1990_year_dict[current_level][current_year]["before 1990"] += 1

    # calculate percent from before 1990, only for 1990 and after (before 1990s it's always 100%)
    percs_lvl = {lvl: [] for lvl in b4_1990_year_dict}
    for lvl in b4_1990_year_dict:
        for yr in years:
            if yr >= 1990:
                percs_lvl[lvl].append(helpers.percent(b4_1990_year_dict[lvl][yr]["before 1990"],
                                                      b4_1990_year_dict[lvl][yr]["total count"]))

    # write each level timeseries to disk
    with open(out_dir + "percent_pre_1990.csv", "w") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(["Hierarchical Level"] + [yr for yr in years if yr >= 1990])
        for lvl in b4_1990_year_dict:
            writer.writerow([lvl] + percs_lvl[lvl])
