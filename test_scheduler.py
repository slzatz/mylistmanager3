'''
#topics = sns_conn.get_all_topics()
#print("topics=",topics)
#topics= {'ListTopicsResponse': {'ListTopicsResult': {'NextToken': None, 'Topics': [{'TopicArn': 'arn:aws:sns:us-east-1:726344206365:sonos'}]}, 'ResponseMetadata': {'RequestId': '677b
#830a-b53c-5d2c-9cd8-ce166f1d0591'}}}

#mytopics = topics["ListTopicsResponse"]["ListTopicsResult"]["Topics"]
#print("mytopics=", mytopics)
#mytopics= [{'TopicArn': 'arn:aws:sns:us-east-1:726344206365:sonos'}]

#Amazon Resource Names (ARNs) uniquely identify AWS resources
#mytopic_arn = mytopics[0]["TopicArn"]
#print("mytopic_arn=", mytopic_arn)
#mytopic_arn= arn:aws:sns:us-east-1:726344206365:sonos

#subscriptions = sns_conn.get_all_subscriptions_by_topic(mytopic_arn)
#print("subscriptions=",subscriptions)
#subscriptions= {'ListSubscriptionsByTopicResponse': {'ListSubscriptionsByTopicResult': {'NextToken': None, 'Subscriptions': [{'Protocol': 'email', 'TopicArn': 'arn:aws:sns:us-east-1:
#726344206365:sonos', 'SubscriptionArn': 'arn:aws:sns:us-east-1:726344206365:sonos:ea23e845-4075-4f37-883f-5b08a986c40a', 'Endpoint': 'slzatz@gmail.com', 'Owner': '726344206365'}, {'P
#rotocol': 'sms', 'TopicArn': 'arn:aws:sns:us-east-1:726344206365:sonos', 'SubscriptionArn': 'arn:aws:sns:us-east-1:726344206365:sonos:2beaa08b-2a3d-4414-bf5c-cd7be2d9e64a', 'Endpoint
#': '12032167088', 'Owner': '726344206365'}, {'Protocol': 'email', 'TopicArn': 'arn:aws:sns:us-east-1:726344206365:sonos', 'SubscriptionArn': 'arn:aws:sns:us-east-1:726344206365:sonos
#:1cda6eeb-70cf-4a3d-be9b-452ee3fe2605', 'Endpoint': '2032167088@mms.att.net', 'Owner': '726344206365'}]}, 'ResponseMetadata': {'RequestId': '9ce0b3f1-4029-5c12-9cb1-feed9a085aee'}}}
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
import boto.sns
import markdown2 as markdown

sns_conn = boto.sns.connect_to_region(
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

def alarm(task_id):
    task = session.query(Task).get(task_id)
    subject = task.title
    body = task.note if task.note else ''
    body = markdown.markdown(body)
    print('Alarm! id:{}; subject:{}'.format(task_id, subject))
    tw.direct_messages.new(user='slzatz', text=subject[:110])

    #res = sns_conn.publish(mytopic_arn, body, subject)
    res = sns_conn.publish(c.listmanager_sns_arn, body, subject) #subject can't be empty
    print("res=",res)

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

#settings.py
#HOST = '0.0.0.0'
#DEBUG = True

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']

@app.route('/add/<int:delay>/<msg>')
def add(delay, msg):
    alarm_time = datetime.now() + timedelta(seconds=delay)
    j = scheduler.add_job(alarm, 'date', run_date=alarm_time, name=msg[:15], args=[msg])
    return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p'))

@app.route('/add_task/<task_id>/<int:days>/<int:minutes>/<msg>') #0.0.0.0:5000/2145/0/10/how%20are%20you
def add_task(task_id, days, minutes, msg):
    alarm_time = datetime.now() + timedelta(days=days, minutes=minutes)
    j = scheduler.add_job(alarm, 'date', id=task_id, run_date=alarm_time, name=msg[:15], args=[task_id])
    z = {'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')}
    return json.dumps(z)
   
@app.route("/")
def index():
    print(scheduler.get_jobs())
    # this should return json - scheduler.get_jobs() returns a list of job instances
    # to turn this into json, would be [job1 dict, job2 dict, job3 dict]
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')} for j in scheduler.get_jobs())
    return json.dumps(z)
    #return '<br><br>'.join(x.name+'<br>'+str(x.id)+'<br>'+x.trigger.run_date.isoformat() for x in scheduler.get_jobs())

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
