'''
script to create an sql database from an existing postgresql one.  Why might this be necessary?
The way that the various ids and tids work, if you recreate the postgresql database, you also need
to recreate the sqlite database since for instance tasks are linked between the two databases because
the postgresql task ids become the sqlite task tids and if you recreate the postgresql database, those
ids change because of deletions.
'''

import datetime
import os
import sys
import lmglobals_s as g

db_directory = os.path.split(g.LOCAL_DB_FILE)[0]
print("db_directory=",db_directory)
try:
    os.mkdir(db_directory)
except OSError as e:
    print(e)
    sys.exit("Could not create directory for sqlite database")

from lmdb_s import * 
import lmdb_p as p

remote_engine = p.remote_engine
print(remote_engine)
remote_session = p.remote_session
print(remote_session)
sqlite_session = local_session ###########################################################
print(sqlite_session)

def createnewsqlitedb():

    # eliminate tasks with ids < 4 because I SetItemData based on sqlite id but if that data is < 4, I know it's a collapse bar
    # so I don't want a real task to have an id < 4
    # fortunately right now sqlite doesn't reclaim the ids of deleted items
    # sqlite starts numbering ids at 1
    
    # this creates the tasks and then deletes them to consume the 1 through 3 ids; don't need/can't delete -1
    
    for i in range(3): 
        task = Task('p')
        sqlite_session.add(task)
    
    sqlite_session.commit()
    
    for i in range(1,4):
        task = sqlite_session.query(Task).get(i)
        if task: # shouldn't need this 
            sqlite_session.delete(task)
    
    sqlite_session.commit()

    print("Starting the process of downloading tasks from server")

    remote_contexts = remote_session.query(p.Context)
    remote_folders = remote_session.query(p.Folder)
    len_contexts = remote_session.query(p.Context).count()
    len_folders = remote_session.query(p.Folder).count()

    print("{} server contexts were downloaded".format(len_contexts))
    print("{} server folders were downloaded".format(len_folders))
    

    #server contexts --> client contexts       
    for rc in remote_contexts:
        context = Context()
        # the sqlite context.tid gets set to the postgres context.id
        # note the the postgres context.tid holds the toodledo context id
        context.tid = rc.id
        context.title = rc.title
        sqlite_session.add(context)
        sqlite_session.commit()
        
    #server folders --> client folders    
    for rf in remote_folders:
        folder = Folder()
        # the sqlite folder.tid gets set to the postgres folder.id
        # note the the postgres folder.tid holds the toodledo folder id
        folder.tid = rf.id
        folder.title = rf.title
        folder.archived = rf.archived
        folder.private = rf.private
        folder.order= rf.order
        sqlite_session.add(folder)
        sqlite_session.commit()
        
    #server tasks -> client tasks
    n=1
    y=250
    while 1:
        remote_tasks = remote_session.query(p.Task).filter(and_(p.Task.id >= n, p.Task.id <= n + y -1))
        #remote_tasks = remote_session.query(p.Task)
        #len_tasks = remote_session.query(p.Task).count()
        len_tasks = remote_tasks.count()
        print("{} server tasks were downloaded".format(len_tasks))

        if len_tasks==0:
            break

        for rt in remote_tasks:
            #if t.context_id != 1633429:     #if you only want to download one context
                #continue                            # might also not want to pick up folders and contexts
            
            task = Task()
            sqlite_session.add(task)
            
            # the sqlite task.tid gets set to the postgres task.id
            # note the the postgres task.tid holds the toodledo task id
            task.tid = rt.id 
            
            task.context_tid = rt.context_tid #local sqlite task.context_tid is the same as server task.context_tid but foreign key is different (c.id v. c.tid)        
            task.duedate = rt.duedate          
            task.folder_tid = rt.folder_tid
            task.title = rt.title
            task.added = rt.added                
            task.star = rt.star
            task.priority = rt.priority
            task.tag = rt.tag
            task.completed = rt.completed    
            task.note = rt.note
            task.remind = rt.remind
            
            # the two lines below were missing and not being pulled off toodledo - not sure why and I added them
            task.duetime = rt.duetime if rt.duetime else None
            task.startdate = rt.startdate if rt.startdate else rt.added 

            try:
                sqlite_session.commit()
            except sqla_exc.IntegrityError as e:
                sqlite_session.rollback()
                print(repr(e))
                print(task.title)
            else:
                if task.tag:

                    for kwn in task.tag.split(','):
                        keyword = sqlite_session.query(Keyword).filter_by(name=kwn).first()
                        if keyword is None:
                            keyword = Keyword(kwn[:25])
                            sqlite_session.add(keyword)
                            sqlite_session.commit()
                        tk = TaskKeyword(task,keyword)
                        sqlite_session.add(tk)

                    try:
                        sqlite_session.commit()
                    except sqla_exc.IntegrityError as e:
                        sqlite_session.rollback()
                        print(repr(e))
                        print(task.title)

        n+=y

    
    
    client_sync = Sync('client')
    sqlite_session.add(client_sync)
    server_sync = Sync('server')
    sqlite_session.add(server_sync)
    sqlite_session.commit()

    #Update synch timestamps
    client_sync = sqlite_session.query(Sync).get('client')
    client_sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=2) # (was 5) giving a little buffer if the db takes time to update on client or server

    server_sync = sqlite_session.query(Sync).get('server')
    connection = remote_engine.connect()
    result = connection.execute("select extract(epoch from now())")
    server_sync.timestamp = datetime.datetime.fromtimestamp(result.scalar()) + datetime.timedelta(seconds=2)
    sqlite_session.commit()  

    print("New Sync times")
    print("client timestamp: {}".format(client_sync.timestamp.isoformat(' ')))
    print("server timestamp: {}".format(server_sync.timestamp.isoformat(' ')))

    print("***************** END SYNC *******************************************")
    

