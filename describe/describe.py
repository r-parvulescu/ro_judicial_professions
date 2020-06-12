"""
Functions for creating descriptive tables and graphs.
"""

import csv
import itertools
import operator
import natsort
from describe import descriptives
from helpers import helpers


def describe(in_file_path, out_directory, profession, start_year, end_year, unit_type=None):
    """
    Generate basic descriptives , and write them to disk.

    :param in_file_path: path to the base data file
    :param out_directory: sting, directory where the descriptives files will live
    :param start_year: first year we're considering
    :param end_year: last year we're considering
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: None or list; if list, each entry is, type of unit we want table deaggreagted by,
                      e.g. one table where rows are metrics for each appellate court region,
                           and another where rows are metrics for each hierarchical level of the judicial system
    :return: None
    """

    with open(in_file_path, 'r') as infile:
        reader = csv.reader(infile)
        next(reader, None)  # skip headers
        table = list(reader)

    # make table of total counts per year
    year_counts_table(table, start_year, end_year, profession, out_directory)

    # make tables for entry and exit cohorts, per year per gender
    entry_exit_gender(table, start_year, end_year, profession, out_directory, entry=True)
    entry_exit_gender(table, start_year, end_year, profession, out_directory, entry=False)

    # for prosecutors and judges only
    if profession == 'prosecutors' or profession == 'judges':

        # make table for extent of career centralisation around capital city appellate region, per year per unit
        career_movements_table(table, profession, "ca cod", out_directory)

        # make tables of total counts per year, per level in judicial hierarchy
        year_counts_table(table, start_year, end_year, profession, out_directory, unit_type='nivel')

        # make tables for exit cohorts, per year, per gender, per level in judicial hierarchy
        entry_exit_gender(table, start_year, end_year, profession, out_directory, entry=False, unit_type='nivel')

        # make table for mobility between appellate court regions
        inter_unit_mobility_table(table, out_directory, profession, 'ca cod')

        for u_t in unit_type:
            # make tables for entry and exit cohorts, per year per unit type
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_directory, entry=True)
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_directory, entry=False)


def year_counts_table(person_year_table, start_year, end_year, profession, out_dir, unit_type=None):
    """
    Makes a table of yearly population counts, and optionally breaks down total counts by unit_type.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param out_dir: directory where the table will live
    :param unit_type: None, or if provided, a string indicating the type of unit (e.g. appellate court region)
    :return: None
    """

    if unit_type:
        out_path = out_dir + profession + '_' + unit_type + '_year_totals.csv'
        fieldnames = ["unit"] + ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        year_metrics = descriptives.pop_cohort_counts(person_year_table, start_year, end_year,
                                                      profession, cohorts=False, unit_type=unit_type)
    else:
        out_path = out_dir + profession + '_year_totals.csv'
        fieldnames = ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        year_metrics = descriptives.pop_cohort_counts(person_year_table, start_year, end_year,
                                                      profession, cohorts=False)

    # make table and write to disk
    with open(out_path, 'w') as o_file:
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        if unit_type:
            # iterate over units
            for unit, years in year_metrics.items():
                if unit != 'grand_total':
                    # iterate over years:
                    for year, metrics in years.items():
                        if start_year <= int(year) <= end_year - 1:  # stay within bounds
                            writer.writerow({"unit": unit, "year": year, "female": metrics['f'], "male": metrics["m"],
                                             "don't know": metrics['dk'], "total count": metrics['total_size'],
                                             "percent female": metrics['percent_female']})

        else:  # no units, just straight years
            for year, metrics in year_metrics['grand_total'].items():
                writer.writerow({"year": year, "female": metrics['f'], "male": metrics["m"],
                                 "don't know": metrics['dk'], "total count": metrics['total_size'],
                                 "percent female": metrics['percent_female']})


