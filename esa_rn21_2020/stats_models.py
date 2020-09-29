"""
Functions for modelling instantaneous hazard of mobility events, i.e. probability of mobility event in a time-point.
"""

import csv
import operator
import itertools
import statistics
from datetime import datetime
from rpy2.robjects import r
from helpers import helpers


def build_data_table(input_py_table, col_augmented_py_table, profession, period_dummies=False):
    """
    Adds a columns to our data table, including dummmies for the main independent variables. Writes the table to disk,
    so we can visually inspect.

    NB: when we put a person-year within a period, that particular year actually indicates the start year of a two-year
    interval in which mobility may occur, because we measure mobility inter-temporally: e.g. we know person X retired in
    that year because they're not in the data the next year. This explains certain period-coding choices, such as
    1989 not being coded as "communism" but as "revolution", since the mobility value for 1989 actually measures whether
    there was mobility in the interval 1989-1990, which as a whole was as revolutionary interval. The open bracket at
    the end of the period below means that we don't look at the interval starting with that year: so for [2012, 2016),
    for example, we consider 2012-13, 2013-14, 2014-15, 2015-16, but NOT 2016-17.

    The periods are:
     - [2005, 2012): CSM reforms & "mica reformă", val = "csm"
     - [2012, 2016): legal codes reforms, val = "codes"
     - [2016, 2020): judicial independence reforms, val = "indep"

    :param input_py_table: person-year table (as list of lists), without columns necessary for the hazard models
    :param col_augmented_py_table: person-year table (as list of lists), WITH new, desired columns
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :param period_dummies: bool, True if you want additional columns which put in one dummy column for each period
    :return: None
    """

    # get handy column indexes
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # initialise the periodisation
    years_periods = {2005: "csm", 2006: "csm", 2007: "csm", 2008: "csm", 2009: "csm", 2010: "csm", 2011: "csm",
                     2012: "codes", 2013: "codes", 2014: "codes", 2015: "codes",
                     2016: "indep", 2017: "indep", 2018: "indep", 2019: "indep"}

    # load the old table, saving the original header
    with open(input_py_table) as in_f:
        person_year_table = list(csv.reader(in_f))
    header = person_year_table[0]

    # initialise new table, with updated header
    new_table = [header + ["entry", "promotion", "retire", "career_length", "period"]]

    # sort old table by unique person ID and year (skip header), and group it by persons
    person_year_table = sorted(person_year_table[1:], key=operator.itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # iterate through people, adding columns and extending the new, column-augmented table
    for person in people:

        for idx, pers_yr in enumerate(person):

            # order of columns is: retire, entry, promoted, period, career length
            entry, promotion, retire, career_length, period = 0, 0, 0, 0, ''

            # by convention, first year in career is "1 year of experience," i.e. 1-indexing
            career_length = idx + 1

            # add period; if a certain year is not in our periodisation, leave empty value
            if int(pers_yr[yr_col_idx]) in years_periods:
                period = years_periods[int(pers_yr[yr_col_idx])]

            # first year of career
            if idx < 1:
                entry = 1

            # non edge years
            elif 0 < idx < len(person) - 1:

                # if your level is lower this year than next, it means you're promoted;
                # by convention, promotion is marked in the anterior year
                if person[idx - 1][lvl_col_idx] < pers_yr[lvl_col_idx]:
                    promotion = 1

            else:  # last year of career
                retire = 1

            new_row = pers_yr + [entry, promotion, retire, career_length, period]

            new_table.append(new_row)

    # if period dummy switch is on, turn "period" column from factors to dummies, appended to end of table
    if period_dummies:
        new_table_with_dummies = [new_table[0] + ["csm_dummies", "codes_dummies", "indep_dummies"]]
        period_col_index_dict = {"csm": 0, "codes": 1, "indep": 2}
        for py in new_table[1:]:  # skip header
            period = py[-1]
            dummy_vals = ['', '', '']
            if period:  # skips rows for which there is no periodisation
                dummy_vals = [0, 0, 0]
                dummy_vals[period_col_index_dict[period]] = 1
            new_table_with_dummies.append(py + dummy_vals)
        new_table = new_table_with_dummies

    # write table to disk
    with open(col_augmented_py_table, 'w') as out_f:
        writer = csv.writer(out_f)
        [writer.writerow(person_year) for person_year in new_table]


def subset_data(full_data_table_path, subset_data_table_path, profession):
    """
    Select a portion of the data to feed into the hazard models, focusing on the desired time-period and make it
    possible to run regressions with person-level fixed effects (which means that everyone must have at least two
    observations). Normally this would be done in R, but I'm bad at R subsetting.

    I want the subset table on disk so humans can inspect it.

    :param full_data_table_path: str, path to the full data table
    :param subset_data_table_path: str, path to where we want the subset table to live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return: None
    """

    # get handy column headers
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    lvl_col_idx = helpers.get_header(profession, 'preprocess').index('nivel')

    # load the data
    with open(full_data_table_path, 'r') as in_f:
        full_py_table = list(csv.reader(in_f))
    # initialise subset table, with header
    subset_table = [full_py_table[0]]

    # only keep years between 2006 and 2019, inclusive,
    # and throw out all observations on the high court, i.e. level 4, too few to analyse statistically; skip header
    filtered_table = [py for py in full_py_table[1:] if 2005 < int(py[yr_col_idx]) < 2020 and py[lvl_col_idx] != "4"]

    # sort table by unique person ID and year then group it by persons
    filtered_table = sorted(filtered_table, key=operator.itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(filtered_table, key=operator.itemgetter(pid_col_idx))]

    # only keep people with minimum two-year careers
    for person in people:
        # if switch is on, skip people with only one person-year observed
        if len(person) < 2:
            continue
        else:
            subset_table.extend(person)

    # write subset table to disk
    with open(subset_data_table_path, 'w') as out_f:
        writer = csv.writer(out_f)
        [writer.writerow(person_year) for person_year in subset_table]


def demean_periods_by_person(input_table_path, outpath_demeaned_table, profession):
    """
    Makes columns with demeaned values for the period dummies, where the person is the group on which we demean.
    Also include columns with the person-level mean of the period dummies.

    :param input_table_path: path to table, some of whose variables we'll demean
    :param outpath_demeaned_table: path where table with demeaned variables will live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return: None
    """

    # load up the old table, initialise the demeaned table with the new table's header
    with open(input_table_path, 'r') as in_f:
        input_table = list(csv.reader(in_f))
    old_header = input_table[0]

    demeaned_table = []

    # sort the table by person and year, group by person; skip header in old table
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    input_table = sorted(input_table[1:], key=operator.itemgetter(pid_col_idx, yr_col_idx))
    people = [person for k, [*person] in itertools.groupby(input_table, key=operator.itemgetter(pid_col_idx))]

    demeaned_table_header = old_header

    # indexes for csm, codes, and indep dummies are 16, 17, 18

    # demean the specified variable, where the "mean" of the variable is taken across the specified stratum
    for person in people:
        csm_mean = statistics.mean([int(pers_yr[16]) for pers_yr in person])
        codes_mean = statistics.mean([int(pers_yr[17]) for pers_yr in person])
        indep_mean = statistics.mean([int(pers_yr[18]) for pers_yr in person])

        # now demean the existing values, and add new row to the demeaned table
        for pers_yr in person:
            demeaned_csm = int(pers_yr[16]) - csm_mean
            demeaned_codes = int(pers_yr[17]) - codes_mean
            demeaned_indep = int(pers_yr[18]) - indep_mean

            demeaned_table.append(pers_yr + [demeaned_csm, csm_mean, demeaned_codes, codes_mean,
                                             demeaned_indep, indep_mean])

    demeaned_table_header.extend(["demeaned_csm", "csm_mean", "demeaned_codes", "codes_mean",
                                  "demeaned_indep", "indep_mean"])
    demeaned_table.insert(0, demeaned_table_header)

    # write the demeaned table to disk
    with open(outpath_demeaned_table, 'w') as out_f:
        writer = csv.writer(out_f)
        [writer.writerow(pers_yr) for pers_yr in demeaned_table]


def run_stat_model(data_file_path):
    """
    Loads the data into R then runs the model in an R instance, handled via rpy2.

    :param data_file_path: str, path to our data table (which is on disk)
    :return:
    """

    # load the data in R
    r('mobility_data <- read.csv("' + data_file_path + '", header = TRUE)')

    # see when the model started
    print(datetime.now())

    # run R code chunks
    r(r_prep_code)
    r(r_retirement_model_code)
    r(r_entry_model_code)

    # see when the model ended
    print(datetime.now())


r_prep_code = """
              library(survival)
              library(lme4)
              
              #library(rstanarm)
              #options(mc.cores = parallel::detectCores())
              
              # convert person ID and level to factors
              mobility_data$cod.persoană <- as.factor(mobility_data$cod.persoană)
              mobility_data$nivel <- as.factor(mobility_data$nivel)
                                        
              # for the appeals areas, make Bucharest (the capital city) the reference category
              mobility_data <- within(mobility_data, ca.cod <- relevel(ca.cod, ref = "CA4"))
              
              # make men the reference category
              mobility_data <- within(mobility_data, sex <- relevel(sex, ref = "m"))

              # check that key independent variables look the way you want them to
              print(unique(mobility_data$an))
              print(unique(mobility_data$nivel))
              print(unique(mobility_data$period))
              """

r_retirement_model_code = """
                          # the main point of this model is to check that a) period effects are not absorbed by either 
                          # area effects (ca.cod), career length effects, or person-level effects, and 
                          # b) whether period-level interactions matter, and how

                          # NB: since I'm including terms for the "csm" and "codes" period, the "indep" period is 
                          # implicitly the reference category
                          
                          # NB: I run things under clogit and glm just to make sure that I'm getting the same output

                          # run the model in clogit
                          retire_clogit <- clogit(
                                                  formula = retire ~ ca.cod + sex + career_length + nivel +  
                                                            csm_mean * nivel + codes_mean * nivel + 
                                                            demeaned_csm * nivel + demeaned_codes * nivel,
                                                  data = mobility_data,
                                                  method = "efron"
                                                 )
                          print(summary(retire_clogit))

 
 
                          # run the model in glm
                          retire_glm <- glm(
                                            formula = retire ~ ca.cod + sex + career_length + nivel +  
                                                      csm_mean * nivel + codes_mean * nivel + demeaned_csm * nivel + 
                                                      demeaned_codes * nivel,
                                            data = mobility_data,
                                            family = binomial(link="logit")
                                            )
                          print(summary(retire_glm))
                                                      


                          # do person-level random effects to get proper confidence intervals, start with random slopes
                          retire_glmer <- glmer(
                                                formula = retire ~ ca.cod + sex + career_length + nivel +  
                                                                   csm_mean * nivel + codes_mean * nivel + 
                                                                    demeaned_csm * nivel + demeaned_codes * nivel +
                                                                   (1 | cod.persoană),
                                                data = mobility_data,
                                                family = binomial(link="logit")
                                                )
                          print(summary(retire_glmer))
                          
                          # COMMENTED OUT BECAUSE IT TAKES IMPOSSIBLY LONG
                          
                          # try fitting a Bayesian glmer, default settings on priors, see if it's feasible -- this is 
                          # fishing a bit 
                          #retire_stan_glmer <- stan_glm(
                          #                                formula = retire ~ period,
                          #                                data = mobility_data,
                          #                                family = binomial(link="logit")
                          #                                )
                                                          
                          #print(summary(retire_stan_glmer))
                          
                          # add predicted probabilities (using the data, from glm) as a last column from the data
                          mobility_data <- cbind(mobility_data, new_col = fitted(retire_glm))

                          
                          """

r_entry_model_code = """          
                      # entry is run without levels, since the vast majority of people enter at the 
                      # first level, very, very few at higher level, not enough power to estimate
                      
                      # also no career length, since entry is ALWAYS at the beginning of a career, perfect 
                      # correlation with career_length = 1
                      
                      # basically, just want to make sure that period effects are totally absorbed by area effects
            
                      # run the model in clogit
                      entry_clogit <- clogit(
                                              formula = entry ~ period + ca.cod,
                                              data = mobility_data,
                                              method = "efron"
                                             )
                                             
                      # run the model in glm
                      entry_glm <- glm(
                                        formula = entry ~ period + ca.cod,
                                        data = mobility_data,
                                        family = binomial(link="logit")
                                        )
                                      
                      # compare model output: don't want effects to be driven by choice of conditional logit  
                      print(summary(entry_clogit))
                      print(summary(entry_glm))
                     """

r_promotion_model_code = ""

if __name__ == "__main__":
    root = "/home/radu/insync/docs/CornellYears/6.SixthYear/currently_working/judicial_professions"
    in_table_leaf = "/data/judicial_professions/preprocessed/population/population_judges_preprocessed.csv"
    out_table_outpath = "/conference_presentations/esa_rn21_2020/model_output/judges_population_mobility_columns.csv"
    filtered_table_outpath = "/conference_presentations/esa_rn21_2020/model_output/judges_filtered.csv"
    demeaned_table_outpath = "/conference_presentations/esa_rn21_2020/model_output/judges_filtered_demeaned.csv"

    build_data_table(root + in_table_leaf, root + out_table_outpath, "judges", period_dummies=True)

    subset_data(root + out_table_outpath, root + filtered_table_outpath, "judges")

    demean_periods_by_person(root + filtered_table_outpath, root + demeaned_table_outpath, "judges")

    run_stat_model(root + demeaned_table_outpath)

"""
    # [1984-1989) : communism -- [1989, 1992) : revolution -- [1992, 1996) -- Law92, i.e. de jure legal system overhaul 
    years_periods = {1985: "communism", 1986: "communism", 1987: "communism", 1988: "communism",
                     1989: "revolution", 1990: "revolution", 1991: "revolution",
                     1992: "law92", 1993: "law92", 1994: "law92", 1995: "law92"}
"""
