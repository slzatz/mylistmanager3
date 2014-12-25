from datetime import datetime, timedelta
import sys
import os
from os.path import expanduser
home = expanduser('~')
import config as c
sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask
from twitter import *

from apscheduler.schedulers.background import BackgroundScheduler

# twitter
oauth_token = c.twitter_oauth_token 
oauth_token_secret = c.twitter_oauth_token_secret
CONSUMER_KEY = c.twitter_CONSUMER_KEY
CONSUMER_SECRET = c.twitter_CONSUMER_SECRET

tw = Twitter(auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET))

def alarm(msg):
    print('Alarm! {}'.format(msg))
    tw.direct_messages.new(user='slzatz', text=msg)

scheduler = BackgroundScheduler()
url = 'sqlite:///scheduler_test.sqlite'
scheduler.add_jobstore('sqlalchemy', url=url)

scheduler.start()

app = Flask(__name__)

# settings.py
#HOST = '0.0.0.0'
#DEBUG = True

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']

@app.route('/add/<int:delay>/<msg>')
def add(delay, msg):
    alarm_time = datetime.now() + timedelta(seconds=delay)
    j = scheduler.add_job(alarm, 'date', run_date=alarm_time, name=msg[:15], args=[msg])
    return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.isoformat())
    
@app.route("/")
def index():
    print(scheduler.get_jobs())
    return '  ---'.join(x.name+' '+str(x.id)+'<br>' for x in scheduler.get_jobs())

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG)
