from datetime import datetime
import wikitextparser as wtp
import deletionToKatdisk
import citeParamChecker
import pywikibot
import logging
import dotenv
import utils
import time
import re

dotenv.load_dotenv()

def handleDeletionDiscussionUpdate(site: pywikibot._BaseSite, titel: str, change: dict|None = None):
    assert re.match('^Wikipedia:Löschkandidaten/.', titel)
    date = citeParamChecker.parseWeirdDateFormats(titel[26:])
    if date is None or date is False or date < '2024-04-06': return
    deletionDiskPage = pywikibot.Page(site, titel) 
    if deletionToKatdisk.moveKatDiskFromDeletionDisk(site, deletionDiskPage, date, change):
        return handleDeletionDiscussionUpdate(site, titel, change)
    logs: dict[str, dict[str,dict]] = utils.loadJson(f'deletionInfo/{date}.json', {})
    if not utils.getBoolEnv('DELETION_NOTIFICATION_ENABLED', True):
        logging.info('skip handling deletion discussion because disabled in .env')
        return
    parsedDeletionDisk = parseDeletionDisk(deletionDiskPage)
    for pagetitle, userlinks in parsedDeletionDisk.items():
        try:
            if logs.get(pagetitle) != None: continue
            logging.info(f'Check page {pagetitle} on deletion disk {date} ...')
            page = pywikibot.Page(site, pagetitle)
            pagetitle = page.title()
            allTitles, mainAuthors = parseRevisionHistory(page)
            if len(allTitles) > 1:
                logging.debug(f'found multiple titles: {' und '.join([f'"{i}"' for i in allTitles])}')
            if any([logs.get(i)!=None for i in allTitles]): 
                if logs.get(pagetitle) == None:
                    logs[pagetitle] = dict()
                continue
            for author in mainAuthors:
                if not mainAuthors[author]['major']: continue
                if re.match(utils.ipRegex, author): logging.info(f'do not notify {author} because he is ip'); continue
                if author in userlinks: logging.info(f'do not notify {author} because already on deletion disk'); continue
                if author in utils.loadJson('opt-out-ld.json', []): logging.info(f'do not notify {author} because of opt out'); continue
                if utils.isBlockedForInfinity(site, author): logging.info(f'do not notify {author} because he is blocked'); continue
                mainAuthors[author]['notified'] = int(time.time())
                logging.info(f'planned notification of {author}')
            logs[pagetitle] = dict(sortMainAuthors(mainAuthors)[-5:])
            utils.dumpJson(f'deletionInfo/{date}.json', logs)
        except Exception as e:
            e.add_note(f'failed while checking page {pagetitle} on deletion disk')
            raise e
    sendDeletionNotifications(site, date)

NOTIFICATION_DELAY = 60*15 # 15min
def sendDeletionNotifications(site, date: str=datetime.now().strftime('%Y-%m-%d')):
    if not utils.getBoolEnv('DELETION_NOTIFICATION_ENABLED', True):
        logging.info('skip sending deletion notifications because disabled in .env')
        return
    logs: dict[str, dict[str,dict]] = utils.loadJson(f'deletionInfo/{date}.json', {})
    deletionDiskTitle = 'Wikipedia:Löschkandidaten/' + utils.formatDate(int(date[8:10]), date[5:7], date[0:4])
    deletionDiskPage = pywikibot.Page(site, deletionDiskTitle)
    parsedDeletionDisk: None|dict[str,dict] = None
    for pagetitle, mainAuthors in logs.items():
        for author in mainAuthors:
            if type(mainAuthors[author].get('notified')) is not int: continue
            if logs[pagetitle][author]['notified'] + NOTIFICATION_DELAY > time.time():
                logging.info(f'wait with notification of {author}')
                continue
            if parsedDeletionDisk is None:
                parsedDeletionDisk = parseDeletionDisk(deletionDiskPage)
            assert parsedDeletionDisk is not None
            if pagetitle not in parsedDeletionDisk.keys():
                logging.warning(f'do not notify {author} because {pagetitle} not found anymore')
                logs[pagetitle][author]['notified'] = False
                continue
            if author in parsedDeletionDisk[pagetitle]:
                logging.info(f'do not notify {author} because already on deletion disk')
                logs[pagetitle][author]['notified'] = False
                continue
            userdisk = pywikibot.Page(site, f'Benutzer Diskussion:{author}')
            allTitles, mainAuthors = parseRevisionHistory(pywikibot.Page(site, pagetitle))
            if checkForExistingInfoOnDisk(userdisk, allTitles): 
                logging.info(f'do not notify {author} because already notified on userdisk')
                logs[pagetitle][author]['notified'] = False 
                continue
            if not pywikibot.Page(site, pagetitle).exists(): 
                logging.info(f'do not notify {author} because article has been deleted')
                logs[pagetitle][author]['notified'] = False 
                continue
            renderedInfo = infoTemplate(author, pagetitle, deletionDiskTitle)
            userdisk.text += renderedInfo
            if not utils.savePage(userdisk, f'Informiere über Löschantrag zu [[{pagetitle}]].', botflag=False):
                logging.info(f'do not notify {author} because saving failed')
                logs[pagetitle][author]['notified'] = False 
                continue
            logs[pagetitle][author]['notified'] = True
            logging.info(f'Notify {author} about deletion disk of {pagetitle}')
    utils.dumpJson(f'deletionInfo/{date}.json', logs)


