"""Helpers functions for describe package."""


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
                                 "localitatea", "stagiu", "altele"],

                   'notaries': ["cod rând", "cod persoană", "nume", "prenume", "sex", "an", "camera", "localitatea"]}

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


def weird_division(numerator, denominator):
    """
    Returns zero if denominator is zero.
    NB: from https://stackoverflow.com/a/27317595/12973664

    :param numerator: something divisible, e.g. int or float
    :param denominator: something divisible, e.g. int or float
    :return: quotient, of type float
    """
    return float(numerator) / float(denominator) if denominator else 0.
