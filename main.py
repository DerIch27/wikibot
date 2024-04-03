from datetime import datetime
import speedcubing
import edelmetalle
import traceback
import utils

if __name__ == '__main__':
    try:
        utils.sendTelegram('Start webscraping routine ...', silent=True)
        
        print('\n======== SPEEDCUBING ========')
        speedcubing.run()
    
        print('\n======== EDELMETALLE ========')
        edelmetalle.run()
        
        print(f'\n[{datetime.now()}] finished webscraping routine\n')
    
    except Exception:
        print('[FAILED]')
        utils.sendTelegram(traceback.format_exc())
        
