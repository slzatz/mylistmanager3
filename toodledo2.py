'''
shamelessly stolen with a few mods from felix riedel's poodledo
'''
import os
import sys
import urllib.request, urllib.error, urllib.parse
import urllib.request, urllib.parse, urllib.error
import io
import shutil

import time
import datetime
#import calendar
#import pytz

from hashlib import md5
import json
import base64
import re

try:
    import lmdialogs
except ImportError:
    lmdialogs = None

try:
    import lmglobals as g
except ImportError:
    import lmglobals2 as g
    print_ = print
else:
    print_ = g.logger.write

print_("Hello from the toodledo2 module")

_SERVICE_URL = 'http://api.toodledo.com/2/'

cg = g.config

appid = 'mylistmanager2'

def _date(d):
    '''server sends an integer via JSON not a string and returns 0 for completed when task has not been completed'''
    
    z = datetime.date.fromtimestamp(d) if d else None    
    return z

def _datetime(d):
    #note that duetime seems to come back as a string when it's zero which is why the "if int(d)
    try:
        z = datetime.datetime.fromtimestamp(int(d)) if int(d) else None
    except Exception as value:
        print(d, value)
        z = None
    return z

def _datetimetz(d):
    #note that duetime comes back as a string when it's zero which is why the "if int(d)
    #utcfromtimestamp is essential
    try:
        z = datetime.datetime.utcfromtimestamp(int(d)) if int(d) else None
    except Exception as value:
        print(d, value)
        z = None
    return z

def _boolstr(s):
    return bool(int(s))

#folder:[{"id":"123","name":"Shopping","private":"0","archived":"0","ord":"1"}, ...]  
#context: #[{"id":"123","name":"Work"}, ...]    
# {"userid":"a1b2c3d4e5f6","alias":"John","pro":"0","dateformat":"0","timezone":"-6",
# "hidemonths":"2","hotlistpriority":"3","hotlistduedate":"2","showtabnums":"1",
# "lastedit_folder":"1281457337","lastedit_context":"1281457997","lastedit_goal":"1280441959",
# "lastedit_location":"1280441959","lastedit_task":"1281458832","lastdelete_task":"1280898329",
# "lastedit_notebook":"1280894728","lastdelete_notebook":"1280898329"}
#[{"num":"24"},{"id":"1234","stamp":"1234567891"},{"id":"1235","stamp":"1234567892"}]

#{"id":"265413904","title":"FW: U.S. panel likely to back arthritis drug of Abbott rival
#(Pfz\/tofacitinib)","modified":1336240586,"completed":0,"folder":"0","priority":"0","context":"0","tag":"","note":"From: maryellen [
#...","remind":"0","star":"0","duedate":1336478400,"startdate":0,"added":1336132800,"duetime":1336456800}

_typemap = {
            
            'id': int,
            'name': str,
            'archived': _boolstr,
            'private': _boolstr,
            'order': int,
            'level': int,
            'contributes': int,
            'userid': str,
            'alias': str,
            'pro': _boolstr,
            'dateformat': int,
            'timezone': int,
            'hidemonths': int,
            'hotlistpriority': int,
            'hotlistduedate': int,
            'lastdelete_task': int,
            'lastdelete_notebook': int,
            'lastedit_task': int,
            'lastedit_folder': int,
            'lastedit_context': int,
            'lastedit_goal': int,
            'lastedit_notebook': int,
            'lastedit_location': int,
            'parent': int,
            'children': int,
            'title': str,
            'tag': str,
            'folder': int,
            'context': int,
            'remind': int,
            'goal': int,
            'added': _date,
            'modified': _datetime, # client and server modified not same; based on each platform
            'startdate': _date,
            'duedate': _date,
            'duedatemod': int,
            'starttime': _datetimetz, #_datetimetz uses utcfromtimestamp and that is necessary
            'duetime': _datetimetz,
            'completed': _date,
            'repeat': int,
            'status': int,
            'star': _boolstr,
            'priority': int,
            'length': int,
            'timer': int,
            'timeron': _datetime,
            'note': str,
            'stamp': _datetime, #? in use
            'num': int,
            'total': int

          }

