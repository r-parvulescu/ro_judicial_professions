"""
Functions for calculating weighted mobility estimates from continuity samples, i.e. samples that track the same set of
courts of appeals areas over the entire time-span of the data. The problem is that with the samples I cannot distinguish
between genuine mobility moves and moves that simply caused by leaving or entering the sample -- consequently, the raw
sample counts are biased, since they pool things together that should be separate.

Fortunately, within the whole population I CAN distinguish between the different mobility type; I have samples up to
2005 (exclusive) and the full population after 2005 (inclusive). So the general approach is to use years for which I
have the full population to estimate the fraction of total moves within the sampled areas that are due to movements
within the sample, or movement that leaves the sample, and THEN (for the years for which I ONLY have samples, not the
population) to adjust raw sample counts by these fractions. For example, if we sample the Craiova appellate area,
I calculate the fractions on the year 2008 (for which I have the whole population) and use these fractions to adjust
for sample counts from 1998 (for which I only have the sample).

The big assumption here is that movements within and between sample areas did not change significantly over time, so
that fractions from latter years are accurate for earlier years. Unfortunately, there is no clear way to test this. I
maintain, however, that weighing in this way is much better than nothing, though there are limitations.

NB: as of 04.12.2020 the area sample we use for judges consists of all courts within the jurisdictions of the
    Alba (CA1), Craiova (CA7), Iaşi (CA9), Ploieşti (CA12) courts of appeals, as well as the High Court (-88)

NB: there is A LOT of doubling up of code in this script, which I keep because frankly when I streamlined everything
    it became very hard to read. This way it's tedious but understandable.

NB: weights pool across al sampled areas

NB: keys oflevel dicts indicate judicial level: 1 = low court, 2 = tribunal, 3 = appeals, 4 = high court

NB: by convention I turn undefined weights (where the denominator is zero) to zero

NB: if for whatever reason the fractions are undefined I treat them as the multiplicative constant (i.e. 1) so that
    the raw sample counts remain unchanged

NB: for judges and prosecutors only!
"""

import csv
from helpers import helpers
from helpers.helpers import get_workplace_code
from preprocess import sample
from describe import totals_in_out
from describe.mobility import hierarchical

# I hard-wire these values because it is very rare that I get significantly more data which warrants changing them
pop_yrs_for_fracts = {"judges": [2006, 2007, 2008],
                      "prosecutors ": []}

samp_yr_range = {"judges": [1980, 2003],
                 "prosecutors": []}

pop_yr_range = {"judges": [2006, 2020],
                "prosecutors": []}

total_range = {"judges": [1978, 2020],
               "prosecutors": []}

samp_areas = {"judges": ["CA1", "CA7", "CA9", "CA12", "-88"],
              "prosecutors": []}


def make_area_sample_measures_table(person_year_table, profession, out_dir):
    """
    Save to disk one big table with all the estimated size of the population, yearly percent change in that size, and
    all the estimated mobility types for the sampled years.

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param out_dir: str, the path to where the transition matrices will live
    """

    samp_yrs = samp_yr_range[profession]

    # get the estimates
    estimated_pop = estimated_population_size(person_year_table, profession)
    estimated_rets = adjusted_retirement_counts(person_year_table, profession)
    estimate_entry = adjusted_entry_counts(person_year_table, profession)
    estimated_proms = adjusted_promotion_counts(person_year_table, profession)
    estimated_demos = adjusted_demotion_counts(person_year_table, profession)
    estimated_transfs = adjusted_lateral_transfer_counts(person_year_table, profession)

    header = ["YEAR", "LEVEL", "ESTIMATED POPULATION", "ESTIMATED COUNT RETIREMENTS", "ESTIMATED COUNT ENTRIES",
              "ESTIMATED COUNT PROMOTIONS", "ESTIMATED COUNT DEMOTIONS", "ESTIMATED COUNT LATERAL TRANSFERS"]

    with open(out_dir + "continuity_sample_mobility_totals_estimates.csv", 'w') as out_f:
        writer = csv.writer(out_f)
        writer.writerow([profession.upper()])
        writer.writerow(header)
        for lvl in range(1, 5):
            for yr in range(samp_yrs[0], samp_yrs[1] + 1):
                writer.writerow([yr, lvl, estimated_pop[yr], estimated_rets[str(lvl)][yr], estimate_entry[str(lvl)][yr],
                                 estimated_proms[str(yr)][lvl], estimated_demos[str(yr)][lvl],
                                 estimated_transfs[str(yr)][lvl]])


