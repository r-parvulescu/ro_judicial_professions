"""
Takes employment records in different formats, converts them into a neat person-period (e.g. person-years)
table, and output this table as as csv.

NB: the base data files were EXTENSIVELY cleaned (by hand) to fix format, typo, etc. issues.
The functions in this module WILL NOT WORK with freshly scraped (dirty) output from scrape_csm_old.py, or from
the other data archives.
"""

import os
import csv
import itertools
import operator
import numpy as np
import pandas as pd
import re
import textract
import camelot
from collect import text_processors
from preprocess.workplace import workplace
from helpers import helpers


# TODO make it work from just memory so you don't have to unzip anything


def combine_profession_tables(preprocessed_dir, out_path):
    """
    Combine the tables from various legal professions into one large table.
    Updates row ID, unique person ID and adds a field marking the profession in which each person-year belongs.

    NB: assumes the profession tables have unique person IDs and row IDs; in practice, this means preprocessed tables

    NB: assumes that the name of the profession is in the file path.

    :param preprocessed_dir: string, path to directory where the preprocessed tables of the different professions live
    "param out_path: str, path where the combined table will live
    :return: None
    """

    # load the court codes dict, we'll need this later
    court_codes = workplace.get_unit_codes('judges')

    legal_professions = {'notaries', 'executori', 'judges', 'prosecutors'}

    # get all column names/variables that are NOT shared across professions
    flex_variables = ['trib cod', 'jud cod', 'nivel', 'instituţie', 'sediul, localitatea', 'stagiu', 'altele']

    # initialise the new, empty table
    combined_professions = []

    # initialise a person ID counter and a person-year counter
    pid = 0
    py_id = 0

    # get file paths
    file_paths = [preprocessed_dir + '/' + f.name for f in os.scandir(preprocessed_dir)
                  if f.is_file() and 'combined' not in f.name]

    for file in file_paths:

        # get the profession from the file name
        profession = [prof for prof in legal_professions if prof in file][0]

        # load the person-year table
        with open(file, 'r') as in_file:
            table = list(csv.reader(in_file))

            # split up the table into people based on person IDs
            header = helpers.get_header(profession, 'preprocess')
            pid_idx = header.index('cod persoană')
            # NB: start table at index 1 to skip header
            people = [person for key, [*person] in itertools.groupby(table[1:], key=operator.itemgetter(pid_idx))]

            for person in people:
                for person_year in person:

                    py_as_dict = helpers.row_to_dict(person_year, profession, 'preprocess')
                    appellate_code = workplace.get_appellate_code(profession, court_codes, py_as_dict)

                    new_py = {"cod rând": py_id, "cod persoană": pid, "profesie": profession,
                              "nume": py_as_dict['nume'], "prenume": py_as_dict['prenume'],
                              "sex": py_as_dict['sex'], "an": py_as_dict['an'], "ca cod": appellate_code}

                    # add remaining variables which vary by profession
                    # if a person-year doesn't have a certain variable (since wrong profession), put "-88"
                    for var in flex_variables:
                        new_py.update({var: py_as_dict[var]}) if var in py_as_dict else new_py.update({var: "-88"})

                    combined_professions.append(new_py)

                    py_id += 1  # increment row ID
                pid += 1  # increment person ID

    # write table to disk
    with open(out_path, 'w') as out_file:
        writer = csv.DictWriter(out_file, fieldnames=helpers.get_header('all', 'combine'))
        writer.writeheader()
        [writer.writerow(pers_yr) for pers_yr in combined_professions]

    # TODO figure out how to do row deduplication on this thing


