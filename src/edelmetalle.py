import wikitextparser as wtp
import pywikibot
import telegram
import requests
import optOut
import utils
import time

def fetch(metall: str):
    print(f'fetch {metall} ...')
    res = requests.get(f'https://prices.lbma.org.uk/json/{metall}.json')
    data = res.json()
    return data[-1]['d'], data[-1]['v'][0]

def fetchTwo(names: tuple[str, str]):
    data_a = fetch(names[0])
    data_b = fetch(names[1])
    assert data_a[0] == data_b[0]
    datum = utils.formatDate(data_a[0][8:10], data_a[0][5:7], data_a[0][0:4])
    return datum, (str(data_a[1]), str(data_b[1]))

def update(template: str, apiNames: tuple[str, str], displayNames: tuple[str, str], option: str):
    site = pywikibot.Site('de', 'wikipedia')
    page = pywikibot.Page(site, f'Vorlage:{template}')
    print(page)
    daysSinceLastRevistion = (time.time() - page.latest_revision['timestamp'].timestamp())/60/60/24
    if daysSinceLastRevistion < 7:
        print('skip update')
        return False
    if page.latest_revision['user'] != 'DerIchBot':
        telegram.send(f'Warnung: Vorlage:{template} zuletzt von {page.latest_revision['user']} bearbeitet.')
        return False
    noinclude = wtp.parse(page.text).get_tags()[1]
    assert noinclude.name == 'noinclude'
    datum, data = fetchTwo(apiNames)
    page.text = "<includeonly>{{#if:{{{Datum|}}} | " + datum + " | {{#if:{{{" + option + "|}}}\n| {{formatnum:\n     {{#expr: ( " + data[0] + " <!-- " + displayNames[0] + " in USD --> / {{Wechselkursdaten|USD}} * {{Wechselkursdaten|{{{1|USD}}}}} / {{#if:{{{Gramm|}}}|31.1034768|1}} ) ^ {{#if:{{{Invert|}}}|-1|1}} * {{{Faktor|1}}} round {{{NKS|2}}} }}\n  }}\n| {{formatnum:\n     {{#expr: ( " + data[1] + " <!-- " + displayNames[1] + " in USD --> / {{Wechselkursdaten|USD}} * {{Wechselkursdaten|{{{1|USD}}}}} / {{#if:{{{Gramm|}}}|31.1034768|1}} ) ^ {{#if:{{{Invert|}}}|-1|1}} * {{{Faktor|1}}} round {{{NKS|2}}} }}\n  }}\n}}\n}}</includeonly>" + str(noinclude)
    site.login()
    assert site.logged_in()
    if optOut.isAllowed(page):
        page.save(bot=True, minor=False, summary=(f'Bot: Aktualisiere Preise: Schlusskurs vom {datum}'))
    site.logout()
    return True
    
def run():
    res1 = update('Goldpreis', ('silver', 'gold_pm'), ('Silber', 'Gold'), 'AG')
    res2 = update('Platinpreis', ('palladium_pm', 'platinum_pm'), ('Palladium ', 'Platin'), 'PD')
    return res1 or res2

if __name__ == '__main__':
    run()
