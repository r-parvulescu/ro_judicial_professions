# FUNCTIONS FOR MOBILITY BETWEEN GEOGRAPHIC UNITS #

import csv
import natsort
import itertools
from operator import itemgetter
from helpers import helpers


def inter_unit_mobility_table(person_year_table, out_dir, profession, unit_type):
    """
    Write to disk a table of subtables, where each subtable is a square matrix where rows are sending units and
    columns are receiving units -- diagonals are "did not move". The output should look something like this:

    YEAR 1
                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    2       0       1
        UNIT 2    6       10      0
        UNIT 3    3       4       4
        ...


    YEAR 2

                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    0        3       5
        UNIT 2    10       5       3
        UNIT 3    2        5       1
        ...
    ...

    :param person_year_table: person year table as a list of lists
    :param out_dir: directory where the inter-unit mobility table(s) will live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table (e.g. "ca cod")
    :return: None
    """

    # get the mobility dict
    mobility_dict = inter_unit_mobility(person_year_table, profession, unit_type)

    # and write it to disk as a table of subtables
    table_out_path = out_dir + unit_type + '_interunit_mobility_tables.csv'
    with open(table_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        for year, sending_units in mobility_dict.items():
            units = natsort.natsorted(list(sending_units))
            writer.writerow([year])
            writer.writerow([''] + units)
            for u in units:
                writer.writerow([u] + [sending_units[u][units[i]] for i in range(0, len(units))])
            writer.writerow(['\n'])


def inter_unit_mobility(person_year_table, profession, unit_type):
    """
    For each year make a dict of interunit mobility where first level keys years, second level keys are sending units,
    and third level keys are receiving units. The base values are counts of movement; diagonals are "did not move".
    The dict form is:

    {'year1':
        {'sending unit1': {receiving unit1: int, receiving unit2: int,...},
         'sending unit2': {receiving unit1: int, receiving unit2: int,...},
         ...
         },
     'year2':
        {'sending unit1': {receiving unit1: int, receiving unit2: int,...},
         'sending unit2': {receiving unit1: int, receiving unit2: int,...},
         ...
         },
     ...
    }

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table

    :return: a multi-level dict
    """

    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)

    # get start and end year of all observations
    person_year_table.sort(key=itemgetter(year_col_idx))
    start_year, end_year = int(person_year_table[0][year_col_idx]), int(person_year_table[-1][year_col_idx])

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
            # compare this year and next year's units
            if idx < len(person) - 1:
                sender = person_year[unit_col_idx]
                receiver = person[idx + 1][unit_col_idx]
                # the transition year is, by convention, the sender's year
                transition_year = int(person_year[year_col_idx])
                # if they're different, we have mobility
                if sender != receiver:
                    # increment the sender-receiver cell in the appropriate year
                    mobility_dict[transition_year][sender][receiver] += 1
                else:  # they didn't move, increment the diagonal
                    mobility_dict[transition_year][sender][sender] += 1
            else:  # last observation, movement is out, which we count in other places, so ignore
                pass

    return mobility_dict
