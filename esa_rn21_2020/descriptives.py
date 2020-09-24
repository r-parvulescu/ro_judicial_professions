"""
Code for estimating key descriptive statistics, mostly centered around professional mobility.
"""

import csv
import operator
import statistics
from itertools import groupby
from copy import deepcopy
from helpers import helpers
from preprocess import sample
from describe.mobility import hierarchical
from describe import totals_in_out


def retirement_promotion_estimates(person_year_table, profession, sampling_year_range, out_dir):
    """
    Estimate how many people retire and move up the legal hierarchy (i.e. get promoted) every year, both in raw counts
    and relative to the population of people open to such retirement.

    Post-2005 we have the complete population of magistrates (i.e. judges and prosecutors) but pre-2005 we have only
    non-random samples. For judges I sample three appellate areas (Alba, Craiova, Iaşi, and Ploieşti) because I have
    yearly data on all courts in these areas since at least 1980. That said, mobility estimates from these samples
    need to be corrected. In particular, I look at three sorts of mobility: retirement, promotion, and entry.

    Post-2005 we are certain that someone retires when they are in the population in year X, but absent in year X+1.
    For the pre-2005 we can't be certain, because that person may have left the sample but stayed in the population,
    i.e. they have simply changed appellate area. I therefore correct sample estimates as follows:

    - for the intervals 2006-2007, 2007-2008, and 2008-2009, see how many magistrates in the sampled areas (Alba,
      Craiova, Iaşi, and Ploieşti) actually retired, and how many just left their respective area. Compute the ratio
      "retirement counts" / "retirement counts + area leaving counts" for each interval, and take the three-interval
      average. The result is a weight: X% of the people that departed the sampled areas actually retired. There is one
      ratio for each judicial level (i.e. low court, tribunal, and appeals).

    - for pre-2005 I count how many people left the sample, then multiply the per-level count by the appropriate weight.
      Obviously, this assumes that the ratio between retirements and area changes is constant over this period. I cannot
      numerically check that assumption.

    Regarding promotion, post-2005 we can just see if someone's judicial level increased between years. Pre-2005 this
    count will be based in the sample because a) those who receive a promotion outside the sample look show up as
    retirements, b) those who entered the sample upon promotion look like new entrants. To address this I construct two
    weights: the ratio of within-area promotions to total promotions, and the ratio of entrants-by-promotion to total
    entrants (per year, per level).

    The final count of (weighted) sample promotions is then computed as follows:
    raw count * 1 / within-total-ratio  + count entrants * promotion-entrants-to-total-ratio

    Finally, to estimate the number of entrants, into the profession using the sample, I do the following:
    count entrants * (1 - promotion-entrants-to-total-ratio).

    Again, the assumption is that the relative balance of inter-area mobility flows is constant throughout the period
    under study, and therefore that ratios derived from 2006-2009 are true of other times as well. I choose the
    2006-2009 period because it's a) the earliest population-level data, and b) this period did not feature major
    judicial reforms.

    Finally, also want estimates of the total size of the population, and of year-on-year population growth.

    :param person_year_table: a table of person-years, as a list of lists; NB: asumes no header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param sampling_year_range: 2-tuple of ints, range of year's for which we're estimating mobility, e.g. (1998-2004)
    :param out_dir: directory where tables of mobility estimates will live
    :return: None
    """

    # get handy column indexes
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # sort person-year table by person then year
    person_year_table.sort(key=operator.itemgetter(pid_col_idx, yr_col_idx))

    # sample all courts in these appeals regions: Alba (CA1), Craiova (CA7), Iaşi (CA9), Ploieşti (CA12)
    appellate_areas_to_sample = ["CA1", "CA7", "CA9", "CA12"]
    cas_sample_table = sample.appellate_area_sample(person_year_table, profession, appellate_areas_to_sample)

    # get weights for retirement, promotion, and entry

    # for those appeals areas, for periods 2006-2007 and 2007-2008, per hierarchical level:
    # a) get ratio of within-area promotions (i.e. people who were already in the area) to total promotions
    # b) get ratio of retirements to retirements + out-of-area transfers
    # Average the values for 2006-07 and 2007-08: these will be weights for estimates from earlier years
    weights = three_year_average_weights(person_year_table, profession, appellate_areas_to_sample,
                                         ["2006", "2007", "2008"])
    retirement_weights = weights["ret_weight"]
    internal_promotion_weights = weights["int_prom_weight"]
    external_promotion_weights = weights["ext_prom_weight"]

    # get raw counts of entries, retirements and promotions per year, per level, in the desired time-frame
    counts = get_raw_counts(cas_sample_table, profession, sampling_year_range)
    ent_counts, ret_counts, prom_counts = counts["entries"], counts["retirements"], counts["promotions"]
    # now weigh those counts with average ratios from 2006-2008. Recall (counts are from sample):
    # estimated retirements = retirement count * retirement weight
    # estimated promotions = promotion count * (1 / interior promotion weight) + entry count * external promotion weight
    # estimated entries = entry count * (1 - external promotion weight)
    for key in internal_promotion_weights:
        for year in ret_counts.keys():
            # round up since these are whole people
            ret_counts[year][key] = round(float(ret_counts[year][key]) * retirement_weights[key])
            prom_counts[year][key] = round(float(helpers.weird_division(prom_counts[year][key],
                                                                        internal_promotion_weights[key])
                                                 + float(ent_counts[year][key]) * external_promotion_weights[key]))
            ent_counts[year][key] = round(ent_counts[year][key] * (1 - external_promotion_weights[key]))

    # relabel, strictly for clarity (notice it's not a deepcopy)
    weighted_ret_counts = ret_counts
    weighted_prom_counts = prom_counts
    weighted_ent_counts = ent_counts

    # using (weighted-estiamted) sample counts, estimate yearly, per-level departure and retirement probabilities, where
    # denominator is sample count of person-years in year X; also estimate what proportion in each year's sample are
    # new entrants
    yearly_counts = counts["total counts"]

    retire_probs = {year: {"1": 0, "2": 0, "3": 0} for year in yearly_counts.keys()}
    promotion_probs = {year: {"1": 0, "2": 0, "3": 0} for year in yearly_counts.keys()}
    entry_proportions = {year: {"1": 0, "2": 0, "3": 0} for year in yearly_counts.keys()}

    for year in yearly_counts:
        for lvl in yearly_counts[year]:
            promotion_probs[year][lvl] = helpers.weird_division(weighted_prom_counts[year][lvl],
                                                                (yearly_counts[year][lvl]))
            retire_probs[year][lvl] = helpers.weird_division(weighted_ret_counts[year][lvl], yearly_counts[year][lvl])
            # NB: entry proportions is simple: how many of this year's samples are newcomers?
            entry_proportions[year][lvl] = helpers.weird_division(weighted_ent_counts[year][lvl],
                                                                  yearly_counts[year][lvl])

    # estimate the size of the professional population for years for which we only have samples
    estimated_pop = estimated_population_size(person_year_table, cas_sample_table, profession, sampling_year_range)

    # estimate year-on-year population growth
    estimated_pop_growth = estimated_population_growth(estimated_pop, sampling_year_range)

    # save to disk one table each for retirements, entries, and departures,
    # and one table for estimated population size and growth
    with open(out_dir + "retirements.csv", 'w') as out_ret:
        writer = csv.writer(out_ret)
        writer.writerow([profession.upper()])
        writer.writerow(["YEAR", "LEVEL", "PROJECTED COUNT RETIREMENTS", "SAMPLE RETIREMENT PROBABILITY"])
        for year in weighted_ret_counts:
            for lvl in weighted_ret_counts[year]:
                writer.writerow([year, lvl, weighted_ret_counts[year][lvl], retire_probs[year][lvl]])

    with open(out_dir + "promotions.csv", 'w') as out_prom:
        writer = csv.writer(out_prom)
        writer.writerow([profession.upper()])
        writer.writerow(["YEAR", "LEVEL", "PROJECTED COUNT PROMOTIONS", "SAMPLE PROMOTION PROBABILITY"])
        for year in weighted_prom_counts:
            for lvl in weighted_prom_counts[year]:
                if lvl in weighted_prom_counts[year] and lvl in promotion_probs[year]:
                    writer.writerow([year, lvl, weighted_prom_counts[year][lvl], promotion_probs[year][lvl]])

    with open(out_dir + "entries.csv", 'w') as out_ent:
        writer = csv.writer(out_ent)
        writer.writerow([profession.upper()])
        writer.writerow(["YEAR", "LEVEL", "PROJECTED COUNT ENTRIES", "SAMPLE ENTRY PROPORTIONS"])
        for year in weighted_ent_counts:
            for lvl in weighted_ent_counts[year]:
                writer.writerow([year, lvl, weighted_ent_counts[year][lvl], entry_proportions[year][lvl]])

    with open(out_dir + "growth.csv", 'w') as out_grow:  # lol
        writer = csv.writer(out_grow)
        writer.writerow([profession.upper()])
        writer.writerow(["YEAR", "PROJECTED POPULATION", "SAMPLE PERCENT GROWTH SINCE PREVIOUS YEAR"])
        for year in estimated_pop:
            if year == min(sorted(list(estimated_pop.keys()))):  # only know pop growth after second year
                writer.writerow([year, estimated_pop[year], "NA"])
            else:
                writer.writerow([year, estimated_pop[year], estimated_pop_growth[year]])


