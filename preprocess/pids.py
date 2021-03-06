"""
Assign each person-year a unique, person-level ID.
"""

import operator
import itertools
import pandas as pd
import copy


def pids(person_year_table, profession, pids_log_path):
    """
    Takes a table of person years, cleans it to make sure nobody is in two or more places at once, interpolates missing
    person-years, assigns each person-year a unique person-level ID, and returns the updated table.

    :param person_year_table: a table of person-years as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param pids_log_path: path where the logs from pids will live
    :return: a person-year table without overlaps, with interpolated person-years, and with unique person IDs
    """

    # initiaite a log of changes
    change_log = []

    # remove overlaps so no person is in 2+ places in one year
    print("     NUMBER OF PERSON-YEARS GOING IN: ", len(person_year_table))
    change_log.append(["NUMBER OF PERSON-YEARS GOING INTO CORRECT_OVERLAPS: ", len(person_year_table)])
    distinct_persons = correct_overlaps(person_year_table, profession, change_log, pids_log_path)

    # print and save some diagnostics
    print("INTERPOLATE PERSON YEARS")

    # interpolate person-years that are missing for spurious reasons
    distinct_persons = interpolate_person_years(distinct_persons, change_log)

    # give each person-year a person-year ID
    person_year_table_with_pids = unique_person_ids(distinct_persons, change_log)

    # since we've added and removed rows, we need to update the row IDs
    person_year_table_with_pids = [[idx] + row[1:] for idx, row in enumerate(person_year_table_with_pids)]

    # write to disk the change log
    change_log = pd.DataFrame(change_log)
    change_log_out_path = pids_log_path + profession + '_pids_change_log.csv'
    change_log.to_csv(change_log_out_path)

    # and return the person-year table without overlaps, with interpolated values, and with person-level IDs,
    # sorted by surname, given name, and year
    return person_year_table_with_pids


