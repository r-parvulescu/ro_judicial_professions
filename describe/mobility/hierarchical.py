import csv
import itertools
import statistics
from operator import itemgetter
from helpers import helpers
from copy import deepcopy


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
    Make table showing the total number of people from select entry cohorts stayed at low court, reached tribunal,
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
