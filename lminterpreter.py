
#@+leo-ver=5-thin
#@+node:slzatz.20141214110339.2: * @file C:/Users/szatz/python3/lminterpreter.py
#@@first
#@@nowrap
#@@tabwidth -4
#@@language python
#@+others
#@+node:slzatz.20120311185910.1685: ** imports

import os
import re
import sys
import code

import PyQt5.QtCore as QtCore
import PyQt5.QtGui as QtGui
import PyQt5.QtWidgets
Qt = QtCore.Qt

# borrowed with minor changes from  JeffMGreg

#https://github.com/JeffMGreg/PyInterp/blob/master/pyinterp.py

#@+node:slzatz.20120311185910.1686: ** class MyInterpreter
class MyInterpreter(PyQt5.QtWidgets.QMainWindow):
    #@+others
    #@+node:slzatz.20120311185910.1687: *3* __init__
    def __init__(self, parent):

        super(MyInterpreter, self).__init__(parent)

        console = MyConsole(self, locals()) 
        self.setCentralWidget(console) 
        
        #tb = self.addToolBar("Commands")
        #tb.setObjectName("Interpreter Toolbar")
        #self.addActions(formatToolbar, ()

    #@+node:slzatz.20120311185910.1688: *3* centerOnScreen
    def centerOnScreen(self):
        # center the widget on the screen
        #The QDesktopWidget class provides access to screen information on multi-head systems.
        resolution = QtGui.QDesktopWidget().screenGeometry()
        self.move((resolution.width()  / 2) - (self.frameSize().width()  / 2),
                  (resolution.height() / 2) - (self.frameSize().height() / 2))

    #@-others
