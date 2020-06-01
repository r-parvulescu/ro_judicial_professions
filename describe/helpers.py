"""Helpers functions for describe package."""


def get_header(profession):
    """
    Different professions have different information, so the headers need to change accordingly.
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: header, as list
    """

    if profession == 'judges' or profession == 'prosecutors':
        headers = ["cod rând", "cod persoană", "nume", "prenume", "sex", "instituţie", "an",
                   "ca cod", "trib cod", "jud cod", "nivel"]
    elif profession == 'executori':
        headers = ["cod rând", "cod persoană", "nume", "prenume", "sex", "sediul", "an",
                   "camera", 'localitatea', 'stagiu', 'altele']
    else:  # profession == 'notaries'
        headers = ["cod rând", "cod persoană", "nume", "prenume", "sex", "an", "camera", 'localitatea']

    return headers


def row_to_dict(row, profession):
    """
    Makes a dict by mapping list values to a list of keys, which vary by profession.
    :param row: a list
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: dict
    """
    keys = get_header(profession)
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
