"""
Functions for extracting data from the judge employment roll .doc files.
"""

import re
import string


# GENERIC HELPERS #

def get_year_month(filepath):
    """
    Get the year and month from the file path -- applicable to monthly employment rolls from 2017 onwards.
    :param filepath: string, path to the file
    :return tuple of (year, month)
    """
    year_month = re.search(r'/([0-9]{2}.+)/', filepath).group(1)
    year, month = year_month.split('/')[0], year_month.split('/')[1]
    return year, month


def doc_pre_clean(text, parquet):
    """standardise text from .doc file by transforming string variants to one version"""
    text = space_name_replacer(text, court_sectors_buc_transdict)  # Bucharest sectors, courts
    if parquet:
        text = space_name_replacer(text, parquet_sectors_buc_transdict)  # Bucharest sectors, parquets
    # # replace all "Î" in middle of word with "Â", remove digits, and problem characters
    text = re.sub(r'\BÎ+\B', r'Â', text)  # replace all "Î" in middle of word with "Â"
    text = text.translate(str.maketrans('', '', string.digits))
    text = text.translate(str.maketrans({'.': ' ', '–': ' ', '-': ' ', '/': ' ', "'": '', "Ț": "Ţ", "Ș": "Ş",
                                         "Ů": "Ţ", "ﾞ": "Ţ", "’": "Ţ", ";": "Ş", "Ř": "Ţ", "]": ' ', '[': ' ',
                                         '_': ' '}))
    return text


def str_cln(text):
    """
    Apply some common cleaners for personal and area names (e.g. towns)
    NB: NOT for workplace names, these must include punctuation since they're street addresses
    :param text: string
    :return: cleaned string
    """

    text = text.upper()
    # use Romanian contemporary orthographic convention: replace "Î" in the middle of words with "Â"
    text = re.sub(r'\BÎ+\B', r'Â', text)
    # use cedilla diacritics
    text = text.replace('Ț', 'Ţ').replace('Ș', 'Ş')
    # remove punctuation
    text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
    # return, removing outside spaces and collapsing whitespace to just one space
    return ' '.join(text.split()).strip()


def multiline_name_contractor(people_periods):
    """
    ignore dud lines, find multiline names and contract them to one line,
    return table of cleaned people_period
    """
    for idx, val in enumerate(people_periods):
        if (val[0] == '') and (val[1] != 'NR') and (val[1] != 'PROCURORULUI') and (val[1] != "ILFOV") \
                and (val[1] != "TERORISM"):
            people_periods[idx - 1][1] = people_periods[idx - 1][1] + ' ' + people_periods[idx][1]
    return [i for i in people_periods if i[0] != '']


def space_name_replacer(text, dictio):
    """
    replaces all instances of irregular name (dict key) with corresponding regular name (dict value)
    handles names with spaces in them, e.g. "Radu Andrei"
    """
    for key, value in dictio.items():
        if key in text:
            text = text.replace(key, value)
    return text


def no_space_name_replacer(text, dictio):
    """
    replaces all instances of irregular name (dict key) with corresponding regular name (dict value)
    handles names with no spaces, e.g. "Maria"
    """
    text_list = text.split()
    for t in text_list:
        if t in dictio:
            text = text.replace(t, dictio[t])
    return text


def key_to_value(text, dictio):
    """
    Replaces the key with its value
    NB: It's import that we match the whole string, otherwise we make mistakes like "CLUJ" --> "CLUJ CLUJ NAPOCA"

    :param text: a string
    :param dictio: a dictionary
    :return: the dictio value corresponding to "text
    """
    if text in dictio:
        text = dictio[text]
    return text


given_name_mistakes_transdict = {
    "AMCA": "ANCA", "AMDREEA": "ANDREEA", "ANGELAA": "ANGELA", "CODRŢA": "CODRUŢA",
    "CRIASTIANA": "CRISTIANA", "CRSITINA": "CRISTINA", "DANDU": "SANDU",
    "DÂNZIANA": "SÂNZIANA", "ELRNA": "ELENA", "GENONEVA": "GENOVEVA", "GEORGICA": "GEORGICĂ",
    "GHEORGEH": "GHEORGHE", "CIRNELIU": "CORNELIU", "IUNUŢ": "IONUŢ", "IYABELA": "ISABELA",
    "LUARA": "LAURA", "MANUEMA": "MANUELA", "MARINENA": "MARINELA", "MRCEA": "MIRCEA",
    "NICUŢOR": "NICUŞOR", "NILOLETA": "NICOLETA", "ORSALYA": "ORSOLYA", "OTILEA": "OTILIA",
    "OTILIEA": "OTILIA", "PRTRONELA": "PETRONELA", "ROYALIA": "ROZALIA", "BUZĂU": '',
    "VIRGINEI": "VIRGINEL", "C TIN": "CONSTANTIN", "D TRU": "DUMITRU", "CORIN A": "CORINA",
    "MIHAELAIULIANA": "MIHAELA IULIANA", "GHEORGHW": "GHEORGHE", "VAENTIN": "VALENTIN",
    "CĂTĂLI N": "CĂTĂLIN", "RONELA": "RONELLA", "ITILIA": "OTILIA", "ANC A": "ANCA",
    "INSPECTOR CSM": '', "R?ZVAN": "RĂZVAN", "LUMINI?A": "LUMINIŢA", "CONSTAN?A": "CONSTANŢA",
    "COASTACHE": "COSTACHE", "AIRELIANA": "AURELIANA", "ANABELA": "ANABELLA", "ANEE": "ANNE",
    "ATILLA": "ATTILA", "CAREN": "CARMEN", "DUMITRIELA": "DUMITRELA", "ELANA": "ELENA",
    "EUGEL": "EUGEN", "MARIETTA": "MARIETA", "SZENDA": "SZENDE", "ŞTEANIA": "ŞTEFANIA",
    "KREISER": "KREISZER", "POMPILU": "POMPILIU", "SERCIU": "SERGIU",
    "ROMEO PETER": "ROMEO PÉTER", "CU PENSIE": '', 'FLOREA CRISTINA': 'FLORÉA CRISTINA',
    "CU PLEACĂ ART": "", "SILIVIU": "SILVIU", "MARCECL": "MARCEL", "DANIELLA": "DANIELA",
    "MARIEANA": "MARIANA", "PANTELEMON": "PANTELIMON", "OLIMPIEA": "OLIMPIA",
    "VERGICICA": 'VERGINICA', "PARASCHIEVA": "PARASCHEVA", "NCOLAE": "NICOLAE", "TITIANA": "TATIANA",
    "EUJEN": "EUGEN", "VIORIVA": 'VIORICA', "EMANELA": "EMANUELA", "VASIICĂ": "VASILICĂ",
    "DUMMITRU": "DUMITRU", "EMANUEAL": "EMANUEL", "VASILII": 'VASILI', "RALUCAMARIANA": "RALUCA MARIANA",
    "DUMIRTU": "DUMITRU", "LOSIF": "IOSIF", "DURNITRU": "DUMITRU", "ISVAN": "ISTVAN", "LULIAN": "IULIAN",
    "GHEROGHE": "GHEORGHE", "IOSN": "IOAN", "CIRPIAN": "CIPRIAN", "LONEL": "IONEL",
    "BAGDAN": "BOGDAN", "GABRIELVALENTIN": "GABRIEL VALENTIN", "FLORINEI": "FLORINEL", "GRIELA": "GABRIELA",
    "LONUŢ": "IONUŢ", "GHEOGHE": "GHEORGHE", "CISTODOR": 'CRISTODOR', "CTIN": "CONSTANTIN", "LOAN": "IOAN",
    "ISABERLA": "ISABELA", "ULPIN": "ULPIU", "ALEANDRINA": "ALEXANDRINA", "CARMNEN": "CARMEN", "MIAHELA": "MIHAELA"
}

