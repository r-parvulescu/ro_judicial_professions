import Levenshtein
import itertools
from operator import itemgetter
from helpers import helpers


def profession_inheritance(person_year_table, profession, year_window=1000):
    """
    Check if each person inherited their profession.

    The assumption is that if in the year that you enter the profession one of your surnames matches the surname of
    someone who was in the profession before you AND who was, at any point, in the same chamber (appellate court
    jurisdiction) as you are upon entry, then you two are kin. More strict match rules for common surnames and the city
    of Bucharest are discussed in the comments of the  relevant match criteria.

    NB: because we consider overlap with ANY surnames (to catch people who add surnames, which is especially
    the case for married women) we make bags of all DISTINCT surnames, so a compound surname like "SMITH ROBSON"
    would become two surnames, "SMITH" and "ROBSON".

    NB: this function is meant to roughly identify kinship and err on the side of inclusion. It assumes that each
    match is then human-checked to weed out false positives, e.g. common surnames that coincidentally overlap. That's
    why I make a match log, not with this function but with that in describe.descriptives.profession_inheritance. Look
    for kin-match log files under analysis/descriptives/inheritance.

    NB: year_window controls how far back in time from the recruit's we look for a match. So if person X enters the
    profession in 2015, and the year window is 5, we look for matches in the interval 2010-2014, inclusive.

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param year_window: int, how many years back we look for matches, e.g. "6" means we look for matches in six years
                        prior to your joining the profession; default is "1000", i.e. look back to beginning of data
    :return: a set of all PIDs who are inheritors
    """

    # get column indexes that we'll need
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    given_name_col_idx = helpers.get_header(profession, 'preprocess').index('prenume')
    chamber_col_idx = helpers.get_header(profession, 'preprocess').index('camera')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # the number of top-ranked surnames (out of the entire set of surnames) that we consider "common", and therefore
    # more liable to lead to false-positives in kin-matches;
    # NB: "0" means that we consider no names common, i.e. max false positive
    # NB: numbers were arrived at by consulting inheritance tables in analysis/descriptives/profession/inheritance
    surname_commonality_cutoffs = {'executori': 5, 'notaries': 14}
    num_top_names = surname_commonality_cutoffs[profession]

    # get set of common surnames across the entire person-year table
    common_surnames = top_surnames(person_year_table, num_top_names, profession)

    # get year range
    person_year_table.sort(key=itemgetter(year_col_idx))  # sort by year
    start_year, end_year = int(person_year_table[0][year_col_idx]), int(person_year_table[-1][year_col_idx])

    # group person-year table by year, make yearly subtables value in dict, key is year
    tables_by_year_dict = {int(pers_years[0][year_col_idx]): pers_years
                           for key, [*pers_years] in itertools.groupby(person_year_table, key=itemgetter(year_col_idx))}

    # get full names for each yearly entry cohort
    yearly_entry_cohorts_full_names = cohort_name_lists(person_year_table, start_year, end_year, profession)

    # make dict where keys are person-ids and values are lists of chambers in which person has served
    pids_chamb_dict = {py[pid_col_idx]: set() for py in person_year_table}  # initialise dict
    [pids_chamb_dict[py[pid_col_idx]].add(py[chamber_col_idx]) for py in person_year_table]  # fill it

    # initialise inheritance set
    inheritor_set = set()

    # starting with the second available year
    for current_year, current_person_years in tables_by_year_dict.items():
        if current_year != min(list(tables_by_year_dict)):

            # get all the people from the previous years
            people_already_here = people_in_prior_years(current_year, start_year,
                                                        person_year_table, year_window, profession)

            # get this year's list of names of new recruits, i.e. fresh entrants
            recruits = yearly_entry_cohorts_full_names[current_year]

            # iterate through the current person years
            for py in current_person_years:
                rec_full_name = py[surname_col_idx] + ' | ' + py[given_name_col_idx]  # recruit's full name

                # if that person is a new recruit;
                # NB: full names in 'recruits' are in format 'SURNAMES | GIVEN NAMES'
                if rec_full_name in recruits:

                    # compare recruit with everyone already in profession
                    for person_already in people_already_here:

                        # if recruit has a kin match with someone already in profession
                        if kin_match(py, person_already, pids_chamb_dict, common_surnames, profession):
                            # add match to inheritance dict
                            inheritor_set.add(py[pid_col_idx])

    # return the entries count dict
    return inheritor_set


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


