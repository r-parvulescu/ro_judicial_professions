import csv
import numpy as np
from scipy.ndimage.filters import uniform_filter1d
from matplotlib import pyplot as plt
import matplotlib.ticker as ticker
from describe import descriptives


def executori_describe(in_file_path, out_directory, start_year, end_year):
    """
    Generate basic descriptives for executori judecătoreşti / judicial debt collectors, and write them to disk.

    :param in_file_path: path to the base data file
    :param out_directory: directory where the descriptives files will live
    :param start_year: first year we're considering
    :param end_year: last year we're considering
    :return: None
    """

    with open(in_file_path, 'r') as infile:
        reader = csv.reader(infile)
        next(reader, None)  # skip headers
        table = list(reader)

    # get basic descriptives

    # figure 1, evolution of percent female

    # figure 1, probability of retirement and entry, by gender


# TODO fill out the skeleton


def describe(profession, source_data, start_year, end_year, prosecs=False):
    """make table and figures of descriptive statistics"""

    outfile = 'describer/output/' + profession + '/descriptives.csv'
    fig1 = 'describer/output/' + profession + '/fig1_retirement_entry'
    fig2 = 'describer/output/' + profession + '/fig2_mobility_up_across'
    fig3 = 'describer/output/' + profession + '/fig3_percent_female'
    fig4 = 'describer/output/' + profession + '/fig4_mobility_gender'
    with open(source_data, 'r') as infile:
        reader = csv.reader(infile)
        next(reader, None)  # skip headers
        table = list(reader)

    # spit out basic statistics
    make_descriptives_table(table, outfile, start_year, end_year, prosecs=prosecs)
    # make figure 1, on retirements and entries
    plot_retirement_entry(table, start_year, end_year, fig1)
    # make figure 2, on promotions
    plot_promotion_probs(table, start_year, end_year, fig2)
    # make figure 3, on gender percentages
    plot_female_percent(table, start_year, end_year, fig3)
    # make figure 4, mobility types by judicial level, by gender
    plot_gender_level_mobility(table, start_year, end_year, fig4)


# PUT ALL DESCRIPTIVES IN A TABLE #