#@+node:slzatz.20120311185910.1689: ** class MyConsole
class MyConsole(PyQt5.QtWidgets.QTextEdit):
    #@+others
    #@+node:slzatz.20120311185910.1693: *3* __init__
    def __init__(self,  parent, interpreterLocals=None):
        super(MyConsole, self).__init__(parent)

        self.parent = parent
        
        sys.stdout = self
        sys.stderr = self
        self.refreshMarker = False   # to change back to >>> from ...
        self.multiLine = False         # code spans more than one line
        self.command = ''             # command to be run
        self.history = []                # list of commands entered
        self.historyIndex = -1

        self.printBanner()              # print sys info
        self.marker()                     # make the >>> or ... marker   

        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, Qt.black)
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(0, 255, 0))
        self.setPalette(palette)
        self.setFont(QtGui.QFont('Courier', 8))
        
        self.palette = palette

        self.interpreterLocals = interpreterLocals if interpreterLocals else {}
            
        self.interpreter = code.InteractiveInterpreter(self.interpreterLocals)
        
    #@+node:slzatz.20120311185910.1694: *3* printBanner
    def printBanner(self):
        self.write(sys.version)
        self.write(' on ' + sys.platform + '\n')
        self.write('PyQt4 ' + QtCore.PYQT_VERSION_STR + '\n')
        msg = 'Type !hist for a history view and !hist(n) history index recall'
        self.write(msg + '\n')
        

    #@+node:slzatz.20120311185910.1695: *3* marker
    def marker(self):
        if self.multiLine:
            self.insertPlainText('... ')
        else:
            self.insertPlainText('>>> ')

    #@+node:slzatz.20120311185910.1697: *3* updateInterpreterLocals
    def updateInterpreterLocals(self, newLocals):
        className = newLocals.__class__.__name__
        self.interpreterLocals[className] = newLocals

    #@+node:slzatz.20120311185910.1698: *3* write
    def write(self, line):
        if "Traceback" in line:
            #QtGui.QMessageBox.warning(self,  "Exception", "Some kind of Exception just occurred!")
            self.palette.setColor(QtGui.QPalette.Base, Qt.red)
            self.palette.setColor(QtGui.QPalette.Text, Qt.black)
            self.setPalette(self.palette)
            self.parent.DockWidget4.raise_()
        self.insertPlainText(line)
        self.ensureCursorVisible()

    #@+node:slzatz.20120311185910.1699: *3* clearCurrentBlock
    def clearCurrentBlock(self):
        # block being current row
        length = len(self.document().lastBlock().text()[4:])
        if length == 0:
            return None
        else:
            # should have a better way of doing this but I can't find it
            [self.textCursor().deletePreviousChar() for x in range(length)]
        return True

    #@+node:slzatz.20120311185910.1700: *3* recallHistory
    def recallHistory(self):
        # used when using the arrow keys to scroll through history
        self.clearCurrentBlock()
        if self.historyIndex != -1:
            self.insertPlainText(self.history[self.historyIndex])
        return True

    #@+node:slzatz.20120311185910.1701: *3* customCommands
    def customCommands(self, command):
        
        if command == '!hist': # display history
            self.append('') # move down one line
            # vars that are in the command are prefixed with ____CC and deleted
            # once the command is done so they don't show up in dir()
            backup = self.interpreterLocals.copy()
            history = self.history[:]
            history.reverse()
            for i, x in enumerate(history):
                iSize = len(str(i))
                delta = len(str(len(history))) - iSize
                line = line  = ' ' * delta + '%i: %s' % (i, x) + '\n'
                self.write(line)
            self.updateInterpreterLocals(backup)
            self.marker()
            return True

        if re.match('!hist\(\d+\)', command): # recall command from history
            backup = self.interpreterLocals.copy()
            history = self.history[:]
            history.reverse()
            index = int(command[6:-1])
            self.clearCurrentBlock()
            command = history[index]
            if command[-1] == ':':
                self.multiLine = True
            self.write(command)
            self.updateInterpreterLocals(backup)
            return True

        if command=='!reset':
            palette = QtGui.QPalette()
            palette.setColor(QtGui.QPalette.Base, Qt.black)
            palette.setColor(QtGui.QPalette.Text, QtGui.QColor(0, 255, 0)) # lime green
            self.setPalette(palette)
            self.write('\n')
            self.marker()
            return True
            
        if command=='!clear':
            self.clear()
            self.printBanner()              # print sys info
            self.marker()                     # make the >>> or ... marker   
            return True
            
        return False

    #@+node:slzatz.20120311185910.1702: *3* keyPressEvent
    def keyPressEvent(self, event):

        if event.key() == Qt.Key_Escape:
            # proper exit
            self.interpreter.runsource('exit()') ###runIt

        if event.key() == Qt.Key_Down:
            if self.historyIndex == len(self.history):
                self.historyIndex -= 1
            try:
                if self.historyIndex > -1:
                    self.historyIndex -= 1
                    self.recallHistory()
                else:
                    self.clearCurrentBlock()
            except:
                pass
            return None

        if event.key() == Qt.Key_Up:
            try:
                if len(self.history) - 1 > self.historyIndex:
                    self.historyIndex += 1
                    self.recallHistory()
                else:
                    self.historyIndex = len(self.history)
            except:
                pass
            return None

        if event.key() == Qt.Key_Home:
            # set cursor to position 4 in current block. 4 because that's where
            # the marker stops
            blockLength = len(self.document().lastBlock().text()[4:])
            lineLength  = len(self.document().toPlainText())
            position = lineLength - blockLength
            textCursor  = self.textCursor()
            textCursor.setPosition(position)
            self.setTextCursor(textCursor)
            return None

        if event.key() in [Qt.Key_Left, Qt.Key_Backspace]:
            # don't allow deletion of marker
            if self.textCursor().positionInBlock() == 4:
                return None

        if event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            # set cursor to end of line to avoid line splitting
            textCursor = self.textCursor()
            position   = len(self.document().toPlainText())
            textCursor.setPosition(position)
            self.setTextCursor(textCursor)

            line = str(self.document().lastBlock().text())[4:] # remove marker
            line.rstrip()
            self.historyIndex = -1

            if self.customCommands(line):
                return None
            else:
                try:
                    line[-1]
                    self.haveLine = True
                    if line[-1] == ':':
                        self.multiLine = True
                    self.history.insert(0, line)
                except:
                    self.haveLine = False

                if self.haveLine and self.multiLine: # multi line command
                    self.command += line + '\n' # + command and line
                    self.append('') # move down one line
                    self.marker() # handle marker style
                    return None

                if self.haveLine and not self.multiLine: # one line command
                    self.command = line # line is the command
                    self.append('') # move down one line
                    self.interpreter.runsource(self.command) ### runIt
                    self.command = '' # clear command
                    self.marker() # handle marker style
                    return None

                if self.multiLine and not self.haveLine: #  multi line done
                    self.append('') # move down one line
                    self.interpreter.runsource(self.command) ##runIt
                    self.command = '' # clear command
                    self.multiLine = False # back to single line
                    self.marker() # handle marker style
                    return None

                if not self.haveLine and not self.multiLine: # just enter
                    self.append('')
                    self.marker()
                    return None
                return None
                
        # allow all other key events
        super(MyConsole, self).keyPressEvent(event)

    #@-others
#@+node:slzatz.20120311185910.1703: ** main
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    win = MyInterpreter(None)
    win.show()
    sys.exit(app.exec_())
#@-others
#@-leo
