"""
Functions for handling gender identification.
"""

import json
import csv
import PyICU


def get_gender(given_names, row, gender_dict):
    """
    Assign gender to each person-period row.
    :param given_names: string of given names
    :param row: person-period row as list e.g. [col1 val, col2 val, col3 val]
    :param gender_dict: dictionary, key = name : val = gender
    :return person_gender, a string that only ever takes the values 'm', 'f' or 'dk'
    """
    person_gender = []
    given_names = given_names.split(' ')
    for name in given_names:
        if name not in gender_dict:
            print("NAME NOT IN GENDER DICT")
            print(row)  # show problem
            return ''
        else:
            if gender_dict[name] != "surname":
                person_gender.append(gender_dict[name])
    # if more than one given name, go with majority vote
    if not (person_gender[1:] == person_gender[:-1]):
        if ('f' in person_gender) and ('m' in person_gender):
            # if even split, put dk
            person_gender = 'dk'
        else:  # if a clear label and a "don't know", opt for clear label
            if 'f' in person_gender:
                person_gender = 'f'
            elif 'm' in person_gender:
                person_gender = 'm'
    else:
        if person_gender:
            person_gender = person_gender[0]
    return person_gender


def update_gender_dict(person_period_table):
    """
    Updates an existing gender dictionary: whenever it finds a given name not in the dictionary it
    prompts you for a gender for that given name: 'm', 'f', 'dk' (don't know) or 'surname', since sometimes the parser
    sneaks surnames in the wrong field. It then turns the name and your response into a a key-value pair
    (key = name : value = gender), and adds it to the dictionary. Finally it saves the next gender dictionary to
    a new json-text file.

    NB: to use the new dictionary, need to manually delete the old one and rename the new gender dict to the old.
    Did this to avoid overwriting at all costs, since making a new gender dictionary from scratch is very tedious.

    :param person_period_table: string, path to a person-period table in a csv
    :return: None

    """

    # load the gender dict
    gender_dict = get_gender_dict()

    # if we get a path, load the existing gender dict; if table, work on it stragithawawy
    if type(person_period_table) is str:
        with open(person_period_table, 'r') as f:
            person_period_table = list(csv.reader(f))[1:]  # skip the header

    for row in person_period_table:
        given_names = row[1].split(' ')
        for name in given_names:
            if name not in gender_dict:  # prompt to assign name
                print(row)
                print(name)
                answer = input("What gender is this name? f,m,dk, surname ")
                if not ((answer == 'f') or (answer == 'm') or (answer == 'dk') or (answer == 'surname')):
                    answer = input("Incorrect format, please, what gender is this name? f,m,dk ")
                gender_dict[name] = answer

    # write new dict to file
    with open('preprocess/gender/ro_gender_dict_updated.txt', 'w') as out_gd:
        # dump the dict
        json.dump(gender_dict, out_gd)


def get_gender_dict():
    with open('preprocess/gender/ro_gender_dict.txt', 'r') as gd:
        return json.load(gd)


def print_uniques(csv_file, col_idx):
    """print all unique column entries, helps weed out typos, misspellings, etc. in names"""
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip head
        uniques = set()
        for row in reader:
            uniques.add(row[col_idx])

    # sort taking into account Romanian diacritics
    collator = PyICU.Collator.createInstance(PyICU.Locale('ro_RO.UTF-8'))
    uniques = [i for i in sorted(list(uniques), key=collator.getSortKey)]
    for u in sorted(list(uniques)):
        print(u)
