"""
Functions below create or update an zipped/compressed data bases of monthly judge and prosecutor employment rolls by
using the websites of the Romanian Superior Council of the Magistracy (CSM). There are two websites, the old one (which
contains data from 2009 to part-2017) and the new one (with data from the rest of 2017 to the present). The new site
is constantly updated, so there are scripts for updating the DB on our end.

Author of Python Code:
    Pârvulescu, Radu Andrei (2020)
    rap348@cornell.edu
"""

import requests
import time
from bs4 import BeautifulSoup
import re
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import shutil
import json
from datetime import datetime


# FOR 2017-ONWARD DATA; SCRAPES NEW CSM SITE #

def update_db(zip_archive_root_path, scrape_log, profession):
    """

    :param zip_archive_root_path:
    :param scrape_log: str, path to where the log of scrapes lives
    :param profession:  string, "judges", "prosecutors", "notaries" or "executori".
    :return:
    """

    # open the zip archive to which we'll be appending files
    zip_arch_path = zip_archive_root_path + '/' + profession + '_2005_onward.zip'
    zip_archive = ZipFile(zip_arch_path, mode='a')

    # set header to pass to requests, so website I ping can see who I am
    header = {'User-Agent': 'Mozilla/5.0 (Linux Mint 18, 32-bit)'}

    # get the dict holding the download links
    data_links_dict = make_link_dict(header, profession)

    # update the DB

    # load the scrape log
    with open(scrape_log, 'r') as in_f:
        slog = json.load(in_f)

    # initialise a set of datetime objects, one for each year-month of each datafile we'll be downloading
    year_month_dates = set()
    # initialise a dict where we put urls from which we failed to get downloads
    download_fails = {}

    # go through all the year-months
    for year, months in data_links_dict.items():
        for mo, units in months.items():

            # if the year-month > max year-month from the scrape log, (i.e. that year-month hasn't been scraped)
            if datetime(int(year), int(mo), 1) > datetime.strptime(slog[profession]['max data date'], "%Y-%m-%d"):
                year_month_dates.add(datetime(int(year), int(mo), 1))

                # download the associated files and store them in the existing DB (which is a zip archive)
                for unit_name, file_link in units.items():
                    file_path = '/'.join([year, mo]) + '-'.join([year, mo, unit_name])
                    download_files_to_zip([file_link], header, zip_archive, download_fails, file_path=file_path)

    retry_failed_downloads(header, zip_archive, download_fails)

    # update the scrape log
    slog[profession]['scrape dates'].append(datetime.today().strftime("%Y-%m-%d"))
    slog[profession]['max data date'] = max(year_month_dates).strftime("%Y-%m-%d")
    with open(scrape_log, 'w') as out_f:
        json.dump(slog, out_f)


def make_link_dict(header, profession):
    """
    Go through the new CSM website and collect the links pointing to the datafiles that hold monthly employment rolls
    of judges and prosecutors. Store these links in a three-level dict organised as year: month : unit_name : link.

    :param header: dict, header for requests.get
    :param profession:  string, "judges", "prosecutors", "notaries" or "executori".
    :return: hierarchical dict, base value is download link
    """

    # the list below contains the link/url base for the profession-specific sites, and the link/url tails specific to
    # to each macro-unit (e.g. Court of Appeals, specialised agency) of said profession

    unit_urls = {'prosecutors': {'base': 'https://www.csm1909.ro/279/',
                                 'tails':
                                     ['3826/Parchetul-de-pe-langa-Inalta-Curte-de-Casatie-si-Justitie',
                                      '3825/Direcţia-de-Investigare-a-Infracţiunilor-de-Criminalitate-Organizată-şi-Terorism',
                                      '3824/Direcţia-Natională-Anticoruptie',
                                      '3823/Parchetul-Militar-de-pe-lângă-Curtea-Militară-de-Apel',
                                      '3822/Parchetul-de-pe-langa-Curtea-de-Apel-Alba-Iulia',
                                      '3821/Parchetul-de-pe-langa-Curtea-de-Apel-Bacau'
                                      '3820/Parchetul-de-pe-langa-Curtea-de-Apel-Brasov'
                                      '3819/Parchetul-de-pe-langa-Curtea-de-Apel-Bucuresti',
                                      '3818/Parchetul-de-pe-langa-Curtea-de-Apel-Cluj',
                                      '3817/Parchetul-de-pe-langa-Curtea-de-Apel-Constanta'
                                      '3816/Parchetul-de-pe-langa-Curtea-de-Apel-Craiova',
                                      '3815/Parchetul-de-pe-langa-Curtea-de-Apel-Galati'
                                      '3814/Parchetul-de-pe-langa-Curtea-de-Apel-Iasi',
                                      '3813/Parchetul-de-pe-langa-Curtea-de-Apel-Pitesti',
                                      '3812/Parchetul-de-pe-langa-Curtea-de-Apel-Ploiesti',
                                      '3811/Parchetul-de-pe-langa-Curtea-de-Apel-Oradea'
                                      '3810/Parchetul-de-pe-langa-Curtea-de-Apel-Suceava',
                                      '3809/Parchetul-de-pe-langa-Curtea-de-Apel-Timisoara',
                                      '3808/Parchetul-de-pe-langa-Curtea-de-Apel-Targu-Mures']},
                 'judges': {'base': 'https://www.csm1909.ro/276/',
                            'tails':
                                ['3790/Înalta-Curte-de-Casaţie-şi-Justiţie', '3789/Curtea-de-Apel-Alba-Iulia',
                                 '3788/Curtea-de-Apel-Bacau', '3787/Curtea-de-Apel-Brasov',
                                 '3786/Curtea-de-Apel-Bucuresti', '3785/Curtea-de-Apel-Cluj',
                                 '3784/Curtea-de-Apel-Constanta', '3783/Curtea-de-Apel-Craiova',
                                 '3782/Curtea-de-Apel-Galati', '3781/Curtea-de-Apel-Iasi',
                                 '3780/Curtea-de-Apel-Oradea', '3779/Curtea-de-Apel-Pitesti',
                                 '3778/Curtea-de-Apel-Ploiesti', '3777/Curtea-de-Apel-Suceava',
                                 '3776/Curtea-de-Apel-Targu-Mures', '3775/Curtea-de-Apel-Timisoara',
                                 '3774/Curtea-Militara-de-Apel']}
                 }

    month_names_ro = {"ianuarie": '01', "februarie": '02', "martie": '03', "aprilie": '04', "mai": '05', "iunie": '06',
                      "iulie": '07', "august": '08', "septembrie": '09', "octombrie": '10', "noiembrie": '11',
                      "decembrie": '12'}

    # initialie links dict
    data_files_links_dict = {}

    base_url = 'https://www.csm1909.ro'

    # each unit_url points to a page containing year-month files for a certain regional/specialised unit,
    # e.g. files for the Cluj Court of Appeals area, or for the Military Courts
    url_base = unit_urls[profession]['base']
    for url_tail in unit_urls[profession]['tails']:

        # new CSM site doesn't have a robots.txt page, I space it by a second for courtesy
        time.sleep(1)

        # each territorial unit (e.g. Cluj Court of Appeals) has its own page of links to employment data files
        # from different year-months
        unit_page = requests.get(url_base + url_tail, headers=header)
        unit_name = get_short_unit_name(url_tail[5:])

        soup = BeautifulSoup(unit_page.text, 'html.parser')

        # traverse the html tree to find the download links associated with that unit's year-month data files
        for file_links_bloc in soup.find_all('div', class_='list-group'):
            for mon_yr_bloc in file_links_bloc.find_all('a'):

                # get the download link for the file
                file_link = base_url + mon_yr_bloc.get('href')

                # find the month-year for that data-file
                # NB: regexp looks for year in text after month string, since format is always 'month_name year'
                mo_yr = [(mo, re.search(r'([1-2][0-9]{3})', mon_yr_bloc.text[mon_yr_bloc.text.index(mo):]).group(1))
                         for mo in month_names_ro if mo in mon_yr_bloc.text]
                year, month = int(mo_yr[0][1]), month_names_ro[mo_yr[0][0]]

                # update the dict of data file links; if no key for a certain year or month, make it
                if year in data_files_links_dict:
                    if month in data_files_links_dict[year]:
                        data_files_links_dict[year][month].update({unit_name: file_link})
                    else:
                        data_files_links_dict[year].update({month: {unit_name: file_link}})
                else:
                    data_files_links_dict.update({year: {month: {unit_name: file_link}}})

    return data_files_links_dict


def get_short_unit_name(name):
    """
    Given a url with the unit's name, return a shortened version of the name.
    :param name: string, e.g. '3808/Parchetul-de-pe-langa-Curtea-de-Apel-Targu-Mures'
    :return: cleaned string, e.g. "PCA Targu-Mures"
    """
    if "Parchetul" in name or "Direcţia" in name:
        if "Inalta" in name:
            return "PICCJ"
        elif "Criminalitate" in name:
            return "DIICOT"
        elif "Anticoruptie" in name:
            return "DNA"
        elif "Militar" in name:
            return "PCMA"
        else:
            return name.replace("Parchetul-de-pe-langa-Curtea-de-Apel-", "PCA ").replace('-', ' ')
    else:
        if "Înalta" in name:
            return "ICCJ"
        elif "Militara" in name:
            return "CMA"
        else:
            return name.replace("Curtea-de-Apel-", "CA ").replace('-', ' ')


