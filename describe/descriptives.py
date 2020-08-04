"""
Functions for calculating counts of different mobility events, across different units.
"""

import csv
from operator import itemgetter
import itertools
from copy import deepcopy
import natsort
import statistics
import Levenshtein
from helpers import helpers
from preprocess.gender import gender


# FUNCTIONS FOR COUNTS FOR WHOLE SAMPLE AS WELL AS ENTRY AND EXIT COHORTS #


def pop_cohort_counts(person_year_table, start_year, end_year, profession, cohorts=True, unit_type=None, entry=True):
    """
    For each year in the range from start_year to end_year, return a dict of counts of women, men, don't knows,
    cohort size, and percent women for that cohort.

    If units are provided (e.g. geographic areas) it calculates the metrics per each unit, so e.g. cohort size per
    year, for each geographic area.

    NB: there can be entry cohorts (those that joined the profession in year X) and exit cohorts (those that left
    the profession in year Y).

    :param person_year_table: a table of person-years, as a list of lists
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param cohorts: bool, True if we want counts for entry and exit cohorts (e.g. all who entered the profession in 
                          2012), False if we want counts for whole population (e.g. all professionals in 2012)
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :param entry: bool, True if we're getting data for entry cohorts, False if for exit cohorts
    :return: a dict of years, where each value is a dict with gender metrics
    """

    pop_counts = {'grand_total': metrics_dict(start_year, end_year)}
    units = None

    # if we have units, initialise a dict of years for each unit
    if unit_type:
        unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)
        units = {person_year[unit_col_idx] for person_year in person_year_table}
        pop_counts.update({unit: metrics_dict(start_year, end_year) for unit in natsort.natsorted(list(units))})

    # make an identical dict for cohorts
    cohort_counts = deepcopy(pop_counts)

    # get total counts
    for person_year in person_year_table:
        update_size_gender(pop_counts, person_year, start_year, end_year, profession, units, unit_type=unit_type)
    percent_female(pop_counts, units, unit_type=unit_type)

    # then get cohort counts

    # group person-years by person
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(1))]  # row[1] == PID
    for person in people:
        # if describing entry cohorts we want the first person-year, else the last person-year (i.e. exit cohorts)
        edge_person_year = person[0] if entry else person[-1]
        update_size_gender(cohort_counts, edge_person_year, start_year, end_year, profession,
                           units, unit_type=unit_type)
    percent_female(cohort_counts, units, unit_type=unit_type)
    update_cohort_of_population(cohort_counts, pop_counts, entry=entry, units=units)

    return cohort_counts if cohorts else pop_counts


def metrics_dict(start_year, end_year):
    """
    Make an empty dict where keys are years and values are dicts of metrics, most related to gender.
    :param start_year: int, year we start looking
    :param end_year: int, year we stop looking at
    :return: dict
    """
    m_dict = {year: {'f': 0, 'm': 0, 'dk': 0, 'total_size': 0, 'chrt_prcnt_of_pop': 0, 'percent_female': 0}
              for year in range(start_year, end_year + 1)}
    return m_dict


def update_size_gender(count_dict, row, start_year, end_year, profession, units, unit_type=None):
    """
    Counts the number of people per year; if unit is given, gives the count of person per year, per unit

    :param count_dict: a dictionary of counts -- for format, see function metrics_dict
    :param row: a person-year as a list
    :param start_year: int, year we start looking at
    :param end_year: int, year we stop looking
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param units: a set of unit categories, each a string
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :return: None
    """
    # if describing entry cohorts we want the first person-year, else the last person-year (i.e. exit cohorts)
    dict_row = helpers.row_to_dict(row, profession, 'preprocess')
    gendr = dict_row['sex']
    year = int(dict_row['an'])
    unit = dict_row[unit_type] if units else None

    # stay within bounds
    if start_year <= year <= end_year:

        # increment cohort sizes and cohort gender counters
        count_dict['grand_total'][year]['total_size'] += 1
        count_dict['grand_total'][year][gendr] += 1
        if unit_type:
            count_dict[unit][year]['total_size'] += 1
            count_dict[unit][year][gendr] += 1


