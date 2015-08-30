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

from config import rds_uri

cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
LOCAL_DB_FILE = os.path.join(cwd,'lmdb','mylistmanager.db')
sqlite_uri = 'sqlite:///' + LOCAL_DB_FILE

__all__ = ['Task', 'Context', 'Folder', 'Keyword', 'TaskKeyword', 'Sync', 'Temp_tid', 'local_engine', 'remote_engine', 'metadata', 'sqla_exc', 'sqla_orm_exc', 'local_session', 'remote_session', 'or_', 'and_', 'case', 'literal', 'asc', 'desc']

metadata = MetaData()
task_table = Table('task',metadata,
              Column('id', Integer, primary_key=True),
              Column('tid', Integer), #, unique=True, nullable=False), #the toodledo id ... unique=True, nullable=False), needs to be non-unique because we get the tids on sync
              #Column('parent_tid', Integer, ForeignKey('task.tid'), default=0), # if this column is going to refer to tid, then postgres wanted tid to be unique and not nullable
              Column('priority', Integer, default=1),
              Column('title',String(255)),
              Column('tag',String(64)),
              #Column('folder_tid', Integer, ForeignKey('folder.tid'), default=0), #use the toodledo id
              Column('folder_tid', Integer, ForeignKey('folder.id'), default=0), #use the postgreSQL id
              #Column('context_tid', Integer, ForeignKey('context.tid'), default=0), #use the toodledo id
              Column('context_tid', Integer, ForeignKey('context.id'), default=0), #use the postgrSQL id
              Column('duetime', DateTime),
              Column('star', Boolean, default=False),
              Column('added', Date), # this is the date that it was added to the server (may not be exact for items created on client but should be close) and it's only a date
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
#Additionally, if the user does not have a Pro account, the only valid numbers are 0,60. If you submit an invalid number, 
#it will be rounded up or down to a valid non zero value.

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

temp_tid_table = Table('temp_tid', metadata,
                 Column('id', Integer, primary_key=True),
                 Column('title', String(32)),
                 Column('type_', String(32)),
                 Column('created', DateTime, default=datetime.datetime.now), 
)


keyword_table = Table('keyword', metadata,
                 Column('id',Integer, primary_key=True),
                 Column('name', String(25), unique=True, nullable=False), #note tag is <=65
)
taskkeyword_table = Table('task_keyword', metadata,
                      Column('task_id', Integer, ForeignKey('task.id'), primary_key=True), 
                      Column('keyword_id', Integer, ForeignKey('keyword.id'), primary_key=True), 
)

sync_table = Table('sync', metadata,
                      Column('machine', String(20), primary_key=True), #NYCPSSZATZ1 or dell4300
                      Column('timestamp', DateTime),
                      Column('unix_timestamp', Integer)
)

class Task(object):
    def __init__(self, title=None, tid=None, **kw):
        self.title = title
        self.tid = tid
        for k in kw:
              setattr(self, k, kw[k])

    @property
    def keywords(self):
        return [tk.keyword for tk in self.taskkeywords]

    def __repr__(self):
        return "<Task(%d - '%s')>" % (self.tid if self.tid else 0, self.title)

class Context(object):
    def __init__(self, tid=None, title=None):
        self.tid = tid
        self.title = title

class Folder(object):
    def __init__(self, tid=None, title=None):
        self.tid = tid
        self.title = title
        
class Keyword(object):
    def __init__(self, name=None):
        self.name = name

    @property # allows some methods to deal with keywords like context, folders
    def title(self):
        return self.name
        
class TaskKeyword(object):
    def __init__(self, task=None, keyword=None):
        self.task = task
        self.keyword = keyword
        
class Sync(object):
    def __init__(self, machine, timestamp=None, unix_timestamp=None):
        self.machine = machine
        self.timestamp = timestamp
        self.unix_timestamp = unix_timestamp

class Temp_tid(object):
    def __init__(self, title=None, type_=None):
        self.title = title
        self.type_ = type_

mapper(Context, context_table, properties = {'folders':relation(Folder,
primaryjoin=and_(context_table.c.tid==task_table.c.context_tid,folder_table.c.tid==task_table.c.folder_tid),
viewonly=True, foreign_keys=[folder_table.c.tid], remote_side=[task_table.c.context_tid]), #backref=backref('contexts', remote_side=[task_table.c.folder_tid])),
'tasks':relation(Task, backref='context'),
#'keywords':relation(Keyword, primaryjoin=and_(keyword_table.c.id==taskkeyword_table.c.keyword_id, task_table.c.id==taskkeyword_table.c.task_id, context_table.c.tid==task_table.c.context_tid),
#viewonly=True, foreign_keys=[keyword_table.c.id], remote_side=[task_table.c.context_tid])
})

# note that you can also do:  keywords = session.query(Keyword).join(['taskkeywords','task','context']).filter(Context.title=='Health')

mapper(Task, task_table, 
properties = { #'children':relation(Task, 
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

# note that even if databases don't exist these won't fail
local_engine = create_engine(sqlite_uri, connect_args={'check_same_thread':False}, echo=False)
Local_Session = sessionmaker(bind=local_engine)
local_session = Local_Session()

remote_engine = create_engine(rds_uri, echo=False)
Remote_Session = sessionmaker(bind=remote_engine)
remote_session = Remote_Session()

#metadata.bind = local_engine # I think only necessary if you're issuing a metadata.create_all(engine) command
#metadata.create_all(local_engine) # only creates if tables not present but not

