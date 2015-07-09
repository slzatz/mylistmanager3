'''
version using simpler AWS SES to send email
using twitter to send direct messages as well
'''
from datetime import datetime, timedelta
import sys
import os
import argparse
import json
from os.path import expanduser, isfile
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
    
parser = argparse.ArgumentParser(description='Command line options for determining which db; sending html email.')

# for all of the following: if the command line option is not present then the value is the opposite of below
parser.add_argument( '--aws', action='store_true', help="Use postgres db located in AWS RDS")
parser.add_argument( '--html', action='store_true', help="Send both a plain and HTML email")
args = parser.parse_args()

session = remote_session if args.aws else local_session

# twitter
oauth_token = c.twitter_oauth_token 
oauth_token_secret = c.twitter_oauth_token_secret
CONSUMER_KEY = c.twitter_CONSUMER_KEY
CONSUMER_SECRET = c.twitter_CONSUMER_SECRET

tw = Twitter(auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET))

#using cloudmailin makes it possible to respond
sender = 'mylistmanager <6697b86bca34dcd126cb@cloudmailin.net>'
recipients = ['slzatz@gmail.com', 'szatz@webmd.net']

if not isfile('sync_log'):
    with open("sync_log", 'w') as f:
        f.write("There is currently no sync file present")

#global
sync_in_progress = False
sonos_companion = {'artist':None, 'source':None, 'updated':False}

def sync():
    global sync_in_progress
    sync_in_progress = True

    if not toodledo2.keycheck():
        print("Could not get a good toodledo key")
        res = ses_conn.send_email(sender, "Failure to obtain toodledo key", "", recipients) 
        return
        
    log, changes, tasklist, deletelist = synchronize2.synchronize(showlogdialog=False, OkCancel=False, local=False) 

    with open("sync_log", 'w') as f:
        f.write(log)

    sync_in_progress = False

    for task in tasklist:
        if task.remind == 1 and task.duetime > (datetime.now() - timedelta(hours=5)): # need server offset
            adjusted_dt = task.duetime + timedelta(hours=5)
            j = scheduler.add_job(alarm, 'date', id=str(task.tid), run_date=adjusted_dt, name=task.title[:50], args=[task.tid], replace_existing=True)
    
    subject = "sync log"
    res = ses_conn.send_email(sender, "Sync Log", log, recipients)

    print("res=",res)

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
    hints = "| priority: !! or zero or 0; alarm: off; star: star or * or nostar; remind: off"
    header = "star: {}; priority: {}; context: {}; reminder: {}".format(task.star, task.priority, task.context.title, task.remind)
    body = header+hints+"\n==================================================================================\n"+body
    print('Alarm! id:{}; subject:{}'.format(task_tid, subject))

    tw.direct_messages.new(user='slzatz', text=subject[:110])

    res = ses_conn.send_email(sender, subject, body, recipients)
    print("res=",res)

    if args.html and body:
        html_body = markdown.markdown(body)
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
    if sync_in_progress:
        return Response("There appears to be a sync already going on", mimetype='text/plain')
    else:
        j = scheduler.add_job(sync, name="sync")
        return Response("Initiated sync - check /sync-log to see what happened", mimetype='text/plain')
   
@app.route("/sync-log")
def sync_log():
    if sync_in_progress:
        return Response("Sync currently underway", mimetype='text/plain')
    else:
        with open("sync_log", 'r') as f:
            z = f.read()
        return Response(z, mimetype='text/plain')

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
        subject = request.form.get('headers[Subject]')
        if subject.lower().startswith('re:'):
            pos = subject.find('|')
            if pos != -1:
                title = subject[3:pos].strip()
                mods = subject[pos+1:].strip().split()
            else:
                title = subject[3:].strip()
                mods = []
            task = session.query(Task).filter(Task.title==title).all()
            if len(task) > 1:
                print("More than one task had the title: {}".format(subject))
                return "More than one task had the title: {}".format(subject)
            elif len(task) == 0:
                print("No task matched: {}".format(subject))
                return "No task matched: {}".format(subject)

            print("There is only one task with the title: {}".format(subject))

            body = request.form.get('plain')
            pattern = "================="
            pos = body.rfind(pattern)
            note = body[1+pos+len(pattern):] if pos!=-1 else body
            #print(body) 
            task = task[0]
            task.note = note

            if mods:
                for m in mods:
                    if '!' in m:
                        task.priority = len(m) if len(m) < 4 else 3
                    if m in ('0', 'zero'):
                        task.priority = 0
                    if m == 'nostar':
                        task.star = False
                    if m in ('*', 'star'):
                        task.star = True
                    if m == 'off':
                        task.remind = None

            session.commit()

            #at one point it was automatically syncing and that may actually be a good idea
            #j = scheduler.add_job(sync, name="sync")

            return "Updated task with new body"

        elif subject.lower().strip() == 'sync': #startswith('sync'):
            j = scheduler.add_job(sync, name="sync")
            return "Initiated sync"
        else:
            return "Email subject did not start with 're:' or sync"

    else:
        return 'It was not a post method'

@app.route('/echo/<artist>/<source>') #0.0.0.0:5000/2145/0/10/how%20are%20you
def echo(artist, source):
    print(artist)
    print(source)
    sonos_companion['artist'] = artist
    sonos_companion['source'] = source
    sonos_companion['updated'] = True
    return json.dumps(sonos_companion)

@app.route('/sonos_companion_check') #0.0.0.0:5000/2145/0/10/how%20are%20you
def sonos_companion_check():
    if sonos_companion['updated']:
        temp = dict(sonos_companion)
        sonos_companion['updated'] = False
        return json.dumps(temp)
    else:
        return json.dumps(sonos_companion)

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
