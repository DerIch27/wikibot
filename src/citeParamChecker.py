from typing import Literal, Any
import wikitextparser as wtp
import pywikibot
import telegram
import logging
import optOut
import utils
import time
import re


NOTIFICATION_PROBLEM_TYPES = '(Parameter (datum|abruf/zugriff)|Abrufdatum) liegt in der Zukunft\\.'


parseMonthDict = {'januar':1, 'jänner':1, 'january':1, 'jan':1,
                  'februar':2, 'february':2, 'feb':2,
                  'märz':3, 'march':3, 'mar':3, 'mrz': 3,
                  'april':4, 'apr':4,
                  'mai':5, 'may':5,
                  'juni':6, 'june':6, 'jun':6,
                  'juli':7, 'july':7, 'jul':7,
                  'august':8, 'aug':8,
                  'september':9, 'sep':9,
                  'oktober':10, 'october':10, 'oct':10, 'okt': 10,
                  'november':11, 'nov':11,
                  'dezember':12, 'december':12, 'dec':12, 'dez': 12}
monthRegex = '(' + '|'.join(parseMonthDict.keys()) + ')'


def formatTimestamp(year: str|int, month: str|int|None=None, day: str|int|None=None) -> str|Literal[False]:
    ''' Formatiert das eingegebene Datum im Format YYYY-MM-DD oder gibt False für ungültige Werte zurück. '''
    month = parseMonthDict[month.lower()] if (type(month) is str and month.lower() in parseMonthDict.keys()) else month
    try:
        year = int(year)
        month = int(month) if month is not None else None
        day = int(day) if day is not None else None
        assert (0 <= year <= 9999)
        assert (month is None) or (1 <= month <= 12)
        assert (day is None) or (1 <= day <= 31)
        assert not (day is not None and month is None)
    except ValueError:
        return False
    except AssertionError:
        return False
    return str(year).rjust(4,'0') + \
        ('' if month is None else '-' + str(month).rjust(2,'0')) + \
            ('' if day is None else '-' + str(day).rjust(2,'0'))


def parseWeirdDateFormats(date: str|None):
    ''' Wandelt möglichst alle Datumsformate, die die Vorlage Internetquelle akzeptiert, in Format YYYY-MM-DD um. Gibt False für ungültige Daten zurück. '''
    try:
        if type(date) is not str: return None
        date = date.lower()
        date = date.replace(' ', ' ') # &nbsp;
        if re.match('[0-9]{4}(-[0-9]{2}(-[0-9]{2}.*)?)?$', date):
            return formatTimestamp(*date[:10].split('-'))
        if re.match('[0-9]{4}-[0-9]{2}-[0-9]$', date):
            return formatTimestamp(*date.split('-'))
        if re.match('[0-9][0-9]?\\.[0-9][0-9]?\\.[0-9]{4}[a-z]?$', date): 
            return formatTimestamp(date.split('.')[2].rstrip('abcdefghijklmnopqrstuvwxyz'), date.split('.')[1], date.split('.')[0])
        if re.match('[0-9][0-9]?\\.? ' + monthRegex + '\\.? [0-9]{4}$', date):
            return formatTimestamp(date.split(' ')[2], date.split(' ')[1].rstrip('.'), date.split(' ')[0].rstrip('.'))
        if re.match(monthRegex + ' [0-9][0-9]?, [0-9]{4}$', date):
            return formatTimestamp(date.split(', ')[1], date.split(' ')[0], date.split(', ')[0].split(' ')[1])
        if re.match(monthRegex + '\\.? [0-9]{4}$', date):
            return formatTimestamp(date.split(' ')[1], date.split(' ')[0].rstrip('.'))
        if re.match('[0-9]{8}t[0-9]{4}$', date):
            return formatTimestamp(date[:4], date[4:6], date[6:8])
        return False
    except Exception as e:
        e.add_note(f'failed while parsing weird date "{date}"')
        raise e