def percent_female(count_dict, units, unit_type=None):
    """
    Update the percent_female value in the count_dict

    :param count_dict: a dictionary of counts -- for format, see function metrics_dict
    :param units: a set of unit categories, each a string
    :param unit_type: None, or string; if string, type of the unit as it appears in header of person_year_table
                      (e.g. "camera")
    :return: None
    """
    # now get percent female per cohort, and per unit if applicable
    for year in count_dict['grand_total']:
        if count_dict['grand_total'][year]['total_size'] != 0:
            count_dict['grand_total'][year]['percent_female'] = helpers.percent(
                count_dict['grand_total'][year]['f'], count_dict['grand_total'][year]['total_size'])
        if unit_type:
            for u in units:
                if count_dict[u][year]['total_size'] != 0:
                    count_dict[u][year]['percent_female'] = helpers.percent(
                        count_dict[u][year]['f'], count_dict[u][year]['total_size'])


def update_cohort_of_population(cohorts_dict, population_dict, entry=True, units=None):
    """
    Updates the value that shows how big a yearly cohort is relative to all the people in that year.

    NB: for entry cohorts, we compare cohort sizes to all people in the PREVIOUS year. For exit cohorts, we
        compare cohort sizes to all people in the CURRENT year.

    :param cohorts_dict: a dictionary of cohorts, where each key is a year and values are metrics for that cohort
    :param population_dict: a dictionary for the whole population, where each key is a year, and values are metrics
                            for all population members for that year
    :param entry: bool, True if we're getting data for entry cohorts, False if for exit cohorts
    :param units: a set of unique units of a certain type, e.g. towns
    :return: None
    """
    for year in cohorts_dict['grand_total']:

        # for entry cohorts, compare with preceding year, unless it's the first year
        if entry and year - 1 in cohorts_dict:
            yearly_pop = population_dict['grand_total'][year - 1]['total_size']
        else:
            yearly_pop = population_dict['grand_total'][year]['total_size']

        if cohorts_dict['grand_total'][year]['total_size'] != 0:
            cohorts_dict['grand_total'][year]['chrt_prcnt_of_pop'] = helpers.percent(
                cohorts_dict['grand_total'][year]['total_size'], yearly_pop)

        if units:
            for u in units:
                # for entry cohorts, compare with preceding year, unless it's the first year
                if entry and year - 1 in cohorts_dict:
                    yearly_unit_pop = population_dict[u][year - 1]['total_size']
                else:
                    yearly_unit_pop = population_dict[u][year]['total_size']

                if cohorts_dict[u][year]['total_size'] != 0:
                    cohorts_dict[u][year]['chrt_prcnt_of_pop'] = helpers.percent(cohorts_dict[u][year]['total_size'],
                                                                                 yearly_unit_pop)


# FUNCTIONS FOR DESCRIBING PROFESSIONAL INHERITANCE

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
    yearly_entry_cohorts_full_names = cohort_name_lists(person_year_table, start_year, end_year, profession)

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
    log_out_path = out_dir + profession + '_kin_matches_' + str(year_window) + '_year_window_' \
                   + 'exclude_ranks_top_names_' + str(num_top_names) + '_match_list_log.csv'
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

    pid_col_idx = helpers.get_header(profession, stage).index('cod persoană')
    year_col_idx = helpers.get_header(profession, stage).index('an')
    surname_col_idx = helpers.get_header(profession, stage).index('nume')
    given_name_col_idx = helpers.get_header(profession, stage).index('prenume')

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

    # TODO need to put in a robustness check for prosecutors that excludes DIICOT and DNA

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


# FUNCTIONS FOR DESCRIBING HIERARCHICAL MOBILITY

