import os
import urllib.request, urllib.error, urllib.parse
import configparser as configparser

#from PyQt5 import QtGui,QtWidgets
#from config import rds_uri

cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
CONFIG_FILE = os.path.join(cwd,'mylistmanager_p.ini')
#LOCAL_DB_FILE = os.path.join(cwd,'lmdb_s','mylistmanager_s.db')
#sqlite_uri = 'sqlite:///' + LOCAL_DB_FILE
#DB_URI = None #####################right now need to change this manually in listmanager  
REMOTE_DB = 'listmanager_p' ############### 09082015
WHOOSH_DIR = os.path.join(cwd, 'whoosh_index_p')
IMAGES_DIR = os.path.join(cwd,'bitmaps')
PLUGIN_DIR = os.path.join(cwd,'plugins')
USER_ICONS = 'folder_icons'
CORE_ICONS = ''
LOG_FILE = os.path.join(cwd,'logfile_p.txt')
VIM = os.path.abspath("c:/Program Files (x86)/Vim/vim74/gvim.exe")
del cwd


# these are for toodledo and I think they are necessary
key = None
timestamp = None

config = configparser.RawConfigParser()
config.read(CONFIG_FILE)

# this could be in listmanager since not sure any other module needs to know
if config.has_option('Application', 'plugins'):
    plugins_enabled = config.getboolean('Application', 'plugins')
else:
    plugins_enabled = False

#def create_action(parent, text, slot=None, shortcut=None, icon=None, icon_res=None, image=None, tip=None, checkable=False):
#
#    action = QtWidgets.QAction(parent)
#    action.setText(text)
#    
#    if icon:
#        action.setIcon(QtGui.QIcon(os.path.join(IMAGES_DIR, icon))) #works without extension but finds bmp before png
#    elif icon_res:
#        action.setIcon(QtGui.QIcon(icon_res)) # uses resource.py
#    elif image:
#        pxmap = QtGui.QPixmap()
#        pxmap.loadFromData(image, 'PNG')
#        action.setIcon(QtGui.QIcon(pxmap))
#        
#    if shortcut:
#        action.setShortcut(shortcut)
#
#    tip = tip if tip else text.lstrip('&')
#    action.setToolTip(tip)
#    action.setStatusTip(tip)
#
#    #note: default overload is triggered(bool checked=False) meaning that slots would have to have two arguments, self and checked
#    #the below gets you the non-default triggered() overload
#    if slot:
#        #action.triggered[()].connect(slot)
#        action.triggered.connect(slot) #12-17-2014
#        #action.connect(slot)
#        
#    if checkable:
#        action.setCheckable(True)
#
#    return action
#
#def add_actions(target, actions):
#    for action in actions:
#        if action is None:
#            target.addSeparator()
#        else:
#            target.addAction(action)
            
def internet_accessible():
    try:
        response=urllib.request.urlopen('http://www.google.com',timeout=1)
    except urllib.error.URLError:
        return False
    else:
        return True

#def check_modified(f):
#    ''' A decorator that checks if there have been any field changes'''
#    
#    def fn(lm, *args, **kwargs):
#        if lm.modified:
#            print("self.modified dict is not empty and so savenote was called")
#            print("self.modified={0}".format(repr(lm.modified)))
#            print("The method that triggered savenote was {0}".format(f.__name__))
#
#            lm.savenote()
#        return f(lm, *args, **kwargs)
#    return fn
#    
#def check_task_selected(f):
#    '''A decorator that checks to see if a task was selected before an action'''
#    
#    def fn(lm, *args, **kwargs):
#        if not lm.task or lm.index==-1:
#            QtWidgets.QMessageBox.information(lm,  'Note', "No row is selected")
#            return
#        else:
#            return f(lm, *args, **kwargs)
#    return fn
#
#def update_whooshdb(f):
#    ''' A decorator that updates the whoosh db because of a task change'''
#    
#    def fn(lm, *args, **kwargs):
#        z = f(lm, *args, **kwargs)
#        lm.updatewhooshentry(False, task=lm.task)
#        return z
#    return fn
#   
#def update_row(f):
#    ''' A decorator that updates the changed row in the table'''
#
#    def fn(lm, *args, **kwargs):
#        z = f(lm, *args, **kwargs)
#        
#        #qtablewidgetitem = QtGui.QTableWidgetItem
#        qcolor = QtGui.QColor
#        #qicon = QtGui.QIcon
#        display = lm.display #dict that just holds display lambda's
#            
#        type_ = 'folder' if lm.Properties['tab']['type'] == 'context' else 'context'
#
#        table = lm.table
#        col_order = lm.col_order
#
#        #deleteditemfont = lm.deleteditemfont
#        #itemfont = lm.itemfont
#
#        
#        task = lm.task
#        n= lm.index
#     
#        if task.completed:
#            table.item(n,0).setIcon(lm.idx0)
#            for c,col in enumerate(col_order[1:],start=1):
#                item = QtWidgets.QTableWidgetItem(*display[col](task))
#                item.setForeground(qcolor('gray'))
#                item.setFont(lm.itemfont[task.priority])
#                table.setItem(n, c, item)
#
#        elif task.deleted:
#            for c,col in enumerate(col_order[1:],start=1):
#                item = QtWidgets.QTableWidgetItem(*display[col](task))
#                item.setForeground(qcolor('gray'))
#                item.setFont(lm.deleteditemfont[task.priority])
#                table.setItem(n, c, item)
#                
#        elif getattr(task, type_).textcolor:
#            for c,col in enumerate(col_order[1:],start=1):
#                item = QtWidgets.QTableWidgetItem(*display[col](task))
#                item.setForeground(qcolor(getattr(task, type_).textcolor))
#                item.setFont(lm.itemfont[task.priority])
#                table.setItem(n, c, item)
#        else:
#            for c,col in enumerate(col_order[1:],start=1):
#                item = QtWidgets.QTableWidgetItem(*display[col](task))
#                item.setFont(lm.itemfont[task.priority])
#                table.setItem(n, c, item)
#                    
#                
#        return z
#    return fn
