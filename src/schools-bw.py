from typing import Any
import wikitextparser as wtp
import pywikibot
import requests
import telegram
import logging
import schools
import random
import optOut
import utils
import json


def getAllSchoolDischs(search: str|None='', multiplePages: bool=True) -> set[str]:
    if search == None: return set()
    uid = random.randint(1, 99999999)
    data: set[str] = set()
    ok = True
    pageNumber = 1
    url = 'https://lobw.kultus-bw.de/didsuche/DienststellenSucheWebService.asmx/SearchDienststellen'
    while ok:
        try:
            query = {'command': 'QUICKSEARCH', 'data': {'dscSearch': search, 'dscPlz': '', 'dscOrt': '', 'dscDienststellenname': '', 'dscSchulartenSelected': '', 'dscSchulstatusSelected': '', 'dscSchulaufsichtSelected': '',
                                                        'dscOrtSelected': '', 'dscEntfernung': '', 'dscAusbildungsSchulenSelected': '', 'dscAusbildungsSchulenSelectedSart': '', 'dscPageNumber': str(pageNumber), 'dscPageSize': '1000', 'dscUnique': str(uid)}}
            res = requests.post(url, json={'json': json.dumps(query)})
            assert res.ok
            rows: list[dict[str, str]] = json.loads(
                res.json().get('d')).get('Rows')
            assert len(rows) > 0
            for school in rows:
                data.add(school['DISCH'].strip("'"))
            pageNumber += 1
            if not multiplePages: ok = False
        except AssertionError:
            ok = False
    return data


def getSchoolByDisch(disch: str):
    url = 'https://lobw.kultus-bw.de/didsuche/DienststellenSucheWebService.asmx/GetDienststelle'
    res = requests.post(url, json={'disch': disch})
    data: dict = json.loads(res.json().get('d'))
    return schools.School(
        name = utils.getText(data.get('NAME')),
        authority = schools.Authority(name=utils.getText(data.get('UEBERGEORDNET')), url=data['UEBERGEORDNET_INTERNET']),
        id = data['DISCH'],
        state = 'BW',
        address = schools.Address(street=data['DISTR'], plz=int(data['PLZSTR']), town=data['DIORT'], district=data['KREISBEZEICHNUNG']),
        phone = data['TELGANZ'],
        fax = data['FAXGANZ'],
        email = data['VERWEMAIL'],
        url = data['INTERNET'],
        principal = data['SLFAMVOR'],
        vicePrincipal = data['V1FAMVOR'],
        students = data['SCHUELER'],
        classes = data['KLASSEN'],
        teachers = data['LEHRER'],
        description = data['DISCH_KURZTEXT'],
        sponsor = schools.Sponsor(sponsorType=data['WL_KURZ_BEZEICHNUNG'], name=data['STR_KURZ_BEZEICHNUNG'])
    )


def addAllDischs():
    site = pywikibot.Site('de', 'wikipedia')
    site.login()
    generator = utils.getTemplateUsage(site, 'Infobox Schule')
    for page in generator:
        parsed = wtp.parse(page.get())
        for template in parsed.templates:
            if template.name.strip() != 'Infobox Schule': continue
            if utils.findTemplateArg(template, 'Region-ISO') != 'DE-BW': continue
            currentID = utils.findTemplateArg(template, 'Schulnummer')
            if currentID not in [None, '']:
                logging.debug(f'skip because id is already set: {page.title()}')
                continue
            dischs = getAllSchoolDischs(page.title()) | getAllSchoolDischs(utils.findTemplateArg(template, 'Schulname'))
            if len(dischs) == 0:
                logging.info(f'skip because no disch was found: {page.title()}')
                continue
            if len(dischs) > 1:
                logging.info(f'skip because multiple dischs were found: {page.title()}')
                continue
            logging.info(f'handle {page.title()}')
            disch = dischs.pop()
            template.set_arg('Schulnummer', disch, preserve_spacing=True)
            page.text = parsed
            if optOut.isAllowed(page):
                page.save(bot=True, minor=False, summary=(f'Bot: Ergänze Schulnummer (DISCH). Siehe https://schulamt-bw.de/Schuladressdatenbank'))


def addWikidataNumberClaim(repo: Any, item: pywikibot.ItemPage, property: str, number: int, url: str, pointInTime: pywikibot.WbTime):
    logging.info(f'try to add claim {property} to {item.title()}')
    existingClaims: list[pywikibot.Claim] = item.get()['claims'].get(property) or []
    for existingClaim in existingClaims:
        pointInTimeQualifiers: list[pywikibot.Claim] = existingClaim.qualifiers.get('P585') or []
        for qual in pointInTimeQualifiers:
            if qual.getTarget() == pointInTime:
                logging.info(f'skip update of {item.title()} because {property} is already set with same point in time qualifier.')
                return
    # Anzahl der Schüler / Studenten / Lehrer
    claim = pywikibot.Claim(repo, property)
    claim.setTarget(pywikibot.WbQuantity(number, site=repo))
    item.addClaim(claim, summary=f'Bot: Adding claim {property}.')
    # Zeitpunkt / Stand
    qualifier = pywikibot.Claim(repo, 'P585')
    qualifier.setTarget(pointInTime)
    claim.addQualifier(qualifier, summary=f'Bot: Adding a qualifier to {property}.')
    # URL der Fundstelle und abgerufen am
    utils.addWikidataSource(repo, claim, url)


def updateWikidata():
    logging.info('START UPDATING BW SCHOOLS ON WIKIDATA')
    wikipedia = pywikibot.Site('de', 'wikipedia')
    wikidata = pywikibot.Site('wikidata', 'wikidata')
    repo = wikidata.data_repository()
    wikidata.login()
    generator = utils.getTemplateUsage(wikipedia, 'Infobox Schule')
    for page in generator:
        parsed = wtp.parse(page.get())
        ids = set()
        for template in parsed.templates:
            if template.name.strip() != 'Infobox Schule': continue
            if utils.findTemplateArg(template, 'Region-ISO') != 'DE-BW': continue
            id = utils.findTemplateArg(template, 'Schulnummer')
            if id != None: ids.add(id)
        if len(ids) != 1: continue
        disch = ids.pop()
        logging.info(f'found disch {disch} of {page.title()}')
        try:
            school = getSchoolByDisch(disch)
        except Exception as e:
            logging.error(f'failed when fetching school: {e}')
        else:
            item = pywikibot.ItemPage.fromPage(page)
            if school.students is not None: addWikidataNumberClaim(repo, item, 'P2196',  school.students, 'https://schulamt-bw.de/Schuladressdatenbank', pywikibot.WbTime(2024, 1))
            if school.teachers is not None: addWikidataNumberClaim(repo, item, 'P10610', school.teachers, 'https://schulamt-bw.de/Schuladressdatenbank', pywikibot.WbTime(2024, 1))
    logging.info('FINISHED UPDATING BW SCHOOLS ON WIKIDATA')


# nohup .venv/bin/python src/schools-bw.py >> logs/schools.log &
if __name__ == '__main__':
    try:
        logging.basicConfig(format='%(asctime)s - %(levelname)s - SCHOOLS BW - %(message)s', level=logging.INFO)
        addAllDischs()
        updateWikidata()
        telegram.send('finished updating bw schools successfull', silent=True)
    except Exception:
        telegram.handleException('SCHOOLS-BW')