given_name_diacritics_transdict = {
    "ADELUTA": "ADELUŢA", "ANCUTA": "ANCUŢA", "ANISOARA": "ANIŞOARA", "ANUTA": "ANUŢA",
    "AURAS": "AURAŞ", "BRANDUSA": "BRÂNDUŞA", "BRANDUŞA": "BRÂNDUŞA", "BRINDUSA": "BRÂNDUŞA",
    "BRÎNDUŞA": "BRÂNDUŞA", "CALIN": "CĂLIN", "CATALIN": "CĂTĂLIN", "CLOPOTEL": "CLOPOŢEL",
    "CONSTANTA": "CONSTANŢA", "COSTICA": "COSTICĂ", "CRACIUN": "CRĂCIUN",
    "CRENGUTA": "CRENGUŢA", "DANTES": "DANTEŞ", "DANUT": "DĂNUŢ", "DANUŢ": "DĂNUŢ",
    "DOINITA": "DOINIŢA", "DRAGOS": "DRAGOŞ", "DĂNUT": "DĂNUŢ", "FANEL": "FĂNEL",
    "CAMPEANA": "CÂMPEANA", "CÎMPEANA": "CÂMPEANA", "FLORIŢA": "FLORIŢĂ",
    "GHEORGITA": "GHEORGIŢĂ", "ROXAN": "ROXANA",
    "GAROFITA": "GAROFIŢA", "GRATIELA": "GRAŢIELA", "HORATIU": "HORAŢIU", "ILENUTA": "ILENUŢA",
    "IONUT": "IONUŢ", "JOITA": "JOIŢA", "LACRAMIOARA": "LĂCRIMIOARA", "IONICA": "IONICĂ",
    "LACRAMOARA": "LĂCRIMIOARA", "LAURENTIU": "LAURENŢIU", "LAURENTIA": "LAURENŢIA",
    "LENUTA": "LENUŢA", "LETITIA": "LETIŢIA", "LICUTA": "LICUŢA", "LUCRETIA": "LUCREŢIA",
    "LUMINITA": "LUMINIŢA", "MIHAITA": "MIHĂIŢĂ", "MIHAIŢĂ": "MIHĂIŢĂ", "MIORITA": "MIORIŢA",
    "MITICA": "MITICĂ", "MIUTA": "MIUŢA", "MUSATA": "MUŞATA", "NELUTA": "NELUŢA",
    "NICOLITA": "NICOLIŢA", "NUTI": "NUŢI", "OPRICA": "OPRICĂ", "PATRITIU": "PATRIŢIU",
    "PAUNIŢA": "PĂUNIŢA", "PETRICA": "PETRICĂ", "PETRISOR": "PETRIŞOR", "PETRUS": "PETRUŞ",
    "PETRUTA": "PETRUŢA", "PUSA": "PUŞA", "RADITA": "RĂDIŢA", "SANDICA": "SĂNDICA",
    "SASA": "SAŞA", "SEVASTITA": "SEVASTIŢA", "SMĂRĂNDITA": "SMĂRĂNDIŢA",
    "SPERANTA": "SPERANŢA", "STEFAN": "ŞTEFAN", "STEFANIA": "ŞTEFANIA", "STELUTA": "STELUŢA",
    "STERICA": "STERICĂ", "SÎNZIANA": "SÂNZIANA", "TAMAS": "TAMAŞ", "TANCUTA": "TANCUŢA",
    "TANTA": "TANŢA", "VALERICA": "VALERICĂ", "VLADUT": "VLĂDUŢ", "ZOITA": "ZOIŢA",
    "CODRUTA": "CODRUŢA", "DUMITRITA": "DUMITRIŢA", "FLORENTA": "FLORENŢA",
    "MADALINA": "MĂDĂLINA", "MARIOARA": "MĂRIOARA", "BRADUTA": "BRĂDUŢA", "CHISCAN": "CHIŞCAN",
    "LAURENTA": "LAURENŢA", "MĂRINICĂ": "MARINICĂ", "PĂCURETU": "PĂCUREŢU", "PRESURA": "PRESURĂ",
    "RAZVAN": "RĂZVAN", "STANCESCU": "STĂNCESCU", "ENIKO": "ENIKŐ", "MANDICA": "MANDICĂ",
    "ANIŞOARĂ": "ANIŞOARA", "ILEANUŢA": "ILENUŢA", "ALIOSA": "ALIOŞA", "FRASINA": "FRĂSINA",
    "TANCUŢA": "TĂNCUŢA", "JANOS": "JÁNOS", "TAŢIANA": "TATIANA", "AŞLAN": 'ASLAN',
    "SADÎC": 'SADÂC', "JENO": "JENŐ", "JENÖ": "JENŐ", "GABOR": "GÁBOR", "MĂRIA": "MARIA"
}

# HELPERS FOR JUDGES #


def update_judge_people_periods(people_periods, unit_lines, text, year, month):
    """
    updates a list of people periods
    :param people_periods: a list of people period
    :param unit_lines: a list of lines associated with a certain unit, e.g. a court
                       typically the first lines contain the name of the unit (e.g. Court X) and
                       subsequent lines contain the names of employees, usually one employee per line
    :param text: the full text from the .doc file
    :param year: the year of the employment roll
    :param month: the month of the employment roll
    """
    court_name = get_court_name(unit_lines)
    names = get_judges_names(unit_lines, text)
    if names is not None:
        for n in names:
            people_periods.append([n[0], n[1], court_name, year, month])


def get_judges_names(unit_lines, text):
    """
    return the names of judges
    :param unit_lines: a list of lines associated with a certain unit, e.g. a court
    :param text: the full text from the .doc file
    """
    names = []
    names_start_idx = judges_find_name_start(unit_lines)
    if names_start_idx is not None:
        unit_lines = unit_lines[names_start_idx:]
        if '\xa0' in text:  # mark of three-column file
            judges_three_col_name_getter(unit_lines, names)
        else:  # two-column file
            judges_two_col_name_getter(unit_lines, names)
        for name in names:
            name[0], name[1] = judge_name_clean(name[0], name[1])
        return names


def judges_two_col_name_getter(list_of_lines, names):
    """
    some of the .doc files come in two (2) columns
    this function returns judge names from such two-column files
    """
    for idx, val in enumerate(list_of_lines):
        if bool(re.match('^(?=.*[a-zA-Z])', val)):
            name_line = val.split('|')
            name_line = [l for l in name_line if bool(re.match('^(?=.*[a-zA-Z])', l))]
            if len(name_line) < 2:  # name spilled over onto next line, put it to last name and skip
                if name_line[0] == 'CRT' or len(name_line[0]) < 2:
                    continue
                names[idx - 1][1] = names[idx - 1][1] + ' ' + name_line[0]
                continue
            name_line = [' '.join(n.split()).strip() for n in name_line]
            names.append(name_line)


def judges_three_col_name_getter(list_of_lines, names):
    """
    some of the .doc files come in three (3) columns
    this function returns judge names from such three-column files
    """
    for l in list_of_lines:
        name_line = list(filter(None, l.split('|')))
        name_line = list(filter(None, [n.strip() for n in name_line]))
        name_line = [' '.join(n.split()).strip() for n in name_line]
        name_line = name_line[:2] if len(name_line) > 2 else name_line
        if len(name_line) > 1:
            names.append(name_line)


def judge_name_clean(surnames, given_names):
    """return surnames and given names that have been run through cleaners"""
    # follow current orthographic rules and replace all "Î" in middle of word with "Â
    given_names = re.sub(r'\BÎ+\B', r'Â', given_names)
    surnames = re.sub(r'\BÎ+\B', r'Â', surnames)
    surnames, given_names = judge_maiden_name_corrector(surnames, given_names)
    surnames = no_space_name_replacer(surnames, judges_surname_transdict).replace('.', '')
    given_names = space_name_replacer(given_names, given_name_mistakes_transdict)
    given_names = no_space_name_replacer(given_names, given_name_diacritics_transdict).replace('.', '')
    return judges_problem_person_name_handler(surnames, given_names)


def judge_maiden_name_corrector(surnames, given_names):
    """if a maiden name is in a given name, moves it to the end of the surname"""
    maiden_name = ''
    # names in brackets are maiden names
    if re.search(r'\((.*?)\)', given_names):
        maiden_name = re.search(r'\((.*?)\)', given_names).group(0)  # isolate maiden name
        given_names = given_names.replace(maiden_name, '').strip()  # take maiden name out of fullname
        maiden_name = ' ' + maiden_name.replace(' ', '')  # clean up the maiden name
    # put maiden name after surname, isolate given names, eliminating hyphens
    surnames = surnames + maiden_name
    return surnames, given_names


def judges_find_name_start(list_of_lines):
    """return the index at which the person names begin"""
    if bool(re.match('^(?=.*[a-zA-Z])', ''.join(list_of_lines))):  # ignore empties
        try:  # names proper usually  start after "CRT"
            names_start_idx = (next((idx for idx, val in enumerate(list_of_lines) if "CRT" in val))) + 1
        except StopIteration:  # or after first entry, which is name of court
            names_start_idx = (next((idx for idx, val in enumerate(list_of_lines)
                                     if bool(re.match('^(?=.*[a-zA-Z])', val))))) + 1
        return names_start_idx


def judges_problem_person_name_handler(surnames, given_names):
    """
    some names mess things up and slip through every other filter
    this function catches them and return the proper variant
    """
    if "AND ONE" in surnames:
        surnames = "ANDONE"
    if "FOSTĂ" in surnames:
        surnames = surnames.replace("( FOSTĂ ", '(')
        surnames = surnames.replace("(FOSTĂ ", '(')
    if 'FOSTA' in surnames:
        surnames = surnames.replace('( FOSTA ', '(')
    return surnames.strip(), given_names.strip()


