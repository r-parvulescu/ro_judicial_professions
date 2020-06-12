"""
One file to click-and-play for the research pipeline: collect the data, preprocess it, generate descriptive statistics,
then do statistical analysis (to come).
"""

from collect import make_table
from preprocess import preprocess
from describe import describe
from local import root

# DIRECTORY STRUCTURE FOR RESEARCH WORKFLOW #

# NB: this script assumes that user has ALREADY created this structure
root = root

trunks = {'dispersed': 'data/dispersed/',
          'collected': 'data/collected/',
          'preprocessed': 'data/preprocessed/',
          'descriptives': 'analysis/descriptives/'}

leaves = {'judges': {'dispersed': 'magistrati/code_ready/judges',
                     'collected': {
                         'file': 'judges/judges',
                         'dir': 'judges/'
                     },
                     'preprocessed': {
                         'population': 'population/population_judges_preprocessed.csv',
                         'sample': 'sample/sample_judges_preprocessed.csv',
                         'standardise': 'standardise_logs_tests/standardise_logs_output_judges/',
                         'pids': 'pids_logs_tests/pids_logs_judges/'
                     },
                     'descriptives': {
                         'population': 'descriptives_judges/population/',
                         'sample': 'descriptives_judges/sample/'}
                     },

          'prosecutors': {'dispersed': 'magistrati/code_ready/prosecutors',
                          'collected': {
                              'file': 'prosecutors/prosecutors',
                              'dir': 'prosecutors/'
                          },
                          'preprocessed': {
                              'population': 'population/population_prosecutors_preprocessed.csv',
                              'sample': 'sample/sample_prosecutors_preprocessed.csv',
                              'standardise': 'standardise_logs_tests/standardise_logs_output_prosecutors/',
                              'pids': 'pids_logs_tests/pids_logs_prosecutors/'
                          },
                          'descriptives': {
                              'population': 'descriptives_prosecutors/population/',
                              'sample': 'descriptives_prosecutors/sample/'}
                          },

          'executori': {'dispersed': 'executori_judecatoresti/code_ready',
                        'collected': {
                            'file': 'executori/executori',
                            'dir': 'executori/'
                        },
                        'preprocessed': {
                            'population': 'population/population_executori_preprocessed.csv',
                            'sample': '',
                            'standardise': 'standardise_logs_tests/standardise_logs_output_executori/',
                            'pids': '/pids_logs_tests/pids_logs_executori/'
                        },
                        'descriptives': {
                            'population': 'descriptives_executori/population/',
                            'sample': ''}
                        },

          'notaries': {'dispersed': 'notari_publici/code_ready',
                       'collected': {
                           'file': 'notaries/notaries_persons',
                           'dir': 'notaries/'
                       },
                       'preprocessed': {
                           'population': 'population/population_notaries_preprocessed.csv',
                           'sample': '',
                           'standardise': '',
                           'pids': ''
                       },
                       'descriptives': {
                           'population': 'descriptives_notaries/population/',
                           'sample': ''}
                       },
          'combined': {'preprocessed': {'population': 'population/population_combined_professions.csv',
                                        'sample': ''},
                       'descriptives': {
                           'population': 'descriptives_combined/population/',
                           'sample': ''}
                       }
          }

if __name__ == '__main__':

    # the dictionary of professions, the years for which each has data, and the units for deaggregated analyses
    professions_details = {'judges': {'range': (1988, 2020),
                                      'units': ('ca cod', 'nivel')},
                           'prosecutors': {'range': (1988, 2019),
                                           'units': ('ca cod', 'nivel')},
                           'executori': {'range': (2001, 2019),
                                         'units': None},
                           'notaries': {'range': (1995, 2019),
                                        'units': None}
                           }

    # run the data pipeline for each professional separately: collection, preprocess, describe
    # write output at each steps, to check logs and so that early steps are saved if later ones error out

    for p, d in professions_details.items():

        # collect the data (which also does a first clean)
        in_dir = root + trunks['dispersed'] + leaves[p]['dispersed']
        out_path = root + trunks['collected'] + leaves[p]['collected']['file']
        make_table.make_pp_table(in_dir, out_path, p)

        # preprocess the data (add variables, standardise names, assign unique IDs, etc.)
        in_dir = root + trunks['collected'] + leaves[p]['collected']['dir']
        pop_out_path = root + trunks['preprocessed'] + leaves[p]['preprocessed']['population']
        sample_out_path = root + trunks['preprocessed'] + leaves[p]['preprocessed']['sample']
        std_log_path = root + trunks['preprocessed'] + leaves[p]['preprocessed']['standardise']
        pids_log_path = root + trunks['preprocessed'] + leaves[p]['preprocessed']['pids']
        preprocess.preprocess(in_dir, pop_out_path, sample_out_path, std_log_path, pids_log_path, p)

        # describe the data (make tables of descriptive statistics)
        pop_in_file = root + trunks['preprocessed'] + leaves[p]['preprocessed']['population']
        pop_out_dir = root + trunks['descriptives'] + leaves[p]['descriptives']['population']
        describe.describe(pop_in_file, pop_out_dir, p, d['range'][0], d['range'][1], d['units'])

        if p == 'judges' or p == 'prosecutors':
            sample_in_file = root + trunks['preprocessed'] + leaves[p]['preprocessed']['sample']
            sample_out_dir = root + trunks['descriptives'] + leaves[p]['descriptives']['sample']
            describe.describe(sample_in_file, sample_out_dir, p, d['range'][0], d['range'][1], d['units'])

    # now do inter-professional comparisons

    # first combine preprocessed data from diverse professions into one table;
    # we do this for the entire population, though can also be done for a sample
    in_dir = root + trunks['preprocessed'] + 'population'
    prep_out_path = root + trunks['preprocessed'] + leaves['combined']['preprocessed']['population']
    # make_table.combine_profession_tables(in_dir, prep_out_path)

    # then we look for transitions from one profession to the other, for a 3-year time window
    descr_out_dir = root + trunks['descriptives'] + leaves['combined']['descriptives']['population']
    describe.inter_professional_transition_table(prep_out_path, descr_out_dir, 1)
