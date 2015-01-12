# for use in non-QT environments
import os
import urllib.request, urllib.error, urllib.parse
import configparser as configparser

from aws_credentials import rds_uri

cwd = os.getcwd()  #cwd => /home/slzatz/mylistmanager
CONFIG_FILE = os.path.join(cwd,'mylistmanager.ini')
LOCAL_DB_FILE = os.path.join(cwd,'lmdb','mylistmanager.db')
sqlite_uri = 'sqlite:///' + LOCAL_DB_FILE
DB_URI = None #####################right now need to change this manually in listmanager  
IMAGES_DIR = os.path.join(cwd,'bitmaps')
PLUGIN_DIR = os.path.join(cwd,'plugins')
USER_ICONS = 'folder_icons'
CORE_ICONS = ''
LOG_FILE = os.path.join(cwd,'logfile.txt')
del cwd

key = None
timestamp = None

config = configparser.RawConfigParser()
config.read(CONFIG_FILE)

def internet_accessible():
    try:
        response=urllib.request.urlopen('http://www.google.com',timeout=1)
    except urllib.error.URLError:
        return False
    else:
