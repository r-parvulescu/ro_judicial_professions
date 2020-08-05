"""
Function for  assigning the a unit-code to a person-period given the full name of its unit
"""

import json


def get_workplace_profile(workplace, workplace_codes):
    """
    Return the organisational code and hierarchical level of each workplace, i.e. the person's workplace profile.

    :param workplace: str, the full name of the workplace
    :param workplace_codes: the codes that locates each workplace within its organisational hierarchy
    :return a list of the workplace code and the level, e.g. ["CA5", "TB16", "J58", "1'] for "JUDECĂTORIA CLUJ"
    """
    code = workplace_codes[workplace.strip()]
    level = get_workplace_level(code)
    return code + [level]


def get_workplace_level(workplace_code):
    """
    Get the level (in the organisational hierarchy) at which a certain workplace is located. This holds for court/judge
    organisational hierarchy as well as parquet/prosecutor hierarchy (the two hierarchies mirror each other).
    1 = judecătorie (lowest level, one);
    2 = tribunal (second level);
    3 = curte de apel (third level);
    4 = înalta curte de casaţie şi justiţie (High Court, highest level)

    :param workplace_code: a list containing three strings that uniquely locate that workplace within the court/parquet
                           hierarchies, e.g., ["CA5", "TB16", "J58"] is the code for "JUDECĂTORIA CLUJ"
    :return level: a string, one of 1, 2, 3, or 4
    """
    if workplace_code[-1] != '-88':
        level = '1'
    elif workplace_code[-2] != '-88':
        level = '2'
    elif workplace_code[-3] != '-88':
        level = '3'
    else:
        level = '4'
    return level


def get_workplace_codes(profession):
    """
    Load and return a dict that associates each workplace name with a code locating it in its profession-specific
    organisational hierarchy. E.g. "JUDECĂTORIA CLUJ" has code ["CA5", "TB16", "J58"].

    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a dict where keys are workplace names and values are its unique code/location in its org hierarchy.
    """
    workplace_type = ''
    if profession == 'prosecutors':
        workplace_type = 'parquet'
    if profession == 'judges':
        workplace_type = 'court'
    unit_codes = 'preprocess/workplace/' + workplace_type + '_codes.txt'
    with open(unit_codes, 'r') as uc:
        return json.load(uc)


def get_appellate_code(profession, court_codes, py_as_dict):
    """
    Get just the appellate code (e.g. 'CA4') of a certain person-year.

    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param court_codes: code of each court, as output by get_unit_codes
    :param py_as_dict: a person-year as a dictionary, e.g. {"name": DERP, "year": 1990, "gender": f}
    :return: the appellate code, as a string
    """
    # if dealing with prosecutors or notaries, translate "camera" (which indicates the
    # appellate region) to an appellate code, so it's comparable with code for judges and prosecs
    if profession == 'notaries' or profession == 'executori':
        appeals_court = 'CURTEA DE APEL ' + py_as_dict['camera']
        appellate_code = court_codes[appeals_court][0]
    else:  # profession is 'judges' or 'prosecutors'
        appellate_code = py_as_dict['ca cod']

    return appellate_code


def hierarchy_to_codes(profession):
    """
    Convert a dictionary of institutions with hierarchical structure like this:

    {'COURT OF APPEALS X': ['CAX',
        {'TRIBUNAL A': ['TBA',
            {'LOCAL COURT 2': 'LC2'}
        }
    }

    Into a dict where each institution full name is associated with a code uniquely describing that institutions's
    place within the relevant professional judicial hierarchcy. So the hierarchy dictionary above (referring to judge
    institutions, i.e. courts) would generate the following code dictionary:

    'LOCAL COURT 2': 'CAX', 'TBA', 'LC2'
    'TRIBUNAL A': 'CAX, 'TBA', '-88'
    'COURT OF APPEALS A': 'CAX', '-88', '-88'

    By convention, the high court of appeals has the code: '-88', '-88', '-88'.

    Dump the code dict in a json.txt file.

    :param profession: string: 'judges', 'prosecutors', 'notaries', 'executori'
    :return: None
    """

    units_hierarchical = ''
    units_codes = ''
    parquet = bool

    if profession == 'judges':
        parquet = False
        units_hierarchical = 'preprocess/workplace/courts_hierarchical.txt'
        units_codes = 'preprocess/workplace/court_codes.txt'
    if profession == 'prosecutors':
        parquet = True
        units_hierarchical = 'preprocess/workplace/parquets_hierarchical.txt'
        units_codes = 'preprocess/workplace/parquet_codes.txt'

    units = {}
    with open(units_hierarchical) as ch:
        data = json.load(ch)
        for ca_k, ca_v in data.items():
            apellate = ca_k[22] if parquet else ca_k[0]
            if apellate == "C":
                ca_code = data[ca_k][0]
                units[ca_k] = [ca_code, '-88', '-88']
                for trib_k, trib_v in data[ca_k][1].items():
                    trib_code = data[ca_k][1][trib_k][0]
                    units[trib_k] = [ca_code, trib_code, '-88']
                    if ("COMERC" not in trib_k) and ("MINORI" not in trib_k):
                        for jud_k, jud_v in data[ca_k][1][trib_k][1].items():
                            jud_code = (data[ca_k][1][trib_k][1][jud_k])
                            units[jud_k] = [ca_code, trib_code, jud_code]
                else:
                    if parquet:
                        units["PARCHETUL DE PE LÂNGĂ ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE"] = ['-88', '-88', '-88']
                        units["DIRECŢIA DE INVESTIGARE A INFRACŢIUNILOR DE CRIMINALITATE ORGANIZATĂ ŞI TERORISM"] = \
                            ["DIICOT", '-88', '-88']
                        units["DIRECŢIA NAŢIONALĂ ANTICORUPŢIE"] = ['DNA', '-88', '-88']
                    else:
                        units["ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE"] = ['-88', '-88', '-88']

    with open(units_codes, 'w') as json_file:
        json.dump(units, json_file)
