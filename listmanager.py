'''
A program to manage information
python3-compatible version
'''
import sip  
from PyQt5 import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
QAction = QtWidgets.QAction

import notetextedit
import lmdialogs

import os
from time import asctime, sleep
import sys
import datetime
import platform
import configparser as configparser
import json
import urllib.request, urllib.parse, urllib.error
import re
import textwrap
import base64
import io
import importlib #for plugins
import argparse
import tempfile
from subprocess import Popen
import resources
import requests

# age is cython-created function more to check cython out than that it was absolutely necessary
try:
    from age_c import age
except ImportError:
    print("Unable to import age c funtion")
    def age(z):
        if z > 1:
            return "{} days".format(z)
        elif z == 1:
            return "yesterday"
        else:
            return "today"

import base64
from optparse import OptionParser
from functools import partial

import markdown2 as markdown
import config as c
import lmglobals as g #moved from below on 12-21-2014

#note synchronize2 is imported in If __name__ == main to delay import until logger defined
import lminterpreter

from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, KEYWORD, NUMERIC
import whoosh.index as index
from whoosh.query import Term, Or, Prefix
from whoosh.filedb.filestore import FileStorage
from whoosh import analysis
from lmdb import *

parser = argparse.ArgumentParser(description='Command line options mainly for debugging purposes.')

# for all of the following: if the command line option is not present then the value is the opposite of the action
parser.add_argument('-q', '--qsettings', action='store_false', help="Don't use QSettings during startup (will *not* save to QSettings on closing")
parser.add_argument('-c', '--console', action='store_false', help="Disable the use of the console so it doesn't swallow errors during __init__")
parser.add_argument('-i', '--ini', action='store_false', help="Don't load the tabs on startup that are stored in the ini file (will save to ini file on closing)")
parser.add_argument('-s', '--sqlite', action='store_true', help="Use (or create if --db_create is active) a local sqlite database")
parser.add_argument('--db_create', action='store_true', help="Create new database - use -s to indicate you want a local sqlite db")

args = parser.parse_args()

if args.sqlite:
    #g.DB_URI = g.sqlite_uri
    session = local_session
    engine = local_engine
else:
    #g.DB_URI = g.rds_uri 
    session = remote_session
    engine = remote_engine

if args.db_create:
    print("\n\nDo you want to create a new database and do a synchonization with Toodledo(Y/N)?")
    reply = input("Y/N:") 
    if reply.lower() == 'y':
        DB_EXISTS = False
        print("DB_EXISTS=",DB_EXISTS," -- meaning we are about to create a new database")

    else:
        sys.exit()
        
else:
    DB_EXISTS = True
        
if not DB_EXISTS and args.sqlite:
    db_directory = os.path.split(g.LOCAL_DB_FILE)[0]

    try:
        os.makedirs(db_directory)
    except OSError:
        sys.exit("Could not create directory for sqlite database")

from lmdb import *

if args.db_create:
    engine.echo = True

VERSION = '0.8'

TODAY = datetime.date.today()

#decorators
check_modified = g.check_modified
check_task_selected = g.check_task_selected
update_whooshdb = g.update_whooshdb
update_row = g.update_row