def adjusted_retirement_counts(person_year_table, profession, weights=False):
    """
    The problem with the raw sample count of retirement is that it does not distinguish between people who genuinely
    leave the profession and those who simply leave the sample (i.e. move to another area) but remain in the profession.
    Consequently, raw sample retirement counts are biased upwards because profession-exits and sample-exits are
    implicitly equated.

    The solution is to use the total population to compute the fraction of retirements from the sample area that are
    genuine departures from the profession and then to multiply the raw sample retirement count by that fraction,
    thereby reducing the upward bias. To be exact, the genuine retirement fraction is computed by

      genuine retirement fraction = genuine retirement counts / (genuine retirement counts + sample-leaving counts)

    and the adjusted retirement count will therefore be

      adjusted number of retirements = raw sample retirement count * genuine retirement fraction

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param weights: bool, if True then instead of returning the adusted counts, return the fractions by which we weigh
                    the observed counts in order to reduce bias
    :return a nested dict, where 1st layer keys are year, 2nd layer keys are level in the judicial hierarchy, and base
            values are the adjusted retirement counts
    """
    samp_yrs, samp_as, fracts_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the population table by person and year then sample from it by area
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    # initialise the dicts; NB: four possible levels, even though level 3 (Appeals courts) only began in 1993
    ret_fracts = {lvl: {"gen_rets": 0, "samp_leaves": 0} for lvl in range(1, 5)}

    people = helpers.group_table_by_persons(sorted_person_year_table, profession)
    for person in people:
        for idx, pers_yr in enumerate(person):

            current_yr, current_lvl, current_area = pers_yr[yr_col_idx], int(pers_yr[lvl_col_idx]), pers_yr[ca_cod_idx]
            # if this year is used for the fraction, and within the sampling areas
            if int(current_yr) in fracts_yrs and current_area in samp_as:
                if idx < len(person) - 1:  # since we do look-aheads to see departures-cum-retirements
                    # if next year's area is NOT within the sampling area, increment sample departures
                    if person[idx + 1][ca_cod_idx] not in samp_as:
                        ret_fracts[current_lvl]["samp_leaves"] += 1

                # if last year is used for the fraction and within the sampling areas, increment genuine retirements
                else:  # NB: this always assume we pick a sampling year than is less than the right censoring year
                    ret_fracts[current_lvl]["gen_rets"] += 1

    # average over the years then get the final fraction, per level
    for lvl in ret_fracts:
        avg_gen_rets = float(ret_fracts[lvl]["gen_rets"]) / float(len(fracts_yrs))
        avg_samp_leave_rets = float(ret_fracts[lvl]["samp_leaves"]) / float(len(fracts_yrs))
        ret_fracts[lvl] = helpers.weird_division(avg_gen_rets, (avg_gen_rets + avg_samp_leave_rets), mult_const=True)

    # get the raw counts
    cas_sample_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
    samp_ret_counts = totals_in_out.pop_cohort_counts(cas_sample_table, samp_yrs[0], samp_yrs[1], profession,
                                                      cohorts=True, unit_type="nivel", entry=False)
    samp_ret_counts.pop("grand_total")  # don't need the grand total

    # and weigh them; round result to four decimals
    for lvl in samp_ret_counts:
        for yr in samp_ret_counts[lvl]:
            samp_ret_counts[lvl][yr] = round(samp_ret_counts[lvl][yr]["total_size"] * ret_fracts[int(lvl)], 4)

    if weights:
        return ret_fracts
    else:
        return samp_ret_counts


