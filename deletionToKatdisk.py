from typing import Any
import wikitextparser as wtp
import pywikibot
import telegram
import logging
import utils
import re
import io

def extractFromDeletionDisk(content: str) -> tuple[str,str]: # (Kategorien, Rest)
    parsed = wtp.parse(content)
    result = ''
    ok = False
    for sec in parsed.sections:
        if sec.level == 1 and (sec.title or '').strip() == 'Benutzerseiten': ok = True; break
        if sec.title != None:
            result += '\n' + sec.level*'=' + ' ' + sec.title + ' ' + sec.level*'=' + '\n\n' + sec.contents
            del sec.title
            sec.contents = ''
        else:
            split = sec.contents.strip().split('\n')
            newContents = []
            if len(split)>0 and re.match('^{{Löschkandidatenseite|erl=.*}}$', split[0]):
                newContents.append(split[0])
                split.pop(0)
            while len(split)>0 and split[0].strip() == '':
                split.pop(0)
            if len(split)>0 and re.match('^<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren. -->', split[0]):
                newContents.append(split[0])
                split.pop(0)
            sec.contents = '\n'.join(newContents) + '\n\n'
            result += '\n'.join(split)
    if not ok:
        raise Exception(f'Keine Überschrift Benutzerdiskussionsseiten auf Löschkandidatenseite gefunden.')
    return result.strip().strip().replace('\n<span></span>\n','\n').replace('\n\n\n', '\n\n'), parsed.string.strip().replace('\n\n\n', '\n\n')


def moveKatDiskFromDeletionDisk(site: Any, deletionDiskPage: pywikibot.Page, date: str, change: dict|None, force: bool=False):
    wrongKats, rest = extractFromDeletionDisk(deletionDiskPage.text)
    if wrongKats != '': 
        moveHistory: dict[str, dict] = utils.loadJson('data/moveHistory.json', {})
        logging.debug(f'wrong kats hash: {hash(wrongKats)}')
        if str(hash(wrongKats)) in moveHistory:
            if force:
                logging.info('handle wrong kats although not new')
            else:
                logging.info('do not handle wrong cats because already in history')
                return False
        if change is not None:
            moveHistory[str(hash(wrongKats))] = {'comment': change['comment'], 'timestamp': change['timestamp'], 'diff': change['revision']['new']}
            utils.dumpJson('data/moveHistory.json', moveHistory)
        telegram.send(f'Verschiebe von {deletionDiskPage.title()}{'' if change is None else '\n'+telegram.difflink(change)}')
        logging.info('Verschiebe Eintrag von Löschdiskussionsseite nach WikiProjekt Kategorien')
        logging.info(change)
        userLink = '???' if change is None else f'[[Benutzer:{change['user']}]]'
        katDiskLink = f'Wikipedia:WikiProjekt Kategorien/Diskussionen/{date[:4]}/{['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'][int(date[5:7])-1]}/{int(date[8:10])}'
        deletionDiskPage.text = rest
        if True: # utils.savePage(deletionDiskPage, f'Verschiebe Beitrag von {userLink} nach [[{katDiskLink}]]', botflag=True):
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
            if not True: # utils.savePage(katDiskPage, f'Verschiebe Beitrag {f'[[Spezial:Diff/{change['revision']['new']}]] ' if change is not None else ''}von {userLink} aus [[{deletionDisk.title()}]]', botflag=True):
                raise Exception('Incomplete move of discussion from deletion disk to kat-disk')
        return True
    return False

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - DEBUGGING - %(message)s', level=logging.DEBUG)
    site = pywikibot.Site('de', 'wikipedia')
    site.login()
    deletionDisk = pywikibot.Page(site, 'Wikipedia:Löschkandidaten/13. Juni 2024')
    moveKatDiskFromDeletionDisk(site, deletionDisk, '2024-06-13', None, force=True)
