"""
Functions for calculating counts of different mobility events, across different units.
"""

from operator import itemgetter
import itertools
import copy
import natsort
from helpers import helpers


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
    cohort_counts = copy.deepcopy(pop_counts)

    # get total counts
    for person in person_year_table:
        update_size_gender(pop_counts, person, start_year, end_year, profession, units, unit_type=unit_type)
    percent_female(pop_counts, units, unit_type=unit_type)

    # then get cohort counts

    # group person-years by person
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(1))]  # row[1] == PID
    for person in people:
        # if describing entry cohorts we want the first person-year, else the last person-year (i.e. exit cohorts)
        edge_person_year = person[0] if entry else person[-1]
        update_size_gender(cohort_counts, edge_person_year, start_year, end_year, profession,
                           units, unit_type=unit_type)
    percent_female(cohort_counts, units, unit_type=unit_type)
    update_cohort_of_population(cohort_counts, pop_counts, entry=entry, units=units)

    return cohort_counts if cohorts else pop_counts


def update_size_gender(count_dict, row, start_year, end_year, profession, units, unit_type=None):
    """
    Counts the number of people per year; if unit is given, gives the count of person per year, per unit

    :param count_dict: a dictionary of counts -- for format, see function metrics_dict
    :param row: a person-year as a list
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
    gender = dict_row['sex']
    year = int(dict_row['an'])
    unit = dict_row[unit_type] if units else None

    # stay within bounds
    if start_year <= year <= end_year:

        # increment cohort sizes and cohort gender counters
        count_dict['grand_total'][year]['total_size'] += 1
        count_dict['grand_total'][year][gender] += 1
        if unit_type:
            count_dict[unit][year]['total_size'] += 1
            count_dict[unit][year][gender] += 1


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
            count_dict['grand_total'][year]['percent_female'] = int(round(count_dict['grand_total'][year]['f']
                                                                          / count_dict['grand_total'][year][
                                                                              'total_size'],
                                                                          2) * 100)
        if unit_type:
            for u in units:
                if count_dict[u][year]['total_size'] != 0:
                    count_dict[u][year]['percent_female'] = int(round(count_dict[u][year]['f']
                                                                      / count_dict[u][year]['total_size'],
                                                                      2) * 100)


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
            cohorts_dict['grand_total'][year]['chrt_prcnt_of_pop'] = int(round(
                cohorts_dict['grand_total'][year]['total_size'] / yearly_pop, 2) * 100)

        if units:
            for u in units:
                # for entry cohorts, compare with preceding year, unless it's the first year
                if entry and year - 1 in cohorts_dict:
                    yearly_unit_pop = population_dict[u][year - 1]['total_size']
                else:
                    yearly_unit_pop = population_dict[u][year]['total_size']

                if cohorts_dict[u][year]['total_size'] != 0:
                    cohorts_dict[u][year]['chrt_prcnt_of_pop'] = int(round(
                        cohorts_dict[u][year]['total_size'] / yearly_unit_pop, 2) * 100)


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


def cohort_name_lists(person_year_table, start_year, end_year, profession, entry=True, combined=False):
    """
    For each year in the range from start_year to end_year, return a list of full-names of the people that joined
    the profession in that year.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param entry: bool, True if we're getting data for entry cohorts, False if for exit cohorts
    :param combined: bool, True if we're dealing with the table of combined professions
    :return: a dict of years, where each value is a list of full-name tuples of the people who joined the profession
             that year
    """
    stage = 'preprocess'
    if combined:
        profession, stage = 'all', 'combine'

    pid_col_idx = helpers.get_header(profession, stage).index('cod persoană')
    year_col_idx = helpers.get_header(profession, stage).index('an')
    surname_col_idx = helpers.get_header(profession, stage).index('nume')
    given_name_col_idx = helpers.get_header(profession, stage).index('prenume')

    # make a dict, key = year, value = empty list
    cohorts = {year: [] for year in range(start_year, end_year + 1)}
    # group by people
    people = [person for k, [*person] in itertools.groupby(sorted(person_year_table, key=itemgetter(pid_col_idx)),
                                                           key=itemgetter(pid_col_idx))]

    # append the full name of the first year of each person to its cohort
    for person in people:
        edge_person_year = person[0] if entry else person[-1]

        if start_year <= int(edge_person_year[year_col_idx]) <= end_year:
            cohorts[int(edge_person_year[year_col_idx])].append(
                edge_person_year[surname_col_idx] + ' | ' + edge_person_year[given_name_col_idx])

    return cohorts


def brought_in_by_family(person_year_table, start_year, end_year, profession):
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
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a dict with key = year and val = list of cohort members who share a surname with a more senior professional
    """

    # initialise a dict with distinct surnames for each year, then populate it
    surnames_by_year = {year: set() for year in range(start_year, end_year + 1)}
    for person_year in person_year_table:
        year = int(person_year[6])  # person_year[6] = year
        surnames = person_year[2].split()  # person_year[2] = surnames
        surnames_by_year[year].update(surnames)

    # get the fullnames of each cohort
    cohort_names = cohort_name_lists(person_year_table, start_year, end_year, profession)

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


def inter_unit_mobility(person_year_table, profession, unit_type, start_year, end_year):
    """
    For each year make a dict of interunit mobility table, a square matrix where rows are sending unit and columns are
    receiving unit -- diagonals are "did not move".

    The output table should be composed of year sub-tables and should look something like this:

    YEAR 1
                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    2       0       1
        UNIT 2    6       10      0
        UNIT 3    3       4       4


    YEAR 2

                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    0        3       5
        UNIT 2    10       5       3
        UNIT 3    2        5       1

    :param person_year_table:
    :param profession:
    :param unit_type:
    :return:
    """
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)

    # the sorted list of unique units
    units = sorted(list({person_year[unit_col_idx] for person_year in person_year_table}))

    # make the mobility dict, which later will become a mobility matrix
    mobility_dict = {}
    for year in range(start_year, end_year + 1):
        # the first-level key is the row/sender, the second-level key is the column/receiver
        units_dict = {unit: {unit: 0 for unit in units} for unit in units}
        mobility_dict.update({year: units_dict})

    # break up table into people
    person_year_table.sort(key=itemgetter(pid_col_idx, year_col_idx))  # sort by person ID and year
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # look at each person
    for person in people:
        # look through each of their person-years
        for idx, person_year in enumerate(person):
            # compare this year and last year's units
            if idx > 0:
                sender = person[idx - 1][unit_col_idx]
                receiver = person_year[unit_col_idx]
                # if they're different, we have mobility
                if sender != receiver:
                    # the transition year is, by convention, the sender's year
                    transition_year = person_year[year_col_idx]
                    # increment the sender-receiver cell in the appropriate year
                    mobility_dict[transition_year][sender][receiver] += 1

    return mobility_dict
