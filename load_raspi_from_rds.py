'''
script used to recreate postgresql listmanager db on a raspberry pi from the one
that was located on AWS RDS
Also was then created a load_ec2_from_raspi to do the reverse
'''

import datetime
from lmdb_pi import * 
import lmdb_p as p
import lmglobals_pi as g

rds_session = p.remote_session

def transfer_tasks_from_rds():
    '''
    this version downloads tasks from toodledo to a database that can be postgreSQL or sqlite and located anywhere
    This does replace the toodledo tid used in task.folder_tid and task.context_tid to use the postgres folder and context ids
    '''

    print("Starting the process of transferring tasks from server")
    
    rds_tasks = rds_session.query(p.Task)
    rds_contexts = rds_session.query(p.Context)
    rds_folders = rds_session.query(p.Folder)
    
    len_contexts = rds_session.query(p.Context).count()
    len_folders = rds_session.query(p.Folder).count()
    len_tasks = rds_session.query(p.Task).count()

    print("{} server tasks were downloaded".format(len_tasks))
    print("{} server contexts were downloaded".format(len_contexts))
    print("{} server folders were downloaded".format(len_folders))

    #server contexts --> client contexts       
    n=0 
    for rc in rds_contexts:
        context = Context()
        n+=1
        # the sqlite context.tid gets set to the postgres context.id
        # note the the postgres context.tid holds the toodledo context id
        context.tid = rc.tid ##########################################
        context.title = rc.title
        raspi_session.add(context)
        raspi_session.commit()
        

    #server folders --> client folders    
    for rf in rds_folders:
        folder = Folder()
        n+=1
        # the sqlite folder.tid gets set to the postgres folder.id
        # note the the postgres folder.tid holds the toodledo folder id
        folder.tid = rf.tid #############################
        folder.title = rf.title
        folder.archived = rf.archived
        folder.private = rf.private
        folder.order= rf.order
        raspi_session.add(folder)
        raspi_session.commit()
        

    #server tasks -> client tasks
    for rt in rds_tasks:
        n+=1
        #if t.context_id != 1633429:     #if you only want to download one context
            #continue                            # might also not want to pick up folders and contexts
        
        task = Task()
        raspi_session.add(task)
        
         # the sqlite task.tid gets set to the postgres task.id
        # note the the postgres task.tid holds the toodledo task id
        task.tid = rt.tid #################################################### 
        
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

#        try:
#            task.parent_tid = t.parent #only in pro accounts
#        except:
#            pass
#
        try:
            raspi_session.commit()
        except sqla_exc.IntegrityError as e:
            raspi_session.rollback()
            print(repr(e))
            print(task.title)
        else:
            if task.tag:

                for kwn in task.tag.split(','):
                    keyword = raspi_session.query(Keyword).filter_by(name=kwn).first()
                    if keyword is None:
                        keyword = Keyword(kwn[:25])
                        raspi_session.add(keyword)
                        raspi_session.commit()
                    tk = TaskKeyword(task,keyword)
                    raspi_session.add(tk)

                #session.commit()
                try:
                    raspi_session.commit()
                except sqla_exc.IntegrityError as e:
                    raspi_session.rollback()
                    print(repr(e))
                    print(task.title)
    
    
    #Update synch timestamps
    client_sync = raspi_session.query(Sync).get('client')
    client_sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=2) # (was 5) giving a little buffer if the db takes time to update on client or server

    #sync.unix_timestamp = int(time.time()+2) #was 5, changed 01-24-2015
    server_sync = raspi_session.query(Sync).get('server')
    connection = rds_engine.connect()
    result = connection.execute("select extract(epoch from now())")
    server_sync.timestamp = datetime.datetime.fromtimestamp(result.scalar()) + datetime.timedelta(seconds=2)
    #server_sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=2) # (was 5) giving a little buffer if the db takes time to update on client or server
    raspi_session.commit()  

    print("New Sync times")
    print("client timestamp: {}".format(client_sync.timestamp.isoformat(' ')))
    print("server timestamp: {}".format(server_sync.timestamp.isoformat(' ')))

    print("***************** END SYNC *******************************************")
    

