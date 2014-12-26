from datetime import datetime, timedelta
import sys
import os
from os.path import expanduser
home = expanduser('~')
import config as c
sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask
from twitter import *

import lmglobals as g #moved from below on 12-21-2014
g.DB_URI = g.sqlite_uri #lmdb needs this set before called
from lmdb_aws import *

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

#tasks = session.query(Task).filter(Task.remind == 1)
#tasks.filter(and_(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)), ~(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())))
tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
print("tasks=",tasks)
for t in tasks:
    print(t.id)
    j = scheduler.add_job(alarm, 'date', id=str(t.id), run_date=t.duetime, name=t.title[:15], args=[t.title])

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
    return '<br><br>'.join(x.name+'<br>'+str(x.id)+'<br>'+x.trigger.run_date.isoformat() for x in scheduler.get_jobs())

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
