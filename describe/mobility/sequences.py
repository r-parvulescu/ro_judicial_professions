"""
Functions for preparing table of career sequences, to feed into social sequence analysis.
"""

from helpers import helpers
import operator
import itertools
from collections import Counter
import statistics
import csv
from copy import deepcopy


def get_geographic_hierarchical_sequences(person_year_table, profession, outdir):
    """
    FOR JUDGES AND PROSECUTORS ONLY

    Makes a table with these columns:
        col 1  = person ID
        col 2 = cohort, i.e. first year in career
        col 3 = gender
        col 4 = length of career (in years)
        col 5 = began at low court
        col 6 = time to retirement (if occured)
        col 7 = time to tribunal promotion (if occurred)
        col 8 = time to court of appeals promotion (if occurred)
        col 9 = time to high court promotion (if occurred)
        col 10 = time to first regional moves (if occurred)
        col 11 = own cohort's average time to retirement (of those that retired)
        col 12 = own cohort's average time to tribunal promotion (of those that were thus promoted)
        col 13 = own cohort's average time to court of appeals promotion (of those that were thus promoted)
        col 14 = own cohort's average time to high court of promotion (of those that were thus promoted)
        col 15 = own cohort's average time to first region move (if occurred)
        col 16 = number of region changes in first 5 years on the job
        col 17 = number of region changes in first 10 years on the job
        col 18 = number of region changes in whole career
        col 19 = whole career sequence of hierarchical states
        col 20 = whole career sequence of relative regional location (explained below)
        col 21 = whole career, two-channel sequence of hierarchical - relative region locations (explained below)
        col 22 = reverse order, whole career, two channel sequence (i.e. going from end of career to beginning)
        col 23 = normal order, two-channel sequence, truncated at 10 years
        col 24 = normal order, two-channel sequence, truncated at five years

    The hierarchical position code shows where in the judicial hierarchy the person is. The elements are:
    LC = municipal, low court, TB = county tribunal, CA = regional court of appeals, HC = national high court.

    The relative regional location code shows where a person was relative to the first region in which they are
    observed. Regions are defined as court of appeals jurisdictions. Everyone's starting region is "1", then if they
    move to another court of appeals jurisdiction they get the label "2", and get the label "3" if they move to a third
    region. If they move to a fourth, fifth, sixth, etc. region they get the label "4+". So the alphabet is 4-long.
    Note that if a person's sequence is something like "1-2-2-2-2-1-1-1" it means that they left their home region,
    stayed in a second region for a while, then returned to their home region.

    NB: the sequences_log file actually records how many people are observed having moved to 4, 5, 6, etc. regions so
        we can see in greater detail if need be

    We then combine these two element sets (alphabet expansion) to create the final set of elements that we use to
    construct the multi-channel sequences. Below are some examples, the rest follow logically:
        LC+1 = low court, first region ; TB+2 = tribunal, second region; CA+3 = court of appeals, third region

    The sequences will look like e.g. LC+1-LC+1-TB+1-TB+2-TB+2, where each year is separated by a dash ("-").

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors"
    :param outdir: directory in which we want the data and log files to live
    :return: None
    """

    # get indices for person ID, year, and gender
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    gend_col_idx = helpers.get_header(profession, 'preprocess').index('sex')

    years = {pers_yr[yr_col_idx] for pers_yr in person_year_table}
    right_censor_year = max({pers_yr[yr_col_idx] for pers_yr in person_year_table})

    # initialise the person-sequence table
    person_sequences_table = []

    # initialise one set of personal IDs of people in two places at once, and another of people with career gaps
    two_places_at_once, career_gaps = set(), set()

    # initialise a dict of cohorts and mean times to events per cohort
    time_to_event_dict = {"TB times": [], "CA times": [], "HC times": [], "ret times": [], "geog move times": []}
    chrt_time_to_event_dict = {chrt: deepcopy(time_to_event_dict) for chrt in years}

    # initialise sequences pools; we'll use these for calculating element frequencies
    hierar_pool, rel_reg_pool, twochannel_pool = [], [], []

    # sort people by unique ID and year, then group by unique ID
    person_year_table.sort(key=operator.itemgetter(pid_col_idx, yr_col_idx))
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # for each person
    for person in people:
        entry_yr = person[0][yr_col_idx]
        pid = person[0][pid_col_idx]
        gndr = person[0][gend_col_idx]

        # remove people with weird careers that indicate some underlying coding errors

        # get a sorted list of all the unique years of a person's career
        career_yrs = sorted(list({int(pers_yr[yr_col_idx]) for pers_yr in person}))
        # if a person is in two places at once they'll have more person-years than years; save to log and skip
        if len(person) > len(career_yrs):
            two_places_at_once.add(pid)
            continue
        # if a person has fewer person-years than the span of their career, there are gaps; save to log and skip
        if len(person) < len(list(range(career_yrs[0], career_yrs[-1] + 1))):
            career_gaps.add(pid)
            continue

        # get sequences
        pers_measures = get_person_measures(person, profession, right_censor_year)
        hierar_seq = pers_measures["hierar seq"]
        rel_reg_seq = pers_measures["rel reg seq"]
        twochannel_seq = [i[0] + "+" + str(i[1]) for i in list(zip(hierar_seq, rel_reg_seq))]
        twochannel_reverse = twochannel_seq[::-1]
        twochannel_trunc_ten = twochannel_seq[:10]
        twochannel_trunc_five = twochannel_seq[:5]

        # add indicator for whether a person began their career at low court (if not, they came extraprofessionally)
        began_at_low_court = 1 if hierar_seq[0] == "LC" else 0

        # add the base sequences to their respective pools
        hierar_pool.extend(hierar_seq), rel_reg_pool.extend(rel_reg_seq), twochannel_pool.extend(twochannel_seq)

        # turn your sequences to strings , with elements separated by a hyphen ("-")
        hierar_seq, rel_reg_seq, twochannel_seq = "-".join(hierar_seq), "-".join(rel_reg_seq), "-".join(twochannel_seq)
        twochannel_reverse, twochannel_trunc_five = "-".join(twochannel_reverse), "-".join(twochannel_trunc_five)
        twochannel_trunc_ten = "-".join(twochannel_trunc_ten)

        # get metrics on movement between geographic regions
        reg_movs = pers_measures["num reg moves total"]
        reg_movs_first_ten = pers_measures["num reg moves first 10"]
        reg_movs_first_five = pers_measures["num reg moves first 5"]

        # update the person-measures-per-cohort lists
        chrt_time_to_event_dict[entry_yr]["ret times"].append(pers_measures["time to ret"])
        chrt_time_to_event_dict[entry_yr]["TB times"].append(pers_measures["time to tb"])
        chrt_time_to_event_dict[entry_yr]["CA times"].append(pers_measures["time to ca"])
        chrt_time_to_event_dict[entry_yr]["HC times"].append(pers_measures["time to hc"])
        chrt_time_to_event_dict[entry_yr]["geog move times"].append(pers_measures["time to first geog move"])

        person_row = [pid, entry_yr, gndr, len(person), began_at_low_court,
                      pers_measures["time to ret"], pers_measures["time to tb"], pers_measures["time to ca"],
                      pers_measures["time to hc"], pers_measures["time to first geog move"],
                      "", "", "", "", "",
                      reg_movs_first_five, reg_movs_first_ten, reg_movs,
                      hierar_seq, rel_reg_seq, twochannel_seq, twochannel_reverse,
                      twochannel_trunc_ten, twochannel_trunc_five]

        person_sequences_table.append(person_row)

    # for each person observation, mark down that person's cohort's time-to-event, if applicable
    update_average_time_to_event(person_sequences_table, chrt_time_to_event_dict)

    # write the person-sequence table to disk as a csv
    header = ["pid", "entry_yr", "gender", "career_length", "start_lc",
              "time_to_ret", "time_to_tb", "time_to_ca", "time_to_hc", "time_to_first_reg_move",
              "chrt_avg_time_ret", "chrt_avg_time_tb", "chrt_avg_time_ca",
              "chrt_avg_to_hc", "chrt_avg_time_first_reg_move",
              "reg_mov_first_5_yrs", "reg_mov_first_10_yrs", "reg_mov_total",
              "hierar_seq", "rel_reg_seq", "multi_seq", "rev_multi_seq", "multi_sec_10", "multi_seq_5"]

    # write the sequences data table to disk
    with open(outdir + "sequences_data_table.csv", 'w') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        [writer.writerow(pers_seq) for pers_seq in person_sequences_table]

    # make the log file
    make_log(hierar_pool, rel_reg_pool, twochannel_pool, two_places_at_once, career_gaps, outdir)


