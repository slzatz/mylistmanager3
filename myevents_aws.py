
from lmdb_aws import session
import datetime
import PyQt5.QtGui as QtGui
#import lmglobals as g

def responses(source, d):

    print("source={}".format(source))
    for z in d:
        print("{}: {}".format(z,d[z]))

    task = d.get('task')
    session = d.get('session')
    

    if source=='newtask':
        if task.context.title!='test':
            task.remind = 1
            task.duedate=task.duetime = datetime.datetime.now() + datetime.timedelta(days=1)
            session.commit()

    if source=='incrementpriority':
        priority = d.get('priority')
        if priority == -1:
            QtGui.QMessageBox.question(None,  'Alert', "Are you sure you want a priority of -1?")
        
