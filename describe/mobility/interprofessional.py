"""
Functions for detecting who moved between professions, and then summing up that movement in a csv table.
"""

import itertools
import csv
from operator import itemgetter
from copy import deepcopy
from helpers import helpers
from preprocess.gender import gender


# FUNCTIONS FOR INTER-PROFESSIONAL TRANSFER DESCRIPTION #

def inter_profession_transfer_table(infile_path, out_dir, year_window):
    """
    Write to disk a table of yearly subtables, where each subtable is a matrix of inter-professional transfers
    for one year; cell values are "count total transfers (percent female of this count)".
    The output should look something like the below (diagonals are zero, always undefined).

    YEAR 1
                    PROFESSION 1  PROFESSION 2  PROFESSION 3
        PROFESSION 1     0 (0%)        3 (66%)       1 (100%)
        PROFESSION 2     6 (50%)       0 (0%)        2 (0%)
        PROFESSION 3     3 (33%)       4 (75%)       0 (0%)
        ...


    YEAR 2
                     PROFESSION 1  PROFESSION 2  PROFESSION 3
        PROFESSION 1      0 (0%)        3 (0%)        5 (20%)
        PROFESSION 2      10 (80%)      0 (0%)        3 (100%)
        PROFESSION 3      2 (100%)      5 (80%)       0 (0%)
        ...
    ...

    :param infile_path: str, path to where a person-year table that covers multiple professions lives
    :param out_dir: directory where the interprofessional transition table(s) will live
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
        multiprofs_py_table.sort(key=itemgetter(year_col_idx))

    # get the dict of inter-professional transfers
    transfers_dict = inter_professional_transfers(multiprofs_py_table, out_dir, year_window)

    # write the transition tables to disk
    table_out_path = out_dir + 'interprofessional_transitions_' + str(year_window) + '_year_window_matrix.csv'
    with open(table_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        for year, exit_professions in transfers_dict.items():
            profs = sorted(list(exit_professions))
            writer.writerow(['', year])
            writer.writerow(['', '', '', 'TO'])
            writer.writerow(['(percent women)', ''] + profs)
            for p in profs:
                frm = ['FROM'] if p == 'judges' else ['']
                writer.writerow(frm + [p] + [str(exit_professions[p][profs[i]]['total transfers']) +
                                             ' (' + str(exit_professions[p][profs[i]]['percent women transfers']) + '%)'
                                             for i in range(0, len(profs))])
            writer.writerow(['\n'])


def inter_professional_transfers(multiprofs_py_table, out_dir, year_window):
    """
    Finds possible name matches between people who retired in year X from profession A, and people who joined
    professions B, C... in the years from X to X+4, inclusive. In other words, if someone left a profession one year,
    see if in the next five years they joined any of the other professions.

    NB: need to choose carefully the start and end years since only for some years do we have overlap between
        different professions

    NB: this function assumes that each match will be human-checked afterwards. Consequently, it errs on the side
        of over-inclusion, i.e. prefers false positives.

    :param multiprofs_py_table: person-year table of all professions
    :param out_dir: directory where the log of interprofessional transition matches will live
    :param year_window: int, how many years after exit we look for interprofessional transition;
                        if year_window = 0, we want only professional transfers in the exit year
                        if year_window = 3, we want only professional transfers in the exit year and two
                            consecutive years, e.g. 2000-2002 (the years 2000, 2001, and 2003)
                        etc.
    :return: None
    """

    # load the gender dict, we'll need this later
    gender_dict = gender.get_gender_dict()

    # get start and end year of all observations
    year_col_idx = helpers.get_header('all', 'combine').index('an')
    start_year, end_year = int(multiprofs_py_table[0][year_col_idx]), int(multiprofs_py_table[-1][year_col_idx])

    # initialise a list/log of matches/putative cross-professional transfers, so we can eyeball for errors
    transfer_match_log = []

    # for each profession get the first and last observation years and the full names of yearly entry and exit cohorts
    professions_data = professions_yearspans_cohorts(multiprofs_py_table, combined=True)

    # make dict with level 1 key is year, level 2 key is sending profession, level 3 key is receiving profession;
    # level 4 dict holds counts: total count transfers from profession A to profession B in year X,
    # count women of those, percent women of those
    transfers_dict = {}
    measures = {'total transfers': 0, 'women transfers': 0, 'percent women transfers': 0}
    for exit_year in range(start_year, end_year):
        # the first-level key is the row/sender, the second-level key is the column/receiver
        professions_dict = {prof: {prof: deepcopy(measures) for prof in professions_data} for prof in professions_data}
        transfers_dict.update({exit_year: professions_dict})

    # for each profession
    for sending_profession in professions_data:

        # for each yearly exit cohort
        for exit_year, names in professions_data[sending_profession]['exit'].items():

            # get set of entrants to OTHER professions, from exit year to year + year_window; e.g. [2000-2002]
            other_profs_entrants = other_professions_entrants(sending_profession, professions_data,
                                                              exit_year, year_window)
            for exitee_name in names:

                # look for name match in set of entrants into other professions, in the specified time window
                for entrant in other_profs_entrants:
                    entrant_name, entry_year, entry_profession = entrant[0], entrant[1], entrant[2]

                    # if names match
                    if name_match(exitee_name, entrant_name):
                        # add match to log for visual inspection
                        transfer_match_log.append([exitee_name, exit_year, sending_profession, '',
                                                   entrant_name, entry_year, entry_profession])

                        # increment value of total counts in the transfer dict
                        transfers_dict[exit_year][sending_profession][entry_profession]['total transfers'] += 1

                        # check if exitee name is female, if yes increment appropriate count in transfer dict
                        exitee_given_names = exitee_name.split(' | ')[1]
                        if gender.get_gender(exitee_given_names, exitee_name, gender_dict) == 'f':
                            transfers_dict[exit_year][sending_profession][entry_profession]['women transfers'] += 1

            # for that year get percent female transfers
            for prof in professions_data:
                n = transfers_dict[exit_year][sending_profession][prof]['women transfers']
                d = transfers_dict[exit_year][sending_profession][prof]['total transfers']
                transfers_dict[exit_year][sending_profession][prof]['percent women transfers'] = helpers.percent(n, d)

    # write the match list log to disk for visual inspection
    log_out_path = out_dir + 'interprofessional_transitions_' + str(year_window) + '_year_window_match_list_log.csv'
    with open(log_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        writer.writerow(["EXITEE NAME", "EXIT YEAR", "EXIT PROFESSION", "",
                         "ENTRANT NAME", "ENTRY YEAR", "ENTRANT PROFESSION"])
        for match in sorted(transfer_match_log, key=itemgetter(1)):  # sorted by exit year
            writer.writerow(match)

    return transfers_dict


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
    multiprofessional_person_year_table.sort(key=itemgetter(prof_col_idx, year_col_idx))

    # make four separate subtables by profession
    professions = [[*prof] for key, prof in itertools.groupby(multiprofessional_person_year_table,
                                                              key=itemgetter(prof_col_idx))]
    data_dict = {}
    for p in professions:
        prof_name = p[0][prof_col_idx]
        start_year, end_year = int(p[0][year_col_idx]), int(p[-1][year_col_idx])
        # NB: +1 to entry year to ignore left censor (when all enter),
        # and -1 to exit year to ignore right censor (when all leave)
        entry_cohorts = helpers.cohort_name_lists(p, start_year + 1, end_year, p, entry=True, combined=combined)
        exit_cohorts = helpers.cohort_name_lists(p, start_year, end_year - 1, p, entry=False, combined=combined)

        data_dict.update({prof_name: {'start year': start_year, 'end year': end_year,
                                      'entry': entry_cohorts, 'exit': exit_cohorts}})
    return data_dict


def other_professions_entrants(sending_profession, professions_data, exit_year, year_window):
    """
    Return set of all people/names who joined every OTHER profession, on the range "year" to "year + year_window".

    :param sending_profession: str, the profession one exits from, i.e. that sends the person to another profession
    :param professions_data: dict of data on professions as generated by function "professions_yearspans_cohorts"
    :param exit_year: str or int, year for which we're looking at a particular exit cohort
    :param year_window: int, upper limit of window in which we're considering inter-professional moves,
                        e.g. if exit year == 2000 and year_window == 2 we look for transfers on the interval [2000,2002]
    :return: a set of entrants to other professions, where each element is a tuple of the form
            (entrant_name, entry_year, entry_prof))
    """

    # see what the other professions are
    other_professions = {prof for prof in professions_data if prof != sending_profession}

    other_profs_entrants = set()

    for entry_prof in other_professions:

        # last_year ensures that our year window doesn't go out of bounds
        last_year = min(int(exit_year) + year_window, professions_data[entry_prof]['end year'])

        for entry_year in range(int(exit_year), last_year + 1):
            # not all professions have the same year set
            if entry_year in professions_data[entry_prof]['entry']:

                for entrant_name in professions_data[entry_prof]['entry'][entry_year]:
                    other_profs_entrants.add((entrant_name, entry_year, entry_prof))

    return other_profs_entrants


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
