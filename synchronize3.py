'''
module to sync remote sql-based server (currently postgreSQL) database with a local (currently sqlite) database
But confusingly the downloadtasksfromserver is about downloading from toodledo to sql-based server with
the additional factor that you want to run the sql-based server in front of the local database such that the
local server cannot synch directly with toodledo only the remote server can.
'''

import os
import time
import sys
import datetime
import calendar
import platform
import json
import urllib.request, urllib.parse, urllib.error
import base64
from functools import partial
import toodledo2
from lmdb import *

try:
    import lmglobals as g
    import lmdialogs
except ImportError:
    print_ = print
    pb = None
else:
    print_ = g.logger.write #this is not created until after listmanager is instantiated although it probably could be
    pb = g.pb

print_("Hello from the synchronize3 module")

def synchronize(parent=None, showlogdialog=True, OkCancel=False, local=True): # if running outside gui, the showdialog=False, OKCancel=False
    '''
    This synch is designed to be between postgreSQL and sqlite.  It is not the synch between toodledo and postgreSQL
    '''
    nn = 0

    changes = [] #server changed context and folder
    tasklist= [] #server changed tasks
    deletelist = [] #server deleted tasks

    session = local_session if local else remote_session
    print(session.get_bind())
    toodledo_call = toodledo2.toodledo_call

    print_("****************************** BEGIN SYNC (JSON) *******************************************")
        
    log = ''

    sync = local_session.query(Sync).get('client') 

    last_client_sync = sync.timestamp #these both measure the same thing - the last time the Listmanager db (note it could be local or in the cloud) synched with postgreSQL
    last_server_sync = sync.unix_timestamp #this is the same time as above expressed as a timestamp - could obviously just convert between them and not store both; avoids timezone issues

    log+= "LISTMANAGER SYNCRONIZATION\n"
    log+="Local\n" if local else "Remote\n"
    log+= "Local Time is {0}\n\n".format(datetime.datetime.now())
    delta = datetime.datetime.now() - last_client_sync
    log+= "The last time client & server were synced (based on client clock) was {0}, which was {1} days and {2} minutes ago.\n".format(last_client_sync.isoformat(' ')[:19], delta.days, delta.seconds/60)
    log+= "Unix timestamp (client clock) for last sync is {0} ---> {1}\n".format(last_server_sync, datetime.datetime.fromtimestamp(last_server_sync).isoformat(' ')[:19])

    #get new server contexts
    server_new_contexts = remote_session.query(Context).filter(Context.created > last_server_sync).all()
    if server_new_contexts:
        nn+=len(server_new_contexts)
        log+= "New server Contexts added since the last sync: {0}.\n".format(len(server_new_contexts))
    else:
        log+="There were no new server Contexts added since the last sync.\n"   
            
    #get new server folders
    server_new_folders = remote_session.query(Folder).filter(Folder.created > last_server_sync).all() 
    if server_new_folders:
        nn+=len(server_new_folders) 
        log+= "New server Folders added since the last sync: {0}.\n".format(len(server_new_folders))
    else:
        log+="There were no new server Folders added since the last sync.\n"    

    #get server updated tasks
    server_updated_tasks = remote_session.query(Task).filter(and_(Task.modified > last_server_sync, Task.deleted==False)).all()

    if server_updated_tasks:
        nn+=len(server_updated_tasks)
        log+="Updated (new and modified) server Tasks since the last sync: {0}.\n".format(len(server_updated_tasks))
    else:
        log+="There were no updated (new and modified) server Tasks since the last sync.\n" 

    #get server deleted tasks
    server_deleted_tasks = remote_session.query(Task).filter(Task.deleted==True).all()
    if server_deleted_tasks:
        nn+=len(server_deleted_tasks)
        log+="Deleted server Tasks since the last sync: {0}.\n".format(len(server_deleted_tasks))
    else:
        log+="There were no server Tasks deleted since the last sync.\n" 

    log+="\nThe total number of changes is {0}.\n".format(nn)
    ####################################################################################################################################################
    #####################################################################################################################################################################
    #get new local  contexts
    client_new_contexts = local_session.query(Context).filter(Context.created > last_client_sync).all()
    if client_new_contexts:
        nn+=len(client_new_contexts)
        log+= "New client Contexts added since the last sync: {0}.\n".format(len(client_new_contexts))
    else:
        log+="There were no new client Contexts added since the last sync.\n"   
            

    alternate_client_new_contexts = local_session.query(Temp_tid).filter_by(type_='context').all()

    if alternate_client_new_contexts:
        log+= "Alternate method: New client Contexts added since the last sync: {0}.\n".format(len(alternate_client_new_contexts))
    else:
        log+="Alternate method: There were no new client Contexts added since the last sync.\n\n"        
    #get new local folders
    client_new_folders = local_session.query(Folder).filter(Folder.created > last_client_sync).all() 
    if client_new_folders:
        nn+=len(client_new_folders) 
        log+= "New client Folders added since the last sync: {0}.\n".format(len(client_new_folders))
    else:
        log+="There were no new client Folders added since the last sync.\n"    


    alternate_client_new_folders = local_session.query(Temp_tid).filter_by(type_='folder').all()

    if alternate_client_new_folders:
        log+= "Alternate method: New client Folders added since the last sync: {0}.\n".format(len(alternate_client_new_folders))
    else:
        log+="Alternate method: There were no new client Folders added since the last sync.\n\n"        
    #get new local tasks
    client_updated_tasks = local_session.query(Task).filter(and_(Task.modified > last_client_sync, Task.deleted==False)).all()

    if client_updated_tasks:
        nn+=len(client_updated_tasks)
        log+="Updated (new and modified) client Tasks since the last sync: {0}.\n".format(len(client_updated_tasks))
    else:
        log+="There were no updated (new and modified) client Tasks since the last sync.\n" 



    #get local deleted tasks
    client_deleted_tasks = local_session.query(Task).filter(Task.deleted==True).all()
    #client_deleted_tasks = local_session.query(Task).filter(and_(Task.modified > last_client_sync, Task.deleted==True, Task.tid != None)).all()
    if client_deleted_tasks:
        nn+=len(client_deleted_tasks)
        log+="Deleted client Tasks since the last sync: {0}.\n".format(len(client_deleted_tasks))
    else:
        log+="There were no client Tasks deleted since the last sync.\n" 


    log+="\nThe total number of changes is {0}.\n".format(nn)

    if showlogdialog and OkCancel:

        dlg = lmdialogs.SynchResults("Synchronization Results", log, parent=parent, OkCancel=True)

        if not dlg.exec_():
            return "Canceled sync", [], [], []

    nnn=0

    if pb:
        pb.setRange(0, nn)
        pb.setValue(nnn)
        pb.show()
    # put new server contexts on the client
    for sc in server_new_contexts:

        # not sure there is any reason that this new server context would be on the client
        try:
            context = local_session.query(Context).filter_by(tid=sc.id).one()
            
        except sqla_orm_exc.NoResultFound:
              
            context = Context()
            local_session.add(context)
            context.tid = sc.id # note that this allows you to go from server supplied context tid to postgreSQL supplied Context.id
            
            log += "{title} is a new context received from the server\n".format(title=sc.title)

        context.title = sc.title
        
        try:
            local_session.commit()
            
        except sqla_exc.IntegrityError:
            local_session.rollback()
            # probably means we ran into the unusual circumstance where context was simultaneously created on client and server
            context.title = sc.title+' from server'
            local_session.commit()
            
            log += "{title} is a new context received from the server but it was a dupe of new client context\n".format(title=sc.title)
        
        nnn+=1

        if pb:
            pb.setValue(nnn)

    # put new client contexts on the server
    for c in client_new_contexts: # this is where we could check for simultaneous creation of folders by checking for title in server_folders

        temp_tid = c.tid

        # note that there could be a context with this title (created by another client) since last sync with current client

        try:
            server_context = remote_session.query(Context).filter_by(title=c.title).one()

        except sqla_orm_exc.NoResultFound:

            context = Context(title=c.title)
            remote_session.add(context)
            remote_session.commit()
            
            server_context = remote_session.query(Context).filter_by(title=c.title).one()

            log += "{title} is a new context received from the server\n".format(title=sc.title)
            print_("There was a problem adding new client context {} to the server".format(c.title))

        server_tid = server_context.id
        c.tid = server_tid
        local_session.commit()
        log+= "Context {title} was added to server and received tid: {tid}\n".format(title=server_context.name, tid=server_tid)
        
        #need to update all tasks that used the temp_tid
        log+= "\nClient tasks that were updated with context id (tid) obtained from server:\n"
        
        tasks_with_temp_tid = local_session.query(Task).filter_by(context_tid=temp_tid) #tasks_with_temp_tid = c.tasks may be a better but would have to move higher
        
        # These changes on client do not get transmitted to the server because they are between old sync time and new sync time
        for t in tasks_with_temp_tid:
            t.context_tid = server_tid
            local_session.commit()
            
            log+= "{title} is in context {context}".format(title=t.title[:30], context=t.context.title) 

        nnn+=1

        if pb:
            pb.setValue(nnn)

    #note these are from class Temp_tid and not class Context
    for c in alternate_client_new_contexts: 
        log+="alternative method: new context: {0}".format(c.title)
        local_session.delete(c)
        local_session.commit()

    # the following is intended to catch contexts deleted on the server
    server_context_tids = set([sc.id for sc in remote_session.query(Context)])
    client_context_tids = set([cc.tid for cc in local_session.query(Context)])

    client_not_server = client_context_tids - server_context_tids

    for tid in client_not_server:
        cc = local_session.query(Context).filter_by(tid=tid).one()
        tasks = local_session.query(Task).filter_by(context_tid=tid).all()
        title = cc.title
        local_session.delete(cc)
        local_session.commit()
        #Note that the delete sets context_tid=None for all tasks in the context
        #I wonder how you set to zero - this is done "manually" below
        log+= "Deleted client context tid: {tid}  - {title}".format(title=title, tid=tid) # new server folders

        #These tasks are marked as changed by server so don't need to do this
        #They temporarily pick of context_tid of None after the context is deleted on the client
        #When tasks are updated later in sync they pick up correct folder_tid=0

        log+= "\nClient tasks that should be updated with context tid = 0 because the Context was deleted from the server:\n"
        
        for t in tasks:
            log+="{title} should to be changed from context_tid: {tid} to 'No Context'\n".format(tid=t.context_tid, title=t.title)
        
        nnn+=1

        if pb:
            pb.setValue(nnn)
        
    #no code for client deleted contexts yet

    #put new server folders on the client
    for sf in server_new_folders:

        try:
            folder = local_session.query(Folder).filter_by(tid=sf.id).one()
            
        except sqla_orm_exc.NoResultFound:
            
            folder = Folder()
            local_session.add(folder)
            folder.tid = sf.id # note that this allows you to go from server supplied fildder tid to postgreSQL supplied Folder.id
            
            log+= "New folder created on client with tid: {tid}; {title}\n".format(tid=sf.id, title=sf.name) # new server folders

        folder.title = sf.title
        folder.archived = sf.archived
        folder.private = sf.private
        folder.order= sf.order 

        try:
            local_session.commit()
            
        except sqla_exc.IntegrityError:
            local_session.rollback()
            # probably means we ran into the unusual circumstance where folder was simultaneously created on client and server
            # and title (name) already existed
            folder.title = sf.title +' from server'
            local_session.commit()
            
            log += "{title} is a new folder received from the server but it was a dupe of new client folder\n".format(title=sf.name)
        
        nnn+=1

        if pb:
            pb.setValue(nnn)


    for f in client_new_folders:
        temp_tid = f.tid

        #[{"id":"12345","name":"MyFolder","private":"0","archived":"0","ord":"1"}]
        try:
            #[server_folder] = toodledo_call('folders/add', name=c.title) 
            server_folder = remote_session.query(Folder).filter_by(title=f.title).one()
                 
        #except toodledo2.ToodledoError as e:
        except Exception as e:
            folder = Folder(title=f.title)
            remote_session.add(folder)
            remote_session.commit()
            print_(repr(e))
            print_("There was a problem adding new client folder {} to the server".format(f.title))


        server_tid = server_folder.id
        f.tid = server_tid
        local_session.commit()
        #tasks_with_temp_tid = f.tasks #see below could use this before you change the folders tid
        log+= "Folder {title} was added to server and received tid: {tid}\n".format(title=server_folder.name, tid=server_tid)

        #need to update all tasks that used the temp_tid
        log+= "Client tasks that were updated with folder id (tid) obtained from server:\n"

        tasks_with_temp_tid = session.query(Task).filter_by(folder_tid=temp_tid) #tasks_with_temp_tid = f.tasks may be a better way to go but would have to move higher

        # These changes on client do not get transmitted to the server because they are between old sync time and new sync time
        for t in tasks_with_temp_tid:
            t.folder_tid = server_tid
            local_session.commit() 

            log+= "Task {title} in folder {folder} \n".format(title=t.title[:30], folder=t.folder.title)

        nnn+=1

        if pb:
            pb.setValue(nnn)
    #note these are from class Temp_tid and not class Folder
    for f in alternate_client_new_folders:
        log+="alternative method: new folder: {0}".format(f.title)
        session.delete(f)
        session.commit()

    # deleting from client, folders deleted on server
    server_folder_tids = set([sf.id for sf in remote_session.query(Folder)])
    client_folder_tids = set([cf.tid for cf in local_session.query(Folder)])

    client_not_server = client_folder_tids - server_folder_tids

    for tid in client_not_server:
        cf = local_session.query(Folder).filter_by(tid=tid).one()
        tasks = local_session.query(Task).filter_by(folder_tid=tid).all() #seems like it needs to be here
        title = cf.title
        local_session.delete(cf)
        local_session.commit()
        log+= "Deleted client folder tid: {tid}  - {title}".format(title=title, tid=tid) # new server folders

        #These tasks are marked as changed by server so don't need to do this
        #They temporarily pick of folder_tid of None after the folder is deleted on the client
        #When tasks are updated later in sync they pick up correct folder_tid=0

        log+= "\nClient tasks that should be updated with folder tid = 0 because Folder was deleted from the server:\n"
        
        for t in tasks:
            log+="{title} should to be changed from folder_tid: {tid} to 'No Folder'\n".format(tid=t.folder_tid, title=t.title)
        
        
        nnn+=1

        if pb:
            pb.setValue(nnn)
        
    #no code for client deleted folders yet



    if server_updated_tasks:
        log+= "\nTask that were updated/created on Server that need to be updated/created on client:\n"

    for st in server_updated_tasks:
        
        task = local_session.query(Task).filter_by(tid=st.id).first()
        
        if not task:
            action = "created"
            task = Task()
            local_session.add(task)
            task.tid = st.id
        else:
            action = "updated"
            
        #  Note that since this synch is between postgreSQL that you don't want to modify the context_tid or folder_tid
        task.context_tid = st.context_tid
        task.duedate = st.duedate
        task.duetime = st.duetime if st.duetime else None #########
        task.remind = st.remind
        task.startdate = st.startdate if st.startdate else st.added ################ may 2, 2012
        task.folder_tid = st.folder_tid 
        task.title = st.title
        task.added = st.added
        task.star = st.star
        task.priority = st.priority
        task.tag = st.tag
        task.completed = st.completed if st.completed else None
        task.note = st.note

        local_session.commit() #new/updated client task commit

        log+="{action}: tid: {tid}; star: {star}; priority: {priority}; completed: {completed}; title: {title}\n".format(action=action, tid=st.id, star=st.star, priority=st.priority, completed=st.completed, title=st.title[:30])

        if task.tag:
            for tk in task.taskkeywords:
                local_session.delete(tk)
            local_session.commit()

            for kwn in task.tag.split(','):
                keyword = local_session.query(Keyword).filter_by(name=kwn).first()
                if keyword is None:
                    keyword = Keyword(kwn)
                    local_session.add(keyword)
                    local_session.commit()
                tk = TaskKeyword(task,keyword)
                local_session.add(tk)

            local_session.commit()
            
        tasklist.append(task)
        
        nnn+=1

        if pb:
            pb.setValue(nnn)

    if client_updated_tasks:
        log+= "\nTask that were updated/created on Client that need to be updated/created on Server:\n"

    for ct in client_updated_tasks:
        
        task = remote_session.query(Task).filter_by(id=ct.tid).first() # could also do get(ct.tid)
        
        if not task:
            action = "created"
            task = Task()
            remote_session.add(task)
            remote.session.commit()
            ct.tid = task.id
            local_session.commit()
        else:
            action = "updated"
            if task in server_updated_tasks:
                action+= "-server won"
                continue

        task.context_tid = ct.context_tid
        task.duedate = ct.duedate
        task.duetime = ct.duetime if st.duetime else None #########
        task.remind = ct.remind
        task.startdate = ct.startdate if ct.startdate else ct.added ################ may 2, 2012
        task.folder_tid = ct.folder_tid 
        task.title = ct.title
        task.added = ct.added
        task.star = ct.star
        task.priority = ct.priority
        task.tag = ct.tag
        task.completed = ct.completed if st.completed else None
        task.note = ct.note

        remote_session.commit() #new/updated client task commit

        log+="{action}: tid: {tid}; star: {star}; priority: {priority}; completed: {completed}; title: {title}\n".format(action=action, tid=st.id, star=st.star, priority=st.priority, completed=st.completed, title=st.title[:30])

        if task.tag:
            for tk in task.taskkeywords:
                remote_session.delete(tk)
            remote_session.commit()

            for kwn in task.tag.split(','):
                keyword = remote_session.query(Keyword).filter_by(name=kwn).first()
                if keyword is None:
                    keyword = Keyword(kwn)
                    remote_session.add(keyword)
                    remote_session.commit()
                tk = TaskKeyword(task,keyword)
                remote_session.add(tk)

            remote_session.commit()
            
        tasklist.append(task)
        
        nnn+=1

        if pb:
            pb.setValue(nnn)

    # Delete from client tasks deleted on server
    # uses deletelist
    for t in server_deleted_tasks:
        task = session.query(Task).filter_by(tid=t.id).first()
        if task:
                    
            log+="Task deleted on Server deleted task on Client - id: {id_}; tid: {tid}; title: {title}\n".format(id_=task.id,tid=task.tid,title=task.title[:30])
            
            deletelist.append(task.id)
            
            for tk in task.taskkeywords:
                session.delete(tk)
            session.commit()
        
            session.delete(task)
            session.commit() 
            
        else:
            
            log+="Task deleted on Server unsuccessful trying to delete on Client - could not find Client Task with tid = {0}\n".format(t.id)   

        nnn+=1

        if pb:
            pb.setValue(nnn)
        
    # uses deletelist
    tids_to_delete = []
    client_tasks = []
    for t in client_deleted_tasks:
        # need 'if' below because a task could be new and then deleted and therefore have not tid; 
        # it will be removed from client but can't send anything to server
        if t.tid:
            tids_to_delete.append(t.tid)
            client_tasks.append(t)
        else:
            deletelist.append(t.id)
            for tk in t.taskkeywords:
                session.delete(tk)
            session.commit()
                    
            session.delete(t)
            session.commit()     
         
    #http://api.toodledo.com/2/tasks/delete.php?key=YourKey;tasks=["1234"%2C"1235"]

    if tids_to_delete:
        try:
            server_tasks = toodledo_call('tasks/delete', tasks=json.dumps(tids_to_delete, separators=(',',':')))
            #[{"id":"1234"},{"id":"1235"}]
        except toodledo2.ToodledoError as e:
            print_(repr(e))
            print_("There was a problem deleting deleted client tasks from the server")
              
        else:  
            for c,s in zip(client_tasks, server_tasks):
                if 'errorCode' in s:
                    log+="Task sqlite id: {0} title: {1} could not be deleted on server; errorCode: {2} - errorDesc: {3}".format(c.id, c.title[:30], s.errorCode, s.get('errorDesc', ''))
                else:
                    log+= "Successfully deleted this task on server - tid: {tid} - {title}\n".format(tid=s.id, title=c.title[:30])
            
                    deletelist.append(c.id) 
            
                    for tk in c.taskkeywords:
                        session.delete(tk)
                    session.commit()
                    
                    session.delete(c)
                    session.commit()     
                    
                    nnn+=1

                    if pb:
                        pb.setValue(nnn)
                
            
        


    sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=5) # giving a little buffer if the db takes time to update on client or server

    sync.unix_timestamp = int(time.time()+5) #time.time returns a float but we're constantly using int timestamps

    session.commit()  

    log+= "\nNew Sync times:\n"
    log+= "isoformat: {0}\n".format(sync.timestamp.isoformat(' '))
    log+= "   unix ts: {0}\n".format(sync.unix_timestamp)
    log+= "Time is {0}\n\n".format(datetime.datetime.now())

    print_("***************** END SYNC *******************************************")

    if pb:
        pb.hide()

    if showlogdialog:
        dlg = lmdialogs.SynchResults("Synchronization Results", log, parent=parent)
        dlg.exec_()
        
    return log,changes,tasklist,deletelist 


    