def adjusted_entry_counts(person_year_table, profession, weights=False):
    """
    The problem with the raw sample count of entries is that it does not distinguish between people who are genuinely
    new recruits to the profession, and those who were already in the profession but outside the sample. Consequently,
    the raw count is biased upwards because it equates entering the sample from within the profession with entering
    the profession tout-court.

    The solution is to use the total population to compute the fraction of entries into the sample that are genuine
    recruits into the profession and then to multiply the raw sample entry count by that fraction, thereby reducing the
    upward bias. To be exact, the genuine entry fraction is computed by

      genuine entry fraction = genuine entry counts / (genuine entry counts + sample-entering counts)

    and the adjusted entry count will therefore be

      adjusted number entries = sample entry count * genuine entry fraction

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param weights: bool, if True then instead of returning the adusted counts, return the fractions by which we weigh
                    the observed counts in order to reduce bias
    :return a nested dict, where 1st layer keys are year, 2nd layer keys are level in the judicial hierarchy, and base
            values are the adjusted entry counts
    """
    samp_yrs, samp_as, fracts_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the population table by person and year then sample from it by area
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    # initialise the dicts; NB: four possible levels, even though level 3 (Appeals courts) only began in 1993
    ent_fracts = {lvl: {"gen_ents": 0, "samp_ents": 0} for lvl in range(1, 5)}

    people = helpers.group_table_by_persons(sorted_person_year_table, profession)
    for person in people:
        for idx, pers_yr in enumerate(person):

            current_yr, current_lvl, current_area = pers_yr[yr_col_idx], int(pers_yr[lvl_col_idx]), pers_yr[ca_cod_idx]

            # if this year is used for the fraction and this year is within the sample area
            if int(current_yr) in fracts_yrs and current_area in samp_as:

                # if it's genuinely the first year, increment genuine entries
                #  NB: this always assumes that we skip the left censor year
                if idx == 0:  # the first year of the career;
                    ent_fracts[current_lvl]["gen_ents"] += 1

                if 1 < idx:  # since we do look-behinds to see if someone entered the sample from elsewhere

                    # if LAST year's appellate area is different from this year's appellate area, increment count of
                    # extra-sample entries
                    if current_area != person[idx - 1][ca_cod_idx]:
                        ent_fracts[current_lvl]["samp_ents"] += 1
    # average over the years then get the final fraction, per level
    for lvl in ent_fracts:
        avg_gen_ents = float(ent_fracts[lvl]["gen_ents"]) / float(len(fracts_yrs))
        avg_samp_ents = float(ent_fracts[lvl]["samp_ents"]) / float(len(fracts_yrs))
        ent_fracts[lvl] = helpers.weird_division(avg_gen_ents, (avg_gen_ents + avg_samp_ents), mult_const=True)

    # get the raw counts
    cas_sample_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
    samp_ent_counts = totals_in_out.pop_cohort_counts(cas_sample_table, samp_yrs[0], samp_yrs[1], profession,
                                                      cohorts=True, unit_type="nivel", entry=True)
    samp_ent_counts.pop("grand_total")  # don't need the grand total
    # and weigh them; round result to four decimals
    for lvl in samp_ent_counts:
        for yr in samp_ent_counts[lvl]:
            samp_ent_counts[lvl][yr] = round(samp_ent_counts[lvl][yr]["total_size"] * ent_fracts[int(lvl)], 4)

    if weights:
        return ent_fracts
    else:
        return samp_ent_counts


