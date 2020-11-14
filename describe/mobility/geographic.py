# FUNCTIONS FOR MOBILITY BETWEEN GEOGRAPHIC UNITS #

import csv
import natsort
import itertools
from operator import itemgetter
from copy import deepcopy
from helpers import helpers
import networkx as nx
from networkx.algorithms.centrality import betweenness_centrality
import community as community_louvain


def inter_unit_mobility_table(person_year_table, out_dir, profession, unit_type):
    """
    Write to disk a table of subtables, where each subtable is a square matrix where rows are sending units and
    columns are receiving units -- diagonals are "did not move". The output should look something like this:

    YEAR 1
                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    2       0       1
        UNIT 2    6       10      0
        UNIT 3    3       4       4
        ...


    YEAR 2

                UNIT 1  UNIT 2  UNIT 3
        UNIT 1    0        3       5
        UNIT 2    10       5       3
        UNIT 3    2        5       1
        ...
    ...

    :param person_year_table: person year table as a list of lists
    :param out_dir: directory where the inter-unit mobility table(s) will live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table (e.g. "ca cod")
    :return: None
    """

    # get the mobility dict
    mobility_dict = inter_unit_mobility(person_year_table, profession, unit_type)

    # and write it to disk as a table of subtables
    table_out_path = out_dir + unit_type + '_interunit_mobility_tables.csv'
    with open(table_out_path, 'w') as out_p:
        writer = csv.writer(out_p)
        for year, sending_units in mobility_dict.items():
            units = natsort.natsorted(list(sending_units))
            writer.writerow([year])
            writer.writerow([''] + units)
            for u in units:
                writer.writerow([u] + [sending_units[u][units[i]] for i in range(0, len(units))])
            writer.writerow(['\n'])


def interunit_transfer_network(person_year_table, profession, unit_type, out_dir):
    """
    Get certain metrics for the interunit (e.g. inter-appellate area) transfer network, i.e. the network created
    by people changing workplaces each year. We want to write to disk a table with the following columns:
        col1 = year
        col2 = graph-level in-degree centralisation
        col3 = graph-level out-degree centralisation
        col4 = top betweennesss centrality node (and its cluster/community)
        col4 = second betweennesss top centrality (and its cluster/community)
        col5 = third betweennesss top centrality (and its cluster/community)
        col6 = fourth betweennesss top centrality (and its cluster/community)
        col7 = fifth betweennesss top centrality (and its cluster/community)

    Also output the directed graph in a format that I can later plug into gephi or nice designs.
    gephi tutorial: https://gephi.org/tutorials/gephi-tutorial-quick_start.pdf

    NB: networkx's finds the shortest path in directed, weighted graphs using Dijkstra's algorithm, which interprets
        higher edge weights as "larger" distances (using a road-network analogy), so your centrality scores on
        are going to be inverted if you use normal weight. Consequently, for betweenness centrality I use reciprocal
        values for weights, so that Dijkstra optimises properly.
        https://stackoverflow.com/questions/50497186/
        https://networkx.github.io/documentation/latest/_modules/networkx/algorithms/centrality/betweenness.html
        https://brilliant.org/wiki/dijkstras-short-path-finder/

    NB: commnunity detection is tricky on directed graphs, so instead I make the digraph undirected, with edge
        weights equalling out-degree plus in-degree weights. So we still have a flow network, albeit undirected
        I could also use the InfoMap API but messing around with it gave me only one partition

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table
    :param out_dir: directory where the inter-unit mobility table(s) will live
    :return:
    """

    # get a dictionary of mobility -- for dict format see function "inter_unit_mobility"
    mob_dict = inter_unit_mobility(person_year_table, profession, unit_type)

    # initiate the output table
    with open(out_dir + "interunit_transfer_network_metrics.csv", 'w') as out_f:
        writer = csv.writer(out_f)
        writer.writerow([profession])
        header = ["YEAR", "INDEG CENTRALISATION", "OUTDEG CENTRALISATION", "1CNTR (CLSTTR)", "2CNTR (CLSTR)",
                  "3CNTR (CLSTR)", "4CNTR (CLSTR)", "5CNTR (CLSTR)"]
        writer.writerow(header), writer.writerow(["\n"])

        # make one directed graph for each year
        for year in mob_dict:
            digraph = nx.DiGraph()
            for sender in mob_dict[year]:
                for receiver in mob_dict[year][sender]:
                    # ignore people who don't move, i.e. self-loops; don't put zero weights, messes up calculations
                    if sender != receiver and mob_dict[year][sender][receiver] != 0:
                        digraph.add_edge(sender, receiver, weight=mob_dict[year][sender][receiver])

            # reciprocate edge weights then get shortest-path betweenness centrality
            g_copy = deepcopy(digraph)
            for u, v, a in g_copy.edges(data=True):
                a["weight"] = 1. / float(a["weight"])
            between_centr = sorted(list(betweenness_centrality(g_copy, normalized=True, weight='weight').items()),
                                   key=itemgetter(1), reverse=True)

            # get in- and out-degree centralisation, to compare networks across professions
            in_degree_centralisation = degree_centralization(digraph, "in")
            out_degree_centralisation = degree_centralization(digraph, "out")

            # make undirected graph and set its edge weights to sum of directed edge weights in digraph
            g_undir = digraph.to_undirected()
            for u_undir, v_undir, a_undir in g_undir.edges(data=True):
                a_undir["weight"] = 0
                for u_dir, v_dir, a_dir in digraph.edges(data=True):
                    if u_dir in {u_undir, v_undir} and v_dir in {u_undir, v_undir}:
                        a_undir["weight"] += a_dir["weight"]

            # do community detection via Louvain modularity algorithm
            partition = community_louvain.best_partition(g_undir)

            # get the top-5 nodes in terms of betweeness centrality, if such exist
            if between_centr:  # avoids years in which we didn't observe inter-unit movement
                row = [year, in_degree_centralisation, out_degree_centralisation]
                for i in range(0, 5):  # sometimes you only get top 1,2,3,4 nodes -- add as many as you can
                    if i < len(between_centr):
                        row.append(between_centr[i][0] + ''.join([' ', '(', str(partition[between_centr[i][0]]), ')']))
                writer.writerow(row)

            # write the directed graph to a GraphML file for drawing in Gephi; I leave this list empty since I pick
            # which years to draw based on the problem and paper at hand
            years_to_graphml = []
            for yr in years_to_graphml:
                if str(year) == str(yr):
                    nx.write_graphml(digraph, out_dir + str(year) + ".graphml")