def entry_exit_gender(person_year_table, start_year, end_year, profession, out_dir, entry=True, unit_type=None):
    """
    Make a table that shows the count and percentage of entry and exit cohorts for each gender, and for each
    unit if applicable.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param out_dir: directory where the table will live
    :param unit_type: None, or if provided, a string indicating the type of unit (e.g. appellate court region)
    :param entry: bool, True if entry cohorts, False if exit cohorts (i.e. everyone who left in year X)
    :return: None
    """

    type_of_cohort = 'entry' if entry else 'departure'

    if unit_type:
        out_path = out_dir + profession + '_' + unit_type + '_' + type_of_cohort + '_cohorts_gender.csv'
        fieldnames = ["unit"] + ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        cohorts = descriptives.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                 cohorts=True, unit_type=unit_type, entry=entry)
    else:
        out_path = out_dir + profession + '_' + type_of_cohort + '_cohorts_gender.csv'
        fieldnames = ["year"] + ["female", "male", "don't know", "total count", "percent female"]
        cohorts = descriptives.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                 cohorts=True, unit_type=None, entry=entry)

    # write table to disc
    with open(out_path, 'w') as o_file:
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        # if we're given unit types
        if unit_type:
            # iterate over units
            for unit, years in cohorts.items():
                if unit != 'grand_total':
                    # iterate over the years:
                    for year, metrics in years.items():
                        if start_year <= int(year) <= end_year - 1:  # stay within bounds
                            writer.writerow({"unit": unit, "year": year, "female": metrics['f'], "male": metrics["m"],
                                             "don't know": metrics['dk'], "total count": metrics['total_size'],
                                             "percent female": metrics['percent_female']})

        else:  # no units, just straight years
            for year, metrics in cohorts['grand_total'].items():
                writer.writerow(
                    {"year": year, "female": metrics['f'], "male": metrics["m"], "don't know": metrics['dk'],
                     "total count": metrics['total_size'], "percent female": metrics['percent_female']})


def entry_exit_unit_table(person_year_table, start_year, end_year, profession, unit_type, out_dir, entry=True):
    """
    Make two csv tables, where the rows are geographic regions and the columns are years. For one table the cells are
    the total number of departures from that region, for that year; for the other table, the cells are the percent
    of departures, relative to all people in that region, in that year.

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, the first year we consider
    :param end_year: int, the last year we consider
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table (e.g. "camera")
    :param entry: bool, True if entry cohorts, False if exit cohorts (i.e. everyone who left in year X)
    :param out_dir: directory where the table will live
    :return: None
    """

    # get data on cohorts by year and unit
    cohorts_per_unit = descriptives.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                      cohorts=True, unit_type=unit_type, entry=entry)
    # write the table to disk
    type_of_cohort = 'entry' if entry else 'departure'
    out_path = out_dir + profession + '_' + type_of_cohort + '_' + unit_type + '_rates.csv'
    with open(out_path, 'w') as o_file:
        fieldnames = ['unit'] + list(range(start_year, end_year))  # omit last year: all leave in right censor year
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        # iterate over units
        for unit, years in cohorts_per_unit.items():
            percent_row = {'unit': unit}
            count_row = {'unit': ''}
            # iterate over the years:
            for year, measures in years.items():
                if start_year <= int(year) <= end_year - 1:  # stay within bounds
                    percent_row.update({year: measures['chrt_prcnt_of_pop']})
                    count_row.update({year: '(' + str(measures['total_size']) + ')'})
            # display the count row under the percent row
            writer.writerow(percent_row)
            writer.writerow(count_row)