def adjusted_promotion_counts(person_year_table, profession, weights=False):
    """
    The problem with the raw sample count of promotions is that it is biased downward, for two reasons:

     a) those who are promoted to a position outside the sample will appear have retired, thus biasing the promotion
        count downward

     b) those who entered the sample via promotion from outside the sample will appear to be new entrants, thus biasing
        the promotion count downward

    Essentially, the sample only counts promotions that occur within the sample, ignoring those promotions that feature
    sample entry or departure.

    To fix this bias we use the total populating to compute the genuine fraction of promotions, namely

      genuine promotion ratio = (within-sample promotions +
                                 promotions leaving the sample +
                                 promotions entering the sample)
                                            /
                                   within-sample promotions

    and the adjusted promotion count will therefore be

      adjusted number of promotions = within-sample promotion count * genuine promotion ratio

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param weights: bool, if True then instead of returning the adusted counts, return the fractions by which we weigh
                    the observed counts in order to reduce bias
    :return a nested dict, where 1st layer keys are year, 2nd layer keys are level in the judicial hierarchy, and base
            values are the adjusted promotion counts
    """
    samp_yrs, samp_as, fracts_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the population table by person and year then sample from it by area
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    # initialise the dicts; NB: four possible levels, even though level 3 (Appeals courts) only began in 1993
    prom_fracts = {lvl: {"within_samp_proms": 0, "samp_leave_proms": 0, "samp_ent_proms": 0} for lvl in range(1, 5)}

    people = helpers.group_table_by_persons(sorted_person_year_table, profession)
    for person in people:
        for idx, pers_yr in enumerate(person):

            current_yr, current_lvl, current_area = pers_yr[yr_col_idx], int(pers_yr[lvl_col_idx]), pers_yr[ca_cod_idx]

            # if this year is used for the fraction and this year is within the sample area
            if int(current_yr) in fracts_yrs and current_area in samp_as:

                if idx < len(person) - 1:  # since we do look-aheads to judge mobility within or leaving the sample

                    # if current hierarchical level is lower than NEXT year's (i.e. there's a promotion this year):
                    if current_lvl < int(person[idx + 1][lvl_col_idx]):
                        # if next year's area is outside the sample, increment count of leaving-sample promotions
                        if person[idx + 1][ca_cod_idx] not in samp_as:
                            prom_fracts[current_lvl]["samp_leave_proms"] += 1

                    else:
                        # if next year's area is within the sample, increment the count of within-sample promotions
                        if person[idx + 1][ca_cod_idx] in samp_as:
                            prom_fracts[current_lvl]["within_samp_proms"] += 1

                if 1 < idx:  # we do look behinds to see if someone entered the sample from elsewhere:

                    # if LAST year's hierarchical level was lower than this year's (i.e. a promotion occurred last year)
                    if int(person[idx - 1][lvl_col_idx]) < current_lvl:
                        # if last year's area was not within the sample, increment the count of extra-sample entries via
                        # promotion
                        prom_fracts[current_lvl]["samp_ent_proms"] += 1

                        # average over the years then get the final fraction, per level
    for lvl in prom_fracts:
        avg_within_samp_proms = float(prom_fracts[lvl]["within_samp_proms"]) / float(len(fracts_yrs))
        avg_samp_leave_proms = float(prom_fracts[lvl]["samp_leave_proms"]) / float(len(fracts_yrs))
        avg_samp_ent_proms = float(prom_fracts[lvl]["samp_ent_proms"]) / float(len(fracts_yrs))
        prom_fracts[lvl] = helpers.weird_division((avg_within_samp_proms + avg_samp_leave_proms + avg_samp_ent_proms),
                                                  avg_within_samp_proms, mult_const=True)

    # get the raw counts
    cas_sample_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
    samp_prom_counts = hierarchical.hierarchical_mobility(cas_sample_table, profession)

    # and weigh them; round result to four decimals
    for yr in samp_prom_counts:
        for lvl in samp_prom_counts[yr]:
            samp_prom_counts[yr][lvl] = round(samp_prom_counts[yr][lvl]["up"]["total"] * prom_fracts[lvl], 4)

    if weights:
        return prom_fracts
    else:
        return samp_prom_counts


