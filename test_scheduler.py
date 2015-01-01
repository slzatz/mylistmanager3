'''
version using simpler AWS SES to send email
using twitter to send direct messages as well
'''
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
import boto.ses
import markdown2 as markdown

ses_conn = boto.ses.connect_to_region(
                                      "us-east-1",
                                      aws_access_key_id=c.aws_access_key_id,
                                      aws_secret_access_key=c.aws_secret_access_key)
    
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

def alarm(task_tid):
    #task = session.query(Task).get(task_id)
    try:
        task = session.query(Task).filter(Task.tid==task_tid).one()
    except Exception as e:
        print("Could not find task tid:",task_tid)
        return
    subject = task.title
    body = task.note if task.note else ''
    html_body = markdown.markdown(body)
    print('Alarm! id:{}; subject:{}'.format(task_tid, subject))
    tw.direct_messages.new(user='slzatz', text=subject[:110])

    #res = sns_conn.publish(mytopic_arn, body, subject)
    res = ses_conn.send_email(
                        'manager.list@gmail.com',
                        'Testng SES',
                        'Hello my friends',
                        ['slzatz@gmail.com', 'szatz@webmd.net'],
                        html_body=html_body)
    print("res=",res)

scheduler = BackgroundScheduler()
url = 'sqlite:///scheduler_test.sqlite'
scheduler.add_jobstore('sqlalchemy', url=url)

tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
print("tasks=",tasks)
for t in tasks:
    #print(t.id)
    print(t.tid)
    j = scheduler.add_job(alarm, 'date', id=str(t.tid), run_date=t.duetime, name=t.title[:15], args=[t.title], replace_existing=True) 

scheduler.start()

app = Flask(__name__)

#settings.py
#HOST = '0.0.0.0'
#DEBUG = True

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']

############################# note - will need to create another task function to handle a simple reminder that was created outside of listmanager ###############
@app.route('/add/<int:delay>/<msg>')
def add(delay, msg):
    alarm_time = datetime.now() + timedelta(seconds=delay)
    j = scheduler.add_job(alarmxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx, 'date', run_date=alarm_time, name=msg[:15], args=[msg])
    return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p'))

@app.route('/add_task/<int:task_tid>/<int:days>/<int:minutes>/<msg>') #0.0.0.0:5000/2145/0/10/how%20are%20you
def add_task(task_tid, days, minutes, msg):
    alarm_time = datetime.now() + timedelta(days=days, minutes=minutes)
    j = scheduler.add_job(alarm, 'date', id=str(task_tid), run_date=alarm_time, name=msg[:15], args=[task_tid], replace_existing=True)
    z = {'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')}
    return json.dumps(z)
   
@app.route("/")
def index():
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')} for j in scheduler.get_jobs())
    return json.dumps(z)

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
