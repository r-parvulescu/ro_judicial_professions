"""
Functions that detect professional inheritance, spit out logs on detection, run robustness checks for said detection,
then write results in csv table to disk.
"""

import itertools
import Levenshtein
from operator import itemgetter
from helpers import helpers
import csv


# FUNCTIONS FOR DESCRIBING PROFESSIONAL INHERITANCE


def prof_inherit_table(out_dir, person_year_table, profession, year_window=1000, num_top_names=0,
                       multi_name_robustness=False):
    """
    Puts the profession inheritance dict in a table, adding some pecentages and sums. Output table has header
    "YEAR", "MALE ENTRIES", "FEMALE ENTRIES", "TOTAL ENTRIES", "MALE INHERITANCE COUNT", "FEMALE INHERITANCE COUNT",
    "TOTAL INHERITANCE COUNT", "MALE INHERITANCE PERCENT", "FEMALE INHERITANCE PERCENT", "TOTAL INHERITANCE PERCENT"

    :param out_dir: directory where the inheritance table will live
    :param person_year_table: a table of person years as a list of lists
    :param year_window: int, how far back you want to look for inheritance; e.g. year_window == 4, we look four years
                        back, so if in 2004, we look back to 2000 (inclusive); Default is 1000, i.e. look at all years
    :param num_top_names: int, the number of top most frequent surnames that we consider the set of "common" surnames,
                          e.g. if num_top_names == 10, the ten surnames with the most associated people are considered
                          the "most common" surnames; Default is zero, i.e. no names are common
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param multi_name_robustness: bool, True if we're running the multi-name robustness check
    :return: None
    """

    # get the inheritance dict
    inheritance_dict = profession_inheritance(out_dir, person_year_table, profession, year_window, num_top_names,
                                              multi_name_robustness=multi_name_robustness)
    sum_male_entries, sum_female_entries = 0, 0
    sum_male_inherit, sum_female_inherit = 0, 0

    if multi_name_robustness:
        table_out_path = out_dir + '/' + profession + '_MN_ROBUST' + '_exclude_surnames_above_rank_' \
                         + str(num_top_names) + '_inheritance_table.csv'
    else:
        table_out_path = out_dir + '/' + profession + '_exclude_surnames_above_rank_' + str(num_top_names) \
                         + '_inheritance_table.csv'

    with open(table_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        writer.writerow([profession.upper()])
        writer.writerow(["YEAR", "MALE ENTRIES", "FEMALE ENTRIES", "TOTAL ENTRIES", "MALE INHERITANCE COUNT",
                         "FEMALE INHERITANCE COUNT", "TOTAL INHERITANCE COUNT", "MALE INHERITANCE PERCENT",
                         "FEMALE INHERITANCE PERCENT", "TOTAL INHERITANCE PERCENT"])

        # for each year in the inheritance dict
        for year, counts in inheritance_dict.items():
            # increment counters
            sum_male_entries += counts["male entrants"]
            sum_female_entries += counts["female entrants"]
            sum_male_inherit += counts["male inherit"]
            sum_female_inherit += counts["female inherit"]

            # get sums and percentages
            total_entries = counts["female entrants"] + counts["male entrants"]
            total_inherit = counts["female inherit"] + counts["male inherit"]
            female_inherit_percent = helpers.percent(counts["female inherit"], counts["female entrants"])
            male_inherit_percent = helpers.percent(counts["male inherit"], counts["male entrants"])
            total_inherit_percent = helpers.percent(total_inherit, total_entries)

            writer.writerow([year, counts["male entrants"], counts["female entrants"], total_entries,
                             counts["male inherit"], counts["female inherit"], total_inherit,
                             male_inherit_percent, female_inherit_percent, total_inherit_percent])

        global_percent_male_inherit = helpers.percent(sum_male_inherit, sum_male_entries)
        global_percent_female_inherit = helpers.percent(sum_female_inherit, sum_female_entries)
        global_percent_total_inherit = helpers.percent(sum_male_inherit + sum_female_inherit,
                                                       sum_male_entries + sum_female_entries)

        writer.writerow(["GLOBAL", sum_male_entries, sum_female_entries, sum_male_entries + sum_female_entries,
                         sum_male_inherit, sum_female_inherit, sum_male_inherit + sum_female_inherit,
                         global_percent_male_inherit, global_percent_female_inherit, global_percent_total_inherit])


def profession_inheritance(out_dir, person_year_table, profession, year_window=1000, num_top_names=0,
                           multi_name_robustness=False):
    """
    Finds people in each entry cohort who were brought into the profession by kin.

    The assumption is that if one of your surnames matches the surname of someone who was in the profession before you
    AND who was, at any point, the same geographic area as you are when enter the profession, then you two are
    kin. More strict match rules for common surnames and the city of Bucharest are discussed in the comments of the
    relevant match criteria.

    NB: because we consider overlap with ANY surnames (to catch people who add surnames, which is especially
    the case for married women) we make bags of all DISTINCT surnames, so a compound surname like "SMITH ROBSON"
    would become two surnames, "SMITH" and "ROBSON".

    NB: "geographic area" is defined as appellate court jurisdiction/chamber/cameră for notaries and
    executori, and county/tribunal area for judges and prosecutors. I choose these geographic units on the grounds that
        a) they overlap with the areas in which people have sufficient "pull" within the professions for help place
           their kin next to them
        b) proportional to the profession's size and territorial structure, these units are small enough that it is
           reasonable to expect that not too many of the same surnames would co-appear in that area by chance

    NB: this function is meant to roughly identify kinship and err on the side of inclusion. It assumes that each
    match is then human-checked to weed out false positives, e.g. common surnames that coincidentally overlap.

    :param out_dir: directory where the log of kin matches will live
    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param year_window: int, how many years back we look for matches, e.g. "6" means we look for matches in six years
                        prior to your joining the profession; default is "1000", i.e. look back to beginning of data
    :param num_top_names: int, number of top surnames (out of entire set of surnames) that we're going to say are
                             "the most common surnames"; Default is zero, i.e. no names are common
    :param multi_name_robustness: bool, True if we're running the multi-name robustness check
    :return: a dict with key = year and val = list of cohort members who share a surname with a more senior professional
    """

    # get column indexes that we'll need
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    given_name_col_idx = helpers.get_header(profession, 'preprocess').index('prenume')
    gender_col_idx = helpers.get_header(profession, 'preprocess').index('sex')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    if profession in {'notaries', 'executori'}:
        area_col_idx = helpers.get_header(profession, 'preprocess').index('camera')
    else:  # profession in {'prosecutors', 'judges'}
        area_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')

    # get set of common surnames across the entire person-year table
    common_surnames = top_surnames(person_year_table, num_top_names, profession)

    # get year range
    person_year_table.sort(key=itemgetter(year_col_idx))  # sort by year
    start_year, end_year = int(person_year_table[0][year_col_idx]), int(person_year_table[-1][year_col_idx])

    # group person-year table by year, make yearly subtables value in dict, key is year
    tables_by_year_dict = {int(pers_years[0][year_col_idx]): pers_years
                           for key, [*pers_years] in itertools.groupby(person_year_table, key=itemgetter(year_col_idx))}

    # intialise dict of counters for each year's entry cohort -- main counters of interest are "male inherit" and
    # "female inherit", indicating how many people of each gender inherited their professions
    inheritance_dict = {year: {"male entrants": 0, "female entrants": 0, "male inherit": 0, "female inherit": 0}
                        for year in range(start_year + 1, end_year + 1)}  # can't see inheritance for first cohort

    # initialise a log of kin matches which we can inspect for hiccups
    kin_match_log = []

    # get full names for each yearly entry cohort
    yearly_entry_cohorts_full_names = helpers.cohort_name_lists(person_year_table, start_year, end_year, profession)

    # make dict where keys are person-ids and values are lists of chambers in which person has served
    pids_chamb_dict = {py[pid_col_idx]: set() for py in person_year_table}  # initialise dict
    [pids_chamb_dict[py[pid_col_idx]].add(py[area_col_idx]) for py in person_year_table]  # fill it

    # starting with the second available year
    for current_year, current_person_years in tables_by_year_dict.items():
        if current_year != min(list(tables_by_year_dict)):

            # get all the people from the previous years
            people_already_here = people_in_prior_years(current_year, start_year,
                                                        person_year_table, year_window, profession)

            # get this year's list of names of new recruits, i.e. fresh entrants
            recruits = yearly_entry_cohorts_full_names[current_year]

            # iterate through the current person years
            for rec in current_person_years:
                rec_full_name = rec[surname_col_idx] + ' | ' + rec[given_name_col_idx]  # recruit's full name
                rec_gend = rec[gender_col_idx]  # recruit's gender

                # if that person is a new recruit;
                # NB: full names in 'recruits' are in format 'SURNAMES | GIVEN NAMES'
                if rec_full_name in recruits:

                    # increment entry cohort counters
                    if rec_gend == 'f':
                        inheritance_dict[current_year]['female entrants'] += 1
                    if rec_gend == 'm':
                        inheritance_dict[current_year]['male entrants'] += 1

                    # compare recruit with everyone already here
                    for person_already in people_already_here:

                        # if recruit has a kin match with someone already here
                        if kin_match(rec, person_already, pids_chamb_dict, common_surnames, profession,
                                     multi_name_robustness=multi_name_robustness):

                            # if match is NOT in match log, put in and increment counters
                            # this condition avoids one recruit matching two people in the same area, which
                            # happens, especially with families of professionals
                            if True not in [True for match in kin_match_log if match[0] == rec_full_name]:

                                # save that kin match into a log file
                                update_kin_match_log(kin_match_log, rec, person_already, rec_full_name, current_year,
                                                     profession)

                                # and increment inheritance values
                                if rec_gend == 'f':
                                    inheritance_dict[current_year]["female inherit"] += 1
                                if rec_gend == 'm':
                                    inheritance_dict[current_year]["male inherit"] += 1

    # write the match log to disk
    log_out_path = ''.join([out_dir + profession, '_kin_matches_', str(year_window), '_year_window_',
                            str(num_top_names), '_match_list_log.csv'])
    with open(log_out_path, 'w') as out_path:
        writer = csv.writer(out_path)
        writer.writerow(["ENTRANT FULL NAME", "ENTRY YEAR", "ENTRY CHAMBER", "ENTRY TOWN", "",
                         "KIN FULL NAME", "KIN YEAR", "KIN CHAMBER", "KIN TOWN"])
        for match in sorted(kin_match_log, key=itemgetter(1)):  # sorted by entry year of recruit
            writer.writerow(match)

    # return the entries count dict
    return inheritance_dict


def top_surnames(person_year_table, top_size, profession):
    """
    Return a set of surnames that are at among the N most frequent, where top_size = N.
    e.g. if top_size = 3, we return surnames that are the most frequent in the population (e.g. "SMITH"),
    the second most-frequent, and the third most frequent. If there are multiple names tied for a certain frequency
    (e.g. SMITH and JONES both equally frequent on number one) then it returns all these (tied) names.

    :param person_year_table: a table of person-years, as a list of lists
    :param top_size: int, number of top names we want to return
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a set of top-ranked surnames
    """

    # let us know what profession we're on
    print(profession.upper())
    print('  SURNAME FREQUENCIES')

    # make dict of surnames
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    surnames = {}
    for person_year in person_year_table:
        for sn in person_year[surname_col_idx].split():
            surnames.update({sn: 0})

    # count the frequency of each surname; each new person that has that name adds one
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    persons = [person for key, [*person] in itertools.groupby(sorted(person_year_table, key=itemgetter(pid_col_idx)),
                                                              key=itemgetter(pid_col_idx))]
    for pers in persons:
        p_sns = pers[0][surname_col_idx].split()  # all person-years have same surnames, just use first year
        for sn in p_sns:
            surnames[sn] += 1

    # now make a new dict where keys are frequencies and values are lists of name that have those frequencies
    max_freq = max(list(surnames.values()))
    freq_dict = {i: [] for i in range(1, max_freq + 1)}  # initialise the dict
    [freq_dict[freq].append(sn) for sn, freq in surnames.items()]  # fill it
    freq_dict = {k: v for k, v in freq_dict.items() if v}  # throw out frequencies with no associated names

    # return a set of the top N names (as defined by top_size), and print what the top N are, so we can judge visually
    top_freqs = sorted(list(freq_dict))[-top_size:]
    top_sns = set()
    for i in top_freqs:
        print('    freq: ' + str(i) + ' ; surnames: ', freq_dict[i])
        for sn in freq_dict[i]:
            top_sns.add(sn)
    # if top size is zero, defined as "there are no top names"
    return top_sns if top_size != 0 else []


def people_in_prior_years(current_year, first_year, person_year_table, year_window, profession):
    """
    Make a list of all people (NOT person years) that appear in the year window prior to the current year.
    The list contains the LAST person-year that we see for that person within the time window
    e.g. if they left three years before the current year, we see their info for three years ago
    if they haven't left yet, we see their info for last year

    NB this matches based on the other person's last location, which is a simplifying heuristic

    :param current_year: int, the current year
    :param first_year: int, first year in the whole person-period table
    :param person_year_table: a table of person years, as a list of lists
    :param year_window: int, how far back we want to look; e.g. if year_window = 3 and current_year = 2008, the
                        time window in which we look is 2005 to 2008.
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a list person years, one per person
    """

    # get column indexes
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')

    # set the window in which we look or names
    min_year = max(current_year - year_window, first_year)  # prevents us from going under bounds
    window = list(range(min_year, current_year))

    # get all the person years before current year
    pys_in_window = [py for py in person_year_table if int(py[year_col_idx]) in window]

    # sort by person-ID and year, groupby person-ID
    pys_in_window.sort(key=itemgetter(pid_col_idx, year_col_idx))
    persons = [person for key, [*person] in itertools.groupby(pys_in_window, key=itemgetter(pid_col_idx))]
    # return a list with last observation of each person (where each person is list of person years with a common PID)
    return [pys_by_pers[-1] for pys_by_pers in persons]


def kin_match(recruit_data, old_pers_data, pids_chamber_dict, common_surnames, profession, multi_name_robustness=False):
    """
    Applies the kinship matching rules, returns True if there's a match.

    The rule is: if the recruit shares at least one surname with the older profession member AND their geographic areas
    match, then they're considered kin. The exceptions are:

        - if one of the surnames in the most common names, then at least TWO surnames need to match
          FOR NOTARIES & EXECUTORI ONLY
        - if the town is Bucharest then the match has to be not only on chamber but also on town/localitate;
          NB: this puts in an asymmetry where recuits from Bucharest CHAMBER can match BUCHAREST town, but recruits
              from BUCHAREST town must match ONLY Bucharest town (not the wider chamber); this is intentional, to
              allow for people from Bucharest town placing their kin in the wider chamber, but not vice verse, since
              it's harder for peripherals to get a foothold downtown than the other way around
          FOR EXECUTORI ONLY
         - if surnames match AND the your office infos differ by at most three Levenshtein distance then we ignore
           other geographic considerations and match you as kin

    NB: chamber ("camera") indicates the appellate court jurisdiction in which the professional operates. This is also
    the lowest level territorial, professional organisation for notaries and executori.

    FOR NOTARIES AND EXECUTORI ONLY
    NB: the most recent chamber of the person already in the profession can match ANY ONE of the chambers in the career
        of the recruit. This accounts for the pattern that inheritors sometimes start in a different chamber (where
        there's an open spot) then move in the town of their kin as soon as possible.
    NB: the above doesn't hold for prosecutors and judges because they move around a lot more; for magistrates their
        entry location needs to match the potential kin's current location. This avoids false positives.

    :param recruit_data: a list of data values (i.e. a row) for a new recruit;
                         data in order of preprocessed headers, see helpers.helpers.get_header under 'preprocess'
    :param old_pers_data: a list of data values (i.e a row) for a person that was there before the new recruit
                         data in order of preprocessed headers, see helpers.helpers.get_header under 'preprocess'
    :param pids_chamber_dict: dict where keys are unique person-IDs and values are lists of the chambers that person
                              has been in
    :param common_surnames: set of strings, of most common surnames
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param multi_name_robustness: bool, True if we're running the multi-name robustness check
    :return: bool, True if there's a match, false otherwise
    """

    # get column indexes
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    if profession in {'notaries', 'executori'}:
        area_col_idx = helpers.get_header(profession, 'preprocess').index('camera')
    else:  # profession in {'prosecutors', 'judges'}
        area_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')

    # get data; NB, surnames turned to bags, which automatically deduplicates surnames, e.g. STAN STAN --> STAN
    rec_pid, rec_sns = recruit_data[pid_col_idx], set(recruit_data[surname_col_idx].split(' '))
    rec_entry_area = recruit_data[area_col_idx]
    old_pers_sns, old_pers_area = set(old_pers_data[surname_col_idx].split(' ')), old_pers_data[area_col_idx]

    # initiate set of matches
    matches = set()

    # one robustness check is to exclude all recruits with multiple surnames, which in practice is mostly women.
    # This is to make sure that trends are not driven by the simple fact of multiple surnames.
    if multi_name_robustness:
        if len(recruit_data[surname_col_idx].split()) > 1:
            return False

    # for each surname
    for sn in rec_sns:

        # EXECUTORI ONLY: if match on surnames and on offices (bar typo), then this trumps geography
        # NB: only executori have office data
        if profession == 'executori':
            sediu_col_idx = helpers.get_header(profession, 'preprocess').index('sediul')
            rec_sediu, old_pers_sediu = recruit_data[sediu_col_idx], old_pers_data[sediu_col_idx]
            if rec_sediu != '-88':  # they need some office info, not just empties
                if len(rec_sns & old_pers_sns) > 0 and Levenshtein.distance(rec_sediu, old_pers_sediu) <= 3:
                    matches.add(True)

        # EXECUTORI AND NOTARIES
        if profession in {'executori', 'notaries'}:
            # if other person's current chamber in recruit's history
            if old_pers_area in pids_chamber_dict[rec_pid]:
                # if the surname is not among the most common
                if sn not in common_surnames:
                    # if there's at least one shared surname
                    if len(rec_sns & old_pers_sns) > 0:

                        town_col_idx = helpers.get_header(profession, 'preprocess').index('localitatea')
                        rec_town, old_pers_town = recruit_data[town_col_idx], old_pers_data[town_col_idx]

                        # if town is NOT Bucharest
                        if rec_town != "BUCUREŞTI":
                            matches.add(True)
                        else:  # recruit's town is Bucharest, old person also needs to currently be in Bucharest
                            if old_pers_town == "BUCUREŞTI":
                                matches.add(True)

                else:  # if the surname is common, need match on at least two surnames
                    if len(rec_sns & old_pers_sns) > 1:
                        matches.add(True)

        else:  # JUDGES AND PROSECUTORS
            # if recruit's first area and other person's current area are the same
            if old_pers_area == rec_entry_area:
                # if the surname is not among the most common
                if sn not in common_surnames:
                    # if there's at least one name in common, match
                    if len(rec_sns & old_pers_sns) > 0:
                        matches.add(True)

                else:  # if the surname is common, need match on at least two surnames
                    if len(rec_sns & old_pers_sns) > 1:
                        matches.add(True)

    # if there's at least one match, return True
    return True if True in matches else False


def update_kin_match_log(kin_match_log, py, person_already, full_name, current_year, profession):
    """
    Updates the log of kin matches, which we keep for later visual inspection.

    The format for the log table should be:
      - left columns: the recruit's full name, year, chamber, and town
      -right columns: same info for the person recruit is kin matched with

    :param kin_match_log: list used to keep track of kin matches, for later visual inspection
    :param py: person-year, list of data fields (order given in helpers.get_headers,
            for "preprocess" and particular profession)
    :param person_already: person-year row of person who was in the profession before the recruit
    :param full_name: recruit's full name
    :param current_year: year in which the recruit joined
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    # get column indexes
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    given_name_col_idx = helpers.get_header(profession, 'preprocess').index('prenume')

    if profession in {'notaries', 'executori'}:
        area_col_idx = helpers.get_header(profession, 'preprocess').index('camera')
        sub_area = helpers.get_header(profession, 'preprocess').index('localitatea')  # sub_area = town
    else:  # profession in {'prosecutors', 'judges'}
        area_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')
        sub_area = helpers.get_header(profession, 'preprocess').index('jud cod')  # sub_area = court/parquet

    rec_area, rec_sub_area = py[area_col_idx], py[sub_area]

    p_alrdy_fn = person_already[surname_col_idx] + ' | ' + person_already[
        given_name_col_idx]
    p_alrdy_chamb, p_alrdy_town = person_already[area_col_idx], person_already[
        sub_area]
    p_alrdy_year = person_already[year_col_idx]

    kin_match_log.append([full_name, current_year, rec_area, rec_sub_area] + [''] +
                         [p_alrdy_fn, p_alrdy_year, p_alrdy_chamb, p_alrdy_town])
