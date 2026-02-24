import pywikibot
import telegram
import requests
import typing
import optOut
import utils
import json
import bs4
import re

disciplines = {'2x2x2': '2x2x2 Cube', 
               '3x3x3': '3x3x3 Cube', 
               '3x3x3blind': '3x3x3 Blindfolded', 
               '3x3x3onehanded': '3x3x3 One-Handed', 
               '3x3x3withfeet': '3x3x3 With Feet', 
               '3x3x3multiblind': '3x3x3 Multi-Blind', 
               '3x3x3fewestmoves': '3x3x3 Fewest Moves', 
               '4x4x4': '4x4x4 Cube', 
               '4x4x4blind': '4x4x4 Blindfolded', 
               '5x5x5': '5x5x5 Cube', 
               '5x5x5blind': '5x5x5 Blindfolded', 
               '6x6x6': '6x6x6 Cube', 
               '7x7x7': '7x7x7 Cube', 
               'Pyraminx': 'Pyraminx', 
               'Megaminx': 'Megaminx', 
               'Skewb': 'Skewb', 
               'Square1': 'Square-1', 
               'Clock': 'Clock'}

eventNameById = {
    '333': '3x3x3 Cube',
    '222': '2x2x2 Cube',
    '444': '4x4x4 Cube',
    '555': '5x5x5 Cube',
    '666': '6x6x6 Cube',
    '777': '7x7x7 Cube',
    '333bf': '3x3x3 Blindfolded',
    '333fm': '3x3x3 Fewest Moves',
    '333oh': '3x3x3 One-Handed',
    'clock': 'Clock',
    'minx': 'Megaminx',
    'pyram': 'Pyraminx',
    'skewb': 'Skewb',
    'sq1': 'Square-1',
    '444bf': '4x4x4 Blindfolded',
    '555bf': '5x5x5 Blindfolded',
    '333mbf': '3x3x3 Multi-Blind',
    '333ft': '3x3x3 With Feet',
    'magic': 'Magic',
    'mmagic': 'Master Magic',
    '333mbo': '3x3x3 Multi-Blind Old Style'
}

def differentLinks(name: str):
    links: dict[str, str] = dict()
    if links.get(name) != None:
        return links.get(name)
    if re.search(' \\(.+\\)$', name):
        return re.sub(' \\(.+\\)$', '', name)

def editWiki(data: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]], 
             parser: typing.Callable[[list[dict[str, str]], str], str], 
             changedDisciplines: list[str], 
             pagename: str, 
             forcedSummary: str|None = None):
    site = pywikibot.Site('de', 'wikipedia')
    page = pywikibot.Page(site, pagename)
    if page.latest_revision["user"] != 'DerIchBot':
        telegram.send(f'Warnung: {pagename} zuletzt von {page.latest_revision["user"]} bearbeitet.')
    newText = generatePage(data, parser)
    if newText != page.text:
        print('Update page ...')
        page.text = newText
        summary = f'Bot: Aktualisiere Rekord{"e" if len(changedDisciplines)>1 else ""} für {" und ".join(changedDisciplines)}.'
        site.login()
        assert site.logged_in()
        if optOut.isAllowed(page):
            page.save(botflag=True, minor=False, summary=(summary if forcedSummary==None else f'Bot: {forcedSummary}'))
    else:
        print('Page content did not change.')

def generatePage(data: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]], parser: typing.Callable[[list[dict[str, str]], str], str]):
    return '<onlyinclude><includeonly><!--\n-->{{#switch: {{{2}}}<!--\n  -->| Single = {{#switch: {{{1}}}' + ''.join(['<!--\n    -->| '+i.ljust(16)+' = '+parser(data[disciplines[i]][0], i) for i in disciplines.keys()]) + '<!--\n    -->| #default         = ' + parseError('Parameter 1 ungültig!') + ' }}<!--\n  -->| Average = {{#switch: {{{1}}}' + ''.join(['<!--\n    -->| '+i.ljust(16)+' = '+parser(data[disciplines[i]][1], i) for i in disciplines.keys()]) + '<!--\n    -->| #default         = ' + parseError('Parameter 1 ungültig!') + ' }}<!--\n  -->| #default = ' + parseError('Parameter 2 ungültig!') + '<!--\n-->}}</includeonly></onlyinclude>\n\n{{Dokumentation}}'

def parseSwitch(data: list[str], key: int):
    data = (['', '', '', ''] + data)[-4:]
    return '{{#switch: {{{' + str(key) + '}}} |4=' + data[0] + ' |3='+ data[1] + ' |2='+ data[2] + ' |#default=' + data[3] + '}}'

months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
def parseDates(data: list[dict[str, str]], discipline: str):
    if data == []: return parseError('Keine Daten für diese Parameterkombination.')
    dates = [i['date'] for i in data]
    dates = [utils.formatDate(i[4:6], months.index(i[0:3])+1, i[8:12]) for i in dates]
    return parseSwitch(dates, 3)

def parseNames(data: list[dict[str, str]], discipline: str):
    if data == []: return parseError('Keine Daten für diese Parameterkombination.')
    months = {'Jan': 'Januar', 'Feb': 'Februar', 'Mar': 'März', 'Apr': 'April', 'May': 'Mai', 'Jun': 'Juni',
              'Jul': 'Juli', 'Aug': 'August', 'Sep': 'September', 'Oct': 'Oktober', 'Nov': 'November', 'Dec': 'Dezember'}
    names = [i['name'] for i in data]
    links = ['[[' + (i if differentLinks(i)==None else differentLinks(i)+'|'+i) + ']]' for i in names]
    return '{{#if: {{#invoke:TemplUtl|faculty|{{{3|}}}}} |<!--\n      -->' + parseSwitch(links, 4) + '|<!--\n      -->' + parseSwitch(names, 4) + '}}'