def make_descriptives_table(table, outfile, start_yr, end_yr, prosecs=False):
    """dump descriptive statistics in a csv"""
    stats = [("TOTAL MAGISTRATES PER YEAR", descriptives.people_per_year(table, start_yr, end_yr)[1:]),
             ("PERCENT FEMALE PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'sex', 'f', ['an', 'nivel'],
                                                                                 'percent')),
             ("TOTAL MOBILITY PER YEAR", descriptives.total_mobility(table, start_yr, end_yr)),
             ("TOTAL ENTRIES PER YEAR", descriptives.entries(table, start_yr, end_yr, year_sum=True)),
             ("ENTRIES BY PER YEAR, PER LEVEL", descriptives.entries(table, start_yr, end_yr, year_sum=False)),
             ("TOTAL RETIREMENTS PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'out', ['an'], "count")),
             ("RETIREMENTS PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'mişcat', 'out', ['an', 'nivel'],
                                                                              "count")),
             ("PROBABILITY OF RETIREMENT PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'out', ['an'],
                                                                                 'percent')),
             ("PROBABILITY OF RETIREMENT PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'mişcat', 'out',
                                                                                            ['an', 'nivel'],
                                                                                            'percent')),
             ("TOTAL PROMOTIONS PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'up', ['an'], 'count')),
             ("TOTAL PROMOTIONS PER YEAR, PER LEVEL",
              descriptives.delta_attribute(table, 'mişcat', 'up', ['an', 'nivel'],
                                           "count")),
             ("PROBABILITY OF PROMOTION PER YEAR",
              descriptives.delta_attribute(table, 'mişcat', 'up', ['an'], 'percent')),
             ("PROBABILITY OF PROMOTION PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'mişcat', 'up',
                                                                                           ['an', 'nivel'], 'percent')),
             ("TOTAL DEMOTIONS PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'down', ['an'], "count")),
             ("TOTAL DEMOTIONS PER YEAR, PER LEVEL",
              descriptives.delta_attribute(table, 'mişcat', 'down', ['an', 'nivel'],
                                           'count')),
             ("PROBABILITY OF DEMOTION PER YEAR",
              descriptives.delta_attribute(table, 'mişcat', 'down', ['an'], 'percent')),
             ("PROBABILITY OF DEMOTION PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'mişcat', 'down',
                                                                                          ['an', 'nivel'], 'percent')),
             ("TOTAL LATERAL MOVES PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'across', ['an'], 'count')),
             ("TOTAL LATERAL MOVES PER YEAR, PER LEVEL", descriptives.delta_attribute(table, 'mişcat', 'across',
                                                                                      ['an', 'nivel'], 'count')),
             ("PROBABILITY OF LATERAL MOVES PER YEAR", descriptives.delta_attribute(table, 'mişcat', 'across', ['an'],
                                                                                    'percent')),
             ("PROBABILITY OF LATERAL MOVES PER YEAR, PER LEVEL",
              descriptives.delta_attribute(table, 'mişcat', 'across', ['an', 'nivel'], 'percent')),
             ["RETIREMENTS PER YEAR PER COURT OF APPEALS, TOP 5"],
             ["RETIREMENTS PER YEAR PER TRIBUNAL, TOP 5"],
             ["RETIREMENTS PER YEAR PER JUDECĂTORIE, TOP 5"],
             ("PER COHORT, 5 YEAR COMPLETED MOBILITY COUNTS", descriptives.mob_cohorts(table, 5, start_yr, end_yr)),
             ("PER COHORT, 5 YEAR COMPLETED MOBILITY PROBABILITIES",
              descriptives.mob_cohorts(table, 5, start_yr, end_yr, percent=True))]
    with open(outfile, 'w') as f:
        writer = csv.writer(f)
        for s in stats:
            writer.writerow([s[0]])
            if s[0][-1] == '5':
                if "APPEALS" in s[0]:
                    unit_list = ['PCA' + str(i) for i in range(1, 16)] + ['DIICOT', 'DNA'] if prosecs \
                        else ['CA' + str(i) for i in range(1, 16)]
                    mob = descriptives.mobility_per_year_per_unit(table, unit_list, start_yr, end_yr,
                                                                  '3', 'out', year_sum=False)
                elif "TRIBUNAL" in s[0]:
                    unit_list = ['PTB' + str(i) for i in range(1, 46)] if prosecs \
                        else ['TB' + str(i) for i in range(1, 47)]
                    mob = descriptives.mobility_per_year_per_unit(table, unit_list, start_yr, end_yr,
                                                                  '2', 'out', year_sum=False)
                elif "JUDECĂTORIE" in s[0]:
                    unit_list = ['PJ' + str(i) for i in range(1, 178)] if prosecs \
                        else ['J' + str(i) for i in range(1, 178)]
                    mob = descriptives.mobility_per_year_per_unit(table, unit_list, start_yr, end_yr,
                                                                  '1', 'out', year_sum=False)
                [writer.writerow([yr_unit[0], yr_unit[1][-5:]]) for yr_unit in mob]
            else:
                [writer.writerow(i) for i in s[1]]
            writer.writerow('\n')


# PLOTTERS #

