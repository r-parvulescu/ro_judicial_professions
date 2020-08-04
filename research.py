"""
One file to click-and-play for the research pipeline: collect the data, preprocess it, generate descriptive statistics,
then do statistical analysis (to come).
"""

from collect import make_table, scrape
from preprocess import preprocess
from describe import describe
from local import root
from pathlib import Path

# DIRECTORY STRUCTURE FOR RESEARCH WORKFLOW #

root = root

trunks = {'dispersed': 'data/dispersed/',
          'collected': 'data/collected/',
          'preprocessed': 'data/preprocessed/',
          'descriptives': 'analysis/descriptives/'}

leaves = {'judges': {'dispersed': {'raw': 'magistrati/compressed_data_clean/judges_raw_clean/',
                                   'scrape log': 'magistrati/compressed_data_cleaned/scrape_log.txt'},
                     'collected': {
                         'file': 'judges/judges',
                         'dir': 'judges/'
                     },
                     'preprocessed': {
                         'population': 'population/population_judges_preprocessed.csv',
                         'standardise': 'standardise_logs_tests/standardise_logs_output_judges/',
                         'pids': 'pids_logs_tests/pids_logs_judges/'
                     },
                     'descriptives': 'descriptives_judges/'

                     },
          'prosecutors': {'dispersed': {'raw': 'magistrati/compressed_data_clean/prosecutors_raw_clean/',
                                        'scrape log': 'magistrati/compressed_data_cleaned/scrape_log.txt'},
                          'collected': {
                              'file': 'prosecutors/prosecutors',
                              'dir': 'prosecutors/'
                          },
                          'preprocessed': {
                              'population': 'population/population_prosecutors_preprocessed.csv',
                              'standardise': 'standardise_logs_tests/standardise_logs_output_prosecutors/',
                              'pids': 'pids_logs_tests/pids_logs_prosecutors/'
                          },
                          'descriptives': 'descriptives_prosecutors/'
                          },

          'executori': {'dispersed': {'raw': 'executori_judecatoresti/compressed_data_clean'},
                        'collected': {
                            'file': 'executori/executori',
                            'dir': 'executori/'
                        },
                        'preprocessed': {
                            'population': 'population/population_executori_preprocessed.csv',
                            'standardise': 'standardise_logs_tests/standardise_logs_output_executori/',
                            'pids': '/pids_logs_tests/pids_logs_executori/'
                        },
                        'descriptives': 'descriptives_executori/'
                        },

          'notaries': {'dispersed': {'raw': 'notari_publici/compressed_data_clean'},
                       'collected': {
                           'file': 'notaries/notaries_persons',
                           'dir': 'notaries/'
                       },
                       'preprocessed': {
                           'population': 'population/population_notaries_preprocessed.csv',
                           'standardise': '',
                           'pids': ''
                       },
                       'descriptives': 'descriptives_notaries/'
                       },
          'combined': {'preprocessed': {'population': 'population/population_combined_professions.csv',
                                        'sample': ''},
                       'descriptives': {
                           'population': 'descriptives_combined/population/',
                       }
                       }
          }

if __name__ == '__main__':
    # run the data pipeline for each professional separately: collection, preprocess, describe
    # write output at each steps, to check logs and so that early steps are saved if later ones error out

    # the dictionary of professions, the years for which each has data, and the units for deaggregated analyses
    professions_details = {'judges': {'range': (1988, 2020),
                                      'units': ('ca cod', 'nivel'),
                                      'samples': ['population',
                                                  'continuity_sample_1988']},
                           'prosecutors': {'range': (1988, 2020),
                                           'units': ('ca cod', 'nivel'),
                                           'samples': ['population',
                                                       'continuity_sample_1988']},
                           'executori': {'range': (2001, 2019),
                                         'units': None,
                                         'samples': ['population']},
                           'notaries': {'range': (1995, 2019),
                                        'units': None,
                                        'samples': ['population']}
                           }

    for prof, deets in professions_details.items():

        # update data with recently uploaded materials from public, state, digital archives
        # NB: only judges and prosecutors have such publicly available data
        if prof in {'judges', 'prosecutors'}:
            in_dir = root + trunks['dispersed'] + leaves[prof]['dispersed']['raw']
            scrape_log = root + trunks['dispersed'] + leaves[prof]['dispersed']['scrape log']
            scrape.update_db(in_dir, scrape_log, prof)

        # collect the data (which also does a first clean)
        in_dir = root + trunks['dispersed'] + leaves[prof]['dispersed']['raw']
        out_path = root + trunks['collected'] + leaves[prof]['collected']['file']
        make_table.make_pp_table(in_dir, out_path, prof)

        # preprocess the data (add variables, standardise names, assign unique IDs, etc.)
        in_dir = root + trunks['collected'] + leaves[prof]['collected']['dir']
        pop_out_path = root + trunks['preprocessed'] + leaves[prof]['preprocessed']['population']
        std_log_path = root + trunks['preprocessed'] + leaves[prof]['preprocessed']['standardise']
        pids_log_path = root + trunks['preprocessed'] + leaves[prof]['preprocessed']['pids']
        preprocess.preprocess(in_dir, pop_out_path, std_log_path, pids_log_path, prof)

        # describe the data, i.e. generate tables of descriptive statistics for different samples
        pop_in_file = root + trunks['preprocessed'] + leaves[prof]['preprocessed']['population']
        for sample in deets['samples']:
            # make directory tree for dumping the descriptives tables; NB: overwrites existing tree structure
            sample_out_dirs = {'totals': '', 'entry_exit': '', 'mobility': '', 'inheritance': ''}
            for d in sample_out_dirs:
                path_end = sample + '/' + d + '/'
                sample_out_dirs.update({d: root + trunks['descriptives'] + leaves[prof]['descriptives'] + path_end})
            [Path(d).mkdir(parents=True, exist_ok=True) for d in sample_out_dirs.values()]
            # generate the descriptives tables
            describe.describe(pop_in_file, sample, sample_out_dirs['totals'], sample_out_dirs['entry_exit'],
                              sample_out_dirs['mobility'], sample_out_dirs['inheritance'], prof,
                              deets['range'][0], deets['range'][1], deets['units'])

    # now do inter-professional comparisons

    # first combine preprocessed data from diverse professions into one table;
    # we do this for the entire population, though can also be done for a sample
    in_dir = root + trunks['preprocessed'] + 'population'
    prep_out_path = root + trunks['preprocessed'] + leaves['combined']['preprocessed']['population']
    make_table.combine_profession_tables(in_dir, prep_out_path)

    # then we look for transitions from one profession to the other, for a 3-year time window
    combined_out_dir = root + trunks['descriptives'] + leaves['combined']['descriptives']['population']
    Path(combined_out_dir).mkdir(parents=True, exist_ok=True)
    describe.inter_profession_transfer_table(prep_out_path, combined_out_dir, 1)
