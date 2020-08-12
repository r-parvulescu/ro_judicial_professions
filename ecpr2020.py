"""
Code for generating data used in my ECPR 2020 presentation, "COVID and Judicial Appointments".
"""

import csv
from natsort import natsorted
from copy import deepcopy
import itertools
import operator
from preprocess import sample, preprocess
from preprocess.workplace import workplace
from helpers import helpers
from describe import describe


def up_to_july(professions):
    """
    Runs normal, inter-year mobility analysis using only data for the first seven months of each year, i.e. up to July.

    :param professions: dict where key is profession name and value is base path to month-level data table
    :return: None
    """

    for prof, path in professions.items():

        # THIS IS FOR RUNNING ANALYSES USING ONLY MONTH DATA UP TO JULY

        # NB: for the sampler below to work properly (i.e. always try to sample July) you need to change the
        # value for "judges" in function preprocess.sample.get_sampling_month rom 4 to 7. Otherwise it tries to sample
        # April, for judges. No such issue for prosecutors.

        # for each year, sample by throwing out all observations occurring in months AFTER July
        with open(path, 'r') as infile:
            person_month_table = list(csv.reader(infile))[1:]
        sampled_years = [y for y in range(2006, 2021)]
        sampled_table = sample.mo_yr_sample(person_month_table, prof, [1, 2, 3, 4, 5, 6, 7], sampled_years)
        # write sampled table to disk
        samp_file_dir = root + 'conference_presentations/ecpr_2020/data/' + prof + '/' + 'sampled_collected/'
        with open(samp_file_dir + prof + '_to_july_sampled_month.csv', 'w') as out_file:
            writer = csv.writer(out_file)
            [writer.writerow(pm) for pm in sampled_table]

        # run preprocessor on sampled data
        prep_dir = root + 'conference_presentations/ecpr_2020/data/' + prof + '/' + 'preprocessed/'
        prep_file_path = prep_dir + prof + '_preprocessed.csv'
        std_log_path = prep_dir
        pids_log_path = prep_dir
        preprocess.preprocess(samp_file_dir, prep_file_path, std_log_path, pids_log_path, prof)

        # get descriptor tables using the preprocessed data
        descr_out_dir = root + 'conference_presentations/ecpr_2020/data/' + prof + '/' + 'descriptors/'
        with open(prep_file_path, 'r') as in_f:
            table = list(csv.reader(in_f))[1:]

        start_year, end_year = 2006, 2020

        # make table of total counts per year
        describe.year_counts_table(table, start_year, end_year, prof, descr_out_dir)

        # make tables of total counts per year, per level in judicial hierarchy
        describe.year_counts_table(table, start_year, end_year, prof, descr_out_dir, unit_type='nivel')

        # make tables for entry and  exit cohorts, per year, per gender, per level in judicial hierarchy
        describe.entry_exit_gender(table, start_year, end_year, prof, descr_out_dir, entry=False, unit_type='nivel')
        describe.entry_exit_gender(table, start_year, end_year, prof, descr_out_dir, entry=True, unit_type='nivel')

        # make table for mobility between appellate court regions
        describe.inter_unit_mobility_table(table, descr_out_dir, prof, 'ca cod')

        # make table for hierarchical mobility
        describe.hierarchical_mobility_table(table, descr_out_dir, prof)

        for unit_type in ['ca cod', 'nivel']:
            # make tables for entry and exit cohorts, per year per unit type
            describe.entry_exit_unit_table(table, start_year, end_year, prof, unit_type, descr_out_dir, entry=True)
            describe.entry_exit_unit_table(table, start_year, end_year, prof, unit_type, descr_out_dir, entry=False)