def hierarchical_mobility(person_year_table, profession):
    """
    Finds how many people, each year, moved up, down, or across (i.e. between geographic units in the same level) from
    their level in the judicial hierarchy, deaggregating mobility by gender. The levels are
    {1: low court, 2: tribunal, 3: appellate court, 4: high court}.  The output dict has the following format:

    {"year": {
        "level1" : {
            "up": {"m": int, "f": int, "dk": int, "total": int, "percent female": int},
             "down": {"m": int, "f": int, "dk": int, "total": int, "percent female": int},
             "across": {"m": int, "f": int, "dk": int, "total": int, "percent female": int}
             },
        "level2": {
            "up": {"m": int, "f": int, "dk": int, "total": int, "percent female": int},
            ...
            },
        ...
        },
    "year2"
    ...
    }

    NB: "m" = male, "f" = "female", "dk" = "don't know".

    NB: there is no "down" for low courts, or "up" and "across" for the high court.

    NB: data on retirements ("out") come via exit cohorts from the function "pop_cohort_counts".

    NB: only judges and prosecutors have a hierarchical system -- this function is not sensical for notaries, executori,
        and lawyers.

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a dict of mobility info
    """

    # get column indexes
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    gender_col_idx = helpers.get_header(profession, 'preprocess').index('sex')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    level_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')
    jud_col_idx = helpers.get_header(profession, 'preprocess').index('jud cod')
    trib_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')
    ca_col_idx = helpers.get_header(profession, 'preprocess').index('ca cod')

    # get the year range and set the mobility types
    years = list(sorted({py[year_col_idx] for py in person_year_table}))
    mobility_types = ["across", "down", "up"]

    # initialise the mobility dict
    mob_dict = {year: {lvl: {mob_type: {"m": 0, "f": 0, "dk": 0, "total": 0, "percent female": 0}
                             for mob_type in mobility_types} for lvl in range(1, 5)} for year in years}

    # group the person-year table by unique person IDs, i.e. by people
    person_year_table.sort(key=itemgetter(pid_col_idx, year_col_idx))  # sort by person ID and year
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # fill in the mobility dict
    for pers in people:
        gend = pers[0][gender_col_idx]
        for idx, pers_year in enumerate(pers):
            # by convention we say there's mobility in this year if next year's location is different
            if idx < len(pers) - 1:
                year, level = pers_year[year_col_idx], int(pers_year[level_col_idx])
                if level < int(pers[idx + 1][level_col_idx]):
                    mob_dict[year][level]["up"][gend] += 1
                elif level > int(pers[idx + 1][level_col_idx]):
                    mob_dict[year][level]["down"][gend] += 1
                else:
                    # need to compare this year and next year's unit to see if they moved laterally
                    # each unit is uniquely identified by it's three-level hierarchical code
                    current_unit = '|'.join([pers_year[jud_col_idx], pers_year[trib_col_idx], pers_year[ca_col_idx]])
                    next_unit = '|'.join(
                        [pers[idx + 1][jud_col_idx], pers[idx + 1][trib_col_idx], pers[idx + 1][ca_col_idx]])
                    if current_unit != next_unit:
                        mob_dict[year][level]["across"][gend] += 1

    # update the aggregate values
    for year, levels in mob_dict.items():
        for lvl, mobility_type in levels.items():
            for mob in mobility_type:
                mob_dict[year][lvl][mob]["total"] = sum([mob_dict[year][lvl][mob]["m"], mob_dict[year][lvl][mob]["f"],
                                                         mob_dict[year][lvl][mob]["dk"]])
                mob_dict[year][lvl][mob]["percent female"] = helpers.percent(mob_dict[year][lvl][mob]["f"],
                                                                             mob_dict[year][lvl][mob]["total"])

    return mob_dict


# FUNCTIONS FOR MOBILITY BETWEEN GEOGRAPHIC UNITS #

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


# FUNCTIONS FOR INTER-PROFESSIONAL TRANSFER DESCRIPTION #

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
        entry_cohorts = cohort_name_lists(p, start_year + 1, end_year, p, entry=True, combined=combined)
        exit_cohorts = cohort_name_lists(p, start_year, end_year - 1, p, entry=False, combined=combined)

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


# TODO still getting weird results from the career climbing/star functions, there shouldn't be observations at all for
#  some years...

# TODO do proper docstrings for career climbing/star functions

