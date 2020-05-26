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


# COHORT METRICS #

def entry_cohort_sizes(person_year_table, start_year, end_year, unit=None):
    """
    Return the size of entry cohorts for each year between start_year and end_year.
    If unit is provided (e.g. hierarchical level, area), also report cohort sizes per unit (e.g. cohort size per area)

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param unit:
    :return a dict of key = year, val = [size]; if units provided, ley = year, val = [(unit 1, size), (unit 2, size)]
    """
    pass


def cohort_counts(person_year_table, start_year, end_year):
    """
    For each year in the range from start_year to end_year, return a list of
    (count of women, count of men, count of dk, cohort size, percent female), of those that joined the profession
    that year.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :return: a dict of years, where each value is a tuple with gender metrics
    """
    # make a dict, key = year, value = empty list with five slots, one for each of
    # count women, count men, count dk, total count, percent female
    cohorts = {year: [0, 0, 0, 0, 0] for year in range(start_year, end_year + 1)}

    # group by people
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(1))]  # row[1] == PID

    for person in people:
        # the first observation in a person-sequence ordered by year is the first year of their career
        start_career = person[0]
        # gender = row[4]
        gender = start_career[4]
        # year = row[6]
        cohort_year = int(start_career[6])

        if start_year <= cohort_year <= end_year:
            if gender == 'f':
                cohorts[cohort_year][0] += 1
            elif gender == 'm':
                cohorts[cohort_year][1] += 1
            else:  # gender == 'dk':
                cohorts[cohort_year][2] += 1

    # get cohort sizes
    for cohort_year in cohorts:
        total_entries = sum(cohorts[cohort_year][:3])
        cohorts[cohort_year][3] = total_entries

    # if there are no entries for a particular year (i.e. cohort size = 0) remove the year from the cohort dict
    cohorts = {year: measures for year, measures in cohorts.items() if measures[3] != 0}

    # now get percent female per cohort
    for cohort_year in cohorts:
        percent_female = int(round(cohorts[cohort_year][0] / cohorts[cohort_year][3], 2) * 100)
        cohorts[cohort_year][4] = percent_female

    return cohorts


def cohort_name_lists(person_year_table, start_year, end_year):
    """
    For each year in the range from start_year to end_year, return a list of full-names of the people that joined
    the profession in that year.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :return: a dict of years, where each value is a list of full-name tuples of the people who joined the profession
             that year
    """
    # make a dict, key = year, value = empty list
    cohorts = {year: [] for year in range(start_year, end_year + 1)}
    # group by people
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(1))]  # row[1] == PID

    # append the full name of the first year of each person to its cohort
    for person in people:
        first_year = person[0]

        if start_year <= int(first_year[6]) <= end_year:  # row[6] = year
            # row[2] = surname, row[3] = given_name
            cohorts[int(first_year[6])].append(first_year[2] + ' | ' + first_year[3])

    return cohorts


def brought_in_by_family(person_year_table, start_year, end_year):
    """
    Finds people in each cohort that share at least one surname with someone who was ALREADY in the profession.
    The assumption is that a surname match indicates kinship.

    Because a person can walk in their relative's occupational footsteps both via direct help (e.g. inheriting a
    business) or by more diffuse mechanisms (e.g. your mother was merely an occupational role model), we do not limit
    how long ago someone with your last name was in the profession. Your tenures may overlap (i.e. you're both in the
    profession at the same time) or the other person may have retired fifteen years before you joined.

    NB: because we consider overlap with ANY surnames (to catch people who add surnames, which is especially
    the case for married women) we make bags of all DISTINCT surnames, so a compound surname like "SMITH ROBSON"
    would become two surnames, "SMITH" and "ROBSON".

    NB: this function is meant to roughly identify kinship and err on the side of inclusion. It assumes that each
    match is then human-checked to weed out false positives, e.g. common surnames that coincidentally overlap.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :return: a dict with key = year and val = list of cohort members who share a surname with a more senior professional
    """

    # initialise a dict with distinct surnames for each year, then populate it
    surnames_by_year = {year: set() for year in range(start_year, end_year + 1)}
    for person_year in person_year_table:
        year = int(person_year[6])  # person_year[6] = year
        surnames = person_year[2].split()  # person_year[2] = surnames
        surnames_by_year[year].update(surnames)

    # get the fullnames of each cohort
    cohort_names = cohort_name_lists(person_year_table, start_year, end_year)

    # initiate a dict with key = year and value = full name of cohort member with a surname match to a previous year
    fullname_with_surname_match = {year: set() for year in range(start_year, end_year + 1)}

    # keep a cohort full name if at least one of its surnames matches a surname from a prior year
    for cohort_year, full_names in cohort_names.items():

        # get the set of all surnames from years BEFORE the cohort year, i.e. before you joined the profession
        surnames_in_prior_years = set()
        [surnames_in_prior_years.update(surnames) for year, surnames in surnames_by_year.items()
         if int(year) < int(cohort_year)]

        # see which of the current cohort surnames match those from prior years,
        # and keep that full name if there's a match
        for fn in full_names:
            surnames = fn.split(' | ')[0].split()
            [fullname_with_surname_match[cohort_year].add(fn) for sn in surnames if sn in surnames_in_prior_years]

    return fullname_with_surname_match


def entries(person_year_table, start_year, end_year, year_sum=False):
    """count the number of entries or exits per year (and if year_sum=False, per level)"""
    year_level_counters = year_level_dict(start_year, end_year)
    person_year_table.sort(key=itemgetter(0, 6))
    person_sequences = [g for k, [*g] in itertools.groupby(person_year_table, key=itemgetter(0))]
    for seq in person_sequences:
        if len(seq) > 1:  # ignore sequences one long, marking as entry or exit would double-count
            year_level_counters[int(seq[0][6])][int(seq[0][-1])] += 1  # first sequence element marks entry point
    return sorted_output(year_level_counters, 1, year_sum)[1:]  # first observation wrong due to censoring


# MEASURES OF MOBILITY/CHANGE #

def total_mobility(person_year_table, start_year, end_year):
    """return a dict of year : total mobility"""
    mobility_per_year = {year: 0 for year in range(start_year, end_year + 1)}
    for py in person_year_table:
        if py[5] != '0':
            mobility_per_year[int(py[6])] += 1
    return sorted(list(mobility_per_year.items()))[1:-1]


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