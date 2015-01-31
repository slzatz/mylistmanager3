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
from functools import wraps
home = expanduser('~')
import config as c
sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask, request, Response, render_template, url_for #, Markup
from twitter import *
from lmdb import *
from apscheduler.schedulers.background import BackgroundScheduler
import boto.ses
import markdown2 as markdown
import toodledo2
import synchronize2

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

sender = 'manager.list@gmail.com'
recipients = ['slzatz@gmail.com', 'szatz@webmd.net']

def sync():

    if not toodledo2.keycheck():
        print("Could not get a good toodledo key")
        res = ses_conn.send_email(sender, "Failure to obtain toodledo key", "", recipients) 
        return
        
    log, changes, tasklist, deletelist = synchronize2.synchronize(showlogdialog=False, OkCancel=False, local=False) 

    for task in tasklist:
        if task.remind == 1 and task.duetime > (datetime.now() - timedelta(hours=5)): # need server offset
            adjusted_dt = task.duetime + timedelta(hours=5)
            j = scheduler.add_job(alarm, 'date', id=str(task.tid), run_date=adjusted_dt, name=task.title[:50], args=[task.tid], replace_existing=True)
    
    subject = "sync log"
    res = ses_conn.send_email(sender, "Sync Log", log, recipients)

    print("res=",res)

    with open("sync_log", 'a') as f:
        f.write(log)

def alarm(task_tid):

    try:
        task = session.query(Task).filter(Task.tid==task_tid).one()
    except Exception as e:
        print("Could not find task tid:",task_tid)
        print("Exception: ",e)
        res = ses_conn.send_email(sender, "Exception trying to find task_tid: {}".format(task_tid), "The exception was: {}".format(e), recipients)
        return
    
    subject = task.title
    body = task.note if task.note else ''
    html_body = markdown.markdown(body)
    print('Alarm! id:{}; subject:{}'.format(task_tid, subject))

    tw.direct_messages.new(user='slzatz', text=subject[:110])

    res = ses_conn.send_email(sender, subject, body, recipients, html_body=html_body)
    print("res=",res)

    #starred tasks automatically repeat their alarm every 24h
    if task.star:
        task.duedate = task.duetime = task.duetime + timedelta(days=1)
        session.commit()
        j = scheduler.add_job(alarm, 'date', id=str(task.tid), run_date=task.duetime, name=task.title[:15], args=[task.tid], replace_existing=True) # shouldn't need replace_existing but doesn't hurt and who knows ...
        print("Starred task was scheduled again")
        print('Task tid:{}; star: {}; title:{}'.format(task.tid, task.star, task.title))
        print("Alarm scheduled: {}".format(repr(j)))

scheduler = BackgroundScheduler()
url = 'sqlite:///scheduler_test.sqlite'
scheduler.add_jobstore('sqlalchemy', url=url)

# On restarting program, want to pick up the latest alarms
tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
print("On restart, there are {} tasks that are being scheduled".format(tasks.count()))
for t in tasks:
    j = scheduler.add_job(alarm, 'date', id=str(t.tid), run_date=t.duetime, name=t.title[:50], args=[t.tid], replace_existing=True) 
    print('Task tid:{}; star: {}; title:{}'.format(t.tid, t.star, t.title))
    print("Alarm scheduled: {}".format(repr(j)))

scheduler.start()

app = Flask(__name__)

#settings.py
#HOST = '0.0.0.0'
#DEBUG = True

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username ==  c.aws_id and password == c.aws_pw

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

############################# note - will need to create another task function to handle a simple reminder that was created outside of listmanager ###############
@app.route('/add/<int:delay>/<msg>')
def add(delay, msg):
    alarm_time = datetime.now() + timedelta(seconds=delay)
    j = scheduler.add_job(alarmxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx, 'date', run_date=alarm_time, name=msg[:15], args=[msg])
    return 'added new job: id: {}<br>  name: {}<br>  run date: {}'.format(j.id, j.name, j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p'))

@app.route('/add_task/<int:task_tid>/<int:days>/<int:minutes>/<msg>') #0.0.0.0:5000/2145/0/10/how%20are%20you
@requires_auth
def add_task(task_tid, days, minutes, msg):
    alarm_time = datetime.now() + timedelta(days=days, minutes=minutes)
    j = scheduler.add_job(alarm, 'date', id=str(task_tid), run_date=alarm_time, name=msg[:50], args=[task_tid], replace_existing=True)
    z = {'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')}
    return json.dumps(z)

@app.route("/sync")
def do_immediate_sync():
    j = scheduler.add_job(sync, name="sync")
    return json.dumps({'name':j.name})
   
@app.route("/")
def index():
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')} for j in scheduler.get_jobs())
    return json.dumps(z)

@app.route("/recent")
def recent():
    tasks = session.query(Task).filter(and_(Task.completed == None, Task.modified > (datetime.now() - timedelta(days=2))))
    tasks2 = session.query(Task).join(Context).filter(and_(Context.title == 'work', Task.priority == 3, Task.completed == None)).order_by(desc(Task.modified))

    z = list(j.id for j in scheduler.get_jobs())
    tasks3 = session.query(Task).filter(Task.tid.in_(z))

    return render_template("recent.html", tasks=tasks, tasks2=tasks2, tasks3=tasks3) #, Markup=Markup) # not sure why you have to pass Markup and not url_for
    
@app.route("/incoming", methods=['GET', 'POST'])
def incoming():
    if request.method == 'POST':
        body = request.form['body']
        print(body) #envelope, headers, body, attachments
    else:
        return 'OK'

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