def between_month_mobility(professions, season):
    """
    Compares within-year mobility between two months (typically April and June) across four years, to see if mobility
    in that interval differs significantly across years.

    NB: the unique identifiers here are full names, on the assumption that there is minimal spurious variance in one
    person's full name across a 3-4 month gap in one year (e.g. it's unlike they get married then and change their
    name in that interval).

    :param professions: dict where key is profession name and value is base path to month-level data table
    :param season: str, season for the months of which we analyse mobility
    :return: None
    """
    if season == 'spring-summer':
        sample_months_years = {'judges': {2020: (4, 6), 2019: (4, 6), 2018: (4, 6), 2017: (4, 6)},
                               'prosecutors': {2020: (4, 7), 2019: (4, 6), 2018: (5, 7), 2016: (4, 6)}}

    else:  # season == fall-winter
        sample_months_years = {'judges': {2019: (9, 12), 2017: (9, 12), 2016: (9, 12), 2015: (9, 12)},
                               'prosecutors': {2019: (9, 12), 2017: (9, 12), 2016: (9, 12), 2015: (9, 12)}}

    for prof, path in professions.items():
        # get person-month table
        with open(path, 'r') as in_file:
            pm_table = list(csv.reader(in_file))[1:]  # start from first index to skip header

        # get samples
        samples = {}
        for year, months in sample_months_years[prof].items():
            # get year_month sample
            samp = sample.mo_yr_sample(pm_table, prof, months, [year])

            # upgrade sample with workplace profile;
            wrk_plc_idx = helpers.get_header(prof, "collect").index("instanță/parchet")
            workplace_codes = workplace.get_workplace_codes(prof)
            samp_upgr = [p_mo + workplace.get_workplace_profile(p_mo[wrk_plc_idx], workplace_codes)
                         for p_mo in samp]  # p_mp means "person month"

            # something wrong with CA Craiova for judges, numbers are whack for 2019 and 2020
            # remove and see if patterns still hold
            if prof == 'judges':
                samp_upgr = [p_mo for p_mo in samp_upgr if p_mo[-4] != 'CA7']

            samples.update({year: samp_upgr})

            # NB: by this point the column headers would be (in this order):
            # ["nume", "prenume", "instanță/parchet", "an", "lună", "ca cod", "trib cod", "jud cod", "nivel"]

        # initialise the profession-specific dicts holding the descriptives; NB: get counts for "nivel" and "ca cod"
        mob_dict = {'entries': 0, 'exits': 0, 'up': 0, 'down': 0, 'across': 0}
        levels, cas = ['1', '2', '3', '4'], natsorted(list({p_mo[5] for p_mo in samples[2019]}))
        lvl_mob_dict = {year: {lvl: deepcopy(mob_dict) for lvl in levels} for year in samples}
        ca_mob_dict = {year: {ca: deepcopy(mob_dict) for ca in cas} for year in samples}

        for year, smpl in samples.items():
            first_mo, last_mo = sample_months_years[prof][year][0], sample_months_years[prof][year][1]

            # caclulate entries and exits between months, separately for level vs geographic area/agency
            fullnames_in_first_month = {p_mo[0] + ' | ' + p_mo[1] for p_mo in smpl if int(p_mo[4]) == first_mo}
            fullnames_in_second_month = {p_mo[0] + ' | ' + p_mo[1] for p_mo in smpl if int(p_mo[4]) == last_mo}

            # entries: unique full names in second month that aren't in first month
            entries = fullnames_in_second_month - fullnames_in_first_month
            # exits: unique full names in first month that aren't in second month
            exits = fullnames_in_first_month - fullnames_in_second_month

            # update the mobility dicts with entry and exit counts
            for p_mo in smpl:
                if p_mo[0] + ' | ' + p_mo[1] in entries:
                    lvl_mob_dict[year][p_mo[-1]]['entries'] += 1  # p_mo[-1] = level
                    ca_mob_dict[year][p_mo[-4]]['entries'] += 1  # p_mo[-4] = ca cod
                if p_mo[0] + ' | ' + p_mo[1] in exits:
                    lvl_mob_dict[year][p_mo[-1]]['exits'] += 1
                    ca_mob_dict[year][p_mo[-4]]['exits'] += 1

            # now for each sample calculate intermonth up, down, and across mobilities

            # group the table by person fullname, throw out all fullnames with anything besides two observations,
            # i.e. don't look at people we see only once, and people we see more than twice are errors (but count these
            # so I know how big of errors we're talking here)

            # make a new table with merged names, i.e. first column is the full name
            fn_table = [[p_mo[0] + ' | ' + p_mo[1]] + p_mo[2:] for p_mo in smpl]
            # NB: columns now ["fullname", "instanță/parchet", "an", "lună", "ca cod", "trib cod", "jud cod", "nivel"]

            # group table by persons, identified by unique full name; fullname is now at the zero index
            # sort table by fullname and month
            people = [person for k, [*person] in itertools.groupby(sorted(fn_table, key=operator.itemgetter(0, 3)),
                                                                   key=operator.itemgetter(0))]

            # throw out persons with only one obs (by definition can't experience within-system mobility) as well as
            # persons with more than two observations (e.g. very common names); these are both sources of measurement
            # error, so mark down how many we throw out of each type for our knowledge
            num_one_obs = len([1 for person in people if len(person) < 2])
            num_multi_obs = len([1 for person in people if len(person) > 2])
            print(prof.upper())
            print('  %s TOTAL PERSONS IN YEAR %s' % (len(people), year))
            print('  %s PERSONS WITH ONE OBSERVATION IN YEAR %s' % (num_one_obs, year))
            print('  %s PERSONS WITH THREE OR MORE OBSERVATIONS IN YEAR %s' % (num_multi_obs, year))
            print('\n')

            two_obs_persons = [person for person in people if len(person) == 2]

            # then for each person see if their level changed between the two months; update data dicts accordingly
            # by convention, the level/ca cod for which we report mobility is level/ca cod of first month/period
            for person in two_obs_persons:
                # person[0] == month 1 obs, person[1] == month 2 obs; person[int][-1] == person month obs level

                # down mobility
                if int(person[0][-1]) < int(person[1][-1]):
                    lvl_mob_dict[year][person[0][-1]]['down'] += 1  # person[0][-1] = level
                    ca_mob_dict[year][person[0][-4]]['down'] += 1  # person[0][-3] == ca cod

                # up mobility
                if int(person[0][-1]) > int(person[1][-1]):
                    lvl_mob_dict[year][person[0][-1]]['up'] += 1  # person[0][-1] = level
                    ca_mob_dict[year][person[0][-4]]['up'] += 1  # person[0][-3] == ca cod

                # across mobility
                # person[int][1] == person month obs workplace name;
                if int(person[0][-1]) == int(person[1][-1]) and person[0][1] != person[1][1]:
                    lvl_mob_dict[year][person[0][-1]]['across'] += 1  # person[0][-1] = level
                    ca_mob_dict[year][person[0][-4]]['across'] += 1  # person[0][-3] == ca cod

        # now make one profession-leve table per mobility types
        mobility_dicts = {'levels_mobility': lvl_mob_dict, 'ca_regions_mobility': ca_mob_dict}
        ordered_years = sorted(list(lvl_mob_dict.keys()))
        mobility_types = list(mob_dict.keys())
        for mob_dict_name, mob_dict in mobility_dicts.items():

            descr_out_dir = root + 'conference_presentations/ecpr_2020/data/' + prof + '/' \
                            + 'descriptors/' + season + '/'
            mob_table_path = descr_out_dir + mob_dict_name + '.csv'
            with open(mob_table_path, 'w') as out_f:
                writer = csv.writer(out_f)

                for mob_type in mobility_types:
                    writer.writerow([prof.upper()])
                    writer.writerow(["INTER MONTH MOBILITY RATE: %s" % (mob_type.upper())])
                    writer.writerow(['unit/level'] + ordered_years)

                    units = cas if 'ca' in mob_dict_name else levels
                    for u in units:
                        data_row = [u]

                        for year in ordered_years:
                            data_row.append(mob_dict[year][u][mob_type])

                        writer.writerow(data_row)
                    writer.writerow('\n')


if __name__ == '__main__':
    root = '/home/radu/insync/docs/CornellYears/6.SixthYear/currently_working/judicial_professions/'
    trunk = root + 'data/collected/'
    samp_file_path = root + 'conference_presentations/ecpr_2020/data/'
    profs = {'prosecutors': trunk + 'prosecutors/prosecutors_month.csv',
             'judges': trunk + 'judges/judges_month.csv'}

    up_to_july(profs)
    between_month_mobility(profs, 'spring-summer')
    between_month_mobility(profs, 'fall-winter')