def parseDeletionDisk(page: pywikibot.Page):
    result: dict[str,set[str]] = {} # {pagetitle: userlinks}
    content = page.text
    parsed = wtp.parse(content)
    for sec in parsed.sections:
        if sec.level != 2: continue
        titellinks = wtp.parse(sec.title).wikilinks
        if len(titellinks) == 0: continue
        pagetitle = titellinks[0].target
        if re.search('\\((erl\\., )?(LAE|LAZ)\\)', sec.title): logging.debug(f'ignore {pagetitle} because LAE/LAZ'); continue
        if re.search('\\((erl\\., )?SLA\\)', sec.title): logging.debug(f'ignore {pagetitle} because SLA'); continue
        if re.search('\\((bleibt|gelöscht|erl.)\\)', sec.title): logging.debug(f'ignore {pagetitle} because ended'); continue
        userlinks = utils.extractUserLinks(sec)
        result[pagetitle] = userlinks
    return result

def sortMainAuthors(authors: dict[str,dict]):
    return sorted(authors.items(), key=lambda autor: autor[1]['score']+1e10*autor[1]['creator'])

def parseRevisionHistory(page: pywikibot.Page) -> tuple[set[str], dict[str,dict]]:
    logging.info(f'parse revision history of page {page.title()} ...')
    try:
        allTitles: set[str] = {page.title()}
        authors: dict[str,dict] = {}
        pagesize = 0
        for rev in page.revisions(reverse=True):
            if re.search('verschob die Seite \\[\\[(.)*\\]\\] nach \\[\\[(.)*\\]\\]', rev['comment']):
                for link in wtp.parse(rev['comment']).wikilinks:
                    allTitles.add(link.target)
            user = rev['user'][3:] if rev['user'].startswith('de>') else rev['user']
            if authors.get(user) == None:
                if re.match(interwikiRegex, user): continue
                authors[user] = {'score': 0, 'major': False, 'notified': False, 'creator': False}
            if rev['parentid'] == 0:
                authors[user]['major'] = True
                authors[user]['creator'] = True
            sizediff = max(0, rev['size']-pagesize); pagesize = rev['size']
            authors[user]['score'] += (sizediff**0.5)/10
            authors[user]['score'] += 1/3 if rev['minor'] else 1
        for autor in authors:
            if authors[autor]['score'] < 3: continue
            if authors[autor]['score'] >= max([author['score'] for author in authors.values()]):
                authors[autor]['major'] = True
            if authors[autor]['score'] >= sum([author['score'] for author in authors.values()])/3:
                authors[autor]['major'] = True
        return allTitles, authors
    except pywikibot.exceptions.NoPageError:
        logging.info('page not found :-(')
        return set(), dict()
    
def checkForExistingInfoOnDisk(disk: pywikibot.Page, pagetitles: set[str]):
    try:
        parsed = wtp.parse(disk.text)
        for pagetitle in pagetitles:
            for sec in parsed.sections:
                if sec.title is None: continue
                if (pagetitle not in sec.title) and (wtp.parse(pagetitle).plain_text() not in wtp.parse(sec.title).plain_text()): continue
                if sec.title.startswith(' Hinweis zur Löschung der Seite') and ('Beste Grüße vom --[[Benutzer:TabellenBot|TabellenBot]] • [[Benutzer Diskussion:Kuebi|Diskussion]]' in sec.contents): continue
                if sec.title.startswith(' Herzlich willkommen in der Wikipedia, ') and (sec.contents.count('lösch') <= 1) and (sec.contents.startswith('Ich habe gesehen, dass [[Wikipedia:Warum sich hier alle duzen|du]] dich kürzlich hier angemeldet hast, und möchte dir ein paar Tipps geben, damit du dich in der Wikipedia möglichst schnell zurechtfindest:')): continue
                if 'lösch' in sec.contents.lower(): return True
        return False
    except pywikibot.exceptions.InvalidTitleError:
        logging.warning(f'got invalid title while checking for existing info on disk')
        return False

interwikiRegex = re.compile('^[a-z][a-z]>')  