def get_person_measures(pers, profession, right_censor_year):
    """
    Given a person's collection of person years, returns a dict with:
     - number of regional moves in first five years of career
     - number of regional moves in first ten years of career
     - number of regional moves in all career
     - person's hierarchical state sequence
     - person's sequence of relative appellate region moves

    :param pers: list of person-years sharing a unique person-ID
    :param profession: string, "judges", "prosecutors"
    :param right_censor_year: int, year in which we stop observing
    :return: dict
    """

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_col_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the person by year
    pers.sort(key=operator.itemgetter(yr_col_idx))

    # get the sequence of hierarchical states
    level_codes_dict = {"1": "LC", "2": "TB", "3": "CA", "4": "HC"}
    hierar_seq = [level_codes_dict[pers_yr[lvl_col_idx]] for pers_yr in pers]

    # now get the sequence of relative region moves
    # first get a dict where region codes are keys and the order of that region's first appearance is the value
    rel_reg_dict = {}
    counter = 1
    for pers_yr in pers:
        if pers_yr[ca_col_idx] not in rel_reg_dict:
            rel_reg_dict[pers_yr[ca_col_idx]] = counter
            counter += 1
    rel_reg_seq = [str(rel_reg_dict[pers_yr[ca_col_idx]]) for pers_yr in pers]

    # the number of regional moves is simply the number of distinct spells in the relative region sequence
    # need to substract 1 since no moving still generates one entry, hence one group
    num_reg_moves_first_five = len([k for k, g in itertools.groupby(rel_reg_seq[:5])]) - 1
    num_reg_moves_first_ten = len([k for k, g in itertools.groupby(rel_reg_seq[:10])]) - 1
    num_reg_moves_total = len([k for k, g in itertools.groupby(rel_reg_seq)]) - 1

    # get times to events
    time_to_ret = len(pers) if pers[-1][yr_col_idx] != right_censor_year else None
    time_to_tb = hierar_seq.index("TB") if "TB" in hierar_seq else None
    time_to_ca = hierar_seq.index("CA") if "CA" in hierar_seq else None
    time_to_hc = hierar_seq.index("HC") if "HC" in hierar_seq else None
    time_to_first_geog_move = next((i for i in range(1, len(rel_reg_seq)) if rel_reg_seq[i] != rel_reg_seq[i - 1]),
                                   None)

    return {"time to ret": time_to_ret, "time to tb": time_to_tb, "time to ca": time_to_ca, "time to hc": time_to_hc,
            "time to first geog move": time_to_first_geog_move, "num reg moves first 5": num_reg_moves_first_five,
            "num reg moves first 10": num_reg_moves_first_ten, "num reg moves total": num_reg_moves_total,
            "hierar seq": hierar_seq, "rel reg seq": rel_reg_seq}


