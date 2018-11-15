#!bin/python
'''
Python 3 only
Uses Sendgrid to send email, CloudMailin to receive mail as HTTP posts, Twitter to send direct messages
and sends mqtt messages to display_info_photos.py via the mqtt broker that is also running on this AWS EC2
'''
from datetime import datetime, timedelta
import sys
import os
import json
import re 
#from os.path import expanduser
#home = expanduser('~')
import config as c
#sys.path =  [os.path.join(home,'sqlalchemy','lib')] + [os.path.join(home, 'twitter')] + sys.path #sqlalchemy is imported by apscheduler
from flask import Flask, request, Response, render_template
from twitter import *
from lmdb_aws import *
from apscheduler.schedulers.background import BackgroundScheduler
import sendgrid
import paho.mqtt.publish as mqtt_publish 
from random import shuffle

# using Sendgrid to send alarm messages
sg = sendgrid.SendGridAPIClient(apikey=c.SENDGRID_API_KEY)
mail_data = {
            "personalizations": [{"to":[{"email": "slzatz@gmail.com"}, {"email":"szatz@webmd.net"}], "subject":""}],
            "from": {"email": c.CLOUDMAILIN},
            "content":[{"type":"text/plain", "value":""}]
            }
# Note that using cloudmailin as sender makes it possible to respond to an alert email
# and update the item that generated the email although really not using this feature much if at all

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
        return
    
    subject = task.title + " [" + str(task_id) + "]"
    body = task.note if task.note else ''
    hints = "| priority: !! or zero or 0; alarm/remind: (on, remind, alarm) or (off, noremind, noalarm); star: (star, *) or nostar"
    header = "star: {}; priority: {}; context: {}; reminder: {}".format(task.star, task.priority, task.context.title, task.remind)
    print('Alarm! id:{}; subject:{}'.format(task_id, subject))

    tw.direct_messages.new(user='slzatz', text=subject[:110])

    mail_data["personalizations"][0]["subject"] = subject #subject of the email
    mail_data["content"][0]["value"] = header+hints+"\n==================================================================================\n"+body
    response = sg.client.mail.send.post(request_body=mail_data)
    print(response.status_code)

    text = ["#{red}"+subject]
    text.extend(body.split("\n"))

    mqtt_publish.single('esp_tft', json.dumps({"header":"Reminder", "text":text, "pos":12, "font_size":14, "bullets":False, "color":(255,0,0)}), hostname='localhost', retain=False, port=1883, keepalive=60)

scheduler = BackgroundScheduler()
url = 'sqlite:///scheduler_test.sqlite'
scheduler.add_jobstore('sqlalchemy', url=url)

app = Flask(__name__)

#settings.py
#HOST = '0.0.0.0'
#DEBUG = True

app.config.from_pyfile('flask_settings.py')
HOST = app.config['HOST'] 
DEBUG = app.config['DEBUG']
PORT = app.config['PORT']
#PORT = 5000

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