def infoTemplate(username: str, pagetitle: str, deletionDiskTitle: str):
    sectiontitle = pagetitle.replace(' ','_')
    if pagetitle.startswith(':Vorlage') or pagetitle.startswith('Vorlage:'):
        return utils.formatUserInfo(f'[[{pagetitle}]]', username, f"""\
gegen die im Betreff genannte, von dir angelegte oder erheblich bearbeitete Vorlage wurde ein Löschantrag gestellt (nicht von mir). Bitte entnimm den Grund dafür der '''[[{deletionDiskTitle}#{sectiontitle[1:]}|Löschdiskussion]]'''. Ob die Vorlage tatsächlich gelöscht wird, wird sich gemäß unserer [[WP:Löschregeln|Löschregeln]] im Laufe der siebentägigen Löschdiskussion entscheiden. 

Du bist herzlich eingeladen, dich an der [[{deletionDiskTitle}#{pagetitle.replace(' ','_')}|Löschdiskussion]] zu beteiligen. Wenn du möchtest, dass die Vorlage behalten wird, kannst du dort die Argumente, die für eine Löschung sprechen, entkräften. Du kannst auch während der Löschdiskussion Verbesserungen an der Vorlage vornehmen.

Da bei Wikipedia jeder Löschanträge stellen darf, sind manche Löschanträge auch offensichtlich unbegründet; solche Anträge kannst du ignorieren.

Vielleicht fühlst du dich durch den Löschantrag vor den Kopf gestoßen, weil durch den Antrag die Arbeit, die Du in den Artikel gesteckt hast, nicht gewürdigt wird. [[WP:Sei tapfer|Sei tapfer]] und [[Wikipedia:Wikiquette|bleibe dennoch freundlich]]. Der andere meint es [[WP:Geh von guten Absichten aus|vermutlich auch gut]].""", ['Benutzer:Xqbot/Opt-out:LD-Hinweis'])
    elif pagetitle.startswith('Benutzer:'):
        return utils.formatUserInfo(f'[[{pagetitle}]]', username, f"""\
gegen die im Betreff genannte, von dir angelegte oder erheblich bearbeitete Benutzerseite wurde ein Löschantrag gestellt (nicht von mir). Bitte entnimm den Grund dafür der '''[[{deletionDiskTitle}#{sectiontitle[1:]}|Löschdiskussion]]'''. Ob die Seite tatsächlich gelöscht wird, wird sich gemäß unserer [[WP:Löschregeln|Löschregeln]] im Laufe der siebentägigen Löschdiskussion entscheiden. 

Du bist herzlich eingeladen, dich an der [[{deletionDiskTitle}#{pagetitle.replace(' ','_')}|Löschdiskussion]] zu beteiligen. Da bei Wikipedia jeder Löschanträge stellen darf, sind manche Löschanträge auch offensichtlich unbegründet; solche Anträge kannst du ignorieren.""", ['Benutzer:Xqbot/Opt-out:LD-Hinweis'])
    else:
        return utils.formatUserInfo(f'[[{pagetitle}]]', username, f"""\
gegen den im Betreff genannten, von dir angelegten oder erheblich bearbeiteten Artikel wurde ein Löschantrag gestellt (nicht von mir). Bitte entnimm den Grund dafür der '''[[{deletionDiskTitle}#{sectiontitle}|Löschdiskussion]]'''. Ob der Artikel tatsächlich gelöscht wird, wird sich gemäß unserer [[WP:Löschregeln|Löschregeln]] im Laufe der siebentägigen Löschdiskussion entscheiden. In [[Wikipedia:Schnelllöschantrag#Artikellöschungen|den hier nachzulesenden Fällen]] kann eine Seite auch sofort gelöscht werden.

Du bist herzlich eingeladen, dich an der [[{deletionDiskTitle}#{pagetitle.replace(' ','_')}|Löschdiskussion]] zu beteiligen. Wenn du möchtest, dass der Artikel behalten wird, kannst du dort die Argumente, die für eine Löschung sprechen, entkräften, indem du dich beispielsweise zur [[Wikipedia:Relevanzkriterien|enzyklopädischen Relevanz]] des Artikels äußerst. Du kannst auch während der Löschdiskussion Artikelverbesserungen vornehmen, die die Relevanz besser erkennen lassen und die [[Wikipedia:Artikel#Mindestanforderungen|Mindestqualität]] sichern.

Da bei Wikipedia jeder Löschanträge stellen darf, sind manche Löschanträge auch offensichtlich unbegründet; solche Anträge kannst du ignorieren.

Vielleicht fühlst du dich durch den Löschantrag vor den Kopf gestoßen, weil durch den Antrag die Arbeit, die Du in den Artikel gesteckt hast, nicht gewürdigt wird. [[WP:Sei tapfer|Sei tapfer]] und [[Wikipedia:Wikiquette|bleibe dennoch freundlich]]. Der andere meint es [[WP:Geh von guten Absichten aus|vermutlich auch gut]].""", ['Benutzer:Xqbot/Opt-out:LD-Hinweis'])
        
if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - DEBUGGING - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site('de', 'wikipedia')
    site.login()
    handleDeletionDiscussionUpdate(site, 'Wikipedia:Löschkandidaten/18. April 2024')
