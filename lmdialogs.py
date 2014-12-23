
#@+leo-ver=5-thin
#@+node:slzatz.20141220151846.42: * @file C:/Users/szatz/mylistman_p3/lmdialogs.py
#@@first
#@@nowrap
#@@tabwidth -4
#@@language python
#@+others
#@+node:slzatz.20100314151332.2778: ** imports


import sys
import platform
import os

from PyQt5 import QtCore, QtGui, QtWidgets
QDialog = QtWidgets.QDialog
Qt = QtCore.Qt

import datetime

from ui_AuthenticationDialog import Ui_AuthenticationDialog

import markdown2 as markdown

import lmglobals as g #May 29, 2012
#print_ = g.logger.write # this won't work here because g.logger has not been defined when listmanager.py imports lmdialogs.py

Ok = QtWidgets.QDialogButtonBox.Ok

Cancel = QtWidgets.QDialogButtonBox.Cancel

Close = QtWidgets.QDialogButtonBox.Close



#@+node:slzatz.20100314151332.2779: ** TaskInfo Dialog
#@+node:slzatz.20100314151332.2780: *3* TaskInfo
class TaskInfo(QDialog):

    def __init__(self, name, data=None, labels=None, parent=None):
        super(TaskInfo, self).__init__(parent)

        table = TaskInfoTable(parent, data, labels)
        table.setMinimumSize(600,600)

        table.setItemDelegateForRow(labels.index('note'), NoteItemDelegate(self)) # Custom Delegate to control editor

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(table)

        buttonBox = QtWidgets.QDialogButtonBox(Ok)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(name)

        buttonBox.accepted.connect(self.accept)

#@+node:slzatz.20100314151332.2781: *3* TaskInfoTable
class TaskInfoTable(QtWidgets.QTableWidget): 
    def __init__(self, parent, data=None, labels=None):
        super(TaskInfoTable, self).__init__(parent)

        #data = [c_task, s_task]
        c_task = data[0]
        s_task = data[1]

        self.setColumnCount(2)
        self.setRowCount(len(labels))

        self.setColumnWidth(0,250)
        self.setColumnWidth(1,250)

        self.setVerticalHeaderLabels(labels) # Vertical.. is for the row headers
        self.verticalHeader().setDefaultSectionSize(18) #somewhat cryptic way to set row sizes
        self.verticalHeader().setVisible(True)

        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft) # set column header text alignment - doesn't affect cells
        self.horizontalHeader().setSectionsMovable(False)
        self.setHorizontalHeaderLabels(['client', 'server']) # Horizontal... is the column headers

        self.setShowGrid(True)

        for n,lab in enumerate(labels):
            item = QtWidgets.QTableWidgetItem(str(c_task.get(lab, '')))
            self.setItem(n, 0, item)

            item = QtWidgets.QTableWidgetItem(str(s_task.get(lab, '')))
            self.setItem(n, 1, item)

        self.setRowHeight(labels.index('title'), 50)
        self.setRowHeight(labels.index('note'),200)

        self.setAlternatingRowColors(True)

        #self.setEditTriggers(QTableWidget.NoEditTriggers)
        #self.setSelectionBehavior(QTableWidget.SelectRows)
        #self.setSelectionMode(QTableWidget.SingleSelection)

#@+node:slzatz.20100314151332.2782: *3* NoteItemDelegate
class NoteItemDelegate(QtWidgets.QItemDelegate):

    def __init__(self, parent = None):
        super(NoteItemDelegate, self).__init__(parent)
        self.parent = parent

    def paint(self, painter, option, index):

        text = index.model().data(index)

        document = QtGui.QTextDocument()
        document.setDefaultFont(option.font)
        
        simple_html = markdown.markdown(text)
        simple_html = simple_html.replace('\n</code></pre>', '</code></pre>')
        document.setHtml(simple_html)
        #document.setHtml(markdown.markdown(text))

        painter.save()
        painter.translate(option.rect.x(), option.rect.y())
        rect = QtCore.QRectF(0.0, 0.0, float(option.rect.width()), float(option.rect.height()))
        document.drawContents(painter, rect)
        painter.restore()      

    def createEditor(self, parent, option, index):

        print("in createEditorNote")
        editor = QtWidgets.QTextEdit(parent)

        return editor

    def setEditorData(self, editor, index):

        print("In setEditorDataNote")

        text = index.model().data(index, Qt.DisplayRole)
        editor.setText(text)


