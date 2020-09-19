"""
Script that models time to retirement, i.e. departure from the profession.

The code is organised as follows: make the appropriate data table in python, write it to disk, then run the
whole r-code from one continuous r chunk. The point is to a) always have the data table that we work with be
human-inspectable, and b) we can easily copy the r-code into RStudio or some other R interface, c) in this format,
just run everything with one click on one script, I don't want to go between two programs.
"""

import csv
import operator
from itertools import groupby
from rpy2.robjects import r
from helpers import helpers


def retirement_model(in_table_path, base_data_out_path, profession):
    """
    Model time to retirement as discrete-time survival/hazard model.

    NB: the table that we import is already in person-year file, but there's no binary marker for "retire" yet

    rpy2 tutorial: http://heather.cs.ucdavis.edu/~matloff/rpy2.html
    dicrete time event history tutorial: https://www.bristol.ac.uk/media-library/sites/cmm/migrated/documents/discrete-time-eha-july2013-combined.pdf
    r glm package tutorial: https://www.tutorialspoint.com/r/r_logistic_regression.htm
    dataframes from  Pandas to R :https://medium.com/@remycanario17/update-converting-python-dataframes-to-r-with-rpy2-59edaef63e0e

    :param in_table_path: str, path to where the person-year table (as csv) lives
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return:
    """
    # import the table from a csv
    with open(in_table_path) as in_f:
        table = list(csv.reader(in_f))

    # add a column marking when someone actually leaves the profession
    retirement_table = retire(table, profession)

    # write table to disk
    with open(base_data_out_path, 'w') as out_f:
        writer = csv.writer(out_f)
        [writer.writerow(person_year) for person_year in retirement_table]

    # load the data in R and run the R code chunk
    load_r_data(base_data_out_path)
    r(r_retirement_code)


def retire(person_year_table, profession):
    """
    Adds a column called "retire" with a "1" in the last year of a career, and a zero if it's not the last year,
    or if the observation is censored.

    NB: assumes that person-year table is already presorted by unique person ID and year

    :param person_year_table: a table of person-years, as a list of lists; comes with header
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return: the augmented person-year table
    """
    # get handy column indexes
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')

    # save original header
    header = person_year_table[0]

    # sort table by unique person ID and year; skip header
    person_year_table = sorted(person_year_table[1:], key=operator.itemgetter(pid_col_idx, yr_col_idx))

    # initialise the new table with updated header
    table_with_retire_col = [header + ["retire"]]

    # get right censor year
    yr_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    right_censor_yr = person_year_table[-1][yr_col_idx]

    # group table by persons
    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    people = [person for k, [*person] in groupby(person_year_table, key=operator.itemgetter(pid_col_idx))]

    # iterate through people, adding the "retire" value in the last column and extending the updated table
    for person in people:
        new_pers_data = [pers_yr + ["0"] for pers_yr in person]

        # if last year of the career is not right censor year, change that value to "1", i.e. mark retirement
        if person[-1][yr_col_idx] != right_censor_yr:
            new_pers_data[-1][-1] = "1"

        # add the updated person-years to person-period table with the retirement column
        table_with_retire_col.extend(new_pers_data)

    return table_with_retire_col


def load_r_data(csv_data_path):
    """
    Load data table into R, depending on profession.
    :return:
    """
    r_code = 'retire_data <- read.csv("' + csv_data_path + '", header = TRUE)'
    r(r_code)


r_retirement_code = """
                    library(lme4)

                    # convert the person IDs and years to factor (we'll treat these as categorical)
                    retire_data$cod.persoană <- as.factor(retire_data$cod.persoană)
                    retire_data$an <- as.factor(retire_data$an)
                    
                    # for "sex", use male as reference category
                    retire_data <- within(retire_data, sex <- relevel(sex, ref = "m"))
                    
                    #retire_model = glmer(formula = retire ~ sex * an, data = retire_data, family = binomial)
                    
                    retire_model <- glmer(
                                          retire ~ an + (1 | sex), 
                                          data = retire_data,
                                          family = binomial(link = "logit")
                                         )
                    
                    rm_summary <- summary.lm(retire_model)
                    #rm_summary$coefficients <- rm_summary$coefficients[1:55,]
                    print(rm_summary)


                    #print(str(retire_data))


                    #print(head(data, 5))
                    """

# build the model, in steps
# 1) retire ~ year (year as categorical, use 1988 as reference)
# 2) retire ~ year, sex (as categorical, male as reference) and year*sex cross term
# 3) retire ~ year, sex, year*sex, personID fixed effects
# 4) retire ~ year, sex, year*sex, personID FE, CA area random effects (random slope and intercept)
# 4) retire ~ year, sex, year*sex, personID FE, jud nested in trib nested in ca, all RE with rand slope &
# intercept
