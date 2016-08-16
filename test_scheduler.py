'''
This version uses Sendgrid to send email and uses twitter to send direct messages
'''
from datetime import datetime, timedelta
import sys
import os
import json
from os.path import expanduser
from functools import wraps
home = expanduser('~')
import config as c
sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask, request, Response, render_template
from twitter import *
from lmdb_p import *
from apscheduler.schedulers.background import BackgroundScheduler
import sendgrid

# Sendgrid stuff below
sg = sendgrid.SendGridAPIClient(apikey=c.SENDGRID_API_KEY)
mail_data = {
            "personalizations": [{"to":[{"email": "slzatz@gmail.com"}, {"email":"szatz@webmd.net"}], "subject":""}],
            "from": {"email": c.CLOUDMAILIN},
            "content":[{"type":"text/plain", "value":""}]
            }
# Note that using cloudmailin as sender makes it possible for recipient to respond

session = remote_session

# twitter
oauth_token = c.twitter_oauth_token 
oauth_token_secret = c.twitter_oauth_token_secret
CONSUMER_KEY = c.twitter_CONSUMER_KEY
CONSUMER_SECRET = c.twitter_CONSUMER_SECRET
tw = Twitter(auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET))

def alarm(task_id):

    try:
        task = session.query(Task).get(task_id)
    except Exception as e:
        print("Could not find task id:",task_id)
        print("Exception: ",e)
        mail_data["personalizations"][0]["subject"] = "Exception trying to find task_id: {}".format(task_id) #subject of the email
        mail_data["content"][0]["value"] = "The exception was: {}".format(e) #body of the email
        response = sg.client.mail.send.post(request_body=mail_data)
        print('mail status code = ',response.status_code)
        #print(response.body)
        return
    
    subject = task.title + " {{" + str(task_id) + "}}"
    body = task.note if task.note else ''
    hints = "| priority: !! or zero or 0; alarm: off; star: star or * or nostar; remind: off"
    header = "star: {}; priority: {}; context: {}; reminder: {}".format(task.star, task.priority, task.context.title, task.remind)
    body = header+hints+"\n==================================================================================\n"+body
    print('Alarm! id:{}; subject:{}'.format(task_id, subject))

    tw.direct_messages.new(user='slzatz', text=subject[:110])

    mail_data["personalizations"][0]["subject"] = subject #subject of the email
    mail_data["content"][0]["value"] = body #body of the email
    response = sg.client.mail.send.post(request_body=mail_data)
    print(response.status_code)
    #print(response.body)

    #starred tasks automatically repeat their alarm every 24h
    if task.star:
        task.duedate = task.duetime = task.duetime + timedelta(days=1)
        session.commit()
        j = scheduler.add_job(alarm, 'date', id=str(task.id), run_date=task.duetime, name=task.title[:15], args=[task.id], replace_existing=True) # shouldn't need replace_existing 
        print("Starred task was scheduled again")
        print('Task id:{}; star: {}; title:{}'.format(task.id, task.star, task.title))
        print("Alarm scheduled: {}".format(repr(j)))

scheduler = BackgroundScheduler()
url = 'sqlite:///scheduler_test.sqlite'
scheduler.add_jobstore('sqlalchemy', url=url)

# On restarting program, want to pick up the latest alarms
tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
print("On restart, there are {} tasks that are being scheduled".format(tasks.count()))
for t in tasks:
    j = scheduler.add_job(alarm, 'date', id=str(t.id), run_date=t.duetime, name=t.title[:50], args=[t.id], replace_existing=True) 
    print('Task id:{}; star: {}; title:{}'.format(t.id, t.star, t.title))
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
    return username ==  c.id and password == c.pw

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

@app.route('/add_task/<int:task_id>/<int:days>/<int:minutes>/<msg>') #0.0.0.0:5000/2145/0/10/how%20are%20you
@requires_auth
def add_task(task_id, days, minutes, msg):
    alarm_time = datetime.now() + timedelta(days=days, minutes=minutes)
    j = scheduler.add_job(alarm, 'date', id=str(task_id), run_date=alarm_time, name=msg[:50], args=[task_id], replace_existing=True)
    z = {'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')}
    return json.dumps(z)

#@app.route("/sync")
#def do_immediate_sync():
#    if sync_in_progress:
#        return Response("There appears to be a sync already going on", mimetype='text/plain')
#    else:
#        j = scheduler.add_job(sync, name="sync")
#        return Response("Initiated sync - check /sync-log to see what happened", mimetype='text/plain')
   
#@app.route("/sync-log")
#def sync_log():
#    if sync_in_progress:
#        return Response("Sync currently underway", mimetype='text/plain')
#    else:
#        with open("sync_log", 'r') as f:
#            z = f.read()
#        return Response(z, mimetype='text/plain')

@app.route("/")
def index():
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')} for j in scheduler.get_jobs())
    return json.dumps(z)