def correct_overlaps(person_year_table, profession, change_log, pids_log_path):
    """
    NB: !! this code only applies to person-year tables !! DO NOT APPLY TO PERSON MONTH TABLES

    NB: !! only do this for complete data, i.e. 2005 and later !!! WILL BE TOO GLITCHY ON INCOMPLETE DATA

    Sometimes we notice that a person is in two or more places at the same time. This can mean that

    a) two or more people share a name

    b) irregular/unusual book-keeping; common reasons for this include
        i) someone is added to the books of the new workplace BEFORE being taken off the rolls of the old workplace
        ii) being delegated from your workplace to another for a short period, so even though you work in each place
        several months, on the year level it will look like you were in two places at once

    We can distinguish between these scenarios by considering the length and the context of the overlap.

    1) if a person is in two or more places for 3+ years, it likely indicates a multiple people with shared a name,
    i.e. case a). Two years of allowable overlap might seem like a lot, but a transition mistake (as in b.i) only needs
    to get made for two calendar months (Dec and Jan), and for us to have gotten unlucky with month sampling,
    to generate a spurious two-year overlap.

    2) if the overlap is 1-2 years, and is located at the transition between workplaces, it's probably a
        book-keeping mistake as in b.i

    3) if the overlap is 1-2 years and does NOT mark a transition, it's probably a delegation period (case b.ii)

    4) if the overlap is 1-2 years and occurs at the edge of our observed sequences, it could either be situation (2)
       above (since we may not have observed the start or end state) or situation (3) above (since the delegation might
       fall at the edge of our observation period)

    All these cases are covered by the vignettes below -- I reference to these in code comments.

    (A)  ONE YEAR OVERLAP, MID SEQUENCE                      (B)  TWO YEAR OVERLAP, MID SEQUENCE

    SURNAME    GIVEN NAME   INSTITUTION   YEAR               SURNAME    GIVEN NAME  INSTITUTION    YEAR

    DERP       BOB JOE      ALPHA         2012               DERP       BOB JOE     ALPHA          2012
    DERP       BOB JOE      ALPHA         2013               DERP       BOB JOE     ALPHA          2013
    DERP       BOB JOE      BETA          2013               DERP       BOB JOE     BETA           2013
    DERP       BOB JOE      BETA          2014               DERP       BOB JOE     ALPHA          2014
    DERP       BOB JOE      BETA          2015               DERP       BOB JOE     BETA           2014
    DERP       BOB JOE      BETA          2016               DERP       BOB JOE     BETA           2015

    Note that for (ii) to hold we need to observe a sending and receiving workplace. Cases (C), (D), and (E) below
    would NOT fall under the ambit of situation (ii), because we can't observe both sending and receiving workplaces.

    (C)  ONE YEAR OVERLAP, START SEQUENCE                    (D)  ONE YEAR OVERLAP, END SEQUENCE

    SURNAME    GIVEN NAME   INSTITUTION   YEAR               SURNAME    GIVEN NAME  INSTITUTION    YEAR

    DERP       BOB JOE      ALPHA         2012               DERP       BOB JOE     BETA           2012
    DERP       BOB JOE      BETA          2012               DERP       BOB JOE     BETA           2013
    DERP       BOB JOE      BETA          2013               DERP       BOB JOE     BETA           2014
    DERP       BOB JOE      BETA          2014               DERP       BOB JOE     BETA           2015
    DERP       BOB JOE      BETA          2015               DERP       BOB JOE     ALPHA          2015

    (E)  TWO YEAR OVERLAP, FULL SEQUENCE                    (F)  ONE YEAR OVERLAP, 3+ PLACES

    SURNAME    GIVEN NAME   INSTITUTION   YEAR              SURNAME    GIVEN NAME  INSTITUTION     YEAR

    DERP       BOB JOE     ALPHA          2012              DERP        BOB JOE     ALPHA           2012
    DERP       BOB JOE     BETA           2012              DERP        BOB JOE     ALPHA           2013
    DERP       BOB JOE     ALPHA          2013              DERP        BOB JOE     BETA            2013
    DERP       BOB JOE     BETA           2013              DERP        BOB JOE     GAMMA           2013
                                                            DERP        BOB JOE     BETA            2014

    (G)  THREE PLUS YEAR OVERLAP                            (H) TWO YEAR OVERLAP, NO TRANSITION

    SURNAME    GIVEN NAME   INSTITUTION   YEAR              SURNAME    GIVEN NAME  INSTITUTION     YEAR

    DERP       BOB JOE     ALPHA          2012              DERP        BOB JOE     ALPHA           2012
    DERP       BOB JOE     BETA           2012              DERP        BOB JOE     ALPHA           2013
    DERP       BOB JOE     ALPHA          2013              DERP        BOB JOE     BETA            2013
    DERP       BOB JOE     BETA           2013              DERP        BOB JOE     ALPHA           2014
    DERP       BOB JOE     ALPHA          2014              DERP        BOB JOE     BETA            2014
    DERP       BOB JOE     BETA           2014              DERP        BOB JOE     ALPHA           2015


    This function is built to remove overlaps in such a way that estimates of inter-year mobility are reduced,
    i.e. that we get conservative estimates of mobility. So when we have a choice as to which person-years to remove or
    split to remove the overlap, we go with that choice which will lead to less mobility being observed.

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param change_log: a list (to be written as a csv) marking the before and after states of the person-sequence
    :param pids_log_path: path where the logs from pids will live
    :return: a list of distinct persons, i.e. of person-sequences that feature no overlaps; this is a triple nested
             list: of person-sequences, which is made up of person-years, each of which is a list of person-year data
    """

    # mark where this function begins in the change log
    print("CORRECT_OVERLAPS")
    change_log.extend([['\n'], ['CORRECT OVERLAPS'], ['\n']])

    # sort the data by surname and given name
    person_year_table.sort(key=operator.itemgetter(1, 2, 5))  # surname = row[1], given name = row[2], year = row[5]

    # group data by surname and given name
    person_sequences = [group for k, [*group] in itertools.groupby(person_year_table, key=operator.itemgetter(1, 2))]

    # initialise a table of distinct persons; a three level list: a list of persons, each containing a list of
    # person-years (i.e. rows), and each row is a list
    distinct_persons = []

    # initialise tables of unusual person-sequences that need special treatment; we inspect these tables visually
    three_place_person_sequences = []
    unable_to_split_person_sequences = []
    filter_slip_person_sequences = []

    # initiate a counter to keep track of how many person years are add/removed by this function
    net_person_years = 0

    for ps in person_sequences:

        # initialise a dict of years and the workplace(s) associated with each year
        years_and_workplaces = {row[5]: [] for row in ps}  # row[5] =  year

        # initialise a set that marks which year-workplace combinations should be removed to eliminate the overlap
        to_remove = set()

        # workplace overlap exists when there are fewer years than rows (since each row is a person-year)
        if len(years_and_workplaces) < len(ps):

            # associate workplaces with years

            # if dealing with judges or prosecutors, use the workplace info in row[4]
            if profession == 'judges' or profession == 'prosecutors':
                [years_and_workplaces[row[5]].append(row[4]) for row in ps]  # row[4] = workplaces
            else:  # we're dealing with notaries and executori, use town info in row[7]
                [years_and_workplaces[row[5]].append(row[7]) for row in ps]

            # CASE (F)
            # if one year features 3+ workplaces, run it through a corrector filter
            if max([len(v) for v in years_and_workplaces.values()]) > 2:
                three_plus_workplaces_to_remove = three_plus_workplaces_handle(ps, years_and_workplaces)

                # if the filter picks something up, incorporate its removal orders into the master to_remove set
                if three_plus_workplaces_to_remove:
                    [to_remove.add(tr) for tr in three_plus_workplaces_to_remove]

                # else, if the filter didn't pick anything up, save person sequence visual inspection and leave as is
                else:
                    [three_place_person_sequences.append(py) for py in ps]
                    three_place_person_sequences.append(['\n'])
                    distinct_persons.append(ps)

                continue

            else:  # no year features more than two institutions

                # CASE (G)
                # if the overlap is of 3+ years IN A CONTIGUOUS BLOCK, split up the person-year
                # NB: if we have non-contiguous sets of one- or two-year overlaps, but the total number of
                # overlap years is greater than two, just treat each overlap separately

                if len(ps) - len(years_and_workplaces) > 2:
                    sequences_split = split_sequences(profession, ps, change_log, unable_to_split_person_sequences)
                    if sequences_split:
                        distinct_persons.extend(sequences_split)
                    continue

                else:  # the overlaps are of one or two years

                    # isolate the overlap years
                    overlap_years = {yr: wrk_plcs for yr, wrk_plcs in years_and_workplaces.items()
                                     if len(wrk_plcs) > 1}

                    # if the overlap is in the middle of the person-sequence
                    if min(overlap_years) > min(years_and_workplaces) \
                            and max(overlap_years) < max(years_and_workplaces):

                        # CASES (A) AND (B)
                        # if the overlap marks a transition
                        transition = if_transition(years_and_workplaces, overlap_years)
                        if transition['transition']:
                            # mark for removal the rows which match the receiving/destination workplace
                            # keeping the sending workplace is arbitrary, it only matters that the
                            # choice be applied consistently
                            for ovrlp_yr in overlap_years:
                                to_remove.add(str(ovrlp_yr) + '-' + transition['workplace_after'])

                        # CASE (H)
                        # no transition, a blip in an otherwise continuous workplace sequence
                        # throw out the blip
                        else:
                            for yr, wrk_plc in overlap_years.items():
                                for wp in wrk_plc:
                                    if wp != transition['workplace_before']:
                                        to_remove.add(str(yr) + '-' + wp)

                    else:  # the overlap is at one or both boundaries

                        # CASES (E)  OR (H)
                        # if overlap is on both boundaries
                        if min(overlap_years) == min(years_and_workplaces) \
                                and max(overlap_years) == max(years_and_workplaces):
                            # mark for removal the workplace in the first row
                            # this choice is arbitrary, it only matters that it be applied consistently
                            first_workplace = ps[0][4] if profession == 'judges' or profession == 'prosecutors' \
                                else ps[0][7]
                            [to_remove.add(str(yr) + '-' + first_workplace) for yr in overlap_years]

                        # CASES (C) OR (H)
                        # if the overlap is only on the lower boundary,
                        elif min(overlap_years) == min(years_and_workplaces) \
                                and max(overlap_years) < max(years_and_workplaces):

                            # keep only the workplace we transition TO, so throw out the sending workplaces
                            # this eliminates one mobility event

                            # get the destination year-workplace
                            sorted_overlap_years = sorted(list(overlap_years))
                            sorted_total_years = sorted(list(years_and_workplaces))

                            last_overlap_year = sorted_overlap_years[-1]
                            last_overlap_year_idx = sorted_total_years.index(last_overlap_year)
                            first_year_after = sorted_total_years[last_overlap_year_idx + 1]
                            destination_workplace = years_and_workplaces[first_year_after][0]

                            # and mark for removal the years with the sending workplace
                            for yr, wrk_plc in overlap_years.items():
                                for wp in wrk_plc:
                                    if wp != destination_workplace:
                                        to_remove.add(str(yr) + '-' + wp)

                        # CASES (D) OR (H)
                        # if the overlap is only on the upper boundary
                        elif max(overlap_years) == max(years_and_workplaces) \
                                and min(overlap_years) > min(years_and_workplaces):

                            # keep only the workplace we transition FROM, so throw out the destination workplaces
                            # this eliminates one mobility event

                            # get the sending year-workplace
                            sorted_overlap_years = sorted(list(overlap_years))
                            sorted_total_years = sorted(list(years_and_workplaces))

                            first_overlap_year = sorted_overlap_years[0]
                            first_overlap_year_idx = sorted_total_years.index(first_overlap_year)
                            year_before = sorted_total_years[first_overlap_year_idx - 1]
                            sending_workplace = years_and_workplaces[year_before][0]

                            # and mark for removal the years with the destination workplace
                            for yr, wrk_plc in overlap_years.items():
                                for wp in wrk_plc:
                                    if wp != sending_workplace:
                                        to_remove.add(str(yr) + '-' + wp)

                        else:
                            # the person-sequence has slipped through the filters, save for visual inspection
                            filter_slip_person_sequences.append(ps)

            # now apply the removal orders to the person sequences, to remove the overlaps

            # the new person-sequence, without overlaps
            new_ps = []
            for pers_yr in ps:
                workplace = pers_yr[4] if profession == 'judges' or profession == 'prosecutors' \
                    else pers_yr[7]

                if str(pers_yr[5]) + '-' + workplace not in to_remove:  # the year-workplace combination
                    new_ps.append(pers_yr)

            # and add the new person-sequence to the list of distinct persons
            distinct_persons.append(new_ps)

            # keep track of the changes, so we can inspect visually and make sure it's behaving correctly

            # sort by surname, given name, and year
            ps.sort(key=operator.itemgetter(1, 2, 5)), new_ps.sort(key=operator.itemgetter(1, 2, 5))

            # we want a double-column csv file:
            # old person-sequence in first column, no-overlap sequence in second column
            for idx, pers_yr in enumerate(ps):
                if idx < len(new_ps):

                    # handle the fact that the judges/prosecutors and executori/notaries tables are shaped differently
                    if profession == 'judges' or profession == 'prosecutors':
                        change_log.append(pers_yr[1:3] + pers_yr[4:6] + ['', ''] + new_ps[idx][1:3] + new_ps[idx][4:6])
                    else:
                        change_log.append(pers_yr[1:3] + pers_yr[5:8] + ['', ''] + new_ps[idx][1:3] + new_ps[idx][5:8])

                else:  # when the old sequence surpases the new
                    if profession == 'judges' or profession == 'prosecutors':
                        change_log.append(pers_yr[1:3] + pers_yr[4:6])
                    else:
                        change_log.append(pers_yr[1:3] + pers_yr[5:8])

            change_log.append(['\n'])

            # and update the counter of net person-years
            net_person_years += len(new_ps) - len(ps)

        else:  # add all the person-year sequences with no overlap years as they are to the list of distinct persons
            distinct_persons.append(ps)

    # write to disk tables of odd sequences, those in 3+ plus places at once and which slipped through all filters

    three_place_seqs = pd.DataFrame(three_place_person_sequences)
    three_place_seqs_path = pids_log_path + profession + '_pids_three_place_person_sequences.csv'
    three_place_seqs.to_csv(three_place_seqs_path)

    filter_slip_seqs = pd.DataFrame(filter_slip_person_sequences)
    filter_slip_seqs_path = pids_log_path + profession + '_pids_filter_slip_person_sequences.csv'
    filter_slip_seqs.to_csv(filter_slip_seqs_path)

    unable_to_split_seqs = pd.DataFrame(unable_to_split_person_sequences)
    unable_to_split_seqs_path = pids_log_path + profession + '_pids_unable_to_split_person_sequences.csv'
    unable_to_split_seqs.to_csv(unable_to_split_seqs_path)

    # print and save some general diagnostics
    print("     NUMBER OF DISTINCT PERSONS GOING IN: ", len(person_sequences))
    print("     NUMBER OF DISTINCT PERSONS COMING OUT: ", len(distinct_persons))
    print("     NUMBER OF DISTINCT PERSONS ADDED: ", len(distinct_persons) - len(person_sequences))
    print("     NET CHANGE IN PERSON-YEARS: ", net_person_years)

    # write to disk the change logs
    change_log.append(['\n'])
    change_log.append(["NUMBER OF DISTINCT PERSONS GOING INTO CORRECT_OVERLAPS: ", len(person_sequences)])
    change_log.append(["NUMBER OF DISTINCT PERSONS COMING OUT OF CORRECT_OVERLAPS: ", len(distinct_persons)])
    change_log.append(["NUMBER OF DISTINCT PERSONS ADDED BY CORRECT_OVERLAPS: ",
                       len(distinct_persons) - len(person_sequences)])
    change_log.append(["NET CHANGE IN PERSON-YEARS AFTER CORRECT_OVERLAPS", net_person_years])
    change_log.append(['\n'])

    # and return the list of distinct persons
    return distinct_persons


def three_plus_workplaces_handle(person_sequence, years_and_workplaces):
    """
    Handles sequences in which one year features three or more workplaces, i.e. it looks like the person is in
    at least three places at once.

    Sometimes we're dealing with a situation where a workplace appears just once in the whole sequence, in that
    tripled-up year, as below. In that case, just eliminate that unique workplace, on the assumption that it's a
    glitch. Therefore, from


    (A) THREE YEAR OVERLAP, ONE UNIQUE WORKPLACE

    SURNAME    GIVEN NAME   INSTITUTION   YEAR

    DERP       BOB JOE     ALPHA          2012
    DERP       BOB JOE     ALPHA          2013
    DERP       BOB JOE     BETA           2013
    DERP       BOB JOE     ALPHA          2014
    DERP       BOB JOE     GAMMA          2014
    DERP       BOB JOE     BETA           2014
    DERP       BOB JOE     BETA           2015

    returns

    SURNAME    GIVEN NAME   INSTITUTION   YEAR

    DERP       BOB JOE     ALPHA          2012
    DERP       BOB JOE     ALPHA          2013
    DERP       BOB JOE     BETA           2013
    DERP       BOB JOE     ALPHA          2014
    DERP       BOB JOE     BETA           2014
    DERP       BOB JOE     BETA           2015

    :param person_sequence: a sequence of person-years sharing a unique person ID, as a list of lists
    :param years_and_workplaces: a dict where keys are years and values are the associated workplaces for said year
    :return: a list containing the year-workplace combo(s) to remove from the person years
    """

    # find the workplaces associated with three-workplace overlaps and their associated year
    three_plus_workplaces_overlaps = {}
    for year, workplaces in years_and_workplaces.items():
        if len(workplaces) > 2:
            three_plus_workplaces_overlaps.update({wp: year for wp in workplaces})

    # get the year frequency of each workplace in the person-sequence
    workplace_year_freqs = {}
    for key, wrkplc_grp in itertools.groupby(sorted(person_sequence, key=operator.itemgetter(4)),
                                             key=operator.itemgetter(4)):
        wrkplc_grp_list = list(wrkplc_grp)
        workplace_year_freqs.update({wrkplc_grp_list[0][4]: len(list(wrkplc_grp_list))})

    # if a workplace in a three-year overlap set is associated with only one year, mark its person-year for exclusion
    to_remove = []
    for workplace, year in three_plus_workplaces_overlaps.items():
        if workplace_year_freqs[workplace] == 1:
            to_remove.append(str(year) + '-' + workplace)

    return to_remove


