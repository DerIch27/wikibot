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


def moveKatDiskFromDeletionDisk(site: Any, deletionDiskPage: pywikibot.Page, date: str, change: dict|None):
    wrongKats, rest = extractFromDeletionDisk(deletionDiskPage.text)
    if wrongKats != '': 
        telegram.send(f'Verschiebe von {deletionDiskPage.title()}')
        logging.info('Verschiebe Eintrag von Löschdiskussionsseite nach WikiProjekt Kategorien')
        logging.info(change)
        userLink = '???' if change is None else f'[[Benutzer:{change['user']}]]'
        katDiskLink = f'Wikipedia:WikiProjekt Kategorien/Diskussionen/{date[:4]}/{['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'][int(date[5:7])-1]}/{int(date[8:10])}'
        deletionDiskPage.text = rest
        if True: #utils.savePage(deletionDiskPage, f'Verschiebe Beitrag von {userLink} nach [[{katDiskLink}]]', botflag=True):
            katDiskPage = pywikibot.Page(site, katDiskLink)
            wrongKatsSplit = wrongKats.split('\n')
            katDiskSplit = katDiskPage.text.split('\n')
            i = 1
            while i <= len(wrongKatsSplit) and \
                i <= len(katDiskSplit) and \
                wrongKatsSplit[len(wrongKatsSplit)-i] == katDiskSplit[len(katDiskSplit)-i]: 
                    i += 1
            katDiskPage.text = '\n'.join(katDiskSplit[:len(katDiskSplit)-i] + wrongKatsSplit[:len(wrongKatsSplit)-i+1] + katDiskSplit[len(katDiskSplit)-i:])
            with io.open('logs/deletionToKatDisk.wiki', 'w', encoding='utf8') as file:
                file.write(katDiskPage.text)
            if not True: # utils.savePage(katDiskPage, f'Verschiebe Beitrag {f'[[Spezial:Diff/{change['revision']['new']}]] ' if change is not None else ''}von {userLink} aus [[{titel}]]', botflag=True):
                raise Exception('Incomplete move of discussion from deletion disk to kat-disk')
        return True
    return False