def make_pp_table(in_dir, out_path, profession):
    """
    Go through employment rolls, extract person-period data, put it into a table, and save as csv.

    :param in_dir: directory where the base data files live
    :param out_path: path where we want the person-period table(s) to live
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return None
    """

    # initialise a dict of person-period tables, according to the time-grain of the table
    # (i.e. person-year vs person-month)
    ppts = {'year': ([], '_year.csv'), 'month': ([], '_month.csv')}
    directories = os.listdir(in_dir) if profession == 'judges' or profession == 'prosecutors' \
        else [in_dir]
    file_count = 0
    for d in directories:
        # if int(re.search(r'([1-2][0-9]{3})', d).group(1)) < 2005:  # to use only pre-2005 data
        dir_abs_path = in_dir + '/' + d
        for root, subdirs, files in os.walk(dir_abs_path):
            for file in files:
                if file_count < 3000:
                    file_count += 1
                    file_path = root + os.sep + file
                    print(file_count, '|', file_path)
                    people_periods_dict = triage(file_path, profession)
                    [ppts[k][0].extend(v) for k, v in people_periods_dict.items() if v]

    # write to csv
    head = helpers.get_header(profession, 'collect')
    for k, v in ppts.items():
        if v[0]:
            unique_row_table = helpers.deduplicate_list_of_lists(v[0])
            with open(out_path + v[1], 'w') as outfile:
                writer = csv.writer(outfile, delimiter=',')
                writer.writerow(head)
                for row in unique_row_table:
                    writer.writerow(row)


def triage(in_file_path, profession):
    """
    Invoke text extraction and processing tools depending on file type.

    .xlsx files come from a research assistant who has hand-cleaned all data, typically from historical
    archives (e.g. pictures of employment rolls from the 1980's).
    NB: .xlsx files may refer to ANY profession, and may contain data at BOTH the year AND the month level

    .pdf files contain employment rolls of prosecutors from 2017 (inclusive) onward; found at csm1909.ro
    NB: .pdf files refer ONLY to prosecutors, and contain ONLY month-level data

    .doc files contain employment rolls for magistrates 2005-2019; data from scrape_csm_old.py and freedom of
    information requests
    NB: .doc files refer ONLY to prosecutors and magistrates, and contain ONLY month-level data

    .csv files come from a research assistant who stitched together yearly tables of members from the the national
    professional associations of notaries and executori judecătoreşţi
    NB: .csv files refer ONLY to executori judecătoreşti and notaries;
        for executori we have person-year data for 2001 and 2003-2019
        for notaries we have person-level data (with entry and exit times, right censored) for 1995-2019

    :param in_file_path: string, path to the file holding employment information
    :param profession: string, "judges", "prosecutors", "notaries" or "executori".
    :return dict with key =  time-grains (i.e. year, month) and value = person-period table
    """
    pps = {'year': [], 'month': []}

    if in_file_path[-4:] == 'xlsx':
        people_periods_dict = get_xlsx_people_periods(in_file_path, profession)
        [pps[k].extend(v) for k, v in people_periods_dict.items() if v]

    if in_file_path[-3:] == 'csv':
        pps['year'].extend(get_csv_people_periods(in_file_path, profession))

    if in_file_path[-3:] == 'pdf':
        year, month = text_processors.get_year_month(in_file_path)
        if "PMCMA" not in in_file_path:  # military prosecutors, skip for now
            pps['month'].extend(get_pdf_people_periods(in_file_path, year, month))

    if in_file_path[-3:] == 'doc':
        year, month = text_processors.get_year_month(in_file_path)
        doc_people_periods = get_doc_people_periods(in_file_path, year, month, profession)
        if doc_people_periods:
            pps['month'].extend(doc_people_periods)

    return pps


def get_xlsx_people_periods(in_file_path, profession):
    """
    Extract all people people-periods (e.g. person-month) from employment rolls in .xlsx format,
    dumps them in tables (as lists of lists), and puts the tables in a dict
    :param in_file_path: string, path to the file holding employment information
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return dict with key =  time-grains (i.e. year, month) and value = person-period table
    """
    df = pd.read_excel(in_file_path)
    table = xlsx_df_cleaners(df).values.tolist()  # not all dfs have same shape, turn to list of lists

    person_years = []
    person_months = []
    for row in table:
        row = list(filter(None, row))
        # too much fidelity, even wrote in an unusual "former/other employee" value; just ignore these for now
        # TODO need to get back to this and figure out how to not throw out these data
        if 'ANGAJAŢI' not in row[2]:
            unit = None  # easy to trace problem

            surnames, given_names = '', ''
            if profession == 'judges':
                unit = text_processors.court_name_cleaner(row[2])
                surnames, given_names = text_processors.judge_name_clean(row[0], row[1])

            if profession == 'prosecutors':
                unit = text_processors.parquet_name_cleaner(row[2])
                surnames, given_names = text_processors.prosec_name_clean(row[0], row[1])

            # month data in the fifth column; if no month data, mark as missing
            if len(row) == 4:
                person_years.append([surnames, given_names, unit, str(row[3])])  # year = row[3]
            else:
                person_months.append([surnames, given_names, unit, str(row[3]), str(int(row[4]))])
        else:
            print(row)
    return {"year": person_years, "month": person_months}