class DotDict(dict):
    def __getattr__(self, attr):
        return self.get(attr, None)
        
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__
    
class ToodledoError(Exception):
    
    def __init__(self, errorcode=None, errordesc=None):
        self.errorcode=errorcode
        self.errordesc=errordesc

    def __str__(self):
        return "{0} - {1}".format(self.errorcode, self.errordesc)
def keycheck():
    
    # we've synched at least once this session so g.key and g.timestamp were created
    if g.key:
        if (datetime.datetime.now() - g.timestamp) < datetime.timedelta(minutes=40, hours=3):
            print_("**used currently active key**")
            delta = g.timestamp + datetime.timedelta(hours=4) - datetime.datetime.now()
            print_("**time left: {0} hours**".format(delta))
            return True
        else:
            result = getnewkey()
            if result:
                print_("**created new key because the key in the ini file had timed out**")
                return True
            else:
                return False

    # we haven't tried to synch yet this session
    if cg.has_section('Toodledo2') and cg.has_option('Toodledo2', 'key') and cg.has_option('Toodledo2', 'timestamp'):
        g.key = key = cg.get('Toodledo2', 'key')
        date_str = cg.get('Toodledo2', 'timestamp')
        try:
            timestamp = datetime.datetime.strptime(date_str,"%Y-%m-%dT%H:%M:%S.%f")
        except:
            timestamp = datetime.datetime.strptime(date_str,"%Y-%m-%dT%H:%M:%S")

        if (datetime.datetime.now() - timestamp) < datetime.timedelta(minutes=40, hours=3):
            print_("**used key stored in ini file**")
            delta = timestamp + datetime.timedelta(hours=4) - datetime.datetime.now()
            print_("**time left: {0} hours**".format(delta))
            g.timestamp = timestamp
            return True
        # key stored in ini had timed out
        else:
            result = getnewkey()
            if result:
                print_("**created new key because the key in the ini file had timed out**")
                return True
            else:
                return False
    # we've never synched or we trashed the ini file            
    else:
        result = getnewkey()
        if result:
            print_("**created new key because there wasn't one in ini file**")
            return True
        else:
            print_("**User abandoned providing email/pw so no key created**")
            return False