def if_transition(years_and_workplaces, overlap_years):
    """
    Function that returns True if the overlap years marked a transition between workplaces, and False if it did not.

    NB: only built to handle one or two years of overlap

    :param years_and_workplaces: a dict of form {Year1: [workplace 1], Year2: [workplace1], Year3:[workplace2]}
    :param overlap_years: dict of key-value pairs of years_and_workplaces that have more than one workplace per year
                          e.g. {Year3: [workplace 3, workplace4]}
    :return: dict if a transition, None otherwise
    """

    years = sorted(list(years_and_workplaces))

    year_before, year_after = None, None
    # if there's only one year of overlap
    if len(overlap_years) == 1:
        ovrlp_yr_idx = years.index(list(overlap_years)[0])
        year_before, year_after = years[ovrlp_yr_idx - 1], years[ovrlp_yr_idx + 1]

    # if there are two years of overlap
    if len(overlap_years) == 2:
        ovrlap_yrs = sorted(list(overlap_years))
        lower_ovrlp_yr, upper_ovrlp_yr = ovrlap_yrs[0], ovrlap_yrs[1]
        lower_ovrlp_yr_idx, upper_ovrlp_yr_idx = years.index(lower_ovrlp_yr), years.index(upper_ovrlp_yr)
        year_before, year_after = years[lower_ovrlp_yr_idx - 1], years[upper_ovrlp_yr_idx + 1]

    # if the workplaces in the years before and after the overlap are different, we have a transition
    if years_and_workplaces[year_before][0] != years_and_workplaces[year_after][0]:
        # return a dict with keys: year before, year after, workplace before, workplace after
        return {'transition': True,
                'workplace_before': years_and_workplaces[year_before][0],
                'workplace_after': years_and_workplaces[year_after][0]}
    else:  # if the before and after workplaces are the same, there's no transition
        return {'transition': False, 'workplace_before': years_and_workplaces[year_before][0]}


