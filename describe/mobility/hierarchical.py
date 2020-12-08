import csv
import itertools
import statistics
import numpy as np
from operator import itemgetter
from copy import deepcopy
from helpers import helpers
from preprocess import sample
from describe import totals_in_out
from describe.mobility import area_samples


# AGGREGATE DESCRIPTORS OF HIERARCHICAL MOBILITY


def hierarchical_mobility_table(person_year_table, out_dir, profession):
    """
    Write to disk a table that shows, per year, per level, per mobility type, the counts by gender and the overall
    percent female of those who experienced that mobility event.

    The header will be ["YEAR", "LEVEL", "ACROSS TOTAL", "ACROSS PERCENT FEMALE", "DOWN TOTAL", "DOWN PERCENT FEMALE",
    "UP TOTAL","UP PERCENT FEMALE"].

    :param out_dir: directory where the inheritance table will live
    :param person_year_table: a table of person years as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    # get the mobility dict
    mobility_dict = hierarchical_mobility(person_year_table, profession)

    # write to disk
    out_path = out_dir + profession + "_hierarchical_mobility.csv"
    fieldnames = ["YEAR", "LEVEL", "ACROSS TOTAL", "ACROSS PERCENT FEMALE", "DOWN TOTAL", "DOWN PERCENT FEMALE",
                  "UP TOTAL", "UP PERCENT FEMALE"]
    with open(out_path, 'w') as out_p:
        writer = csv.DictWriter(out_p, fieldnames=fieldnames)
        writer.writerow({"YEAR": profession.upper(), "LEVEL": '', "ACROSS TOTAL": '', "ACROSS PERCENT FEMALE": '',
                         "DOWN TOTAL": '', "DOWN PERCENT FEMALE": '', "UP TOTAL": '', "UP PERCENT FEMALE": ''})
        writer.writeheader()
        for year, levels in mobility_dict.items():
            for lvl, mob_type in levels.items():
                across_total, across_percent = mob_type["across"]["total"], mob_type["across"]["percent female"]
                down_total, down_percent = mob_type["down"]["total"], mob_type["down"]["percent female"]
                up_total, up_percent = mob_type["up"]["total"], mob_type["up"]["percent female"]

                writer.writerow({"YEAR": year, "LEVEL": lvl,
                                 "ACROSS TOTAL": across_total, "ACROSS PERCENT FEMALE": across_percent,
                                 "DOWN TOTAL": down_total, "DOWN PERCENT FEMALE": down_percent,
                                 "UP TOTAL": up_total, "UP PERCENT FEMALE": up_percent})


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


# DESCRIPTORS FOCUSING ON UPWARD MOBILITY, BREAKING IT DOWN BY SPEED OF MOBILITY AND GENDER


def career_climbers_table(person_year_table, out_dir, profession, use_cohorts, first_x_years):
    """
    Make table showing the total number of people from select entry cohorts who stayed at low court, reached tribunal,
    appellate court, or even high court level, within a certain time frame. Also gives percent female of this total
    number, per category. Rows are levels in the judicial hierarchy.

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param use_cohorts: list of ints, each int represents a year for which you analyse entry cohorts, e.g. [2006, 2007]
    :param first_x_years: int, the number of years from start of career that we condsider, e.g. ten years since entry
    :param out_dir: str, directory where the career climber and stars tables will live
    :return: None
    """

    # get dicts of career climbs and of star_cohorts
    career_climbs = career_climbings(person_year_table, profession, use_cohorts, first_x_years)

    # write the career climbing table
    out_path_climbs = ''.join([out_dir, profession, "_career_climbs_", str(use_cohorts[0]), "-",
                               str(use_cohorts[-1]), ".csv"])
    with open(out_path_climbs, 'w') as out_pc:
        writer = csv.writer(out_pc)
        header = ["LEVEL", "TOTAL MAXED OUT AT LEVEL", "PERCENT FEMALE MAXED OUT AT LEVEL",
                  "AVERAGE NUMBER OF YEARS TO REACH LEVEL"]
        writer.writerow([profession.upper()])
        writer.writerow(header)
        levels = ['low court', 'tribunal', 'appellate', 'high court']
        for level in levels:
            writer.writerow([level, career_climbs[level]['counts dict']['total'],
                             career_climbs[level]['counts dict']['percent female'],
                             career_climbs[level]['counts dict']['avrg yrs to promotion']])


def career_climbings(person_year_table, profession, use_cohorts, first_x_years):
    """
    Return a dict of metrics on career climbing, i.e. of moving up the judicial hierarchy.

    NB: these metrics are only for a subset of observations, namely those specified by use_cohorts. The purpose of this
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
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
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


