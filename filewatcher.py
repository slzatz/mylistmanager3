import sys
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
import tempfile, os
from subprocess import call, Popen
vim = os.path.abspath("c:/Program Files (x86)/Vim/vim74/gvim.exe")
#EDITOR = os.environ.get('EDITOR','vim') #that easy!
#print(EDITOR)
initial_message = "hi" # if you want to set up the file somehow
#f = open("hello.txt")
#print(f)
#with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as temp:
#  temp.write(initial_message)
  #temp.flush()
#  print(temp.name)
#call([vim, os.path.abspath(temp.name)])
temp = tempfile.NamedTemporaryFile(mode='w', suffix=".tmp", delete=False)
#temp = open("hello.txt", mode='w+')
temp.write(initial_message)
temp.flush() #without this doesn't write the message
temp.close() #apparently unless you close the file, vim sees it as being used by another program and opens in read only mode
print(temp.name)
#call([vim, os.path.abspath(temp.name)])
Popen([vim, os.path.abspath(temp.name)])
print(temp.name)

class Example(QtWidgets.QWidget):
    
    def __init__(self):
        super(Example, self).__init__()
        #self.initUI()

    def directory_changed(self, path):
        print('Directory Changed: %s' % path)
        self.setWindowTitle(path)
        
    def file_changed(self, path):
        print('File Changed: %s' % path)
        self.setWindowTitle(path)

    def initUI(self):
        
        self.setGeometry(300, 300, 250, 150)
        self.setWindowTitle('Icon')
        self.setWindowIcon(QtGui.QIcon('web.png'))        
                
        p = QtCore.QDir("c:/users/szatz/mylistman_p3")
        paths = ["."]
        self.fs_watcher = QtCore.QFileSystemWatcher()
        self.fs_watcher.addPath(p.path())
        self.fs_watcher.addPath("hello.txt")
        self.fs_watcher.addPath(os.path.abspath(temp.name))
        self.fs_watcher.directoryChanged.connect(self.directory_changed)
        self.fs_watcher.fileChanged.connect(self.file_changed)
        print(self.fs_watcher.directories())
        print(self.fs_watcher.files())
        self.setWindowTitle('hello')

def main():
    
    app = QtWidgets.QApplication(sys.argv)
    ex = Example()
    ex.initUI()
    ex.show()
    print(ex.fs_watcher.files())
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    print("hello")

  #  '/path/to',
  #  '/path/to/files_1',
  #  '/path/to/files_2',
  #  '/path/to/files_3',
  #  ]