#@+node:slzatz.20120527203527.1701: ** TextColor Dialog
#@+node:slzatz.20120527203527.1702: *3* TextColor
class TextColor(QDialog):

    def __init__(self, name, things, parent=None, type_=None): #highlight
        super(TextColor, self).__init__(parent)
        
        self.print_ = g.logger.write

        table = TextColorTable(parent, things, type_)
        table.setMinimumSize(600,600)
        table.cellClicked.connect(self.cellclick)   #SIGNAL("cellClicked(int,int)")
        table.itemSelectionChanged.connect(self.itemselected)    #SIGNAL("itemSelectionChanged()")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(table)

        buttonBox = QtWidgets.QDialogButtonBox(Close)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(name)

        buttonBox.rejected.connect(self.reject)
        
        self.table = table
        
    def cellclick(self, r, c):
        self.print_("In cellclick")
        columns = {0:'title', 1:'icon', 2:'color', 3:'color'}
        self.print_("r={0}, c={1}".format(r,c))
        title = self.table.item(r, 0).text()   # or item.(r, 0).data(Qt.DisplayRole)
        self.print_("title = {}".format(title))

        self.title = title
        self.column = columns[c]
        self.done(1)
        
    def itemselected(self):
        ranges = self.table.selectedRanges()
        row = ranges[0].topRow() if ranges else -1  
        self.print_("In itemselected; row = {}".format(row))
        
#@+node:slzatz.20120527203527.1703: *3* TextColorTable
class TextColorTable(QtWidgets.QTableWidget): 
    def __init__(self, parent, things, type_):
        super(TextColorTable, self).__init__(parent)

        self.setColumnCount(4)
        self.setRowCount(len(things))

        self.setColumnWidth(0,100)
        self.setColumnWidth(1,25)
        self.setColumnWidth(2,200)
        self.setColumnWidth(3,200)

        #self.setVerticalHeaderLabels(labels) # Vertical.. is for the rows (no labels produces numbers, which seems OK)
        self.verticalHeader().setDefaultSectionSize(18) #somewhat cryptic way to set row sizes
        self.verticalHeader().setVisible(True)

        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft) # set column header text alignment - doesn't affect cells
        self.horizontalHeader().setMovable(False)
        self.setHorizontalHeaderLabels(['title', 'icon', 'normal', 'bold']) # Horizontal... is the column headers

        self.setShowGrid(True)
        
        bold = QtGui.QFont()
        bold.setBold(True)

        for n,thing in enumerate(things):
            item = QtWidgets.QTableWidgetItem(thing.title)
            self.setItem(n, 0, item)
            
            # note if thing.image == None then an 'empty' icon is created -- isNull() == True
            pxmap = QtGui.QPixmap()
            pxmap.loadFromData(thing.image, 'PNG')
            icon = (QtGui.QIcon(pxmap), '')
            # note that icon = (QtGui.QIcon(thing.image), '') does not work even though essentially the same thing works for qresources
   
            item = QtWidgets.QTableWidgetItem(*icon) # note works when thing.image == None
            #item = QtGui.QTableWidgetItem(QtGui.QIcon(os.path.join(g.IMAGES_DIR, 'folder_icons', '{}'.format(thing.icon))),'') #handles icon = None
            self.setItem(n, 1, item)
            
            item = QtWidgets.QTableWidgetItem("The rain in spain")
            item.setTextColor(QtGui.QColor(thing.textcolor))
            self.setItem(n, 2, item)
            
            item = QtWidgets.QTableWidgetItem("The rain in spain")
            item.setFont(bold)
            item.setTextColor(QtGui.QColor(thing.textcolor))
            self.setItem(n, 3, item)       

        self.setAlternatingRowColors(True)

#@+node:slzatz.20100314151332.2783: ** SynchResults
class SynchResults(QDialog):
    def __init__(self, title, text=None, parent=None, OkCancel=False):
        super(SynchResults, self).__init__(parent)

        textBrowser = QtWidgets.QTextBrowser()
        textBrowser.setMinimumSize(800,550)
        textBrowser.setReadOnly(True)
        textBrowser.setFontPointSize(8.0)

        if text:
            textBrowser.setPlainText(text)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(textBrowser)

        if OkCancel:
            buttonBox = QtWidgets.QDialogButtonBox(Ok|Cancel)
        else:
            buttonBox = QtWidgets.QDialogButtonBox(Ok)
            
        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(title)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)



