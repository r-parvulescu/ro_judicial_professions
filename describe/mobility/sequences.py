"""
Functions for preparing table of career sequences, to feed into social sequence analysis.
"""

from helpers import helpers
import operator
import itertools
import statistics
import csv
from copy import deepcopy


def get_geographic_hierarchical_sequences(person_year_table, right_censor_year, profession, outdir):
    """

    FOR JUDGES AND PROSECUTORS ONLY, ONLY FROM 2006 ONWARD

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

        HC-MW = high court, move within regions (from Bucharest to the High Court, which is also in Bucharest)
        HC-MB = high court, move between regions (from the provinces to Bucharest, where the High Court is)

    The resulting sequences will look like e.g. LC-NM-LC-NM-TB-MW-TB-NM-TB-NM-CA-MB-CA-NM, where each year is
    separated by the pipe "-".

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param right_censor_year: int, the year in which we censor
    :param outdir: directory in which we want to place the data table
    :return: None
    """

    # get indices for person ID, year, ca cod, trib cod, j cod, and level code
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    gend_col_idx = helpers.get_header(profession, 'preprocess').index('sex')

    # initialise the person-sequence table
    person_sequences_table = []

    # initialise one set of personal IDs of people in two places at once, and another of people with career gaps
    two_places_at_once, career_gaps = set(), set()

    # sort people by unique ID and year, then group by unique ID
    person_year_table.sort(key=operator.itemgetter(pid_col_idx, yr_col_idx))
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # for each person
    for person in people:
        # get a sorted list of all the unique years of a person's career
        career_yrs = sorted(list({int(pers_yr[yr_col_idx]) for pers_yr in person}))
        entry_yr = career_yrs[0]

        # only consider careers starting in 2006 or later
        if 2006 <= entry_yr:
            pid = person[0][pid_col_idx]
            gndr = person[0][gend_col_idx]  # person's gender

            # if a person is in two places at once they'll have more person-years than years; save to log and skip
            if len(person) > len(career_yrs):
                two_places_at_once.add(pid)
                continue

            # if a person has fewer person-years than the span of their career, there are gaps; save to log and skip
            if len(person) < len(list(range(career_yrs[0], career_yrs[-1] + 1))):
                career_gaps.add(pid)
                continue

            # get the full sequence, and truncated at five and ten years
            geog_lvl_moves_seq = get_geog_lvl_moves_seq(person, profession)
            began_at_low_court = 1 if geog_lvl_moves_seq[:2] == "LC" else 0
            first_ten_yrs = '-'.join(geog_lvl_moves_seq.split('-')[:10]) if len(geog_lvl_moves_seq) > 54 else ''
            first_five_yrs = '-'.join(geog_lvl_moves_seq.split('-')[:5]) if len(geog_lvl_moves_seq) > 29 else ''

            between_moves = count_between_moves_in_time_interval(geog_lvl_moves_seq)

            time_to_tb_promotion, time_to_ac_promotion = time_to_promotion(geog_lvl_moves_seq)

            time_to_retirement = ''
            if entry_yr + len(geog_lvl_moves_seq.split("-")) < right_censor_year:
                time_to_retirement = len(geog_lvl_moves_seq.split("-"))

            # time to first geographic move
            frst_geog_mv = next((idx + 1 for idx, mv in enumerate(geog_lvl_moves_seq.split("-")) if mv[-2:] == "MB"),
                                "")

            person_row = [pid, entry_yr, time_to_retirement, gndr, between_moves["first 6 years"],
                          between_moves["first 11 years"], between_moves["first 15 years"], began_at_low_court,
                          time_to_tb_promotion, time_to_ac_promotion, '', '', '', '', frst_geog_mv,
                          len(geog_lvl_moves_seq.split('-')), geog_lvl_moves_seq, first_five_yrs, first_ten_yrs]

            person_sequences_table.append(person_row)

    # now for each person, mark their cohort's average time to tribunal and court of appeals promotion
    average_time_to_promotion(person_sequences_table)

    # mark career stars
    career_star(person_sequences_table)

    # write the person-sequence table to disk as a csv
    header = ["pid", "entry_year", "time_to_retirement", "gender", "region_moves_first_6_yrs",
              "region_moves_first_11_yrs", "region_moves_first_15_yrs", "began_at_LC", "time_to_tb_prom",
              "time_to_ca_prom", "cohort_avg_time_to_tb_prom", "cohort_avg_time_to_ca_prom", "tb_career_star",
              "ca_career_star", "time_to_first_geog_move", "sequence_career_length", "geog_lvl_moves_sequence",
              "first_ten_yrs_seq", "first_five_yrs_seq"]
    with open(outdir + "sequences_data_table.csv", 'w') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        [writer.writerow(pers_seq) for pers_seq in person_sequences_table]

    # write out a log with metrics of the full person sequences,
    # so we know what, which, and why we exclude some observations
    with open(outdir + "sequences_log.csv", 'w') as out_log:
        seq_log = []
        log_writer = csv.writer(out_log)
        # for each column containing sequences, get element frequencies
        element_frequencies(person_sequences_table, seq_log)
        [log_writer.writerow(row) for row in seq_log]
        log_writer.writerow([])
        # then mark the number and IDs of people excluded because their careers are glitchy
        log_writer.writerow(["NUMBER OF PERSONS EXCLUDED BECAUSE THEY'RE IN TWO PLACES AT ONCE & THEIR IDS"])
        log_writer.writerow([len(two_places_at_once)]), log_writer.writerow([pid for pid in two_places_at_once])
        log_writer.writerow(["NUMBER OF PERSONS EXCLUDED BECAUSE THEY HAVE CAREER GAPS & THEIR IDS"])
        log_writer.writerow([len(career_gaps)]), log_writer.writerow([pid for pid in career_gaps])