def downloadtasksfromserver(local=True):
    '''
    this version downloads tasks from toodledo to a database that can be postgreSQL or sqlite and located anywhere
    '''

    session = local_session if local else remote_session
    toodledo_call = toodledo2.toodledo_call
    
    # I should make it possible to select only certain contexts
    print_("Starting the process of downloading tasks from server")
    
    account_info = toodledo_call('account/get')
    # {"lastedit_folder":"1281457337","lastedit_context":"1281457997","lastedit_goal":"1280441959","lastedit_location":"1280441959",
    #"lastedit_task":"1281458832","lastdelete_task":"1280898329","lastedit_notebook":"1280894728","lastdelete_notebook":"1280898329"}

    # note that Toodledo API only lets you bring back 1000 tasks at a time
    server_tasks = []
    n= 0
    while 1:
        # always returns id, title, modified, completed
        # also note that duetime and startdate were added 08302015
        stats,tasks = toodledo_call('tasks/get', start=str(n), end=str(n+1000), fields='folder,star,priority,duedate,duetime,startdate, context,tag,added,note')
        server_tasks.extend(tasks)
        if stats['num'] < 1000:
            break
        n+=1000    

    server_contexts = toodledo_call('contexts/get')
    server_folders = toodledo_call('folders/get')
    
    len_contexts = len(server_contexts)
    len_folders = len(server_folders)
    len_tasks = len(server_tasks)

    print_("last task changed on server: {}".format(account_info.lastedit_task))
    print_("{} server tasks were downloaded".format(len_tasks))
    print_("{} server contexts were downloaded".format(len_contexts))
    print_("{} server folders were downloaded".format(len_folders))

    if pb: 
        pb.setRange(0, len_contexts+len_folders+len_tasks)
        pb.setValue(0)
        pb.show()
    
    
    #server contexts --> client contexts
    for n,c in enumerate(server_contexts, n):
        context = Context()
        session.add(context)
        context.tid = c.id
        context.title = c.name
        #context.default = c.def

        session.commit()
        
        if pb:
            pb.setValue(n)

    #server folders --> client folders    
    for n,f in enumerate(server_folders, n):
        folder = Folder()
        session.add(folder)
        folder.tid = f.id
        folder.title = f.name
        folder.archived = f.archived
        folder.private = f.private
        folder.order= f.order

        session.commit()
        
        if pb:
            pb.setValue(n)

    #server tasks -> client tasks
    for n,t in enumerate(server_tasks):
        
        #if t.context_id != 1633429:     #if you only want to download one context
            #continue                            # might also not want to pick up folders and contexts
        
        task = Task()
        session.add(task)
        task.tid = t.id 
                                  
        # the commented out line immediately below is what was here previously and the two lines below that are for the postgreSQL server
        #task.context_tid = t.context 
        context = session.query(Context).filter_by(tid = t.context).one()
        task.context_tid = context.id
        
        task.duedate = t.duedate          
        
        # the commented out line immediately below is what was here previously and the two lines below that are for the postgreSQL server
        # task.folder_tid = t.folder
        folder = session.query(Folder).filter_by(tid = t.folder).one()
        task.folder_tid = folder.id
           
        task.title = t.title
        task.added = t.added                
        task.star = t.star
        task.priority = t.priority
        task.tag = t.tag
        task.completed = t.completed    
        task.note = t.note
        task.remind = t.remind
        
        # the two lines below were missing and not being pulled off toodledo - not sure why and I added them
        task.duetime = t.duetime if t.duetime else None
        task.startdate = t.startdate if t.startdate else t.added 