def parseTime(data: list[dict[str, str]], discipline: str):
    if data == []: return parseError('Keine Daten für diese Parameterkombination.')
    ergebnis = data[0].get('single') if data[0].get('single') != '' else data[0].get('average')
    assert isinstance(ergebnis, str) and ergebnis != ''
    einheit = 'Züge' if 'moves' in discipline else ('Minuten' if ':' in ergebnis else 'Sekunden')
    ergebnisList = ergebnis.replace('.',',').split(' ')
    return ergebnisList[0] + '<!--' + ' '*(8-len(ergebnisList[0])) + '-->{{#if: {{#invoke:TemplUtl|faculty|{{{3|}}}}} | ' + ('&#32;in '+ergebnisList[1] if len(ergebnisList)>1 else '') + '&nbsp;' + einheit + '}}'

def parseEvents(data: list[dict[str, str]], discipline: str):
    if data == []: return parseError('Keine Daten für diese Parameterkombination.')
    events = [i['competition'] for i in data]
    return parseSwitch(events, 3)

def parseError(text: str):
    return f'<span class="error">{text}</span> [[Kategorie:Wikipedia:Vorlagenfehler/Speedcubing]]'

def stripTag(tag: bs4.element.Tag | None):
    if not isinstance(tag, bs4.element.Tag):
        return ''
    return tag.text.strip()

def formatTime(centiseconds: int, showCenti: bool):
    minutes = centiseconds // 6000
    centiseconds = centiseconds % 6000
    seconds = centiseconds // 100
    centiseconds = centiseconds % 100
    centiString = f'.{centiseconds:02}' if showCenti else ''
    if minutes == 0: return f'{seconds}{centiString}'
    hours = minutes // 60
    minutes = minutes % 60
    hoursString = f'{hours}:' if hours!=0 else ''
    return f'{hoursString}{minutes}:{seconds:02}{centiString}'

def formatValue(data: dict):
    # see https://github.com/thewca/worldcubeassociation.org/blob/main/app/webpacker/lib/wca-live/attempts.js
    value = data['value']
    event = data['event_id']
    if 'mb' in event: # multi blind
        missed = value % 100
        points = 99 - value // 10000000
        seconds = value // 100 % 100000
        return f'{points+missed}/{points+2*missed} {formatTime(seconds*100, showCenti=False)}'
    elif 'fm' in event: # fewest moves
        if data['type']=='single': return str(value)
        else: return  f'{value/100:.2f}'
    else:
        return formatTime(value, showCenti=True)

def formatDateForJson(data: dict):
    return f'{months[data['month']-1]} {data['day']:02}, {data['year']}'

def scrape():
    print('Lade worldcubeassociation.org ...')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',  'Accept': 'application/json'}
    result = requests.get('https://www.worldcubeassociation.org/results/records?show=history', headers=headers)
    assert result.ok
    rows: list[dict] | None = result.json().get('rows')
    assert rows is not None
    data: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = dict()
    for row in rows:
        event = row['event_id']
        event = eventNameById[event]
        if data.get(event) is None: data[event] = ([], [])
        type = row.get('type')
        assert type == 'single' or type == 'average'
        index = 0 if type == 'single' else 1
        formatedTime = formatValue(row)
        if len(data[event][index]) > 0 and formatedTime != data[event][index][0][['single', 'average'][index]]: continue
        data[event][index].append({'date': formatDateForJson(row),
                                   'single': formatedTime if type == 'single' else '',
                                   'average': formatedTime if type == 'average' else '',
                                   'name': row['person_name'],
                                   'competition': getFullCompetitionName(row['competition_id'])})
    return data
    
def run():
    newData = scrape()
    oldData: dict[str, tuple] = utils.loadJson('speedcubing.json', {})
    utils.dumpJson('speedcubing.json', newData)
    changedDisciplines = [i for i in disciplines.keys() if json.dumps(oldData.get(disciplines[i]), ensure_ascii=False) != json.dumps(newData.get(disciplines.get(i)), ensure_ascii=False)]
    changes = changedDisciplines != []
    if not changes:
        print('Keine Änderung an den Rohdaten.')
    else:
        editWiki(newData, parseDates,  changedDisciplines, 'Vorlage:Speedcubing-Rekorddatum')
        editWiki(newData, parseTime,   changedDisciplines, 'Vorlage:Speedcubing-Rekordzeit')
        editWiki(newData, parseEvents, changedDisciplines, 'Vorlage:Speedcubing-Rekordevent')
        editWiki(newData, parseNames,  changedDisciplines, 'Vorlage:Speedcubing-Rekordhalter')
    print('Erfolgreich ausgeführt.')
    return changes

def getFullCompetitionName(id: str):
    res = requests.get(f'https://www.worldcubeassociation.org/api/v0/competitions/{id}')
    assert res.ok
    content = res.json()
    assert content is not None
    return content['name']

if __name__ == '__main__':
    # editWiki(newData, parseEvents, changedDisciplines, 'Benutzer:DerIchBot/Spielwiese/Vorlage:Speedcubing-Rekorddatum', forcedSummary='Tests ...')
    # print(generatePage(newData, parseNames))
    run()