def plot_retirement_entry(person_year_table, start_year, end_year, outfile):
    """
    two-panel plot, shared x-axis:
    top: retirement probabilities on left y-axis and number of entrants on right y-axis
    bottom: retirement probabilities by level of judicial hierarchy
    only graph observations between second and second-to-last, exclude for weird edges from interval censoring
    """

    ret_count = descriptives.delta_attribute(person_year_table, 'mişcat', 'out', ['an'], 'count')[1:-1]
    ent_count = [e[1] for e in descriptives.entries(person_year_table, start_year, end_year, year_sum=True)]
    ret_probs = descriptives.delta_attribute(person_year_table, 'mişcat', 'out', ['an', 'nivel'], 'percent')

    fig1 = plt.figure(figsize=(10, 5))
    x = np.linspace(start_year, end_year, len(range(start_year, end_year + 1)))[1:-1]

    # top panel, on retirements and entries
    ax_ret = fig1.add_subplot(211)
    ax_ret.plot(x, [i[1] for i in ret_count], 'b-', label='retirements')
    ax_ret.plot(x, ent_count, 'r--', label='entries')

    ax_ret.legend(loc='upper right', fancybox=True, fontsize='small')
    ax_ret.set_title('Yearly Number of Retirements and Entries, 2007-2017')
    ax_ret.set_ylabel('total number')
    ax_ret.tick_params(axis='y')
    yticks_ret = ax_ret.yaxis.get_major_ticks()
    yticks_ret[0].label1.set_visible(False)
    yticks_ret[-1].label1.set_visible(False)
    plt.setp(ax_ret.get_xticklabels(), visible=False)

    # bottom panel, on retirement probability by level
    ret_probs = [(yr, *lvl_prob) for yr, lvl_prob in ret_probs
                 if int(start_year + 1) <= int(yr) <= int(end_year - 1)]  # flatten tuple of tuples
    lvl1 = [i[1][1] * 100 for i in ret_probs]
    lvl2 = [i[2][1] * 100 for i in ret_probs]
    lvl3 = [i[3][1] * 100 for i in ret_probs]
    lvl4 = [i[4][1] * 100 for i in ret_probs]

    ax_multi = fig1.add_subplot(212, sharex=ax_ret)
    ax_multi.plot(x, lvl1, 'r--', label='Local Court')
    ax_multi.plot(x, lvl2, 'b-', label='County Tribunal')
    ax_multi.plot(x, lvl3, 'g:', label='Court of Appeals')
    ax_multi.plot(x, lvl4, 'k-.', label='High Court')

    xticks = ax_multi.xaxis.get_major_ticks()
    xticks[0].label1.set_visible(False)
    xticks[-1].label1.set_visible(False)
    yticks_multi = ax_multi.yaxis.get_major_ticks()
    yticks_multi[0].label1.set_visible(False)
    yticks_multi[-1].label1.set_visible(False)
    ax_multi.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))

    title = 'Yearly Retirement Probability by Judicial Level, ' + str(start_year) + '-' + str(end_year)
    ax_multi.set_title(title)
    ax_multi.set_xlabel('year')
    ax_multi.set_ylabel('retirement probability')
    ax_multi.legend(loc='upper right', fancybox=True, fontsize='small')
    plt.tight_layout()
    plt.savefig(outfile)


def plot_promotion_probs(person_year_table, start_year, end_year, outfile):
    """plot moving average of promotion probability, per level"""
    prom_probs = descriptives.delta_attribute(person_year_table, 'mişcat', 'up', ['an', 'nivel'], 'percent')
    probs = [(yr, *lvl_prob) for yr, lvl_prob in prom_probs
             if int(start_year) <= int(yr) <= int(end_year - 1)]  # flatten tuple of tuples
    # huge yearly variance, smooth with moving average of size 3, for edges just multiply edge value
    lvl1_avg = uniform_filter1d([p[1][1] * 100 for p in probs], size=3, mode='nearest')
    lvl2_avg = uniform_filter1d([p[2][1] * 100 for p in probs], size=3, mode='nearest')
    lvl3_avg = uniform_filter1d([p[3][1] * 100 for p in probs], size=3, mode='nearest')

    fig1 = plt.figure(figsize=(10, 4.6))
    ax = fig1.add_subplot(111)
    x = [i for i in range(start_year, end_year)]

    ax.plot(x, lvl1_avg, 'r--', label='Local Court')
    ax.plot(x, lvl2_avg, 'b-', label='County Tribunal')
    ax.plot(x, lvl3_avg, 'g:', label='Court of Appeals')

    ax.set_xticks([i for i in range(start_year + 1, end_year, 2)])
    yticks = ax.yaxis.get_major_ticks()
    yticks[0].label1.set_visible(False)
    yticks[-1].label1.set_visible(False)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))

    # put legend underneath x-axis
    box = ax.get_position()  # shrink axis height by 10% at bottom
    ax.set_position([box.x0, box.y0 + box.height * 0.1, box.width, box.height * 0.9])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), fancybox=True, ncol=3, fontsize='small')

    title = 'Promotion Probability by Judicial Level (Moving Average), ' + str(start_year) + '-' + str(end_year - 1)
    plt.title(title)
    plt.xlabel("year")
    plt.ylabel("promotion probability")
    plt.savefig(outfile)


def plot_female_percent(person_year_table, start_year, end_year, outfile):
    """line graphs percent female per year, per level"""
    percentages = descriptives.delta_attribute(person_year_table, 'sex', 'f', ['an', 'nivel'], 'percent')
    centages = [(yr, *lvl_cent) for yr, lvl_cent in percentages
                if int(start_year) <= int(yr) <= int(end_year)]  # flatten tuple of tuples

    lvl1 = [i[1][1] * 100 for i in centages]
    lvl2 = [i[2][1] * 100 for i in centages]
    lvl3 = [i[3][1] * 100 for i in centages]
    lvl4 = [i[4][1] * 100 for i in centages]

    fig1 = plt.figure(figsize=(10, 4.6))
    ax = fig1.add_subplot(111)
    x = np.linspace(start_year, end_year, len(range(start_year, end_year + 1)))

    ax.plot(x, lvl1, 'r--', label='Local Court')
    ax.plot(x, lvl2, 'b-', label='County Tribunal')
    ax.plot(x, lvl3, 'g:', label='Court of Appeals')
    ax.plot(x, lvl4, 'k-.', label='High Court')

    yticks = ax.yaxis.get_major_ticks()
    yticks[0].label1.set_visible(False)
    yticks[-1].label1.set_visible(False)
    ax.set_xticks([i for i in range(start_year + 1, end_year, 2)])
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))

    # put legend underneath x-axis
    box = ax.get_position()  # shrink axis height by 10% at bottom
    ax.set_position([box.x0, box.y0 + box.height * 0.1, box.width, box.height * 0.9])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), fancybox=True, ncol=4, fontsize='small')

    title = 'Percent Female by Judicial Level, ' + str(start_year) + '-' + str(end_year)
    plt.title(title)
    plt.xlabel("year")
    plt.ylabel("percent female")
    plt.savefig(outfile)


def plot_gender_level_mobility(person_year_table, start_year, end_year, outfile):
    """plot comparative mobility of men and and women, across years and levels"""
    fig, axs = plt.subplots(4, figsize=(15, 15), sharex=True)
    x = [i for i in range(start_year + 1, end_year)]
    lines = []
    labels = []
    colours = {'1': 'k', '2': 'r', '3': 'b', '4': 'y'}
    levels = {'1': 'local court', '2': 'county tribunal', '3': 'court of appeals', '4': 'high court'}
    mobs = ['out', 'up', 'down', 'across']
    for idx, m in enumerate(mobs):
        mob = descriptives.delta_attribute(person_year_table, 'mişcat', m,
                                           ['an', 'nivel', 'sex'], 'percent', output_series=True)
        men_mob = {'1': [], '2': [], '3': [], '4': []}
        fem_mob = {'1': [], '2': [], '3': [], '4': []}
        for yr in range(start_year + 1, end_year):
            for lvl in men_mob:
                men_mob[lvl].append(mob[str(yr), lvl, 'm'])
                fem_mob[lvl].append(mob[str(yr), lvl, 'f'])

        # not all types of mobility are applicable to all levels
        # no promotions and lateral transfers from High Court, no demotions from Local Court
        if m == 'up' or m == 'across':
            del men_mob['4']
            del fem_mob['4']
        if m == 'down':
            del men_mob['1']
            del fem_mob['1']

        for lvl in men_mob:
            axs[idx].plot(x, [i * 100 for i in men_mob[lvl]], color=colours[lvl], linestyle=':',
                          label='men, ' + levels[lvl])
            axs[idx].plot(x, [i * 100 for i in fem_mob[lvl]], color=colours[lvl], linestyle='-',
                          label='women, ' + levels[lvl])
        axs[idx].yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
        axs[idx].set_title(m.title() + ' Mobility', size='medium')
        if m == 'out':
            axLine, axLabel = axs[idx].get_legend_handles_labels()
            lines.extend(axLine)
            labels.extend(axLabel)
        if m == 'across':
            lgd = axs[idx].legend(lines, labels, fancybox=True, loc='upper center', ncol=4,
                                  bbox_to_anchor=(0.5, -1), fontsize='x-small')

    plt.xlabel('year')
    plt.ylabel('percent mobility')
    fig.suptitle('Mobility by Type, Across Gender and Judicial Level')
    fig.tight_layout()
    fig.subplots_adjust(top=0.9)
    fig.savefig(outfile, bbox_extra_artists=[lgd])  # , bbox_inches='tight')