judges_surname_transdict = {
    "ACIOBANITEI": "ACIOBĂNIŢEI", "AFRASINIE": "AFRĂSINIE", "AILENA": "AILENE",
    "AIONITOAIE": "AIONIŢOAIE", "ANCUTA": "ANCUŢA", "ANUTI": "ANUŢI", "ARBANAS": "ARBĂNAŞ",
    "ASTALAŞ": "ASTĂLAŞ", "AVASILCĂI": "AVASILICĂI", "AXÎNTI": "AXINTI",
    "BADESCU": "BĂDESCU", "BADICEANU": "BĂDICEANU", "BADULESCU": "BĂDULESCU",
    "BENEGIU": "BENEGUI", "BLEOANCĂ": "BLEOANCĂ", "BLANARIU": "BLĂNARIU", "BOBOS": "BOBOŞ",
    "BOCHIS": "BOCHIŞ", "BOLOS": "BOLOŞ", "BONTAS": "BONTAŞ", "BRATIS": "BRATIŞ",
    "BREZAE": "BREZAIE", "BRESUG": "BREŞUG", "BRÎNZICĂ": "BRĂNZICĂ", "BUTUCA": "BUTUCĂ",
    "BUZA": "BUZĂ", "BÎRSESCU": "BÂRSESCU", "BÎRŞĂŞTEANU": "BÎRSĂŞTEANU", "BĂISAN": "BĂIŞAN",
    "CAMPEAN": "CÂMPEAN", "CAPOTA": "CAPOTĂ", "CEAUSESCU": "CEAUŞESCU", "CETERAS": "CETERAŞ",
    "CEUCA": "CEUCĂ", "CHIDOVĂŢ": "CHIDOVEŢ", "CHIRILA": "CHIRILĂ", "CIOARA": "CIOARĂ",
    "CIRCIUMARU": "CÂRCIUMARU", "CIRSTESCU": "CÂRSTESCU", "CIRSTOCEA": "CÂRSTOCEA",
    "COARNA": "COARNĂ", "CODINA": "CODINĂ", "COJOCARIU": "COJOCARU", "CORAS": "CORAŞ",
    "CORUGA": "CORUGĂ", "COSTASI": "COSTAŞI", "CRISAN": "CRIŞAN", "DANAILA": "DĂNĂILĂ",
    "DANILA": "DĂNILĂ", "DANILEŢ": "DĂNILEŢ", "DARABAN": "DĂRĂBAN", "DRAGOS": "DRAGOŞ",
    "DUDAS": "DUDAŞ", "DUMINECA": "DUMINECĂ", "DURBACA": "DURBACĂ", "DUSA": "DUŞA",
    "DUTA": "DUŢĂ", "DUTĂ": "DUŢĂ", "FAZAKAŞ": "FAZAKAS", "FALAMAS": "FĂLĂMAS",
    "FĂNUTA": "FĂNUŢĂ", "FARCAS": "FARCAŞ", "FRAŢILESCU": "FRĂŢILESCU",
    "FUNDATUREANU": "FUNDĂTUREANU", "GAINA": "GĂINĂ", "GAISTEANU": "GĂIŞTEANU",
    "GALAŢANU": "GĂLĂŢANU", "GÂRLECI": "GÂRLICI", "GHERCA": "GHERCĂ", "GHILA": "GHILĂ",
    "GRADINARIU": "GRĂDINARIU", "GRADINARU": "GRĂDINARU", "GRIGORASCU": "GRIGORAŞCU",
    "GROAPA": "GROAPĂ", "GUTU": "GUŢU", "HANCAŞ": "HANCĂŞ", "HARTMAN": "HARTMANN",
    "HOLBOCEANU": "HOLBOCIANU", "IONITA": "IONIŢĂ", "ISAILĂ": "ISĂILĂ",
    "ISTRATESCU": "ISTRĂTESCU", "IUJĂ": "IUJA", "LACUSTEANU": "LĂCUSTEANU",
    "LASCONI": "LĂSCONI", "LINTA": "LINŢA", "LITA": "LIŢĂ", "LIXANDROIU": "LIXĂNDROIU",
    "LUCACEL": "LUCĂCEL", "LUCGHIAN": "LUCHIAN", "LUCHOAN": "LUCHIAN", "MADUTA": "MĂDUŢĂ",
    "MANASTIREANU": "MĂNĂSTIREANU", "MARIS": "MARIŞ", "MAIEREANU": "MĂIEREANU",
    "MĂSTACAN": "MĂSTĂCAN", "MÂNGAŢĂ": "MÂNGÂŢĂ", "MERISESCU": "MERIŞESCU",
    "MEROBIAN": "MESROBIAN", "MESTER": "MEŞTER", "MIHAIANU": "MIHĂIANU", "MINCA": "MINCĂ",
    "MOISA": "MOISĂ", "MONCIA": "MONCEA", "MOTAN": "MOŢAN", "MPSTPCAN": "MĂSTĂCAN",
    "MUSAT": "MUŞAT", "MUŞINOU": "MUŞINOI", "NASTASE": "NĂSTASE", "NASTASIE": "NĂSTASIE",
    "NĂSTĂSIE": "NĂSTASIE", "NEGOIŢA": "NEGOIŢĂ", "NEGRILA": "NEGRILĂ", "NEMES": "NEMEŞ",
    "NEMTEANU": "NEMŢEANU", "NENITA": "NENIŢĂ", "NIŢUQÂ": "NIŢU", "NOSLACAN": "NOŞLĂCAN",
    "OANNCEA": "OANCEA", "OBOROCEANU": "OBOROCIANU", "OPRIS": "OPRIŞ", "ORASEANU": "ORĂŞEANU",
    "ORASTEANU": "ORĂŞTEANU", "OROSAN": "OROŞAN", "PADURARIU": "PĂDURARIU",
    "PALINCAS": "PALINCAŞ", "PASARE": "PASĂRE", "PASCA": "PAŞCA", "PASTORICI": "PASTORCICI",
    "PATRAS": "PĂTRAŞ", "PATRAŞ": "PĂTRAŞ", "PATRAUS": "PĂTRĂUŞ", "PÂRLETEANU": "PÂRLEŢEANU",
    "PĂRVULESCU": "PÂRVULESCU", "PETRASCU": "PETRAŞCU", "PETRISOR": "PETRIŞOR",
    "PINTILEI": "PINTILIE", "PIRJOL": "PÂRJOL", "PIRVU": "PÂRVU", "PIRVULESCU": "PÂRVULESCU",
    "PISLARU": "PÂSLARU", "PLACINTA": "PLĂCINTĂ", "PLACINTĂ": "PLĂCINTĂ", "POIANA": "POIANĂ",
    "POLITEANU": "POLIŢEANU", "POMANA": "POMANĂ", "PREOEASA": "PREOTEASA",
    "PREPELIŢA": "PREPELIŢĂ", "PRICINA": "PRICINĂ", "PUSCASIU": "PUŞCASIU",
    "RAMASCANU": "RAMAŞCANU", "REGHINA": "REGHINĂ", "RETEZATU": "RETEZANU",
    "RISNOVEANU": "RÂSNOVEANU", "ROMILA": "ROMILĂ", "ROS": "ROŞ", "ROSIORU": "ROŞIORU",
    "ROSU": "ROŞU", "RUSAN": "RUŞAN", "SALAJAN": "SĂLĂJAN", "SALAPA": "ŞALAPA",
    "SANDULESCU": "SĂNDULESCU", "SARB": "SÂRB", "SEBESAN": "SEBEŞAN", "SECARA": "SECARĂ",
    "SECRETEANU": "SECREŢEANU", "SEGARCEANU": "SEGĂRCEANU", "SERBAN": "ŞERBAN",
    "SERBANESCU": "ŞERBĂNESCU", "SIPOTEANU": "ŞIPOTEANU", "SIRBU": "SÂRBU",
    "SMÂNTÂNA": "SMÂNTÂNĂ", "SPÂNACHE": "SPÂNOCHE", "SPRINCEANA": "SPRÂNCEANA",
    "STANESCU": "STĂNESCU", "STANISOR": "STANIŞOR", "STĂNILA": "STĂNILĂ",
    "SZIKSAY": "SZIKSZAY", "TANDARESCU": "ŢĂNDĂRESCU", "TANTĂU": "TANŢĂU",
    "TĂMĂZLACARU": "TĂMĂZLĂCARU", "TÂLVAR": "TÂLVĂR", "TEAHA": "TEANA", "TIMISAN": "TIMIŞAN",
    "TIŢA": "TIŢĂ", "TRAISTARU": "TRĂISTARU", "TRANCA": "TRANCĂ", "TRUTESCU": "TRUŢESCU",
    "TUCA": "TUCĂ", "TULICA": "TULICĂ", "VACARUS": "VĂCĂRUŞ", "VADUVA": "VĂDUVA",
    "VALEANU": "VĂLEANU", "VALVOI": "VÂLVOI", "VÂRGĂ": "VARGA", "VARTOPEANU": "VÂRTOPEANU",
    "VATAVU": "VĂTAVU", "VATRA": "VATRĂ", "VÂNŞU": "VÂNŢU", "VEGHES": "VEGHEŞ",
    "VERDES": "VERDEŞ", "VIJLOI": "VÂJLOI", "VILCU": "VÂLCU", "VILCELEANU": "VÂLCELEANU",
    "VISAN": "VIŞAN", "ZBARCEA": "ZBÂRCEA", "ZGLIMBRA": "ZGLIMBEA", "AGAFITEI": "AGAFIŢEI",
    "AILENE": "AILENEI", "AIONESE": "AIONESEI", "ALECXANDRU": "ALEXANDRU", "APETREI": "APETRI",
    "ATUDOSIEI": "ATUDOSEI", "AXINTI": "AXÂNTI", "BADILĂ": "BĂDILĂ", "BADOI": "BĂDOI",
    "BALAŞCA": "BALAŞCĂ", "BARAN": "BĂRAN", "BIRAU": "BIRĂU", "BLEOANCA": "BLEOANCĂ",
    "BOROS": "BOROŞ", "BROASCA": "BROASCĂ", "BRUMA": "BRUMĂ", "BRĂNZICĂ": "BRÂNZICĂ",
    "BURLIBASA": "BURLIBAŞA", "BANYAI": "BÁNYAI", "BIGIOI": "BÂGIOI", "BÂGOI": "BÂGIOI",
    "BÂLBA": "BÂLBĂ", "BÂRSAŞTEANU": "BÂRSĂŞTEANU", "BÂRŞĂŞTEANU": "BÂRSĂŞTEANU",
    "BĂDIŢA": "BĂDIŢĂ", "BALAN": "BĂLAN", "BARBULESCU": "BĂRBULESCU", "CALANCE": "CALANCEA",
    "CALOTA": "CALOTĂ", "CAMENIŢA": "CAMENIŢĂ", "CATUNA": "CĂTUNA", "CHIRVASA": "CHIRVASĂ",
    "CHIRVASE": "CHIRVASĂ", "CHIS": "CHIŞ", "CIORCAS": "CIORCAŞ", "CIOVIRNACHE": 'CIOVÂRNACHE',
    "COVÂRNACHE": "CIOVÂRNACHE", "CIRLIG": "CÂRLIG", "CIRSTOIU": "CÂRSTOIU",
    "COBISCAN": "COBÂSCAN", "COMÂSCAN": "COBÂSCAN", "COMSA": "COMŞA", "CORLĂŢENU": "CORLĂŢEANU",
    "COTUTIU": "COTUŢIU", "CREMENITCHI": "CREMENIŢCHI", "CRETOIU": "CREŢOIU",
    "CREŢANU": "CREŢEANU", "CRÂSMARU": "CRÂŞMARU", "CRPCIUN": "CRĂCIUN", "CARSTEA": "CÂRSTEA",
    "CALIN": "CĂLIN", "CĂRSTESCU": "CÂRSTESCU", "DASCALU": "DASCĂLU", "DEACONU": "DIACONU",
    "DOMNITEANU": "DOMNIŢEANU", "DOROBANTU": "DOROBANŢU", "DOTIU": "DOŢIU", "DRAGAN": 'DRĂGAN',
    "DRAGHICI": "DRĂGHICI", "DUMITRASCU": 'DUMITRAŞCU', "DUSCCEAC": "DUSCEAC",
    "DUTESCU": "DUŢESCU", "EROS": "ERÖS", "FARTATHY": 'FARMATHY', "FAT": "FĂT", "FIT": "FIŢ",
    "FLORUT": "FLORUŢ", "FĂLĂMAS": "FĂLĂMAŞ", "GADICI": "GÂDICI", "GALESCU": "GĂLESCU",
    "GARBACI": "GÂRBACI", "GASPAR": "GAŞPAR", "GAVRILA": "GAVRILĂ", "GIORGESCU": "GEORGESCU",
    "GHEALDIR": "GHEALDÂR", "GRECUP": "GRECU", "GROZAVESCU": "GROZĂVESCU",
    "VLADISLAU": 'VLADISLAV', "GURITĂMANOLE": "GURITĂ MANOLE", "GYORGY": "GYÖRGY",
    "GĂLĂTAN": "GĂLĂŢAN", "GĂRCU": "GÂRCU", "HANCĂS": "HANCĂŞ", "HANCAS": "HANCĂŞ",
    "HARALAMBE": "HARALAMBIE", "HATEGAN": "HAŢEGAN", "HEGYI": "HEGY", "HURDUCACI": "HURDUGACI",
    "HELRGHELEGIU": "HERGHELEGIU", "HOALGA": "HOALGĂ", "HRITCU": "HRIŢCU", "HĂRĂBOR": "HĂRĂBOI",
    "ILUT": "ILUŢ", "ILYES": "ILYÉS", "IORANESCU": "IORDANESCU", "IVANUŞCĂ": "IVĂNUŞCĂ",
    "IVĂHIŞI": "IVĂNIŞI", "IVANIŞ": "IVĂNIŞ", "IVĂNUŞCA": 'IVĂNUŞCĂ', "JIRLĂEANU": "JÂRLĂEANU",
    "KARDALUS": "KARDALUŞ", "KAZĂR": "LAZĂR", "KULCEAR": "KULCSAR", "LERESZTES": 'KERESZTES',
    "LODOABA": "LODOABĂ", "LUSUŞAN": "LUDUŞAN", "MAGYORI": 'MAGYARI', "MAIREAN": "MAIEREAN",
    "MANCAS": "MANCAŞ", "MANDROC": "MÂNDROC", "MANIGUŢIU": 'MĂNIGUŢIU', "MARGINA": "MARGINĂ",
    "MEUCĂ": 'MEAUCĂ', "MIHALACGE": "MIHALACHE", "MIHAIESCU": 'MIHĂIESCU',
    "MINDRUTIU": "MINDRUŢIU", "MITRANCA": 'MITRANCĂ', "MODILCĂ": 'MODÂLCĂ', "MOIS": "MOIŞ",
    "MORMĂILĂ": "MORNĂILĂ", "MOROSANU": "MOROŞANU", "MOT": "MOŢ", "MOTIRLICHIE": "MOŢÂRLICHIE",
    "MOTÂRLICHIE": "MOŢÂRLICHIE", "MOTĂŢEANU": "MOŢĂŢEANU", "MURESAN": "MUREŞAN",
    "MAIEREAN": "MĂIEREAN", "NEACSU": "NEACŞU", "MAE": "NAE", "NISULESCU": "NIŞULESCU",
    "NITOI": "NIŢOI", "NITULESCU": "NIŢULESCU", "NOVACESCU": "NOVĂCESCU", "OPRIŢA": "OPRIŢĂ",
    "OSICECANU": "OSICEANU", "PANTELEEV": "PENTELEEV", "PANŢIRU": "PANŢÂRU",
    "PARFENE": "PARFENIE", "PASTILA": 'PASTILĂ', "PAUN": 'PĂUN', "PESCĂRUS": "PESCĂRUŞ",
    "PISMIS": "PISMIŞ", "POTANG": "POTÂNG", "PRICIN": "PRICINĂ", "PURCARIŢĂ": "PURCĂRIŢĂ",
    "PUŞCA": "PUŞCĂ", "PUŞCASIU": "PUŞCAŞIU", "PUSCHIN": "PUŞCHIN", "PUTURA": "PUŢURA",
    "PALTINEANU": "PĂLTINEANU", "PĂSCULEŢ": "PĂŞCULEŢ", "PUŞOU": "PUŞOIU", "RACEANU": "RĂCEANU",
    "RADOCĂ": "RĂDOCĂ", "RAT": "RAŢ", "RUSTI": "RUŞTI", "RADULESCU": "RĂDULESCU",
    "SABAU": "SABĂU", "SAICIUC": "SAUCIUC", "SCIUCHIN": 'ŞCIUCHIN', "SENDRESCU": "ŞENDRESCU",
    "SFINTESCU": "SFINŢESCU", "SING": "SINGH", "SOFRANCA": "ŞOFRANCA", "SPOEALĂ": "SPOIEALĂ",
    "SPRÂNCEANA": "SPRÂNCEANĂ", "SPATARU": "SPĂTARU", "STANILA": "STĂNILĂ",
    "STANILĂ": "STĂNILĂ", "STEFAN": "ŞTEFAN", "STANCESCU": "STĂNCESCU",
    "STANCULESCU": "STĂNCULESCU", "SUHANI": "ŞUHANI", "SZATMARI": "SZATMÁRI", "SZABO": "SZÁBO",
    "SARBU": "SÂRBU", "SALAN": "SĂLAN", "TAGA": "ŢAGA", "TANASE": "TĂNASE", "TELBIS": 'TELBIŞ',
    "TAPLIUC": "ŢAPLIUC", "LORENJA": "LORENA", "TATAR": "TĂTAR", "TAU": "ŢĂU",
    "TIMOASCĂ": "TIMOAŞCĂ", "TINCA": 'TINCĂ', "TINEGHE": "ŢINEGHE", "TIRLEA": "ŢIRLEA",
    "TOSA": "TOŞA", "TRUTA": "TRUŢĂ", "TRUŢA": "TRUŢĂ", "TUDURUŢA": "TUDURUŢĂ",
    "TARLION": "TÂRLION", "TĂMĂSAN": 'TĂMĂŞAN', "TĂNĂSICA": "TĂNĂSICĂ", "TĂU": "ŢAU",
    "TĂRNICERIU": "TĂRNICERU", "TARÂŢĂ": 'TĂRÂŢĂ', "VADANA": "VĂDANA", "VALS": "VALD",
    "ALIXANDRI": "ALEXANDRI", "VINTEANU": "VITANU", "VIOIU": "VIŞOIU", "VOICILA": "VOICILĂ",
    "VRINCEANU": "VRÂNCEANU", "VADEANU": "VĂDEANU", "VALAN": "VĂLAN", "VĂTZARU": "VĂRZARU",
    "VARZARU": 'VĂRZARU', "VASONAN": "VĂSONAN", "ZETES": "ZETEŞ", "ZUGRAVEL": "ZUGRĂVEL",
    "ÎMPARATU": 'ÎMPĂRATU', "ŞODINCA": "ŞODINCĂ", "SOLOVĂSTRU": "ŞOLOVĂSTRU",
    "SORTAN": 'ŞORTAN', "ŞORÂNDARU": 'ŞORÂNDACU', "ŞTEFANESCU": "ŞTEFĂNESCU",
    "STEFĂNIŢĂ": "ŞTEFĂNIŢĂ", "TAMBLAC": "ŢAMBLAC", "TARI": "ŢARI", "ŢIRLEA": 'ŢÂRLEA',
    "ŢUIU": "TUIU", "ŢÂCŞA": "TÂCŞA", "TIPLEA": "ŢIPLEA", "ŢĂPURIN": "ŢAPURIN",
    "TERMURE": "ŢERMURE", "CRETEANU": "CREŢEANU", "GIURCA": "GIURCĂ", "ILEASĂ": "ILIASĂ",
    "IVĂNIŞI": "IVĂNIŞ", "LAZĂU": "LĂZĂU", "MIRĂUŢĂ": "MIRUŢĂ", "PATRA": "PATRĂ",
    "RACLEA": "RÂCLEA"
}