def adjusted_demotion_counts(person_year_table, profession, weights=False):
    """
    The problem with the raw sample count of demotions is that it is biased downward, for two reasons:

     a) those who are demoted to a position outside the sample will appear have retired, thus biasing the demotion
        count downward

     b) those who entered the sample via demotion from outside the sample will appear to be new entrants, thus biasing
        the demotino count downward

    Essentially, the sample only counts demotions that occur within the sample, ignoring those demotions that feature
    sample entry or departure.

    To fix this bias we use the total populating to compute the genuine fraction of promotions, namely

      genuine demotion ratio = (within-sample demotions +
                                 demotions leaving the sample +
                                 demotions entering the sample)
                                            /
                                   within-sample demotions

    and the adjusted demotion count will therefore be

      adjusted number of demotions = within-sample demotion count * genuine demotion ratio

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param weights: bool, if True then instead of returning the adusted counts, return the fractions by which we weigh
                    the observed counts in order to reduce bias
    :return a nested dict, where 1st layer keys are year, 2nd layer keys are level in the judicial hierarchy, and base
            values are the adjusted demotion counts
    """
    samp_yrs, samp_as, fracts_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the population table by person and year then sample from it by area
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    # initialise the dicts; NB: four possible levels, even though level 3 (Appeals courts) only began in 1993
    demo_fracts = {lvl: {"within_samp_demos": 0, "samp_leave_demos": 0, "samp_ent_demos": 0} for lvl in range(1, 5)}

    people = helpers.group_table_by_persons(sorted_person_year_table, profession)
    for person in people:
        for idx, pers_yr in enumerate(person):

            current_yr, current_lvl, current_area = pers_yr[yr_col_idx], int(pers_yr[lvl_col_idx]), pers_yr[ca_cod_idx]

            # if this year is used for the fraction and this year is within the sample area
            if int(current_yr) in fracts_yrs and current_area in samp_as:

                if idx < len(person) - 1:  # since we do look-aheads to judge mobility within or leaving the sample

                    # if current hierarchical level is higher than NEXT year's (i.e. there's a demotion this year):
                    if current_lvl > int(person[idx + 1][lvl_col_idx]):
                        # if next year's area is outside the sample, increment count of leaving-sample demotions
                        if person[idx + 1][ca_cod_idx] not in samp_as:
                            demo_fracts[current_lvl]["samp_leave_demos"] += 1

                    else:
                        # if next year's area is within the sample, increment the count of within-sample demotions
                        if person[idx + 1][ca_cod_idx] in samp_as:
                            demo_fracts[current_lvl]["within_samp_demos"] += 1

                if 1 < idx:  # we do look behinds to see if someone entered the sample from elsewhere:

                    # if LAST year's hierarchical level was higher than this year's (i.e. a demotion occurred last year)
                    if int(person[idx - 1][lvl_col_idx]) > current_lvl:
                        # if last year's area was not within the sample, increment the count of extra-sample entries via
                        # demotion
                        demo_fracts[current_lvl]["samp_ent_demos"] += 1

    # average over the years then get the final fraction, per level
    for lvl in demo_fracts:
        avg_within_samp_demos = float(demo_fracts[lvl]["within_samp_demos"]) / float(len(fracts_yrs))
        avg_samp_leave_demos = float(demo_fracts[lvl]["samp_leave_demos"]) / float(len(fracts_yrs))
        avg_samp_ent_demos = float(demo_fracts[lvl]["samp_ent_demos"]) / float(len(fracts_yrs))
        demo_fracts[lvl] = helpers.weird_division((avg_within_samp_demos + avg_samp_leave_demos + avg_samp_ent_demos),
                                                  avg_within_samp_demos, mult_const=True)

    # get the raw counts
    cas_sample_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
    samp_demo_counts = hierarchical.hierarchical_mobility(cas_sample_table, profession)

    # and weigh them; round result to four decimals
    for yr in samp_demo_counts:
        for lvl in samp_demo_counts[yr]:
            samp_demo_counts[yr][lvl] = round(samp_demo_counts[yr][lvl]["down"]["total"] * demo_fracts[lvl], 4)

    if weights:
        return demo_fracts
    else:
        return samp_demo_counts


