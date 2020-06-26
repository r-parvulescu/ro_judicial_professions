"""
Functions for creating descriptive tables and graphs.
"""

import csv
import itertools
import operator
import natsort
from scipy.stats.stats import pearsonr
from describe import descriptives
from helpers import helpers


def describe(in_file_path, out_dir_tot, out_dir_mob, out_dir_inher, profession, start_year, end_year, unit_type=None):
    """
    Generate basic descriptives , and write them to disk.

    :param in_file_path: path to the base data file
    :param out_dir_tot: string, directory where the descriptive files on total counts will live
    :param out_dir_mob: string, directory where the descriptive files on mobility will live
    :param out_dir_inher: string, directory where the descriptive files on inheritance will live
    :param start_year: first year we're considering
    :param end_year: last year we're considering
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: None or list; if list, each entry is, type of unit we want table deaggreagted by,
                      e.g. one table where rows are metrics for each appellate court region,
                           and another where rows are metrics for each hierarchical level of the judicial system
    :return: None
    """

    with open(in_file_path, 'r') as infile:
        table = list(csv.reader(infile))[1:]  # start from first index to skip header
    '''
    # make table of total counts per year
    year_counts_table(table, start_year, end_year, profession, out_dir_tot)

    # make tables for entry and exit cohorts, per year per gender
    entry_exit_gender(table, start_year, end_year, profession, out_dir_mob, entry=True)
    entry_exit_gender(table, start_year, end_year, profession, out_dir_mob, entry=False)
    '''
    # for prosecutors and judges only
    if profession == 'prosecutors' or profession == 'judges':
        career_climbers_stars_table(table, out_dir_mob, profession, use_cohorts=[2006, 2007, 2008, 2009],
                                    first_x_years=10, )
        '''
        # make table for extent of career centralisation around capital city appellate region, per year per unit
        career_movements_table(table, profession, "ca cod", out_dir_mob)

        # make tables of total counts per year, per level in judicial hierarchy
        year_counts_table(table, start_year, end_year, profession, out_dir_tot, unit_type='nivel')

        # make tables of total counts per year, per appellate region
        year_counts_table(table, start_year, end_year, profession, out_dir_tot, unit_type='ca cod')

        # make tables for entry and  exit cohorts, per year, per gender, per level in judicial hierarchy
        entry_exit_gender(table, start_year, end_year, profession, out_dir_mob, entry=False, unit_type='nivel')
        entry_exit_gender(table, start_year, end_year, profession, out_dir_mob, entry=True, unit_type='nivel')

        # make table for mobility between appellate court regions
        inter_unit_mobility_table(table, out_dir_mob, profession, 'ca cod')
        
        # make table for hierarchical mobility
        hierarchical_mobility_table(table, out_dir_mob, profession)

        # make table of correlations between labour shortages and number of women that enter a tribunal area
        low_court_gender_balance_profession_growth_table(table, out_dir_mob, profession)

        for u_t in unit_type:
            # make tables for entry and exit cohorts, per year per unit type
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_dir_mob, entry=True)
            entry_exit_unit_table(table, start_year, end_year, profession, u_t, out_dir_mob, entry=False)

    else:  # for notaries and executori only

        # make table for professional inheritance
        profession_inheritance_table(out_dir_inher, table, profession, year_window=1000, num_top_names=3)
    '''


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

                percent_never_left_home = helpers.percent(never_left_home, num_careers)
                percent_never_left_buc = helpers.percent(never_left_buc, num_start_buc)
                percent_non_buc_through_buc = helpers.percent(non_buc_through_buc, num_start_non_buc)
                percent_non_buc_through_non_buc = helpers.percent(num_non_buc_through_non_buc, num_start_non_buc)

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
        multiprofs_py_table.sort(key=operator.itemgetter(year_col_idx))

    # get the dict of inter-professional transfers
    transfers_dict = descriptives.inter_professional_transfers(multiprofs_py_table, out_dir, year_window)

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