def getnewkey():
    
    email = None
    userid = None
      
    if cg.has_section('Toodledo2') and cg.has_option('Toodledo2', 'userid'):
        userid = cg.get('Toodledo2', 'userid')
        
    if cg.has_section('Toodledo2') and cg.has_option('Toodledo2', 'pw'):
        b64pw = cg.get('Toodledo2', 'pw').encode('utf-8') # type(b64pw)==bytes
        #pw = base64.b64decode(b64pw).decode('utf-8') # you don't want to do str(...) before decoding it's bytes
        pw = base64.b64decode(b64pw) #b64decode wants to operate on bytes and returns bytes
    else:
        dlg = lmdialogs.Authenticate("Toodledo Authentication", parent=None)
        if dlg.exec_(): # if cancel - dlg.exec_ is False
            email, pw = dlg.getData()
        else:
            return False
        
    if userid is None:
        b = (email+'api4f7e15dc12cdf').encode('utf-8')
        #m = md5(email+'api4f7e15dc12cdf')
        m = md5(b)
        sig = m.hexdigest()
        url = _SERVICE_URL + 'account/lookup.php'
        data = urllib.parse.urlencode(dict(appid=appid, email=email, pass_=pw, sig=sig)) # pass= doesn't work
        data = data.replace('_=', '=')
        bdata = data.encode('utf-8') #12-20-2014 
        userid = post(url, bdata)['userid']
    
    b = (userid+'api4f7e15dc12cdf').encode('utf-8')
    #m = md5(userid+'api4f7e15dc12cdf')
    m = md5(b)
    sig = m.hexdigest()
    url = _SERVICE_URL + 'account/token.php'
    data = urllib.parse.urlencode(dict(appid=appid, userid=userid, sig=sig)) # pass= doesn't work
    bdata = data.encode('utf-8') #12-20-2014 
    token = post(url, bdata)['token']
    #print(type(token))->unicode str
    #g.key = key = md5(md5(pw).hexdigest() + 'api4f7e15dc12cdf'+ token).hexdigest()
    #pw = pw.encode('utf-8')
    g.key = key = md5((md5(pw).hexdigest() + 'api4f7e15dc12cdf' + token).encode('utf-8')).hexdigest()
    g.timestamp = timestamp = datetime.datetime.now()
    
    if not cg.has_section('Toodledo2'):
        cg.add_section('Toodledo2')
        
    cg.set('Toodledo2', 'key', key)
    cg.set('Toodledo2', 'timestamp', timestamp.isoformat())
    
    if not cg.has_option('Toodledo2', 'userid'):
         cg.set('Toodledo2', 'userid', userid)   
    
    if not cg.has_option('Toodledo2', 'pw'):
        b64pw = base64.b64encode(pw.encode('utf-8')) # type(b64pw)==bytes
        cg.set('Toodledo2', 'pw', b64pw.decode('utf-8')) # need to write a decoded unicode string
        
    return True

def toodledo_call(method, **kwargs):
    
    def convert(dic):
        for x in dic:
            dic[x] = _typemap.get(x, lambda y:y)(dic[x])
        return DotDict(dic)
    
    url = _SERVICE_URL + method +'.php'
    
    kwargs['key'] = g.key ###KEY
    
    data = urllib.parse.urlencode(kwargs)
    data = data.replace('_=', '=')
    bdata = data.encode('utf-8') #12-20-2014 
    request = urllib.request.Request(url, bdata)
    
    # prints an abbreviated note to the log
    if 'tasks' in kwargs:
        unquoted_data = re.sub(r'"note":".*?[^\\]"', lambda x:'{} ..."'.format(x.group(0)[:25]), urllib.parse.unquote_plus(data))
    else:
        unquoted_data = urllib.parse.unquote_plus(data)
        
    print_("url={0}?{1}".format(url, unquoted_data))
    
    stream = urllib.request.urlopen(request)
    #s = io.StringIO()
    #shutil.copyfileobj(stream, s)
    #s.seek(0)
    j_resp = stream.read()
    j_resp = j_resp.decode('utf-8')
    response = json.loads(j_resp)
    
    # prints an abbreviated note to the log
    if '"note":"' in j_resp:
         j_resp = re.sub(r'"note":".*?[^\\]"', lambda x:'{} ..."'.format(x.group(0)[:25]), j_resp)
    
    print_("stream={}".format(j_resp)) 

    if not response:
        return []
        
    if 'errorCode' in response:
        raise ToodledoError(response['errorCode'], response.get('errorDesc', ''))
        
    response = convert(response) if hasattr(response, 'keys') else [convert(d) for d in response]
    
    if not hasattr(response, 'keys') and 'num' in response[0]:
        return response[0],  response[1:]
    else:
        return response
def post(url, bdata):
    request = urllib.request.Request(url, bdata)
    stream = urllib.request.urlopen(request)
    #s = io.StringIO()
    #shutil.copyfileobj(stream, s)
    #s.seek(0)
    #server_response = json.loads(s.read())
    j_resp = stream.read()
    j_resp = j_resp.decode('utf-8')
    server_response = json.loads(j_resp)
    #server_response = json.loads(stream.read())
    
    if 'errorCode' in server_response:
        raise ToodledoError("{0} - {1}".format(server_response['errorCode'], server_response.get('errorDesc', '')))
    else:
        return server_response
        
