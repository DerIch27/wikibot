import deletionInfo
import unreviewed
import pywikibot
import telegram
import logging
import katdisk

if __name__ == '__main__':
    try:
        logging.basicConfig(format='%(asctime)s - %(levelname)s - HOURLY - %(message)s', level=logging.INFO)
        logging.info(f'start hourly routine')
        
        site = pywikibot.Site('de', 'wikipedia')
        katdisk.handleKatDiscussionToday(site)
        deletionInfo.sendDeletionNotifications(site)
        unreviewed.run(site)
        
        logging.info(f'finished hourly routine')
    
    except Exception:
        telegram.handleException('HOURLY')