def career_movements_table(person_year_table, profession, unit_type, out_dir):
    """
    Write to disk a csv table of metrics that shows, for cohorts in multi-year windows, several metrics on
    career-level inter-unit mobility

    We want a table with columns

    ["never_left_home", "buc_never_left", "non_buc_through_buc", non_buc_through_non_buc]

    which meani (in order)
        - "percent of all careers that never left their home unit",
        - "percent of careers that began in Bucharest and never left that unit",
        - "percent of careers that did not start in the Bucharest unit and did, at some point, pass through the
           Bucharest unit"
        - "percent of careers that did not start in Bucharest, did change unit, but only to non-Bucharest units

    And the rows are [5, 10, 15], represeting the above measures at different increments since the career began: five
    years into the career, ten, then fifteen years into the career

    The big table will be composed of a set of little tables as described above, one each for all careers that started
    in the time-windows provided by function get_time_length_bands. Examples of time windows are:
        i.   1988-1993
        ii.  1994-1999
        iii. 2000-2005
        iv.  2006-2011
        v.   2011-2016

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table (e.g. "camera")
    :param out_dir: directory where the table will live
    :return:
    """

    # get the code for the Bucharest unit, given the unit type and the profession
    bucuresti_codes = {'judges': {'ca cod': 'CA4', 'trib cod': 'TB9'},
                       'prosecutors': {'ca cod': 'PCA4', 'trib cod': 'PTB9'},
                       'executori': {'camera': 'BUCUREŞTI', 'localitatea': 'BUCUREŞTI'},
                       'notaries': {'camera': 'BUCUREŞTI', 'localitatea': 'BUCUREŞTI'}}

    buc_code = bucuresti_codes[profession][unit_type]

    # split the table into persons/careers;  row[1] == PID
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=operator.itemgetter(1))]

    # bin the careers into the multi-year time-bands, according to the year in which the career began,
    # and also into bins according to career length; e.g. careers that began in 1995 lasting at least ten years
    time_length_bands = get_time_length_bands(profession)

    fill_time_bands(people, time_length_bands, profession)

    # get the column index where information on our unit type (e.g. appellate court region) resides
    unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)

    # write the table to disk
    out_path = out_dir + profession + '_' + unit_type + '_career_centralisation.csv'
    with open(out_path, 'w') as o_file:
        fieldnames = ['max career length'] + ['never_left_home', 'buc_never_left',
                                              'non_buc_through_buc', 'non_buc_through_non_buc']
        writer = csv.DictWriter(o_file, fieldnames=fieldnames)
        writer.writeheader()

        # for each time band
        for band, lengths in time_length_bands.items():

            writer.writerow({'max career length': band, 'never_left_home': '',
                             'buc_never_left': '', 'non_buc_through_buc': '',
                             'non_buc_through_non_buc': ''})

            # for each career length bin
            for length, careers in lengths.items():

                # initialise the counters for
                never_left_home = 0  # never leaving home unit
                never_left_buc = 0  # never leaving Bucharest (if from Bucharest)
                non_buc_through_buc = 0  # passing through Bucharest (if not from Bucharest)

                # number of careers in time band, in length bin that started in Bucharest
                num_start_buc = 0

                # for each career
                for c in careers:

                    # if the first year of their career was in Bucharest, increment counter of careers that
                    # began in the capital city
                    if c[0][unit_col_idx] == buc_code:
                        num_start_buc += 1

                    # if groupby unit type returns only one group, person didn't leave home unit
                    if len([group for key, [*group] in itertools.groupby(c,
                                                                         key=operator.itemgetter(unit_col_idx))]) <= 1:
                        never_left_home += 1

                        # if they've never left home AND the first year of their career was in Bucharest, these are
                        # capital city people that never left
                        if c[0][unit_col_idx] == buc_code:
                            never_left_buc += 1

                    else:  # they left home

                        # if the first year of their careers was NOT Bucharest AND Bucharest is in their careers,
                        # these are provincials whose careers took them into the capital city
                        if c[0][unit_col_idx] != buc_code and \
                                len({prsn_yr[unit_col_idx] for prsn_yr in c if prsn_yr[unit_col_idx] == buc_code}) > 0:
                            non_buc_through_buc += 1

                # number of careers in this time band, in this length bin
                num_careers = len(careers)

                # number of careers that did not start in Bucharest
                num_start_non_buc = num_careers - num_start_buc

                # number of careers that did not start in Bucharest and never went through Bucharest
                num_non_buc_through_non_buc = num_start_non_buc - non_buc_through_buc

                percent_never_left_home = int(round(helpers.weird_division(never_left_home, num_careers), 2) * 100)
                percent_never_left_buc = int(round(helpers.weird_division(never_left_buc, num_start_buc), 2) * 100)
                percent_non_buc_through_buc = int(round(helpers.weird_division(non_buc_through_buc,
                                                                               num_start_non_buc), 2) * 100)
                percent_non_buc_through_non_buc = int(round(helpers.weird_division(num_non_buc_through_non_buc,
                                                                                   num_start_non_buc), 2) * 100)

                # and write the row
                percent_row = {'max career length': length, 'never_left_home': percent_never_left_home,
                               'buc_never_left': percent_never_left_buc,
                               'non_buc_through_buc': percent_non_buc_through_buc,
                               'non_buc_through_non_buc': percent_non_buc_through_non_buc}
                writer.writerow(percent_row)

                count_row = {'max career length': '', 'never_left_home': '(' + str(never_left_home) + ')',
                             'buc_never_left': '(' + str(never_left_buc) + ')',
                             'non_buc_through_buc': '(' + str(non_buc_through_buc) + ')',
                             'non_buc_through_non_buc': '(' + str(num_non_buc_through_non_buc) + ')'}
                writer.writerow(count_row)


