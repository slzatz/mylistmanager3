#from lmdb import *
import toodledo2
import synchronize2
import boto.ses
import sys
import config as c

#from lmdb import *
#s = remote_session
#sync = s.query(Sync).get('client')
#last_client_sync = sync.timestamp
#edited_tasks = s.query(Task).filter(and_(Task.modified > last_client_sync, Task.deleted==False, Task.tid!=None)).all()
#edited_tasks  #[<Task(395948460 - 'Reckitt')>]

if toodledo2.keycheck():
    log, changes, tasklist, deletelist = synchronize2.synchronize(showlogdialog=False, OkCancel=False, local=False) 
else:
    print("Could not get a good toodledo key")
    sys.exit()

ses_conn = boto.ses.connect_to_region(
                                      "us-east-1",
                                      aws_access_key_id=c.aws_access_key_id,
                                      aws_secret_access_key=c.aws_secret_access_key)

subject = "sync log"
res = ses_conn.send_email(
                    'manager.list@gmail.com',
                    "Sync Log",
                    log,
                    ['slzatz@gmail.com', 'szatz@webmd.net']) #,
                    #html_body=html_body)
print("res=",res)

with open("sync_log", 'a') as f:
    f.write(log)


print("changes={} type={}".format(changes, type(changes)))
print("tasklist={0}".format([t.title for t in tasklist])) #this is a goofy print
print("deletelist={} type={}".format(deletelist, type(deletelist)))