def split_sequences(profession, person_sequence, change_log, unable_to_split_person_sequences):
    """

    NB: BUILT ONLY FOR SEQUENCES THAT FEATURE ONLY ONE NAME IN 2 PLACES, WILL NOT WORK FOR ONE NAME IN 3+ PLACES

    Takes a year-sorted sequence of person years that share a full name which is in two places at once,
    and returns two sequences, one for each place.

    I assume (heuristically) that distinct career sequences develop in the same Appellate Court area;
    elif they're in the same appellate area, then in the same Tribunal Area;
    elif they're in the same Tribunal Area, then in different Local Courts.
    That is, this is an assumption of a tendency towards career localism and continuity.

    So, for example, the function should take this sequence with overlaps (where CA == court area)

    (A)

    SURNAME    GIVEN NAME   INSTITUTION   YEAR  CA

    DERP       BOB JOE     ALPHA          2012  1
    DERP       BOB JOE     BETA           2012  2
    DERP       BOB JOE     ALPHA          2013  1
    DERP       BOB JOE     BETA           2013  2
    DERP       BOB JOE     ALPHA          2014  1
    DERP       BOB JOE     BETA           2014  2


    and return these two sequences

    (B)                                                     (C)

    SURNAME    GIVEN NAME   INSTITUTION   YEAR  CA          SURNAME    GIVEN NAME  INSTITUTION     YEAR  CA

    DERP       BOB JOE     ALPHA          2012  1           DERP        BOB JOE     BETA           2012  2
    DERP       BOB JOE     ALPHA          2013  1           DERP        BOB JOE     BETA           2013  2
    DERP       BOB JOE     ALPHA          2014  1           DERP        BOB JOE     BETA           2014  2


    This function can also deal with situations where overlaps are not cont

    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param person_sequence: a year-ordered sequence of person-years sharing a full name; as a list of lists
    :param change_log: a list (to be written as a csv) marking the before and after states of the person-sequence
    :param unable_to_split_person_sequences: a list of persons who for one year are in at least three different places,
                                        which we save for visual inspection
    :return: a list of person-sequences; in the example above, a list with [B, C]
    """

    # different professions are organised differently, so the grouping changes

    if profession == 'judges' or profession == 'prosecutors':
        # sort by appellate court area, tribunal court area, then court name
        person_sequence.sort(key=operator.itemgetter(6, 7, 8))

    else:  # profession is 'executori' or 'notaries'
        # sort by regional chamber and town
        person_sequence.sort(key=operator.itemgetter(6, 7))

    # group by appellate area
    # value at index 6 holds appellate court area code
    p_seqs = [group for k, [*group] in itertools.groupby(person_sequence, key=operator.itemgetter(6))]

    # if you don't get two groups, group by tribunal area
    # value at index 7 holds tribunal area code
    if len(p_seqs) != 2:
        p_seqs = [group for k, [*group] in itertools.groupby(person_sequence, key=operator.itemgetter(7))]

    if profession == 'judges' or profession == 'prosecutors':
        # if you don't get two groups, group by local court
        # value at index 8 holds local court code
        if len(p_seqs) != 2:
            p_seqs = [group for k, [*group] in itertools.groupby(person_sequence, key=operator.itemgetter(8))]

    # if you still don't get two groups do nothing, and save the person-sequence for visual inspection
    if len(p_seqs) != 2:
        unable_to_split_person_sequences.append(['\n'])
        unable_to_split_person_sequences.extend([py[1:3] + py[4:9] for py in sorted(person_sequence,
                                                                                    key=operator.itemgetter(5))])
        unable_to_split_person_sequences.append(['\n'])
        return None

    # otherwise, update the change log and return the groups
    else:

        # because we'll be visually inspecting the changes, we want the output table to be in the format
        # COL 1 = input sequence, COL 2 = output sequences

        # side-by-side for input sequence and first output sequence
        for idx, pers_yr in enumerate(p_seqs[0]):
            if profession == 'judges' or profession == 'prosecutors':
                comparison_row = person_sequence[idx][1:3] + person_sequence[idx][4:6] + ['', ''] + \
                                 pers_yr[1:3] + pers_yr[4:6]
            else:
                comparison_row = person_sequence[idx][1:3] + person_sequence[idx][5:8] + ['', ''] + \
                                 pers_yr[1:3] + pers_yr[5:8]

            change_log.append(comparison_row)

        change_log.append(6 * [''] + ['NEXT PERSON'])

        # side-by-side for input sequence and second output sequence
        for idx, pers_yr in enumerate(p_seqs[1]):

            if profession == 'judges' or profession == 'prosecutors':
                comparison_row = person_sequence[len(p_seqs[0]) + idx][1:3] + \
                                 person_sequence[len(p_seqs[0]) + idx][4:6] + ['', ''] + \
                                 pers_yr[1:3] + pers_yr[4:6]
            else:
                comparison_row = person_sequence[len(p_seqs[0]) + idx][1:3] + \
                                 person_sequence[len(p_seqs[0]) + idx][5:8] + ['', ''] + \
                                 pers_yr[1:3] + pers_yr[5:8]

            change_log.append(comparison_row)
        change_log.append('\n')

        return p_seqs


