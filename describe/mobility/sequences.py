"""
Functions for preparing table of career sequences, to feed into social sequence analysis.
"""

from helpers import helpers
import operator
import itertools
import statistics
import csv


def get_geographic_hierarchical_sequences(person_year_table_path, profession, outdir):
    """

    FOR JUDGES AND PROSECUTORS ONLY

    Makes a table with twelve columns (zero-indexed):

        col 0  = person ID
        col 1 = entry year (first year in career)
        col 2 = gender
        col 3 = number of region changes in first 6 years on the job
        col 4 = number of region changes in first 11 years on the job
        col 5 = number of region changes in first 15 years on the job
        col 6 = time to tribunal promotion (if occurred)
        col 7 = time to court of appeals promotion (if occurred)
        col 8 = own cohort's average time to tribunal promotion OF THOSE PROMOTED
        col 9 = own cohort's average time to promotion OF THOSE PROMOTED
        col 10 = length of sequence (i.e. career length in years)
        col 11 = joint sequence of hierarchical position and geographic movement
        col 12 = first five years of said sequence (i.e. sequence truncated after five years; fifth year included)
        col 13 = first ten years of said sequence (i.e. sequence truncated after ten years; tenth year included)

    The hierarchical position code shows where in the judicial hierarchy the person is. The elements are:
        LC = municipal, low court, TB = county tribunal, CA = regional court of appeals, HC = national high court.

    The geographic movement code shows whether the person moved workplace and if they changed appellate court region,
    since last year. The elements are "NT" for "no move", "MW" for "moved within appellate region," and "MB" for
    "moved between appellate regions."

    By convention, moves are compared to last year, so e.g. TB-MB means "this year in tribunal, last year in low court,
    move took place between appellate regions.

    We then combine these two element sets (alphabet expansion) to create the final set of elements that we use to
    construct the sequences:

        LC-NM = low court, no move             LC-MW = low court, move within region
        TB-NM = tribunal, no move              TB-MW = tribunal, move within region
        CA-NM = court of appeals, no move      CA-MW = court of appeals, move within region
        HC-NM = high court, no move

        LC-MB = low court, move between regions
        TB-MB = tribunal, move between regions
        CA-MB = court of appeals, move between regions

        HC-M = high court, move (because there is only one court in the land)

    The resulting sequences will look like e.g. LC-NM|LC-NM|TB-MW|TB-NM|TB-NM|CA-MB|CA-NM, where each year is
    separated by the pipe "|".

    :param person_year_table_path: path to a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param outdir: directory in which we want to place the data table
    :return: None
    """

    # load the person-year table
    with open(person_year_table_path, 'r') as in_f:
        person_year_table = list(csv.reader(in_f))[1:]

    # get indices for person ID, year, ca cod, trib cod, j cod, and level code
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    gend_col_idx = helpers.get_header(profession, 'preprocess').index('sex')

    # initialise the person-sequence table
    person_sequences_table = []

    # sort people by unique ID and year, then group by unique ID
    person_year_table.sort(key=operator.itemgetter(pid_col_idx, yr_col_idx))
    persons = [pers for key, [*pers] in itertools.groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # for each person
    for pers in persons:
        pid = pers[0][pid_col_idx]
        entry_yr = pers[0][yr_col_idx]  # the year they entered the profession
        gndr = pers[0][gend_col_idx]  # person gender

        # get the full sequence, and truncated at five and ten years
        geog_lvl_moves_seq = get_geog_lvl_moves_seq(pers, profession)
        began_at_low_court = 1 if geog_lvl_moves_seq[:2] == "LC" else 0
        first_five_yrs = '|'.join(geog_lvl_moves_seq.split('|')[:5]) if len(geog_lvl_moves_seq) > 29 else ''
        first_ten_yrs = '|'.join(geog_lvl_moves_seq.split('|')[:10]) if len(geog_lvl_moves_seq) > 54 else ''
        between_moves = count_between_moves_in_time_interval(geog_lvl_moves_seq)

        time_to_tb_promotion, time_to_ac_promotion = time_to_promotion(geog_lvl_moves_seq)

        person_row = [pid, entry_yr, gndr, between_moves["first 6 years"], between_moves["first 11 years"],
                      between_moves["first 15 years"], began_at_low_court, time_to_tb_promotion, time_to_ac_promotion,
                      '', '', len(geog_lvl_moves_seq.split('|')), geog_lvl_moves_seq, first_five_yrs, first_ten_yrs]

        person_sequences_table.append(person_row)

    # now for each person, mark their cohort's average time to tribunal and court of appeals promotion
    average_time_to_promotion(person_sequences_table)

    # write the person-sequence table to disk as a csv
    header = ["pid", "entry_year", "gender", "region_moves_first_6_yrs", "region_moves_first_11_yrs",
              "region_moves_first_15_yrs", "began_at_LC", "time_to_tb_prom", "time_to_ac_prom",
              "cohort_avg_time_to_tb_prom", "cohort_avg_time_to_ac_prom", "sequence_career_length",
              "geog_lvl_moves_sequence", "first_five_yrs_seq", "first_ten_yrs_seq"]
    with open(outdir + "sequences_data_table.csv", 'w') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        [writer.writerow(pers_seq) for pers_seq in person_sequences_table]


def get_geog_lvl_moves_seq(pers, profession):
    """
    Given a person's collection of person years, returns a sequence of geographic moves - hierarchical level.

    :param pers: list of person-years, sorted by years (in increasing order) and sharing a unique person-ID
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: str, sequence of geographic moves - hierarchical position with elements separated by a bar ("|"),
                  e.g. LC-NM|LC-NM|TB-MW|TB-NM|TB-NM|CA-MB|CA-NM
    """

    ca_col_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    trib_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')
    j_col_idx = helpers.get_header(profession, 'preprocess').index('jud cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    level_codes = {"1": "LC", "2": "TB", "3": "CA", "4": "HC"}

    mov_seq = []

    # for each person's year
    for idx, pers_yr in enumerate(pers):

        # element for the first year ; by definition, no movement possible
        if idx < 1:
            this_yr_lvl = pers_yr[lvl_col_idx]
            mov_seq.append(level_codes[this_yr_lvl])

        # since we see movement by comparing current workplace to last year's workplace, we compute movement metrics
        # by starting at the second year
        else:
            this_yr_lvl = pers_yr[lvl_col_idx]

            last_yr_workplace_code = [pers[idx - 1][ca_col_idx], pers[idx - 1][trib_col_idx], pers[idx - 1][j_col_idx]]
            this_yr_workplace_code = [pers_yr[ca_col_idx], pers_yr[trib_col_idx], pers_yr[j_col_idx]]

            # see if workplace changed
            if last_yr_workplace_code != this_yr_workplace_code:

                # if the CA unit code matches, it's a move within
                if last_yr_workplace_code[0] == this_yr_workplace_code[0]:  # CA code is first in workplace code
                    geog_move = "MW"

                else:  # it's a move between

                    # if CA codes do not match, current CA code is -88 (i.e. high court, in Bucharest city),
                    # and previous TB code was TB9, (i.e. Bucharest city) then no move, since person stayed
                    # in Bucharest
                    if this_yr_workplace_code[0] == '-88' and last_yr_workplace_code[1] == 'TB9':
                        geog_move = "MW"

                    else:  # between move
                        geog_move = "MB"

            else:  # no move
                geog_move = "NM"

            mov_seq.append(level_codes[this_yr_lvl] + '-' + geog_move)

    # return sequence as string, with year elements divided by the "|" bar
    return '|'.join(mov_seq)


def count_between_moves_in_time_interval(geog_lvl_moves_seq):
    """
    Report number of geographic moves for sequences of geographic moves - hierarchical levels of different lengths.
     - for sequences 4-6 years/element long, report if there is at least one move
     - for sequences 9-11 years/elements long, report if there are at least two moves
     - for sequences 13-15 years/elements long, report if there are at least three moves

     If the sequence we analyse is "not long enough", report "NLE" instead.

     NB: I realise I'm duplicating loops from get_geog_lvl_moves() but I want the code to be clear.

    :param geog_lvl_moves_seq:
    :return: return a 3-tuple
    """

    split_seq = geog_lvl_moves_seq.split('|')
    num_years = len(split_seq)

    moves_in_span = {"first 6 years": [], "first 11 years": [], "first 15 years": []}

    if 15 <= num_years:
        [moves_in_span["first 15 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 15]
        [moves_in_span["first 11 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 11]
        [moves_in_span["first 6 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 6]

    elif 11 <= num_years < 15:
        moves_in_span["first 15 years"] = ''
        [moves_in_span["first 11 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 11]
        [moves_in_span["first 6 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 6]

    elif 6 <= num_years < 11:
        moves_in_span["first 15 years"] = ''
        moves_in_span["first 11 years"] = ''
        [moves_in_span["first 6 years"].append(1) for idx, elem in enumerate(split_seq) if "MB" in elem and idx < 6]

    # get the sums of moves per time interval/span
    for span, moves in moves_in_span.items():
        if type(moves) == list:
            moves_in_span[span] = str(sum(moves))

    return moves_in_span


def time_to_promotion(person_sequence):
    """
    How many years it took the person to get promoted too tribunal and court of appeals. If never promoted,
    leave empty.

    :param person_sequence: a string of elements separated by the pipe, e.g. LC-NM|LC-NM|TB-MW|TB-NM|TB-NM|CA-MB|CA-NM
    :return: 2-tuple of ints, first string is number of years to tribunal promotion, second is number of years
             to court of appeals promotion
    """
    split_seq = person_sequence.split('|')

    tb_prom = next((elem for elem in split_seq if "TB" in elem), None)
    ac_prom = next((elem for elem in split_seq if "CA" in elem), None)

    years_to_tb_prom = split_seq.index(tb_prom) if tb_prom else ''
    years_to_ac_prom = split_seq.index(ac_prom) if ac_prom else ''

    return years_to_tb_prom, years_to_ac_prom


def average_time_to_promotion(person_sequences_table):
    """
    With each person-row associate their cohort's average time to tribunal and court of appeals promotion FOR THOSE
    WHO WERE PROMOTED, i.e. this ignores those who never made those grades. Likewise, look at only those who started
    at low court, i.e. not parallel transfers from other professions.

    :param person_sequences_table: a table (as list of lists) of persons with associated sequence and career info
    :return: None, just updates the table we put in
    """
    cohort_years = {pers[1] for pers in person_sequences_table}

    # dict of cohort : cohort's average time to TB and AC promotion
    chrt_prom_dict = {chrt: {"mean TB promotion time": "NA", "mean CA promotion time": "NA"} for chrt in cohort_years}

    # sort and group the person sequences table by cohort
    person_sequences_table.sort(key=operator.itemgetter(1))  # (zero-indexed) col 1 = entry_year (i.e. cohort marker)
    cohorts = [chrt for key, [*chrt] in itertools.groupby(person_sequences_table, key=operator.itemgetter(1))]

    # now get the average time to promotion of all those promoted in each cohort
    for chrt in cohorts:
        chrt_yr = chrt[0][1]  # if they started at low court, pers[6] = =1
        times_to_tb_promotion = list(filter(None, [pers[7] for pers in chrt if pers[6] == 1]))
        times_to_ac_promotion = list(filter(None, [pers[8] for pers in chrt if pers[6] == 1]))

        # put if conditions to avoid empty lists, e.g. nobody promoted for cohort one year before right censor
        # NB: round down to integer, so when we compare own performance vs average, average is slightly inflated
        if times_to_tb_promotion:
            chrt_prom_dict[chrt_yr]["mean TB promotion time"] = int(statistics.mean(times_to_tb_promotion))
        if times_to_ac_promotion:
            chrt_prom_dict[chrt_yr]["mean CA promotion time"] = int(statistics.mean(times_to_ac_promotion))

    # now associate each row / person observation with their cohort's average promotion times
    for person in person_sequences_table:
        entry_cohort_year = person[1]
        person[9] = chrt_prom_dict[entry_cohort_year]["mean TB promotion time"]
        person[10] = chrt_prom_dict[entry_cohort_year]["mean CA promotion time"]
