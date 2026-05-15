import pywikibot
import requests
import optOut

def fetchAndFormat(active: str):
    data = requests.get(f'https://api.landtag-rlp.de/api/mp/filteredList?searchTerm=&active={active}').json().get('content')
    return [f'|{i.get("firstname")} {i.get("lastname")} = https://landtag-rlp.de/de/parlament/abgeordnete/abgeordnetensuche/{i.get("urlKey")}' for i in data]

def run():
    data = requests.get('https://api.landtag-rlp.de/api/mp/filteredList?searchTerm=&active=active').json().get('content') + requests.get('https://api.landtag-rlp.de/api/mp/filteredList?searchTerm=&active=inactive').json().get('content')
    site = pywikibot.Site('de', 'wikipedia')
    page = pywikibot.Page(site, 'Vorlage:Biographie beim Landtag Rheinland-Pfalz')
    site.login()
    assert site.logged_in()
    page.text = '<onlyinclude><includeonly>[{{#switch: {{{1|Doris Ahnen}}}<!--bot-anfang--><!-- *** 18. Wahlperiode *** -->\n' + \
        '\n'.join(fetchAndFormat('active')) + \
        '\n\n<!-- *** Ausgeschieden *** -->\n' + '\n'.join(fetchAndFormat('inactive')) + \
        '\n<!--bot-ende-->|#default=<span class="error">Biographielink für {{{1|}}} nicht vorhanden, siehe [[Vorlage:Biographie beim Landtag Rheinland-Pfalz]].</span>\n}} Biographie beim Landtag Rheinland-Pfalz]</includeonly></onlyinclude>\n\n{{Dokumentation}}'
    if optOut.isAllowed(page):
        page.save(bot=True, minor=False, summary=(f'Bot: Ergänze ehemalige Abgeordnete'))
    site.logout()

if __name__ == '__main__':
    run()