# TODO need to eliminate the use of this function, on account of there is so much noise around minimum time to
#  to promotion, partly because the legislature kept fiddling with the number for political reasons


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


# TRANSITION MATRICES FOR INTER-LEVEL MOBILITY


def make_inter_level_hierarchical_transition_matrixes_tables(person_year_table, profession, out_dir):
    """
    This function spits out two .csv's per profession, where one CSV contains the transition matrices for all observed
    years except the left and right censors (since we judge entry and departure based on anterior and posterior year
    to focal year X) and the other shows the transition PROBABILITY matrices for the same years.

    :param person_year_table: a table of person years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param out_dir: str, the path to where the transition matrices will live
    :return: None
    """
    global_trans_dict = inter_level_transition_matrices(person_year_table, profession)

    with open(out_dir + 'yearly_count_hierarchical_transition_matrices.csv', 'w') as out_ct, \
            open(out_dir + 'yearly_count_hierarchical_probability_transition_matrices.csv', 'w') as out_pb:

        count_writer, prob_writer = csv.writer(out_ct), csv.writer(out_pb)
        count_writer.writerow([profession]), count_writer.writerow([]),
        prob_writer.writerow([profession]), prob_writer.writerow([]),

        for yr in global_trans_dict:
            count_writer.writerow([yr]), prob_writer.writerow([yr])

            for lvl in global_trans_dict[yr]:
                count_row = [str(key) + ' : ' + str(value) for key, value in global_trans_dict[yr][lvl].items()]
                count_writer.writerow(count_row)

                level_sum_key = str(lvl) + '-' + "level_sum"
                level_sum = global_trans_dict[yr][lvl][level_sum_key]
                prob_row = [str(key) + ' : ' + str(round(helpers.weird_division(value, level_sum), 4))
                            for key, value in global_trans_dict[yr][lvl].items()]
                prob_writer.writerow(prob_row)
            count_writer.writerow([]), prob_writer.writerow([])