def update_average_time_to_event(person_sequences_table, chrt_time_to_event_dict):
    """
    With each person-row, if that person experiencede event X then put in the average time-to-event across their
    cohort.

    :param person_sequences_table: a table (as list of lists) of persons with associated sequence and career info
    :param chrt_time_to_event_dict: dict where first level is cohort, second level is event type, and values are
                                    times to event
    :return: None, just updates the table we put in
    """
    # first, evaluate the lists of times into averages
    for cohort, times_dicts in chrt_time_to_event_dict.items():
        for event in times_dicts:
            if list(filter(None, times_dicts[event])):
                # I round down to the integer so that when comparing own time to event to cohort's, the comparison
                # is particularly strict vis-a-vis whether one outperforms own cohort
                times_dicts[event] = int(statistics.mean(list(filter(None, times_dicts[event]))))

    for person_row in person_sequences_table:
        chrt = person_row[1]  # the persons's cohort in in person_row[1]
        if person_row[5]:  # time to retirement is in person_row[5]
            if person_row[5] < chrt_time_to_event_dict[chrt]["ret times"]:
                person_row[10] = chrt_time_to_event_dict[chrt]["ret times"]
        if person_row[6]:  # time to tribunal promotion is in person_row[6]
            if person_row[6] < chrt_time_to_event_dict[chrt]["TB times"]:
                person_row[11] = chrt_time_to_event_dict[chrt]["TB times"]
        if person_row[7]:  # time to court of appeals promotion is in person_row[7]
            if person_row[7] < chrt_time_to_event_dict[chrt]["CA times"]:
                person_row[12] = chrt_time_to_event_dict[chrt]["CA times"]
        if person_row[8]:  # time to high court promotion is in person_row[8]
            if person_row[8] < chrt_time_to_event_dict[chrt]["CA times"]:
                person_row[13] = chrt_time_to_event_dict[chrt]["CA times"]
        if person_row[9]:  # time to first geographic move is in person_row[9]
            if person_row[9] < chrt_time_to_event_dict[chrt]["geog move times"]:
                person_row[14] = chrt_time_to_event_dict[chrt]["geog move times"]


