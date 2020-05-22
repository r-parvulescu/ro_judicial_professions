"""
Functions for calculating counts of different mobility events, across different units.
"""

from operator import itemgetter
import itertools
import pandas as pd


# COUNTS OF ENTITIES #

def people_per_year(person_year_table, start_year, end_year):
    """returns a list of (year, count of unique people) tuples"""
    ids_per_year = {year: set() for year in range(start_year, end_year + 1)}
    [ids_per_year[int(py[6])].add(py[0]) for py in person_year_table]
    return sorted(list({k: len(val) for k, val in ids_per_year.items()}.items()))


def people_per_level_per_year(person_year_table, start_year, end_year, ratios=False):
    """
    returns a list of (year : (count J, count TB, count CA, count ICCJ)) tuples
    or if ratios=False of yearly ratios between the sizes of adjacent levels"""
    ids_per_year_per_level = {year: {1: 0, 2: 0, 3: 0, 4: 0} for year in range(start_year, end_year)}
    for py in person_year_table:
        ids_per_year_per_level[int(py[6])][int(py[-1])] += 1
    if ratios:  # get ratio of totals between level X and the level immediately below it
        ratios_per_year = {}
        for k, v in ids_per_year_per_level.items():
            cnts = sorted(list(v.items()), key=itemgetter(1))
            sorted_ratios = (round(cnts[0][1] / cnts[1][1], 2), round(cnts[1][1] / cnts[2][1], 2),
                             round(cnts[2][1] / cnts[3][1], 2))
            ratios_per_year[k] = sorted_ratios
        return sorted(list(ratios_per_year.items()))
    else:
        ids_per_year_per_level = [(k, sorted(list(v.items()), key=itemgetter(1)))
                                  for k, v in ids_per_year_per_level.items()]
        return sorted(list(ids_per_year_per_level))


# MEASURES OF MOBILITY/CHANGE #

def total_mobility(person_year_table, start_year, end_year):
    """return a dict of year : total mobility"""
    mobility_per_year = {year: 0 for year in range(start_year, end_year + 1)}
    for py in person_year_table:
        if py[5] != '0':
            mobility_per_year[int(py[6])] += 1
    return sorted(list(mobility_per_year.items()))[1:-1]


def entries(person_year_table, start_year, end_year, year_sum=False):
    """count the number of entries or exits per year (and if year_sum=False, per level)"""
    year_level_counters = year_level_dict(start_year, end_year)
    person_year_table.sort(key=itemgetter(0, 6))
    person_sequences = [g for k, [*g] in itertools.groupby(person_year_table, key=itemgetter(0))]
    for seq in person_sequences:
        if len(seq) > 1:  # ignore sequences one long, marking as entry or exit would double-count
            year_level_counters[int(seq[0][6])][int(seq[0][-1])] += 1  # first sequence element marks entry point
    return sorted_output(year_level_counters, 1, year_sum)[1:]  # first observation wrong due to censoring


def delta_attribute(person_year_table, attribute, attr_type, per_unit, metric, output_series=False):
    """
    metrics of person_years that are of mobility type per unit (e.g. per year, per level)
    :param person_year_table: person-year table as list of lists
    :param mobility_type: str:  'up', 'out', 'across', 'down', or 'NA'
    :param per_unit: list of units as strings, e.g. ['year', 'level']
    :param metric: str, "percent" or "count"
    """
    print(person_year_table[0])
    columns = ["cod rând", "cod persoană", "nume", "prenume", "sex", "instituţie", "an",
               "ca cod", "trib cod", "jud cod", 'nivel', 'None']
    df = pd.DataFrame(person_year_table)
    print(df[:5])
    df = pd.DataFrame(person_year_table, columns=columns)
    df = pd.get_dummies(df, columns=[attribute])
    attr_dum_col = attribute + '_' + attr_type
    measure = None   # errors out if no metric provided
    if metric == "percent":
        measure = df.groupby(per_unit)[attr_dum_col].mean().round(decimals=4)
    if metric == "count":
        measure = df.groupby(per_unit)[attr_dum_col].sum()
    if output_series:
        return measure
    measure = measure.to_dict().items()
    if len(per_unit) < 2:  # if just one unit, sort output ascending
        return sorted(list(measure))
    else:  # assumes first key element is always year
        output = {}
        for key, value in measure:
            if key[0] not in output:
                output[key[0]] = []
            output[key[0]].append((*key[1:], value))
        return sorted(list(output.items()))


def mobility_per_year_per_unit(person_year_table, unit_list, start_year, end_year,
                               unit_type, mobility_type, year_sum=False):
    """
    counts the number of mobility events per year, per unit
    NB: units are either courts of appeals, tribunals, judecătorii.
    NB: mobility types: 'up', 'across', 'down', 'out'
    """

    unit_types_idx = {'1': -2, '2': -3, '3': -4}
    year_unit_counters = year_unit_dict(start_year, end_year + 1, unit_list)
    for py in person_year_table:
        if py[5] == mobility_type:
            idx = unit_types_idx[unit_type]
            if py[-1] == unit_type:
                year_unit_counters[int(py[6])][py[idx]] += 1
    return sorted_output(year_unit_counters, 0, year_sum)


def mob_cohorts(person_year_table, years_after, start_year, end_year, percent=False):
    """
    counts of mobility events per cohort, up to X years after they enter
    if percent=True return percent of cohort person-years accounted for by each mobility type
    """
    cohort_dict = {str(year): {'up': 0, 'down': 0, 'across': 0, 'out': 0, 'NA': 0, '0': 0}
                   for year in range(start_year, end_year + 1)}
    # groupby person  ID
    person_year_table.sort(key=itemgetter(0, 6))
    person_sequences = [g for k, [*g] in itertools.groupby(person_year_table, key=itemgetter(0))]
    for seq in person_sequences:
        entry_year = seq[0][6]
        yr_range = min(len(seq), years_after)
        for yr in range(yr_range):
            cohort_dict[entry_year][seq[yr][5]] += 1
    if percent:
        for cohort, mob in cohort_dict.items():
            sum_mob = sum(mob.values())
            percent_mob = {k: round(weird_division(v, sum_mob), 3) for k, v in mob.items()}
            cohort_dict[cohort] = percent_mob
    return sorted_output(cohort_dict, 0, year_sum=False)[:-years_after + 1]


def sorted_output(year_dict, sort_key, year_sum):
    """returns year_dict as sorted list, by year by categories, or by year summed across categories"""
    if year_sum:  # get sum of mobility across levels
        year_dict = [(k, sum(v.values())) for k, v in year_dict.items()]
    else:
        year_dict = [(k, sorted(list(v.items()), key=itemgetter(sort_key)))
                     for k, v in year_dict.items()]
    return sorted(list(year_dict))


def year_level_dict(l_yr, u_yr):
    """return a dict of dicts, of years holding levels, from lower year to upper year"""
    return {year: {1: 0, 2: 0, 3: 0, 4: 0} for year in range(l_yr, u_yr)}


def year_unit_dict(l_yr, u_yr, unit_list):
    """return a dict of dicts, of years holding units (e.g. courts of appeals), from lower year to upper year"""
    return {year: {unit: 0 for unit in unit_list} for year in range(l_yr, u_yr)}


def weird_division(n, d):
    # from https://stackoverflow.com/a/27317595/12973664
    return n / d if d else 0