def get_court_name(lines):
    """return the name of the court"""
    in_line_split = '(' if '(' in lines[0] else 'DIN'
    if ("CURŢII" in lines[0]) or ("CURTII" in lines[0]):
        court_name = "TRIBUNALUL " + lines[0][:lines[0].find(in_line_split)]
    elif ("TRIBUNALULUI" in lines[0]) or ("TRIBUNALUI" in lines[0]):
        court_name = "JUDECĂTORIA " + lines[0][:lines[0].find(in_line_split)]
    elif ("ÎNALTA" in lines[0]) or ("INALTA" in lines[0]):
        court_name = 'ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE'
    else:
        court_name = "CURTEA DE APEL " + lines[0].replace('|', '').strip()
    # catch multiline court names
    if "RAZA" in court_name:
        line = [lines[0].replace('|', '').strip() + lines[1].replace('|', '').strip()]
        court_name = get_court_name(line)
    return court_name_cleaner(court_name)


def court_name_cleaner(court_name):
    """returns court name that's gone through several cleaners"""
    # deal with the commercial and specialised "courts", which are actually tribunals
    if ("COMERCIAL M" in court_name) or ("SPECIALIZAT M" in court_name):
        court_name = court_name.replace("JUDECĂTORIA", "TRIBUNALUL")
    court_name = court_name.translate(str.maketrans('', '', string.punctuation))
    court_name = ' '.join(court_name.split()).strip()  # reduces whitespace to one space
    court_name = space_name_replacer(court_name, court_sectors_buc_transdict)
    court_name = space_name_replacer(court_name, court_names_transdict)
    # catch this non-standard name which slips through every other filter (very frustrating)
    if court_name == 'JUDECĂTORIA RM VÂLCEA':
        court_name = "JUDECĂTORIA RÂMNICU VÂLCEA"
    return court_name