def getNextMonth(datestring: str):
    ''' Verschiebt Datum der Form YYYY-MM-DD um einen Monat. '''
    year = int(datestring[:4])
    month = int(datestring[5:7])
    day = int(datestring[8:10])
    month += 1
    if month > 12: year += 1; month = 1
    maxDays = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1]
    day = min(day, maxDays)
    return formatTimestamp(year, month, day)


def getNextYear(datestring: str):
    ''' Verschiebt Datum der Form YYYY-MM-DD um einen Monat. '''
    year = int(datestring[:4])
    month = int(datestring[5:7])
    day = int(datestring[8:10])
    year += 1
    return formatTimestamp(year, month, day)


def getNextDay(datestring: str):
    ''' Verschiebt Datum der Form YYYY-MM-DD um einen Tag. '''
    year = int(datestring[:4])
    month = int(datestring[5:7])
    day = int(datestring[8:10])
    day += 1
    if day > [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1]: month += 1; day = 1
    if month > 12: year += 1; month = 1
    return formatTimestamp(year, month, day)


def templateOk(template: wtp.Template) -> tuple[Literal[True]|str, str|None]:
    ''' Prüft, ob Daten der Vorlagen Internetquelle, Literatur und Cite web ungültig sind oder in der Zukunft liegen '''
    templateName = template.name.strip()
    if templateName not in ['Internetquelle', 'Literatur', 'Cite web']:
        return True, None
    todayString = utils.getTodayString()
    abruf   = parseWeirdDateFormats(utils.findTemplateArg(template, {'Internetquelle': 'abruf',   'Literatur': 'Abruf',   'Cite web': 'access-date'}[templateName]))
    zugriff = parseWeirdDateFormats(utils.findTemplateArg(template, {'Internetquelle': 'zugriff', 'Literatur': 'Zugriff', 'Cite web': 'accessdate'}[templateName]))
    datum   = parseWeirdDateFormats(utils.findTemplateArg(template, {'Internetquelle': 'datum',   'Literatur': 'Datum',   'Cite web': 'date'}[templateName]))
    if abruf == False: return 'Abrufdatum ungültig.', abruf
    if zugriff == False: return 'Zugriffsdatum ungültig.', zugriff
    if datum == False: return 'Veröffentlichungsdatum ungültig.', datum
    if datum != None and datum > getNextYear(todayString): return "Parameter datum liegt in der Zukunft.", datum
    if abruf == None and zugriff == None and templateName == 'Internetquelle': return "Pflichtparameter abruf nicht gesetzt.", abruf
    if abruf == None and zugriff == None and templateName != 'Internetquelle': return True, None
    if abruf != None and zugriff != None: return "Parameter abruf und zugriff beide gesetzt.", abruf
    if abruf == None: abruf = zugriff
    if abruf > getNextDay(todayString): return "Parameter abruf/zugriff liegt in der Zukunft.", abruf
    if abruf < '2000': return "Parameter abruf/zugriff liegt weit in der Vergangenheit.", abruf
    return True, None


def archiveParamsOk(template: wtp.Template) -> Literal[True] | str:
    ''' Prüft, ob Parameter archiv-url und archiv-datum der Vorlagen Internetquelle und Cite web konsistent sind '''
    if template.name.strip() != 'Internetquelle': return True
    if utils.findTemplateArg(template, 'titel') == None: return 'Pflichtparameter titel nicht gesetzt.'
    archivurl   = utils.findTemplateArg(template, 'archiv-url')
    archivdatum = parseWeirdDateFormats(utils.findTemplateArg(template, 'archiv-datum'))
    abrufdatum  = parseWeirdDateFormats(utils.findTemplateArg(template, 'abruf'))
    datum       = parseWeirdDateFormats(utils.findTemplateArg(template, 'datum'))
    if archivdatum == False: return 'Archivierungsdatum ungültig.'
    if abrufdatum == False or datum == False: return True # wird von datesOk abgefangen
    if archivurl == None and archivdatum == None: return True
    if archivurl == None and archivdatum != None: return True # 'Parameter archiv-datum ohne archiv-url gesetzt.'
    if archivdatum != None: archivdatum = archivdatum.replace('-', '')
    if abrufdatum  != None: abrufdatum  = abrufdatum.replace('-', '')
    if datum       != None: datum       = datum.replace('-', '')
    if not re.match('^https://web.archive.org/web/[0-9]{14}/', archivurl): return True
    if archivurl[28:36] == archivdatum or archivurl[28:36] == abrufdatum or archivurl[28:36] == datum: return True
    if archivdatum == None: return True # "Kein Archivierungsdatum gesetzt."
    return "Falsches Archivierungsdatum gesetzt."

