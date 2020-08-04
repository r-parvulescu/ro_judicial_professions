"""
Functions for sampling from a person-month table to generate a person-year table.
"""

import operator
import itertools
import statistics
import pandas as pd
from helpers import helpers


def person_years(person_month_table, month, change_dict):
    """
    Turn a person-month table into a person-year table by sampling from the specified month, and if that month is
    missing for the person, from the next available month. E.g. if we want to sample April, but that month is missing
    for person X, try sampling May or March, and if those are missing try June or February, etc. until you hit a month.

    While using whatever month data is available makes it so that there are not always twelve months between
    observations, this approach guards against people looking like they've retired, when really they were simply not
    recorded for the sampling month.

    NB: there are people in the employment rolls who where in two places at once; this is a deduplication issue that
    is explicitly dealt with later. This function groups such people together, so to avoid deduplicating now, if
    a person-year contains multiple observations for the same month, use all of them.

    :param person_month_table: table of person-months, as a list of lists
    :param month: int: 1-12
    :param change_dict: a dict where we record before (key) and after (value) state changes, and an overview of changes
    :return a person-year level table, with only one month observation, per person, per year
    """

    # sort table by surname, given name, year, and month
    person_month_table.sort(key=operator.itemgetter(0, 1, 3, 4))

    # initiate the list that will hold the year-level observations for each person
    one_obs_per_year = []

    # initialise of list of months that we actually sampled, to get some sampling diagnostics
    sampled_months = []

    # isolate all the person-years by grouping together rows that share a surname, given name, and year
    # each person-year is itself a list, and the elements are the person months
    for key, [*py] in itertools.groupby(person_month_table, key=operator.itemgetter(0, 1, 3)):

        # select the person-month that matches the desired month
        # if that month does not exit, use the observation from the nearest month

        # recall, we don't want to deduplicate here: if a person-year has multiple observations
        # for one month, use all of them

        # initialise a dict with 'key = month' and 'value = person-month observations'
        obs_by_month = {int(person_month[4]): [] for person_month in py}
        # then fill the values
        for person_month in py:
            obs_by_month[person_month[4]].append(person_month)  # month = row[4]

        # if there is an observation for that month, use it
        if month in obs_by_month:
            one_obs_per_year.extend(obs_by_month[month])
            sampled_months.append(month)

        # else, look for nearest month and use its observation; if two months are equally close, the method below
        # always picks the lower month; this decision is arbitrary, it only matters that it be consistent
        else:
            available_months = list(obs_by_month.keys())
            closest_month = min([(i, abs(month - i)) for i in available_months], key=operator.itemgetter(1))[0]
            one_obs_per_year.extend(obs_by_month[closest_month])
            sampled_months.append(closest_month)

    # remove the month column
    one_obs_per_year = [row[:-1] for row in one_obs_per_year]

    print('AVERAGE AND STDEV OF MONTH SAMPLED: %s, %s' % (round(statistics.mean(sampled_months), 2),
                                                          round(statistics.stdev(sampled_months), 2)))

    change_dict['overview'].append(['AVERAGE AND STDEV OF MONTH SAMPLED', round(statistics.mean(sampled_months), 2),
                                    round(statistics.stdev(sampled_months), 2)])

    return one_obs_per_year


def get_sampling_month(profession):
    """
    FOR DATA AS OF MAY 13 2020:

    - for judges 1988-2020, the output of prep.sample.month_availability indicates that April is the best month
    to anchor sampling.

    - for prosecutors 1988-2019, the output of prep.sample.month_availability indicates that September is the best month
    to anchor sampling.

    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: int, the sample month
    """

    sampling_months = {'judges': 4, 'prosecutors': 9, 'notaries': 0, 'executori': 0}
    return sampling_months[profession]