def kin_match(recruit_data, old_pers_data, pids_chamber_dict, common_surnames, profession):
    """
    Applies the kinship matching rules, returns True if there's a match.

    The rule is: if the recruit shares at least one surname with the older profession member AND their chambers match,
    then they're considered kin. The exceptions are:
        - if surnames match AND the your office infos differ by at most three Levenshtein distance then we ignore
        other geographic considerations and match you as kin
        - if surnames match and either their full name is in your office info, or your full name is in their office
        info, then ignore other geographic considerations and match you as kin
        - if one of the surnames in the most common names, then we need a match on BOTH surnames
          before accepting the match
        - if the town is Bucharest then the match has to be not only on chamber but also on town/localitate;
          NB: this puts in an asymmetry where recuits from Bucharest CHAMBER can match BUCHAREST town, but recruits
              from BUCHAREST town must match ONLY Bucharest town (not the wider chamber); this is intentional, to
              allow for people from Bucharest town placing their kin in the wider chamber, but not vice verse, since
              it's harder for peripherals to get a foothold downtown than the other way around

    NB: chamber ("camera") indicates the appellate court jurisdiction in which the professional operates. This is also
    the lowest level territorial, professional organisation for notaries and executori.

    NB: the most recent chamber of the person already in the profession can match ANY ONE of the chambers in the career
        of the recruit. This accounts for the pattern that inheritors sometimes start in a different chamber (where
        there's an open spot) then move in the town of their kin as soon as possible.

    :param recruit_data: a list of data values (i.e. a row) for a new recruit;
                         data in order of preprocessed headers, see helpers.helpers.get_header under 'preprocess'
    :param old_pers_data: a list of data values (i.e a row) for a person that was there before the new recruit
                         data in order of preprocessed headers, see helpers.helpers.get_header under 'preprocess'
    :param pids_chamber_dict: dict where keys are unique person-IDs and values are lists of the chambers that person
                              has been in
    :param common_surnames: set of strings, of most common surnames
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: bool, True if there's a match, false otherwise
    """

    # get column indexes
    surname_col_idx = helpers.get_header(profession, 'preprocess').index('nume')
    chamber_col_idx = helpers.get_header(profession, 'preprocess').index('camera')
    town_col_idx = helpers.get_header(profession, 'preprocess').index('localitatea')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # get data; NB, surnames turned to bags, which automatically deduplicates surnames, e.g. STAN STAN --> STAN
    rec_pid, rec_sns = recruit_data[pid_col_idx], set(recruit_data[surname_col_idx].split(' '))
    rec_town = recruit_data[town_col_idx]
    old_pers_sns, old_pers_chamb = set(old_pers_data[surname_col_idx].split(' ')), old_pers_data[chamber_col_idx]
    old_pers_town = old_pers_data[town_col_idx]

    # initiate set of matches
    matches = set()

    # for each surname
    for sn in rec_sns:

        # if match on surnames and on offices (bar typo); office info only available for executori
        if profession == 'executori':
            sediu_col_idx = helpers.get_header(profession, 'preprocess').index('sediul')
            rec_sediu, old_pers_sediu = recruit_data[sediu_col_idx], old_pers_data[sediu_col_idx]
            if rec_sediu != '-88':  # they need some office info, not just empties
                if len(rec_sns & old_pers_sns) > 0 and Levenshtein.distance(rec_sediu, old_pers_sediu) <= 3:
                    matches.add(True)

        # if the sn is not among the most common
        if sn not in common_surnames:
            # if there's at least one name in common AND recruit and person already there share 1+ chambers
            if len(rec_sns & old_pers_sns) > 0 and old_pers_chamb in pids_chamber_dict[rec_pid]:
                # if town is NOT Bucharest
                if rec_town != "BUCUREŞTI":
                    matches.add(True)
                else:  # recruit's town is Bucharest, old person also needs to be in Bucharest
                    if old_pers_town == "BUCUREŞTI":
                        matches.add(True)
        else:  # if the surname is common, need match on two surnames
            if len(rec_sns & old_pers_sns) > 1:
                matches.add(True)
    # if there's at least one match, return True
    return True if True in matches else False
