from datetime import datetime
import telegram
import psutil
import utils
import csv
import io

def getStats():
    return (
        psutil.cpu_percent(interval=30),
        psutil.virtual_memory().percent,
        psutil.disk_usage('/').percent
    )

def formatStats(stats: tuple[float,float,float]):
    return f'CPU: {stats[0]}%\nRAM: {stats[1]}%\nDISK: {stats[2]}%'

def badStats(stats: tuple[float,float,float]):
    return stats[0] > 80 or stats[1] > 90 or stats[2] > 80

def saveStats(stats: tuple[float,float,float]):
    utils.ensureDir('./logs/monitoring.csv')
    with io.open('./logs/monitoring.csv', 'a') as file:
        writer = csv.writer(file)
        writer.writerow([str(datetime.now())] + list(stats))

def run():
    stats = getStats()
    saveStats(stats)
    if badStats(stats):
        telegram.send(f'Monitoring Warning:\n{formatStats(stats)}', silent=True)

if __name__ == '__main__':
    run()