class Problem(dict):
    def __init__(self, titel: str|None=None, problemtyp: str|None=None, snippet: str|None=None, foundDate: str|None=None, assets: Any=None, dictionary: dict = {}):
        if not isinstance(titel,       str): titel       = dictionary.get('titel')
        if not isinstance(problemtyp,  str): problemtyp  = dictionary.get('problemtyp')
        if not isinstance(snippet,     str): snippet     = dictionary.get('snippet')
        if not isinstance(foundDate,   str): foundDate   = dictionary.get('foundDate')
        if assets is None:                   assets      = dictionary.get('assets')
        freshVersion = dictionary.get('freshVersion')
        revision     = dictionary.get('revision')
        user         = dictionary.get('user')
        assert isinstance(titel, str)
        assert isinstance(problemtyp, str)
        assert isinstance(snippet, str)
        assert isinstance(foundDate, str)
        assert isinstance(freshVersion, bool) or freshVersion is None
        assert isinstance(revision, int) or revision is None
        assert isinstance(user, str) or user is None
        self.titel        = titel
        self.problemtyp   = problemtyp
        self.foundDate    = foundDate
        self.snippet      = snippet
        self.freshVersion = freshVersion
        self.revision     = revision
        self.user         = user
        self.assets       = assets
    def __str__(self):
        return self.titel + ': ' + self.problemtyp + ' ' + self.snippet
    def __eq__(self, other):
        if type(other) != Problem: return False
        if self.titel != other.titel: return False
        if self.problemtyp != other.problemtyp: return False
        if self.snippet != other.snippet: return False
        return True
    def toDict(self):
        return {'titel': self.titel, 'problemtyp': self.problemtyp, 'snippet': self.snippet, 'foundDate': self.foundDate, 'revision': self.revision, 'freshVersion': self.freshVersion, 'assets': self.assets, 'user': self.user}


def loadAllProblems() -> list[Problem]:
    content: list[dict] = utils.loadJson('problems.json', [])
    return  [Problem(dictionary=problem) for problem in content]


def dumpAllProblems(allProblems: list[Problem]):
    content = [problem.toDict() for problem in allProblems]
    utils.dumpJson('problems.json', content)


def checkPageContent(titel: str, content: str, todayString: str):
    wiki = wtp.parse(content)
    for ref in wiki.get_tags('ref'):
        potentialDate = re.search('abgerufen (am|im) (([0-9][0-9]?\\.[0-9][0-9]?\\.[0-9]{3}[0-9]?[0-9]?)|(([0-9][0-9]?\\. )?' + monthRegex + ' [0-9]{3}[0-9]?[0-9]?))', ref.contents.lower())
        if potentialDate:
            date = parseWeirdDateFormats(potentialDate.group(2))
            if date is False:
                yield Problem(titel, 'Abrufdatum ungültig.', str(ref), todayString, date)
            elif date > getNextDay(todayString):
                yield Problem(titel, 'Abrufdatum liegt in der Zukunft.', str(ref), todayString, date)
    for template in wiki.templates:
        result, asset = templateOk(template)
        if True != result: 
            yield Problem(titel, result, str(template), todayString, asset)
        result = archiveParamsOk(template)
        if True != result: 
            yield Problem(titel, result, str(template), todayString)