class ListManager(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(ListManager, self).__init__(parent)
        
        
        self.setWindowTitle("My Listmanager")

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.showMessage("Ready", 5000)

        g.pb = self.pb = QtWidgets.QProgressBar(status) # putting pb 'into' lmglobals
        status.addPermanentWidget(self.pb)
        self.pb.hide()

        self.status = status

        if args.qsettings:
            settings = QtCore.QSettings()

            if settings.contains("MainWindow/Geometry"):
                self.restoreGeometry(settings.value('MainWindow/Geometry'))
                self.restoreState(settings.value('MainWindow/State')) 

     
        if not DB_EXISTS:
            
            context = Context(tid=0, title='No Context')
            session.add(context)
            folder = Folder(tid=0, title="No Folder")
            session.add(folder)
            session.commit()
            
            # eliminate tasks with ids < 4 because I SetItemData based on sqlite id but if that data is < 4, I know it's a collapse bar
            # so I don't want a real task to have an id < 4
            # fortunately right now sqlite doesn't reclaim the ids of deleted items
            # sqlite starts numbering ids at 1
            
            # this creates the tasks and then deletes them to consume the 0 through 3 ids; don't need/can't delete -1
            
            for p in range(3): 
                task = Task('p')
                session.add(task)
            
            session.commit()
            
            task = Task("My very first task written from " + platform.uname()[1]) # need one item to remain or will reuse starting at zero
            session.add(task)
            session.commit()
            
            for p in range(1,4):
                task = session.query(Task).get(p)
                if task: # shouldn't need this 
                    session.delete(task)
            
            session.commit()
            
            sync = Sync('client')
            #sync = session.query(Sync).get('client') #switching server to timestamp
            session.add(sync)
            sync.timestamp = datetime.datetime.fromordinal(1)
            sync.unix_timestamp = 1
            session.commit()

        # self.PageProperties is the dictionary of dictionaries that carry the various properties for each notebook page
        # the key is the splitter for that page which is the widget managed by the tabmanager
        # self.PageProperties[splitter] = ...
        self.PageProperties = {} 

        self.index = -1 # this is row number of the currently highlighted row
        self.modified = {} # tracks whether note or db_note have been modified

        self.priorities = [-1,0,1,2,3] # the possible priorities - matches Toodledo

        self.active_search = None
        self.search_contexts = None # for when we're searching specific context(s)

        self.sync_log = ''
        self.vim_files = {} #dictionary to hold files being edited in VIM
        action =partial(g.create_action, self)
        add_actions = g.add_actions
        IMAGES_DIR = g.IMAGES_DIR
        im_file = partial(os.path.join, IMAGES_DIR)

        self.arrows = ('bitmaps/down_arrow.png','bitmaps/up_arrow.png')

        self.idx1 = QtGui.QIcon(':/bitmaps/box.png')
        self.idx0 = QtGui.QIcon(im_file('filledwhitebox.bmp'))

        star = QtGui.QIcon(':/bitmaps/star.png')
        starno = QtGui.QIcon(im_file('starno.gif'))

        note_icon = QtGui.QIcon(':/bitmaps/note.png')

        alarm_clock = QtGui.QIcon(':/bitmaps/alarm-clock.png')

        alarm_clock_disable = QtGui.QIcon(':/bitmaps/alarm-clock-disable.png')

        #if DB_EXISTS:
        if os.path.exists("indexdir"):
            self.ix = index.open_dir("indexdir")
            self.searcher = self.ix.searcher()
        else:
            self.searcher = None

        self.logger = g.logger = Logger(self, logfile=g.LOG_FILE)

        a_transfer = action("Transfer to Editor", self.logger.transfer)
        a_save = action("Save to Log File", self.logger.save)
        a_clear_text = action("Clear Window", self.logger.clear_text)
        a_save_and_clear = action("Save to Log File and Clear Window", self.logger.save_and_clear)

        self.logger.setContextMenuPolicy(Qt.ActionsContextMenu)
        add_actions(self.logger, (a_transfer, a_save, a_clear_text, a_save_and_clear))

        self.db_note = QtWidgets.QTextEdit()
        self.db_note.setAcceptRichText(False)
        self.db_note.setObjectName('plain_note')
        self.db_note.setEnabled(False)
        self.db_note.textChanged.connect(self.note_modified)

        self.note_manager = NoteManager(main_window=self)
        self.note_manager.menuBar().setVisible(False)
        self.note_manager.format_toolbar.setEnabled(False)
        self.note = self.note_manager.note
        self.highlighter = self.note.highlighter
        self.highlighter.setDocument(None) #the default state is that there is no document highlighting
        self.note.setEnabled(False)
        self.note.textChanged.connect(self.note_modified)

        self.tab_manager = QtWidgets.QTabWidget()
        self.tab_manager.setMovable(True)
        self.tab_manager.setTabsClosable (True)
        self.tab_manager.setObjectName("Main Tab")

        self.setCentralWidget(self.tab_manager)

        # tab manager context menu set later when action have been created

        self.tab_manager.tabCloseRequested.connect(self.closetab) #SIGNAL("tabCloseRequested(int)")
        self.tab_manager.currentChanged.connect(self.onpagechange) # new style signal/slot

        # the menus created below will become contextmenu menus for each table widget that is created
        # they are also used as the menus in the toolbar

        #createprioritymenu()
        self.p_menu = QtWidgets.QMenu(self)
        priorityGroup = QtWidgets.QActionGroup(self)
        for p in reversed(self.priorities):
            a = action(str(p), partial(self.setpriority, priority=p), checkable=True)
            priorityGroup.addAction(a)
            self.p_menu.addAction(a)

        #self.c_menu
        self.createcontextmenu()

        #self.f_menu
        self.createfoldermenu()

        loc_dict = {}
        loc_dict = dict(globals())
        loc_dict['self'] = locals()['self']

        if args.console:
            self.console = lminterpreter.MyConsole(self, loc_dict)
        else:
            self.console = QtWidgets.QWidget()

        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        DockWidget = QtWidgets.QDockWidget("Log", self)
        DockWidget.setObjectName("log")
        DockWidget.setAllowedAreas(Qt.BottomDockWidgetArea|Qt.RightDockWidgetArea)
        DockWidget.setWidget(self.logger)
        #self.addDockWidget(QtCore.Qt.RightDockWidgetArea, DockWidget) #QtCore.Qt.BottomDockWidgetArea

        DockWidget2 = QtWidgets.QDockWidget("Note", self)
        DockWidget2.setObjectName("note")
        DockWidget2.setAllowedAreas(Qt.RightDockWidgetArea)
        DockWidget2.setFeatures (QtWidgets.QDockWidget.DockWidgetMovable|QtWidgets.QDockWidget.DockWidgetFloatable) ##### but not closable
        DockWidget2.setWidget(self.note_manager)
        self.addDockWidget(Qt.RightDockWidgetArea, DockWidget2)

        DockWidget2.topLevelChanged.connect(self.shownotemenus)

        DockWidget3 = QtWidgets.QDockWidget("DB Note", self)
        DockWidget3.setObjectName("db_note")
        DockWidget3.setAllowedAreas(Qt.RightDockWidgetArea)
        DockWidget3.setWidget(self.db_note)
        self.addDockWidget(Qt.RightDockWidgetArea, DockWidget3)

        DockWidget4 = QtWidgets.QDockWidget("Console", self)
        DockWidget4.setObjectName("console")
        DockWidget4.setAllowedAreas(Qt.RightDockWidgetArea)
        DockWidget4.setWidget(self.console) #to get all the locals going to set in __main__
        self.addDockWidget(Qt.RightDockWidgetArea, DockWidget4)

        self.DockWidget4 = DockWidget4 #need to get at this DockWidget from __main__

        self.addDockWidget(Qt.RightDockWidgetArea, DockWidget) #Qt.BottomDockWidgetArea

        # Klugy but makes sure that the note and db_note dockwidgets are
        # the right size when they are undocked - couldn't find any other way
        rect = self.geometry()
        z = (rect.x() + 75, rect.y() + 100, 800, 500)

        DockWidget.setFloating(True)
        DockWidget.setGeometry(*z)
        DockWidget.setFloating(False)

        DockWidget2.setFloating(True)
        DockWidget2.setGeometry(*z)
        DockWidget2.setFloating(False)

        DockWidget3.setFloating(True)
        DockWidget3.setGeometry(*z)
        DockWidget3.setFloating(False)

        DockWidget4.setFloating(True)
        DockWidget4.setGeometry(*z)
        DockWidget4.setFloating(False)

        # makes sure that Note is first (on the left) and the selected tab
        self.tabifyDockWidget(DockWidget2, DockWidget3)
        self.tabifyDockWidget(DockWidget2, DockWidget4)
        DockWidget2.raise_()

        log_dock_action = DockWidget.toggleViewAction()
        note_db_dock_action = DockWidget3.toggleViewAction() 

        self.note_manager.menuBar().setVisible(False)
        self.note_manager.format_toolbar.setEnabled(False)
        self.note.setEnabled(False)
        self.db_note.setEnabled(False)

        filemenu = self.menuBar().addMenu("&File")

        a_opencontext = action("&Context(s)...", partial(self.opentabs2, type_='context'), icon_res=':/bitmaps/open_context') # doesn't need png
        a_openfolder = action("&Folders(s)...", partial(self.opentabs2, type_='folder'), icon_res=':/bitmaps/open_folder')
        a_opentag = action("&Tag(s)...", partial(self.opentabs, type_='tag'), icon_res=':/bitmaps/open_tag')

        m_openmenu = filemenu.addMenu("&Open")
        add_actions(m_openmenu, (a_opencontext, a_openfolder, a_opentag))

        a_recent_items_all = action("All", partial(self.showrecentitems, tab_value='ALL'))
        a_recent_items_created = action("Created (on this client)", partial(self.showrecentitems, tab_value='Created'))
        a_recent_items_modified = action("Modified", partial(self.showrecentitems, tab_value='Modified'))
        a_recent_items_completed = action("Completed", partial(self.showrecentitems, tab_value='Completed'))

        m_recentfiles = filemenu.addMenu("&Recent Tasks")
        add_actions(m_recentfiles, (a_recent_items_all, a_recent_items_created, a_recent_items_modified, a_recent_items_completed))

        a_starstab = action("Create Stars Tab",
                                     partial(self.createnewtab,
                                     title = '*Stars*',
                                     tab = {'type':'app','value':'star'}, 
                                     filter_by = {'column':'context', 'value':'*ALL'},
                                     sort ={'column':'priority','direction':0},
                                     col_order = ['box', 'alarm', 'priority', 'star', 'title', 'note', 'context', 'startdate'],
                                     collapsible = False,
                                     show_completed=False),
                                                         
                                     checkable=False, icon='display_starred')
                                                                         
        a_alarmtab = action("Create Alarm Tab", 
                                     partial(self.createnewtab,
                                     title = 'Alarms',
                                     tab ={'type':'app','value':'alarm'},
                                     filter_by = {'column':'context', 'value':'*ALL'},
                                     sort ={'column':'duedate','direction':0},
                                     collapsible = False,
                                     show_completed=False,
                                     col_order = ['box','priority','alarm','duedate','duetime','star','title','note','context']),

                                     checkable=False, icon='display_alarmed')

        add_actions(filemenu, (None, a_starstab, a_alarmtab))

        a_multitab_folders = action("Folders", partial(self.create_multi_tab, type_='folder'))
        a_multitab_contexts = action("Contexts", partial(self.create_multi_tab, type_='context'))

        m_multimenu = filemenu.addMenu(QtGui.QIcon(os.path.join(IMAGES_DIR, 'display_all_todo_related.png')), "Create Multi-value Tab") #os.path.join(IMAGES_DIR, '{0}.png'.format(icon)))
        add_actions(m_multimenu, (a_multitab_folders, a_multitab_contexts))

        a_newcontext = action("&New Context", self.newcontext)
        a_savenote = action("Save Note", self.savenote, 'Ctrl+S')
        a_closetab = action("Close Current Tab", self.closetab)
        a_close_all = action("Close All", self.close_all)
        a_saveconfiguration = action("Save Configuration", self.saveconfiguration)
        a_loadconfiguration = action("Load Configuration", self.loadconfiguration)
        a_savetab = action("Save Tab", self.savetab)

        a_quit = action("&Quit", self.close, "Ctrl+Q", "filequit", "Close the application")


        add_actions(filemenu, (None, a_newcontext, None, a_savenote, None, a_closetab, a_close_all, None, a_saveconfiguration, a_loadconfiguration, 
                                        None,  a_savetab))

        if args.qsettings:
            savedtabs = settings.value('savedtabs')
            self.savedtabs = [] if savedtabs is None else savedtabs # shouldn't be necessary but seems to be 10.27.2012
        else:
            self.savedtabs = []
            
        self.m_savedtabsmenu = filemenu.addMenu("Saved Tabs")

        for i, properties in enumerate(self.savedtabs):
            aa = self.createsavedtab(properties, i)
            self.m_savedtabsmenu.addAction(aa)

        filemenu.addSeparator() 
        filemenu.addAction(a_quit)

        taskmenu = self.menuBar().addMenu("&Task")

        a_newtask = action("&New Task", self.newtask, 'Alt+I', icon='list_add')
        a_togglecompleted = action("Toggle Completed", self.togglecompleted, icon_res=':/bitmaps/filledbox.png') 
        a_togglestar = action("Toggle Star", self.togglestar, icon_res=':/bitmaps/star.png', checkable=True)
         
        p_action = QtWidgets.QAction(QtGui.QIcon(':/bitmaps/priority'), 'Set Priority', self)

        self.a_select_tags = action("Select &Tag", self.select_tags, 'Ctrl+T', icon='tag-new')
        a_selectfolder = action("Select Folder", self.selectcontextfolder, 'Ctrl+F', icon='folder_new')
        a_selectcontext = action("Select Context", self.selectcontextfolder, icon='context')
        a_duedate = action("Set Duedate/Time", self.setduedate, icon='office-calendar')
        a_deletetask = action("Delete/Undelete", self.deletetask, icon_res=':/bitmaps/delete.png')

        add_actions(taskmenu, (a_newtask, None, a_togglecompleted, a_togglestar, p_action, a_selectcontext, a_selectfolder, self.a_select_tags, 
                                              a_duedate, None, a_deletetask)) 
        displaymenu = self.menuBar().addMenu("&Display")

        a_refresh = action("&Refresh Display", self.refresh, 'Ctrl+R', icon='view-refresh')
        a_refreshlistonly = action("Refresh &List Only", self.refreshlistonly)
        a_note = action("Dock/Undock Note", partial(self.ondockwindow, dw=DockWidget2), 'Ctrl+N')
        a_dbnote = action("Dock/Undock DB Note", partial(self.ondockwindow, dw=DockWidget3), 'Ctrl+D')
        a_logger = action("Dock/Undock Log", partial(self.ondockwindow, dw=DockWidget, cur=False, check_task_selected=False), 'Ctrl+L')
        a_console = action("Dock/Undock Console", partial(self.ondockwindow, dw=DockWidget4, check_task_selected=False), 'Alt+C')
        a_modifycolumns =  action("Modify Columns...", self.modifycolumns, icon='modifycolumns')
        a_showcompleted = action("Show Completed", self.showcompleted, icon='showcompleted', checkable=True)
        a_showhidefilterby = action("Show\Hide Filter-by List", self.showhidefilterby, checkable=True)
        a_changefilterbycolumn = action("Change Column to Filter By", self.changefilterbycolumn)
        a_toggle_collapsible = action("Collapsible by Priority", self.toggle_collapsible, checkable=True, icon='collapsible')
        a_change_tab_name = action("Rename or save search as ...", self.change_tab_name)
        a_removesort = action("Remove sorting", self.removesort, icon='sort')
        add_actions(displaymenu, (a_refresh, a_refreshlistonly, None, log_dock_action, note_db_dock_action, None, a_note, a_dbnote, a_console, a_logger, None, a_change_tab_name, a_showcompleted, a_toggle_collapsible, a_removesort, None, a_showhidefilterby, a_changefilterbycolumn, a_modifycolumns))

        self.a_showcompleted = a_showcompleted
        self.a_showhidefilterby = a_showhidefilterby
        self.a_toggle_collapsible = a_toggle_collapsible

        a_folder_icon_color = action("Folder", partial(self.iconcolordialog, type_='folder'))
        a_context_icon_color = action("Context", partial(self.iconcolordialog, type_='context'))
        m_icon_color = displaymenu.addMenu("Chose Icon/Text Color")
        add_actions(m_icon_color, (a_folder_icon_color, a_context_icon_color))
        toolmenu = self.menuBar().addMenu("&Tools")

        a_synchronize_local = action("&Synchronize (local)", self.synchronize, 'Alt+S', icon='arrow_ns')
        a_synchronize_remote = action("Synchronize (remote)", partial(self.synchronize, local=False))
        a_showsync_log = action("Show Synchronize Log", self.showsync_log)
        a_showdeleted = action("Show Deleted", self.showdeleted)
        a_print_note_to_log = action("Print Note to Log", self.print_note_to_log)
        a_close_event = action("Write ini file", self.closeEvent)
        a_on_simple_html2log = action("Print simple html to log", self.on_simple_html2log)
        a_ontaskinfo = action("Show Task Info", partial(self.ontaskinfo, retrieve_server=True))
        a_deletecontexts = action("Delete Context(s)...", partial(self.deletecontexts, type_='context'))
        a_updatewhooshentry = action("Update Whoosh Entry Manually", self.updatewhooshentry) 
        a_get_tabinfo = action("Show Tab Info", self.get_tabinfo)
        a_whooshtaskinfo = action("Check Whoosh Task Position", self.whooshtaskinfo)
        a_removedeadkeywords = action("Remove Unused Keywords ...", self.removedeadkeywords)
        a_renew_alarms = action("Renew Expired Alarms", self.renew_alarms)
        a_startdate = action("Set Startdate", partial(self.setdate, which='startdate'), icon='office-calendar')
        a_resetinterp = action("Reset Console", self.resetinterp)
        a_clearsavedtabs = action("Clear Saved Tabs", self.clearsavedtabs)
        a_create_whooshdb = action("Create Whoosh Database", self.create_whooshdb2)
        a_edit_note_in_vim = action("Edit note in vim", self.edit_note_in_vim, 'Alt+N')

        add_actions(toolmenu, (a_synchronize_local, a_synchronize_remote, a_showsync_log, None, a_updatewhooshentry,
                                         a_whooshtaskinfo, None, a_print_note_to_log, a_close_event, a_on_simple_html2log, None,
                                         a_ontaskinfo, a_get_tabinfo, None, a_showdeleted, None, a_removedeadkeywords, 
                                         a_deletecontexts, None, a_renew_alarms, a_startdate, a_resetinterp, a_clearsavedtabs, None, a_create_whooshdb, a_edit_note_in_vim))
                                         
        a_create_image_string = action("Create image string", self.create_image_string)

        toolmenu.addAction(a_create_image_string)

        # plugins need to define a function that takes ListManager() => self as an argument - essentially makes it a method
        # They need to include title, icon, function

        if g.plugins_enabled:
            plugin_files = os.listdir(g.PLUGIN_DIR)
            
            if plugin_files:
                pluginmenu = self.menuBar().addMenu("Plugin")
            
            for name in plugin_files:
                if name.endswith(".py") and not name.startswith("_"):
                    modulename = 'plugins.{}'.format(name.rsplit('.',1)[0])
                    module = importlib.import_module(modulename)
            
                    a_plugin = action(module.title, partial(module.function, self), image=module.image)
                    pluginmenu.addAction(a_plugin)
                
        helpmenu = self.menuBar().addMenu("&Help")
        a_showversions = action("Versions", self.showversions)
        add_actions(helpmenu, (a_showversions,))
        #Toolbar
        fileToolbar = self.addToolBar("File")
        fileToolbar.setObjectName("FileToolBar")
        add_actions(fileToolbar, (a_opencontext, a_openfolder, a_opentag, a_starstab, a_alarmtab, None))

        if g.plugins_enabled:

            plugin_actions = pluginmenu.actions()
            
            if plugin_actions:
                pluginToolbar = self.addToolBar("Plugins")
                pluginToolbar.setObjectName("Plugins ToolBar")
            
            for a_plugin in plugin_actions:
                pluginToolbar.addAction(a_plugin)
            
        p_action.setMenu(self.p_menu)
        self.p_action = p_action

        a_incrementpriority = action("Increment Priority", self.incrementpriority, icon='priority')
        a_incrementpriority.setMenu(self.p_menu) 

        a_selectfolder = action("Select Folder", partial(self.selectcontextfolder, type_='folder'), 'Ctrl+F', icon='folder_new')
        a_selectfolder.setMenu(self.f_menu)
        self.a_selectfolder = a_selectfolder

        a_selectcontext = action("Select Context", partial(self.selectcontextfolder, type_='context'), icon='context')
        a_selectcontext.setMenu (self.c_menu)
        self.a_selectcontext = a_selectcontext 

        tasktb = self.addToolBar("Task")
        tasktb.setObjectName("TaskToolBar")

        add_actions(tasktb, (a_newtask, None, a_togglecompleted, a_togglestar, a_deletetask, a_incrementpriority, a_selectcontext, a_selectfolder, self.a_select_tags, a_duedate))

        displayToolbar = self.addToolBar("Display")
        displayToolbar.setObjectName("DisplayToolBar")
        add_actions(displayToolbar, (a_refresh, None, a_showcompleted, a_toggle_collapsible, a_removesort, None, a_modifycolumns))
        toolsToolbar = self.addToolBar("Tools")
        toolsToolbar.setObjectName("Tools ToolBar")
        toolsToolbar.addAction(a_synchronize_local)
        search_tb = QtWidgets.QToolButton()
        search_tb.setIcon(QtGui.QIcon('bitmaps/magnifier-left.png'))
        search_tb.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        search_menu = QtWidgets.QMenu(search_tb)
        a_search_all = action("Search All Contexts", partial(self.searchcontext, search='all'), checkable=True)
        a_search_all.setChecked(True)
        self.a_search_all = a_search_all

        search_context = action("Search Context...", partial(self.searchcontext, search='context'), checkable=True)

        search_what = QtWidgets.QActionGroup(self)
        search_what.addAction(a_search_all)
        search_what.addAction(search_context)

        search_menu.addAction(a_search_all)
        search_menu.addAction(search_context)

        search_tb.setMenu(search_menu)

        lineEdit = QtWidgets.QLineEdit()
        lineEdit.setWindowIcon(QtGui.QIcon("bitmaps/refresh.png"))    
        lineEdit.setFixedSize(140,25)
        searchToolbar=self.addToolBar("Search")
        searchToolbar.setObjectName("SearchToolBar")
        searchToolbar.addWidget(search_tb)
        searchToolbar.addWidget(lineEdit)

        self.search = lineEdit

        #lineEdit.setDisabled(False)
        #self.query_parse_flag = 10   
        self.search.textEdited.connect(self.do_search)

        # needs to be here because the actions need to have been defined (in Menus section)
        self.tab_manager.setContextMenuPolicy(Qt.ActionsContextMenu)
        add_actions(self.tab_manager, (a_change_tab_name, a_showcompleted, a_showhidefilterby, a_toggle_collapsible, a_savetab))#####
        format1 = '%m/%d/%y'
        format2 = '%m/%d/%y %H:%M:%S'
        format3 =  '%H:%M'

        center = Qt.AlignHCenter
        left = Qt.AlignLeft

        qicon = QtGui.QIcon
                
        now = datetime.datetime.now

        self.col_info = {
            'box':        {'label':'',         'width':20, 'align': center, 'sortable':False,'fixed':True, 'action':self.togglecompleted,'display': None},
            'priority':   {'label':'p',        'width':20, 'align': center, 'sortable':True, 'fixed':True, 'action':self.on_pmenu,   'display': lambda x: (str(x.priority),)},
            'star':       {'label':'s',        'width':22, 'align': center, 'sortable':True, 'fixed':True, 'action':self.togglestar,     'display': lambda x: (star if x.star else starno,"")},
            'folder':     {'label':'folder',   'width':100,'align': center, 'sortable':True, 'fixed':False,'action':partial(self.selectcontextfolder, type_='folder'),   'display': lambda x:(x.folder.title if x.folder.tid else '',)},
            'f_icon':       {'label':'f-i',        'width':25, 'align': center, 'sortable':False,'fixed':True, 'action':partial(self.selectcontextfolder, type_='folder'),   'display': lambda x: self.folder_icons[x.folder.title]},
            'c_icon':       {'label':'c-i',        'width':25, 'align': center, 'sortable':False,'fixed':True, 'action':partial(self.selectcontextfolder, type_='context'),   'display': lambda x: self.context_icons[x.context.title]},
            'title':      {'label':'title',    'width':550,'align': center, 'sortable':True, 'fixed':False,'action':lambda x: None,     'display': lambda x:(x.title,)},
            'tid':        {'label':'tid',      'width':75, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (str(x.tid) if x.tid else '',)},
            'folder_tid': {'label':'f_tid',    'width':75, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (str(x.folder_tid) if x.folder_tid else '',)},
            'modified':   {'label':'modified', 'width':85, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (x.modified.strftime(format1) if x.added else '',)},
            'completed':  {'label':'completed','width':75, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (x.completed.strftime(format1) if x.completed else '',)},
            'added':      {'label':'added',    'width':75, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (x.added.strftime(format1) if x.added else '',)},
            'created':    {'label':'created',  'width':115, 'align': center, 'sortable':True, 'fixed':True, 'action':lambda x: None,     'display': lambda x: (x.created.strftime(format2) if x.created else '',)},
            'duedate':    {'label':'duedate',     'width':66, 'align': center, 'sortable':True, 'fixed':True, 'action':self.setduedate,  'display': lambda x: (x.duedate.strftime(format1) if x.duedate else '',)},
            'duetime':    {'label':'duetime',     'width':55, 'align': center, 'sortable':True, 'fixed':True, 'action':self.setduedate,  'display': lambda x: (x.duetime.strftime(format3) if x.duetime else '',)},
            'startdate':    {'label':'date',     'width':75, 'align': center, 'sortable':True, 'fixed':False, 'action':partial(self.setdate, which='startdate'),  'display': lambda x: (age((TODAY - x.startdate).days) if x.startdate else '',)},
             'alarm':      {'label':'a',        'width':20,'align':center, 'sortable':False, 'fixed':True, 'action':self.setduedate,       'display': lambda x: (alarm_clock if x.duetime>now() else alarm_clock_disable,'') if x.remind else ('',)},
            'tag':        {'label':'tag',      'width':60, 'align': center, 'sortable':True, 'fixed':False,'action':self.select_tags,      'display': lambda x: (x.tag if x.tag else '',)},
            'note':       {'label':'notes',    'width':30, 'align': center, 'sortable':False,'fixed':True,'action':partial(self.ondockwindow, dw=DockWidget2),     'display': lambda x: (note_icon, '') if x.note else ('',)},   
            'context':    {'label':'context',  'width':80, 'align': center, 'sortable':True, 'fixed':False,'action':partial(self.selectcontextfolder, type_='context'),  'display': lambda x: (x.context.title,)}, 
            }

        self.display = {x:self.col_info[x]['display'] for x in self.col_info}
        self.action = {x:self.col_info[x]['action'] for x in self.col_info}

        #self.display['icon'] = lambda x: self.folder_icons[x.folder.title]

        # the initial set of properties for each page
        #tab['type']  are strings like 'context', 'folder', 'active_search', 'saved_search','all', 'recent' and 
        #tab['value'] are strings like 'work', 'todo' and for searches the query terms and 
        #both type and value need to be filled in when creating tab
        self.InitialProperties = {
                                'tab':{'type':None,'value':None},
                                'title':None, #set when creating tab
                                'tab_icon':None,
                                'filter_by':{'column':'folder','value':'*ALL'},
                                'sort':{'column':None,'direction':0}, #don't sort to start with
                                'show_completed':False,
                                'split_window':True,
                                'priority_display':{'-1':False,'0':False,'1':False,'2':True,'3':True}, #just have 2 and 3 expanded for starters, probably should be [True, False, True ...] and not a dic
                                'col_widths':None, #will be defined when table created
                                'col_order':['box','startdate','priority','star','title','note'], # important initial columns and their order; completed needs to be first
                                'collapsible':True
                                }     
                                
        normal = QtGui.QFont()
        bold = QtGui.QFont()
        bold.setBold(True)
        strikeout = QtGui.QFont()
        strikeout.setStrikeOut(True)
        boldstrikeout = QtGui.QFont(bold)
        boldstrikeout.setStrikeOut(True)
                 
        self.itemfont = {-1:normal, 0:normal, 1:normal, 2:normal, 3:bold}         
        self.deleteditemfont = {-1:strikeout, 0:strikeout, 1:strikeout, 2:strikeout, 3:boldstrikeout}
        
        self.folder_icons = {c.title:(QtGui.QIcon("bitmaps/folder_icons/{}.png".format(c.title)), '') for c in session.query(Folder)}

        #self.folder_icons = {}
        #for f in session.query(Folder):
        #    if f.image:
        #        pxmap = QtGui.QPixmap()
        #        pxmap.loadFromData(f.image, 'PNG')
        #        icon = (QtGui.QIcon(pxmap), '') 
        #    else:
        #        icon = ('',)
        #    self.folder_icons[f.title] = icon

        self.context_icons = {c.title:(QtGui.QIcon("bitmaps/folder_icons/{}.png".format(c.title)), '') for c in session.query(Context)}
        #self.context_icons = {}
        #for c in session.query(Context):
        #    if c.image:
        #        pxmap = QtGui.QPixmap()
        #        pxmap.loadFromData(c.image, 'PNG')
        #        icon = (QtGui.QIcon(pxmap), '') 
        #    else:
        #        icon = ('',)
        #    self.context_icons[c.title] = icon
            
        #{'context': self.context_icons, 'folder' self.folder_icons, 'app':{'star':fjdsl,'alarm':jfkdjfdk, 'search':lkfdldskf}, 'recent', {}, 'tag': {}}

        self.icons = {'context': self.context_icons, 'folder':self.folder_icons, 'app':{'star':(QtGui.QIcon(':/bitmaps/star.png'),''),'alarm':(QtGui.QIcon(':/bitmaps/alarm-clock.png'),'')}}
         
        # the below work
        #self.context_icons = {c.title:(QtGui.QIcon("bitmaps/context_icons/{}".format(c.icon)), '') if c.icon else ('',) for c in session.query(Context)}
        #self.folder_icons = {f.title:(QtGui.QIcon("bitmaps/folder_icons/{}".format(f.icon)), '') if f.icon else ('',) for f in session.query(Folder)}

        # new user location
        # self.folder_icons = {f.title:(QtGui.QIcon("bitmaps/user/{}".format(f.icon)), '') if f.icon else ('',) for f in session.query(Folder)}
        # self.context_icons = {c.title:(QtGui.QIcon("bitmaps/user/{}".format(c.icon)), '') if c.icon else ('',) for c in session.query(Context)}

        #user_icon = partial(os.path.join,'bitmaps','user')
        #user_icon(f.icon)

        self.myevent = MyEvent()

        try:
            import myevents
        except ImportError as e:
            print(e)
            self.myevent.signal.connect(lambda x,y:None)
        else:
            self.myevent.signal.connect(myevents.responses) # since only one signal don't need ...signal[str, dict].connect....

        # watch files that vim is editing
        self.fs_watcher = QtCore.QFileSystemWatcher()
        self.fs_watcher.fileChanged.connect(self.file_changed_in_vim)
        
        if DB_EXISTS:
            if args.ini:
                QtCore.QTimer.singleShot(0, self.loadtabs)
        else:
            if self.confirm("Do you want to perform an initial synchonization with Toodledo?"):
                QtCore.QTimer.singleShot(0, self.downloadtasksfromserver)
                print("hello")

    def loadtabs(self):
        # open the tabs that were last open when the application was closed
        
        if g.config.has_option('Properties', 'tab_properties'):
            properties = json.loads(g.config.get('Properties', 'tab_properties'))
            
            self.setUpdatesEnabled(False)

            # note the one problem with this is that it prevents the fullsize method from stretching
            # columns to the full width of the table widget
            # I think the main reason to block signals was not to trigger onpagechange
            # although not sure that's a big deal so should probably try to remove these (May 24, 2012)
            self.tab_manager.blockSignals(True)
                
            for tab in properties:
                self.createnewtab(**tab)
        
            self.tab_manager.blockSignals(False)
        
            if g.config.has_option('Properties', 'current' ):
                current = g.config.getint('Properties', 'current')
                if current != -1:
                    self.tab_manager.setCurrentIndex(current)
                    tab_count = self.tab_manager.count()
                    if current == tab_count -1:  # need to trigger if the current page is the last tab since there wouldn't be a pagechage
                        self.onpagechange(current) 
        
            self.setUpdatesEnabled(True)

    def downloadtasksfromserver(self):
        '''
        sends all tasks on server down to client
        '''
        print_("Got here in downloadtasksfromserver")
        if not toodledo2.keycheck():
            print_("Unable to get toodledo key")
            return
        
        synchronize2.downloadtasksfromserver()
        
        if self.confirm("Would you like to enable full-text search (uses Whoosh)?"):
            self.create_whooshdb()
            
            self.ix = index.open_dir("indexdir")
            self.searcher = self.ix.searcher()

    def note_modified(self):
        which = self.sender().objectName()
        self.modified[which] = True

    def createfoldermenu(self):
        self.f_menu = QtWidgets.QMenu(self)
        
        folders = session.query(Folder).filter(Folder.tid!=0).all()
        folders.sort(key=lambda f:str.lower(f.title))
        no_folder = session.query(Folder).filter_by(tid=0).one()
        folders = [no_folder] + folders
        
        iconGroup = QtWidgets.QActionGroup(self)
        
        for f in folders:
            #icon = 'folder_icons/'+f.icon if f.icon else ''
            #a = g.create_action(self, f.title, partial(self.updatefolder, title=f.title), icon=icon , checkable=True)
            a = g.create_action(self, f.title, partial(self.updatefolder, title=f.title), image=f.image , checkable=True)
            iconGroup.addAction(a)
            self.f_menu.addAction(a)

    def createcontextmenu(self):
        self.c_menu = QtWidgets.QMenu(self)
        
        contexts = session.query(Context).filter(Context.tid!=0).all()
        contexts.sort(key=lambda c:str.lower(c.title))
        no_context = session.query(Context).filter_by(tid=0).one()
        contexts = [no_context] + contexts
        
        self.contextGroup = QtWidgets.QActionGroup(self)
        
        for c in contexts:
            a = g.create_action(self, c.title, partial(self.updatecontext, title=c.title), image=c.image, checkable=True)
            self.contextGroup.addAction(a)
            self.c_menu.addAction(a)
            
    def createimagewithoverlay(self, base_image='bitmaps/unordered-list-tag.png', overlay_image=None):

        base_image=QtGui.QImage(base_image)
        imagewithoverlay = QtGui.QImage(base_image.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        painter = QtGui.QPainter(imagewithoverlay)

        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.fillRect(imagewithoverlay.rect(), Qt.transparent)

        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, base_image)

        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver);
        painter.drawImage(10, 10, overlay_image);

        painter.end()

        return imagewithoverlay

    def createsavedtab(self, properties, n): 

        #for i, properties in enumerate(self.savedtabs): # probably wouldn't need self
     
        aa = QtGui.QAction(properties['title'], self)
        
        qimage = QtGui.QImage()
        if properties['tab']['type'] == 'folder':
            z = session.query(Folder).filter_by(title=properties['tab']['value']).one()
            qimage.loadFromData(z.image, 'PNG')
        elif properties['tab']['type'] == 'context':
            z = session.query(Context).filter_by(title=properties['tab']['value']).one()
            qimage.loadFromData(z.image, 'PNG')
        elif properties['tab']['type'] == 'star':
            qimage.load(':/bitmaps/star.png', 'PNG')
        else:
            qimage.loadFromData('', 'PNG')
        
        image = self.createimagewithoverlay(overlay_image=qimage)
        pxmap = QtGui.QPixmap()
        pxmap.convertFromImage(image)
        aa.setIcon(QtGui.QIcon(pxmap))
            
        self.connect(aa, QtCore.SIGNAL("triggered()"), partial(self.loadtab, n))
        
        return aa

        #self.m_savedtabsmenu.addAction(aa) # would need self
        #self.savedtabsactions.append(aa) # probably wouldn't need self

    def shownotemenus(self, floating):
        self.note_manager.menuBar().setVisible(floating)

    def createnewtab(self, **kw):
        '''
        must have title=xxxx and tab={'type':xxxx,'value':yyyy}
        self.InitialProperties = {
                            'tab':{'type':None,'value':None},
                            'title':None, #set when creating tab
                            'tab_icon':None,
                            'filter_by':{'column':'folder','value':'*ALL'},
                            'sort':{'column':None,'direction':0}, #don't sort to start with
                            'show_completed':False,
                            'split_window':True,
                            'priority_display':{'-1':False,'0':False,'1':False,'2':True,'3':True}, #just have 2 and 3 expanded for starters, probably should be [True, False, True ...] and not a dic
                            'col_widths':None, #will be defined when table created
                            'col_order':['box','priority','star','title','note','tag','folder'], # important initial columns and their order; completed needs to be first
                            'collapsible':True
                            }     
        '''

        Properties = dict(self.InitialProperties)
        Properties.update(kw)
        self.Properties = Properties
        self.col_order = Properties['col_order'] #not sure if I should just use Properties['col_order']

        self.LBox = LBox = QtWidgets.QListWidget()

        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        splitter.addWidget(LBox)

        self.table = table = self.createtable() 

        splitter.addWidget(table)

        if 'window_sizes' not in Properties:
            Properties['window_sizes'] = [0,500] #[75,500] -> [0,500] should hide filterby list

        splitter.setSizes(Properties['window_sizes'])

        self.PageProperties[splitter] = Properties # addTab triggers onpagechange so this needs to preceed
        
        # tab icon - it is no longer part of Properties but is determined by the nature of the tab 
        # (ie folder -specifically which one, context - specifically which one, star and alarm)#####
        # However the below if elif is really ugly and maybe it's a self.tab_icons dict that's 
        #{'context': self.context_icons, 'folder' self.folder_icons, 'app':{'star':fjdsl,'alarm':jfkdjfdk, 'search':lkfdldskf}, 'recent', {}, 'tag': {}}
        # tab_icon = self.tab_icons[tab_type].get(tab_value)
        
        if Properties['tab']['type'] == 'tag':
            tab_icon = QtGui.QIcon(':/bitmaps/tag.png')
        else:
            tab_icon = self.icons.get(Properties['tab']['type'], {}).get(Properties['tab']['value'], (None,))[0]
        
        tab_num = self.tab_manager.addTab(splitter, tab_icon, Properties['title']) if tab_icon else self.tab_manager.addTab(splitter, Properties['title']) 

        sort = Properties['sort']
        if sort['column']:
            col = Properties['col_order'].index(sort['column']) #prob in some places just do col_order Properties['col_order']
            img = QtGui.QIcon(self.arrows[sort['direction']])
            col_item = table.horizontalHeaderItem(col)
            col_item.setIcon(img)

        self.tab_manager.setCurrentIndex(tab_num) # moved up for tabtooltip on 1/15/2012 - might not work
        
        self.refresh()

        self.status.showMessage("Successfully loaded %s"%Properties['title'])

        LBox.currentItemChanged.connect(self.filterlist) #12-19-2014

    def createtable(self):

        Properties = self.Properties
        col_order = Properties['col_order']

        table = Table(self, col_info=self.col_info, col_order=col_order, col_widths=Properties['col_widths']) #self.col_order
        table.setItemDelegateForColumn(col_order.index('title'), TitleDelegate(self)) # Custom Delegate for title editor

        header = table.horizontalHeader()
        #header.setStretchLastSection(True) ##### screws up table.columnCount among other things
        
        header.sectionResized.connect(self.updatecolumnwidths) #SIGNAL("sectionResized(int,int,int)")
        header.sectionMoved.connect(self.updatecolumnorder) #SIGNAL("sectionMoved(int,int,int)")
        header.sectionClicked.connect(self.columnclick) #SIGNAL('sectionClicked(int)')

        table.cellClicked.connect(self.cellclick) #SIGNAL("cellClicked(int,int)")
        table.itemSelectionChanged.connect(self.itemselected) #SIGNAL("itemSelectionChanged()")

        # this is the signal sent by the table when a cell editor is closed - other choice is to send it "manually" and not do this
        table.itemDelegateForColumn(col_order.index('title')).commitData.connect(self.save_title) # SIGNAL("commitData(QWidget*)")
        table.return_sc = QtWidgets.QShortcut(QtGui.QKeySequence("Return"), table, self.edittableitem) #for some reason context=QtCore.Qt.WidgetShortcut doesn't work but set below
        table.return_sc.setContext(Qt.WidgetShortcut)

        if Properties['col_widths'] is None: 
            Properties['col_widths'] = [table.columnWidth(n) for n in range(table.columnCount())]  # might want len(col_order)

        table.setContextMenuPolicy(Qt.ActionsContextMenu)
        g.add_actions(table, (self.p_action, self.a_selectcontext, self.a_selectfolder, self.a_select_tags))

        return table

    def replacetable(self, context_title=None):
        '''Called by modifycolumns and updatecolumnorder'''

        splitter = self.tab_manager.currentWidget()
        
        self.table.deleteLater()

        self.table = table = self.createtable()
        sizes = splitter.sizes()
        splitter.addWidget(table)
        splitter.setSizes([sizes[0], 0, sizes[1]]) 
        self.displayitems()

    @check_modified
    def onpagechange(self, page_index):
        '''This is the slot for self.tab_manager - SIGNAL("currentChanged(int)") - returns the index'''
        print_("At the beginning of onpagechange")

        if page_index == -1:
            return

        splitter = self.tab_manager.currentWidget()

        self.Properties = Properties = self.PageProperties[splitter]
        
        # ? following is necessary, not sure it's a speed up but it does also simplify reading the code
        #maybe should just set in the Table instances ie self.table.col_order
        self.col_order = Properties['col_order'] # ? necessary, it's a maybe speed that also simplifies reading the code

        self.LBox = splitter.widget(0)
        self.table = splitter.widget(1)

        self.setWindowTitle("Listmanager - type: %s; value: %s filtered by: %s"%(Properties['tab']['type'], Properties['tab']['value'],Properties['filter_by']['column']))

        self.itemselected()

        self.a_showcompleted.setChecked(self.Properties['show_completed'])
        self.a_showhidefilterby.setChecked(bool(self.Properties['window_sizes'][0]))
        self.a_toggle_collapsible.setChecked(self.Properties['collapsible'])

        self.table.return_sc.setEnabled(True) ##### not sure I need this but may be belt & suspenders b/o escape key
        
        print_("onpagechange -- table width {}".format(self.table.size().width()))
        print_("title width = {}".format(Properties['col_widths'][self.col_order.index('title')]))
        
        print_("onpagechange -- page_index {0}".format(page_index))

    def cellclick(self, r, c):

        '''
        The cellClicked(int,int) SIGNAL comes after the 
        "itemSelectionChanged() SIGNAL. 
        '''
        
        # note that self-index can still be -1 but act of clicking on a cell should set it to something other than -1
        #if self.index == -1: # now that the number of rows is correct shouldn't need this but we'll see
         #   return
        
        # set in table's mousePressEvent method
        if not self.table.leftpressed:
            return
        
        id_ = self.table.item(self.index,0).data(Qt.UserRole)

        if id_ < 4:
            self.Properties['priority_display'][str(id_)] = not self.Properties['priority_display'][str(id_)]
            self.refreshlistonly() 
            return

        # the first click into an unselected row should selelct the row but otherwise not do anything
        if not self.new_row: 
            self.action[self.col_order[c]](False) # to deal with qActions sending checked = False; it's reason in column stuff it's now lambda x
        else:
            self.new_row = False
            
    def edittableitem(self): # Native table text editor
        '''uses delegate'''

        print("In edittableitem")
        print("return pressed")

        if self.index != -1: 

            item = self.table.item(self.index, self.Properties['col_order'].index('title')) #self.Properties['col_order'] = self.col_order.index
            self.table.editItem(item)
            
            # I believe that the table detects the keying of a RETURN in QLineEdit and then issues a CommitData and we don't want that RETURN to be intercepted
            # Will enable RETURN again in save_title
            self.table.return_sc.setEnabled(False) 

    def updatecolumnwidths(self, col, old, new):  
        '''slot for sectionResized(int,int,int)'''
        print_("in updatecolumnwidths")
        #print_("col = {0}; old = {1}, new = {2}".format(col, old, new))
        #print_("{}".format(repr(self.tab_manager.currentWidget())))
        #print_("{}".format(repr(self.table)))

        self.Properties['col_widths'][col] = new

    def updatecolumnorder(self, logical, old, new):
        '''slot for sectionMoved(int,int,int)'''
        
        moved_col = self.Properties['col_order'][old]
        moved_width = self.Properties['col_widths'][old]
        
        del self.Properties['col_order'][old]
        del self.Properties['col_widths'][old]
        
        self.Properties['col_order'].insert(new,moved_col)
        self.Properties['col_widths'].insert(new,moved_width)

        self.replacetable()

    def removecolumn(self, c):

        del self.col_order[c]
        del self.Properties['col_widths'][c]
        
        self.replacetable()
        
    @update_row
    @check_task_selected
    @check_modified
    def togglecompleted(self, checked):

        task = self.task 

        if not task.completed:
            task.completed = datetime.datetime.now().date()
        else:
            task.completed = None
            # below not done in updaterow
            self.table.item(self.index,0).setIcon(self.idx1)

        session.commit()
        
    @update_row
    @check_task_selected
    @check_modified
    def togglestar(self, checked):    

        self.task.star = not self.task.star
        session.commit()

        #self.a_togglestar.setChecked(self.task.star) # decided cute but unnecessary

    def on_pmenu(self, checked):
        self.p_menu.exec_(QtGui.QCursor.pos())

    # order is bottom to top
    @update_row
    @check_task_selected
    @check_modified
    def incrementpriority(self, checked):
        task = self.task
        priority = task.priority
        priority += 1
        if priority ==4:
            priority = -1

        task.priority = priority
        session.commit()

        p_list = self.priorities[:]
        p_list.reverse()
        i = p_list.index(priority)
        self.p_menu.actions()[i].setChecked(True)
        
        self.myevent.signal.emit('incrementpriority', {'task':task, 'priority':priority})

    # order is bottom to top
    @update_row
    @check_task_selected
    def setpriority(self, checked, priority=0):

        self.task.priority = priority
        session.commit()
        
    @update_row
    @check_modified
    @check_task_selected
    def setduedate(self, checked):

        task = self.task
        idx = self.index

        table = self.table
        Properties = self.Properties

        if task.duedate:
            duedate = task.duedate
            d = QtCore.QDate(duedate.year, duedate.month,duedate.day)
        else:
            d = QtCore.QDate.currentDate()
            
        if task.duetime:
            duetime = task.duetime
            t = QtCore.QTime(duetime.hour, duetime.minute, duetime.second)
        else:
            t = QtCore.QTime.currentTime()
            
        qdt = QtCore.QDateTime(d,t)
        
        state = bool(task.remind)

        dlg = lmdialogs.TaskDueDateTime(title="Select a date", qdatetime=qdt, state=state, parent=self)

        if dlg.exec_(): # if cancel - dlg.exec_ is False
            qdatetime = dlg.qdatetime # QDateTime
            
            #################### this shouldn't be necessary when they all go back to naive
            task.duetime = None #sqlite tries to copmare old datetime to new and if it's naive compared to aware get TypeError
            session.commit()
            
            task.duedate = task.duetime = datetime.datetime.fromtimestamp(qdatetime.toTime_t())
            
            if dlg.setalarm:
                task.remind = 1
            else:
                task.remind = None # or maybe should be zero since that's what server will send back
            
            session.commit()

    @update_row
    @check_modified
    @check_task_selected
    def setdate(self, checked, which=None): #not a qAction method but need this because treating them the same

        task = self.task
        idx = self.index

        table = self.table
        Properties = self.Properties

        taskdate = getattr(task, which)
        if taskdate:
            date = QtCore.QDate()
            date.setDate(taskdate.year, taskdate.month,taskdate.day)
        else:
            date = None

        dlg = lmdialogs.TaskDueDate(title="Select a date", date=date)

        if dlg.exec_(): # if cancel - dlg.exec_ is False
            date = dlg.date # QDate

            print_(repr(date.getDate()))
            z = date.getDate()

            dt = datetime.datetime(*z)
            setattr(task, which, dt.date())
            session.commit()

    @check_task_selected
    @check_modified
    def selectcontextfolder(self, checked, type_='context'): 
        '''
        Called by Select Context of Task Menu and toolbar context push button
        Displays a dialog with both existing contexts and place to type new context
        '''
        task = self.task
        
        if type_ == 'context':
            things = self.context_icons
            sel = task.context.title if task.context else None # is this necessary or is no context still a context?
        else:
            things = self.folder_icons
            sel = task.folder.title if task.context else None # is this necessary or is no context still a context?
        
        dlg = lmdialogs.SelectContextFolder("Select", things, parent=self, initial_selection=sel)

        if dlg.exec_():
            list_choice = dlg.listWidget.selectedItems()[0].text()
            new_name = dlg.new_name

            print_("list_choice={0}\nnew_name={1}".format(list_choice, new_name))

            # new entry trumps a choice from the list
            title = new_name if new_name else list_choice
            if type_=='context':
                self.updatecontext(title=title)
            else:
                self.updatefolder(title=title)

    @update_row
    @update_whooshdb
    @check_task_selected
    def updatefolder(self, title=None):

        task = self.task

        folder = session.query(Folder).filter_by(title=title).first()

        if folder:
            task.folder = folder
        else:
            reply = QtWidgets.QMessageBox.question(self,
                                              "Confirmation",
                                              "Do you want to create a new folder?",
                                              QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                print("You said no to creating a new folder")
                return
            
            temp_tid = Temp_tid(title=title, type_='folder')
            session.add(temp_tid)
            session.commit()

            # will need to change the tid when we upload the folder to the server
            new_folder = Folder(title=title, tid=temp_tid.id)
            task.folder = new_folder 
            session.add(new_folder)
            
            a_newfolder = g.create_action(self, new_folder.title, partial(self.updatefolder, new_folder.title), checkable=True)
            self.iconGroup.addAction(a_newcontext)
            self.f_menu.addAction(a_newfolder)   
            
        session.commit()

    @update_row
    @update_whooshdb
    @check_task_selected
    def updatecontext(self, checked, title=None):
        '''
        Called by each of the table widget context submenu actions and the toolbar menu widget
        and by method selectcontext (and appears in synchronize
         if there is a new context, because menus need to be updated)
        '''
        task = self.task

        context = session.query(Context).filter_by(title=title).first()
        if context:
            task.context = context
        else:

            reply = QtGui.QMessageBox.question(self, "Confirmation", "Do you want to create a new context?",
                                                                QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)

            if reply == QtGui.QMessageBox.No:
                print_("You said no to creating a new context")
                return

            temp_tid = Temp_tid(title=title, type_='context')
            session.add(temp_tid)
            session.commit()

            # will need to change the tid when we upload the folder to the server
            new_context = Context(title=title, tid=temp_tid.id)
            task.context = new_context 
            session.add(new_context)
            
            a_newcontext = g.create_action(self, new_context.title, partial(self.updatecontext, new_context.title), checkable=True)
            self.contextGroup.addAction(a_newcontext)
            self.c_menu.addAction(a_newcontext)   

        session.commit()

    @check_task_selected
    @check_modified
    def select_tags(self, checked):
        
        context = self.task.context.title
        titles = sorted(self.get_keywords('context', context), key=str.lower)

        sel = [kw.title for kw in self.task.keywords]
        
        print("sel={0}".format(sel))

        dlg = lmdialogs.MultiChoiceOrNew("Select", titles, parent=self, initial_selection=sel)

        if dlg.exec_():
            selections = dlg.choices
            newentries = dlg.newentry
            
            newentries = [z.strip() for z in newentries.split(',') if z] #if gets rid of '' new entries

            print("selections={0}\nnewentries={1}".format(selections, newentries))
            
            selections_lower = [z.lower() for z in selections]
            
            # remove any new entries that match selections in the listwidget
            newentries = [z for z in newentries if z.lower() not in selections_lower]
            
            # make sure that any new entries are really new and also not just different because of letter case, if not new, use existing
            for n,text in enumerate(newentries):
                result = dlg.listWidget.findItems(text, Qt.MatchFixedString) #case insensitive match
                if result:
                    newentries[n] = result[0].text()
                
            # this worked too to eliminate letter case issues
            #title_dict = dict(zip([t.lower() for t in titles],titles))
            #newentries = [title_dict.get(z.lower(), z) for z in newentries]
            
            print("newentries={0}".format(newentries))
            
            tag = selections + newentries
            
            print("new tag list = {0}".format(tag))
            
            self.updatetag(tag)

    @update_row
    @update_whooshdb
    @check_task_selected
    def updatetag(self, tag):
        '''tag is a list''' 

        task = self.task
        
        # select_tags should be sending clean list with stripped white space
        # would be better creating tag after doing keywords see below
        #task.tag = ",".join(tag) if tag else None
        #session.commit()
        
        print_("In updatetag: tag={0}".format(tag))

        for tk in task.taskkeywords:
            session.delete(tk)
        session.commit()
        
        for kwn in tag: # tag will be '' when task.tag is None
            keyword = session.query(Keyword).filter_by(name=kwn).first()
            if keyword is None:
                keyword = Keyword(kwn)
                session.add(keyword)
            tk = TaskKeyword(task,keyword)
            session.add(tk)

        session.commit()
        
        #task.tag is a string of keywords separated by commas
        task.tag = ','.join(kwn.name for kwn in task.keywords)
        session.commit()

    #@update_row #doesn't work for a new task but abbreviated version in body of method
    @check_modified
    def newtask(self, checked):

        table = self.table
        Properties = self.Properties

        #Should probably check that 'tab' is in Properties
        tab_type = Properties['tab']['type']
        tab_value = Properties['tab']['value']

        task = Task(priority=3, title='<New Item>')
        
        ############################## this is now in a plugin myevent - could be an option that all new items remind/alarm
        #if 1:
        #    task.remind = 1
        #    task.duedate=task.duetime = datetime.datetime.now() + datetime.timedelta(days=1)
        #############################################################
        
        session.add(task)
        session.commit()

        self.task = task

        if tab_type in ('context', 'folder'):
            mapper_class = Context if tab_type == 'context' else Folder
            tab_value_object = session.query(mapper_class).filter_by(title=tab_value).one()
            setattr(task, tab_type, tab_value_object) 
            session.commit()
        elif tab_type == 'app' and tab_value=='star':
            task.star = True
            session.commit()
            
        task.startdate = datetime.datetime.today().date() ############### may 2, 2012
        session.commit()

        self.note.clear() # these trigger note_edit
        self.db_note.clear()
        self.modified = {} 

        table.insertRow(0)

        item0 = QtWidgets.QTableWidgetItem(self.idx1,'')
        item0.setData(Qt.UserRole, int(task.id))
        table.setItem(0, 0, item0)            

        self.index = 0
        
        # an abbreviated version of @update_row - note that can't be at the end of this method but should be here
        type_ = 'folder' if Properties['tab']['type'] == 'context' else 'context'
        color = QtGui.QColor(getattr(task, type_).textcolor)
        for c,col in enumerate(self.col_order[1:],start=1):
            item = QtWidgets.QTableWidgetItem(*self.display[col](task))
            item.setFont(self.itemfont[task.priority])
            item.setForeground(color)
            table.setItem(0, c, item)
        
        item = table.item(0, self.col_order.index('title'))
        table.setCurrentItem(item)

        table.editItem(item) #initiates the editing of the table item and in this case triggers delegate code; could call edittableitem but the latter would need to be changed
        self.table.return_sc.setEnabled(False) ## this means return will not be intercepted

        self.new_row = False 
        
        self.myevent.signal.emit('set_reminder', {'task':task, 'session':session})

    @update_row
    @check_modified
    @check_task_selected
    def deletetask(self, checked):

        self.task.deleted = not self.task.deleted
        session.commit()
            
    @update_row
    @update_whooshdb
    def save_title(self, editor=None):  #editor=None was added on April 22, 2012 but surprising it worked without it.
        '''
        ... QtCore.SIGNAL("commitData(QWidget*)"), self.save_title) --> widget is the editor
        '''
        print_("In save_title")

        task = self.task
        
        task.title = title = editor.text()
        session.commit()

        print_("title={0} was saved to the database".format(title))

        # if this doesn't get enabled then won't be able to edit items
        self.table.return_sc.setEnabled(True) 

    @check_modified
    def newcontext(self, evt=None):
        '''
        Creates a new context on the client that will be synced to the server
        Also creates a new tab with the context
        '''

        result = QtGui.QInputDialog.getText(self,"New Context","Enter new context:", QtGui.QLineEdit.Normal)

        new_context_title, b = result

        if not b:
            return

        context_titles = [c.title.lower() for c in session.query(Context)]

        if new_context_title.lower() in context_titles:

            reply = QtGui.QMessageBox.warning(self,
                                 "Duplicate Context",
                                 "Context '{0}' already exists".format(new_context_title))

            return

        reply = QtGui.QMessageBox.question(self,
                                "Create New Context?",
                                "Are you sure you want to create Context '{0}'?".format(new_context_title),
                                QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            temp_tid = Temp_tid(title=new_context_title, type_='context') 
            session.add(temp_tid)
            session.commit()
            new_context = Context(tid=temp_tid.id, title=new_context_title) 
            session.add(new_context)
            session.commit()

            a = g.create_action(self, new_context_title, partial(self.updatecontext, new_context_title), checkable=True)
            self.contextGroup.addAction(a)
            self.c_menu.addAction(a)

            self.createnewtab(title=new_context_title, tab={'type':'context', 'value':new_context_title})

    @check_modified
    def opentabs(self, check, type_=None):

        class_ = {'folder':Folder, 'context':Context, 'tag':Keyword}

        open_titles = [d['tab']['value'] for d in list(self.PageProperties.values()) if d['tab']['type']==type_]
        all = session.query(class_[type_]).all()
        unopened_titles = sorted([z.title for z in all if not z.title in open_titles], key=str.lower)

        dlg = lmdialogs.ChoiceDlg("Select", unopened_titles, parent=self)
        
        if dlg.exec_():
            for title in dlg.choices:
                tab_title ="{} ({})".format(title, type_[0])
                filter_by = {'column':'folder','value':'*ALL'} if type_=='context' else {'column':'context','value':'*ALL'}
                self.createnewtab(title=tab_title, tab={'type':type_, 'value':title}, filter_by=filter_by)


    @check_modified
    def opentabs2(self, checked, type_='context'): # check is there because qaction.trigger.connect(method) returns false

        '''
        Called by File OpenTabs
        '''

        things = self.context_icons if type_=='context' else self.folder_icons
        
        dlg = lmdialogs.SelectContextFolder("Select", things, parent=self, initial_selection=None, multi=True, new_entry=False)

        if dlg.exec_():
            
            for item in dlg.listWidget.selectedItems():
                title = item.text()
                tab_title ="{} ({})".format(title, type_[0])
                filter_by = {'column':'folder','value':'*ALL'} if type_=='context' else {'column':'context','value':'*ALL'}
                tab_icon = things[title]
                
                self.createnewtab(title=tab_title, tab={'type':type_, 'value':title}, tab_icon=tab_icon, filter_by=filter_by)

    def showrecentitems(self, tab_value=None):

        show_completed = True if tab_value in ('ALL', 'Completed') else False

        self.createnewtab(
                            title = '*Recently* '+tab_value,
                            tab = {'type':'recent', 'value':tab_value},
                            filter_by={'column':'context','value':'*ALL'}, 
                            show_completed=show_completed)


    @check_modified
    def create_multi_tab(self, type_=None):
        
        class_ = {'folder':Folder, 'context':Context, 'tag':Keyword}

        filter_by = {'column':'folder','value':'*ALL'} if type_=='context' else {'column':'context','value':'*ALL'}

        all = session.query(class_[type_]).all()
        names = sorted([z.title for z in all], key=str.lower)
        if len(names) < 2:
            #should issue a dialog
            return

        dlg = lmdialogs.ChoiceDlg("Select", names, parent=self)
        
        tab_icon = os.path.join('folder_icons', 'scream')
        
        if dlg.exec_():
            tab_title = '-'.join(dlg.choices)
            tab_value = ','.join(dlg.choices)
            self.createnewtab( title=tab_title,
                                         tab={'type':type_+'s', 'value':tab_value},
                                         tab_icon=tab_icon,
                                         filter_by=filter_by,
                                         sort ={'column':'priority','direction':0},
                                         collapsible = False,
                                         col_order = ['box','icon','added','priority','star','title','context','tag','folder'],
                                         col_widths = None,
                                         show_completed=False)
                            

    def showallitems(self):
        self.createnewtab('*ALL', tab_type='all', filter_by={'column':'context','value':'*ALL'})

    def deletecontexts(self, type_=None):
        '''
        Note that you can delete contexts and folders on the server and
        have those changes propogate properly to the client.  
        ''' 
        
        reply = QtGui.QMessageBox.question(self,
                                    "Delete Context",
                                    "Would you like to delete one or more contexts - this is serious?",
                                    QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.No:
            return
        
        class_ = {'folder':Folder, 'context':Context, 'tag':Keyword}

        list_ = session.query(class_[type_]).all()
        
        titles = sorted([z.title for z in list_ if z.tid != 0], key=str.lower)
        if not len(titles):
            print_("Nothing to delete")
            #should show a dialog
            return

        dlg = lmdialogs.ChoiceDlg("Select", titles, parent=self)
        
        if dlg.exec_():
            list_ = []
            for title in dlg.choices:
                x = session.query(class_[type_]).filter_by(title=title).first()
                list_.append(x)
            
            print(list_)
            return       
            
            log = ''
            for c in list_:
                c.deleted = True #!!!!!! can't do this until create this field
                tasks = c.tasks
                for t in tasks:
                    t.context_tid = 0
                    log+= "{title} now has 'No Context'\n".format(title=t.title)
        
            session.commit()

    @check_modified
    def close_all(self):

        pc = self.tab_manager.count()
        self.tab_manager.setCurrentIndex(pc-1)

        # the following may be necessary or you  mayget errors when deleting pages - need to check but no reason for signals anyway
        self.tab_manager.blockSignals(True)

        while self.tab_manager.count():
            self.closetab()

        self.note.clear()
        #note that Clearing does set self.modified (eg {'name':1})
        self.modified = {}

        self.tab_manager.blockSignals(False)

    @check_modified
    def closeEvent(self, event=None): #event is necessary

        cg = g.config
        
        #if args.qsettings: #removed "if" on 10.27.2012
        settings = QtCore.QSettings()
        settings.setValue("MainWindow/Geometry",self.saveGeometry())
        settings.setValue("MainWindow/State",self.saveState())
        settings.setValue("savedtabs", self.savedtabs) # appears to write None if self.savedtabs is []

        # save tabs and their properties
        x=[]
        for p in range(self.tab_manager.count()):
            sw = self.tab_manager.widget(p)
            Properties = self.PageProperties[sw] 
            tab = Properties['tab']
      
            if  tab['value'] != 'active_search':
                x.append(Properties)

        if not cg.has_section('Startup'):
            cg.add_section('Startup')

        tab = self.Properties['tab']

        if  tab['value'] != 'active_search':
            cg.set('Startup', 'current_tab', json.dumps(self.Properties))

        if not cg.has_section('Properties'):
            cg.add_section('Properties')
            
        cg.set('Properties', 'tab_properties', json.dumps(x))
        current = self.tab_manager.currentIndex()
        cg.set('Properties', 'current', current)

        with open(g.CONFIG_FILE, 'w') as configfile:
            cg.write(configfile)

    @check_modified
    def saveconfiguration(self):
        
        cg = g.config

        # save tabs and their properties
        cg = configparser.RawConfigParser()
        
        z=[]
        for p in range(self.tab_manager.count()):
            sw = self.tab_manager.widget(p)
            Properties = self.PageProperties[sw] 
            tab = Properties['tab']
      
            if  tab['value'] != 'active_search':
                #z.append((tab.get('type'),tab.get('value'))) # this would be better but involves other changes
                z.append((Properties.get('title'), tab.get('type'),tab.get('value'))) #don't need title

        cg.add_section('Startup')
        cg.set('Startup', 'tabs', json.dumps(z))
        
        tab = self.Properties['tab']
        if  tab['value'] != 'active_search':
            cg.set('Startup', 'current_tab', json.dumps(self.Properties['tab']))

        tab_properties = []
        for Properties in list(self.PageProperties.values()):
            tab = Properties['tab']

            if  tab['value'] != 'active_search':
                #t = (tab['type'], tab['value']) 05132012
                tab_properties.append(Properties)  

        cg.add_section('Properties')

        cg.set('Properties', 'tab_properties', json.dumps(tab_properties))
        
        cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
        file_ = os.path.join(cwd,'untitled.lmc')
        file_ = QtGui.QFileDialog().getSaveFileName(self, "Save File As",file_, "LMC (*.lmc)")
        print(file_)

        with open(file_, 'w') as configfile:
            cg.write(configfile)

    @check_modified
    def loadconfiguration(self):
        reply = QtGui.QMessageBox.warning(self,
                                                   "Confirmation",
                                                    "This will close all the current tabs; Do you want to proceed?",
                                                     QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:

            self.close_all()
            
            file_ = QtGui.QFileDialog().getOpenFileName(self, "Open File", os.getcwd(), "LMC (*.lmc)")
            print(file_)
            g.config = configparser.RawConfigParser()
            g.config.read(file_) # if file doesn't exist returns [] else returns list of files
            
            QtCore.QTimer.singleShot(0, self.loadtabs)
        
    @check_modified
    def savetab(self):
        
        if  self.Properties['tab']['value'] == 'active_search':
            return

        ln = len(self.savedtabs)
        if ln > 3:
            del self.savedtabs[-1]
            
        self.savedtabs.insert(0, dict(self.Properties))
        
        self.m_savedtabsmenu.clear()
        #self.savedtabsactions = []
        
        for i, properties in enumerate(self.savedtabs):
            aa = self.createsavedtab(properties, i)
            self.m_savedtabsmenu.addAction(aa)
            #self.savedtabsactions.append(aa)
         
         #seems like you would need the following if you were going to update the toolbar and probably don't need toolbar actions at all
         #for a in self.savedtabsactions:
             #fileToolbar.addAction(a)
            
    @check_modified
    def loadtab(self, n):
        
        properties = self.savedtabs[n]
        
        self.createnewtab(**properties)
        
    @check_modified
    def closetab(self, L=-1):
        
        '''
        Important:  the current Index is where the tab is at the time so it represents a position and is not permanently associated
        with a specific tab and its content -- the current index of the far left tab is always 0, the next tab is 1, etc.
        
        L is returned correctly  even if you click the close box on a tab that doesn't have focus
        However, the action of clicking on the tab close box doesn't change the current Index
        That needs to be done explicitly -- see below
        '''
        
        print("tab requested to close is {0}: {1}".format(L, self.tab_manager.tabText(L)))

        if L==-1: # called by menu item
            L = self.tab_manager.currentIndex() #a tab changes its Index to whatever position it is moved to (makes things easier)
        else:
            self.tab_manager.setCurrentIndex(L) #because clicking on an inactive tab's close doesn't set current index
            
        # self.Properties will be correct because setting current index generates a pagechange
            
        tab = self.Properties['tab']

        # two situations - tab being closed is inc_search or inc_search is higher num than tab being closed
        # this will need to change because the incremental search can move (qt)
        if tab['value'] =='active_search':
            self.search.clear() # this may generate a text updated event that we need to catch
            self.active_search = None

        #current widget should be correct because of setting current index
        splitter = self.tab_manager.currentWidget() # this is not working and is removing another tab
        self.tab_manager.removeTab(L)
        splitter.deleteLater() # not sure if you need this or not

        del self.PageProperties[splitter]





    @update_row
    @update_whooshdb
    @check_task_selected
    def savenote(self, check=False):

        if 'plain_note' in self.modified:  #self.modified.get('plain_note', False)
            text = self.db_note.toPlainText()
        elif 'note' in self.modified:
            text = self.note.toMarkdown()
        else:
            return

        text= re.sub('\n\n\n*\n','\n\n', text)

        self.task.note = text
        session.commit()

        simple_html = markdown.markdown(text)

        # kluge to get rid of extra line after a pre block
        simple_html = simple_html.replace('\n</code></pre>', '</code></pre>')

        self.note.setHtml(simple_html)
        self.db_note.setPlainText(text)

        self.modified = {}

        print_("Note Saved")

        self.myevent.signal.emit('set_reminder', {'task':self.task, 'session':session})

    def displayitems(self):

        qtablewidgetitem = QtWidgets.QTableWidgetItem
        qcolor = QtGui.QColor
        #qicon = QtGui.QIcon

        display = self.display #dict that just holds display lambda's
            
        type_ = 'folder' if self.Properties['tab']['type'] == 'context' else 'context'

        table = self.table
        col_order = self.col_order

        itemfont = self.itemfont
        deleteditemfont = self.deleteditemfont

        idx1 = self.idx1
        idx0 = self.idx0
        
        query = self.get_current_tasks()
        rows = query.count() ########
        
        table.clearContents()

        if not self.Properties['collapsible']:
            
            table.setRowCount(rows)

            for n,task in enumerate(query):
                item = qtablewidgetitem(idx1 if not task.completed else idx0, '')
                item.setData(Qt.UserRole, int(task.id))
                table.setItem(n, 0, item)
                color = qcolor(getattr(task, type_).textcolor) if not (task.deleted or task.completed) else qcolor('gray')
                font = itemfont if not task.deleted else deleteditemfont
                
                for c,col in enumerate(col_order[1:],start=1):
                    item = qtablewidgetitem(*display[col](task))
                    item.setFont(font[task.priority])
                    item.setForeground(color)
                    table.setItem(n, c, item)

        else:
            collapsed = QtGui.QIcon('bitmaps/collapsed.png')
            expanded = QtGui.QIcon('bitmaps/expanded.png')
            table.setRowCount(rows+len(self.priorities)) ############# max needed; will reduce, see below
            n=0 # the row count
            for p,b in reversed(sorted(self.Properties['priority_display'].items())):

                item = qtablewidgetitem(expanded if b else collapsed, '')
                item.setData(Qt.UserRole, int(p))
                item.setBackground(qcolor("GREY"))
                table.setItem(n, 0, item)

                for c in range(1, len(col_order)):
                    item = qtablewidgetitem()
                    item.setBackground(qcolor("GREY"))
                    table.setItem(n, c, item)            

                p_query = query.filter(Task.priority==p)
                s = "Priority %d: %d items"%(int(p), p_query.count())
                item = qtablewidgetitem(s)
                item.setBackground(qcolor("GREY"))
                #item.setTextColor(qcolor("WHITE"))
                item.setForeground(qcolor("WHITE")) #12-19-2014
                table.setItem(n, col_order.index('title'), item)   
                n+=1

                if b:
                    for task in p_query:
                        item = qtablewidgetitem(idx1 if not task.completed else idx0, '')
                        item.setData(Qt.UserRole, int(task.id))
                        table.setItem(n, 0, item)
                        color = qcolor(getattr(task, type_).textcolor) if not (task.deleted or task.completed) else qcolor('gray')
                        font = itemfont if not task.deleted else deleteditemfont
                        
                        for c,col in enumerate(col_order[1:],start=1):
                            item = qtablewidgetitem(*display[col](task))
                            item.setFont(font[task.priority])
                            item.setForeground(color)
                            table.setItem(n, c, item)

                        n+=1
            
            table.setRowCount(n) # correct the row count
            
        return rows            

    @check_modified
    def itemselected(self):

        '''the "itemSelectionChanged() SIGNAL is only emitted if the row wasn't previously selected - it is SIGNALLED 
        *before* the cellClicked(int,int) is issued.  Note that onpagechange calls itemselected and nothing may be selected'''

        table = self.table

        ranges = table.selectedRanges()
        self.index = ranges[0].topRow() if ranges else -1  

        table.return_sc.setEnabled(True) ####### not sure I need this but may be belt & suspenders - escape key

        if self.index == -1:
            self.task = None
            self.note.clear() #triggers a note modified
            self.db_note.clear()
            print_("No selection during itemselected")
            self.modified = {}

            self.note.setEnabled(False)
            self.db_note.setEnabled(False)
            self.note_manager.format_toolbar.setEnabled(False)

            return

        #if table.item(self.index, 0): # once number of rows is same as number of tasks - don't need to check this #### May 19, 2012
        id_ = table.item(self.index,0).data(Qt.UserRole)

        if id_ < 4:
            self.task = None
            self.note.clear() #triggers a note modified 
            self.db_note.clear() #triggers a note modified even if the note doesn't change
            #self.modified = {} ### May 19, 2012

            self.note.setEnabled(False)
            self.db_note.setEnabled(False)
            self.note_manager.format_toolbar.setEnabled(False)

        else:

            self.task = task = session.query(Task).get(id_)
            note = task.note if task.note else ''

            # kluge -- needs to be fixed in markdown2
            simple_html = markdown.markdown(note)
            simple_html = simple_html.replace('\n</code></pre>', '</code></pre>')
            self.note.setHtml(simple_html)

            self.db_note.setPlainText(note)

            p_list = self.priorities[:]
            p_list.reverse()
            i = p_list.index(self.task.priority)
            self.p_menu.actions()[i].setChecked(True)

            folders = session.query(Folder).filter(Folder.tid!=0).all()
            folders.sort(key=lambda f:str.lower(f.title))            
            f_list = ['No Folder'] + [f.title for f in folders]
            i = f_list.index(self.task.folder.title)
            self.f_menu.actions()[i].setChecked(True)

            contexts = session.query(Context).filter(Context.tid!=0).all()
            contexts.sort(key=lambda c:str.lower(c.title))
            c_list = ['No Context'] + [c.title for c in contexts]
            i = c_list.index(self.task.context.title)
            self.c_menu.actions()[i].setChecked(True)

            self.new_row = True #because method is called because a new row was selected

            self.note.setEnabled(True)
            self.db_note.setEnabled(True)
            self.note_manager.format_toolbar.setEnabled(True)
            
            # highlight search terms in note if on search tab
            if self.Properties['tab']['type'] == 'search':
                self.highlightsearchterms()
            else:
                self.highlighter.setDocument(None)

            delegate = table.itemDelegateForColumn(self.col_order.index('title'))
            title_col = self.col_order.index('title')

            #note that tooltip gets created only and each time the row is selected
            #once the row is selected once tooltip will appear on hover whether row is selected or not

            if delegate.sizeHint(table.viewOptions(), table.indexFromItem(table.item(self.index, title_col))).width() > table.columnWidth(title_col):
                table.item(self.index, title_col).setToolTip("{0} ({1})".format(task.title, task.context.title)) # task.title+' ('+task.context.title+')'
            else:
                table.item(self.index, title_col).setToolTip(task.context.title)
            
            #self.a_togglestar.setChecked(task.star) # decided cute but unnecessary
     
        QtCore.QTimer.singleShot(0, lambda: self.modified.clear())

    def showcompleted(self, evt=None):

        self.Properties['show_completed'] = not self.Properties['show_completed']
        self.refresh()

    def removesort(self):
        '''
        Once you sort a table, without this method there is no way to remove the sorting criteria - 
        this is particularly important in being able to sort and remove sort from xapian searches
        ? if this still applies 12-28-2014
        '''
        sort_col = self.Properties['sort']['column']
        
        if sort_col is None:
            return
        
        col_item = self.table.horizontalHeaderItem(self.col_order.index(sort_col))
        col_item.setIcon(QtGui.QIcon())
        
        self.Properties['sort'] = {'column':None,'direction':0}
        
        self.refresh()

    @check_modified
    #@check_task_selected
    def ondockwindow(self, checked, dw=None, cur=True, check_task_selected=True): 

        if check_task_selected and (not self.task or self.index==-1):
            QtWidgets.QMessageBox.information(self,  'Note', "There was no row selected.  Please select one.") 
            return

        if not dw.isVisible():
            dw.show()

        dw.setFloating(not dw.isFloating())

        # note needed when both floating and docked to raise and activiate
        dw.activateWindow() 
        dw.raise_()  
        
        txt = dw.widget()

        if cur:
            cursor = txt.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            txt.setTextCursor(cursor)

    @check_modified
    def refresh(self, check=False): 

        if not self.PageProperties: # no tabs need this in other places
            return

        #self.table.blockSignals(True)
        num_tasks = self.displayitems()
        #self.table.blockSignals(False)

        #self.note.blockSignals(True)
        self.note.clear() # this triggers a textChanged() event
        #self.note.blockSignals(False)

        #self.db_note.blockSignals(True)
        self.db_note.clear() # this triggers a textChanged() event
        #self.db_note.blockSignals(False)

        Properties = self.Properties
        tab_value = Properties['tab']['value']
        tab_type = Properties['tab']['type']

        self.index = -1
        self.task = None

        self.modified = {} #not necessary if you block the signal

        LBox = self.LBox

        if Properties['filter_by']['column'] == 'context':
            if tab_type == 'folder':
                contexts = session.query(Context).join(Task,Folder).filter(Folder.title==tab_value)
                LB_items = ['*ALL','No Context'] + sorted([c.title for c in contexts if c.tid!=0], key=str.lower)
            else:    
                LB_items = ['*ALL','No Context'] + sorted([c.title for c in session.query(Context).filter(Context.tid!=0)], key=str.lower)

        elif Properties['filter_by']['column'] == 'folder':
            if tab_type == 'context':
                #context = session.query(Context).filter_by(title=tab_value).one()
                folders = session.query(Folder).join(Task,Context).filter(Context.title==tab_value)
                #LB_items = ['*ALL','No Folder'] + sorted([f.title for f in context.folders if f.tid!=0], key=unicode.lower)
                LB_items = ['*ALL','No Folder'] + sorted([f.title for f in folders if f.tid!=0], key=str.lower)
            else:
                LB_items = ['*ALL','No Folder'] + sorted([f.title for f in session.query(Folder).filter(Folder.tid!=0)], key=str.lower)

        elif Properties['filter_by']['column'] == 'priority':
            LB_items = ['*ALL'] + ['3','2','1','0','-1']

        elif Properties['filter_by']['column'] == 'tag':
                LB_items = ['*ALL'] + self.get_keywords(tab_type, tab_value)

        LBox.blockSignals(True)

        LBox.clear()
        LBox.addItems(LB_items)

        LBox.setCurrentRow(0)

        items = LBox.findItems(Properties['filter_by']['value'], Qt.MatchExactly)
        if items:
            LBox.setCurrentItem(items[0])

        LBox.blockSignals(False)
        
        self.tab_manager.setTabToolTip(self.tab_manager.currentIndex(), str(num_tasks)+" tasks")

    @check_modified
    def refreshlistonly(self): 

        if not self.PageProperties: # no tabs need this in other places
            return

        #self.table.blockSignals(True)
        num_tasks = self.displayitems()
        #self.table.blockSignals(False)

        self.index = -1
        self.task = None

        #self.note.blockSignals(True)
        self.note.clear() # this triggers a textChanged() event
        self.db_note.clear()
        #self.note.blockSignals(False)

        self.modified = {} #not necessary if you block the signal
        
        self.tab_manager.setTabToolTip(self.tab_manager.currentIndex(), str(num_tasks)+" tasks")

    @check_modified
    def filterlist(self, new_item, prev_item):

        self.Properties['filter_by']['value'] = new_item.text()
        self.refreshlistonly()

    def columnclick(self, col):
        
        print("section clicked")

        if not self.col_info[self.col_order[col]]['sortable']: 
            return

        table = self.table
        sort = self.Properties['sort']

        prev_sort_col = sort['column'] #.get('column') #if this is the first sort Properties['sort'] is {}

        sort['column'] = self.col_order[col]

        if prev_sort_col == sort['column']:
            sort['direction'] = not sort['direction']
        else:
            sort['direction'] = 0

        self.refresh()

        if prev_sort_col:
            col_item = table.horizontalHeaderItem(self.col_order.index(prev_sort_col))
            col_item.setIcon(QtGui.QIcon())

        col_item = table.horizontalHeaderItem(col)
        img = QtGui.QIcon(self.arrows[sort['direction']])
        col_item.setIcon(img)

    def changefilterbycolumn(self):

        filter_by = ['folder','context','priority','tag'] #modified

        dlg = lmdialogs.ChoiceDlg("Select", filter_by, multi=False, parent=self)
        filter_column = self.Properties['filter_by']['column']
        dlg.listWidget.setCurrentRow(filter_by.index(filter_column))

        if dlg.exec_():
            filter_column = dlg.choices[0]

            Properties = self.Properties
            Properties['filter_by']['column'] = filter_column
            Properties['filter_by']['value'] = '*ALL'
            if filter_column == 'priority':
                Properties['collapsible'] = False

            if Properties['window_sizes'][0]==0:
                Properties['window_sizes'][0]=75
                splitter = self.tab_manager.currentWidget()
                splitter.setSizes(Properties['window_sizes']) 

            self.refresh()

            self.setWindowTitle("List Manager AWS - type: %s; value: %s filtered by: %s"%(Properties['tab']['type'], Properties['tab']['value'],Properties['filter_by']['column']))

    def toggle_collapsible(self):
        self.Properties['collapsible'] = not self.Properties['collapsible']
        self.refreshlistonly()

    def modifycolumns(self):

        full_list = list(self.col_info.keys())
        full_list.remove('box') # completion box is not optional

        in_use_list  = self.col_order[:]
        in_use_list.remove('box')

        full_list_set = set(full_list)
        in_use_set = set(in_use_list)

        available_set = full_list_set - in_use_set

        prev_col_widths = dict(list(zip(self.col_order, self.Properties['col_widths'])))
        
        print("launched modify columns ...")

        dlg = lmdialogs.ModifyColumns(self,list(available_set),in_use_list)

        if dlg.exec_():
            print(repr(dlg.lst))
            self.col_order = ['box']+dlg.lst #adding back completed column in 0th position

            # title is the one column along with completed (in zero position) that needs to be there
            if 'title' not in self.col_order:
                self.col_order.append('title')

            # since we may have removed the column we were sorting by
            self.Properties['sort'] = {'column':None,'direction':0} 

            # set the col_order property; probably in wrong place but need to set self.col_order
            self.Properties['col_order'] = self.col_order       

            self.Properties['col_widths'] = [prev_col_widths.get(name, self.col_info[name]['width']) for name in self.col_order]

            self.replacetable()

    def display_danger_items(self):
        self.display_danger_in_all_contexts = not self.display_danger_in_all_contexts
        self.display_danger_action.setChecked(self.display_danger_in_all_contexts)
        self.refreshlistonly()
        
    def showhidefilterby(self):

        splitter = self.tab_manager.currentWidget()
        Properties = self.Properties
        
        Properties['window_sizes'][0] = 75 if Properties['window_sizes'][0]==0 else 0
        
        splitter.setSizes(Properties['window_sizes'])

    def change_tab_name(self):
        '''
        Saves tab name for regular tabs and saves searches so they will be reloaded
        '''
        
        #also used to save a search
        
        tab_idx = self.tab_manager.currentIndex()
        
        tab_title = self.tab_manager.tabText(tab_idx)
        result = QtGui.QInputDialog.getText(self,"Tag","Enter Tab Name", QtGui.QLineEdit.Normal, tab_title)

        tab_title, b = result

        if not b:
            return

        print("New tab name={0}".format(tab_title))
        
        self.tab_manager.setTabText(tab_idx, tab_title)
        
        self.Properties['title'] = tab_title
        
        if self.active_search == self.tab_manager.currentWidget():
            self.Properties['tab']['value'] = 'saved_search'  
            self.active_search = None
            self.search.clear()
        
    @check_modified
    @check_task_selected
    def ontouch(self):

        self.task.modified = datetime.datetime.now()
        session.commit()

        self.refreshlistonly()

    def highlightsearchterms(self):
        terms = self.Properties['query_string']
        self.highlighter.setDocument(self.note.document())
        term_list = [x for x in terms.split() if x.lower() not in ('and','or')] #don't want to highlight and, or
        self.highlighter.setkeywords(term_list)

    def iconcolordialog(self, type_): #'folder';'context'
        
        class_ = {'folder':Folder, 'context':Context}
        things = session.query(class_[type_]).all()
        
        dlg = lmdialogs.TextColor("Select", things, parent=self, type_=type_)

        if dlg.exec_(): #True if user clicks on a row and false if they click cancel/done or window close box
        
            title = dlg.title
            column = dlg.column
            
            thing = session.query(class_[type_]).filter_by(title=title).first()
            
            qcolor = QtGui.QColor(thing.textcolor)
            
            if column=='icon':

                #pngs = os.listdir(os.path.join(g.IMAGES_DIR,'{}_icons'.format(type_)))
                pngs = os.listdir(os.path.join(g.IMAGES_DIR,'folder_icons'))
                
                
                dlg = lmdialogs.SelectIcon("Select an icon for {} {}".format(type_, title), things, pngs, parent=self, initial_selection=None, type_=type_)
                if dlg.exec_(): # if cancel - dlg.exec_ is False
                    print_("icon choice={}".format(dlg.icon_choice))
                    
                    if dlg.icon_choice == 'No Icon':
                        thing.icon = None
                        thing.image = None
                    else:
                        thing.icon = dlg.icon_choice
                        
                        image = QtGui.QImage("bitmaps/folder_icons/{}".format(dlg.icon_choice))
                        if image.isNull():
                            print_("Image is Null")
                        else:
                            ba = QtCore.QByteArray()
                            buf = QtCore.QBuffer(ba)
                            buf.open(QtCore.QIODevice.ReadWrite)
                            zz = image.save(buf, 'PNG')
                            if zz:
                                thing.image = ba.data()
                            else:
                                print_("Could not save image to buffer")
                    
                    session.commit()

                    #update the menus that include icons and the display dictionaries (self.folder_icons and self.context_icons)
                    #### Note that you don't need else because thing.image==None creates a Null icon but just seems better to have no icon at all
                    if thing.image:
                        pxmap = QtGui.QPixmap()
                        pxmap.loadFromData(thing.image, 'PNG')
                        icon = (QtGui.QIcon(pxmap), '')
                    else:
                        icon = ('',)  
                    
                    if type_=='folder':
                        self.folder_icons[thing.title] = icon
                        self.createfoldermenu() #need creaticon(folder)menu and context menu
                        self.a_selectfolder.setMenu(self.f_menu)
                    else:
                        self.context_icons[thing.title] = icon
                        self.createcontextmenu() #need creaticon(folder)menu and context menu
                        self.a_selectcontext.setMenu(self.c_menu)

            else:
            
                print_("column={}".format(column))
                print_("rgb_color={}".format(qcolor.getRgb()))
                
                newqcolor = QtGui.QColorDialog.getColor(qcolor, self, "Choose a color for {} text".format(title))
                if newqcolor.isValid():
                    print_("new color = {}".format(repr(newqcolor)))
                    
                    c = newqcolor.rgb() 
                    print_("Rgb int = {}".format(c))
                    c &= 0xffffffff #needs to be an unsigned long (may not be necessary but Web postings suggested it might be)
                    print_("Rgb int made long = {}".format(c))
                    thing.textcolor = c  
                    session.commit() 
                                
            self.iconcolordialog(type_)
            
    def fullsize(self, tablewidth):

        #splitter = self.tab_manager.currentWidget() # will be the new splitter on tab change
        table = self.table # for some reason is the 'old" table (the one prior to the click on the tab changing the tab)
        
        # Appears that when you click on a tab the old table is still active and the old table's title may be changed incorrectly
        # However, the new splitter is present so there should be a way to detect splitter/table mismatch
        # Instead went with QTimer in resizeEvent and that worked
        #if splitter.widget(1) != table: return
      
        z = sum(table.columnWidth(n) for n in range(table.columnCount()))
        c = self.col_order.index('title')
        w = self.Properties['col_widths'][c]

        w += tablewidth - z 
        table.setColumnWidth(c, w)
        
        # don't need to do following because resizing title column triggers method updatecolumnwidths
        #self.Properties['col_widths'][c] = w 
        
    @check_modified
    def synchronize(self, checked, local=True):
        

        if not g.internet_accessible():
            QtWidgets.QMessageBox.warning(self,  'Alert', "Internet not accessible right now.")
            return
            
        if not toodledo2.keycheck():
            print_("Unable to get toodledo key")
            return
        
        self.sync_log, changes, tasklist, deletelist = synchronize2.synchronize(parent=self, 
                                                                                showlogdialog=True, 
                                                                                OkCancel=True,
                                                                                local=local)
        print("changes={0}".format(changes))
        print("tasklist={0}".format([t.title for t in tasklist])) #this is a goofy print
        print("deletelist={0}".format(deletelist))
        
        if 'contexts' in changes:
            self.createcontextmenu()
            
        if 'folders' in changes:
            self.createfoldermenu()
            
        for task in tasklist:
            self.updatewhooshentry(False, task=task) #False -> checked is because of QAction
            
        for id_ in deletelist: #these ids are local client task.ids and that is what whoosh uses
            self.deletefromwhooshdb(id_)

        reply = QtWidgets.QMessageBox.question(self,
                                          "Confirmation",
                                          "Do you want to synchronize with the remote AWS db?",
                                          QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.No:
            print("You said no to synching with the remote AWS db")
            return

        try:
            r = requests.get("http://54.173.234.69:5000/sync") #probably should add http auth  auth=(c.aws_id, c.aws_pw))
        except:
            QtWidgets.QMessageBox.warning(self,  'Alert', "Could not sync remote AWS db!")
            return

        n = 1
        while n < 6:
            try:
                r = requests.get("http://54.173.234.69:5000/sync-log")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self,  'Alert', "Could not retrieve AWS db sync log!")
                break
            else:
                log = r.text
                if len(log) > 100:
                    dlg = lmdialogs.SynchResults("Synchronization Results", log, parent=self)
                    dlg.exec_()
                    break 
                n+=1
                sleep(1)

        print("Number of attemps: {}".format(n))
                
    def showsync_log(self):
        dlg = lmdialogs.SynchResults("Synchronization Results", self.sync_log, parent=self)
        dlg.exec_()
        
    def create_whooshdb(self):
        tasks = session.query(Task)
        r = tasks.count()
        self.pb.setRange(0, r)
        self.pb.setValue(0)
        self.pb.show()
        
        #If unique=True on a field then value of this field may be used to replace documents with the same value when the user calls document_update() on an IndexWriter. 
        #the below works - I used that schema and then search on Prefix
        #schema = Schema(title=TEXT, tag=KEYWORD, note=TEXT, task_id=NUMERIC(numtype=int, bits=64, unique=True, stored=True)) #probably better to do signed=False 

        #Below is my take on how you use a custom Tokenizer including Ngram that only looks at the start of words
        #phrase = False means we're not indexing across words which doesn't make sense when doing real-time incremental searching
        my_analyzer =analysis.RegexTokenizer() | analysis.LowercaseFilter() | analysis.StopFilter() | analysis.NgramFilter(3,7,at='start')
        #schema = Schema(title=TEXT(my_analyzer, phrase=False), note=TEXT(my_analyzer, phrase=False), task_id=NUMERIC(numtype=int, bits=64, unique=True, stored=True))
        schema = Schema(title=TEXT(my_analyzer, phrase=False), tag=KEYWORD(commas=True, lowercase=True, scorable=True), note=TEXT(my_analyzer, phrase=False), task_id=NUMERIC(numtype=int, bits=64, unique=True, stored=True))
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        
        # Calling index.create_in on a directory with an existing index will clear the current contents of the index.
        ix = create_in("indexdir", schema)
        writer = ix.writer()

        for n,task in enumerate(tasks):

            writer.add_document(title = task.title,
                                tag = task.tag, 
                                note = task.note, 
                                task_id = task.id) #str(task.id) if using ID(unique=True, stored=True)) 
                                           
            self.pb.setValue(n)
             
        writer.commit()
        
        print_("Whoosh database indexing complete")
        
        self.pb.hide()

    def create_whooshdb2(self):
        tasks = session.query(Task)
        r = tasks.count()
        self.pb.setRange(0, r)
        self.pb.setValue(0)
        self.pb.show()
        
        my_analyzer =analysis.RegexTokenizer() | analysis.LowercaseFilter() | analysis.StopFilter() | analysis.NgramFilter(3,7,at='start')
        schema = Schema(content=TEXT(my_analyzer, phrase=False), task_id=NUMERIC(numtype=int, bits=64, unique=True, stored=True))
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        
        # Calling index.create_in on a directory with an existing index will clear the current contents of the index.
        ix = create_in("indexdir", schema)
        writer = ix.writer()

        for n,task in enumerate(tasks):

            note = task.note if task.note else '' 
            text = ' '.join(k.name for k in task.keywords) + ' ' + task.title + ' ' + note

            writer.add_document(content = text, 
                                task_id = task.id) #str(task.id) if using ID(unique=True, stored=True)) 
                                           
            self.pb.setValue(n)
             
        writer.commit()
        
        print_("Whoosh database indexing complete")
        
        self.pb.hide()

    def file_changed_in_vim(self, path):
        print('File Changed: %s' % path)
        task_id = self.vim_files[path]
        f = open(path, mode='r')
        text = f.read()
        self.task.note = text
        session.commit()
       # kluge to get rid of extra line after a pre block
        simple_html = markdown.markdown(text)
        simple_html = simple_html.replace('\n</code></pre>', '</code></pre>')

        self.note.setHtml(simple_html)
        self.db_note.setPlainText(text)

        print(self.modified) #the writes to self.note and self.db_note produce self.modified={'plain_note':True,'note':True}
        self.modified = {}
        task = session.query(Task).get(task_id)
        
        print_("Note Saved from Vim was note id: {} title: {}".format(task_id,task.title))

    def edit_note_in_vim(self):
        note = self.task.note if self.task.note else ''
        temp = tempfile.NamedTemporaryFile(mode='w', prefix='lm', suffix='.tmp', delete=False)
        temp.write(note)
        temp.flush()
        temp.close()
        self.vim_files[temp.name] = self.task.id
        print(repr(self.vim_files))
        Popen([g.VIM, "+set nonu", "+set lines=40", "+set columns=100", os.path.abspath(temp.name)])
        self.fs_watcher.addPath(os.path.abspath(temp.name))
        
    def print_note_to_log(self):
        print_(self.note.toHtml())

    def get_tabinfo(self): #check
        
        #print_("check={}".format(check))
        
        class_ = {'folder':Folder, 'context':Context, 'tag':Keyword}

        Properties = self.Properties
        
        type_ = Properties['tab']['type']
        
        print("type_={0}".format(type_))
        
        if not (type_ == 'context' or type_ == 'folder' ):
            return

        title =  Properties['tab']['value']

        query = session.query(Task).join(class_[type_]).filter(class_[type_].title==title)

        count = query.count()
        msg = "Total number of tasks in %s: %d\n"%(title,count)

        active = query.filter(and_(Task.completed==None, Task.deleted==False)).count()
        msg = msg + "Total number of active tasks in %s: %d\n"%(title,active)

        complete = query.filter(~(or_(Task.completed==None, Task.deleted==True))).count() #not_ also works
        msg = msg + "Total number of completed tasks in %s: %d\n"%(title,complete) 

        deleted = query.filter(Task.deleted==True).count() #not_ also works
        msg = msg + "Total number of deleted tasks in %s: %d\n"%(title,deleted) 

        msg = msg + "\nOf active tasks...\n"
        count = query.filter(and_(Task.completed==None, Task.star==True, Task.deleted==False)).count()
        msg = msg + "Starred tasks: %d\n"%count
        for p in reversed(self.priorities):
            count = query.filter(and_(Task.completed==None, Task.priority==p, Task.deleted==False)).count()
            msg = msg + "Priority %d tasks: %d\n"%(p, count)

        task = query.filter(and_(Task.completed==None, Task.deleted==False)).order_by(Task.created).first()
        if task:
            msg = msg + "\nOldest active record:\n%s\ncreated on: %s\n"%(task.title, task.created.strftime("%m/%d/%y")) 
        if task:
            task = query.filter(and_(Task.completed==None, Task.deleted==False)).order_by(Task.modified).first()
            msg = msg + "\nActive record with oldest modification:\n%s\nlast modified: %s\n"%(task.title, task.modified.strftime("%m/%d/%y %H:%M:%S"))

        dlg = lmdialogs.SynchResults("Synchronization Results", msg, parent=self, OkCancel=True)
        
        dlg.exec_()

    @check_task_selected
    def whooshtaskinfo(self, check=False):
        id_ = self.task.id
        docnum = self.searcher.document_number(task_id=id_)
        stored_fields = self.searcher.stored_fields(docnum)
        print("stored fields (task.id)={} and whoosh docnum={}".format(stored_fields, docnum))
        #keywords_and_scores = self.searcher.key_terms([docnum], 'title') #need to be vectored, which I don't really get
        #print("key *title* terms=", keywords_and_scores)
        text, ok = QtWidgets.QInputDialog.getText(self,"Whoosh","Enter search terms for task.id {}; Whoosh docnum {}".format(id_, docnum)) 
        
        if ok and text:
            print_(text)
            results = self.get_query_ids(text)
            
            try:
                pos = results.index(id_)
            except ValueError:
                print_("Not in list")
            else:
                print_("position: {}".format(pos))
            
    def showdeleted(self):

            self.createnewtab(title='*Deleted*', tab={'type':'deleted_items', 'value':None}, filter_by={'column':'context','value':'*ALL'}, collapsible=False)

    def recreatekeywordsfromtag(self):
        '''May be possible to have unused keywords and unused taskkeywords (e.g., deleted task)
           and this wipes the slate clean and lets you recreate kewyord_table and taskkeyword_table'''
           
        if self.confirm("Do you really want to recreate keywords from tags?"):
            
            keyword_table.drop()   
            taskkeyword_table.drop()
        
            keyword_table.create()   
            taskkeyword_table.create()
        
            tasks = session.query(Task).filter(Task.tag != None).all()
            
            pb = self.pb
            
            pb.setRange(0, len(tasks))
            pb.setValue(0)
            pb.show()
        
            for n,task in enumerate(tasks):
                for kwn in task.tag.split(','):
                    # We could do kwn.strip and then write them back to tab
                    # but new logic should do this when the tag is entered
                    keyword = session.query(Keyword).filter_by(name=kwn).first()
                    if keyword is None:
                        keyword = Keyword(kwn)
                        session.add(keyword)
                        session.commit()
                    taskkeyword = TaskKeyword(task, keyword)
                    session.add(taskkeyword)
                    
                pb.setValue(n)
                    
            session.commit()
            
            pb.hide()
                
    def removedeadkeywords(self):
        '''May be possible to have unused keywords and unused taskkeywords (e.g., deleted task)
           and this wipes the slate clean and lets you recreate kewyord_table and taskkeyword_table'''
           
        keywords = session.query(Keyword).all()
                
        keyword_list = sorted([kw.name for kw in keywords if not kw.taskkeywords], key=str.lower)
        
        text = "Do you want to eliminate these orphan keywords?"
        
        dlg = lmdialogs.ChoiceDlg("Orphan Keywords", keyword_list, label_text=text, parent=self)
        if dlg.exec_():
            for kw in keywords:
                if not kw.taskkeywords:
                    print(kw.name)
                    session.delete(kw)
            session.commit()

    @check_task_selected
    @check_modified
    def ontaskinfo(self, check, retrieve_server=False): #appear to have to add check to all of them because triggered is returning check 12-21-2014

        print_("check={}".format(check))

        task = self.task

        f = lambda x: x if x is not None else ''

        c_map = {'sqlite_id':'id', 'context_id':'context_tid', 'folder_id':'folder_tid'} #dialog label:actual label
        s_map = {'tid':'id', 'folder_id':'folder', 'context_id':'context'}

        labels = ('sqlite_id', 'tid', 'star', 'priority', 'title', 'context','context_id', 'folder','folder_id', 'tag', 'added', 'modified', 'duedate', 'duetime','startdate','completed','note')

        c_task = dict(task.__dict__)
        c_task = {lab:f(c_task[c_map.get(lab,lab)]) for lab in labels} 
        c_task.update(context=c_task['context'].title, folder=c_task['folder'].title)

        if task.tid and retrieve_server: # if it's a new task that hasn't gotten a tid from server yet, there won't be a server task to retrieve
            
            if not toodledo2.keycheck():
                print_("Could not retrieve server info because could not get key")
                return

            toodledo_call = toodledo2.toodledo_call
              
            s_folders = toodledo_call('folders/get') #[{"id":"123","name":"Shopping","private":"0","archived":"0","ord":"1"},...
            s_folders_map =  {z['id']:z['name'] for z in s_folders}   

            s_contexts = toodledo_call('contexts/get') # [{"id":"123","name":"Work"},{"id":"456","name":"Home"},{"id":"789","name":"Car"}]
            s_contexts_map =  {z['id']:z['name'] for z in s_contexts}   

            stats, s_task = toodledo_call('tasks/get', id_=task.tid, fields='folder,star,priority,duedate,duetime,startdate,context,tag,added,note') #{"num":"2","total":"2"}, [{"id":"1234","title":"Buy Milk","modified":1281990824,"completed":0,"folder":"5409195","star":"1","priority":"-1"},{"id":"1235","title":"Fix flat tire","modified":1280877483,"completed":1280808000,"folder":"0","star":"0","priority":"0"}]

            if s_task:
                s_task = s_task[0]
                s_task['sqlite_id'] = ''
                s_task = {lab:f(s_task[s_map.get(lab,lab)]) for lab in labels}
                s_task['folder'] = s_folders_map.get(s_task['folder_id']  , 'No Folder')
                s_task['context'] = s_contexts_map.get(s_task['context_id']  , 'No Context')
        else:
            s_task = {}

        dlg = lmdialogs.TaskInfo("Compare", data = [c_task, s_task], labels=labels, parent=self)

        dlg.exec_()

    def on_simple_html2log(self):
        print(markdown.markdown(self.task.note))

    def resetinterp(self):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, Qt.black)
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(0, 255, 0)) # lime green
        self.console.setPalette(palette)

    def renew_alarms(self):
        
        now = datetime.datetime.now()
        tasks = session.query(Task).filter(and_(Task.remind != None, Task.duetime<now))
        
        interval = 30
        
        for n,t in enumerate(tasks[:10]):
            t.duetime = t.duedate = now + datetime.timedelta(minutes=n*interval)
            print_('"{0}" now has an alarm set for {1}'.format(t.title[:40],t.duetime))
            
        session.commit()

        
    def create_image_string(self):
        
        file_ = QtGui.QFileDialog().getOpenFileName(self, "Select PNG File", g.IMAGES_DIR, "PNG (*.png)")
        print(file_)
        
        image = QtGui.QImage(file_)
        if image.isNull():
            print_("Image is Null")
        else:
            ba = QtCore.QByteArray()
            buf = QtCore.QBuffer(ba)
            buf.open(QtCore.QIODevice.ReadWrite)
            zz = image.save(buf, 'PNG')
            if zz:
                self.zz = ba.data()
                print_(repr(ba.data()))
                f = file('test12345','w')
                f.write(repr(ba.data())) #works
                f.close()
            else:
                print_("Could not save image to buffer")
                    
        return
        
        #######################################
                    
        pngs = os.listdir(os.path.join(g.IMAGES_DIR,'folder_icons'))
        dlg = lmdialogs.SelectIcon("Select an icon to create a string image", parent=self, pngs=pngs)
        if dlg.exec_(): # if cancel - dlg.exec_ is False
            print_("icon choice={}".format(dlg.icon_choice))
            
            if dlg.icon_choice == 'No Icon':
                print_("Chose no icon")
                return
                
            image = QtGui.QImage("bitmaps/folder_icons/{}".format(dlg.icon_choice))
            if image.isNull():
                print_("Image is Null")
            else:
                ba = QtCore.QByteArray()
                buf = QtCore.QBuffer(ba)
                buf.open(QtCore.QIODevice.ReadWrite)
                zz = image.save(buf, 'PNG')
                if zz:
                    self.zz = ba.data()
                    print_(repr(ba.data()))
                    f = file('test12345','w')
                    f.write(repr(ba.data())) #works
                    f.close()
                else:
                    print_("Could not save image to buffer")
                    
    def clearsavedtabs(self):
        self.savedtabs = []
        self.m_savedtabsmenu.clear()
        QtGui.QMessageBox.information(self,  'Information', "Saved tabs were cleared")
        
    def searchcontext(self, search=None):

        if search == 'context':
            print('search context')
            titles = sorted([c.title for c in session.query(Context).filter(Context.tid!=0)], key=str.lower)
            titles = ['No Context'] + titles
            dlg = lmdialogs.ChoiceDlg("Select", titles, parent=self)
            if dlg.exec_():
                print("dlg.choices={0}".format(dlg.choices))
                if dlg.choices:
                    self.search_contexts = dlg.choices
                else:
                    self.a_search_all.setChecked(True)
                    self.search_contexts = None
            else:
                self.a_search_all.setChecked(True)
                self.search_contexts = None
            
                    
                # note if choices is [] need to check all - too lazy to address now
            
        else:
            self.search_contexts = None
            print('all')

    def do_search(self, text=None):
        
        print("do search")

        query_string = self.search.text().lower()

        if not query_string and self.active_search is None: 
            return

        # You can backspace to no characters on incremental or return with no characters in standard
        if not query_string:
            self.table.clearContents() 
            return
        
        if len(query_string) < 3:
            return
        
        if self.active_search:
            self.tab_manager.setCurrentWidget(self.active_search)
            self.Properties['query_string'] = query_string
            self.Properties['search_contexts'] = self.search_contexts
            self.refreshlistonly()
        else:
            tab_title = '*SEARCH'
            
            if self.search_contexts:
                tab_title = tab_title + ' ' + ','.join(self.search_contexts)
                
            self.createnewtab(
                                       title=tab_title,
                                       tab={'type':'search', 'value':'active_search'},
                                       filter_by={'column':'context','value':'*ALL'},
                                       collapsible=False,
                                       col_order = ['box','startdate','star','title','context','tag'],
                                       search_contexts=self.search_contexts,
                                       query_string=query_string)

            self.active_search = self.tab_manager.currentWidget()

    def get_query_ids(self, query_string):
        '''
        Now based on Whoosh 
        '''
        #Not sure whether this should be an n-gram search or a Prefix search - below uses n-gram except for tag
        #query = Or([Term('title', query_string), Term('note', query_string), Prefix('tag', query_string)])
        
        #the below works and uses Prefix to search on beginning of work v. n-gram
        #query = Or([Prefix('title', query_string), Prefix('note', query_string)]) #needs tags
       
        #print(repr(query))
        #results = self.searcher.search(query, limit=50)
        results = self.searcher.search(Term('content', query_string), limit=50)
        
        return [r['task_id'] for r in results] 

    def get_current_tasks(self, priority=None): 
        '''returns a query unless its a Find - need to think about that'''

        Properties = self.Properties
        sort = Properties['sort']     # the sort property is:{'column':c_name or None,'direction':0}
        tab_type = Properties['tab']['type']
        tab_value = Properties['tab']['value']
        show_completed = Properties['show_completed']
        filter_by = Properties['filter_by']

        session.expunge_all() # not sure this is necessary but trying to create a clean slate on which to retrieve tasks

        tasks = session.query(Task) # there is a tab_type = '*ALL' that this covers

        #tab_type
        if tab_type == 'context':
            tasks = tasks.join(Context).filter(Context.title==tab_value)

        elif tab_type == 'search':
            
            query_ids = self.get_query_ids(Properties['query_string']) # tab_value contains the search terms
            #print_("query_ids = {0}".format(query_ids))
            
            if not query_ids:
                # using query.count later so do query below as opposed to returning []
                return tasks.filter_by(id=0) #producing an empty result set query
            else:
                if Properties['search_contexts']:
                    conditions = [Context.title == term for term in Properties['search_contexts']]
                    tasks = tasks.join(Context).filter(or_(*conditions))
                
                if sort['column']:
                    # no need to sort because they will be sorted in the sort section and ? you can't sort twice anyway
                    tasks = tasks.filter(Task.id.in_(query_ids))
                else:
                     tasks = tasks.filter(Task.id.in_(query_ids)).order_by(case([(Task.id == value, literal(index)) for index, value in enumerate(query_ids)]))    
        
        elif tab_type == 'folder':
            tasks = tasks.join(Folder).filter(Folder.title==tab_value)

        elif tab_type == 'tag': 
            tasks = tasks.join(TaskKeyword, Keyword).filter(and_(Task.id==TaskKeyword.task_id,TaskKeyword.keyword_id==Keyword.id, Keyword.name==tab_value))

        elif tab_type == 'recent':

            if tab_value == 'ALL':
                tasks = tasks.filter(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)))
            elif tab_value == 'Created':
                tasks = tasks.filter(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
            elif tab_value == 'Completed':
                tasks = tasks.filter(Task.completed > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
            elif tab_value == 'Modified':
                tasks = tasks.filter(and_(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)), ~(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())))

        elif tab_type == 'deleted_items':
            tasks = tasks.filter(Task.deleted==True)
             
        elif tab_type == 'app':
            if tab_value == 'star':
                tasks = session.query(Task).filter(Task.star==True)
            
            elif tab_value == 'alarm':
                #tasks = session.query(Task).filter(~or_(Task.remind == None, Task.remind ==0))  # note server thinks it's zero but I have lots of None should decide
                tasks = session.query(Task).filter(and_(or_(Task.remind != None, Task.remind != 0), Task.duedate > datetime.datetime.now()))
                
            else:
               print("We have a problem because that is a tab value of tab type app  that I don't recognize; tab_value =",tab_value)
            
        elif tab_type == 'folders' or tab_type == 'contexts':
            class_ = {'folders':Folder, 'contexts':Context}
            conditions = []
            for term in tab_value.split(','):
                 #conditions.append(Folder.title == term) ###############
                 conditions.append(getattr(class_[tab_type], 'title') == term)
                 
            condition = or_(*conditions)
            #print(condition)
            tasks = tasks.join(class_[tab_type]).filter(condition)

        else:
            print("We have a problem because that is a tab type that I don't recognize; tab_type =",tab_type)

        #don't show deleted tasks
        #tasks = tasks.filter(Task.deleted==False)

        #filter_by
        if filter_by['column'] == 'folder':
             if filter_by['value']  != '*ALL':
                tasks = tasks.outerjoin(Folder).filter(Folder.title==filter_by['value']) #need outer join for sorting
                folder_join = True
        elif filter_by['column'] == 'context':
            if filter_by['value']  != '*ALL':
                tasks = tasks.join(Context).filter(and_(Context.title==filter_by['value'], Task.deleted==False))
        elif filter_by['column'] == 'tag':
            if filter_by['value'] != '*ALL':
                keyword = session.query(Keyword).filter_by(name=filter_by['value']).one()
                tasks = tasks.join(TaskKeyword).filter(and_(Task.id==TaskKeyword.task_id,TaskKeyword.keyword_id==keyword.id))

        #priorities
        if priority is not None: #priority can be zero
            tasks = tasks.filter(Task.priority==priority)

        if Properties['filter_by']['column'] == 'priority' and not Properties['filter_by']['value']=='*ALL':
            tasks = tasks.filter(Task.priority==int(Properties['filter_by']['value']))

        #show_completed 
        if not show_completed:
            tasks = tasks.filter(Task.completed==None)

        #sort
        if sort['column']:
            direction = asc if sort['direction'] else desc #asc and desc must be sqlalchemy constants
            if sort['column'] == 'folder':
                tasks = tasks.outerjoin(Folder).order_by(direction(Folder.title)) 
            elif sort['column'] == 'context':
                tasks = tasks.join(Context).order_by(direction(Context.title)) 
            else:
                sort_column = getattr(Task, sort['column'])
                tasks = tasks.order_by(direction(sort_column))
        else:
            tasks = tasks.order_by(desc(Task.modified))

        return tasks

    def get_keywords(self, tab_type, tab_value):

       # I believe the context and folder queries only pick up keywords where there is an associated task
       # orphan keywords are not picked up by the queries.
        
        if tab_type == 'context':
            keywords = session.query(Keyword).join(TaskKeyword,Task,Context).filter(Context.title==tab_value).all()
        elif tab_type == 'folder':
            keywords = session.query(Keyword).join(TaskKeyword,Task,Folder).filter(Folder.title==tab_value).all()
        else:
            keywords = session.query(Keyword).all()

        keywords.sort(key=lambda x:str.lower(x.name))
        keyword_names = [keyword.name for keyword in keywords]

        return keyword_names

    def updatewhooshentry(self, checked, task=None):
        
        if task is None:
            task = self.task
        
        writer = self.ix.writer()