#        try:
#            task.parent_tid = t.parent #only in pro accounts
#        except:
#            pass
#
        try:
            session.commit()
        except sqla_exc.IntegrityError as e:
            session.rollback()
            print_(repr(e))
            print_(task.title)
        else:
            if task.tag:

                for kwn in task.tag.split(','):
                    keyword = session.query(Keyword).filter_by(name=kwn).first()
                    if keyword is None:
                        keyword = Keyword(kwn[:25])
                        session.add(keyword)
                        session.commit()
                    tk = TaskKeyword(task,keyword)
                    session.add(tk)

                #session.commit()
                try:
                    session.commit()
                except sqla_exc.IntegrityError as e:
                    session.rollback()
                    print_(repr(e))
                    print_(task.title)
    
        if pb:
            pb.setValue(n)
    
    #Update synch timestamps
    sync = session.query(Sync).get('client')
    sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=2) # (was 5) giving a little buffer if the db takes time to update on client or server
    sync.unix_timestamp = int(time.time()+2) #was 5, changed 01-24-2015
    session.commit()  

    print_("New Sync times")
    print_("isoformat timestamp: {}".format(sync.timestamp.isoformat(' ')))
    print_("unix timestamp: {}".format(sync.unix_timestamp))

    print_("***************** END SYNC *******************************************")
    
    if pb:
        pb.hide() 

