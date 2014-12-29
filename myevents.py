'''
Slots that can be used for custom/plugin-type actions
'''
import datetime
from PyQt5 import QtWidgets

def responses(source, d):

    print("source={}".format(source))
    for z in d:
        print("{}: {}".format(z,d[z]))

    task = d.get('task')
    session = d.get('session')

    if source=='set_reminder':
        task.remind = 1
        task.duedate=task.duetime = datetime.datetime.now() + datetime.timedelta(days=1)
        session.commit()

    if source=='incrementpriority':
        priority = d.get('priority')
        if priority == -1:
            QtWidgets.QMessageBox.question(None,  'Alert', "Are you sure you want a priority of -1?")
        