@app.route("/")
def index():
    z = list({'id':j.id, 'name':j.name, 'run_date':j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')} for j in scheduler.get_jobs())
    return json.dumps(z)

@app.route("/update_alarms")
def update_alarms():
    # delete all existing alarms since apscheduler has no knowledge of how db may have changed
    for j in scheduler.get_jobs():
        j.remove()

    tasks = session.query(Task).filter(Task.remind==1, Task.completed==None, Task.duetime>datetime.now())
    print("On restart or following sync, there are {} tasks that are being scheduled".format(tasks.count()))
    z = []
    for t in tasks:
        j = scheduler.add_job(alarm, 'date', id=str(t.id), run_date=t.duetime, name=t.title[:50], args=[t.id], replace_existing=True) 
        z.append("id: {} name: {} run date: {}".format(j.id, j.name, j.trigger.run_date.strftime('%a %b %d %Y %I:%M %p')))

        print('Task id:{}; star: {}; title:{}'.format(t.id, t.star, t.title))
        print("Alarm scheduled: {}".format(repr(j)))

    return Response('\n'.join(z), mimetype='text/plain')

@app.route("/recent")
def recent():
    tasks = session.query(Task).filter(and_(Task.completed == None, Task.modified > (datetime.now() - timedelta(days=2))))
    tasks2 = session.query(Task).join(Context).filter(and_(Context.title == 'work', Task.priority == 3, Task.completed == None)).order_by(desc(Task.modified))

    z = list(j.id for j in scheduler.get_jobs())
    tasks3 = session.query(Task).filter(Task.id.in_(z))

    return render_template("recent.html", tasks=tasks, tasks2=tasks2, tasks3=tasks3) 
    
# not really using this but allows you to update the info box of starred todos
@app.route("/starred_work_todos")
def starred_work_todos():
    tasks = session.query(Task).join(Context).filter(Context.title=='work', Task.priority==3, Task.completed==None, Task.deleted==False)
    titles = ['#'+task.title if task.star else task.title for task in tasks]
    shuffle(titles)
    print(datetime.now())
    print(repr(titles).encode('ascii', 'ignore'))
    data = {"header":"To Do", "text":titles, "pos":3} #text value is a list
    mqtt_publish.single('esp_tft', json.dumps(data), hostname='localhost', retain=False, port=1883, keepalive=60)
    return "\n".join(titles)
#testin

@app.route("/test", methods=['GET', 'POST'])
def test():
    if request.method == 'POST':
        subject = request.form.get('thisIsA')
        print(subject)
        return "OK"

# emails coming in from cloudmailin
@app.route("/incoming", methods=['GET', 'POST'])
def incoming():
    '''This works for email2http which allows us to let a specific ip address in'''
    if request.method == 'POST':
        subject = request.form.get('subject')
        #subject = request.form.get('thisIsA')
        #print(subject)
        #return "OK"
        if subject[:3].lower() in ('re:', 'fw:'):
            subject = subject[3:].strip()
        elif subject[:4].lower() == 'fwd:': 
            subject = subject[4:].strip()
        body = request.form.get('body')
        id_ = None
        p = re.compile('{{[^"]*}}')  
        m = p.search(subject)
        if m:
            begin,end = m.span()
            id_ = int(subject[begin+2:end-2])
            subject = subject[:begin] + subject[end:]
        
        #pos = subject.find('|')
        pos = subject.find('@') #the start of the task mods is the context flag
        if pos != -1:
            mods = subject[pos:].strip().split()
            subject = subject[:pos].strip()
        elif body.find("Maryellen Wiess") != -1:
            pos = body.find("Maryellen Wiess, 64 Sixth Street, Wood Ridge, NJ 07075")
            body = body[:pos if pos!=-1 else len(body)+1] 
            pos = body.find(subject)
            if pos != -1:
                pos = body.find(subject, pos+len(subject))
                if pos != -1:
                    body = body[pos+len(subject):]
            mods = ['@industry', '!!!', '*'] 
        else:
            #mods = []
            # if no @context then assume work, priority 3 and a star
            mods = ['@work', '!!!', '*'] 
        print("subject =",subject) 
        if id_:
            task = session.query(Task).get(id_)
            task.title = subject
            print("There was an id: {} so assuming this is a modification of an existing task: {}".format(id_,subject))
        else:
            print("There was no id so assuming this is a new task: {}".format(subject))
            task = Task(title=subject)
            task.startdate = datetime.today().date() 
            session.add(task)
            session.commit()

        #body = request.form.get('plain')
        pattern = "================="
        pos = body.rfind(pattern)
        note = body[1+pos+len(pattern):] if pos!=-1 else body
        #print(body) 
        task.note = note.strip()

        for m in mods:
            if '!' in m:
                task.priority = len(m) if len(m) < 4 else 3
            if m in ('0', 'zero'):
                task.priority = 0
            if m == 'nostar':
                task.star = False
            if m in ('*', 'star'):
                task.star = True
            if m in ('off', 'noremind', 'noalarm'):
                task.remind = 0
            if m in ('on', 'remind', 'alarm'):
                task.remind = 1
                task.duedate = task.duetime = datetime.now() + timedelta(days=1)
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

        #update_alarms() # added that alarms should be updated when new or modified tasks are received by email 02012017
        if task.star and task.remind:
            j = scheduler.add_job(alarm, 'date', id=str(task.id), run_date=datetime.now()+timedelta(days=1), name=task.title[:15], args=[task.id], replace_existing=True) # shouldn't need replace_existing 
            print("Incoming email was starred and remind so task was scheduled")
            print('Task id:{}; star: {}; title:{}'.format(task.id, task.star, task.title))
            print("Alarm scheduled: {}".format(repr(j)))

    else:
        print("It was not a post method")

    return "OK"

def incoming_old():
    '''This worked for cloudmailin which did not have the option to let a single ip address in'''
    if request.method == 'POST':
        subject = request.form.get('headers[Subject]')
        #subject = request.form.get('thisIsA')
        #print(subject)
        #return "OK"
        if subject[:3].lower() in ('re:', 'fw:'):
            subject = subject[3:].strip()
        elif subject[:4].lower() == 'fwd:': 
            subject = subject[4:].strip()
        body = request.form.get('plain')
        id_ = None
        p = re.compile('{{[^"]*}}')  
        m = p.search(subject)
        if m:
            begin,end = m.span()
            id_ = int(subject[begin+2:end-2])
            subject = subject[:begin] + subject[end:]
        
        #pos = subject.find('|')
        pos = subject.find('@') #the start of the task mods is the context flag
        if pos != -1:
            mods = subject[pos:].strip().split()
            subject = subject[:pos].strip()
        elif body.find("Maryellen Wiess") != -1:
            pos = body.find("Maryellen Wiess, 64 Sixth Street, Wood Ridge, NJ 07075")
            body = body[:pos if pos!=-1 else len(body)+1] 
            pos = body.find(subject)
            if pos != -1:
                pos = body.find(subject, pos+len(subject))
                if pos != -1:
                    body = body[pos+len(subject):]
            mods = ['@industry', '!!!', '*'] 
        else:
            #mods = []
            # if no @context then assume work, priority 3 and a star
            mods = ['@work', '!!!', '*'] 
        print("subject =",subject) 
        if id_:
            task = session.query(Task).get(id_)
            task.title = subject
            print("There was an id: {} so assuming this is a modification of an existing task: {}".format(id_,subject))
        else:
            print("There was no id so assuming this is a new task: {}".format(subject))
            task = Task(title=subject)
            task.startdate = datetime.today().date() 
            session.add(task)
            session.commit()

        #body = request.form.get('plain')
        pattern = "================="
        pos = body.rfind(pattern)
        note = body[1+pos+len(pattern):] if pos!=-1 else body
        #print(body) 
        task.note = note.strip()

        for m in mods:
            if '!' in m:
                task.priority = len(m) if len(m) < 4 else 3
            if m in ('0', 'zero'):
                task.priority = 0
            if m == 'nostar':
                task.star = False
            if m in ('*', 'star'):
                task.star = True
            if m in ('off', 'noremind', 'noalarm'):
                task.remind = 0
            if m in ('on', 'remind', 'alarm'):
                task.remind = 1
                task.duedate = task.duetime = datetime.now() + timedelta(days=1)
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

        #update_alarms() # added that alarms should be updated when new or modified tasks are received by email 02012017
        if task.star and task.remind:
            j = scheduler.add_job(alarm, 'date', id=str(task.id), run_date=datetime.now()+timedelta(days=1), name=task.title[:15], args=[task.id], replace_existing=True) # shouldn't need replace_existing 
            print("Incoming email was starred and remind so task was scheduled")
            print('Task id:{}; star: {}; title:{}'.format(task.id, task.star, task.title))
            print("Alarm scheduled: {}".format(repr(j)))

    else:
        print("It was not a post method")

    return "OK"

# update alarms before restarting scheduler
update_alarms()
scheduler.start()

if __name__ == '__main__':
    app.run(host=HOST, debug=DEBUG, port=PORT, use_reloader=False)