def get_geog_lvl_moves_seq(pers, profession):
    """
    Given a person's collection of person years, returns a sequence of geographic moves - hierarchical level.

    :param pers: list of person-years, sorted by years (in increasing order) and sharing a unique person-ID
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: str, sequence of geographic moves - hierarchical position with elements separated by a hyphen ("-"),
                  e.g. LC-NM-LC-NM-TB-MW-TB-NM-TB-NM-CA-MB-CA-NM
    """

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_col_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    trib_col_idx = helpers.get_header(profession, 'preprocess').index('trib cod')
    j_col_idx = helpers.get_header(profession, 'preprocess').index('jud cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the person by year
    pers.sort(key=operator.itemgetter(yr_col_idx))

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

            mov_seq.append(level_codes[this_yr_lvl] + '+' + geog_move)

    # return sequence as string, with year elements divided by the "-" hyphen
    return '-'.join(mov_seq)


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

    split_seq = geog_lvl_moves_seq.split('-')
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

    :param person_sequence: a string of elements separated by the pipe, e.g. LC-NM-LC-NM-TB-MW-TB-NM-TB-NM-CA-MB-CA-NM
    :return: 2-tuple of ints, first string is number of years to tribunal promotion, second is number of years
             to court of appeals promotion
    """
    split_seq = person_sequence.split('-')

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

    # now get the average time to promotion of all those promoted in each cohort, ONLY counting those people whose
    # careers started at low court, ergo avoiding those who transfered into the profession laterally
    for chrt in cohorts:
        chrt_yr = chrt[0][1]
        # if they started at low court, pers[7] == 1
        # person[8] = time to TB promotion, person[9] = time to CA promotion
        times_to_tb_promotion = list(filter(None, [pers[8] for pers in chrt if pers[7] == 1]))
        times_to_ca_promotion = list(filter(None, [pers[9] for pers in chrt if pers[7] == 1]))

        # put if conditions to avoid empty lists, e.g. nobody promoted for cohort one year before right censor
        # NB: round down to integer, so more harsh comparison o own performance vs average
        if times_to_tb_promotion:
            chrt_prom_dict[chrt_yr]["mean TB promotion time"] = int(statistics.mean(times_to_tb_promotion))
        if times_to_ca_promotion:
            chrt_prom_dict[chrt_yr]["mean CA promotion time"] = int(statistics.mean(times_to_ca_promotion))

    # now associate each row / person observation with their cohort's average promotion times
    for person in person_sequences_table:
        entry_cohort_year = person[1]
        person[10] = chrt_prom_dict[entry_cohort_year]["mean TB promotion time"]
        person[11] = chrt_prom_dict[entry_cohort_year]["mean CA promotion time"]


def career_star(person_sequences_table):
    """
    Add indicator for whether a person is a tribunal career star climber or a court of appeals star climber.
    :param person_sequences_table:
    :return: None, just update an existing table
    """
    # person[8] is time to TB promotion, person[9] time to CA promotion, person[10] is cohort's average time to TB
    # promotion, and person[11] is cohort's average time to CA promotion

    # person[12] is the indicator for TB career star, person[13] the indicator for CA career star
    for person in person_sequences_table:

        if person[8] and person[10] != "NA":  # need this condition since not all people climb the ladder
            person[12] = 1 if person[8] < person[10] else 0
        else:
            person[12] = 0

        if person[9] and person[11] != "NA":  # need this condition since not all people climb the ladder
            person[13] = 1 if person[9] < person[11] else 0
        else:
            person[13] = 0


def element_frequencies(person_sequences_table, sequences_log):
    """
    In a sequence log, add rows indicating the frequency distribution of elements for full sequences, truncated
    first ten-year sequences, and truncated first five-year sequences. Sort that list by frequency in decreasing order.

    :param person_sequences_table: a table (as list of lists) of persons with associated sequence and career info
    :param sequences_log: list, a log where we record such metrics, which will get written as csv for visual inspection
    :return: None, just updates the table we put in
    """

    elem_freq_dict = {"LC+NM": 0, "TB+NM": 0, "CA+NM": 0, "HC+NM": 0, "LC+MW": 0, "TB+MW": 0, "CA+MW": 0,
                      "LC+MB": 0, "TB+MB": 0, "CA+MB": 0, "HC+MB": 0, "HC+MW": 0}

    elem_freqs = []

    # the last three columns of the table contain sequences, so calculate element frequences for each column
    for idx in [-3, -2, -1]:
        local_elem_freq_dict = deepcopy(elem_freq_dict)
        for row in person_sequences_table[1:]:  # skip the header
            seq = row[idx]
            for elem in seq.split("-")[1:]:  # the first element (e.g. "LC") does not have a move value by definition
                local_elem_freq_dict[elem] += 1
        freqs = sorted(list(local_elem_freq_dict.items()), key=operator.itemgetter(1), reverse=True)
        elem_freqs.append(freqs)

    # now add these frequencies to the end of the table
    sequences_log.append([])
    sequences_log.append(["Full Sequences: Element Frequencies"]), sequences_log.append(elem_freqs[0])
    sequences_log.append(["First Five Years: Element Frequencies"]), sequences_log.append(elem_freqs[1])
    sequences_log.append(["First Ten Years: Element Frequencies"]), sequences_log.append(elem_freqs[2])