def inter_level_transition_matrices(person_year_table, profession):
    """
    NB: ONLY FOR JUDGES AND PROSECUTORS!

    For each year, return a dict containing a transition frequency matrix of actor moves. If there are are N levels in
    the system then there are N rows and N+4 columns: one extra column for frequency of retirement out of that level,
    another for frequency of no movement at all (i.e. stay in your position), another column of the total number of
    people available to move in that year (this is just the sum of people in that level in year X, and the denominator
    for the percentages), and one last column to count how many observations we skipped, because said people in that
    year had discontinuities in their careers (e.g. was there 1987-1992, then 1996-2004).

    The cells of the NxN submatrix of the transition frequency matrix are read as
    "# of total transitions from i to j", where "i" is the row index and "j" the column index.

    TRANSITION FREQUENCY MATRIX FOR YEAR X

                Level 1     Level 2     Level 3     Retire      Stay Put    Level Sum   Discontinuous
    Level 1
    Level 2
    Level 3

    NB: this is what the

    NB: lower levels are higher up the hierarchy, so 1 > 2 in terms of hierarchical position

    :param person_year_table: a table of person years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: a nested dict, where top-level keys are years, then you have levels, then you have types of move per level,
             e.g. retirements, or moves from Lvl1 to Lvl2
    """

    # get handy column indexes
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    wrkplc_idx = helpers.get_header(profession, 'preprocess').index('instituţie')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    years = sorted(list({int(py[yr_col_idx]) for py in person_year_table}))

    # make the global transition dict, a three-layer dict: first layer is "year", second layer is "level",
    # third level is measures
    global_trans_dict = {}
    for yr in years:
        global_trans_dict[yr] = {}

        # number of levels can change with years
        levels = sorted(list({int(py[lvl_col_idx]) for py in person_year_table if int(py[yr_col_idx]) == yr}))

        # get a list of all possible moves, e.g. "1-3" means "demotion from level 1 to level 3"
        possible_moves = []
        for i in levels:
            for j in levels:
                possible_moves.append(str(i) + '-' + str(j))
            possible_moves.append(str(i) + '-' + "retire"), possible_moves.append(str(i) + '-' + "static")
            possible_moves.append(str(i) + '-' + "level_sum"), possible_moves.append(str(i) + '-' + "discontinuous")

        # update the global transition dict with the base, count dict for each level
        for lvl in levels:
            global_trans_dict[yr][lvl] = {pm: 0 for pm in possible_moves if int(pm[0]) == lvl}

    # need to do some ad-hoc correction to account for years in which the number of levels expands, either because
    # we now have data on a new level that was already there (e.g. we have data on the High Court only starting in 1988)
    # or in reality a new level was added (e.g. introduction of appellate courts in 1993). Basically, 1987 and 1992
    # need to resemble the year after, so we can properly imput mobility data
    global_trans_dict[1987] = deepcopy(global_trans_dict[1988])
    global_trans_dict[1992] = deepcopy(global_trans_dict[1993])

    # now fill up the dict with counts

    # group table by persons
    person_year_table = sorted(person_year_table, key=itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    for person in people:
        for idx, pers_yr in enumerate(person):
            current_wrkplc, current_lvl = pers_yr[wrkplc_idx], int(pers_yr[lvl_col_idx])
            current_yr = int(pers_yr[yr_col_idx])

            # update the level sum
            lvl_sum_key = str(current_lvl) + '-' + "level_sum"
            global_trans_dict[current_yr][current_lvl][lvl_sum_key] += 1

            if idx < len(person) - 1:  # all but retirement year
                next_yr_wrkplc, next_yr_lvl = person[idx + 1][wrkplc_idx], person[idx + 1][lvl_col_idx]
                next_yr_yr = person[idx + 1][yr_col_idx]

                # look only at changes in consecutive years; this avoids people with interrupted careers,
                # which usually occur in the sampled periods because people leave and re-enter the sample

                if int(current_yr) + 1 == int(next_yr_yr):

                    if current_wrkplc != next_yr_wrkplc:  # workplace mobility occurred

                        if current_lvl != next_yr_lvl:  # hierarchical mobility occurred
                            hierarch_mob_key = str(current_lvl) + '-' + str(next_yr_lvl)
                            global_trans_dict[current_yr][current_lvl][hierarch_mob_key] += 1

                        else:  # no hierarchical mobility, i.e. movement within the level
                            within_mob_key = str(current_lvl) + '-' + str(current_lvl)
                            global_trans_dict[current_yr][current_lvl][within_mob_key] += 1

                    else:  # no mobility at all
                        static_key = str(current_lvl) + '-' + "static"
                        global_trans_dict[current_yr][current_lvl][static_key] += 1

                else:  # count persons skipped due to discontinuous careers so we know how much data we're excluding
                    discontinuous_key = str(current_lvl) + '-' + "discontinuous"
                    global_trans_dict[current_yr][current_lvl][discontinuous_key] += 1

        # retirement year
        retirement_level, retirement_year = int(person[-1][lvl_col_idx]), int(person[-1][yr_col_idx])
        retirement_key = str(person[-1][lvl_col_idx]) + '-' + "retire"
        global_trans_dict[retirement_year][retirement_level][retirement_key] += 1

    return global_trans_dict


def make_vacancy_transition_tables(person_year_table, profession, out_dir, years, averaging_years=None, area_samp=False,
                                   out_dir_area_samp=None):
    """
    Make a csv containing one sub-table for each of the years that we select, with each sub-table showing the transition
    probabilites between hiearchical levels of vacancies. Optionally, we may also include a table that averages across
    desired years. e.g. 1984-1989.

    Each sub-table should be NxN+1, where N = number of levels, and the last column represents vacancies leaving the
    system, i.e. people being recruited into the system.

    NB: diagonals signify mobility WITHIN the level

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param out_dir: str, the path to where the transition matrices will live
    :param years: list of ints, the years for which we want vacancy probability transition matrixes
    :param averaging_years: list of ints over which we want to average vacancy frequency tables, e.g. [1985, 1986, 1987]
    :param area_samp: bool,True if we want to sample from specific areas
    :param out_dir_area_samp: if given, str showing the out-directory where we want the vacancy transition tables for
                              the sample areas to live
    :return: None
    """
    averaging_years = averaging_years if averaging_years else []  # if no averaging years provided, make empty list
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    proms_weights, demos_weights, transfs_weights = None, None, None  # throws up errors if things go awry

    # get entry counts, in easy format
    entry_counts = totals_in_out.pop_cohort_counts(sorted_person_year_table, years[0], years[-1], profession,
                                                   cohorts=True, unit_type="nivel", entry=True)
    entry_counts.pop("grand_total")  # don't need the grand total
    for lvl in entry_counts:
        for yr in entry_counts[lvl]:
            entry_counts[lvl][yr] = entry_counts[lvl][yr]["total_size"]

    if area_samp:
        # I hard code these in since they change so rarely
        samp_areas = {"judges": ["CA1", "CA7", "CA9", "CA12", "-88"], "prosecutors": []}
        samp_yr_range = {"judges": [1980, 2003], "prosecutors": []}
        samp_yrs, samp_as = samp_yr_range[profession], samp_areas[profession]

        # get sample-adjusted entry counts and sample weights for mobility
        entry_counts = area_samples.adjusted_entry_counts(person_year_table, profession)
        proms_weights = area_samples.adjusted_promotion_counts(sorted_person_year_table, profession, weights=True)
        demos_weights = area_samples.adjusted_demotion_counts(sorted_person_year_table, profession, weights=True)
        transfs_weights = area_samples.adjusted_lateral_transfer_counts(sorted_person_year_table, profession,
                                                                        weights=True)
        # restrict person-year table to sampling areas
        sorted_person_year_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
        # redirect the out-directory
        out_dir = out_dir_area_samp

    # get person-level transition frequencies levels
    trans_freqs = inter_level_transition_matrices(sorted_person_year_table, profession)

    with open(out_dir + "vacancy_probability_transition_matrixes.csv", "w") as out_f:
        writer = csv.writer(out_f)

        # this is unused if averaging years stays empty
        avg_vac_trans_mat = np.empty((4, 5), float)

        # for each sampling year
        for yr in years:

            # make array of zeros, for four levels; not all years have four levels, but zero rows/columns are harmless
            trans_mat = np.zeros((4, 4))

            for lvl in range(1, 5):  # for departure levels in the system, i.e. the level FROM which mobility happens
                if lvl in trans_freqs[yr]:  # if the levels exist in that year (since some are added later)

                    # now weigh the observed values
                    # NB: route = mobility route, e.g. "1-2" means "mobility from level 1 to level 2"
                    for route, mob_freq in trans_freqs[yr][lvl].items():

                        # ignore retirements, non-movements, sums, and discontinuities
                        if route.split("-")[1].isdigit():

                            # level you leave and level you go to; -1 since numpy zero indexes
                            departing, arriving = int(route.split("-")[0]) - 1, int(route.split("-")[1]) - 1

                            # get frequency counts and put them in the frequency matrix; if sampling, weigh the counts
                            if departing < arriving:  # promotions
                                trans_mat[departing][arriving] = mob_freq
                                if area_samp:
                                    trans_mat[departing][arriving] = round(mob_freq * proms_weights[lvl], 5)

                            if departing == arriving:  # lateral transfers
                                trans_mat[departing][arriving] = mob_freq
                                if area_samp:
                                    trans_mat[departing][arriving] = round(mob_freq * transfs_weights[lvl], 5)

                            if departing > arriving:  # demotions
                                trans_mat[departing][arriving] = mob_freq
                                if area_samp:
                                    trans_mat[departing][arriving] = round(mob_freq * demos_weights[lvl], 5)

            # transpose the person-level mobility frequency matrix to get the vacancy mobility matrix
            vac_trans_mat = np.transpose(trans_mat)

            # by convention, we thus far treated levels in incrementing order, i.e. level 1 < 2 < 3 < 4. The convention
            # in vacancy chains studies is that 1 > 2 > 3 > 4, and to get that we transpose the array along the
            # anti-diagonal/off-diagonal
            vac_trans_mat = vac_trans_mat[::-1, ::-1].T

            # in the last column we put vacancy "retirements", i.e. entries of people into the system

            entry_freqs = [entry_counts[str(level)][yr] for level in range(1, 5) if str(level) in entry_counts]
            entries_col = np.asarray(entry_freqs[::-1])[..., None]  # give it Nx1 shape; reverse order for 1 > 2 > 3...
            vac_trans_mat = np.append(vac_trans_mat, entries_col, 1)

            if yr in averaging_years:
                avg_vac_trans_mat = np.add(avg_vac_trans_mat, vac_trans_mat)

            vac_prob_mat = freq_mat_to_prob_mat(vac_trans_mat.tolist(), round_to=5)
            # add that transition probability matrix to table
            writer.writerow([profession.upper(), yr])
            header = ["", "Level 1", "Level 2", "Level 3", "Level 4", "Recruits"]
            writer.writerow(header)
            for i in range(len(vac_prob_mat)):
                writer.writerow([header[1:][i]] + vac_prob_mat[i])
            writer.writerow(["\n"])

        if averaging_years:
            avg_vac_trans_mat = np.divide(avg_vac_trans_mat, float(len(averaging_years) - 1))
            avg_vac_prob_mat = freq_mat_to_prob_mat(avg_vac_trans_mat.tolist(), round_to=5)
            writer.writerow(["AVERAGED ACROSS YEARS"] + averaging_years)
            header = ["", "Level 1", "Level 2", "Level 3", "Level 4", "Recruits"]
            writer.writerow(header)
            for i in range(len(avg_vac_prob_mat)):
                writer.writerow([header[1:][i]] + avg_vac_prob_mat[i])


def freq_mat_to_prob_mat(frequency_matrix, round_to=15):
    """
    Take a matrix of frequencies and turn it into a probability matrix, where each cell is divided by its row sum.
    NB: leaves zero rows as they are are

    :param frequency_matrix: list of lists, e.g. [[1,2,], [3,4]]
    :param round_to: int, to how many decimals we want to round; default is fifteen
    :return list of lists, where rows sum to 1, e.g. [[0.25, 0.75], [0.9, 0.1]]
    """
    probability_matrix = []
    for i in range(len(frequency_matrix)):
        row_sum = sum(frequency_matrix[i])
        prob_row = [round(helpers.weird_division(round(cell, 5), row_sum), round_to) for cell in frequency_matrix[i]]
        probability_matrix.append(prob_row)
    return probability_matrix
