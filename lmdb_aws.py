
#@+leo-ver=5-thin
#@+node:slzatz.20141220151846.43: * @file C:/Users/szatz/mylistman_p3/lmdb_aws.py
#@@first
#@@language python
#@@tabwidth -4
#@@nowrap
#@+others
#@+node:slzatz.20120322073931.1687: ** imports
import sys
import os
import datetime
import platform

#Need to put sqlalchemy on the sys.path
home = os.path.split(os.getcwd())[0]
sqla_dir = os.path.join(home,'sqlalchemy','lib')
sys.path = [sqla_dir] + sys.path 

from sqlalchemy import *
from sqlalchemy.orm import *
import sqlalchemy.orm.exc as sqla_orm_exc
import sqlalchemy.exc as sqla_exc

import lmglobals as g
from aws_credentials import rds_uri

#@+node:slzatz.20120322182513.1694: ** __all__
__all__ = ['Task', 'Context', 'Folder', 'Keyword', 'TaskKeyword', 'Sync', 'Temp_tid', 'engine', 'metadata', 'sqla_exc', 'sqla_orm_exc', 'session', 'or_', 'and_', 'case', 'literal', 'asc', 'desc']
#@+node:slzatz.20120322073931.1689: ** Metadata
metadata = MetaData()



#@+node:slzatz.20120322073931.1691: ** Tables
#@+node:slzatz.20120323164545.1707: *3* task_table
task_table = Table('task',metadata,
              Column('id', Integer, primary_key=True),
              Column('tid', Integer), #, unique=True, nullable=False), #the toodledo id ... unique=True, nullable=False), needs to be non-unique because we get the tids on sync
              #Column('parent_tid', Integer, ForeignKey('task.tid'), default=0), # if this column is going to refer to tid, then postgres wanted tid to be unique and not nullable
              Column('priority', Integer, default=1),
              Column('title',String(255)),
              Column('tag',String(64)),
              Column('folder_tid', Integer, ForeignKey('folder.tid'), default=0), #use the toodledo id
              Column('context_tid', Integer, ForeignKey('context.tid'), default=0), #use the toodledo id
              Column('duetime', DateTime),
              Column('star', Boolean, default=False),
              Column('added', Date), # this is the date that it was added to the server (may not be exact for items created on client but should be close) and its only a date
              Column('completed', Date),
              Column('duedate', Date),
              Column('note', Text),
              Column('repeat', Integer),
              Column('deleted', Boolean, default=False),
              Column('created', DateTime, default=datetime.datetime.now), 
              Column('modified', DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now),
              Column('startdate', Date),
              #Column('starttime', Time),
              Column('remind', Integer)
)

#startdate : A GMT unix timestamp for when the task starts. The time component of this timestamp will always be noon

# duetime : A GMT unix timestamp for when the task is due. If the task does not have a time set, then this will be 0. 
#If the task has a duetime without a duedate set, then the date component of this timestamp will be Jan 1, 1970. 
#Times are stored as floating times. In other words, 10am is always 10am, regardless of your timezone. 
#You can convert this timestamp to a GMT string and display the time component without worrying about timezones.

# starttime : A GMT unix timestamp for when the task starts. If the task does not have a time set, then this will be 0. 
#If the task has a starttime without a startdate set, then the date component of this timestamp will be Jan 1, 1970. 
#Times are stored as floating times. In other words, 10am is always 10am, regardless of your timezone. 
#You can convert this timestamp to a GMT string and display the time component without worrying about timezones.

# remind : An integer that represents the number of minutes prior to the duedate/time that a reminder will be sent. 
#Set it to 0 for no reminder. Values will be constrained to this list of 
#valid numbers (0, 1, 15, 30, 45, 60, 90, 120, 180, 240, 1440, 2880, 4320, 5760, 7200, 8640, 10080, 20160, 43200). 
#Additionally, if the user does not have a Pro account, the only valid numbers are 0,60. If you submit an invalid number, it will be
# rounded up or down to a valid non zero value.