#@+node:slzatz.20100314151332.2784: ** ChoiceDlg
class ChoiceDlg(QDialog):

    def __init__(self, name, stringlist=None, multi=True, label_text=None, parent=None):
        super(ChoiceDlg, self).__init__(parent)

        listWidget = QtWidgets.QListWidget()
        listWidget.setSelectionMode(QtWidgets.QListWidget.MultiSelection if multi else QtWidgets.QListWidget.SingleSelection)
            
        if stringlist is not None:
            listWidget.addItems(stringlist)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(listWidget)
        
        if label_text:
            font = QtGui.QFont()
            font.setBold(True)
            font.setPointSize(10)
            label = QtWidgets.QLabel(label_text)
            label.setFont(font)
            layout.addWidget(label)
            
        buttonBox = QtWidgets.QDialogButtonBox(Ok|Cancel)
        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(name)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        self.listWidget = listWidget

    def accept(self):
        self.choices = []
        for item in self.listWidget.selectedItems():
            self.choices.append(item.text())
            
        super(ChoiceDlg, self).accept()

#@+node:slzatz.20100314151332.3086: ** VersionsDlg
class VersionsDlg(QDialog):

    def __init__(self, title, text=None, parent=None):
        super(VersionsDlg, self).__init__(parent)

        label = QtWidgets.QLabel(text)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        buttonBox = QtWidgets.QDialogButtonBox(Ok)
        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(title)
        
        #self.connect(buttonBox, QtCore.SIGNAL("accepted()"),self, QtCore.SLOT("accept()"))
        buttonBox.accepted.connect(self.accept)

#@+node:slzatz.20120620063905.1702: ** SelectContextFolder
class SelectContextFolder(QDialog):

    def __init__(self, name, d=None, parent=None, initial_selection=None, multi=False, new_entry=True):
        super(SelectContextFolder, self).__init__(parent)

        self.listWidget = QtWidgets.QListWidget()
        
        if multi:
            self.listWidget.setSelectionMode(QtWidgets.QListWidget.MultiSelection)
        else:
            self.listWidget.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
        
        pxmap_no = QtGui.QPixmap(16,16)
        pxmap_no.fill() #default Qt.white
        no_icon = QtGui.QIcon(pxmap_no)

        for title,icon in list(d.items()):
            QtWidgets.QListWidgetItem(icon[0] if icon[0] else no_icon, title, self.listWidget)

        layout = QtWidgets.QVBoxLayout()
        
        if new_entry:
            self.lineEdit = QtWidgets.QLineEdit()
            layout.addWidget(self.lineEdit)
            
        layout.addWidget(self.listWidget)

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(name)
        
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        if initial_selection:
            self.set_initial_selection(initial_selection)

        self.listWidget.setFocus()
        
        self.new_entry = new_entry

    def set_initial_selection(self, text):
        lst = self.listWidget.findItems (text, Qt.MatchFixedString|Qt.MatchCaseSensitive)
        item = lst[0]
        self.listWidget.setCurrentItem(item) # may not need to setItemSelected

    def accept(self):
        #choice = self.listWidget.selectedItems()
        #self.list_choice = choice[0].text() if choice else None # 03/13/2010
        
        if self.new_entry:
            self.new_name = self.lineEdit.text() # added self # 03/13/2010

        super(SelectContextFolder, self).accept()

#@+node:slzatz.20120304081931.1661: ** MultiChoiceOrNew
class MultiChoiceOrNew(QDialog):
    #@+others
    #@+node:slzatz.20120304081931.1662: *3* __init__
    def __init__(self, name, stringlist=None, parent=None, initial_selection=None):
        super(MultiChoiceOrNew, self).__init__(parent)

        self.name = name

        self.listWidget = QtWidgets.QListWidget()
        self.listWidget.setSelectionMode(QtWidgets.QListWidget.MultiSelection)

        if stringlist is not None:
            self.listWidget.addItems(stringlist)

        self.lineEdit = QtWidgets.QLineEdit()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.listWidget)

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(name)

        self.connect(buttonBox, QtCore.SIGNAL("accepted()"),self, QtCore.SLOT("accept()"))
        self.connect(buttonBox, QtCore.SIGNAL("rejected()"),self, QtCore.SLOT("reject()"))

        if initial_selection:
            self.setinitialselections(initial_selection)

        self.listWidget.setFocus()

    #@+node:slzatz.20120304081931.1663: *3* setinitialselections
    def setinitialselections(self, initial_selection):
        for text in initial_selection:
            result = self.listWidget.findItems (text, Qt.MatchFixedString) #MatchFixedString flag performs a case insensitive search
            if result:  # if somehow '' is in a tag (for example trailing comma in tag) but this should not happen
                item = result[0]
            self.listWidget.setItemSelected(item, True)

    #@+node:slzatz.20120304081931.1664: *3* accept
    def accept(self):
        self.choices = [item.text() for item in self.listWidget.selectedItems()]
        self.newentry = self.lineEdit.text() # added self # 03/13/2010

        #QDialog.accept(self) # can't do self.accept() since we've overwritten that method
        super(MultiChoiceOrNew, self).accept()

    #@-others