# FOR 2009-2017 DATA; SCRAPES OLD CSM SITE #


def make_zip_archive(profession):
    """
    Find all downloadable doc(x) files on the old CSM site, download them then, and save them to a compressed
    directory on disk.

    :param profession:  string, "judges", "prosecutors", "notaries" or "executori".
    :return: None
    """

    # archive_path = where the archive lives
    # profession_site = profession-specific page where all the year-month links for that profession reside

    if profession == 'judges':
        profession_site = 'http://old.csm1909.ro/csm/index.php?cmd=080101&pg=1&arh=1'
        zip_archive_path = 'judges_2009_2017.zip'

    else:  # profession == 'prosecutors'
        profession_site = 'http://old.csm1909.ro/csm/index.php?cmd=080201&pg=1&arh=1'
        zip_archive_path = 'prosecutors_2009_2017.zip'

    # make header to pass to requests, tell site who I am
    header = {'User-Agent': 'Mozilla/5.0 (Linux Mint 18, 32-bit)'}

    # define key parameters, the absolute base of the url path and the marker we want to select download urls by
    url_base = 'http://old.csm1909.ro/csm/'
    download_url_marker = '.doc'

    # work in memory, speedier
    in_memory_file = BytesIO()
    zip_archive = ZipFile(in_memory_file, mode='w')

    # get the urls to files
    file_urls = get_file_urls(profession_site, header, url_base, download_url_marker)

    # download the urls; save downloads that fail
    download_fails = {}
    [download_files_to_zip(url, header, zip_archive, download_fails) for url in file_urls]
    retry_failed_downloads(header, zip_archive, download_fails)

    zip_archive.close()

    # write zip archive to disk
    in_memory_file.seek(0)
    with open(zip_archive_path, 'wb') as f:
        shutil.copyfileobj(in_memory_file, f)


def get_file_urls(url_of_urls, headers, url_base, download_url_marker):
    """
    Return a list of all urls leading to .doc(x) files.

    :param url_of_urls: urls of page containing download urls
    :param headers: dict, header for requests.get
    :param url_base: str, path to root for href url
    :param download_url_marker: str, regex marker for correct download url
    :return: list
    """
    file_urls = []
    page = requests.get(url_of_urls, headers=headers)
    soup = BeautifulSoup(page.text, features="lxml")
    for link in soup.find_all('a', attrs={'href': re.compile(download_url_marker)}):
        file_urls.append(url_base + link.get('href'))
    return file_urls


# COMMON FUNCTIONS #

def download_files_to_zip(url, headers, zip_archive, download_fails, file_path=None):
    """
    Download .doc(x) file and append it to an existing zip archive.

    :param url: str, url leading to files for downloading
    :param headers: dict, header for requests.get
    :param zip_archive: zip archive where file is deposited
    :param download_fails: dict, urls (as strings) from which we have not been able to download data
                            key is url, value is its associated file_path
    :param file_path: str, showing where in zip archive file should go; if none, assume we're scraping the old CSM site
    """
    # be courteous and leave a 1-second delay (old CSM site robots.txt explicitly asks for it)
    time.sleep(1)

    # try downloading the file
    try:
        file = requests.get(url, headers=headers)
        if not file_path:
            # store by year, month, largest territorial unit
            file_path = '/' + url[40:44] + '/' + url[37:39] + '/' + url[34:]
        zip_archive.writestr(file_path, file.content, compress_type=ZIP_DEFLATED)

        # if download successful, remove the url from the set of download misfires
        if url in download_fails:
            del download_fails[url]

    # if download unsuccessful, add url to set of download misfires
    except requests.exceptions.ConnectionError:
        download_fails.update({url: file_path})


def retry_failed_downloads(header, zip_archive, download_fails):
    """
    Given a dict of download fails, try to download each of them again, up to three times. If there are still
    urls that won't download after three tries, print out the recalcitrant urls plus their filepaths (which contain
    information on unit and date of data files).

    :param header: dict, header for requests.get
    :param zip_archive: zip archive where file is deposited
    :param download_fails: dict, keys are urls, values are file_paths (as used for inserting them in the zip archive)
    :return: None
    """
    for i in range(0, 3):
        [download_files_to_zip(url, header, zip_archive, download_fails, file_path=f_path)
         for url, f_path in download_fails.items()]

    if not download_fails:
        print('FAILED DOWNLOADS')
        [print(url, ' : ', f_path) for url, f_path in download_fails.items()]