def career_stars(person_year_table, profession, use_cohorts, first_x_years):
    """

    We want two pieces of information:

    a) of climbers, what percent of those that beat average climb time to appellate court also previously beat average
        climb time to tribunal? This helps us see how much second level star is predicted by first level star status
    b) per yearly cohort, total count and % female of everyone who beat the average climb time from low court to
        tribunal, conditional on them having climbed

    NB: these metrics are for all cohorts in the dataset, but the average climb time is derived from the cohorts in
        "use_cohorts". The assumption is that differences in average climb times across cohorts are not important.

    :param person_year_table:
    :param profession:
    :param use_cohorts:
    :param first_x_years:
    :return:
    """

    # get column indexes
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    gender_col_idx = helpers.get_header(profession, 'preprocess').index('sex')
    level_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort by unique person ID and year, then group by person-year
    person_year_table.sort(key=itemgetter(pid_col_idx, year_col_idx))
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # get average climb time to tribunal and appelate courts
    career_climbs = career_climbings(person_year_table, profession, use_cohorts, first_x_years)
    avg_to_trib = career_climbs['tribunal']['counts dict']['avrg yrs to promotion']
    avg_to_appellate = career_climbs['appellate']['counts dict']['avrg yrs to promotion']

    # initialise star cohort dict
    all_years = sorted(list({py[year_col_idx] for py in person_year_table}))
    steps = {'tribunal', 'appellate'}
    star_cohorts = {year: {step: {'m': 0, 'f': 0, 'dk': 0, 'total': 0, 'percent female': 0} for step in steps}
                    for year in all_years}

    total_to_appellate = 0  # counter of how many climbed to appellate level by normal route
    continuation_stars = 0  # counter of many appellate stars were also trib stars

    for person in people:
        entry_year = person[0][year_col_idx]
        gend = person[0][gender_col_idx]
        levels = {int(person_year[level_col_idx]) for person_year in person}  # the levels person's been in

        # if they've been in low courts and tribunals
        if len({1, 2} & levels) >= 2:

            time_to_trib = time_to_promotion(person, profession, 'tribunal', 1000)

            # if they respected minimum time before promotion to tribunal, i.e. not extra-professional imports
            # AND they got to tribunal faster than average
            if min_time_promotion('tribunal') <= time_to_trib < avg_to_trib:
                # increment the relevant tribunal star gender counter in the appropriate start year
                star_cohorts[entry_year]['tribunal'][gend] += 1

        # if they've been in low courts, tribunals, and appellate courts
        if len({1, 2, 3} & levels) >= 3:

            time_to_appellate = time_to_promotion(person, profession, 'appellate', 1000)
            time_to_tribunal = time_to_promotion(person, profession, 'tribunal', 1000)

            # if they respected minimum time before promotion to tribunal AND minimum to appellate
            if min_time_promotion('tribunal') <= time_to_tribunal and \
                    min_time_promotion('appellate') <= time_to_appellate:

                total_to_appellate += 1  # increment counter of all who reached appellate via normal path

                # if they climbed to appellate faster than average
                if time_to_appellate < avg_to_appellate:
                    star_cohorts[entry_year]['appellate'][gend] += 1

                # if they climbed to appellate court AND to tribunal faster than average
                if time_to_appellate < avg_to_appellate and time_to_tribunal < avg_to_trib:
                    continuation_stars += 1

    # get sums and percentages
    percent_continuation_stars = helpers.percent(continuation_stars, total_to_appellate)
    for year, levels in star_cohorts.items():
        for lvl, counts in levels.items():
            counts['total'] = counts['m'] + counts['f'] + counts['dk']
            counts['percent female'] = helpers.percent(counts['f'], counts['total'])

    # return trib_star_cohorts with percent_continuation_stars added
    star_cohorts.update({"percent continuation stars": percent_continuation_stars})
    return star_cohorts


def career_climbings(person_year_table, profession, use_cohorts, first_x_years):
    """
    Return a dict of metrics on career climbing, i.e. of moving up the judicial hierarchy.

    NB: these metrics are only for a subset of observations, namely those speciied by use_cohorts. The purpose of this
        feature is to help us avoid years with rotten data, while giving us a big enough time interval to catch
        movement up two levels

    We want two pieces of information:

    a) total counts and % female of those who stay in low courts, climb to tribunals, and climb to appellate courts
    b) average time it took to climb, whether to tribunal or appellate court, for those cohort members who climbed to
        those levels

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param use_cohorts: list of ints, each int represents a year for which you analyse entry cohorts, e.g. [2006, 2007]
    :param first_x_years: int, the number of years from start of career that we condsider, e.g. ten years since entry
    :return:
    """

    # get column indexes
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    gender_col_idx = helpers.get_header(profession, 'preprocess').index('sex')

    # sort by unique person ID and year, then group by person-year
    person_year_table.sort(key=itemgetter(pid_col_idx, year_col_idx))
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # initialise dict that breaks down careers by how high they climbed
    counts_dict = {'m': 0, 'f': 0, 'dk': 0, 'total': 0, 'percent female': 0, 'avrg yrs to promotion': 0}
    levels = ['low court', 'tribunal', 'appellate', 'high court']
    careers_by_levels = {lvl: {'career type table': [], 'counts dict': deepcopy(counts_dict)} for lvl in levels}
    fill_careers_by_levels_dict(people, profession, use_cohorts, careers_by_levels)

    # for each career type get basic descriptives
    for step, info in careers_by_levels.items():
        times_to_promotion = []
        for pers in info['career type table']:
            gend = pers[0][gender_col_idx]

            # see time it takes to climb hierarchy; use only first X years of career, to make comparable
            # careers of different total length
            t_to_promotion = time_to_promotion(pers, profession, step, first_x_years)

            # if person jumped seniority requirements (e.g. came from different legal profession), or has > ten years
            # (this is an error, since time_to_promotion should only keep first ten years), ignore

            if t_to_promotion == 'NA':  # catches low court people
                info['counts dict'][gend] += 1
            else:  # t_to_promotion != 'NA', i.e. everyone else
                if min_time_promotion(step) <= t_to_promotion < 11:
                    times_to_promotion.append(t_to_promotion)  # save time to promotion
                    info['counts dict'][gend] += 1

        info['counts dict']['total'] = info['counts dict']['f'] + info['counts dict']['m'] + info['counts dict']['dk']
        info['counts dict']['percent female'] = helpers.percent(info['counts dict']['f'], info['counts dict']['total'])
        info['counts dict']['avrg yrs to promotion'] = 'NA' if 'NA' in times_to_promotion or times_to_promotion == [] \
            else round(statistics.mean(times_to_promotion))

    return careers_by_levels