#@+node:slzatz.20120613065744.1701: ** SelectIcon
class SelectIcon(QDialog):

    def __init__(self, name, things=None, pngs=None, parent=None, initial_selection=None, type_=None):
        super(SelectIcon, self).__init__(parent)

        self.name = name

        self.listWidget1 = QtWidgets.QListWidget()
        self.listWidget1.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
        self.listWidget1.setViewMode(QtWidgets.QListView.ListMode) #IconMode
        #self.listWidget1.setDisabled(True)

        self.listWidget2 = QtWidgets.QListWidget()
        self.listWidget2.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
        self.listWidget2.setViewMode(QtWidgets.QListView.ListMode) #IconMode

        things = things if things else []
        pngs = pngs if pngs else []
        
        pxmap_no = QtGui.QPixmap(16,16)
        pxmap_no.fill(Qt.lightGray) #default = Qt.white
        
        #painter = QtGui.QPainter(pxmap)
        #painter.setPen(Qt.blue)
        #painter.drawLine(2,2,14,14)
        
        no_icon = QtGui.QIcon(pxmap_no)
        
        for t in things:
            if t.image:
                pxmap = QtGui.QPixmap()
                pxmap.loadFromData(t.image)
                icon = QtGui.QIcon(pxmap)
            else:
                icon = no_icon

            #icon = QtGui.QIcon("bitmaps/{0}_icons/{1}".format(type_, t.icon) if t.icon else no_icon
            
            QtWidgets.QListWidgetItem(icon, t.title, self.listWidget1)

        QtWidgets.QListWidgetItem(no_icon, 'No Icon', self.listWidget2) 
        for s in pngs:
            QtWidgets.QListWidgetItem(QtGui.QIcon("bitmaps/folder_icons/{}".format(s)), s, self.listWidget2) 
            #QtGui.QListWidgetItem(QtGui.QIcon(os.path.join(g.IMAGES_DIR, '{}_icons'.format(type_),'{}'.format(s), self.listWidget2)))
        
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(10)
        label_L = QtWidgets.QLabel("Current folders")
        label_L.setFont(font)
        label_R = QtWidgets.QLabel("Available icons")
        label_R.setFont(font)
        #layout.addWidget(label)
        
        layout_L = QtWidgets.QVBoxLayout()
        layout_L.addWidget(label_L)
        layout_L.addWidget(self.listWidget1)
        
        layout_R = QtWidgets.QVBoxLayout()
        layout_R.addWidget(label_R)
        layout_R.addWidget(self.listWidget2)

        layout1 = QtWidgets.QHBoxLayout()
        layout1.addLayout(layout_L)
        layout1.addLayout(layout_R)

        layout2 = QtWidgets.QVBoxLayout()
        layout2.addLayout(layout1)

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel)

        layout2.addWidget(buttonBox)
        self.setLayout(layout2)
        self.setWindowTitle(name)

        # A QDialog has the slots (methods) accept and reject
        # Note that you can override those slots and still use
        # the SLOT construction
        self.connect(buttonBox, QtCore.SIGNAL("accepted()"),self, QtCore.SLOT("accept()"))
        self.connect(buttonBox, QtCore.SIGNAL("rejected()"),self, QtCore.SLOT("reject()"))

        self.connect(self.listWidget1, QtCore.SIGNAL("itemClicked(QListWidgetItem*)"), self.itwasclicked1)
        self.connect(self.listWidget2, QtCore.SIGNAL("itemClicked(QListWidgetItem*)"), self.itwasclicked2)

        # this actually works -- not sure why you'd use it but it shows how
        # you include a C++ signature (if that's the right term)
        #self.connect(buttonBox, SIGNAL("clicked(QAbstractButton*)"),self.itwasclicked)

        if initial_selection:
            self.set_initial_selection(initial_selection)

        self.listWidget2.setFocus()

    def set_initial_selection(self, text):
        lst = self.listWidget1.findItems (text, Qt.MatchFixedString|Qt.MatchCaseSensitive)
        item = lst[0]
        self.listWidget1.setCurrentItem(item) # may not need to setItemSelected

    def itwasclicked1(self):
        print("it was clicked 1")
        self.listWidget2.clearSelection()

    def itwasclicked2(self):
        print("it was clicked 2")
        self.listWidget1.clearSelection()

    #def reject(self): #03/13/2010
    #    print("cancel")
    #    QDialog.reject(self) # can't do self.reject() since we've overwritten that method

    def accept(self):
        #choice = self.listWidget1.selectedItems() if self.listWidget1.selectedItems() else self.listWidget2.selectedItems()
        choice = self.listWidget2.selectedItems()
        self.icon_choice = choice[0].text() if choice else None 

        QDialog.accept(self) # can't do self.accept() since we've overwritten that method

