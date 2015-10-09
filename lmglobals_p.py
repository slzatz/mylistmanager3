import os
import urllib.request, urllib.error, urllib.parse
import configparser as configparser

cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
CONFIG_FILE = os.path.join(cwd,'mylistmanager_p.ini')
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
            
def internet_accessible():
    try:
        response=urllib.request.urlopen('http://www.google.com',timeout=1)
    except:
        return False
    else:
        return True

