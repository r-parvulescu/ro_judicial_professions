"""
Handy helper functions.
"""

import csv
import itertools
from operator import itemgetter
from preprocess import sample
from preprocess import standardise


def get_header(profession, stage):
    """
    Different professions have different information, so the headers need to change accordingly.
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param stage: string, stage of data usage we're in; admissible values are "collect", "preprocess", "combine"
    :return: header, as list
    """

    if stage == 'collect':
        headers = {'judges': ["nume", "prenume", "instanță/parchet", "an", "lună"],

                   'prosecutors': ["nume", "prenume", "instanță/parchet", "an", "lună"],

                   'executori': ["nume", "prenume", "sediul", "an", "camera", 'localitatea', 'stagiu', 'altele'],

                   'notaries': ["nume", "prenume", "camera", "localitatea", "intrat", "ieşit"]}

        head = headers[profession]

    elif stage == 'preprocess':
        headers = {'judges': ["cod rând", "cod persoană", "nume", "prenume", "sex", "instituţie", "an",
                              "ca cod", "trib cod", "jud cod", "nivel"],

                   'prosecutors': ["cod rând", "cod persoană", "nume", "prenume", "sex", "instituţie", "an",
                                   "ca cod", "trib cod", "jud cod", "nivel"],

                   'executori': ["cod rând", "cod persoană", "nume", "prenume", "sex", "sediul", "an", "camera",
                                 "localitatea", "stagiu", "altele", "moştenitor"],

                   'notaries': ["cod rând", "cod persoană", "nume", "prenume", "sex", "an", "camera", "localitatea",
                                "moştenitor"]}

        head = headers[profession]

    else:  # stage == 'combine'
        head = ["cod rând", "cod persoană", "profesie", "nume", "prenume", "sex", "an", "ca cod", 'trib cod',
                'jud cod', 'nivel', 'instituţie', 'sediul, localitatea', 'stagiu', 'altele']

    return head


def row_to_dict(row, profession, stage):
    """
    Makes a dict by mapping list values to a list of keys, which vary by profession.
    :param row: a list
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param stage: string, stage of data usage we're in; admissible values are "collect", "preprocess", "combine"
    :return: dict
    """
    keys = get_header(profession, stage)
    return dict(zip(keys, row))


def percent(numerator, denominator):
    """
    Returns an integer valued percentage from a numerator and denominator. Evidently assumes that the numerator
    is the fraction of the denominator total. E.g. if n = 3 and d = 4, we get 75.

    :param numerator: int or float
    :param denominator: int or float
    :return: int, the percentage
    """

    return int(round(weird_division(numerator, denominator), 2) * 100)


def weird_division(numerator, denominator):
    """
    Returns zero if denominator is zero.
    NB: from https://stackoverflow.com/a/27317595/12973664

    :param numerator: something divisible, e.g. int or float
    :param denominator: something divisible, e.g. int or float
    :return: quotient, of type float
    """
    return float(numerator) / float(denominator) if denominator else 0.


def deduplicate_list_of_lists(list_of_lists):
    """
    Remove duplicate rows from table as list of lists quicker than list comparison: turn all rows to strings,
    put them in a set, them turn set elements to list and add them all to another list.

    :param list_of_lists: what it sounds like
    :return list of lists without duplicate rows (i.e. duplicate inner lists)
    """
    # inner list comprehension turns everything to a string to avoid concat errors, e.g. string + int
    uniques = set(['|'.join([str(entry) for entry in row]) for row in list_of_lists])
    return [row.split('|') for row in uniques]


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

    pid_col_idx = get_header(profession, stage).index('cod persoană')
    year_col_idx = get_header(profession, stage).index('an')
    surname_col_idx = get_header(profession, stage).index('nume')
    given_name_col_idx = get_header(profession, stage).index('prenume')

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


def sum_dictionary_values(list_of_dicts):
    """
    If each dict in a list has the exact same keys and the values are integers, floats, etc. this function returns a
    dict with the same keys, where values are sums of values from the separate dicts.
    :param list_of_dicts: a list of dictionaries with identical keys and summable values
    :return: dict, same keys as input dicts, values are sums of input dict values
    """
    sum_dict = {key: 0 for key in list_of_dicts[0].keys()}
    for d in list_of_dicts:
        for key in d.keys():
            sum_dict[key] += float(d[key])
    return sum_dict


def debug_names(person_period_table_path, profession, year_range, lev_dist, name_type):
    """
    Sometimes names vary between years by two diacritics or some slight misspelling due to input inconsistency.
    This function finds names in certain years (e.g. 1985, 1986) which are different up to a certain Levenshtein
    distance, and prints them out. It's then our job to see how we handle them.

    NB: takes as input a pre-processed table, with header

    :param person_period_table_path: str, path to where the person-period table lives on disk
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param year_range: 2-tuple of ints representing lower and upper years, e.g. (2004, 2018)
    :param lev_dist: int, levenshtein/edit distance between two strings, e.g. "DERP" and "DER" have lev_dist = 1
    :param name_type: str, "surname", "given name" or "full name"
    :return: None
    """

    # load the table
    with open(person_period_table_path, 'r') as in_f:
        person_period_table = list(csv.reader(in_f))[1:]  # skip header

    # get handy column indexes
    yr_col_idx = get_header(profession, "preprocess").index("an")
    surname_col_idx = get_header(profession, "preprocess").index("nume")
    given_name_col_idx = get_header(profession, "preprocess").index("prenume")

    # make a set of all names
    if name_type == "surname":
        name_set = {pp[surname_col_idx] for pp in person_period_table
                    if year_range[0] <= int(pp[yr_col_idx]) <= year_range[1]}
    elif name_type == "given name":
        name_set = {pp[given_name_col_idx] for pp in person_period_table
                    if year_range[0] <= int(pp[yr_col_idx]) <= year_range[1]}
    else:  # name_type == "full name":
        name_set = {pp[surname_col_idx] + ' | ' + pp[given_name_col_idx] for pp in person_period_table
                    if year_range[0] <= int(pp[yr_col_idx]) <= year_range[1]}

    # compute Levenshtein/edit distance between the names
    name_pairs_lev_dist_apart = standardise.pairwise_ldist(name_set, lev_dist)

    # print out the results for us to eyeball
    [print(pair) for pair in name_pairs_lev_dist_apart]