def fill_careers_by_levels_dict(people, profession, use_cohorts, career_types_dict):
    """
    Update a career types dict (form given in first part of function "career stars").

    :param people: a list of persons, where each "person" is a list of person years (each itself of list) that share
                   a unique person-level ID
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param use_cohorts: list of ints, each int represents a year for which you analyse entry cohorts, e.g. [2006, 2007]
    :param career_types_dict: a layered dict (form given in first part of function "career stars")
    :return: None
    """

    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    level_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    for person in people:
        entry_year = int(person[0][year_col_idx])  # get their entry year
        entry_level = int(person[0][level_col_idx])  # some people start higher because before they were e.g. lawyers
        levels = {int(person_year[level_col_idx]) for person_year in person}  # see what levels they've been in

        # keep only people from specified entry cohorts who started at first level, i.e. no career jumpers
        if entry_year in use_cohorts and entry_level == 1:
            if 4 in levels:
                career_types_dict['high court']['career type table'].append(person)
            elif 3 in levels:
                career_types_dict['appellate']['career type table'].append(person)
            elif 2 in levels:
                career_types_dict['tribunal']['career type table'].append(person)
            else:
                career_types_dict['low court']['career type table'].append(person)


def time_to_promotion(person, profession, level, first_x_years):
    """
    Given a career level, find how long (i.e. how many person years) it took to get there.
    
    :param person: a list of person years that share a unique person ID
    :param profession:
    :param level: string, 'tribunal', 'appellate', or 'high court', indicating position in judicial hierarchy
    :param first_x_years: int, how many years after start of career we consider, e.g. ten years after joing profession
    :return: t_to_promotion, int, how long (in years) it took to get promoted
    """

    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    level_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # see how long it takes them to get a promotion; compare only first X years of everyone's career
    t_to_promotion = 'NA'
    entry_year = int(person[0][year_col_idx])

    if level == 'tribunal':  # count how many years they were at low court
        t_to_promotion = len([pers_year for pers_year in person if int(pers_year[level_col_idx]) == 1
                              and int(pers_year[year_col_idx]) < entry_year + first_x_years])

    if level == 'appellate':  # count how many year they were at low court or tribunal, i.e. not at appellate
        t_to_promotion = len([pers_year for pers_year in person if (int(pers_year[level_col_idx]) == 1
                                                                    or int(pers_year[level_col_idx]) == 2)
                              and int(pers_year[year_col_idx]) < entry_year + first_x_years])

    if level == 'high court':  # count how many years they were at low court
        t_to_promotion = len([pers_year for pers_year in person if int(pers_year[level_col_idx]) != 4
                              and int(pers_year[year_col_idx]) < entry_year + first_x_years])

    return t_to_promotion


def min_time_promotion(hierarchical_level):
    """
    There are strict seniority rules for promotion in the magistracy. If a person spent less than 3 years before a
    tribunal promotion, less than 6 years before appellate court promotion, or less than 10 ten years before high court
    promotion, they must have come from another profession, as this lets you jump seniority requirements.

    :param hierarchical_level: string representing level in judicial hierarchy; must take values 'low court',
                               'tribunal', 'appellate', or 'high court'
    :return: int, minimum number of years at which one can get promoted
    """

    return {'low court': 0, 'tribunal': 3, 'appellate': 6, 'high court': 10}[hierarchical_level]
