from datetime import datetime
import wikitextparser as wtp
from typing import Any
import citeParamChecker
import pywikibot
import telegram
import logging
import utils
import json
import re
import io

def extractFromDeletionDisk(content: str) -> tuple[str,str]: # (Kategorien, Rest)
    parsed = wtp.parse(content)
    result = ''
    ok = False
    for sec in parsed.get_sections(include_subsections=False):
        if sec.level == 1 and (sec.title or '').strip() == 'Benutzerseiten': ok = True; break
        if sec.title != None:
            result += '\n' + sec.level*'=' + ' ' + sec.title + ' ' + sec.level*'=' + '\n\n'
            del sec.title
        split = sec.contents.strip().split('\n')
        newDeletionDiskContents = []
        if len(split)>0 and re.match('^{{Löschkandidatenseite|erl=.*}}$', split[0]):
            newDeletionDiskContents.append(split[0])
            split.pop(0)
        while len(split)>0 and split[0].strip() == '':
            split.pop(0)
        if '<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren. -->' in split:
            newDeletionDiskContents.append('<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren. -->')
            split.remove('<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren. -->')
        if len(newDeletionDiskContents) == 0:
            sec.contents = ''
        else:
            sec.contents = '\n'.join(newDeletionDiskContents) + '\n\n'
        result += '\n'.join(split)
    if not ok:
        raise Exception(f'Keine Überschrift Benutzerdiskussionsseiten auf Löschkandidatenseite gefunden.')
    newContentsString = result.strip().strip()\
        .replace('\n<span></span>\n','\n')\
        .replace('\n\n\n', '\n\n')\
        .replace(r"""<span class="wp_boppel noviewer" aria-hidden="true" role="presentation">[[Datei:Symbol support vote.svg|15px|link=]]&nbsp;</span>'''Pro'''""", "{{Pro}}")
    return newContentsString, parsed.string.strip().replace('\n\n\n', '\n\n')


def moveKatDiskFromDeletionDisk(site: Any, deletionDiskPage: pywikibot.Page, change: dict|None, force: bool=False):
    date = citeParamChecker.parseWeirdDateFormats(deletionDiskPage.title()[26:])
    wrongKats, rest = extractFromDeletionDisk(deletionDiskPage.text)
    if wrongKats != '': 
        moveHistory: dict[str, dict] = utils.loadJson('moveHistory.json', {})
        logging.debug(f'wrong kats hash: {hash(wrongKats)}')
        if str(hash(wrongKats)) in moveHistory:
            if force:
                logging.info('handle wrong kats although not new')
            else:
                logging.info('do not handle wrong cats because already in history')
                return False
        if change is not None:
            moveHistory[str(hash(wrongKats))] = {'comment': change['comment'], 
                                                 'timestamp': change['timestamp'], 
                                                 'timestring': datetime.fromtimestamp(change['timestamp']).strftime('%d.%m.%Y %H:%M'), 
                                                 'diff': change['revision']['new']}
            utils.dumpJson('moveHistory.json', moveHistory)
        logging.info('Verschiebe Eintrag von Löschdiskussionsseite nach WikiProjekt Kategorien')
        logging.info(change)
        userLink = '???' if change is None else f'[[Benutzer:{change['user']}]]'
        katDiskLink = f'Wikipedia:WikiProjekt Kategorien/Diskussionen/{date[:4]}/{['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'][int(date[5:7])-1]}/{int(date[8:10])}'
        deletionDiskPage.text = rest
        katDiskPage = pywikibot.Page(site, katDiskLink)
        wrongKatsSplit = wrongKats.split('\n')
        katDiskSplit = katDiskPage.text.split('\n')
        i = 1
        while i <= len(wrongKatsSplit) and \
            i <= len(katDiskSplit) and \
            wrongKatsSplit[len(wrongKatsSplit)-i] == katDiskSplit[len(katDiskSplit)-i]: 
                i += 1
        katDiskPage.text = '\n'.join(katDiskSplit[:len(katDiskSplit)-i+1] + ['\n'.join(wrongKatsSplit[:len(wrongKatsSplit)-i+1]) + ' <small>(verschoben vom [[Benutzer:DerIchBot|DerIchBot]])</small>'] + katDiskSplit[len(katDiskSplit)-i+1:])
        with io.open('logs/deletionToKatDisk.wiki', 'w', encoding='utf8') as file:
            file.write(katDiskPage.text)
        if force or (change is not None and checkCommentForAnswer(change['comment'], katDiskPage.text)):
            if utils.savePage(deletionDiskPage, f'Verschiebe Beitrag von {userLink} nach [[{katDiskLink}]]', botflag=True):
                if not utils.savePage(katDiskPage, f'Verschiebe Beitrag {f'[[Spezial:Diff/{change['revision']['new']}]] ' if change is not None else ''}von {userLink} aus [[{deletionDiskPage.title()}]]', botflag=True):
                    raise Exception('Incomplete move of discussion from deletion disk to kat-disk')
            return True
            telegram.send(f'Verschiebe Eintrag in {deletionDiskPage.title()}{'' if change is None else f' ({telegram.difflink(change)})'}')
        else:
            telegram.send(f'Falscher Eintrag in {deletionDiskPage.title()}{'' if change is None else f' ({telegram.difflink(change)})'}')
    return False

def checkCommentForAnswer(comment: str, katDiskContent: str):
    parsedComment = re.match('/\\* ((.)*) \\*/', comment)
    if parsedComment is None: return False
    sectionTitles: list[str] = []
    for sec in wtp.parse(katDiskContent).get_sections():
        if sec.title is None: continue
        sectionTitles.append(wtp.parse(sec.title).plain_text().replace(':Kategorie', 'Kategorie').strip())
    logging.info(f'check deletion disk comment "{comment}" against {json.dumps(sectionTitles, ensure_ascii=False)}')
    return parsedComment[1] in sectionTitles

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - DEBUGGING - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site('de', 'wikipedia')
    deletionDisk = pywikibot.Page(site, 'Wikipedia:Löschkandidaten/24. August 2025')
    moveKatDiskFromDeletionDisk(site, deletionDisk, None, force=False)