def xlsx_df_cleaners(df):
    """
    Run a pandas df through a bunch of (mostly text) cleaners.
    :return a pandas df
    """
    df = df.drop(df.columns[0], axis=1)  # drop ID column
    df = df.applymap(lambda s: s.upper() if type(s) == str else s)  # everything uppercase
    df = df.applymap(lambda s: s.replace('Ț', 'Ţ') if type(s) == str else s)  # deal with non-standard
    df = df.applymap(lambda s: s.replace('Ș', 'Ş') if type(s) == str else s)  # diacritics
    df = df.applymap(lambda s: s.replace('-', ' ') if type(s) == str else s)  # remove hyphens
    df = df.replace(np.nan, '', regex=True)  # swap nan's for empty string
    return df


def get_csv_people_periods(in_file_path, profession):
    """
    Extract person-years from a csv-file, run data through cleaners, and return list of person-years.

    :param in_file_path: string, path to the file holding employment information
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return: a person-period table, as a list of lists
    """
    # initialise list of person-years
    person_years = []

    # read in the base data
    with open(in_file_path, 'r') as in_file:
        reader = csv.DictReader(in_file)

        # clean the rows we already have and dump the clean versions in a new table
        for row in reader:
            if profession == 'executori':
                clean_names = text_processors.executori_name_cleaner(row['nume'], row['prenume'],
                                                                     row['camera'], row['localitate'])

                # if there's no info for the workplace, stagiu, or altele, give them the '-88'
                work_place = row['sediu'].upper() if row['sediu'] else '-88'
                stagiu = row['stagiu'].upper() if row['stagiu'] else '-88'
                altele = row['altele'].upper() if row['altele'] else '-88'

                new_row = clean_names[:2] + [work_place, row['an']] + clean_names[2:] + [stagiu, altele]

            else:  # profession == 'notaries'

                # clean person and place names
                surnames, given_names = text_processors.str_cln(row['nume']), text_processors.str_cln(row['prenume'])
                chamber, town = text_processors.str_cln(row['camera']), text_processors.str_cln(row['localitatea'])

                # clean up given name and town names
                given_names = text_processors.notaries_given_name_correct(given_names)
                town = text_processors.notaries_town_correct(town)

                # strip the day and year info from time of entry, keep only year
                entry_year = row['intrat'].split('.')[-1]

                # if no exit year, mark with '-88'
                exit_year = row['ieşit'] if row['ieşit'] else '-88'

                new_row = [surnames, given_names, chamber, town, entry_year, exit_year]

            person_years.append(new_row)

    # return the cleaned person-years
    return person_years


def get_pdf_people_periods(in_file_path, year, month):
    # TODO 'post rezervat' (snuck in there, find it)
    """
    Extract all people people-periods (e.g. person-month) from employment rolls in .pdf format,
    dumps them in tables (as lists of lists)
    NB: this function ignores the internal hierarchy and/or territorial division of PICCJ, DIICOT and DNA
    :param in_file_path: string, path to the file holding employment information
    :param year: string of year, e.g. "1990"
    :param month: string of two-digit month, e.g. "04", or "12"
    :return person-period table, as list of lists
    """
    person_periods = []
    tables = camelot.read_pdf(in_file_path, pages='1-end')
    tables = camelot_parser(in_file_path, tables)

    special_parquet = text_processors.pdf_get_special_parquets(in_file_path)
    if tables:
        for t in tables:
            table_as_list = t.df.values.tolist()

            # sometimes the first row is the header
            if table_as_list[0][0].strip() == 'NUME PERSONAL PARCHETE' or table_as_list[0][-1] == 'P.J.':
                table_as_list = table_as_list[1:]

            for row in table_as_list:
                parquet = special_parquet if special_parquet else text_processors.pdf_get_parquet(row)
                parquet = text_processors.space_name_replacer(parquet, text_processors.parquet_sectors_buc_transdict)
                parquet = text_processors.space_name_replacer(parquet, text_processors.parquet_names_transict)

                # for now, avoid military parquets
                if parquet != 'SPM':

                    # avoid junk input, e.g. fullname = "A1" in 2017-09-PCA_Timisoara.pdf
                    # also "Post rezervat" in 2018-02-PCA_Cluj.pdf
                    if len(row[0]) > 3 or " rezervat" in row[0]:  # row[0] = fullname
                        surnames, given_names = text_processors.get_prosecutor_names(row[0])
                        # words that sneak in due to improper formatting
                        given_names = given_names.replace("execuţie", '').replace('conducere', '')
                        # some double maiden names are separated by a comma
                        surnames = surnames.replace(',', ' ')
                        surnames, given_names = text_processors.prosecs_problem_name_handler(surnames, given_names)
                        person_periods.append([surnames, given_names, parquet, year, month])
                    else:
                        print(row[0])
    else:
        return
    return person_periods