#@+node:slzatz.20100314151332.2787: ** TaskDueDate
class TaskDueDate(QDialog):
    def __init__(self, title, date=None, parent=None):
        super(TaskDueDate, self).__init__(parent)

        calendar = QtWidgets.QCalendarWidget()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(calendar)

        buttonBox = QtWidgets.QDialogButtonBox(Ok|Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        # the following was used for testing
        #self.connect(calendar, SIGNAL("selectionChanged()"), self.selection_changed)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(title)

        self.calendar = calendar

        if date:
            calendar.setSelectedDate(date)

    def selection_changed(self):
        # this was used for testing
        print(self.calendar.selectedDate().toString(Qt.TextDate))
        print(self.calendar.selectedDate().toString(Qt.ISODate))

    def accept(self):
        self.date = self.calendar.selectedDate()
        super(TaskDueDate, self).accept()

#@+node:slzatz.20120505112324.1683: ** TaskDueDateTime
class TaskDueDateTime(QDialog):
    def __init__(self, title, qdatetime=None, state=None, parent=None):
        super(TaskDueDateTime, self).__init__(parent)
        
        dteditor = QtWidgets.QDateTimeEdit(qdatetime, parent) if qdatetime else QtWidgets.QDateTimeEdit(parent)
        dteditor.setDisplayFormat("M'/'d'/'yy' 'hh:mm")
        dteditor.setCalendarPopup(True)
        
        spin = AlarmSpinBox(self)
        # 15 min, 30 min, one hour, 2 hours, 1 day, 1 week
        
        alarm = QtWidgets.QCheckBox("Set Alarm")
        alarm.setChecked(state)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(dteditor)  #layout.addWidget(calendar)
        layout.addWidget(spin)
        layout.addWidget(alarm)

        buttonBox = QtWidgets.QDialogButtonBox(Ok|Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        # the following was used for testing
        self.connect(dteditor, QtCore.SIGNAL("dateTimeChanged(QDateTime)"), self.selection_changed)
        self.connect(spin, QtCore.SIGNAL("valueChanged(int)"), self.do_something)
        self.connect(spin, QtCore.SIGNAL("valueChanged(QString)"), self.do_something2)

        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(title)
        
        self.dteditor = dteditor
        self.alarm = alarm
        self.qdatetime = qdatetime
        #self.dt = datetime.datetime.fromtimestamp(qdatetime.toTime_t())
        self.dt = datetime.datetime.now()
            
    def do_something(self, i):
        print(str(i))
        if i==0:
            self.dteditor.setDateTime(self.qdatetime)
        elif i==1:
            delta = datetime.timedelta(minutes=5)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute))
        elif i==2:
            delta = datetime.timedelta(minutes=15)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute))
        elif i==3:
            delta = datetime.timedelta(minutes=30)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute))
        elif i==4:
            delta = datetime.timedelta(hours=1)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute)) 
        elif i==5:
            delta = datetime.timedelta(days=1)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute))
        elif i==6:
            delta = datetime.timedelta(weeks=1)
            newdt = self.dt+delta
            self.dteditor.setDateTime(QtCore.QDateTime(newdt.year, newdt.month, newdt.day, newdt.hour, newdt.minute))
            
    def do_something2(self, s):
        print(s)

    def selection_changed(self, date):
        # this was used for testing
        print("Selection Changed")
        print(self.dteditor.date().toString())
        print(self.dteditor.dateTime().toString())

    def accept(self):
        self.qdatetime = self.dteditor.dateTime()
        self.setalarm = self.alarm.isChecked()
        super(TaskDueDateTime, self).accept()