#@+node:slzatz.20120323164545.1706: *3* context_table
context_table = Table('context', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('tid', Integer, unique=True, nullable=False), #the toodledo id
                 Column('title', String(32), unique=True, nullable=False), 
                 Column('default', Boolean, default=False),
                 Column('created', DateTime, default=datetime.datetime.now), 
                 Column('deleted', Boolean, default=False),  # need to add this to delete contexts on client
                 Column('icon', String(32)),
                 Column('textcolor', Integer),
                 Column('image', LargeBinary)
)
#@+node:slzatz.20120323164545.1705: *3* folder_table
folder_table = Table('folder', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('tid', Integer, unique=True, nullable=False), #the toodledo id
                 Column('title', String(32), nullable=False),#unique=True - toodledo can have same title
                 Column('private', Boolean, default=False),
                 Column('archived', Boolean, default=False),
                 Column('order', Integer),
                 Column('created', DateTime, default=datetime.datetime.now), 
                 Column('deleted', Boolean, default=False),  # need to add this to delete folders on client
                 Column('icon', String(32)),
                 Column('textcolor', Integer),
                 Column('image', LargeBinary)
)
#@+node:slzatz.20120323164545.1704: *3* temp_tid_table
temp_tid_table = Table('temp_tid', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('title', String(32)),
                 Column('type_', String(32)),
                 Column('created', DateTime, default=datetime.datetime.now), 
)
#@+node:slzatz.20120323164545.1703: *3* keyword_table
keyword_table = Table('keyword', metadata,
                 Column('id',Integer, primary_key=True),
                 Column('name', String(25), unique=True, nullable=False), #note tag is <=65
)
#@+node:slzatz.20120323164545.1702: *3* taskkeyword_table
taskkeyword_table = Table('task_keyword', metadata,
                      Column('task_id', Integer, ForeignKey('task.id'), primary_key=True), 
                      Column('keyword_id', Integer, ForeignKey('keyword.id'), primary_key=True), 
)
#@+node:slzatz.20120323164545.1700: *3* sync_table
sync_table = Table('sync', metadata,
                      Column('machine', String(20), primary_key=True), #NYCPSSZATZ1 or dell4300
                      Column('timestamp', DateTime),
                      Column('unix_timestamp', Integer)
)

#@+node:slzatz.20120323164545.1701: *3* reminder_table - not in use
# reminder_table = Table('reminder', metadata,
                      # Column('uuid', String(32), primary_key=True),
                      # Column('item_uuid', String(32), ForeignKey('item.uuid'), nullable=False),
                      # Column('method', String(5)),
                      # Column('period', String(5)),
                      # Column('rdate', String(4)),
                      # Column('rtime', String(4)),
                      # Column('deleted', Boolean, default=False),
                      # Column('timestamp', DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now),                       
#)
#@+node:slzatz.20120322073931.1693: ** Classes
#@+node:slzatz.20120323164545.1715: *3* Task
class Task(object):
    def __init__(self, title=None, tid=None, **kw):
        self.title = title
        self.tid = tid
        for k in kw:
              setattr(self, k, kw[k])

#@verbatim
    #@property
    #def age(self):
        #return datetime.datetime.now() - self.modified

    @property
    def keywords(self):
        return [tk.keyword for tk in self.taskkeywords]

    def __repr__(self):
        return "<Task(%d - '%s')>" % (self.tid if self.tid else 0, self.title)

#@+node:slzatz.20120323164545.1714: *3* Context
class Context(object):
    def __init__(self, tid=None, title=None):
        self.tid = tid
        self.title = title

#@+node:slzatz.20120323164545.1713: *3* Folder
class Folder(object):
    def __init__(self, tid=None, title=None):
        self.tid = tid
        self.title = title
        