#        writer.update_document(task_id=task.id,
#                               title=task.title,
#                               tag=task.tag,
#                               note=task.note)
#
        note = task.note if task.note else '' 
        text = ' '.join(k.name for k in task.keywords) + ' ' + task.title + ' ' + note

        writer.add_document(content = text, 
                            task_id = task.id) #str(task.id) if using ID(unique=True, stored=True)) 
        writer.commit()
        
        #Note While the writer is open and during the commit, the index is still available for reading. 
        #Existing readers are unaffected and new readers can open the current index normally. 
        #Once the commit is finished, existing readers continue to see the previous version of the index 
        #(that is, they do not automatically see the newly committed changes). New readers will see the updated index.
        
        self.ix = index.open_dir("indexdir")
        self.searcher = self.ix.searcher()
        
     
        print_("Updated in Whoosh DB: task id: {0}, {1} ...".format(task.id, task.title[:40]))
        
    def deletefromwhooshdb(self, id_):

        writer = self.ix.writer()
        try:
            #note documentation (in at least one place: How to index documents) has a mistake that says you can delete
            #by doing ix.delete_by_term;ix.commit() but the right way is below: 
            writer.delete_by_term('task_id', id_) 
            writer.commit()
        except Exception as e:
            print("Problem deleting term from whoosh--",e)
            print("Task {0}:  -- was not in Whoosh DB".format(id_))

    def confirm(self, text):
        reply = QtWidgets.QMessageBox.question(self, "Confirmation", text, QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
        return reply==QtWidgets.QMessageBox.Yes

    def showversions(self):

        import sqlalchemy

        python_version = sys.version.split()[0]
        sqla_version = sqlalchemy.__version__ 

        whoosh_version = index.version(FileStorage("indexdir"))[0]
        whoosh_version = '.'.join(str(x) for x in list(whoosh_version))
        
        values = (python_version, QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR, sip.SIP_VERSION_STR, sqla_version, whoosh_version)
        text = "python:\t{}\npyqt:\t{}\nqt:\t{}\nsip:\t{}\nsqla:\t{}\nwhoosh:\t{}".format(*values)
        
        dlg = lmdialogs.VersionsDlg('Versions', text, self)
        dlg.exec_()

class Table(QtWidgets.QTableWidget):
    def __init__(self, parent, col_info=None, col_order=None, col_widths=None): #added parent
        #QTableWidget.__init__(self) 
        super(Table, self).__init__(parent)
        
        self.parent = parent
        
        self.setHorizontalHeader(Header(self))
        
        self.hheader = self.horizontalHeader()

        self.column_info = col_info
        self.column_order = col_order
        self.column_widths = col_widths
        self.setMinimumSize(600,300)
        
        #self.setStyleSheet("QTableWidget { } QTableWidget::item { padding-bottom 5px; padding-bottom 5px; border-bottom: 5px solid #000; }") # does something but not what you want

        self.setup()

    def setup(self):

        col_order = self.column_order
        col_info = self.column_info

        self.setColumnCount(len(col_order))

        if self.column_widths:
            for c,w in enumerate(self.column_widths):
                self.setColumnWidth(c, w)
                if col_info[col_order[c]]['fixed']:
                    self.hheader.setSectionResizeMode(c, QtWidgets.QHeaderView.Fixed) # testing

        else:
            for c,c_name in enumerate(col_order):
                self.setColumnWidth(c, col_info[c_name]['width'])
                if col_info[c_name]['fixed']:
                    self.hheader.setSectionResizeMode(c, QtWidgets.QHeaderView.Fixed) # testing

        self.setHorizontalHeaderLabels([col_info[c_name]['label'] for c_name in col_order])

        self.verticalHeader().setDefaultSectionSize(18) #somewhat cryptic way to set row sizes
        self.verticalHeader().setVisible(False)

        #In Header Class
        #self.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft) # set column header text alignment - doesn't affect cells
        #self.horizontalHeader().setMovable(True)

        self.setShowGrid(False)

        self.setAlternatingRowColors(True)
        self.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        
        action = QtWidgets.QAction("Remove Column", self)
        action.triggered.connect(self.removecolumn)
        self.hheader.addAction(action)
        self.hheader.setContextMenuPolicy(Qt.ActionsContextMenu)
        
    def contextMenuEvent_(self, event):
        # this worked but there was a simpler way
        self.obj.tableContextMenuEvent(event)

    def mousePressEvent(self, e):
              
        self.leftpressed = e.button() == Qt.LeftButton
        
        super(Table, self).mousePressEvent(e)

    def edit__(self, index, trigger, event):
        '''this isn't doing anything but for testing'''

        if QtGui.QTableWidget.edit(self, index, trigger, event):
            print('editing:', index.row(), index.column())
            #self.editor_open = True
            print("shortcut inactive")
            return True
        else:
            self.editor_open = False
            print("shortcut active")
            return False
            
    def removecolumn(self):
        print("Remove column")
        print("column={0}".format(self.hheader.selectedcolumn))
        self.parent.removecolumn(self.hheader.selectedcolumn)

    def resizeEvent(self, event):
        w = event.size().width() # note this width takes into account presence or absence of scrollbar
        
        #print_("In table's resize event: {}".format(w))
        
        # Appears that at least on Windows when you click on a tab to change tabs the 'old' table from the previoius tab is still active 
        # and therefore the old table's title width may be changed (incorrectly)
        # However, the new splitter is present so it also worked to check for new splitter old table but QTimer worked
        
        QtCore.QTimer.singleShot(0, lambda: self.parent.fullsize(w))
        
class Header(QtWidgets.QHeaderView):
    def __init__(self, parent):    
        super(Header, self).__init__(Qt.Horizontal, parent)
        
        self.setSectionsClickable(True)
        self.setSectionsMovable(True)
        self.setDefaultAlignment(Qt.AlignLeft) # set column header text alignment - doesn't affect cells
        
        #self.leftpressed = False # not sure this is necessary but might as well define it
        #self.rightpressed = False # not sure this is necessary but might as well define it
        
    def mousePressEvent(self, e):
        
        if e.button() == Qt.RightButton:
            self.selectedcolumn = self.logicalIndexAt(e.pos())
        
        super(Header, self).mousePressEvent(e)
        
class TitleDelegate(QtWidgets.QItemDelegate):
    '''
    self.view.setItemDelegate(ViewDelegate(self))
    where self.view is the QTableView and self is the parent (a QMainWindow class).
    Note that the delegate has been implemented both to learn about delegates
    and to allow the return key to be used to trigger editing and also to
    close the editor.  As simple as that sounds, it seemed necessary to implement
    the delegate to do that.
    '''
    def __init__(self, parent=None):
        super(TitleDelegate, self).__init__(parent)
        self.parent = parent

    def createEditor(self, parent, option, index):

        print("in createEditor")
        
        editor = QtWidgets.QLineEdit(parent)
        #editor = QItemDelegate.createEditor(self, parent, option, index) # this creates the default editor for the cell and should work (untested)
        
        #somehow the editingFinished signal seems to trigger a bunch of things without explicitly connecting it to anything
        #self.connect(editor, QtCore.SIGNAL("editingFinished()"), self.commitAndCloseEditor) 
        
        return editor

    def commitAndCloseEditor(self):
        '''not in use'''
        
        editor = self.sender()
        print("In commitAndCloseEditor")

        #self.editor_active = False

        # right now this is method is not being called


        # this signal is emitted for saving the data into the model; seems to be emitted automatically by the editor
        # not sure why it isn't necessary to emit this signal
        # I wonder if this will save automatically but don't think so
        self.emit(QtCore.SIGNAL("commitData(QWidget*)"), editor) #editor emits this signal without need to do it explicitly

        # this signal is emitted to close the editor widget
        self.emit(QtCore.SIGNAL("closeEditor(QWidget*)"), editor) 


    def setEditorData(self, editor, index):
        '''Note that also using this method to deselect the text in the title since I think that is what I prefer'''

        print("In setEditorData")

        text = index.model().data(index, Qt.DisplayRole)
        editor.setText(text)
        
        if text != '<New Item>':
            # I don't want the text all selected (the default) because then it's easy to wipe it out
            QtCore.QTimer.singleShot(0, editor.deselect) # needed to delay this call and this works

    def setModelData(self, editor, model, index):

        # note that setEditorData is called after this method - not sure why
        # although presumably calling model.setData creates some signal

        print("In setModelData")

        # this is necessary to get the table to update and then save_title can access it
        model.setData(index, editor.text())

class NoteManager(QtWidgets.QMainWindow):
    '''
      Needs to be a QMainWindow so it can get a toolbar
      used in one of the dockwidgets
      '''
    def __init__(self, main_window=None, parent=None):
        super(NoteManager, self).__init__(parent)
        self.main_window = main_window
        self.note = notetextedit.NoteTextEdit()
        self.note.setObjectName('note')

        self.setCentralWidget(self.note)

        #self.highlighter = notetextedit.MyHighlighter(self.note) #put it in NoteTextEdit

        action = partial(g.create_action, self)

        self.setStyleSheet("QTextEdit { background-color: #FFFFCC;}") # I think you can only set the background of a QAbstractScrollArea-derived object

        stylesheet = '''
        h1 {color:red;}
        h2 {color:green;}
        li {margin-bottom:10px;}
        code {color:blue;}
        '''

        self.note.document().setDefaultStyleSheet(stylesheet)

        fileMenu = self.menuBar().addMenu("&File")
        fileSaveNote = action("Save Note \tCtrl+S", self.savenote, icon='document-save') #, 'Ctrl+S') ####### 3/29/2012
        filePrintNote = action("Print Note", self.OnPrintNote, icon='document-print')
        filePageSetup = action("Page Setup", self.OnPageSetup, icon='document-print-preview')

        g.add_actions(fileMenu, (fileSaveNote, filePageSetup, filePrintNote))

        editMenu = self.menuBar().addMenu("&Edit")

        editCopyAction = action("&Copy", self.note.copy, QtGui.QKeySequence.Copy, "copy",
                    "Copy text to the clipboard")
        editCutAction = action("Cu&t", self.note.cut, QtGui.QKeySequence.Cut, "editcut",
                    "Cut text to the clipboard")
        editPasteAction = action("&Paste", self.note.paste, QtGui.QKeySequence.Paste, "paste",
                    "Paste in the clipboard's text")

        g.add_actions(editMenu, (editCopyAction, editCutAction, editPasteAction))

        formatMenu = self.menuBar().addMenu("&Format")
        bold = action("&Bold", self.note.toggleBold, 'Ctrl+B', icon='format-text-bold')
        italic = action("&Italic", self.note.toggleItalic, 'Ctrl+I', icon='format-text-italic')
        mono = action("&Mono", self.note.toggleCode, icon='format-text-mono')
        preformat = action("&Code Block", self.note.make_pre_block, icon='pre-tag')
        num_list = action("&Numbered List", self.note.create_numbered_list, icon='ordered-list-tag')
        bullet_list = action("&Bulleted List", self.note.create_bulleted_list, icon='unordered-list-tag')
        remove_formatting = action("&Clear Formatting", self.note.make_plain_text, icon='edit-clear')
        anchor = action("&Anchor", self.note.create_anchor, 'Ctrl+A', icon='internet-web-browser')

        ## header submenu ################################################
        headerMenu = QtWidgets.QMenu(self)
        headerMenuAction = action("&Header", self.note.increment_heading, 'Ctrl+H', icon='heading-tag')
        h1 = action("H&1", partial(self.note.make_heading,1))
        h2 = action("H&2", partial(self.note.make_heading,2))
        h3 = action("H&3", partial(self.note.make_heading,3))
        g.add_actions(headerMenu, (h1, h2, h3))
        headerMenuAction.setMenu(headerMenu)
        #################################################################

        g.add_actions(formatMenu, (bold, italic, mono, None, anchor, preformat, None, num_list, bullet_list, None, headerMenuAction, None, remove_formatting))

        formatToolbar = self.addToolBar("Format")
        formatToolbar.setObjectName("NoteToolBar")
        g.add_actions(formatToolbar, (filePrintNote, None, bold,italic, preformat, mono, None, preformat, anchor, None, headerMenuAction, num_list, bullet_list, remove_formatting))

        self.format_toolbar = formatToolbar
        #noteToolbar.setIconSize(QSize(24,16))
        #formatToolbar.setFixedHeight(24)

    def OnPrintNote(self):
        printer = QtGui.QPrinter()
        printDialog = QtGui.QPrintDialog(printer, self)
        if printDialog.exec_()== QtGui.QDialog.Accepted:
            self.note.print_(printer)

    def OnPageSetup(self):
        printer = QtGui.QPrinter()
        z = QtGui.QPageSetupDialog(printer)
        if z.exec_() == QtGui.QDialog.Accepted:
            print(printer.orientation())

    def savenote(self):
        self.main_window.savenote()

    def textCursor(self):
        return self.note.textCursor()
        
    def setTextCursor(self, cursor):
        self.note.setTextCursor(cursor)
        
class Logger (QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None, logfile=None):
        #QtGui.QPlainTextEdit.__init__(self, parent)
        super(Logger, self).__init__(parent)

        self.appendPlainText("%s\n"%asctime())

        self.path = logfile

        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

        self.document().setDefaultFont(QtGui.QFont('Helvetica', 8))
        
    def write(self, msg):
        # for some reason each print seems to create two writes, one of which is just a line feed
        msg = textwrap.fill(msg.strip(), 175)
        if msg: 
            self.appendPlainText(msg)
            
    def transfer(self):    
        path = os.path.join(os.environ['TMP'],'logger.%s'%NOTE_EXT)

        f = file(path,'w')
        f.write(self.toPlainText())
        f.close()

        os.startfile(path)
        
    def save(self):
        f = file(self.path,'a')
        f.write(self.toPlainText())
        f.close()

        QtGui.QMessageBox.information(self,  'Information', "Appended test to logfile.txt")
        
    def clear_text(self):
        self.clear()
        self.appendPlainText("%s\n"%asctime()) 

    def save_and_clear(self):
        f = file(self.path,'a')
        f.write(self.toPlainText())
        f.close()

        self.clear()
        self.appendPlainText("%s\n"%asctime())

        QtGui.QMessageBox.information(self,  'Information', "Appended test to logfile.txt")

class MyEvent(QtCore.QObject):
    signal = QtCore.pyqtSignal(str, dict)

if __name__ == '__main__':  

    # only needed if running two apps on some machine
    if g.config.has_option('Application', 'name' ):
        appname = g.config.get('Application', 'name' )
    else:
        appname = 'mylistmanager'

    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("SLZ Inc.")
    app.setOrganizationDomain("kayakroll.blogspot.com")
    app.setApplicationName(appname)
    app.setWindowIcon(QtGui.QIcon('bitmaps/mlm.png')) 
    mainwin = ListManager()
    
    #print = print_ = mainwin.logger.write # or print or print_ = g.logger.write (eventually leave print alone)
    print_ = mainwin.logger.write #made this change on 12-24-2014 - assume now print actually prints to the console but we'll see 
    
    # import is here so synchronize and toodledo are imported after ListManager instance is created since synchronize accesses pb and logger
    #and toodledo2 prints to logger
 
    import synchronize2
    import toodledo2
    
    mainwin.show()
    app.exec_() 



