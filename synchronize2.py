

import lmdialogs

import os
import time
import sys
import datetime
import calendar
import platform
import configparser as configparser
import json
import urllib.request, urllib.parse, urllib.error
import re

#import urllib.request, urllib.parse, urllib.error will be needed for python 3.x
import base64
from optparse import OptionParser
from functools import partial

#import toodledo
import toodledo2

# all the db stuff and sqlalchemy
from lmdb import *

import lmglobals as g

cg = g.config

print_ = g.logger.write #this is not created until after listmanager is instantiated although it probably could be

print = print_

print_("Hello from the synchronize2 module")

pb = g.pb #this requires listmanager to be instantiatede

def synchronize(parent=None, showlogdialog=True, OkCancel=False):
    #{"id":"265413904","title":"FW: U.S. panel likely to back arthritis drug of Abbott rival
    #(Pfz\/tofacitinib)","modified":1336240586,"completed":0,"folder":"0","priority":"0","context":"0","tag":"","note":"From: maryellen [
    #...","remind":"0","star":"0","duedate":1336478400,"startdate":0,"added":1336132800,"duetime":1336456800}

    attr_map = dict(id='tid', folder='folder_tid', context='context_tid')

    _convert = lambda x: calendar.timegm(x.timetuple()) if x else 0
    #previously _convert_ = lambda x: int(time.mktime(x.timetuple())) if x else 0, 
    #it's not the same and I think current _convert function is correct but not 100% sure

        
    _typemap = {
                
                    'id': str, 
                    'title': lambda x:x,
                    'tag': lambda x: x if x else '',
                    'folder': str,
                    'context': str,
                    'remind': lambda x: str(x) if x else "0",
                    'startdate': _convert,
                    'duedate': _convert,
                    'duetime': _convert,
                    'completed': _convert,
                    'star': lambda x: str(int(x)), 
                    'priority': str,
                    'note': lambda x:x,

                        }

    #not using concept of parent

    nn = 0

    changes = [] #server changed context and folder
    tasklist= [] #server changed tasks
    deletelist = [] #server deleted tasks

    toodledo_call = toodledo2.toodledo_call

    print_("****************************** BEGIN SYNC (JSON) *******************************************")
        
    log = ''

    sync = session.query(Sync).get('client') #switching server to timestamp

    last_client_sync = sync.timestamp
    last_server_sync = sync.unix_timestamp

    log+= "JSON SYNC\n"
    log+= "Local Time is {0}\n\n".format(datetime.datetime.now())
    delta = datetime.datetime.now() - last_client_sync
    log+= "The last time client & server were synced (based on client clock) was {0}, which was {1} days and {2} minutes ago.\n".format(last_client_sync.isoformat(' ')[:19], delta.days, delta.seconds/60)
    log+= "Unix timestamp (client clock) for last sync is {0} ---> {1}\n".format(last_server_sync, datetime.datetime.fromtimestamp(last_server_sync).isoformat(' ')[:19])

    account_info = toodledo_call('account/get')

    # {"lastedit_folder":"1281457337","lastedit_context":"1281457997","lastedit_goal":"1280441959","lastedit_location":"1280441959",
    #"lastedit_task":"1281458832","lastdelete_task":"1280898329","lastedit_notebook":"1280894728","lastdelete_notebook":"1280898329"}

    log+= "The last task edited on server was at {0} ---> {1}.\n".format(account_info.lastedit_task, datetime.datetime.fromtimestamp(account_info.lastedit_task).isoformat(' ')[:19])
    log+= "The last task deleted on server was at {0} ---> {1}.\n".format(account_info.lastdelete_task, datetime.datetime.fromtimestamp(account_info.lastdelete_task).isoformat(' ')[:19])
    log+="Note on May 13, 2012 the server clock seemed to be running about a minute slower than my computer clock\n\n"
    #contexts
    #http://api.toodledo.com/2/contexts/get.php?key=YourKey
    #[{"id":"123","name":"Work"},{"id":"456","name":"Home"},{"id":"789","name":"Car"}]

    if account_info.lastedit_context and account_info.lastedit_context > last_server_sync:
        server_contexts = toodledo_call('contexts/get')
        nn+=len(server_contexts)
        log+="There were change(s) to server Contexts since the last sync and all {0} Contexts were downloaded.\n".format(len(server_contexts))
        changes.append('contexts')
    else:
        server_contexts = []
        log+="There were no Context changes (edits, deletions, additions) on the server since the last sync.\n"

    #folders
    if account_info.lastedit_folder and account_info.lastedit_folder > last_server_sync:
        #[{"id":"123","name":"Shopping","private":"0","archived":"0","ord":"1"},...]
        server_folders = toodledo_call('folders/get')
        nn+=len(server_folders)
        log+="There were change(s) to server Folders since the last sync and all {0} Folders were downloaded.\n".format(len(server_folders))
        changes.append('folders')
    else:
        server_folders = []
        log+="There were no Folder changes (edits, deletions, additions) on the server since the last sync.\n"

    #tasks
    if account_info.lastedit_task and account_info.lastedit_task > last_server_sync:
        server_updated_tasks = []
        n= 0
        while 1:
            # always returns id, title, modified, completed
            stats,tasks = toodledo_call('tasks/get', start=str(n), end=str(n+1000), modafter=last_server_sync, fields='folder,star,priority,duedate,context,tag,added,note,startdate,duetime,remind')
            server_updated_tasks.extend(tasks)
            if stats['num'] < 1000:
                break
            n+=1000

        nn+=len(server_updated_tasks)
        log+="Created and/or modified Server Tasks since the last sync: {0}.\n".format(len(server_updated_tasks))
    else:
        server_updated_tasks = []
        log+="There were no Tasks created and/or modified on the server since the last sync.\n"

    #deleted tasks
    if account_info.lastdelete_task and account_info.lastdelete_task > last_server_sync:
        stats,server_deleted_tasks = toodledo_call('tasks/deleted', after=last_server_sync) 
        nn+=len(server_deleted_tasks)
        log+="Server Tasks deleted since the last sync: {0}.\n\n".format(len(server_deleted_tasks))
    else:
        server_deleted_tasks = []
        log+="There were no Tasks that were deleted on the server since the last sync.\n\n"

    #contexts
    client_new_contexts = session.query(Context).filter(Context.created > last_client_sync).all()
    if client_new_contexts:
        nn+=len(client_new_contexts)
        log+= "New client Contexts added since the last sync: {0}.\n".format(len(client_new_contexts))
    else:
        log+="There were no new client Contexts added since the last sync.\n"   
            
    alternate_client_new_contexts = session.query(Temp_tid).filter_by(type_='context').all()

    if alternate_client_new_contexts:
        log+= "Alternate method: New client Contexts added since the last sync: {0}.\n".format(len(alternate_client_new_contexts))
    else:
        log+="Alternate method: There were no new client Contexts added since the last sync.\n\n"        

    #folders
    client_new_folders = session.query(Folder).filter(Folder.created > last_client_sync).all() 
    if client_new_folders:
        nn+=len(client_new_folders) 
        log+= "New client Folders added since the last sync: {0}.\n".format(len(client_new_folders))
    else:
        log+="There were no new client Folders added since the last sync.\n"    

    alternate_client_new_folders = session.query(Temp_tid).filter_by(type_='folder').all()

    if alternate_client_new_folders:
        log+= "Alternate method: New client Folders added since the last sync: {0}.\n".format(len(alternate_client_new_folders))
    else:
        log+="Alternate method: There were no new client Folders added since the last sync.\n\n"        

    #tasks
    client_new_tasks = session.query(Task).filter(and_(Task.tid==None, Task.deleted==False)).all()
    if client_new_tasks:
        nn+=len(client_new_tasks)
        log+="New client Tasks added since the last sync: {0}.\n".format(len(client_new_tasks))
    else:
        log+="There were no new client Tasks added since the last sync.\n" 
        
    alternate_client_new_tasks = session.query(Task).filter(and_(Task.created > last_client_sync, Task.deleted==False)).all() 
    if alternate_client_new_tasks:
        log+= "Alternate method: New client Tasks added since the last sync: {0}.\n".format(len(alternate_client_new_tasks))
    else:
        log+="Alternate method: There were no new client Tasks added since the last sync.\n\n"        
        

    client_edited_tasks = session.query(Task).filter(and_(Task.modified > last_client_sync, Task.deleted==False, Task.tid!=None)).all()

    if client_edited_tasks:
        nn+=len(client_edited_tasks)
        log+="Edited client Tasks since the last sync: {0}.\n".format(len(client_edited_tasks))
    else:
        log+="There were no edited client Tasks since the last sync.\n" 

    #deletes
    client_deleted_tasks = session.query(Task).filter(Task.deleted==True).all()
    #client_deleted_tasks = session.query(Task).filter(and_(Task.modified > last_client_sync, Task.deleted==True, Task.tid != None)).all()
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

    pb.setRange(0, nn)
    nnn=0
    pb.setValue(nnn)
    pb.show()

    #[{"id":"123","name":"Work"},{"id":"456","name":"Home"},{"id":"789","name":"Car"}]

    for sc in server_contexts:
        try:
            context = session.query(Context).filter_by(tid=sc.id).one()
            
        except sqla_orm_exc.NoResultFound:
              
            context = Context()
            session.add(context)
            context.tid = sc.id 
            
            log += "{title} is a new context received from the server\n".format(title=sc.name)

        context.title = sc.name
        
        try:
            session.commit()
            
        except sqla_exc.IntegrityError:
            session.rollback()
            # probably means we ran into the unusual circumstance where context was simultaneously created on client and server
            context.title = sc.name+' from server'
            session.commit()
            
            log += "{title} is a new context received from the server but it was a dupe of new client context\n".format(title=sc.name)
        
        nnn+=1
        pb.setValue(nnn)


    for c in client_new_contexts: # this is where we could check for simultaneous creation of folders by checking for title in server_folders
        temp_tid = c.tid

        try:
            [server_context] = toodledo_call('contexts/add', name=c.title) #[{"id":"12345","name":"MyContext"}]

        except toodledo2.ToodledoError as tooderror:
            print_(repr(tooderror))
            print_("There was a problem adding new client context {} to the server".format(c.title))

            if tooderror.errorcode == 5: # duplicate name errorcode
                 [server_context] = toodledo_call('contexts/add', name=c.title+' from client')
            else:
                continue

        server_tid = server_context.id
        c.tid = server_tid
        session.commit()
        log+= "Context {title} was added to server and received tid: {tid}\n".format(title=server_context.name, tid=server_tid)
        
        #need to update all tasks that used the temp_tid
        log+= "\nClient tasks that were updated with context id (tid) obtained from server:\n"
        
        tasks_with_temp_tid = session.query(Task).filter_by(context_tid=temp_tid) #tasks_with_temp_tid = c.tasks may be a better but would have to move higher
        
        # These changes on client do not get transmitted to the server because they are between old sync time and new sync time
        for t in tasks_with_temp_tid:
            t.context_tid = server_tid
            session.commit()
            
            log+= "{title} is in context {context}".format(title=t.title[:30], context=t.context.title) 

        nnn+=1
        pb.setValue(nnn)

    #note these are from class Temp_tid and not class Context
    for c in alternate_client_new_contexts: 
        log+="alternative method: new context: {0}".format(c.title)
        session.delete(c)
        session.commit()
    #server_contexts = client.getContexts()
    if server_contexts:
        server_context_tids = set([sc.id for sc in server_contexts])
        client_context_tids = set([cc.tid for cc in session.query(Context).filter(Context.tid!=0)])

        client_not_server = client_context_tids - server_context_tids

        for tid in client_not_server:
            cc = session.query(Context).filter_by(tid=tid).one()
            tasks = session.query(Task).filter_by(context_tid=tid).all()
            title = cc.title
            session.delete(cc)
            session.commit()
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
            pb.setValue(nnn)
            
            
           

    #no code for client deleted contexts yet

     #[{"id":"123","name":"Shopping","private":"0","archived":"0","ord":"1"},...]
    for sf in server_folders:
        try:
            folder = session.query(Folder).filter_by(tid=sf.id).one()
            
        except sqla_orm_exc.NoResultFound:
            
            folder = Folder()
            session.add(folder)
            folder.tid = sf.id
            log+= "New folder created on client with tid: {tid}; {title}\n".format(tid=sf.id, title=sf.name) # new server folders

        folder.title = sf.name
        folder.archived = sf.archived
        folder.private = sf.private
        folder.order= sf.order 

        try:
            session.commit()
            
        except sqla_exc.IntegrityError:
            session.rollback()
            # probably means we ran into the unusual circumstance where folder was simultaneously created on client and server
            # and title (name) already existed
            folder.title = sf.name+' from server'
            session.commit()
            
            log += "{title} is a new folder received from the server but it was a dupe of new client folder\n".format(title=sf.name)
        
        nnn+=1
        pb.setValue(nnn)

    for f in client_new_folders:
        temp_tid = f.tid

        #[{"id":"12345","name":"MyFolder","private":"0","archived":"0","ord":"1"}]
        try:
            [server_folder] = toodledo_call('folders/add', name=c.title) 
                 
        except toodledo2.ToodledoError as tooderror:
            print_(repr(tooderror))
            print_("There was a problem adding new client folder {} to the server".format(f.title))

            if tooderror.errorcode == 5: # duplicate name errorcode
                 [server_folder] = toodledo_call('folders/add', name=f.title+' from client')
            else:
                continue

        server_tid = server_folder.id
        f.tid = server_tid
        session.commit()
        #tasks_with_temp_tid = f.tasks #see below could use this before you change the folders tid
        log+= "Folder {title} was added to server and received tid: {tid}\n".format(title=server_folder.name, tid=server_tid)

        #need to update all tasks that used the temp_tid
        log+= "Client tasks that were updated with folder id (tid) obtained from server:\n"

        tasks_with_temp_tid = session.query(Task).filter_by(folder_tid=temp_tid) #tasks_with_temp_tid = f.tasks may be a better way to go but would have to move higher

        # These changes on client do not get transmitted to the server because they are between old sync time and new sync time
        for t in tasks_with_temp_tid:
            t.folder_tid = server_tid
            session.commit() 

            log+= "Task {title} in folder {folder} \n".format(title=t.title[:30], folder=t.folder.title)

        nnn+=1
        pb.setValue(nnn)

    #note these are from class Temp_tid and not class Folder
    for f in alternate_client_new_folders:
        log+="alternative method: new folder: {0}".format(f.title)
        session.delete(f)
        session.commit()

    if server_folders:
        server_folder_tids = set([sf.id for sf in server_folders])
        client_folder_tids = set([cf.tid for cf in session.query(Folder).filter(Folder.tid!=0)])

        client_not_server = client_folder_tids - server_folder_tids

        for tid in client_not_server:
            cf = session.query(Folder).filter_by(tid=tid).one()
            tasks = session.query(Task).filter_by(folder_tid=tid).all() #seems like it needs to be here
            title = cf.title
            session.delete(cf)
            session.commit()
            log+= "Deleted client folder tid: {tid}  - {title}".format(title=title, tid=tid) # new server folders

            #These tasks are marked as changed by server so don't need to do this
            #They temporarily pick of folder_tid of None after the folder is deleted on the client
            #When tasks are updated later in sync they pick up correct folder_tid=0

            log+= "\nClient tasks that should be updated with folder tid = 0 because Folder was deleted from the server:\n"
            
            for t in tasks:
                log+="{title} should to be changed from folder_tid: {tid} to 'No Folder'\n".format(tid=t.folder_tid, title=t.title)
            
            
            nnn+=1
            pb.setValue(nnn)
            
    #no code for client deleted folders yet

    # Update client with server changes - both new and edited tasks
    # fields='folder,star,priority,duedate,context,tag,added,note' plus always returns id, title, modified, completed 
    # note that while modified is passed from the server we don't do anything with it since client and server modified are different

    if server_updated_tasks:
        log+= "\nTask that were updated/created on Server that need to be updated/created on client:\n"

    for t in server_updated_tasks:
        
        task = session.query(Task).filter_by(tid=t.id).first()
        
        if not task:
            action = "created"
            task = Task()
            session.add(task)
            task.tid = t.id
        else:
            action = "updated"
            if task in client_edited_tasks:
                client_edited_tasks.remove(task) # server changes win
                
        #################### this shouldn't be necessary when they all go back to naive
        task.duetime = None ##########   just to deal with any lingering aware
        session.commit() #############

        task.context_tid = t.context
        task.duedate = t.duedate
        #task.duetime = (t.duetime + datetime.timedelta(hours=4)) if t.duetime else None #########
        task.duetime = t.duetime if t.duetime else None #########
        task.remind = t.remind
        task.startdate = t.startdate if t.startdate else t.added ################ may 2, 2012
        task.folder_tid = t.folder
        task.title = t.title
        task.added = t.added
        task.star = t.star
        task.priority = t.priority
        task.tag = t.tag
        task.completed = t.completed if t.completed else None
        task.note = t.note

        # I am not calling parent at the moment so wondering if this should just be removed
        # try:
            # task.parent_tid = t.parent #only in pro accounts
        # except:
            # pass

        session.commit() #new/updated client task commit

        log+="{action}: tid: {tid}; star: {star}; priority: {priority}; completed: {completed}; title: {title}\n".format(action=action, tid=t.id, star=t.star, priority=t.priority, completed=t.completed, title=t.title[:30])

        if task.tag:
            for tk in task.taskkeywords:
                session.delete(tk)
            session.commit()

            for kwn in task.tag.split(','):
                keyword = session.query(Keyword).filter_by(name=kwn).first()
                if keyword is None:
                    keyword = Keyword(kwn)
                    session.add(keyword)
                    session.commit()
                tk = TaskKeyword(task,keyword)
                session.add(tk)

            session.commit()
            
        tasklist.append(task)
        
        #could the xapian be done here?
        #if XAPIANENABLED:
            #for task in tasklist:
                #self.updatexapianentry(task) # obviously self won't work
        
        nnn+=1
        pb.setValue(nnn)

    #Update tasks on server with client edited tasks
    #if client_edited_tasks:
    log+= "\nTasks edited on this client that were updated on the server:\n" if client_edited_tasks else ''
        
    n=0
    while 1:
        client_tasks = client_edited_tasks[n:n+50]
        print_("client_edited_tasks; n = {}".format(n))
        if not client_tasks:
            break
            
        lst = []
            
        for t in client_tasks:
            
            # some old tasks may have some weird stuff in things like completed 
            try:
                            
                z = {a:_typemap[a] (getattr(t, attr_map.get(a,a))) for a in _typemap}
                lst.append(z)
            
            except Exception as value:
                
                print_("Problem in client-edited-tasks with id: {0}: {1}".format(t.id,t.title))
                print_(repr(value))
        
        kwargs = {'tasks':json.dumps(lst, separators=(',',':')), 'fields':'folder,star,priority,duedate,context,tag,added,note,startdate,duetime,remind'}
        #kwargs=[{"id":"1234","title":"My Task","modified":1281990824,"completed":0,"folder":"0","star":"0"},{"id":"1235","title":"Another","modified":1280877483,"completed":0,"folder":"0","star":"1"}]
        # separators option is just compacting representation
        
        server_tasks = toodledo_call('tasks/edit', **kwargs)
        
        for c,s in zip(client_tasks, server_tasks):
            
            if 'errorCode' in s:
                log+="Task tid: {0} title: {1} could not be updated on server; errorCode: {2} - errorDesc: {3}".format(c.tid, c.title, s.errorCode, s.get('errorDesc', ''))
            else:
                #s.title = s.title.encode('ascii', 'replace')[:30] #not sure that encoding the unicode into a byte string is necessary 12-22-2014
                log+="Task tid: {id}; star: {star}; priority: {priority}; completed: {completed}; title: {title}\n".format(**s)
            
            nnn+=1
            pb.setValue(nnn)
            
        n+=50
            
    log+="\nNew client tasks that were added to the server:\n" if client_new_tasks else ''

    n=0
    while 1:
        client_tasks = client_new_tasks[n:n+50] #can only upload 50 tasks at a time according to API
        print_("client_new_tasks; n = {}".format(n))
        if not client_tasks:
            break

        lst = []
        for t in client_tasks:         
            z = {a:_typemap[a] (getattr(t, attr_map.get(a,a))) for a in _typemap}          
            lst.append(z)

        kwargs = {'tasks':json.dumps(lst, separators=(',',':')), 'fields':'folder,star,priority,duedate,context,tag,added,note,startdate,duetime,remind'}
        #[{"id":"1234","title":"My Task","modified":1281990824,"completed":0,"folder":"0","star":"0"}, {"id":"1235","title":"Another","modified":1280877483,"completed":0,"folder":"0","star":"1","ref":"98765"}]
        
        server_tasks = toodledo_call('tasks/add', **kwargs)
        
        for c,s in zip(client_tasks, server_tasks):
            
            if 'errorCode' in s:
                log+="Task sqlite id: {0} title: {1} could not be updated on server; errorCode: {2} - errorDesc: {3}".format(c.id, c.title, s.errorCode, s.get('errorDesc', ''))
            else:
                c.tid = s.id    # need to pick up the server id for each task
                c.added = s.added #### April 24, 2012
                session.commit()
                
                #s.title = s.title.encode('ascii', 'replace')[:30] #not sure that encoding the unicode into a byte string is necessary 12-22-2014
                log+="Task tid: {id}; star: {star}; priority: {priority}; completed: {completed}; title: {title}\n".format(**s)
            
            nnn+=1
            pb.setValue(nnn)
            
        n+=50
        
    # Delete from client tasks deleted on server
    # uses deletelist
    for t in server_deleted_tasks:
        task = session.query(Task).filter_by(tid=t.id).first()
        if task:
                    
            log+="Task deleted on Server deleted task on Client - id: {id_}; tid: {tid}; title: {title}\n".format(id_=task.id,tid=task.tid,title=task.title.encode('ascii', 'replace')[:30])
            
            deletelist.append(task.id)
            
            for tk in task.taskkeywords:
                session.delete(tk)
            session.commit()
        
            session.delete(task)
            session.commit() 
            
        else:
            
            log+="Task deleted on Server unsuccessful trying to delete on Client - could not find Client Task with tid = {0}\n".format(t.id)   

        nnn+=1
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
        except toodledo2.ToodledoError as value:
            print_(repr(value))
            print_("There was a problem deleting deleted client tasks from the server")
              
        else:  
            for c,s in zip(client_tasks, server_tasks):
                if 'errorCode' in s:
                    log+="Task sqlite id: {0} title: {1} could not be deleted on server; errorCode: {2} - errorDesc: {3}".format(c.id, c.title.encode('ascii', 'replace')[:30], s.errorCode, s.get('errorDesc', ''))
                else:
                    log+= "Successfully deleted this task on server - tid: {tid} - {title}\n".format(tid=s.id, title=c.title.encode('ascii', 'replace')[:30])
            
                    deletelist.append(c.id) 
            
                    for tk in c.taskkeywords:
                        session.delete(tk)
                    session.commit()
                    
                    session.delete(c)
                    session.commit()     
                    
                    nnn+=1
                    pb.setValue(nnn)
                
            
        
    sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=5) # giving a little buffer if the db takes time to update on client or server

    sync.unix_timestamp = int(time.time()+5) #time.time returns a float but we're constantly using int timestamps

    session.commit()  

    log+= "\nNew Sync times:\n"
    log+= "isoformat: {0}\n".format(sync.timestamp.isoformat(' '))
    log+= "   unix ts: {0}\n".format(sync.unix_timestamp)
    log+= "Time is {0}\n\n".format(datetime.datetime.now())

    print_("***************** END SYNC *******************************************")

    pb.hide()

    if showlogdialog:
        dlg = lmdialogs.SynchResults("Synchronization Results", log, parent=parent)
        dlg.exec_()
        
    return log,changes,tasklist,deletelist 
    