def yearly_weights(person_year_table, profession, appellate_areas_to_sample, weighting_year):
    """
    Get following weights (as ratios), per year, per level:
     - retirement / retire + leave area
     - internal promotion / total promotions
     - external promotion / total entries

    All counts are based on comparing the sampled appellate areas to the population in the other appellate areas.

    NB: these weights pool across sampled areas

    NB: keys in base-level dicts indicate judicial level: 1 = low court, 2 = tribunal, 3 = appeals, 4 = high court

    NB: by convention I turn undefined weights (where the denominator is zero) to zero

    NB: assumes weighting years feature entire population.

    :param person_year_table: a table of person-years, as a list of lists; comes with header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param appellate_areas_to_sample: list of appellate area codes indicating which areas we sample, e.g. ["CA1, "CA5"]
    :param weighting_year: year based on which we draw weights. NB: since we measure mobility by comparing this year
                           with adjacted ones (e.g. we know you got promoted because your level in weighting_year is
                           less than your level in weighting_year+1), weighting_year actually signifies an interval.
                           So "2006" refers to mobility in the period 2006-2007. Years are as str, e.g. "2017".
    :return: dict of yearly weights
    """

    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    ca_cod_idx = helpers.get_header(profession, 'preprocess').index('ca cod')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # make the dicts that hold mobility counts per level
    lvls_dict = {"1": 0, "2": 0, "3": 0}
    total_retirements, total_area_leaves = deepcopy(lvls_dict), deepcopy(lvls_dict)
    total_promotions, internal_promotions = deepcopy(lvls_dict), deepcopy(lvls_dict)
    total_entries, external_promotions = deepcopy(lvls_dict), deepcopy(lvls_dict)

    # group table by persons
    person_year_table = sorted(person_year_table, key=operator.itemgetter(pid_col_idx, yr_col_idx))
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    people = [person for k, [*person] in groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # iterate through people
    for person in people:

        # iterate through person-years
        for idx, pers_yr in enumerate(person):

            if idx < 1:  # for the first year of the career; NB: this always assumes that we skip the left censor year

                # if first year is sampling year, and the person-year is in the sampling areas
                if pers_yr[yr_col_idx] == weighting_year and pers_yr[ca_cod_idx] in appellate_areas_to_sample:
                    # increment total entries
                    total_entries[pers_yr[lvl_col_idx]] += 1

            elif 0 < idx < len(person) - 1:  # look up to the second-last person-year

                # if this year is sampling year, and this person-year is in the sampling areas
                if pers_yr[yr_col_idx] == weighting_year and pers_yr[ca_cod_idx] in appellate_areas_to_sample:

                    # if current appellate area is different from next year appellate area, increment total area leaves
                    if pers_yr[ca_cod_idx] != person[idx + 1][ca_cod_idx]:
                        total_area_leaves[pers_yr[lvl_col_idx]] += 1

                    # if current appellate area is different from last year's appellate area AND
                    # last year's level is lower than this year's level, increment external promotions
                    if pers_yr[ca_cod_idx] != person[idx + 1][ca_cod_idx] \
                            and person[idx - 1][lvl_col_idx] < pers_yr[lvl_col_idx]:
                        external_promotions[pers_yr[lvl_col_idx]] += 1

                    # if this year's level is lower than next year's level, increment total promotions
                    if pers_yr[lvl_col_idx] < person[idx + 1][lvl_col_idx]:
                        total_promotions[pers_yr[lvl_col_idx]] += 1

                        # if this year's level is lower than next year's
                        # AND this year's appellate area is the same as next years, increment internal promotions
                        if pers_yr[ca_cod_idx] == person[idx + 1][ca_cod_idx]:
                            internal_promotions[pers_yr[lvl_col_idx]] += 1

            else:  # we're in the last year, i.e. the retirement year
                # NB: this always assume we pick a sampling year than is less than the right censoring year

                # if last year is sampling year and in sampling areas, increment retirements counter
                if person[-1][yr_col_idx] == weighting_year and person[-1][ca_cod_idx] in appellate_areas_to_sample:
                    total_retirements[person[-1][lvl_col_idx]] += 1

    # make retirement weights
    retirement_weights = {}
    for key in total_retirements:
        retirement_weights.update({key: helpers.weird_division(total_retirements[key],
                                                               (total_area_leaves[key] + total_retirements[key]))})
    # make internal promotion weights
    internal_promotion_weights = {}
    for key in total_promotions:
        internal_promotion_weights.update(
            {key: helpers.weird_division(internal_promotions[key], total_promotions[key])})

    # make external promotion weights
    external_promotion_weights = {}
    for key in total_entries:
        external_promotion_weights.update({key: helpers.weird_division(external_promotions[key], total_entries[key])})

    return {"ret_leave": retirement_weights,
            "int_prom": internal_promotion_weights,
            "ext_prom": external_promotion_weights}


def three_year_average_weights(person_year_table, profession, appellate_areas_to_sample, weighting_years):
    """
    Get average of weights from three different years.

    NB: assumes these years feature entire population.

    :param person_year_table: a table of person-years, as a list of lists; comes with header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param appellate_areas_to_sample: list of appellate area codes indicating which areas we sample, e.g. ["CA1, "CA5"
    :param weighting_years: list of years (as str) that we use for weighting, e.g. ["2012", "2013", "2015"]
                            NB: always assumed to be list of three elements.
    :return: dict of averaged weights
    """
    ratios_1 = yearly_weights(person_year_table, profession, appellate_areas_to_sample, weighting_years[0])
    ratios_2 = yearly_weights(person_year_table, profession, appellate_areas_to_sample, weighting_years[1])
    ratios_3 = yearly_weights(person_year_table, profession, appellate_areas_to_sample, weighting_years[2])

    ret_leave_1, ret_leave_2, ret_leave_3 = ratios_1["ret_leave"], ratios_2["ret_leave"], ratios_3["ret_leave"]
    int_prom_1, int_prom_2, int_prom_3 = ratios_1["int_prom"], ratios_2["int_prom"], ratios_3["int_prom"]
    ext_prom_1, ext_prom_2, ext_prom_3 = ratios_1["ext_prom"], ratios_2["ext_prom"], ratios_3["ext_prom"]

    sum_ret_leave = helpers.sum_dictionary_values([ret_leave_1, ret_leave_1, ret_leave_3])
    avg_ret_leave = {key: value / 3. for key, value in sum_ret_leave.items()}

    sum_int_prom = helpers.sum_dictionary_values(([int_prom_1, int_prom_2, int_prom_3]))
    avg_int_prom = {key: value / 3. for key, value in sum_int_prom.items()}

    sum_ext_prom = helpers.sum_dictionary_values([ext_prom_1, ext_prom_2, ext_prom_3])
    avg_ext_prom = {key: value / 3. for key, value in sum_ext_prom.items()}

    return {"ret_weight": avg_ret_leave, "int_prom_weight": avg_int_prom, "ext_prom_weight": avg_ext_prom}


def get_raw_counts(person_year_table, profession, sampling_year_range):
    """
    Get counts, in different years/intervals, of: number of professionals, entries, retirements, promotions.
    Keep only data for years in the year_range

    :param person_year_table: a table of person-years, as a list of lists; comes with header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param sampling_year_range: 2-tuple of ints, range of year's for which we're estimating mobility, e.g. (1998-2004)
    :return: dict of dicts, where top-level dicts indicate nature of count (e.g. "retirements") and bottom level
             dict shows count of retirements per judicial level (e.g. lvl2, i.e. tribunals)
    """

    total_counts = totals_in_out.pop_cohort_counts(person_year_table, 1978, 2020, profession,
                                                   cohorts=False, unit_type="nivel")

    entries = totals_in_out.pop_cohort_counts(person_year_table, 1978, 2020, profession,
                                              cohorts=True, unit_type="nivel", entry=True)

    retirements = totals_in_out.pop_cohort_counts(person_year_table, 1978, 2020, profession,
                                                  cohorts=True, unit_type="nivel", entry=False)

    promotions = hierarchical.hierarchical_mobility(person_year_table, profession)

    years = list(promotions.keys())

    # keep only level data for years within the specified year range
    retirements.pop("grand_total"), total_counts.pop("grand_total")

    for yr in years:
        # toss out extraneous years for promotions
        if int(yr) < sampling_year_range[0] or int(yr) > sampling_year_range[1]:
            if yr in promotions:
                promotions.pop(yr)

        # toss out extraneous years for retirements and total counts
        for key in retirements:
            if int(yr) < sampling_year_range[0] or int(yr) > sampling_year_range[1]:
                if int(yr) in retirements[key]:
                    entries[key].pop(int(yr))
                    retirements[key].pop(int(yr))
                    total_counts[key].pop(int(yr))

    # for entries retirements and total counts, only keep total size for that year
    # keys of promotion are the years, apply to all dicts
    ent_counts = {year: {"1": 0, "2": 0, "3": 0} for year in promotions.keys()}
    ret_counts = {year: {"1": 0, "2": 0, "3": 0} for year in promotions.keys()}
    tot_counts = {year: {"1": 0, "2": 0, "3": 0} for year in promotions.keys()}
    for lvl in retirements:
        for year in retirements[lvl]:
            ent_counts[str(year)][lvl] = entries[lvl][year]["total_size"]
            ret_counts[str(year)][lvl] = retirements[lvl][year]["total_size"]
            tot_counts[str(year)][lvl] = total_counts[lvl][year]["total_size"]

    # for promotions
    prom_counts = {year: {"1": 0, "2": 0, "3": 0} for year in promotions.keys()}
    for year in promotions:
        for lvl in promotions[year]:
            prom_counts[year][str(lvl)] = promotions[year][lvl]["up"]["total"]

    return {"entries": ent_counts, "retirements": ret_counts, "promotions": prom_counts, "total counts": tot_counts}


def estimated_population_size(person_year_table, areas_sample_table, profession, sampling_year_range):
    """
    Estimate the total size of the profession for the years in sampling_year_range. Assumes that the ratio between the
    sum of the sampled appeals areas and the sum of the rest of the areas remained constant over the entire data period.

    :param person_year_table: a table of person-years, as a list of lists; assumes no header
    :param areas_sample_table: a table of person-years within the sampled areas, as a list of lists; assumes no header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param sampling_year_range: 2-tuple of ints, range of year's for which we're estimating mobility, e.g. (1998-2004)
    :return: dict of estimated population sizes: keys are years, value are estimates
    """

    # get ratios of sample size to population size for for 2006, 2007, 2008.
    samp_size = totals_in_out.pop_cohort_counts(areas_sample_table, 1978, 2020, profession,
                                                cohorts=False, unit_type="nivel")
    pop_size = totals_in_out.pop_cohort_counts(person_year_table, 1978, 2020, profession,
                                               cohorts=False, unit_type="nivel")
    ratio_06 = samp_size["grand_total"][2006]["total_size"] / pop_size["grand_total"][2006]["total_size"]
    ratio_07 = samp_size["grand_total"][2007]["total_size"] / pop_size["grand_total"][2007]["total_size"]
    ratio_08 = samp_size["grand_total"][2008]["total_size"] / pop_size["grand_total"][2008]["total_size"]

    # average these ratios (across the three years)
    samp_to_pop_ratios = [ratio_06, ratio_07, ratio_08]
    avg_samp_to_pop_ratio = statistics.mean(samp_to_pop_ratios)

    # for each year, multiply the number of people in sample by reciprocal of sample size / population ratio: these are
    # the population estimate for the years in which we only have samples
    estim_pop = {}
    for year in samp_size["grand_total"]:
        if sampling_year_range[0] <= int(year) <= sampling_year_range[1]:
            estim_pop.update({str(year): round(float(samp_size["grand_total"][year]["total_size"])
                                               / float(avg_samp_to_pop_ratio))})
    return estim_pop


def estimated_population_growth(estimated_pop, sampling_year_range):
    """
    Estimate how much the population grew between any two years, expressed in percentages.
    :param estimated_pop: dict: keys are years, values are estimated population sizes
    :param sampling_year_range: 2-tuple of ints, range of year's for which we're estimating mobility, e.g. (1998-2004)
    :return: dict of estimated growth percentages: keys are years, values are percentages
    """
    estimated_growth = {}
    for year in range(sampling_year_range[0] + 1, sampling_year_range[1] + 1):
        year_diff = estimated_pop[str(year)] - estimated_pop[str(year - 1)]
        year_percent_growth = helpers.percent(year_diff, estimated_pop[str(year - 1)])
        estimated_growth.update({str(year): year_percent_growth})
    return estimated_growth


if __name__ == "__main__":
    root = "/home/radu/insync/docs/CornellYears/6.SixthYear/currently_working/judicial_professions/"
    branch = "data/judicial_professions/preprocessed/population/"
    leaf = "population_judges_preprocessed.csv"
    judges_population_filepath = root + branch + leaf
    tables_out_dir = root + "conference_presentations/esa_rn21_2020/data_tables/"

    with open(judges_population_filepath, 'r') as in_f:
        pers_yr_table = list(csv.reader(in_f))[1:]  # skip header

    retirement_promotion_estimates(pers_yr_table, "judges", (1985, 1996), tables_out_dir)
