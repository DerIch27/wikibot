import pywikibot
import logging
import utils
import re

def checkPage(page: pywikibot.Page):
    content = page.get()
    for link, year in re.findall('\\* \\[\\[([^\\]]*)\\]\\] \\(\\* ([0-9]{4})\\)', content):
        logging.info(f'found something: {[link, year, page.title]}')
        utils.addToCsv('birthDates.csv', [link, year, page.title], ['link', 'year', 'pagetitle'])

if __name__ == '__main__':
    site = pywikibot.Site('de', 'wikipedia')
    page = pywikibot.Page(site, 'Hohenstaufen-Gymnasium (Kaiserslautern)')
    checkPage(page)