def profession_inheritance_table(out_dir, person_year_table, profession, year_window=1000, num_top_names=0):
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
    :return: None
    """

    # get the inheritance dict
    inheritance_dict = descriptives.profession_inheritance(out_dir, person_year_table, profession,
                                                           year_window, num_top_names)
    sum_male_entries, sum_female_entries = 0, 0
    sum_male_inherit, sum_female_inherit = 0, 0

    table_out_path = out_dir + '/' + profession + '_inheritance_table.csv'
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


def low_court_gender_balance_profession_growth_table(person_year_table, out_dir, profession):
    """
    Table that shows the size of an entry cohort relative to the existing workforce, and the change in gender ratio
    in the existing workforce since last year. "Existing workforce" refers to all low court magistrates in a certain
    county/tribunal area, for each year.

    For judges and prosecutors this means all magistrates working at low courts in a certain tribunal area (but
    NOT the juges and appellate or tribunal courts). For notaries and executori this means all professionals working
    within the county (since these professions have a one-level hierarchy).

    THe columns are counties and the rows are years. Each row has two subrows:
        i.  RELATIVE ENTRY COHORT SIZE: percent value of this year's entry cohort relative to last year's workforce size
        ii. CHANGE IN GENDER RATIO: difference between this year's percent female and last year's pecent female;
                                    a negative value indicates masculinisation, a positive value feminisation

    Row correlations shows yearly correlation between relative entry cohort size and change in gender ratio, across
    tribunal areas, with p-value for correlation. Column correlations shows correlation between relative entry cohort
    size and mean change in gender ratio per tribunal, across years, with p-value for correlation.

    :param out_dir: directory where the inheritance table will live
    :param person_year_table: a table of person years as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """
    # get column indexes
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    jud_col_idx = helpers.get_header(profession, 'preprocess').index('jud cod')
    tb_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')

    # keep only person years that refer to low courts or low court parquets
    person_year_table = [py for py in person_year_table if py[jud_col_idx] != '-88']

    # get set of all tribunals and first and last observation years
    all_tbs = natsort.natsorted(list({py[tb_col_idx] for py in person_year_table}))
    edge_years = {int(py[year_col_idx]) for py in person_year_table}
    start_year, end_year = min(edge_years), max(edge_years)

    # get entry cohort data for all years, at lower court level
    entry_cohorts = descriptives.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                   cohorts=True, unit_type='jud cod', entry=True)
    # get totals data for all years, at lower court level
    year_totals = descriptives.pop_cohort_counts(person_year_table, start_year, end_year, profession,
                                                 cohorts=False, unit_type='jud cod')

    # make dict where first level keys are year, second level keys are tribunal areas,
    # and third level keys are person-years, then populate it
    tb_year_dict = {year: {tb: [] for tb in all_tbs} for year in range(start_year, end_year + 1)}
    [tb_year_dict[int(py[year_col_idx])][py[tb_col_idx]].append(py) for py in person_year_table]

    # make dict of net changes in worker counts: first level keys are years, second level keys are tribunal areas,
    # third level keys are "total worker gain" and "net female entry cohort"
    net_dict = {year: {tb: {'relative entry cohort size': 0, 'change gender balance': 0} for tb in all_tbs}
                for year in range(start_year + 1, end_year + 1)}  # omit first year, comparisons are with previous year

    # fill the net dict
    for year, tbs in tb_year_dict.items():
        for tb, person_years in tbs.items():
            if year > start_year:  # start with second year, since we look behind one year

                previous_year_num_workers = len(tb_year_dict[year - 1][tb])
                this_year_num_workers = len(person_years)

                # get list of all low courts in this tribunal area, in this year
                all_juds = {py[jud_col_idx] for py in person_years}

                # initialise count of entry cohort size for low courts in tribunal area
                this_year_entry_cohort_size = 0
                # initialise counts for total number of women and total number of people, for last year and this year
                previous_year_total_women, this_year_total_women = 0, 0
                for jud in all_juds:
                    this_year_entry_cohort_size += entry_cohorts[jud][year]['total_size']
                    previous_year_total_women += year_totals[jud][year - 1]['f']
                    this_year_total_women += year_totals[jud][year]['f']

                percent_female_last_year = helpers.percent(previous_year_total_women, previous_year_num_workers)
                percent_female_this_year = helpers.percent(this_year_total_women, this_year_num_workers)
                diff_percent_female = percent_female_this_year - percent_female_last_year  # neg means masculinisation
                relative_entry_cohort_size = helpers.percent(this_year_entry_cohort_size, previous_year_num_workers)

                # update net dict
                net_dict[year][tb]['relative entry cohort size'] = relative_entry_cohort_size
                net_dict[year][tb]['change gender balance'] = diff_percent_female

    # for each year make one list of "relative entry cohort size" across tribunals, and another for
    # "change gender balance" across tribunals. Then find the correlation between the lists.
    output_table = []
    for year in net_dict:
        relative_entry_cohort_size_list, gender_balance_change_list = [], []
        for tb in all_tbs:
            relative_entry_cohort_size_list.append(net_dict[year][tb]['relative entry cohort size'])
            gender_balance_change_list.append(net_dict[year][tb]['change gender balance'])

        correl = pearsonr(relative_entry_cohort_size_list, gender_balance_change_list)
        correl_val, correl_p = round(correl[0], 3), round(correl[1], 3)

        output_table.append([year, "RELATIVE ENTRY COHORT SIZE"] + relative_entry_cohort_size_list)
        output_table.append(['', "CHANGE GENDER BALANCE"] + gender_balance_change_list + [correl_val, correl_p])

    # do likewise for lists and correlatoins across years, per tribunal
    column_correls, column_ps = ['', ''], ['', '']
    for tb in all_tbs:
        tb_relative_entry_list, tb_gender_balance_list = [], []
        for year in net_dict:
            tb_relative_entry_list.append(net_dict[year][tb]['relative entry cohort size'])
            tb_gender_balance_list.append(net_dict[year][tb]['change gender balance'])

        tb_correl = pearsonr(tb_relative_entry_list, tb_gender_balance_list)
        tb_correl_val, tb_correl_p = round(tb_correl[0], 3), round(tb_correl[1], 3)
        column_correls.append(tb_correl_val), column_ps.append(tb_correl_p)

    output_table.append(column_correls), output_table.append(column_ps)

    # and write table to disk
    out_path = out_dir + profession + '_low_court_gender_balance_profession_growth.csv'
    with open(out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        writer.writerow([profession.upper()])
        writer.writerow(['', "TRIBUNALS"])
        writer.writerow(['YEAR', ''] + all_tbs + ["CORREL"])
        [writer.writerow(row) for row in output_table]


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
    mobility_dict = descriptives.hierarchical_mobility(person_year_table, profession)

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


def career_climbers_stars_table(person_year_table, out_dir, profession, use_cohorts, first_x_years):
    """
    Make two tables and write them to disk.

    The first table shows the total number of people from select entry cohorts stayed at low court, reached tribunal,
    appellate court, or even high court level, within a certain time frame. Also gives percent female of this total
    number, per category. Rows are levels in the judicial hierarchy.

    The second table shows
        a) the percent of appellate stars (i.e. those who reached the court of appeals faster than
            average) who were also tribunal stars. This let us see whether tribunal star status predicts appellate
            court star status; this percentage is over the whole period under consideration
        b) for each entry cohort, how many of its people were tribunal stars, how many appellate stars, and what the
            percent female was in each cohort-category
    Rows are year of entry.

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param use_cohorts: list of ints, each int represents a year for which you analyse entry cohorts, e.g. [2006, 2007]
    :param first_x_years: int, the number of years from start of career that we condsider, e.g. ten years since entry
    :param out_dir: str, directory where the career climber and stars tables will live
    :return: None
    """

    # get dicts of career climbs and of star_cohorts
    career_climbs = descriptives.career_climbings(person_year_table, profession, use_cohorts, first_x_years)
    stars = descriptives.career_stars(person_year_table, profession, use_cohorts, first_x_years)

    # write the career climbing table
    out_path_climbs = out_dir + profession + "_career_climbs_" + str(use_cohorts[0]) + "-" + str(use_cohorts[-1]) \
                      + ".csv"
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

    # write the career stars table
    out_path_stars = out_dir + profession + "_career_stars.csv"
    with open(out_path_stars, 'w') as out_ps:
        writer = csv.writer(out_ps)
        header = ["COHORT YEAR", "LEVEL", "TOTAL STARS", "PERCENT FEMALE STARS"]
        writer.writerow([profession.upper()])
        writer.writerow(["PERCENT OF APPELLATE STARS THAT ALSO TRIBUNAL STARS", stars["percent continuation stars"]])
        writer.writerow(header)
        years = sorted(list(stars))[:-1]
        stars_levels = ["tribunal", "appellate"]
        for yr in years:
            writer.writerow([yr])
            for lvl in stars_levels:
                writer.writerow(["", lvl, stars[yr][lvl]['total'], stars[yr][lvl]['percent female']])
