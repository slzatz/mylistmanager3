
#@+leo-ver=5-thin
#@+node:slzatz.20141214092447.45: * @file C:/Users/szatz/python3/_myevents_aws.py
#@@first
#@@nowrap
#@@language python
#@@tabwidth -4
#@+others
#@+node:slzatz.20141214092447.46: ** _myevents_aws declarations

from lmdb import session
import datetime
import PyQt4.QtGui as QtGui
#@+node:slzatz.20141214092447.47: ** responses
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
        
#@-others
#@-leo
