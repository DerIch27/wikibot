import citeParamChecker
import pywikibot
import traceback
import telegram
import optOut
import utils
import flask

app = flask.Flask(__name__)

HOST = '87.106.41.45'
PORT = 3000

@app.route('/aktualisiere-wartungsliste-cache')
def aktualisiere_wartungsliste_cache(): 
    if utils.checkLastUpdate('aktualisiere-wartungsliste-cache', 15)[0]:
        citeParamChecker.updateWikilist()
        return 'Wartungsliste erfolgreich aktualisiert. Du wirst gleich weitergeleitet ...', {"Refresh": "4; url=https://de.wikipedia.org/wiki/Benutzer:DerIchBot/Wartungsliste"}
    else:
        return 'Aktualisierung verweigert, da letzte Aktualisierung aus Cache weniger als 15 Minuten her ist.'

@app.route('/aktualisiere-wartungsliste-check')
def aktualisiere_wartungsliste_check(): 
    if utils.checkLastUpdate('aktualisiere-wartungsliste-check', 15)[0]:
        site = pywikibot.Site('de', 'wikipedia')
        citeParamChecker.checkPagesInProblemList(site)
        citeParamChecker.updateWikilist()
        return 'Wartungsliste erfolgreich geprüft und aktualisiert. Du wirst gleich weitergeleitet ...', {"Refresh": "4; url=https://de.wikipedia.org/wiki/Benutzer:DerIchBot/Wartungsliste"}
    else:
        return 'Aktualisierung verweigert, da letzte Aktualisierung mit Prüfung weniger als 15 Minuten her ist.'

@app.route('/aktualisiere-opt-out')
def aktualisiere_opt_out(): 
    if utils.checkLastUpdate('download-opt-out-list', 5)[0]:
        optOut.download()
        return 'Opt-Out Liste erfolgreich heruntergeladen. Du wirst gleich weitergeleitet ...', {"Refresh": "4; url=https://de.wikipedia.org/wiki/Benutzer:DerIchBot/Opt-Out_Liste"}
    else:
        return 'Aktualisierung verweigert, da letzte Aktualisierung weniger als 5 Minuten her ist.'

@app.route('/number-of-problems')
def number_of_problems():
    return f'{len(citeParamChecker.loadAllProblems())} Probleme im Cache'

@app.errorhandler(500)
def exception_handler(error):
    app.logger.error(f'STATUS 500\n\n{traceback.format_exc()}')
    telegram.handleException('WEBSERVER')
    return "Unerwarteter interner Fehler aufgetreten. Der Betreiber wurde bereits benachrichtigt.", 500

if __name__=='__main__': 
    app.run(host=HOST, port=PORT)