def adjusted_lateral_transfer_counts(person_year_table, profession, weights=False):
    """
    The problem with the raw sample count of lateral trasnfers is that it is biased downward, for two reasons:

     a) those who trasnfer laterally to a position outside the sample will appear have retired, thus biasing the
        lateral transfer count downward

     b) those who entered the sample via lateral transfer from outside the sample will appear to be new entrants, thus
        biasing the lateral transfer count downward

    Essentially, the sample only counts lateral transfers that occur within the sample, ignoring those lateral transfers
     that feature sample entry or departure.

    To fix this bias we use the total populating to compute the genuine fraction of lateral transfers, namely

      genuine promotion ratio = (within-sample lateral transfers +
                                 lateral transfers leaving the sample +
                                 lateral transfers entering the sample)
                                            /
                                   within-sample lateral transfers

    and the adjusted lateral transfer count will therefore be

      adjusted number of lateral transfers = within-sample lateral transfer count * genuine lateral transfer ratio

    :param person_year_table: list of lists, a list of person-years (each one a list of values)
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param weights: bool, if True then instead of returning the adusted counts, return the fractions by which we weigh
                    the observed counts in order to reduce bias
    :return a nested dict, where 1st layer keys are year, 2nd layer keys are level in the judicial hierarchy, and base
            values are the adjusted lateral transfer counts
    """
    samp_yrs, samp_as, fracts_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # sort the population table by person and year then sample from it by area
    sorted_person_year_table = helpers.sort_pers_yr_table_by_pers_then_yr(person_year_table, profession)

    # initialise the dicts; NB: four possible levels, even though level 3 (Appeals courts) only began in 1993
    trans_fracts = {lvl: {"within_samp_transfs": 0, "samp_leave_transfs": 0, "samp_ent_transfs": 0}
                    for lvl in range(1, 5)}

    people = helpers.group_table_by_persons(sorted_person_year_table, profession)
    for person in people:
        for idx, pers_yr in enumerate(person):

            current_yr, current_lvl, current_area = pers_yr[yr_col_idx], int(pers_yr[lvl_col_idx]), pers_yr[ca_cod_idx]

            # if this year is used for the fraction and this year is within the sample area
            if int(current_yr) in fracts_yrs and current_area in samp_as:

                if idx < len(person) - 1:  # since we do look-aheads to judge mobility within or leaving the sample

                    # if current hierarchical level is equal to NEXT year's AND the exact workplaces differ
                    # (i.e. there's a lateral transfer this year):
                    if current_lvl == int(person[idx + 1][lvl_col_idx]) and \
                            get_workplace_code(pers_yr, profession) != get_workplace_code(person[idx + 1], profession):

                        # if next year's area is outside the sample, increment count of leaving-sample transfers
                        if person[idx + 1][ca_cod_idx] not in samp_as:
                            trans_fracts[current_lvl]["samp_leave_transfs"] += 1

                    else:
                        # if next year's area is within the sample, increment the count of within-sample demotions
                        if person[idx + 1][ca_cod_idx] in samp_as:
                            trans_fracts[current_lvl]["within_samp_transfs"] += 1

                if 1 < idx:  # we do look behinds to see if someone entered the sample from elsewhere:

                    # if LAST year's hierarchical level was the same as this year's AND the exact workplaces different
                    # (i.e. a lateral transfer occurred last year)
                    if int(person[idx - 1][lvl_col_idx]) == current_lvl and \
                            get_workplace_code(pers_yr, profession) != get_workplace_code(person[idx - 1], profession):
                        # if last year's area was not within the sample, increment the count of extra-sample entries via
                        # lateral transfer
                        trans_fracts[current_lvl]["samp_ent_transfs"] += 1

    # average over the years then get the final fraction, per level
    for lvl in trans_fracts:
        avg_within_samp_transfs = float(trans_fracts[lvl]["within_samp_transfs"]) / float(len(fracts_yrs))
        avg_samp_leave_transfs = float(trans_fracts[lvl]["samp_leave_transfs"]) / float(len(fracts_yrs))
        avg_samp_ent_transfs = float(trans_fracts[lvl]["samp_ent_transfs"]) / float(len(fracts_yrs))
        trans_fracts[lvl] = helpers.weird_division((avg_within_samp_transfs +
                                                    avg_samp_leave_transfs +
                                                    avg_samp_ent_transfs),
                                                   avg_within_samp_transfs, mult_const=True)

    # get the raw counts
    cas_sample_table = sample.appellate_area_sample(sorted_person_year_table, profession, samp_as)
    samp_transf_counts = hierarchical.hierarchical_mobility(cas_sample_table, profession)

    # and weigh them; round result to four decimals
    for yr in samp_transf_counts:
        for lvl in samp_transf_counts[yr]:
            samp_transf_counts[yr][lvl] = round(samp_transf_counts[yr][lvl]["across"]["total"] * trans_fracts[lvl], 4)

    if weights:
        return trans_fracts
    else:
        return samp_transf_counts