def interpolate_person_years(distinct_persons, change_log):
    """
    Sometimes sequences are missing a year or two in the middle. It is unreasonable that someone retired from a
    judicial profession for 1-2 years only to return afterwards, so we assume that an absence of two years or less
    reflects a book-keeping error or a leave of absence, and interpolate the missing person-years.

    The absence may mark a transition between institutions, i.e. the last workplace before the absence may differ
    from the first workplace after the absence. This function covers handles that scenario, as well as the case when
    the absence does not mark institutional change.

    The vignettes below cover all possible cases -- I refer to them in the code.

    (A)  ONE YEAR GAP, NO INSTITUTION CHANGE                 (B)  TWO YEAR GAP, NO INSTITUTION CHANGE

    SURNAME    GIVEN NAME   INSTITUTION   YEAR               SURNAME    GIVEN NAME  INSTITUTION    YEAR

    DERP       BOB JOE      ALPHA         2012               DERP       BOB JOE     ALPHA          2012
    DERP       BOB JOE      ALPHA         2013               DERP       BOB JOE     ALPHA          2013
    DERP       BOB JOE      ALPHA         2015               DERP       BOB JOE     ALPHA          2016
    DERP       BOB JOE      ALPHA         2016               DERP       BOB JOE     ALPHA          2017


    (C)  ONE YEAR GAP, CHANGE OF INSTITUTIONS                (D)  TWO YEAR GAP, CHANGE OF INSTITUTIONS

    SURNAME    GIVEN NAME   INSTITUTION   YEAR               SURNAME    GIVEN NAME  INSTITUTION    YEAR

    DERP       BOB JOE      ALPHA         2012               DERP       BOB JOE     ALPHA          2012
    DERP       BOB JOE      ALPHA         2013               DERP       BOB JOE     ALPHA          2013
    DERP       BOB JOE      BETA          2015               DERP       BOB JOE     BETA           2016
    DERP       BOB JOE      BETA          2016               DERP       BOB JOE     BETA           2017
    DERP       BOB JOE      GAMMA         2017               DERP       BOB JOE     GAMMA          2018


    :param distinct_persons: a list of distinct persons, i.e. of person-sequences that feature no overlaps; this is
                             a triple nested list: of person-sequences, which is made up of person-years, each of
                             which is a list of person-year data
    :param change_log: a list (to be written as a csv) marking the before and after states of the person-sequence
    :return: a list of distinct persons with interpolated person-years
    """

    # mark where this function begins in the change log
    change_log.extend([['\n'], ['INTERPOLATE_PERSON_YEARS'], ['\n']])

    # initialise a list of distinct persons with interpolated person-years
    interpolated_distinct_persons = []

    # initialise a counter to keep track of how many person-years the interpolation adds
    interpolation_counter = 0

    # iterate through the person-sequences
    for pers_seq in distinct_persons:

        # sort the person_sequence by year
        pers_seq.sort(key=operator.itemgetter(5))  # person_year=[5] == year

        # see if this person has one- or two-year gaps between person-years
        # i.e. if the difference in years between consecutive person-years is 2 or 3
        year_diffs = {int(pers_seq[idx + 1][5]) - int(py[5]) for idx, py in enumerate(pers_seq)
                      if idx < len(pers_seq) - 1}

        # if there is indeed a 1-2 year gap
        if 2 in year_diffs or 3 in year_diffs:

            # deepcopy the person-sequence so we can add interpolated person-years without live-updating iterable
            intrplt_pers_seq = copy.deepcopy(pers_seq)

            # go through the person-sequence looking for missing years
            for i in range(len(pers_seq) - 1):

                year_diff = int(pers_seq[i + 1][5]) - int(pers_seq[i][5])  # again, person_year=[5] == year

                # CASES (A) AND (C)
                # we're missing a year, i.e. the year difference between two consecutive person years is 2
                if year_diff == 2:
                    #  whether or not the gap marks a change in workplace, insert a person-year with the missing
                    # year and the workplace value of the last year before the gap; workplace before the gap
                    # (and not the first workplace after) is arbitrary: it only matters that we do so consistently
                    new_person_year = pers_seq[i][:5] + [str(int(pers_seq[i][5]) + 1)] + pers_seq[i][6:]
                    intrplt_pers_seq.insert(0, new_person_year)

                # CASES (B) and (D)
                # we're missing two years, i.e. the year difference between two consecutive person-years is 3
                if year_diff == 3:
                    # same as above; insert two person-years with the missing years and the departure workplace
                    new_person_year_1 = pers_seq[i][:5] + [str(int(pers_seq[i][5]) + 1)] + pers_seq[i][6:]
                    new_person_year_2 = pers_seq[i][:5] + [str(int(pers_seq[i][5]) + 2)] + pers_seq[i][6:]
                    intrplt_pers_seq.insert(0, new_person_year_1), intrplt_pers_seq.insert(0, new_person_year_2)

            # sort the new person-sequence by year
            intrplt_pers_seq.sort(key=operator.itemgetter(5))

            # update the change log with a side-by-side of the old and new person-sequences
            for idx, py in enumerate(intrplt_pers_seq):
                if idx < len(pers_seq):
                    change_log.append(pers_seq[idx][1:3] + pers_seq[idx][4:6] + ['', ''] +
                                      py[1:3] + py[4:6])
                else:
                    change_log.append(6 * [''] + py[1:3] + py[4:6])
            # add the person-sequence with interpolated years to the new list
            interpolated_distinct_persons.append(intrplt_pers_seq)

            # update the counter of interpolated person years
            interpolation_counter += len(intrplt_pers_seq) - len(pers_seq)

            # and go on to the next person
            continue

        else:  # there's no 1-2 year gap

            # add the person-sequence to the new list as is
            interpolated_distinct_persons.append(pers_seq)

    #  print and save some diagnostics

    print("     NET CHANGE IN PERSON-YEARS: ", interpolation_counter)

    change_log.append(['\n'])
    change_log.append(["NUMBER OF PERSON-YEARS ADDED BY INTERPOLATE_PERSON_YEARS: ", interpolation_counter])
    change_log.append(['\n'])

    # and return the list of person, completed with the interpolated person-years
    return interpolated_distinct_persons


def unique_person_ids(distinct_persons, change_log):
    """
    Assign each person-year a new field with the person-ID to which the person-year belongs.

    :param distinct_persons: a list of distinct persons, i.e. of person-sequences that feature no overlaps; this is
                             a triple nested list: of person-sequences, which is made up of person-years, each of
                             which is a list of person-year data
    :param change_log: a list (to be written as a csv) marking the before and after states of the person-sequence
    :return: a list of distinct persons, where each person-year has the person-level ID
    """

    # initialise the list of person-years with unique person IDs
    person_year_table_with_pids = []

    # add a person-level ID to each person-year
    for idx, person in enumerate(distinct_persons):
        for person_year in person:
            # dump all person-years in one table
            person_year_table_with_pids.append(person_year[:1] + [idx] + person_year[1:])

    # update the change log with the total number of person-years coming out
    print("NUMBER OF PERSON-YEARS AT THE END: ", len(person_year_table_with_pids))
    change_log.append(["NUMBER OF PERSON-YEARS AFTER ASSIGNING UNIQUE IDS: ", len(person_year_table_with_pids)])

    # and return the table with person-level unique IDs
    return sorted(person_year_table_with_pids, key=operator.itemgetter(2, 3, 6))