def inter_unit_mobility(person_year_table, profession, unit_type):
    """
    For each year make a dict of interunit mobility where first level keys years, second level keys are sending units,
    and third level keys are receiving units. The base values are counts of movement; diagonals are "did not move".
    The dict form is:

    {'year1':
        {'sending unit1': {receiving unit1: int, receiving unit2: int,...},
         'sending unit2': {receiving unit1: int, receiving unit2: int,...},
         ...
         },
     'year2':
        {'sending unit1': {receiving unit1: int, receiving unit2: int,...},
         'sending unit2': {receiving unit1: int, receiving unit2: int,...},
         ...
         },
     ...
    }

    :param person_year_table: a table of person-years, as a list of lists
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :param unit_type: string, type of the unit as it appears in header of person_year_table
    :return: a multi-level dict
    """

    pid_col_idx = helpers.get_header(profession, 'preprocess').index('cod persoană')
    year_col_idx = helpers.get_header(profession, 'preprocess').index('an')
    unit_col_idx = helpers.get_header(profession, 'preprocess').index(unit_type)

    # get start and end year of all observations
    person_year_table.sort(key=itemgetter(year_col_idx))
    start_year, end_year = int(person_year_table[0][year_col_idx]), int(person_year_table[-1][year_col_idx])

    # the sorted list of unique units
    units = sorted(list({person_year[unit_col_idx] for person_year in person_year_table}))

    # make the mobility dict, which later will become a mobility matrix
    # NB: ignore last year: since we observe mobility by comparing to next year, last year's mobility always zero
    mobility_dict = {}
    for year in range(start_year, end_year):
        # the first-level key is the row/sender, the second-level key is the column/receiver
        units_dict = {unit: {unit: 0 for unit in units} for unit in units}
        mobility_dict.update({year: units_dict})

    # break up table into people
    person_year_table.sort(key=itemgetter(pid_col_idx, year_col_idx))  # sort by person ID and year
    people = [person for key, [*person] in itertools.groupby(person_year_table, key=itemgetter(pid_col_idx))]

    # look at each person
    for person in people:
        # look through each of their person-years
        for idx, person_year in enumerate(person):
            # compare this year and next year's units ; ignore last year, since no movement by def'n in last year
            if idx < len(person) - 1 and person_year[year_col_idx] != str(end_year):
                sender = person_year[unit_col_idx]
                receiver = person[idx + 1][unit_col_idx]
                # the transition year is, by convention, the sender's year
                transition_year = int(person_year[year_col_idx])
                # if they're different, we have mobility
                if sender != receiver:
                    # increment the sender-receiver cell in the appropriate year
                    mobility_dict[transition_year][sender][receiver] += 1
                else:  # they didn't move, increment the diagonal
                    mobility_dict[transition_year][sender][sender] += 1
            else:  # last observation, movement is out, which we count in other places, so ignore
                pass

    return mobility_dict


def degree_centralization(directed_graph, degree_direction):
    """
    Get in- and out-degree centralisation. Cribbed from answer in https://stackoverflow.com/questions/35243795

    :param directed_graph: a networkx DiGraph object
    :param degree_direction: str, "in" for in-degree, "out" for out-degree
    :return centralisation score, rounded to our decimal points
    """
    n = directed_graph.order()

    if degree_direction == "in":
        node_degrees = directed_graph.in_degree(weight="weight")
    else:
        node_degrees = directed_graph.out_degree(weight="weight")
    degree_values = [i[1] for i in node_degrees]

    if degree_values:
        max_in = max(degree_values)
        centralization = float((n * max_in - sum(degree_values))) / float((n - 1) ** 2)
        return round(centralization, 4)
    else:
        return None