def make_log(hierar_pool, rel_reg_pool, twochannel_pool, two_places_at_once, career_gaps, outdir):
    """
    Write to disk a sequences log file showing
    a) the element distributions, for the separate and multichannel sequences
    b) how many people were dropped because they were in two places at the same time
    c) how many people were dropped because they had career gaps

    :param hierar_pool: list, contains all elements from all hierarchical position state sequences
    :param rel_reg_pool: list, contains all elements from all relative region position state sequences
    :param twochannel_pool: list, contains all elements from all two-channel position state sequences
    :param two_places_at_once: set, contains the unique IDs of all people who were in two places at once
    :param career_gaps: set, contains the unique IDs of all people with career gaps
    :param outdir: str, path to the directory in which we want the logfile to live
    :returns: None, just writes to disk
    """

    # get the element frequencies, in decreasing order
    hierar_e_freqs = sorted(list(dict(Counter(hierar_pool)).items()), key=operator.itemgetter(1), reverse=True)
    rel_reg_e_freqs = sorted(list(dict(Counter(rel_reg_pool)).items()), key=operator.itemgetter(1), reverse=True)
    twochannel_e_freqs = sorted(list(dict(Counter(twochannel_pool)).items()), key=operator.itemgetter(1), reverse=True)

    with open(outdir + "sequences_log.csv", 'w') as out_log:
        log_writer = csv.writer(out_log)
        # mark down element frequencies
        log_writer.writerow(["HIERARCHICAL SEQUENCE ELEMENT FREQUENCIES"]), log_writer.writerow(hierar_e_freqs)
        log_writer.writerow(["RELATIVE REGION SEQUENCE ELEMENT FREQUENCIES"]), log_writer.writerow(rel_reg_e_freqs)
        log_writer.writerow(["TWO-CHANNEL SEQUENCE ELEMENT FREQUENCIES"]), log_writer.writerow(twochannel_e_freqs)
        log_writer.writerow([])
        # then mark the number and IDs of people excluded because their careers are glitchy
        log_writer.writerow(["NUMBER OF PERSONS EXCLUDED BECAUSE THEY'RE IN TWO PLACES AT ONCE & THEIR IDS"])
        log_writer.writerow([len(two_places_at_once)]), log_writer.writerow([pid for pid in two_places_at_once])
        log_writer.writerow(["NUMBER OF PERSONS EXCLUDED BECAUSE THEY HAVE CAREER GAPS & THEIR IDS"])
        log_writer.writerow([len(career_gaps)]), log_writer.writerow([pid for pid in career_gaps])
