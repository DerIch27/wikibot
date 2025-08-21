from pywikibot.comms import eventstreams
import birthDatesChecker
import citeParamChecker
import deletionInfo
import pywikibot
import telegram
import requests
import logging
import katdisk
import utils
import time
import re

def formatSeconds(timediff: int):
    timediff = int(timediff)
    result = f'{timediff%60} s'; timediff = timediff // 60
    if timediff == 0: return result
    result = f'{timediff%60} min, {result}'; timediff = timediff // 60
    if timediff == 0: return result
    result = f'{timediff%24} h, {result}'; timediff = timediff // 24
    if timediff == 0: return result
    return f'{timediff} d, {result}'


def getPageFromRevision(site, revision: int):
    request = site.simple_request(action='query', prop='revisions', revids=revision)
    data = request.submit()
    pageId = list(data['query']['pages'].keys())[0]
    return data['query']['pages'][pageId]['title']


def getStream():
    stream = eventstreams.EventStreams(streams='recentchange')
    stream.register_filter(type='edit', wiki='dewiki')
    return stream


def monitorRecentChanges():
    site = pywikibot.Site('de', 'wikipedia')
    site.login()
    stream = getStream()
    while True:
        try:
            change = next(stream)
            logging.debug(f'handle recent change {change.get('revision')} on {change.get('title')}')
            lag = int(time.time() - change['timestamp'])
            if lag > 600: # 10min
                logging.warning(f'received revision {change['revision']['new']} with lag {lag} and reset stream')
                stream = getStream()
                lastLagNotification = utils.checkLastUpdate('recent-lagged-stream', 30)
                if not lastLagNotification[0]:
                    telegram.send(f'reset stream after lag of {formatSeconds(lag)} ({telegram.difflink(change)}); Last lag {int(lastLagNotification[1]//60)}min ago', silent=True)
            telegram.alarmOnChange(change)
            if '�' in change['title']: # Invalid title
                logging.warning(f'replacement char found in title "{change.get('title')}" on change {change.get('revision')}')
                newTitle = getPageFromRevision(site, change['revision']['new'])
                change['title'] = newTitle
            if change['namespace'] == 4: # Wikipedia:XYZ
                if re.match('^Wikipedia:Löschkandidaten/.', change['title']):
                    deletionInfo.handleDeletionDiscussionUpdate(site, change['title'], change)
                if re.match('^Wikipedia:WikiProjekt Kategorien/Diskussionen/[0-9]{4}/(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)/[0-9][0-9]?$', change['title']):
                    katdisk.handleKatDiscussionUpdate(site, change['title'])
            elif change['namespace'] == 0: # Artikelnamensraum
                page = pywikibot.Page(site, change['title'])
                birthDatesChecker.checkPage(page)
                citeParamChecker.checkPagefromRecentChanges(page, change['title'])
        except requests.exceptions.HTTPError as e:
            telegram.handleServerError(e)
            monitorRecentChanges()
        except requests.exceptions.ConnectTimeout as e:
            telegram.handleServerError(e)
            monitorRecentChanges()
        except pywikibot.exceptions.ServerError as e:
            telegram.handleServerError(e)
            monitorRecentChanges()
        except TypeError as e:
            if str(e) == "Session.request() got an unexpected keyword argument 'last_event_id'":
                telegram.handleServerError(e)
                monitorRecentChanges()
            else:
                e.add_note(f'failed while handling recent change {change.get('revision')} on {change.get('title')}')
                raise e
        except Exception as e:
            e.add_note(f'failed while handling recent change {change.get('revision')} on {change.get('title')}')
            raise e


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - RECENT CHANGES - %(message)s', level=logging.INFO)
    telegram.send('start recent changes service ...', silent=True)
    try:
        monitorRecentChanges()
    except KeyboardInterrupt:
        print('Exception: KeyboardInterrupt')
    except Exception as e:
        telegram.handleException('RECENT CHANGES')
            