def month_availability(person_month_table, profession):
    """
    The function that samples one month to reduce a person-month table to a person-year table assumes tries to pick
    the specified month (e.g. '04', April), and failing that looks for the nearest available month (e.g. March or May).
    When picking which month we'd like to sample (and, failing that, start our search from) it's helpful to know
    which months have more observations in the data set: obviously, we'd like to sample from the month with the most
    observations.

    The availability of months varies by Tribunal jurisdiction (until 2005 the Tribunals were the ones that,
    by law, kept employment records for all courts in their area -- so if data is missing here, it will be missing
    at tribunal level) and year (data are more complete in some years than others). So we have three axes of variation:
    month, year, and tribunal jurisdiction. This function makes a csv with two tables:

        (a) tribunal (row) by month (column),
        (b) year (row) by month (column).

    The number in each cell represents the number of observations for that combination: for instance, 155 in cell
    Tribunal X -- April means that, for the month of April (across all years) we see 155 observations for Tribunal X.
    The ideal month to sample (or begin our search from) is one that has a high column sum and low column variance,
    i.e. consistently many observations across tribunal and year.

    :param person_month_table: table of person-months, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    df = pd.DataFrame(person_month_table)
    df.set_axis(['nume', 'prenume', 'instanţă/parchet', 'an', 'lună'], axis=1, inplace=True)

    # make year (row) month (column) table
    df['lună'] = df['lună'].astype(str)
    # pivot table, count values in 'name'
    year_months = pd.pivot_table(df, index=['an'], columns=["lună"], values=['nume'], aggfunc=len)
    year_months.loc['sum'] = year_months.sum()
    year_months.loc['variance'] = year_months.std()

    # TODO make tribunal (row) by month (column)

    out_file_name = 'prep/sample/' + profession + '_month_availability.csv'
    year_months.to_csv(out_file_name)


def mo_yr_sample(person_month_table, profession, months, years):
    """
    Sample only the person-months from the specified months in the specified years. For the example values below,
    we would sample person-years from April, July, and December of 2006, 2007, and 2008.

    NB: works only on the "collected" table

    :param person_month_table: table of person-months, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param months: iterable of ints for months (1-12), e.g. [4 ,7, 12]
    :param years: iterable of ints for years, e.g. [2006, 2007, 2008]
    :return: a person-month table with observations only from the specified months and years
    """
    months, years = set(months), set(years)
    mon_idx = helpers.get_header(profession, 'collect').index('lună')
    year_idx = helpers.get_header(profession, 'collect').index('an')

    # initialise sampled person-month table
    sampled_pm_table = []

    for pm in person_month_table:
        if int(pm[mon_idx]) in months and int(pm[year_idx]) in years:
            sampled_pm_table.append(pm)
    print(len(sampled_pm_table))
    return sampled_pm_table


def continuity_sample(person_year_table, time_period, profession):
    """
    There are several points in time in which my datasets become increasingly restricted, e.g. before 2005 I only have
    data on half of the parquets, but after 2005 I have data on all the parquets.

    This functions samples data based on which institutions/units have CONTINUE across a pre-defined time period;
    period bounds are included. For example, if my whole data i 1990-2010, but my time-period is 1995-2007, keep only
    those units for which we have data for both 1995 and 2007 (on the assumption that we also have data for all the
    years in between).

    The point is to make across-time comparison meaningful, since we're just studying those units that are there for
    the whole period, and not muddling things up by also trying to handle units that (dis)appear partway through.

    NB: units may appear and disappear over the time-period because
        a) the units were disbanded, e.g. Scorniceşti court
        b) the units were founded, e.g. DIICOT
        c) I do not have data on those units for the whole period

    This function only returns data on units that were there throughout the entire period for which we have data.
    It does not distinguish between units with incomplete data due to substantive reasons (i.e. they were founded
    part-way through) as opposed to research reasons (i.e. we couldn't obtain full-period data for that unit).

    NB: as of 03.08.2020 this function is only meant to work with judges and prosecutors; have complete data for the
    entire observation periods for the other professions

    :param person_year_table: a table, as a list of lists, where year row is a person-period (e.g. a person-month)
    :param time_period: tuple of ints, boundary years of the time period, e.g. (2005, 2015)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a person-year table with continuity of allowable workplaces
    """

    year_idx = helpers.get_header(profession, 'preprocess').index('an')
    unit_name_idx = helpers.get_header(profession, 'preprocess').index('instituţie')

    # make two sets: one of unit names that appear in the first year of the period, another set of unit names appearing
    # in the last year of the period
    first_year_unit_names = {py[unit_name_idx] for py in person_year_table
                             if int(py[year_idx]) == time_period[0]}
    last_year_unit_names = {py[unit_name_idx] for py in person_year_table
                            if int(py[year_idx]) == time_period[1]}

    # continuity units are those with data for both the first and the last years of the specified time period
    continuity_unit_names = first_year_unit_names & last_year_unit_names

    # only keep person-years whose year value fall within the specified time period
    period_years = set([y for y in range(time_period[0], time_period[1] + 1)])
    period_table = [py for py in person_year_table if int(py[year_idx]) in period_years]

    # and which are associated with units which were there for the whole period
    period_unit_continuity_table = [py for py in period_table if py[unit_name_idx] in continuity_unit_names]

    return period_unit_continuity_table