def checkPage(site: Any, pagetitle: str, allProblems: list[Problem]):
    try:
        page = pywikibot.Page(site, pagetitle)
        content = page.get()
        for problem in checkPageContent(page.title(), content, utils.getTodayString()):
            if problem in allProblems: continue
            for rev in page.revisions(total=50):
                try:
                    if rev['parentid'] == 0: problem.revision = rev['revid']; break
                    if 'mw-manual-revert' in rev['tags'] or 'mw-rollback' in rev['tags']: continue
                    timestamp: pywikibot.Timestamp = rev['timestamp']
                    revTimestamp = str(timestamp.year).rjust(4,'0') + '-' + str(timestamp.month).rjust(2,'0') + '-' + str(timestamp.day).rjust(2,'0')
                    oldContent = page.getOldVersion(rev['parentid'])
                    if oldContent == None: break # Version verborgen
                    oldProblems = list(checkPageContent(page.title(), oldContent, revTimestamp))
                    if problem not in oldProblems:
                        problem.freshVersion = (oldProblems == [])
                        problem.revision = rev['revid']
                        problem.user = rev['user']
                        break
                except Exception as e:
                    e.add_note(f'failed while checking if problem already existed before revision {rev.get('revid')}')
                    raise e
            logging.info(f'Problem: {problem}')
            yield problem
    except pywikibot.exceptions.IsRedirectPageError:
        return
    except pywikibot.exceptions.NoPageError:
        return
    except pywikibot.exceptions.ServerError as e:
        telegram.handleServerError(e)
        return checkPage(site, pagetitle, allProblems)
    except Exception as e:
        e.add_note(f'failed while checking page {pagetitle}')
        raise e


def checkPagesInProblemList(site):
    allProblems = loadAllProblems()
    logging.debug(f'checking list of {len(allProblems)} problems ...')
    site.login()
    index = 0
    allPages = set()
    while index < len(allProblems):
        problem = allProblems[index]
        allPages.add(problem.titel)
        page = pywikibot.Page(site, problem.titel)
        try:
            content = page.text
        except pywikibot.exceptions.NoPageError:
            logging.debug(f'Artikel {problem.titel} verschwunden.')
            del allProblems[index]
            continue
        except pywikibot.exceptions.ServerError as e:
            telegram.handleServerError(e)
            continue
        if problem in checkPageContent(problem.titel, content, problem.foundDate): 
            index += 1
        else:
            logging.debug(f'Problem in {problem.titel} abgearbeitet.')
            del allProblems[index]
    for page in allPages:
        allProblems += checkPage(site, page, allProblems)
    dumpAllProblems(allProblems)


def updateWikilist():
    allProblems = loadAllProblems()
    datum = None
    titel = None
    wikitext = '{{/Info|' + str(len(allProblems)) + '|' + utils.getTodayString() + '}}\n\n'
    for problem in allProblems:
        if datum != problem.foundDate:
            wikitext += f'== {utils.formatDateFromDatestring(problem.foundDate)} ==\n\n'
        if titel != problem.titel or datum != problem.foundDate:
            wikitext += '{{Überschriftensimulation|3|Text=[[' + problem.titel + ']]}}\n'
        wikitext += f'{problem.problemtyp}{'' if problem.revision==None else f' ([[Spezial:Diff/{problem.revision}|Änderung]]{'' if problem.freshVersion else ' ???'})'}\n'
        wikitext += f'<pre>{problem.snippet}</pre>\n\n'
        datum = problem.foundDate
        titel = problem.titel
    site = pywikibot.Site('de', 'wikipedia')
    site.login()
    page = pywikibot.Page(site, 'Benutzer:DerIchBot/Wartungsliste')
    page.text = wikitext
    site.login()
    if optOut.isAllowed(page):
        page.save(botflag=True, minor=False, summary=(f'Bot: Aktualisiere Wartungsliste: {len(allProblems)} Einträge'))
    site.logout()