def camelot_parser(in_file_path, tables):
    """
    Try and get the most accurately parsed pdf table from camelot; if accuracy is problematic, skip and let us know.

    if lattice parsing accuracy < 90% try stream parsing
        if stream parsing accuracy > 90%, return stream-parsed tables
        else print file_path (to inspect that pdf) and return None (skip the inaccurate file)

    :param in_file_path: string, path to the file holding employment information
    :param tables: iterable of camelot tables
    :return tables if accuracy is acceptable, None otherwise
    """
    accuracies = [t.parsing_report['accuracy'] for t in tables]
    if min(accuracies) < 90:
        print("------------------------ USED STREAM ------------------------")
        tables = camelot.read_pdf(in_file_path, pages='1-end', flavor='stream')
        # if accuracy still low, print filepath so I can inspect the pdf
        if min([t.parsing_report['accuracy'] for t in tables]) < 90:
            print(in_file_path)
            return None
        return tables
    else:
        return tables


def get_doc_people_periods(in_file_path, year, month, profession):
    """
    Extract all people people-periods (e.g. person-month) from employment rolls in .doc format,
    dumps them in tables (as lists of lists)
    :param in_file_path: string, path to the file holding employment information
    :param year: string of year, e.g. "1990"
    :param month: string of two-digit month, e.g. "04", or "12"
    :param profession: string, "judges", "prosecutors", "notaries" or "executori"
    :return person-period table, as list of lists
    """
    prosecs = True if profession == 'prosecutors' else False
    # extract text, capitalise, and pre-clean
    text = text_processors.doc_pre_clean(textract.process(in_file_path).decode('utf-8').upper(), prosecs)
    if get_doc_military_data(text):
        return
    people_periods = []
    split_mark = 'PARCHETUL ' if prosecs else 'JUDECĂTORIA |JUDECATORIA |TRIBUNALUL |CURTEA DE APEL'
    # splits the text into chunks, each chunk is the employment roll for one unit, e.g. a court of parquet
    units = re.split(split_mark, text)
    for u in units:
        # turns the text lines (usually each line is an employee) into a list, basically a list of employees
        unit_lines = list(filter(None, u.splitlines()))
        if len(unit_lines) > 1:
            if prosecs:
                text_processors.update_prosec_people_periods(people_periods, unit_lines, split_mark, year, month)
            else:
                text_processors.update_judge_people_periods(people_periods, unit_lines, text, year, month)
    people_periods = text_processors.multiline_name_contractor(people_periods)
    if prosecs:
        people_periods = text_processors.prosec_multiline_name_catcher(people_periods)
    return people_periods


def get_doc_military_data(text):
    """
    As it stands, lets us know whether the file refers to military courts or parquets,
    :param text: text (parsed by textract) of the whole .doc file
    :return: bool, True if the file refers to military courts or parquets, False otherwise
    """
    # TODO write this function to actually get person-periods from military court/parquet employment rolls
    #  the military courts/parquets have their own, separate territorial structure, which takes work to untangle
    # detect if it's data from the miliitary courts/parquets
    military = (re.search(r'PARCHETELOR MILITARE|PARCHETELE MILITARE|PARCHETUL MILITAR', text)
                is not None) or (re.search(r'CURTEA MILITAR|TRIBUNALUL MILITAR', text) is not None)
    return military
