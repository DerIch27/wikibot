import wikitextparser as wtp
from typing import Optional
import deletionToKatdisk
import citeParamChecker
import pywikibot
import unittest
import schools
import utils
import bs4


class TestDateParsing(unittest.TestCase):
    def test_weird_date_parsing(self):
        site = pywikibot.Site('de', 'wikipedia')
        page = pywikibot.Page(site, 'Benutzer:DerIchBot/Datumstests')
        rawDates = [i.split('|')[2] for i in page.get().split('\n\n')]
        parsedDates = [p.text.replace(u'\xa0', u' ').strip() for p in bs4.BeautifulSoup(page.get_parsed_page(), 'html.parser').find_all('p')]
        self.assertEqual(len(rawDates), len(parsedDates))
        for raw, parsed in zip(rawDates, parsedDates):
            with self.subTest(raw=raw, parsed=parsed):
                timestamp = citeParamChecker.parseWeirdDateFormats(raw)
                if timestamp != False: timestamp = utils.formatDateFromDatestring(timestamp)
                if timestamp == False: timestamp = 'Format invalid'
                self.assertEqual(timestamp, parsed)
                
    def test_date_month_offset(self):
        self.assertEqual(citeParamChecker.getNextMonth('2020-03-17'), '2020-04-17')
        self.assertEqual(citeParamChecker.getNextMonth('2025-12-20'), '2026-01-20')
        self.assertEqual(citeParamChecker.getNextMonth('2021-01-30'), '2021-02-28')
                
    def test_date_day_offset(self):
        self.assertEqual(citeParamChecker.getNextDay('2020-03-17'), '2020-03-18')
        self.assertEqual(citeParamChecker.getNextDay('2025-12-31'), '2026-01-01')
        self.assertEqual(citeParamChecker.getNextDay('2021-01-31'), '2021-02-01')


class TestSchoolDecorators(unittest.TestCase):
    def test_can_be_none(self):
        self.assertTrue(schools.canBeNone(str|None|float))
        self.assertTrue(schools.canBeNone(str|Optional[str]|int))
        self.assertTrue(schools.canBeNone(None))
        self.assertFalse(schools.canBeNone(str|int))
        self.assertFalse(schools.canBeNone(float))


class TestDeletionDiskExtraction(unittest.TestCase):
    def test_extract_from_page_without_category(self):
        for i, pagecontent in enumerate(['{{Wikipedia:Löschkandidaten/!Seitenkopf|erl=}}\n<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren und auch diesen Kommentar löschen. -->\n\n= Benutzerseiten =\n== [[Benutzer:DerIch27]] ==\n\nbla',
                                         '{{Löschkandidatenseite|erl=}}\n<!-- Hinweis an den letzten Bearbeiter: Wenn alles erledigt ist, hinter "erl=" mit --~~~~ signieren. -->\n\n= Benutzerseiten =\n\n= Metaseiten =\n\n= Vorlagen =\n\n= Listen =\n\n= Artikel =\n']):
            with self.subTest(index=i, pagecontent=pagecontent):
                cats, rest = deletionToKatdisk.extractFromDeletionDisk(pagecontent)
                self.assertEqual(cats, '')


class TestCiteParamChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = pywikibot.Site('de', 'wikipedia')
    def testInvalidTemplate(self):
        pagetitle = 'Grammer AG'
        page = pywikibot.Page(self.site, pagetitle)
        problems = list(citeParamChecker.checkPage(page, pagetitle, [], 264257961))
        self.assertEqual(len(problems), 1)
        problem = problems[0]
        self.assertEqual(problem.titel, pagetitle)
        self.assertEqual(problem.problemtyp, 'Parameter abruf/zugriff liegt in der Zukunft.')
        self.assertEqual(problem.assets, '2026-12-02')
        self.assertFalse(problem.freshVersion)
    def testTypoCheck(self):
        for templatename in ['Internetquelle/', 'Inernentquelle', 'Lateratur']:
            with self.subTest(templatename=templatename):
                self.assertTrue(citeParamChecker.checkTemplateTypo(wtp.Template('{{'+templatename+'}}')))
        for templatename in ['Internetquelle', 'Navigationsleiste deutschsprachiger Literaturnobelpreisträger', 'TUR']:
            with self.subTest(templatename=templatename):
                self.assertFalse(citeParamChecker.checkTemplateTypo(wtp.Template('{{'+templatename+'}}')))


if __name__ == '__main__':
    unittest.main()