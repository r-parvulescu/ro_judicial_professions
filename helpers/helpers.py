"""
Handy helper functions.
"""


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