numberOfChanges = 0
numberOfNewProblems = 0
def checkPagefromRecentChanges(site: Any, pagetitle: str):
    global numberOfNewProblems
    global numberOfChanges
    numberOfChanges += 1
    allProblems = loadAllProblems()
    newProblems = checkPage(site, pagetitle, allProblems)
    for problem in newProblems:
        numberOfNewProblems += 1
        if re.match(NOTIFICATION_PROBLEM_TYPES, problem.problemtyp) and problem.freshVersion:
            futureWarnings: list[str] = utils.loadJson('futureWarningsPlanned.json', [])
            if problem.titel not in futureWarnings: futureWarnings.append(problem.titel)
            utils.dumpJson('futureWarningsPlanned.json', futureWarnings)
        if len(allProblems) < 300 and problem not in allProblems:
            allProblems.append(problem)
    dumpAllProblems(allProblems)
    if numberOfChanges >= 200:
        logging.info(f'Checked 200 changes and found {numberOfNewProblems} new problems.')
        numberOfNewProblems = 0
        numberOfChanges = 0


def sendPlannedNotifications(site):
    plannedNotifications: list[str] = utils.loadJson('futureWarningsPlanned.json', [])
    sentNotifications: dict[str, dict[str, str]] = utils.loadJson('futureWarningsSent.json', {})
    skippedNotifications: set[str] = set()
    outgoingNotifications: dict[str, set[str]] = {}
    for pagetitle in plannedNotifications:
        try:
            logging.info(f'check page "{pagetitle}" to notifications on cite param problems ...')
            try:
                timeSinceLastRevision: float = (time.time() - pywikibot.Page(site, pagetitle).latest_revision['timestamp'].timestamp()) / 3600
            except pywikibot.exceptions.NoPageError:
                logging.info(f'page "{pagetitle}" does not exist')
                continue
            logging.debug(f'time since latest revision on {pagetitle}: {timeSinceLastRevision:.2f}h')
            if timeSinceLastRevision < 6:
                logging.info(f'skip problem notification on "{pagetitle}" because latest revision is too new')
                skippedNotifications.add(pagetitle)
                continue
            for problem in checkPage(site, pagetitle, []):
                if not re.match(NOTIFICATION_PROBLEM_TYPES, problem.problemtyp): continue
                if not problem.freshVersion: continue
                if sentNotifications.get(problem.user) == None: sentNotifications[problem.user] = {}
                if sentNotifications[problem.user].get(pagetitle) != None: 
                    logging.info(f'skip notification of {problem.user} on "{pagetitle}" because already notified on {sentNotifications[problem.user][pagetitle]}')
                    continue
                logging.debug(problem.toDict())
                if outgoingNotifications.get(problem.user) == None: outgoingNotifications[problem.user] = set()
                datumstyp = 'Veröffentlichungsdatum' if problem.problemtyp.startswith('Parameter datum') else 'Abrufdatum'
                outgoingNotifications[problem.user].add(f'Du hast mit [[Spezial:Diff/{problem.revision}|dieser Änderung]] auf [[{pagetitle}]] den {utils.formatDateFromDatestring(problem.assets)} als {datumstyp} angegeben. Da dieses Datum in der Zukunft liegt, möchte ich dich bitten, deine Änderung nochmal auf Tippfehler zu überprüfen.')
                sentNotifications[problem.user][pagetitle] = utils.getTodayString()
        except Exception as e:
            e.add_note(f'failed while compiling notification on page "{pagetitle}"')
            raise e
    for user, messages in outgoingNotifications.items():
        messageList = list(messages)
        messageList[0] = messageList[0][0].lower() + messageList[0][1:]
        completeMessage = utils.formatUserInfo('Möglicherweise fehlerhafte Datumsangabe', user, '\n\n'.join(messageList))
        userdisk = pywikibot.Page(site, f'Benutzer Diskussion:{user}')
        userdisk.text += completeMessage
        if utils.savePage(userdisk, f'Informiere über potentiell fehlerhafte Datumsangabe', botflag=True):
            logging.info(f'Notify {user} about cite param problem')
        else:
            logging.info(f'do not notify {user} because saving failed')
    utils.dumpJson('futureWarningsPlanned.json', list(skippedNotifications))
    utils.dumpJson('futureWarningsSent.json', sentNotifications)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - CITE PARAMS - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site('de', 'wikipedia')
    sendPlannedNotifications(site)
    