court_names_transdict = {
    "ALSED": "ALEŞD", "TÎRGU": "TÂRGU", "TĂRGU": "TÂRGU", "STEHAIA": "STREHAIA", "PITESTI": "PITEŞTI",
    "HÎRLĂU": "HÂRLĂU", "CAMPULUNG": "CÂMPULUNG", "VÎNJU": "VÂNJU", "RM  VÂLCEA": "RÂMNICU VÂLCEA",
    "RM VÂLCEA": "RÂMNICU VÂLCEA", "RM VALCEA": "RÂMNICU VÂLCEA", "COMERCIAL": "COMERC SPECIAL",
    "SPECIALIZAT": "COMERC SPECIAL", "TG ": "TÂRGU ", "SF ": "SFÂNTU ", "ORASTIE": "ORĂŞTIE",
    "BALCESTI": "BĂLCEŞTI", "BÎRLAD": "BÂRLAD", "COSTESTI": "COSTEŞTI", "ARGES": "ARGEŞ",
    "DRAGASANI": "DRĂGĂŞANI", "SÎNNICOLAU": "SÂNNICOLAU", "ŞOMCUTA": "ŞOMCUŢA", "VALCEA": "VÂLCEA",
    "ICCJ": "ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE", "TRIBUNAL II": "TRIBUNALUL BIHOR",
    "CURTEA DE APEL MUREŞ": "CURTEA DE APEL TÂRGU MUREŞ", "TRIB ": "TRIBUNALUL ", "HATEG": "HAŢEG",
    "JUD ": "JUDECĂTORIA ", "PETROSANI": "PETROŞANI", "JUDECATORIA": "JUDECĂTORIA",
    "ROŞIORII": "ROŞIORI"
}

court_sectors_buc_transdict = {
    "LUI 1": "LUI UNU", "LUI 2": "LUI DOI", "LUI 3": "LUI TREI", "LUI 4": "LUI PATRU",
    "LUI 5": "LUI CINCI", "LUI 6": "LUI ŞASE",
    'RAZA TRIBUNALUL BISTRI': 'RAZA TRIBUNALULUI BISTRI'
}


# HELPERS FOR PROSECUTORS #

def update_prosec_people_periods(people_periods, unit_lines, split_mark, year, month):
    """updates a list of people periods"""
    parquet_name = get_parquet_name(unit_lines, split_mark)
    # get the clean-ish lines that actually contain peoples' names
    name_lines = get_prosec_person_name_lines(unit_lines)
    for nl in name_lines:
        name = nl[0]
        if name.upper().find('CRT') == -1:  # ignores this common dud line
            full_name = get_prosecutor_names(name)
            if full_name is not None:
                people_periods.append([full_name[0], full_name[1], parquet_name, year, month])


def get_prosec_person_name_lines(unit_lines):
    """returns a list of clean-ish lines, each containing a prosecutor's name"""
    # a bunch of cleaning to isloate names
    clean_name_lines = []
    for line in unit_lines[1:]:
        clean_line = list(filter(None, line.strip().replace('\xa0', '').splitlines()))
        for cl in clean_line:
            cleaner_line = list(filter(None, cl.split('|')))
            cleaner_line = list(filter(None, [cl.strip() for cl in cleaner_line[:-1]]))
            clean_name_lines.append(cleaner_line)
    return list(filter(None, clean_name_lines))


def get_prosecutor_names(fullname):
    """given a string with the full name, return a tuple with surname and given names"""
    if prosecs_normal_text(fullname):
        surnames, given_names = prosec_maiden_name_corrector(fullname)
        return prosec_name_clean(surnames, given_names)


def prosec_name_clean(surnames, given_names):
    """
    run surnames and given names through cleaners, return neater versions
    if fullname is not an empty string
    """
    # follow current orthographic rules and replace all "Î" in middle of word with "Â
    given_names = re.sub(r'\BÎ+\B', r'Â', given_names)
    surnames = re.sub(r'\BÎ+\B', r'Â', surnames)
    # got to cedilla diacritics
    given_names = given_names.replace('Ț', 'Ţ').replace('Ș', 'Ş')
    surnames = surnames.replace('Ț', 'Ţ').replace('Ș', 'Ş')
    # the NR bit eliminates a common parsing error
    given_names = space_name_replacer(given_names, given_name_mistakes_transdict).replace('NR', '')
    given_names = no_space_name_replacer(given_names, given_name_diacritics_transdict)
    surnames = no_space_name_replacer(surnames, prosec_surname_transdict)
    surnames, given_names = prosecs_problem_name_handler(surnames, given_names)
    # remove periods from given names
    given_names = given_names.replace('.', ' ')
    if len(surnames) > 2:
        # no outside spaces, no space more than one long
        surnames = ' '.join(surnames.split()).strip()
        given_names = ' '.join(given_names.split()).strip()
        return surnames, given_names


def prosec_maiden_name_corrector(fullname):
    """
    sometimes maiden names are put in brackets and are incorrectly in the given name field
    return maiden name at end of surname, with clean given name
    """
    maiden_name = ''
    # names in brackets are maiden names
    if re.search(r'\((.*?)\)', fullname):
        maiden_name = re.search(r'\((.*?)\)', fullname).group(0)  # isolate maiden name
        fullname = fullname.replace(maiden_name, '').strip()  # take maiden name out of fullname
        maiden_name = ' ' + maiden_name.replace(' ', '')  # clean up the maiden name
    # put maiden name after surname, isolate given names, eliminating hyphens
    surnames = fullname[:fullname.find(' ') + 1].strip() + maiden_name
    given_names = fullname[fullname.find(' ') + 1:].replace('-', ' ')
    return surnames, given_names


def prosec_multiline_name_catcher(people_periods):
    """catches and handles multiline and/or type names that slip through other functions"""
    for idx, val in enumerate(people_periods):
        if val[0][0] == '(':
            # handles this particular exception
            if val[1] == "TĂTARUOANA":
                people_periods[idx][0] = val[1][:6] + ' ' + people_periods[idx][0]
                people_periods[idx][1] = val[1][6:]
            # handles multiline name like
            # (APETROAIEI) CHINDEA
            # CODRUŢA SIMONA
            elif val[1] != '':
                people_periods[idx + 1][1] = people_periods[idx + 1][0] + ' ' + people_periods[idx + 1][1]
                people_periods[idx + 1][0] = people_periods[idx][1] + ' ' + people_periods[idx][0]
                people_periods[idx][0] = ''
            # handles multiline name like
            # DIMOFTE | RODICA MARLENA
            # (VASILE)
            else:
                people_periods[idx - 1][0] = people_periods[idx - 1][0] + ' ' + val[0]
                people_periods[idx][0] = ''
    return [i for i in people_periods if i[0] != '']