def estimated_population_size(person_year_table, profession):
    """
    To estimate the total size of the profession (i.e. of the population) for years in which we only have a sample,
    estimate the ratio between population and samples size for years in which we DO have the whole population, then
    for years with samples only multiply this population inflation ratio by the observed sample size. To be exact

      population inflation ratio = population size / sample size

      estimates population size = sample size * population inflation ratio

    NB: this assumes that the ratio between the total population and the sum of the sampled areas is roughly constant
        across the years whose population sizes we're estimating.

    :param person_year_table: a table of person-years, as a list of lists; assumes no header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return: dict of estimated population sizes: keys are years, value are estimates
    """

    samp_yrs, samp_as, ratio_yrs = samp_yr_range[profession], samp_areas[profession], pop_yrs_for_fracts[profession]
    pop_yrs, total_yrs = pop_yr_range[profession], total_range[profession]
    areas_sample_table = sample.appellate_area_sample(person_year_table, profession, samp_as)

    # get ratio of sample size to population size for desired years, average across said years
    samp_size = totals_in_out.pop_cohort_counts(areas_sample_table, total_yrs[0], total_yrs[1], profession,
                                                cohorts=False, unit_type="nivel")
    pop_size = totals_in_out.pop_cohort_counts(person_year_table, pop_yrs[0], pop_yrs[1], profession,
                                               cohorts=False, unit_type="nivel")
    avg_samp_size, avg_total_size = 0, 0
    for r_yr in ratio_yrs:
        avg_samp_size += samp_size["grand_total"][r_yr]["total_size"]
        avg_total_size += pop_size["grand_total"][r_yr]["total_size"]
    avg_samp_size = float(avg_samp_size) / float(len(ratio_yrs))
    avg_total_size = float(avg_total_size) / float(len(ratio_yrs))
    pop_inflation_ratio = avg_total_size / avg_samp_size

    # for each year in which we only have samples, multiply the number of people in sample by the population inflation
    # ratio; these are the population estimates for the years in which we only have samples. Round to 4 decimals.
    estim_pop = {}
    for yr in range(samp_yrs[0], samp_yrs[1] + 1):
        estim_pop.update({yr: round(float(samp_size["grand_total"][yr]["total_size"] * pop_inflation_ratio), 4)})
    return estim_pop