#@+node:slzatz.20120323164545.1708: *3* Keyword
class Keyword(object):
    def __init__(self, name=None):
        self.name = name

    @property # allows some methods to deal with keywords like context, folders
    def title(self):
        return self.name
        
#@+node:slzatz.20120323164545.1709: *3* TaskKeyword
class TaskKeyword(object):
    def __init__(self, task=None, keyword=None):
        self.task = task
        self.keyword = keyword
        
#@+node:slzatz.20120323164545.1710: *3* Sync
class Sync(object):
    def __init__(self, machine, timestamp=None, unix_timestamp=None):
        self.machine = machine
        self.timestamp = timestamp
        self.unix_timestamp = unix_timestamp

#@+node:slzatz.20120323164545.1711: *3* Temp_tid
class Temp_tid(object):
    def __init__(self, title=None, type_=None):
        self.title = title
        self.type_ = type_

#@+node:slzatz.20120323164545.1712: *3* Reminder - not in use
# class Reminder(object):
    # def __init__(self, uuid=None, **kw):
        # if uuid:
            # self.uuid = uuid
        # else:
            # self.uuid = get_uuid()
        # for k in kw:
            # setattr(self, k, kw[k])
            
#@+node:slzatz.20120322073931.1695: ** Mappers
mapper(Context, context_table, properties = {'folders':relation(Folder,
primaryjoin=and_(context_table.c.tid==task_table.c.context_tid,folder_table.c.tid==task_table.c.folder_tid),
viewonly=True, foreign_keys=[folder_table.c.tid], remote_side=[task_table.c.context_tid]), #backref=backref('contexts', remote_side=[task_table.c.folder_tid])),
'tasks':relation(Task, backref='context'),
#'keywords':relation(Keyword, primaryjoin=and_(keyword_table.c.id==taskkeyword_table.c.keyword_id, task_table.c.id==taskkeyword_table.c.task_id, context_table.c.tid==task_table.c.context_tid),
#viewonly=True, foreign_keys=[keyword_table.c.id], remote_side=[task_table.c.context_tid])
})

# note can also do:  keywords = session.query(Keyword).join(['taskkeywords','task','context']).filter(Context.title=='Health')

mapper(Task, task_table, 
properties = { #'children':relation(Task, 
#remote_side=[task_table.c.parent_tid], 
#backref=backref('parent', remote_side=[task_table.c.tid])),
'taskkeywords':relation(TaskKeyword, lazy=True, backref='task') #was lazy=False; note that he default loader strategy is lazy=True so it isn't necessary here
})

mapper(Folder, folder_table, properties = {
'tasks':relation(Task, backref='folder')
})

mapper(Keyword, keyword_table)

mapper(TaskKeyword, taskkeyword_table, properties= {
'keyword': relation(Keyword, lazy=False, backref='taskkeywords')})

mapper(Sync, sync_table)

mapper(Temp_tid, temp_tid_table)

#mapper(Reminder, reminder_table) 

engine = create_engine(rds_uri, echo=True)
metadata.bind = engine
metadata.create_all(engine)

#@+node:slzatz.20120322073931.1697: ** Session
Session = sessionmaker()
Session.configure(bind=engine)
session = Session()

#@+node:slzatz.20120322073931.1699: ** run
def run():

    #cwd = os.getcwd()
    #PARENT_DIRECTORY,APPLICATION_DIRECTORY = os.path.split(cwd) #/home/slzatz/, wxToodledo
    #DB_FILE = os.path.join(cwd,'lmdb/mylistmanager.db')

    engine = create_engine('sqlite:///'+g.DB_FILE, echo=False)
    #engine2 = create_engine('sqlite:///:memory:', echo=True)

    metadata.bind = engine #not sure you need to bind metadata to an engine if you're not going to create/drop tables; may need this if session not bound to an engine
    #metadata2.bind = engine2
    return engine

#@-others
#@-leo