def get_parquet_name(lines, split_mark):
    """returns the name of the parquet"""
    # if first entries are empty, go until you hit something
    if not bool(re.match('^(?=.*[a-zA-Z])', lines[0])):
        lines = [l for l in lines if bool(re.match('^(?=.*[a-zA-Z])', l))]
    parquet_name = ''
    if lines:
        if re.search(r'ANTICORUPTIE|ANTICORUPŢIE', lines[0]) is not None:
            parquet_name = "DIRECŢIA NAŢIONALĂ ANTICORUPŢIE"
        elif re.search(r"INVESTIGARE", lines[0]) is not None:
            parquet_name = "DIRECŢIA DE INVESTIGARE A INFRACŢIUNILOR DE CRIMINALITATE ORGANIZATĂ ŞI TERORISM"
        elif re.search(r"ÎNALTA", lines[0]) is not None:
            parquet_name = "PARCHETUL DE PE LÂNGĂ ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE"
        elif "TRIBUNALUL PENTRU MINORI" in lines[0]:
            parquet_name = "PARCHETUL DE PE LÂNGĂ TRIBUNALUL PENTRU MINORI ŞI FAMILIE BRAŞOV"
        else:
            parquet_name = (split_mark + lines[0]).replace('|', '').strip()
            parquet_name = parquet_name.replace('-', ' ').translate(str.maketrans('', '', string.punctuation))
    parquet_name = parquet_name.replace('  ', ' ')
    if multiline_parquet_name(parquet_name):
        parquet_name = parquet_name + ' ' + lines[1].replace('|', '').strip()
    parquet_name = space_name_replacer(parquet_name, parquet_names_transict)
    parquet_name = ' '.join(parquet_name.split()).strip()
    if parquet_name == "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA ALBA":
        parquet_name = "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA ALBA IULIA"
    return parquet_name


def multiline_parquet_name(parquet_name):
    """return True if red flags of multiline parquet name are present; if True, we can contract name across lines"""
    if (parquet_name == "PARCHETUL DE") or \
            (parquet_name == "PARCHETUL DE PE") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ TRIBUNALUL") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ CURTEA") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ CURTEA DE") \
            or (parquet_name == "PARCHETUL DE PE LÂNGĂ CURTEA DE APEL"):
        return True
    else:
        return False


def parquet_name_cleaner(parquet_name):
    """returns parquet name that's gone through several cleaners"""
    parquet_name = parquet_name.translate(str.maketrans('', '', string.punctuation))
    parquet_name = parquet_name.replace('-', ' ').replace('  ', ' ')
    parquet_name = space_name_replacer(parquet_name, parquet_sectors_buc_transdict)  # parquet = row[2]
    parquet_name = space_name_replacer(parquet_name, parquet_names_transict)
    parquet_name = ' '.join(parquet_name.split()).strip()
    if 'PARCHETUL DE PE LÂNGĂ ' not in parquet_name:
        parquet_name = 'PARCHETUL DE PE LÂNGĂ ' + parquet_name
    if "ŞIMLEU" in parquet_name:
        parquet_name = "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA ŞIMLEUL SILVANIEI"
    return parquet_name


parquet_names_transict = {
    "BRASOV": "BRAŞOV", "BUCUREŞTI": "BUCUREŞTI", "CONSTANTA": "CONSTANŢA", "PITESTI": "PITEŞTI",
    "PLOIESTI": "PLOIEŞTI", "CAMPULUNG": "CÂMPULUNG", "VÎNJU": "VÂNJU", "RM  VALCEA": "RÂMNICU VÂLCEA",
    "COMERCIAL": "COMERC SPECIAL", "SPECIALIZAT": "COMERC SPECIAL", "TG MURES": "TÂRGU MUREŞ",
    "LEHLIU GARA": "LEHLIU GARĂ", "ODORHEIUL": "ODORHEIU", "ROSIORI": "ROŞIORI", "TÎRGU": "TÂRGU",
    "TARGU": "TÂRGU", "IALOMITA": "IALOMIŢA", "ÎALTA": "ÎNALTA", "SÎNNICOLAU": "SÂNNICOLAU",
    "TG BUJOR": "TÂRGU BUJOR", "LAPUS": "LĂPUŞ", "SECTORULUI CINCI BUCUREŞTI": "SECTORULUI CINCI",
    "SECTORULUI DOI BUCUREŞTI": "SECTORULUI DOI", "SECTORULUI PATRU BUCUREŞTI": "SECTORULUI PATRU",
    "SECTORULUI TREI BUCUREŞTI": "SECTORULUI TREI", "SECTORULUI UNU BUCUREŞTI": "SECTORULUI UNU",
    "SECTORULUI ŞASE BUCUREŞTI": "SECTORULUI ŞASE", "SFANTU": "SFÂNTU", "ŞOMCUTA": "ŞOMCUŢA",
    "JUDECĂTORIAVIŞEU": "JUDECĂTORIA VIŞEU", "TRIBUNALULBRAŞOV": "TRIBUNALUL BRAŞOV",
    "TIMISOARA": "TIMIŞOARA", "HĂRŞOVA": "HÂRŞOVA", "CALARASI": "CĂLĂRAŞI",
    "CÎMPENI": "CÂMPENI", "FAGARAS": "FĂGĂRAŞ", "INTORSURA BUZAULUI": "ÎNTORSURA BUZĂULUI",
    "JUGOJ": "LUGOJ", "ZARNESTI": "ZĂRNEŞTI", "TRIBUNLAUL": "TRIBUNALUL", "INSURĂŢEI": "ÎNSURĂŢEI",
    "REŞITA": 'REŞIŢA', "TÂRNAVENI": "TÂRNĂVENI", "CARAS SEVERIN": "CARAŞ SEVERIN",
    "PROCURATURA JUDEŢEANĂ": "PARCHETUL DE PE LÂNGĂ TRIBUNALUL", "RĂCANI": "RĂCARI", "AGNIŢA": "AGNITA",
    "PROCURATURA LOCALĂ": "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA", "TG SECUIESC": "TÂRGU SECUIESC",
    "SF GHEORGHE": "SFÂNTU GHEORGHE", "ŞIMLEU SILVANIEI": "ŞIMLEUL SILVANIEI"

}

parquet_sectors_buc_transdict = {
    "PARCHETUL DE PE LÂNGĂ  ": '', "TOR 1": "TORULUI UNU", "TOR 2": "TORULUI DOI",
    "TOR 4": "TORULUI PATRU", "TOR 3": "TORULUI TREI", "TOR 5": "TORULUI CINCI",
    "TOR 6": "TORULUI ŞASE", 'TORUL 1': "TORULUI UNU", "TORUL 2": "TORULUI DOI",
    "TORUL 3": "TORULUI TREI", "TORUL 4": "TORULUI PATRU", "TORUL 5": "TORULUI CINCI",
    "TORUL 6": "TORULUI ŞASE", "TRIBUNALULMF": "TRIBUNALUL PENTRU MINORI ŞI FAMILIE"
}


def pdf_get_special_parquets(file_path):
    """
    The .pdf files have parquet name written ONLY in their file path; look there.
    DNA, PICCJ, and DIICOT are special: they're either at the top of the hierarchy, or form a semi-parallel system
    :param file_path: string, path to .pdf file containing prosecutor employment rolls
    :return string, standardised name of special parquet
    """

    if "DNA" in file_path:
        special_parquet = "DIRECŢIA NAŢIONALĂ ANTICORUPŢIE"
    elif "DIICOT" in file_path:
        special_parquet = "DIRECŢIA DE INVESTIGARE A INFRACŢIUNILOR DE CRIMINALITATE ORGANIZATĂ ŞI TERORISM"
    elif "PICCJ" in file_path:
        special_parquet = "PARCHETUL DE PE LÂNGĂ ÎNALTA CURTE DE CASAŢIE ŞI JUSTIŢIE"
    else:
        special_parquet = ''
    return special_parquet


def pdf_get_parquet(row):
    """
    The .pdf files have parquet name written ONLY in their file path; look there.
    :param row: row of person-period table, as parsed by collector.converter.convert.get_pdf_people_periods
    :return: string, standardised name of row's parquet
    """

    if row[-1] != '':
        parquet = "PARCHETUL DE PE LÂNGĂ JUDECĂTORIA " + row[-1].upper().strip()
    elif row[-2] != '':
        parquet = row[-2].upper().strip().replace("PT", "PARCHETUL DE PE LÂNGĂ TRIBUNALUL")
    elif row[-3] != '':
        parquet = row[-3].upper().strip().replace("PCA", "PARCHETUL DE PE LÂNGĂ CURTEA DE APEL")
    else:
        parquet = 'ERROR'
    return parquet


def prosecs_normal_text(text):
    """returns True if red flags of misprocessed name are absent; if False, we can ignore the line containing them"""
    if (len(text) > 3) and ("LA DATA DE" not in text) and ("ÎNCEPÂND CU" not in text) \
            and ("CRIMINALITATE" not in text) and ("TÂRGU" not in text) and ("NUME" not in text) \
            and ("ORGANIZATĂ" not in text) and ("STABILITATE" not in text) and ("EXTERNE" not in text) \
            and ("CURTEA" not in text) and ("INFRACŢIUNILOR" not in text) and ("EUROPA" not in text) \
            and ("LÂNGĂ" not in text) and ("DIICOT" not in text) and ("DNA" not in text) \
            and ("PROCUROR" not in text) and ("JUDECĂTORIA" not in text) and ("CSM" not in text):
        return True
    else:
        return False


