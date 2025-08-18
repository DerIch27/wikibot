import traceback
import requests
import logging
import dotenv
import utils
import time
import re
import os


dotenv.load_dotenv()
DISABLED = not utils.getBoolEnv('TELEGRAM_ENABLED', False)
TARGET_USER = os.getenv('TELEGRAM_TARGET_USER')
ACCESS_TOKEN = os.getenv('TELEGRAM_ACCESS_TOKEN')
if DISABLED:
    logging.info('telegram notifications are disabled')
elif TARGET_USER is None or ACCESS_TOKEN is None:
    logging.error('telegram credentials are not set in .env')
    raise Exception('telegram credentials are not set in .env')


def send(message: str, silent: bool=False):
    if DISABLED: logging.info('telegram is disabled. skip notification:\n' + message); return
    maxLogLength = 75
    logmessage = message.replace('\n', ' ↵ ')
    message = message.replace('_', '\_')
    logging.info(f'Send telegram message: {logmessage[:maxLogLength]}{'...' if len(logmessage)>maxLogLength else ''}')
    url = f'https://api.telegram.org/bot{ACCESS_TOKEN}/sendMessage'
    result = requests.post(url, {'chat_id': TARGET_USER, 'text': message, 'disable_notification': silent, 'parse_mode': 'Markdown'})
    if not result.ok: 
        logging.error(f'sending telegram message of length {len(message)} failed with status {result.status_code}')
        try:
            logging.error(f'telegram response: {result.json()}')
        except:
            pass
    return result.ok


def handleException(tag: str):
    logging.error(traceback.format_exc())
    if not send(f'FAILED [{tag}]\n\nMimimi, du hast Müll gebaut, deshalb stürze ich jetzt ab:\n\n' + traceback.format_exc()):
        send(f'FAILED [{tag}]')
    

def handleServerError(e: Exception):
    logging.warning(f'Handle Server Error\n{traceback.format_exc()}')
    pastServerErrors: list[float] = utils.loadJson('serverErrors.json', [0])
    lastServerError = time.time()-pastServerErrors[0]
    pastServerErrors = [i for i in pastServerErrors if (time.time()-i)<60*60*24*7] + [time.time()] # 7d
    utils.dumpJson('serverErrors.json', pastServerErrors)
    fail = len([i for i in pastServerErrors if (time.time()-i)<60*30]) > 5 # 30min
    if fail:
        e.add_note(f'failed on server error; last error {lastServerError/60:.0f}min ago')
        raise e
    if lastServerError < 60 *60 * 3: # 3h
        send(f'WARNING: Ignored Server Error; last one {lastServerError/60:.0f}min ago', silent=True)
    time.sleep(60)
    
    
def difflink(change: dict):
    return f'[Diff](https://de.wikipedia.org/wiki/Spezial:Diff/{change['revision']['new']})'


outstandingNotifications: list[str] = []
lastSentNotification: float = 0
lastXqbotDeletionNotification = time.time()
xqbotInactive = False
def alarmOnChange(change: dict):
    global lastXqbotDeletionNotification
    global xqbotInactive
    global outstandingNotifications
    global lastSentNotification
    if outstandingNotifications != [] and lastSentNotification + 60*60*3 < time.time():
        logging.info('send change alarms')
        send('\n'.join(outstandingNotifications))
        lastSentNotification = time.time()
        outstandingNotifications = []
    def notify(msg: str):
        logging.warning(change)
        outstandingNotifications.append(f'{msg} ({difflink(change)})')
    XQBOT_INACTIVITY_NOTIFICATION_DELAY = 18
    if not xqbotInactive and time.time() - lastXqbotDeletionNotification > 60*60*XQBOT_INACTIVITY_NOTIFICATION_DELAY:
        xqbotInactive = True
        outstandingNotifications.append(f'xqbot inaktiv für {XQBOT_INACTIVITY_NOTIFICATION_DELAY}h')
    if re.match('Bot: Benachrichtigung über Löschdiskussion zum Artikel', change['comment']):
        lastXqbotDeletionNotification = time.time()
        if xqbotInactive or utils.getBoolEnv('DELETION_NOTIFICATION_ENABLED', True):
            xqbotInactive = False
            notify('XqBot aktiv')
            return True
    if change['user'] == 'TaxonBot' and re.match('^Bot: [1-9][0-9]? Abschnitte? nach \\[\\[Benutzer(in)? Diskussion:.*\\]\\] archiviert – letzte Bearbeitung: \\[\\[user:DerIchBot|DerIchBot\\]\\] \\(.*\\)$', change['comment']):
        return False
    if change['user'] == 'SpBot' and re.match('^Archiviere [1-9][0-9]? Abschnitt(.)* - letzte Bearbeitung: \\[\\[:User:DerIchBot|DerIchBot\\]\\],', change['comment']):
        return False
    if change['user'] == 'DerIchBot':
        return False
    if 'DerIchBot' in change['comment']:
        notify('DerIchBot erwähnt')
        return True
    watchlist = ['Vorlage:Platinpreis', 'Vorlage:Goldpreis', 'Vorlage:Speedcubing-Rekorddatum', 'Vorlage:Speedcubing-Rekordevent', 
                 'Vorlage:Speedcubing-Rekordhalter', 'Vorlage:Speedcubing-Rekordzeit']
    if change['title'] in watchlist:
        notify('Beobachtete Seite bearbeitet.')
        return True


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - TELEGRAM - %(message)s', level=logging.DEBUG)
    send('Bahnstrecke Ringsted–Rødby F�rge')