@app.route("/update_alarms")
def update_alarms():
    for j in scheduler.get_jobs():
        j.remove()
    tasks = session.query(Task).filter(and_(Task.remind == 1, Task.duetime > datetime.now()))
    print("On restart or following sync, there are {} tasks that are being scheduled".format(tasks.count()))
    for t in tasks:
        j = scheduler.add_job(alarm, 'date', id=str(t.id), run_date=t.duetime, name=t.title[:50], args=[t.id], replace_existing=True) 
        print('Task id:{}; star: {}; title:{}'.format(t.id, t.star, t.title))
        print("Alarm scheduled: {}".format(repr(j)))

    z = ["id: {} name: {} run date: {}".format(j.id, j.name, j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')) for j in scheduler.get_jobs()]
    return Response('\n'.join(z), mimetype='text/plain')

@app.route("/recent")
def recent():
    tasks = session.query(Task).filter(and_(Task.completed == None, Task.modified > (datetime.now() - timedelta(days=2))))
    tasks2 = session.query(Task).join(Context).filter(and_(Context.title == 'work', Task.priority == 3, Task.completed == None)).order_by(desc(Task.modified))

    z = list(j.id for j in scheduler.get_jobs())
    tasks3 = session.query(Task).filter(Task.id.in_(z))

    return render_template("recent.html", tasks=tasks, tasks2=tasks2, tasks3=tasks3) 
    
@app.route("/incoming", methods=['GET', 'POST'])
def incoming():
    if request.method == 'POST':
        subject = request.form.get('headers[Subject]')
        if subject.lower().startswith('re:'):
            subject = subject[3:].strip()

        pos = subject.find('|')
        if pos != -1:
            title = subject[:pos].strip()
            mods = subject[pos+1:].strip().split()
        else:
            title = subject
            mods = []
        tasks = session.query(Task).filter(Task.title==title).all()
        if len(tasks) > 1:
            print("More than one task had the title: {}".format(title))
            return Response("More than one task had the title: {}".format(title), mimetype='text/plain')
        elif len(tasks) == 1:
            print("There was a match - only one task had the title: {}".format(title))
            task = tasks[0]
            update = True
        else:
            print("No task matched so assuming this is a new task: {}".format(title))
            task = Task(title=title)
            task.startdate = datetime.today().date() 
            session.add(task)
            session.commit()
            update = False

        body = request.form.get('plain')
        pattern = "================="
        pos = body.rfind(pattern)
        note = body[1+pos+len(pattern):] if pos!=-1 else body
        #print(body) 
        task.note = note

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
            if m.startswith('@'):
                context_title = m[1:].replace('_', ' ') # allows you to 'not work' as 'not_work'
                context = session.query(Context).filter_by(title=context_title).first()
                if context:
                    task.context = context
            if m.startswith('*') and len(m) > 1:
                folder_title = m[1:].replace('_', ' ')
                folder = session.query(Folder).filter_by(title=folder_title).first()
                if folder:
                    task.folder = folder

        session.commit()

        text = "Updated task" if update else "Created new task"
        return Response("{} with title: {}".format(text,title), mimetype='text/plain')

    else:
        return 'It was not a post method'

@app.route("/incoming_from_echo", methods=['GET', 'POST'])
def incoming_from_echo():
    if request.method == 'POST':
        data = request.get_json() #this is a python dictionary
        print(data)

        task = Task(title=data.get('title', 'No title'), priority=data.get('priority', 3), star=data.get('star', False))
        task.startdate = datetime.today().date() 
        task.note = data.get('note', "Created from Echo on {}".format(task.startdate))

        session.add(task)
        session.commit()

        context = session.query(Context).filter_by(title=data.get('context', '')).first()
        if context:
            task.context = context

        echo_folder = session.query(Folder).filter_by(title='echo').one()
        task.folder = echo_folder

        session.commit()

        if task.star:
            task.remind = 1
            task.duedate = task.duetime = datetime.now() + timedelta(days=1)
            session.commit()
            j = scheduler.add_job(alarm, 'date', id=str(task.id), run_date=task.duetime, name=task.title[:15], args=[task.id], replace_existing=True) 

        print("Created new task with title: {}, star: {}, context: {}, folder: {}, remind: {}".format(task.title, "yes" if task.star else "no", task.context.title, task.folder.title, "yes" if task.remind else "no"))
        return Response("Created new task with title: {}".format(task.title), mimetype='text/plain')

    else:
        return 'It was not a post method'

@app.route("/scrobble", methods=['POST'])
def scrobble():
    data = request.get_json() #this is a python dictionary
    print(data)

    sonos_track['artist'] = data.get('artist', '')
    sonos_track['title'] = data.get('title', '')
    sonos_track['updated'] = True

    return Response("OK", mimetype='text/plain')
    
#@app.route('/echo/<artist>/<source>') #0.0.0.0:5000/2145/0/10/how%20are%20you
#def echo(artist, source):
#    print(artist)
#    print(source)
#    sonos_companion['artist'] = artist
#    sonos_companion['source'] = source
#    sonos_companion['updated'] = True
#    return json.dumps(sonos_companion)

@app.route('/sonos_check') #0.0.0.0:5000/2145/0/10/how%20are%20you
def sonos_check():
    if sonos_track['updated']:
        temp = dict(sonos_track)
        sonos_track['updated'] = False
        return json.dumps(temp)
    else:
        #return "No Change"
        return json.dumps(sonos_track)

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, use_reloader=False)
