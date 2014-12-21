
#@+leo-ver=5-thin
#@+node:slzatz.20141220151846.46: * @file C:/Users/szatz/mylistman_p3/lmglobals.py
#@@first
#@@nowrap
#@@tabwidth -4
#@@language python
#@+others
#@+node:slzatz.20120318160356.1672: ** imports
import os
import urllib.request, urllib.error, urllib.parse
import configparser as configparser

import PyQt5.QtGui as QtGui
import PyQt5.QtWidgets

#@+node:slzatz.20120318160356.1673: ** constants
cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
CONFIG_FILE = os.path.join(cwd,'mylistmanager.ini')
#DB_FILE = os.path.join(cwd,'lmdb','mylistmanager.db')
IMAGES_DIR = os.path.join(cwd,'bitmaps')
PLUGIN_DIR = os.path.join(cwd,'plugins')
USER_ICONS = 'folder_icons'
CORE_ICONS = ''
LOG_FILE = os.path.join(cwd,'logfile.txt')
XAPIAN_DIR = os.path.join(cwd,'xapian')
del cwd

xapianenabled = False

key = None
timestamp = None



#@+node:slzatz.20120318160356.1674: ** configparser
config = configparser.RawConfigParser()
config.read(CONFIG_FILE)

# this could be in listmanager since not sure any other module needs to know
if config.has_option('Application', 'plugins'):
    plugins_enabled = config.getboolean('Application', 'plugins')
else:
    plugins_enabled = False


#@+node:slzatz.20120331211211.1719: ** create_action
def create_action(parent, text, slot=None, shortcut=None, icon=None, icon_res=None, image=None, tip=None, checkable=False):

    action = PyQt5.QtWidgets.QAction(parent)
    action.setText(text)
    
    if icon:
        action.setIcon(QtGui.QIcon(os.path.join(IMAGES_DIR, icon))) #works without extension but finds bmp before png
    elif icon_res:
        action.setIcon(QtGui.QIcon(icon_res)) # uses resource.py
    elif image:
        pxmap = QtGui.QPixmap()
        pxmap.loadFromData(image, 'PNG')
        action.setIcon(QtGui.QIcon(pxmap))
        
    if shortcut:
        action.setShortcut(shortcut)

    tip = tip if tip else text.lstrip('&')
    action.setToolTip(tip)
    action.setStatusTip(tip)

    #note: default overload is triggered(bool checked=False) meaning that slots would have to have two arguments, self and checked
    #the below gets you the non-default triggered() overload
    if slot:
        #action.triggered[()].connect(slot)
        action.triggered.connect(slot) #12-17-2014
        #action.connect(slot)
        
    if checkable:
        action.setCheckable(True)

    return action

#@+node:slzatz.20120331211211.1721: ** add_actions
def add_actions(target, actions):
    for action in actions:
        if action is None:
            target.addSeparator()
        else:
            target.addAction(action)
            
#@+node:slzatz.20120424065252.1679: ** internet_accessible
def internet_accessible():
    try:
        response=urllib.request.urlopen('http://www.google.com',timeout=1)
        return True
    except urllib.error.URLError as err: pass
    return False
#@+node:slzatz.20120623191748.1701: ** decorators
#@+node:slzatz.20120623191748.1703: *3* check_modified
def check_modified(f):
    ''' A decorator that checks if there have been any field changes'''
    
    def fn(lm, *args, **kwargs):
        if lm.modified:
            print("self.modified dict is not empty and so savenote was called")
            print("self.modified={0}".format(repr(lm.modified)))
            print("The method that triggered savenote was {0}".format(f.__name__))

            lm.savenote()
        return f(lm, *args, **kwargs)
    return fn
    
#@+node:slzatz.20120623191748.1705: *3* check_task_selected
def check_task_selected(f):
    '''A decorator that checks to see if a task was selected before an action'''
    
    def fn(lm, *args, **kwargs):
        if not lm.task or lm.index==-1:
            PyQt5.QtWidgets.QMessageBox.information(lm,  'Note', "No row is selected")
            return
        else:
            return f(lm, *args, **kwargs)
    return fn
#@+node:slzatz.20120623191748.1707: *3* update_whooshdb
def update_whooshdb(f):
    ''' A decorator that updates the xapiandb because of a task change'''
    
    def fn(lm, *args, **kwargs):
        z = f(lm, *args, **kwargs)
        #if xapianenabled:
        lm.updatewhooshentry(lm.task)
        return z
    return fn
   
   
#@+node:slzatz.20120701110419.1710: *3* update_row
def update_row(f):
    ''' A decorator that updates the changed row in the table'''

    def fn(lm, *args, **kwargs):
        z = f(lm, *args, **kwargs)
        
        #@+<<intro>>
        #@+node:slzatz.20120701110419.1711: *4* <<intro>>
        #qtablewidgetitem = QtGui.QTableWidgetItem
        qcolor = QtGui.QColor
        #qicon = QtGui.QIcon
        display = lm.display #dict that just holds display lambda's
            
        type_ = 'folder' if lm.Properties['tab']['type'] == 'context' else 'context'

        table = lm.table
        col_order = lm.col_order

        #deleteditemfont = lm.deleteditemfont
        #itemfont = lm.itemfont

        #@-<<intro>>
        
        task = lm.task
        n= lm.index
     
        #@+<<updaterow>>
        #@+node:slzatz.20120701110419.1712: *4* <<updaterow>>
        if task.completed:
            table.item(n,0).setIcon(lm.idx0)
            for c,col in enumerate(col_order[1:],start=1):
                item = PyQt5.QtWidgets.QtGui.QTableWidgetItem(*display[col](task))
                item.setForeground(qcolor('gray'))
                item.setFont(lm.itemfont[task.priority])
                table.setItem(n, c, item)

        elif task.deleted:
            for c,col in enumerate(col_order[1:],start=1):
                item = PyQt5.QtWidgets.QTableWidgetItem(*display[col](task))
                item.setForeground(qcolor('gray'))
                item.setFont(lm.deleteditemfont[task.priority])
                table.setItem(n, c, item)
                
        elif getattr(task, type_).textcolor:
            for c,col in enumerate(col_order[1:],start=1):
                item = PyQt5.QtWidgets.QtGui.QTableWidgetItem(*display[col](task))
                item.setForeground(qcolor(getattr(task, type_).textcolor))
                item.setFont(lm.itemfont[task.priority])
                table.setItem(n, c, item)
        else:
            for c,col in enumerate(col_order[1:],start=1):
                item = PyQt5.QtWidgets.QTableWidgetItem(*display[col](task))
                item.setFont(lm.itemfont[task.priority])
                table.setItem(n, c, item)
            



                    
        #@-<<updaterow>>
                
        return z
    return fn
#@-others
#@-leo