def fill_time_bands(list_of_persons, time_length_bands, profession):
    """
    Fills a dict of time bands and career lengths with the appropriate careers in the approriate time bands and
    length bins.

    :param list_of_persons: a list of people, where each person is a list of person-years sharing the same person-ID
    :param time_length_bands: dict of dicts, first level key is the time band (e.g. 1988-1993), value is a dict with
                              where each key is the max length of a career and the value is all the careers whose
                              length is less than that key/max length. For example,

                             {"1988-1993": {5: [], 10: [], 15: []}, "1994-1999": {5: [], 10: [], 15: []},
                             "2000-2005": {5: [], 10: [], 15: []}, "2006-2011": {5: [], 10: [], 15: []},
                             "2011-2016": {5: [], 10: [], 15: []}}

    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    for person in list_of_persons:
        start_year_of_career = helpers.row_to_dict(person[0], profession, 'preprocess')
        year = start_year_of_career['an']
        for band in time_length_bands:
            # NB: since the right censor year varies, not all time bands will contain ten or fifteen year careers
            lower_year, upper_year = int(band.split('-')[0]), int(band.split('-')[1])
            if lower_year <= int(year) <= upper_year:  # ignore careers outside the desired time bands
                if len(person) <= 5:
                    time_length_bands[band][5].append(person)
                elif 5 < len(person) <= 10:
                    time_length_bands[band][10].append(person)
                else:  # 10 < len(person)
                    time_length_bands[band][15].append(person)


def get_time_length_bands(profession):
    """
    Different profession have different time length bands. Return the appropriate one.
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a dict of time length bands (itself a dict of dicts)
    """
    if profession == 'judges' or profession == 'prosecutors':

        time_length_bands = {"1988-1993": {5: [], 10: [], 15: []}, "1994-1999": {5: [], 10: [], 15: []},
                             "2000-2005": {5: [], 10: [], 15: []}, "2006-2011": {5: [], 10: [], 15: []},
                             "2011-2016": {5: [], 10: [], 15: []}}

    elif profession == 'executori':

        time_length_bands = {"2001-2005": {5: [], 10: [], 15: []}, "2006-2010": {5: [], 10: [], 15: []},
                             "2011-2015": {5: [], 10: [], 15: []}}

    else:  # profession == 'notari
        time_length_bands = {}

    return time_length_bands


def inter_professional_transition_table(infile_path, out_dir, year_window):
    """
    Finds possible name matches between people who retired in year X from profession A, and people who joined
    professions B, C... in the years from X to X+4, inclusive. In other words, if someone left a profession one year,
    see if in the next five years they joined any of the other professions.

    NB: need to choose carefully the start and end years since only for some years do we have overlap between
        different professions

    NB: this function assumes that each match will be human-checked afterwards. Consequently, it errs on the side
        of over-inclusion, i.e. prefers false positives.

    :param infile_path: str, path to where a person-year table that covers multiple professions lives
    :param out_dir: directory where the interprofessional transition table will live
    :param year_window: int, how many years after exit we look for interprofessional transition;
                        if year_window = 0, we want only professional transfers in the exit year
                        if year_window = 3, we want only professional transfers in the exit year and two
                            consecutive years, e.g. 2000-2002 (the years 2000, 2001, and 2003)
                        etc.
    :return: None
    """

    # load the multiprofessional person-year table
    with open(infile_path, 'r') as in_file:
        multiprofs_py_table = list(csv.reader(in_file))[1:]  # skip first line, headers
        # sort by year
        year_col_idx = helpers.get_header('all', 'combine').index('an')
        multiprofs_py_table.sort(key=operator.itemgetter(year_col_idx))

    # get start and end year of all observations
    start_year, end_year = int(multiprofs_py_table[0][year_col_idx]), int(multiprofs_py_table[-1][year_col_idx])

    # initialise a list/log of cross-professional matches, so we can eyeball matches for errors
    cross_prof_match_log = []

    # for each profession get the first and last observation years and the full names of yearly entry and exit cohorts
    professions_data = professions_yearspans_cohorts(multiprofs_py_table, combined=True)

    # initialise a dict (later a set of matrices) where each year is a table, each first-level key is a row,
    # representing the sending profession, and each second level key is a column, representing the receiving profession;
    # the base values are counts of how many people went from profession A to B in year X.
    # make the mobility dict, which later will become a mobility matrix
    transfers_dict = {}
    for exit_year in range(start_year, end_year):
        # the first-level key is the row/sender, the second-level key is the column/receiver
        professions_dict = {prof: {prof: 0 for prof in professions_data} for prof in professions_data}
        transfers_dict.update({exit_year: professions_dict})

    # for each profession
    for sending_profession in professions_data:
        # see what the other professions are
        other_professions = {prof for prof in professions_data if prof != sending_profession}

        # for each yearly exit cohort
        for exit_year, names in professions_data[sending_profession]['exit'].items():

            # get a set of all names who joined every other profession on the range "year" to "year + year_window"
            # e.g. if year == 2000 and year_window == 2, the set includes all entrants in years [2000, 2002]
            other_professions_entrants = set()
            for other_prof in other_professions:

                # don't consider profession Y if we don't have data for it yet
                if int(exit_year) >= professions_data[other_prof]['start year']:

                    # last_year makes sure that our year window doesn't go out of bounds
                    last_year = min(int(exit_year) + year_window, professions_data[other_prof]['end year'])

                    for entry_year in range(int(exit_year), last_year + 1):
                        # not all professions have the same year set
                        if entry_year in professions_data[other_prof]['entry']:

                            for entrant_name in professions_data[other_prof]['entry'][entry_year]:
                                other_professions_entrants.add((entrant_name, entry_year, other_prof))

            for exitee_name in names:

                # look for name match in set of entrants into other professions, in the specified time window
                for entrant in other_professions_entrants:
                    entrant_name, entry_year, entry_profession = entrant[0], entrant[1], entrant[2]

                    # if names match
                    if name_match(exitee_name, entrant_name):
                        # add match to log for visual inspection
                        cross_prof_match_log.append([exitee_name, exit_year, sending_profession, '',
                                                     entrant_name, entry_year, entry_profession])

                        # increment appropriate cell in the transition dict/table
                        transfers_dict[exit_year][sending_profession][entry_profession] += 1

    # write the match list log to disk for visual inspection
    log_out_path = out_dir + 'interprofessional_transitions_' + str(year_window) + '_year_window_match_list_log.csv'
    with open(log_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        writer.writerow(["EXITEE NAME", "EXIT YEAR", "EXIT PROFESSION", "",
                         "ENTRANT NAME", "ENTRY YEAR", "ENTRANT PROFESSION"])
        for match in sorted(cross_prof_match_log, key=operator.itemgetter(1)):  # sorted by exit year
            writer.writerow(match)

    # write the transition tables to disk
    table_out_path = out_dir + 'interprofessional_transitions_' + str(year_window) + '_year_window_matrix.csv'
    with open(table_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        for year, exit_professions in transfers_dict.items():
            profs = sorted(list(exit_professions))
            writer.writerow([year])
            writer.writerow([''] + profs)
            for p in profs:
                writer.writerow([p] + [exit_professions[p][profs[i]] for i in range(0, len(profs))])
            writer.writerow(['\n'])

    # TODO also deaggregate transition table by gender


def professions_yearspans_cohorts(multiprofessional_person_year_table, combined=False):
    """
    Given a multiprofessional year table, returns a dict of this form

    {'profession':
        {'start year': int, first observed year for profession
         'end year': int, last observed year for profesion
         ' entry': {year1: list of entry cohort names for year1, year1: list of entry cohort names for year1,...}
         'exit': {year1: list of entry cohort names for year1, year2: list of entry cohort names for year2,...}
         }
    }

    :param multiprofessional_person_year_table: a person-year table that covers multiple professions
    :param combined: bool, True if we're dealing with the table of combined professions
    :return: a dict of data on each profession
    """
    # sort the table by profession and by year
    prof_col_idx = helpers.get_header('all', 'combine').index('profesie')
    year_col_idx = helpers.get_header('all', 'combine').index('an')
    multiprofessional_person_year_table.sort(key=operator.itemgetter(prof_col_idx, year_col_idx))

    # make four separate subtables by profession
    professions = [[*prof] for key, prof in itertools.groupby(multiprofessional_person_year_table,
                                                              key=operator.itemgetter(prof_col_idx))]
    data_dict = {}
    for p in professions:
        prof_name = p[0][prof_col_idx]
        start_year, end_year = int(p[0][year_col_idx]), int(p[-1][year_col_idx])
        # NB: +1 to entry year to ignore left censor (when all enter),
        # and -1 to exit year to ignore right censor (when all leave)
        entry_cohorts = descriptives.cohort_name_lists(p, start_year + 1, end_year, p, entry=True, combined=combined)
        exit_cohorts = descriptives.cohort_name_lists(p, start_year, end_year - 1, p, entry=False, combined=combined)

        data_dict.update({prof_name: {'start year': start_year, 'end year': end_year,
                                      'entry': entry_cohorts, 'exit': exit_cohorts}})
    return data_dict


def name_match(fullname_1, fullname_2):
    """
    Compares two full names and matches if certain match rules (described in comments) are met. The order in which the
    fullnames are introduced as parameters matters -- the first fullname is, in a sense, the "primary", the "anchor"

    :param fullname_1: str, full name of the form "SURNAMES | GIVEN NAMES"
    :param fullname_2: str, full name of the form "SURNAMES | GIVEN NAMES"
    :return: bool, True if match False otherwise
    """

    # extract surnames and given names from each full name
    sns_1, gns_1 = set(fullname_1.split(' | ')[0].split(' ')), set(fullname_1.split(' | ')[1].split(' '))
    sns_2, gns_2 = set(fullname_2.split(' | ')[0].split(' ')), set(fullname_2.split(' | ')[1].split(' '))

    # if one name has at least four components and the other has at least three components,
    # OR surname_1 contain "POPESCU", which is the single most common Romanian surname
    if (len(sns_1) + len(gns_1) > 3 and len(sns_2) + len(gns_2) > 2) \
            or \
            ("POPESCU" in sns_1 and len(sns_1) + len(gns_1) > 2):

        # the match needs to be at least 2-1 i.e. two surnames and one given name,
        # or two given names and one surname
        if (len(sns_1 & sns_2) > 0 and len(gns_1 & gns_2) > 1) \
                or \
                (len(sns_1 & sns_2) > 1 and len(gns_1 & gns_2) > 0):

            return True

        else:
            return False

    # otherwise match if the names (now 3 or less components long, not containing surname "POPESCU"
    # unless they're two-long) share at least one surname and one given name
    elif len(sns_1 & sns_2) > 0 \
            and len(gns_1 & gns_2) > 0:

        return True

    else:
        return False


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
    mobility_dict = descriptives.inter_unit_mobility(person_year_table, profession, unit_type)

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