def prosecs_problem_name_handler(surnames, given_names):
    """some names are frequently input wrong in the base data file; this function handles them ad-hoc"""
    if given_names == "FLORESCU":
        given_names, surnames = surnames, "FLORESCU"
    if ("HĂINEALĂ" in given_names) or ("SCHMIDT" in given_names):
        given_names, surnames = "OANA", "SCHMIDT HĂINEALĂ"
    if "RODRIGUES" in given_names:
        given_names, surnames = "CRISTINA", "MĂRINCEAN"
    if "ECEDI" in surnames:
        given_names = "STOISAVLEVICI LAURA"
    if "CANTEMIR" in given_names:
        given_names, surnames = "ŞTEFĂNEL", "OPREA CANTEMIR"
    if "MASSIMO" in given_names:
        given_names, surnames = "MARIO MASSIMO", "DEL CET"
    if "MELANOVSCHI" in given_names:
        given_names, surnames = "LIUDMILA", "VARTOLOMEI MELANOVSCHI"
    if "PĂCUREŢU" in given_names:
        given_names, surnames = "ION", "CANACHE PĂCUREŢU"
    if "ŞESTACHOVSCHI" in given_names or 'ŞESTACOVSCHI' in given_names:
        given_names, surnames = "SIMONA", "ŞESTACHOVSCHI MOANGĂ"
    if "EZRA" in given_names:
        given_names, surnames = "CRISTINA DIANA", "BEN EZRA"
    if "DUMITRESCU" in surnames and "CHIŞCAN" in surnames:
        given_names, surnames = "LUMINIŢA", "NICOLESCU (DUMITRESCU CHIŞCAN)"
    if given_names == "COLŢ":
        given_names, surnames = 'MIHAI', "COLŢ"
    return surnames, given_names


prosec_surname_transdict = {
    "HĂLCIUG": "HĂLGIUG", "AILOAIE": "AILOAE", "ANDREIAS": "ANDREIAŞ",
    "ANTĂLOAE": "ANTĂLOAIE", "ANUŢA": "ANUŢĂ", "APETROAIEI": "APETROIE", "ARAMA": "ARAMĂ",
    "ARGESEANU": "ARGEŞEANU", "AVĂDĂNEI": "AVĂDĂNII", "BĂDIŢA": "BĂDIŢĂ",
    "BĂRBUCIANU": "BĂRBUCEANU", "BANICA": "BANICĂ", "BLAJAN": "BLĂJAN", "BLANARU": "BLĂNARU",
    "BOŢOCHINĂ": "BOŢOGHINĂ", "CAUTIS": "CAUTIŞ", "CEASCAI": "CEAŞCAI", "CEASCĂI": "CEAŞCAI",
    "CECALACEAN": "CECĂLACEAN", "CENUSE": "CENUŞE", "CHIRILA": "CHIRILĂ", "CHIS": "CHIŞ",
    "CIMPEAN": "CÂMPEAN", "CIOARA": "CIOARĂ", "CISMASU": "CISMAŞU", "CIUMARNEAN": "CIUMĂRNEAN",
    "COCÎRLĂ": "COCÂRLĂ", "COMANITA": "COMĂNIŢĂ", "CREŢ": "CRET", "CUBLESAN": "CUBLEŞAN",
    "CÎMPEAN": "CÂMPEAN", "CĂPĂŢÎNĂ": "CĂPĂŢÂNĂ", "DASCALU": "DASCĂLU", "DONTETE": "DONŢETE",
    "DRAGAN": "DRĂGAN", "FACKELMAN": "FACKELMANN", "FOITOS": "FOITOŞ", "FRUNZA": "FRUNZĂ",
    "GHITU": "GHIŢU", "GLONT": "GLONŢ", "GRIGORAS": "GRIGORAŞ", "GÎDEA": "GÂDEA",
    "HARTMAN": "HARTMANN", "HOBINCU": "HOBÎNCU", "IANUS": "IANUŞ", "IASINOVSCHI": "IAŞINOVSCHI",
    "IFTINICHI": "IFTINCHI", "ILIES": "ILIEŞ", "IONITA": "IONIŢA", "JABA": "JABĂ",
    "JAŞCANUI": "JAŞCANU", "JUGASTRU": "JUGĂSTRU", "JĂRDIANA": "JĂRDIEANU",
    "JĂRDIANU": "JĂRDIEANU", "KOVESI": "KÖVESI", "LIVADARU": "LIVĂDARU",
    "LIVĂDARIU": "LIVĂDARU", "LIŢA": "LIŢĂ", "LĂNCRĂJAN": "LĂNCRĂNJAN", "MASCAS": "MASCAŞ",
    "MATES": "MATEŞ", "MERISESCU": "MERIŞESCU", " MESAROS": "MESAROŞ", "MICLOSINĂ": "MICLOŞINĂ",
    "MIERLITA": "MIERLIŢĂ", "MIRISAN": "MIRIŞAN", "MITRICA": "MITRICĂ", "MOACA": "MOACĂ",
    "MORIŞCA": "MORIŞCĂ", "MAMALIGAN": "MĂMĂLIGAN", "MĂNDICA": "MĂNDICĂ", "NARITA": "NARIŢA",
    "NEAMTU": "NEAMŢU", "NEGRUTIU": "NEGRUŢIU", "NĂVODARU": "NĂVĂDARU", "PAIUSI": "PAIUŞI",
    "PETRICA": "PETRICĂ", "PETRUSCA": "PETRUŞCĂ", "PLESCA": "PLEŞCA", "POREMSCHI": "POREMBSCHI",
    "POSTICA": "POSTICĂ", "POTERASU": "POTERAŞU", "POTÎRCĂ": "POTÂRCĂ", "PÎRLOG": "PĂRLOG",
    "PRISECARIU": "PRISECARU", "PROSA": "PROŞA", "PURTAN": "PURTANT", "PÎRVU": "PÂRVU",
    "PÎRCĂLĂBESCU": "PÂRCĂLĂBESCU", "RADOI": "RĂDOI", "RADUCANU": "RĂDUCANU",
    "RAKOCZI": "RAKOCZY", "RASCOTA": "RASCOTĂ", "REINKE": "REINCKE", "SADIC": "SADÎC",
    "SFÎRIAC": "SFÂRIAC", "SITIAVU": "SITIARU", "SOVA": "ŞOVA", "SPERIUSI": "SPERIUŞI",
    "STANCULESCU": "STĂNCULESCU", "STEPĂNESCU": "STEPANENCU", "STOENESC": "STOENESCU",
    "STRANCIUC": "STRANCIUG", "STRUNA": "STRUNĂ", "STRÎMBEI": "STRÂMBEI", "STÎNGĂ": "STÂNGĂ",
    "SUBTIRELU": "SUBŢIRELU", "SUTMAN": "SUTIMA", "TARNOVIETCHI": "TARNOVIEŢCHI",
    "TELEKI": "TELEKY", "TIGANAS": "ŢIGĂNAŞ", "TIGANUS": "ŢIGĂNUŞ", "TINICA": "TINICĂ",
    "TOLOARGĂ": "TOLOROAGĂ", "TOMOIESCU": "TOMOESCU", "TOMOIOAGĂ": "TOMOIAGĂ",
    "TOPLICEANU": "TOPOLICEANU", "TRASTAU": "TRASTĂU", "VACARU": "VĂCARU", "VEISA": "VEIŞA",
    "VESTEMANU": "VEŞTEMEANU", "VLADESCU": "VLĂDESCU", "VRÎNCIANU": "VRÂNCIANU",
    "VÎLCU": "VÂLCU", "ZAMFIRECU": "ZAMFIRESCU", "ŢÎRLEA": "ŢÂRLEA", "ŢÂBÂRNĂ": "ŢĂBÂRNĂ",
    "ADRINOIU": "ANDRINOIU", "AMUSCALIŢEI": "AMUSCĂLIŢEI", "BADICA": "BĂDICA",
    "BALAS": "BALAŞ", "BALOŞ": "BOLOŞ", "BARAI": "BARA", "BILHA": "BÂLHA", "BOCHIS": "BOCHIŞ",
    "BORS": "BORŞ", "BOSCANU": 'BOSIANU', "BOSTIOG": "BOŞTIOG", "BOTOC": "BOŢOC",
    "BRATULEA": "BRĂTULEA", "BIRSAN": "BÂRSAN", "BALDEA": "BÂLDEA", "BITU": "BÂTU",
    "BABUŢĂU": "BĂBUŢĂU", "BĂDICA": "BĂDICĂ", "BAGEAG": "BĂGEAG", "CALIN": "CĂLIN",
    "CECĂLACEAN": "CECĂLĂCEAN", "CERGHIZAN": "CERCHIZAN", "CERGA": "CERGĂ",
    "GHIRILĂ": "CHIRILĂ", "CIMPEANA": "CIMPEANU", "CIMPOIERU": "CIMPOERU",
    "CIOCHINA": 'CIOCHINĂ', "CITIRIGA": "CITIRIGĂ", "CIOBOTARIU": "CIUBOTARIU",
    "COJOACA": "COJOACĂ", "COSNEANU": "COŞNEANU", "CRACIUNESCU": 'CRĂCIUNESCU',
    "CRISU": "CRIŞU", "CALINESCU": "CĂLINESCU", "CĂRĂMIZANU": "CĂRĂMIZARU", "DUSA": "DUŞA",
    "DUTOIU": 'DUŢOIU', "FELDIOREAN": "FELDIOREANU", "FISCHEV": "FISCHER", "GABURA": 'GABURĂ',
    "GARL": "GAL", "GERENY": "GERENYI", "GOSEA": "GOŞEA", "HARLAMBIE": "HARALAMBIE",
    "HÂRŞMAN": "HIRŞMAN", "ILIESCI": "ILIESCU", "MARIS": "MARIŞ", "MESAROS": 'MESAROŞ',
    "MIHILĂ": "MIHĂILĂ", "MORŞOI": "MURŞOI", "MOTOARCA": "MOTOARCĂ", "MOSOIU": "MOŞOIU",
    "MURESAN": 'MUREŞAN', "MUT": "MUŢ", "MĂCEŞANU": "MĂCEŞEANU", "NEGUŢ": "NEGRUŢ",
    "NICOARA": "NICOARĂ", "NISIOI": "NISOI", "NITESCU": 'NIŢESCU', "NASTASIE": "NĂSTASIE",
    "ODIHNĂ": "ODINĂ", "ONA": "ONEA", "OPARIUC": "OPĂRIUC", "PANCESCU": "PĂNCESCU",
    "PANA": "PANĂ", "PANTURU": 'PANŢURU', "PAUN": 'PĂUN', "PASALEGA": 'PAŞALEGA',
    "PASTIU": 'PAŞTIU', "PRAŢA": "PAŢA", "PETRAN": 'PETREAN', "PRUNA": 'PRUNĂ',
    "PĂRCĂLĂBESCU": 'PÂRCĂLĂBESCU', "PAUNA": "PĂUNA", "RADUCA": "RADUICA", "ROMAS": "ROMAŞ",
    "ROTARIU": 'ROTARU', "RADULESCU": 'RĂDULESCU', "SCALETCHI": "SCALEŢCHI",
    "STANCESCU": "STĂNCESCU", "STANCIOIU": "STĂNCIOIU", "STEFAN": 'ŞTEFAN', "SUTIMA": "SUTIMAN",
    "SINGEORZAN": "SÂNGEORZAN", "TAMAŞ": 'TĂMAŞ', "TANASE": 'TĂNASE', "TAPLIUC": "ŢAPLIUC",
    "TRAISTARU": "TRĂISTARU", "TRINCĂ": "TRÂNCĂ", "TURLEA": 'ŢURLEA', "TANASĂ": 'TĂNASĂ',
    "TARAŞ": "TĂRAŞ", "VESTEMEAN": "VEŞTEMEAN", "VESTEMEANU": "VEŞTEMEANU",
    "VINTILA": "VINTILĂ", "VOINA": 'VOINEA', "VIJIAC": "VÂJIAC", "VADUVAN": "VĂDUVAN",
    "VĂETIŞI": "VĂETIŞ", "VĂSII": "VĂSÂI", "ZAPODEANU": "ZĂPODEANU", "SELARU": "ŞELARU",
    "SENTEŞ": "ŞENTEŞ", "SPAIUC": "ŞPAIUC", "TICOFSCHI": "ŢICOFSCHI"
}


