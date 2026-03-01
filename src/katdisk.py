import wikitextparser as wtp
from typing import Literal
import citeParamChecker
import pywikibot
import telegram
import logging
import utils
import time
import re

NOTIFICATION_DELAY = 60*15 # 15min
def handleKatDiscussionUpdate(site: pywikibot._BaseSite, titel: str):
    date = titel.split('/')[2] + '-' + str(citeParamChecker.parseMonthDict[titel.split('/')[3].lower()]).rjust(2,'0') + '-' + titel.split('/')[4].rjust(2,'0')
    if date < '2024-04-18': return
    logs: dict[str, int|str|Literal[False]] = utils.loadJson(f'katDiskInfo/{date}.json', {})
    diskPage = pywikibot.Page(site, titel)
    parsedDisk = parseKatDisk(diskPage)
    outstandingNotifications: tuple[dict[str,list[str]], dict[str,list[str]]] = ({}, {}) # (suspended notifications, necessary notifications)
    for kattitle, userlinks in parsedDisk.items():
        logstate = logs.get(kattitle)
        if logstate == None: 
            logs[kattitle] = int(time.time())
        elif (type(logstate) == int) and logstate+NOTIFICATION_DELAY < time.time():
            logs[kattitle] = False
        else:
            logging.debug(f'skip {kattitle} because already handled with logstate {logstate}')
            continue
        logging.info(f'Check category {kattitle} on category disk {date} ... (logstate: {logstate})')
        creator = getPageCreator(pywikibot.Page(site, kattitle))
        if creator is None: logging.info(f'no creator of {kattitle} found'); continue
        if re.match(ipRegex, creator): logging.info(f'do not notify {creator} because he is ip'); continue
        if creator in userlinks: logging.info(f'do not notify {creator} because already on kat-disk'); continue
        if utils.isBlockedForInfinity(site, creator): logging.info(f'do not notify {creator} because he is blocked'); continue 
        if outstandingNotifications[int(logs[kattitle]==False)].get(creator) == None: outstandingNotifications[int(logs[kattitle]==False)][creator] = []
        outstandingNotifications[int(logs[kattitle]==False)][creator].append(kattitle)
    for creator in outstandingNotifications[1]:
        kattitles = outstandingNotifications[1][creator] + (outstandingNotifications[0].get(creator) or [])
        if notify(site, creator, kattitles, titel):
            for kat in kattitles:
                logs[kat] = creator
    utils.dumpJson(f'katDiskInfo/{date}.json', logs)


def handleKatDiscussionToday(site):
    date = time.localtime()
    diskTitle = f'Wikipedia:WikiProjekt Kategorien/Diskussionen/{date.tm_year}/{['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'][date.tm_mon-1]}/{date.tm_mday}'
    handleKatDiscussionUpdate(site, diskTitle)


def notify(site, creator: str, kattitles: list[str], diskTitle: str):
    userdisk = pywikibot.Page(site, f'Benutzer Diskussion:{creator}')
    renderedInfo = infoTemplate(creator, kattitles, diskTitle)
    userdisk.text += renderedInfo
    if utils.savePage(userdisk, f'Informiere über Diskussion zu {' und '.join([f'[[:{i}]]' for i in kattitles])}.', botflag=False):
        logging.info(f'Notify {creator} about kat-disk of {' and '.join(kattitles)}')
        return True
    logging.info(f'do not notify {creator} because saving failed')
    return False


def parseKatDisk(page: pywikibot.Page) -> dict[str,set[str]]:
    result: dict[str,set[str]] = {} # {pagetitle: userlinks}
    try:
        content = page.text
    except pywikibot.exceptions.ServerError as e:
        telegram.handleServerError(e)
        return parseKatDisk(page)
    else:
        parsed = wtp.parse(content)
        for sec in parsed.sections:
            if sec.level != 2: continue
            titellinks = wtp.parse(sec.title).wikilinks
            for link in titellinks:
                if not link.target.startswith(':Kategorie:'): continue
                kattitle = link.target[1:]
                userlinks = utils.extractUserLinks(sec)
                result[kattitle] = userlinks
        return result

def getPageCreator(page: pywikibot.Page) -> str|None:
    try:
        for rev in page.revisions(reverse=True, total=1):
            return rev['user']
        return None
    except pywikibot.exceptions.InvalidTitleError:
        return None
    except pywikibot.exceptions.NoPageError:
        return None

ipRegex = re.compile('^(((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])|((([0-9a-fA-F]){1,4})\\:){7}([0-9a-fA-F]){1,4})$') 

def infoTemplate(username: str, kattitles: list[str], diskTitle: str):
    assert len(kattitles) > 0
    sectiontitle = f'[[:{kattitles[0]}]]{' und '+str(len(kattitles)-1)+' weitere' if len(kattitles)>1 else ''}'
    return utils.formatUserInfo(sectiontitle, username, f'zu {len(kattitles) if len(kattitles)>1 else 'der im Betreff genannten und'} von dir erstellten Kategorie{'n' if len(kattitles)>1 else ''} wurde auf [[{diskTitle}]] eine Diskussion begonnen. Du bist herzlich eingeladen, dich an der Diskussion zu beteiligen.')

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - DEBUGGING - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site('de', 'wikipedia')
    handleKatDiscussionToday(site)