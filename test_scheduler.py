from datetime import datetime, timedelta
import sys
import os
import argparse
import json
from os.path import expanduser
home = expanduser('~')
import config as c
sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask
from twitter import *
from lmdb import *

from apscheduler.schedulers.background import BackgroundScheduler

parser = argparse.ArgumentParser(description='Command line options for determining which db.')

# for all of the following: if the command line option is not present then the value is True
parser.add_argument( '--aws', action='store_true', help="Use AWS version of database")
args = parser.parse_args()

session = remote_session if args.aws else local_session

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

tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
print("tasks=",tasks)
for t in tasks:
    print(t.id)
    j = scheduler.add_job(alarm, 'date', id=str(t.id), run_date=t.duetime, name=t.title[:15], args=[t.title], replace_existing=True) 

scheduler.start()

app = Flask(__name__)

# settings.py
#HOST = '0.0.0.0'
#DEBUG = True #true messes up apscheduler because of dups 

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']

@app.route('/add/<int:delay>/<msg>')
def add(delay, msg):
    alarm_time = datetime.now() + timedelta(seconds=delay)
    j = scheduler.add_job(alarm, 'date', run_date=alarm_time, name=msg[:15], args=[msg])
    return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.isoformat())

@app.route('/add_task/<task_id>/<int:days>/<int:minutes>/<msg>') #0.0.0.0:5000/2145/0/10/how%20are%20you
def add_task(task_id, days, minutes, msg):
    alarm_time = datetime.now() + timedelta(days=days, minutes=minutes)
    j = scheduler.add_job(alarm, 'date', id=task_id, run_date=alarm_time, name=msg[:15], args=[msg])
    #return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.isoformat())
    z = {'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.isoformat()}
    return json.dumps(z)
   
@app.route("/")
def index():
    print(scheduler.get_jobs())
    # this should return json - scheduler.get_jobs() returns a list of job instances
    # to turn this into json, would be [job1 dict, job2 dict, job3 dict]
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.isoformat()} for j in scheduler.get_jobs())
    return json.dumps(z)
    #return '<br><br>'.join(x.name+'<br>'+str(x.id)+'<br>'+x.trigger.run_date.isoformat() for x in scheduler.get_jobs())

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