# HELPERS FOR EXECUTORI JUDECĂTOREŞTI

def executori_name_cleaner(surnames, given_names, chamber, town):
    """
    Apply standard cleaners to the surnames and given names of judicial debt collectors.

    :param surnames: string
    :param given_names: string
    :param town: string, the town in which the executor operates
    :param chamber: string, the regional area in which the executor operates,which coincide with appellate
                    court jurisdictions
    :return: cleaned names
    """

    surnames, given_names, chamber, town = str_cln(surnames), str_cln(given_names), str_cln(chamber), str_cln(town)

    # remove a maiden name marker from the surnames
    surnames = surnames.replace("FOSTA", ' ').replace("FOSTĂ", ' ')

    # run given names through the translation dictionaries
    given_names = space_name_replacer(given_names, given_name_mistakes_transdict)
    given_names = no_space_name_replacer(given_names, given_name_diacritics_transdict)
    surnames = no_space_name_replacer(surnames, executori_surname_transdict)

    # run chamber and town names through translation dictionaries
    chamber = key_to_value(chamber, executori_chamber_transdict)
    town = key_to_value(town, executori_town_transdict)
    town = executori_town_exceptions(town, chamber)

    # return, removing outside spaces and reducing multiple spaces to one
    return [' '.join(surnames.split()).strip(), ' '.join(given_names.split()).strip(),
            ' '.join(chamber.split()).strip(), ' '.join(town.split()).strip()]


executori_surname_transdict = {"MILOS": "MILOŞ", "TALPA": "TALPĂ", "OANA": "OANĂ", "CHERSA": "CHERŞA",
                               "FRINCU": "FRÂNCU"}


def executori_town_exceptions(town, chamber):
    """
    There's a misspelling of towns in which it is unclear which town is being referred to unless we also
    consult information about its chamber. This function catches and corrects that exception.

    :param town: string, the town (localitatea) in which an executor has their office
    :param chamber: string, the chamber (camera), which is the regional unit in which the executor operates
    :return: the corrected town string
    """

    if town == "CÂMPULUNG" and chamber == "SUCEAVA":
        town = "CÂMPULUNG MOLDOVENESC"
    return town


executori_chamber_transdict = {"CLUJ NAPOCA": "CLUJ", "ALBA": "ALBA IULIA", "ARAD": "TIMIŞOARA",
                               "ALBA LULIA": "ALBA IULIA", "BACAU": "BACĂU", "BRASOV": "BRAŞOV",
                               "BUZĂU": "PLOIEŞTI"}

executori_town_transdict = {"SFÂNTU": "SFÂNTU GHEORGHE", "BUZĂULUI": "ÎNTORSURA BUZĂULUI", "ALBA LULIA": "ALBA IULIA",
                            "BÂRLAN": "BÂRLAD", "CHIŞINĂU CRIŞ": "CHIŞINEU CRIŞ", "CLUJ": "CLUJ NAPOCA",
                            "CURTEA DE": "CURTEA DE ARGEŞ", "DROBETA TURNU": "DROBETA TURNU SEVERIN",
                            "GHEORGHIENI": "GHEORGHENI", "GHEORGHE": "SFÂNTU GHEORGHE", "GĂESTI": "GĂEŞTI",
                            "INTORSURA BUZĂULUI": "ÎNTORSURA BUZĂULUI", "MARE": "SÂNNICOLU MARE",
                            "SÂNNICOLAU": "SÂNNICOLAU MARE", "MARMAŢIEI": "SIGHETU MARMAŢIEI", "MOLDOVA":
                                "MOLDOVA NOUĂ", "MOLDOVENESC": "CÂMPULUNG MOLDOVENESC", "MACIN": "MĂCIN",
                            "ODOREHIU": "ODORHEIU SECUIESC", "ORAVITA": "ORAVIŢA", "ORAŞTIE": "ORĂŞTIE",
                            "PODU": "PODU TURCULUI", "PODUL TURCULUI": "PODU TURCULUI", "RADUCANENI": "RĂDUCĂNENI",
                            "RM SĂRAT": "RÂMNICU SĂRAT", "RM VÂLCEA": "RÂMNICU VÂLCEA", "ROŞIORI DE": "ROŞIORI DE VEDE",
                            "RĂCĂRI": "RĂCARI", "SECUIESC": "ODORHEIU SECUIESC", "SECUISC": "ODORHEIU SECUIESC",
                            "SFANTU GHEORGHE": "SFÂNTU GHEORGHE", "SIGHISOARA": "SIGHIŞOARA",
                            "SILVANIEI": "ŞIMLEU SILVANIEI", "SÂNICOLAU MARE": "SÂNNICOLAU MARE",
                            "TG BUJOR": "TÂRGU BUJOR", "TG CĂRBUNEŞTI": "TÂRGU CĂRBUNEŞTI", "TG NEAMŢ": "TÂRGU NEAMŢ",
                            "TULCEĂ": "TULCEA", "VIŞEUL DE SUS": "VIŞEU DE SUS", "VĂLENII DE": "VĂLENII DE MUNTE",
                            "ZÂMEŞTI": "ZĂRNEŞTI", "ZĂRNEŞTI SUSPENDAT": "ZĂRNEŞTI", "ÎNTORSURA": "ÎNTORSURA BUZĂULUI",
                            "ŞIMLEU": "ŞIMLEU SILVANIEI", "TÂRGU": "TÂRGU CĂRBUNEŞTI"}


# HELPERS FOR NOTARI PUBLICI

def notaries_given_name_correct(given_names):
    """
    Corrects typos in given names for notaries.

    :param given_names: string, given name
    :return: corrected given names, as string
    """

    given_names = space_name_replacer(given_names, notaries_given_name_transdict)
    given_names = no_space_name_replacer(given_names, given_name_diacritics_transdict)
    return given_names


notaries_given_name_transdict = {"LULIA": "IULIA", "LBOLYA": "IBOLYA", "LULIAN": "IULIAN", "HORALIU": "HORAŢIU",
                                 "LOAN": "IOAN", "LULIANA": "IULIANA", "LONUŢ": "IONUŢ", "LOANA": "IOANA",
                                 "LLEANA": "ILEANA", "LMANUELA": "IMANUELA", "LONELA": "IONELA", "LOSIF": "IOSIF",
                                 "LVANCA": "IVANCA", "LONEL": "IONEL", "LLIOARA": "ILIOARA", "LUSTINA": "IUSTINA",
                                 "LULIUS": "IULIUS", "LRINA": "IRINA", "LANINA": "IANINA", "COMELIU": "CORNELIU",
                                 "LOLANDA": "IOLANDA", "LLIE": "ILIE", "VIAD": 'VLAD', "ANDREL": "ANDREI"}


def notaries_town_correct(town):
    """
    Correct misspelled town/commune names
    :param town: string, name of town/comune (localitate)
    :return: clean place name
    """
    corrected_town = key_to_value(town, notaries_town_transdict)
    return corrected_town


notaries_town_transdict = {"DĂRĂŞTI LLFOV": "DĂRĂŞTI ILFOV", "LERNUT": "IERNUT", "LEPUREŞTI": "IEPUREŞTI",
                           "PODU LLOAIEI": "PODU ILOAIEI"}