def downloadtasksfromserver():
    '''
    sends all tasks on server down to client
    '''

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
        stats,tasks = toodledo_call('tasks/get', start=str(n), end=str(n+1000), fields='folder,star,priority,duedate,context,tag,added,note')
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
        
        pb.setValue(n)

    #server tasks -> client tasks
    for n,t in enumerate(server_tasks):
        
        #if t.context_id != 1633429:     #if you only want to download one context
            #continue                            # might also not want to pick up folders and contexts
        
        task = Task()
        session.add(task)
        task.tid = t.id                           
        task.context_tid = t.context 
        task.duedate = t.duedate          
        task.folder_tid = t.folder          
        task.title = t.title
        task.added = t.added                
        task.star = t.star
        task.priority = t.priority
        task.tag = t.tag
        task.completed = t.completed    
        task.note = t.note
        task.remind = t.remind
        
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
    
        pb.setValue(n)
    
   # #server contexts --> client contexts
   # 
   # for n,c in enumerate(server_contexts, n):
   #     context = Context()
   #     session.add(context)
   #     context.tid = c.id
   #     context.title = c.name
   #     #context.default = c.def

   #     session.commit()
   #     
   #     pb.setValue(n)

   # #server folders --> client folders    
   # for n,f in enumerate(server_folders, n):
   #     folder = Folder()
   #     session.add(folder)
   #     folder.tid = f.id
   #     folder.title = f.name
   #     folder.archived = f.archived
   #     folder.private = f.private
   #     folder.order= f.order

   #     session.commit()
   #     
   #     pb.setValue(n)

    #Update synch timestamps
    sync = session.query(Sync).get('client')
    sync.timestamp = datetime.datetime.now() + datetime.timedelta(seconds=5) # giving a little buffer if the db takes time to update on client or server
    sync.unix_timestamp = int(time.time()+5)
    session.commit()  

    print_("New Sync times")
    print_("isoformat timestamp: {}".format(sync.timestamp.isoformat(' ')))
    print_("unix timestamp: {}".format(sync.unix_timestamp))

    print_("***************** END SYNC *******************************************")
    
    pb.hide() 

