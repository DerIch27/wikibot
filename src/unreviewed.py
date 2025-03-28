from bs4 import BeautifulSoup
import pywikibot
import telegram
import requests
import logging
import optOut
import utils
import time
import csv
import io
import re


def scrapeUnreviewedChanges():
    response = requests.get('https://de.wikipedia.org/w/index.php?title=Spezial:Seiten_mit_ungesichteten_Versionen')
    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text()
    searchResult = re.search('Derzeit sind [0-9\\.]+ Änderungen ausstehend', text)
    assert searchResult is not None
    numberPart = searchResult.group(0)[13:-22].replace('.','')
    return int(numberPart)


def scrapeEditors():
    response = requests.get('https://de.wikipedia.org/wiki/Spezial:Sichtungsstatistik')
    soup = BeautifulSoup(response.text, 'html.parser')
    searchResult = re.search('Wikipedia hat momentan [0-9\\.]+ Benutzer mit Sichterrecht.', soup.get_text())
    assert searchResult is not None
    return int(searchResult.group(0)[23:-27].replace('.',''))


def save(site, text: str, force=False):
    page = pywikibot.Page(site, 'Benutzer:FNBot/FlaggedLag')
    if page.latest_revision["user"] != 'DerIchBot':
        telegram.send(f'Warnung: Benutzer:FNBot/FlaggedLag zuletzt von {page.latest_revision["user"]} bearbeitet.')
        if not force: return False
    if not optOut.isAllowed(page):
        if not force: return False
    page.text = text
    site.login()
    page.save(botflag=True, minor=False, summary='Bot: Update')


def getTrend():
    path = utils.getDataPath('unreviewedChanges.csv')
    entry: None | tuple[float,int] = None
    with io.open(path, 'r', encoding='utf8') as file:
        for line in csv.DictReader(file.readlines()):
            if line['unreviewedPages'] == '': continue
            timediff = (time.time() - int(line['timestamp'])) / 60 / 60 / 24
            if entry is not None and timediff < 14: return entry
            entry = (timediff, int(line['unreviewedPages']))
    if entry is None: return (1,0)
    return entry
        

def run(site):
    logging.info('download lag data')
    numberOfUnreviewedChanges = scrapeUnreviewedChanges()
    numberOfUnreviewedPages = getUnreviewedPages(site)
    numberOfEditors = scrapeEditors()
    diffToOldest = getOldest()
    pastEntry = getTrend()
    trend = (numberOfUnreviewedPages - pastEntry[1]) / pastEntry[0]
    utils.addToCsv('unreviewedChanges.csv', [utils.getTodayString(), int(time.time()), numberOfUnreviewedChanges, round(diffToOldest,2), numberOfUnreviewedPages])
    writeTemplate(site, numberOfUnreviewedPages, trend, diffToOldest, numberOfEditors)
    

def writeTemplate(site, numberOfUnreviewedPages: int, trend: float, diffToOldest: float, numberOfEditors: int):
    if not utils.checkLastUpdate('lag-template-update', 60*4)[0]: return
    logging.info('update lag template')
    page = pywikibot.Page(site, 'Benutzer:FNBot/FlaggedLag')
    if page.latest_revision["user"] != 'DerIchBot':
        telegram.send(f'Warnung: Benutzer:FNBot/FlaggedLag zuletzt von {page.latest_revision["user"]} bearbeitet.')
    else:
        page.text = f'{numberOfUnreviewedPages}|{int(round(trend))}|{int(round(diffToOldest))}|{numberOfEditors}'
        utils.savePage(page, 'update template', True)


def getNumberOfActiveUsers():
    PARAMS = {
        "action": "query",
        "meta": "siteinfo",
        "siprop": "statistics",
        "format": "json"
    }
    response = requests.get('https://de.wikipedia.org/w/api.php', params=PARAMS)
    data = response.json()
    return data["query"]['statistics']['activeusers']


def getOldest():
    PARAMS = {
        "action": "query",
        "list": "oldreviewedpages",
        "orlimit": "1",
        "format": "json",
        "orstart": "2000-01-01T00:00:00Z",
    }
    response = requests.get('https://de.wikipedia.org/w/api.php', params=PARAMS)
    data = response.json()
    timestamp = data['query']['oldreviewedpages'][0]['pending_since']
    diff = time.time() - time.mktime(time.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ'))
    return diff / 60 / 60 / 24


def getUnreviewedPages(site):
    orstart = "2000-01-01T00:00:00Z"
    oldreviewedpages = 0
    while orstart is not None:
        request = site.simple_request(
            action="query",
            list="oldreviewedpages",
            orlimit='max',
            orstart=orstart,
            format="json"
        )
        data = request.submit()
        oldreviewedpages += len(data.get("query", {}).get("oldreviewedpages", []))
        orstart = data.get("continue", {}).get("orstart")
    return oldreviewedpages

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - DEBUGGING - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site("de", "wikipedia")
    run(site)
    