#@+node:slzatz.20120506103546.1683: ** AlarmSpinBox
class AlarmSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super(AlarmSpinBox, self).__init__(parent)
        
        regex = QtCore.QRegExp(r"[1-9][mindayshour]\\d{0,6}")
        self.validator = QtGui.QRegExpValidator(regex, self)
        print(repr(self.validator))
        self.setRange(0,6)
        self.setWrapping(True)
        #self.setReadOnly(True)
        self.lineEdit().setReadOnly(True)
                
    def valueFromText(self, text):
        #15 min, 30 min, 1 hour, 1 day, 1 week, 1 month
        if text == "0 min":
            return 0
        elif text=="5 min":
            return 1
        elif text == "15 min":
            return 2
        elif text=="30 min":
            return 3
        elif text=="1 hour":
            return 4
        elif text=="1 day":
            return 5
        elif text=="1 week":
            return 6
            
    def textFromValue(self, value):
        if value==0:
            return "0 min"
        elif value==1:
            return "5 min"
        elif value==2:
            return "15 min"
        elif value==3:
            return "30 min"
        elif value==4:
            return "1 hour"
        elif value==5:
            return "1 day"
        elif value==6:
            return "1 week"
            
    def validate(self, text, pos):
        return self.validator.validate(text, pos)
        
    
        
    
        
    
#@+node:slzatz.20100314151332.2788: ** ModifyColumns Dialog
#@+node:slzatz.20120324175830.1713: *3* Modify Columns
class ModifyColumns(QDialog):

    def __init__(self, parent=None, lst=None, lst2=None):
        super(ModifyColumns, self).__init__(parent)
        
        self.setAcceptDrops(True) ########### changed on 4/12/2014 wasn't previously necessary

        listWidget = LWidget(parent,lst)
        listWidget.setWindowTitle("1")
        listWidget2 = LWidget(parent, lst2)
        listWidget2.setWindowTitle("2")


        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        splitter.addWidget(listWidget)
        splitter.addWidget(listWidget2)

        buttonBox = QtWidgets.QDialogButtonBox(Ok|Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(splitter)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

        self.setWindowTitle("Modify Columns Test")

        self.lw2 = listWidget2
        
        print("Launched Modify Columns ...")
        
        print("drag enabled =",self.lw2.dragEnabled())

    def accept(self):
        lst = []
        for index in range(self.lw2.count()):
            lst.append(self.lw2.item(index).text()) # 03/13/2010
        self.lst = lst

        super(ModifyColumns, self).accept()
#@+node:slzatz.20120324175830.1714: *3* LWidget
class LWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None, lst=None):
        super(LWidget, self).__init__(parent) ###########
        self.setAcceptDrops(True)
        self.setDragEnabled(True)

        if lst is not None:
            self.addItems(lst)
        else:
            self.addItems(['a','b','c','d'])

    def dragEnterEvent(self, event):
        print("dragEnterEvent")
        event.accept()

    def dragMoveEvent(self, event):
        print("dragMoveEvent")
        event.setDropAction(Qt.MoveAction)
        event.accept()

    def dropEvent(self, event):
        if event.source()==self:
            #event.setDropAction(Qt.MoveAction) #doesn't seem to matter ######
            QtWidgets.QListWidget.dropEvent(self, event)
            if platform.uname()[0]=='Linux':
                items = self.selectedItems()
                self.takeItem(self.row(items[0]))
            return
        print("drop event", event)
        event.setDropAction(Qt.MoveAction) #MoveAction
        #QListWidget.dropEvent(self, event)
        #event.accept() # this alone pulls it off but it doesn't show up.
        print("event.source()=",event.source())
        source = event.source()
        items = source.selectedItems()
        item = items[0]
        print(item.text())
        text = item.text()
        self.addItem(text)
        #source.takeItem(source.row(item))
        #QListWidget.dropEvent(self, event) # doesn't show up if event.accept()
        #event.accept()
        print("self.windowTitle()={0}".format(self.windowTitle()))
        print(event.source().windowTitle())
        event.accept()


#@-others
#@-leo
