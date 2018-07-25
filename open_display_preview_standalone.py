#!bin/python
'''
curses script that is called by listmanager_cli.py do_open method
To handle the edge case of the last page, we could add page_max_rows
which would always be the same as max_rows except for the last page
Not sure it's worth it so haven't implemented it
  
Note that when you press an arrow key getch sees three keys in rapid succession as follows:

\033
[
A, B, C or D

Below are the basic colors supported by curses expressed as:
    curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

curses.color_pair(2)|curses.A_BOLD

0:black, 1:red, 2:green, 3:yellow, 4:blue, 5:magenta, 6:cyan, and 7:white

Other ways to change text:
A_BLINK	Blinking text
A_BOLD	Extra bright or bold text
A_DIM	Half bright text
A_REVERSE	Reverse-video text
A_STANDOUT	The best highlighting mode available
A_UNDERLINE	Underlined text
'''
import sys
import curses
from datetime import datetime
import time
import json
import textwrap
from SolrClient import SolrClient
import requests
from config import SOLR_URI
from lmdb_p import *
import xml.etree.ElementTree as ET

actions = {'n':'note', 't':'title', 's':'star', 'c':'completed', '\n':'select', 'q':None}
keys = {'B':'j', 'A':'k', 'C':'l', 'D':'h'}

solr = SolrClient(SOLR_URI + '/solr')
collection = 'listmanager'

def update_solr(task=None):
    solr = SolrClient(SOLR_URI + '/solr/')
    collection = 'listmanager'

    if not task:
        return

    document = {}
    document['id'] = task.id
    document['title'] = task.title
    document['note'] = task.note if task.note else ''
    #document['tag'] =[t for t in task.tag.split(',')] if task.tag else []
    document['tag'] =[k.name for k in task.keywords] # better this than relying on tag

    document['completed'] = task.completed != None
    document['star'] = task.star # haven't used this yet and schema doesn't currently reflect it

    #note that I didn't there was any value in indexing or storing context and folder
    document['context'] = task.context.title
    document['folder'] = task.folder.title

    json_docs = json.dumps([document])
    response = solr.index_json(collection, json_docs)

    # response = solr.commit(collection, waitSearcher=False) # doesn't actually seem to work
    # Since solr.commit didn't seem to work, substituted the below, which works
    url = SOLR_URI + '/solr/' + collection + '/update'
    r = requests.post(url, data={"commit":"true"})
    #print(r.text)
    root = ET.fromstring(r.text)
    #if root[0][0].text == '0':
    #    print(self.colorize("solr update successful", 'yellow'))
    #else:
    #    print(self.colorize("there was a problem with the solr update", 'yellow'))

def open_display_preview(c_title):
    screen = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(4, 15, -1)
    color_map = {'{blue}':3, '{red}':1, '{green}':2,'{white}':4}
    curses.curs_set(0)
    curses.cbreak() # respond to keys without needing Enter
    curses.noecho()
    size = screen.getmaxyx()
    screen.nodelay(True)
    #normal = curses.A_NORMAL
    half_width = size[1]//2
    win = curses.newwin(size[0]-2, half_width-1, 1, 1)
    win2 = curses.newwin(size[0]-2, half_width-1, 1, half_width+1)

    page = 0
    row_num = 1
    max_chars_line = half_width - 5
    max_rows = size[0]-4
    tasks = remote_session.query(Task).join(Context).\
                filter(Context.title==c_title, Task.deleted==False).\
                       order_by(desc(Task.modified)).all()
    last_page = len(tasks)//max_rows
    last_page_max_rows = len(tasks)%max_rows

    def draw_note(task):
        win2.clear()
        win2.box()

        note = task.note if task.note else ""
        paras = note.splitlines()

        n = 1

        for para in paras:
            # this handles blank lines
            if not para:
                n+=1
                continue

            for line in textwrap.wrap(para, max_chars_line):

                if n > max_rows:
                    break

                try:
                    win2.addstr(n, 3, line)  #(y,x)
                except Exception as e:
                     pass

                n+=1

        win2.refresh()

    def draw():
        win.clear()
        win.box()
        page_tasks = tasks[max_rows*page:max_rows*(page+1)]
        n = 1
        for i,task in enumerate(page_tasks, page*max_rows+1):

            if n+2 == size[0]:
                break

            c = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL
            win.addstr(n, 2, f"{i}. {task.title[:max_chars_line-7]}{c}", font)  #(y,x)

            n+=1

        win.refresh() 


    screen.clear()
    screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]} max_rows = {max_rows} last_page = {last_page}", curses.A_BOLD)

    s = "j:page down k: page up h:page left l:page right n:edit [n]ote t:edit [t]itle s:[s]elect and ENTER/RETURN no action"
    if len(s) > size[1]:
        s = s[:size[1]-1]
    screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
    screen.refresh()

    draw()
    draw_note(tasks[0])
    win.addstr(row_num, 1, ">")  #j
    win.refresh()

    accum = []
    arrow = False
    page_max_rows = max_rows if last_page else last_page_max_rows
    while 1:
        n = screen.getch()
        if n == -1:
            continue

        c = chr(n)
        if arrow:
            accum.append(c)
            if len(accum) == 2:
                c = keys.get(accum[-1], 'z')
                accum = []
                arrow = False
        elif c == '\x1b': #o33:
            arrow = True
            continue
            
        #if c in ['s', 'n', 't', 'c', '\n', 'q']:
        if c in ['n', 't', '\n', 'q']:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            task = tasks[(page*max_rows)+row_num-1]
            return {'action':actions[c], 'task_id':task.id}

        if c in ['s']:
            task = tasks[(page*max_rows)+row_num-1]
            task.star = not task.star
            comp = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL
            win.move(row_num, 2)
            win.clrtoeol()
            win.addstr(row_num, 2, f"{page*max_rows+row_num}. {task.title[:max_chars_line-7]}{comp}", font)  #(y,x)
            win.refresh()
            remote_session.commit()
            #update_solr(task)

        if c in ['c']:
            task = tasks[(page*max_rows)+row_num-1]

            if not task.completed:
                task.completed = datetime.now().date()
            else:
                task.completed = None

            remote_session.commit()

            comp = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL
            win.move(row_num, 2)
            win.clrtoeol()
            win.addstr(row_num, 2, f"{page*max_rows+row_num}. {task.title[:max_chars_line-7]}{comp}", font)  #(y,x)
            win.addch(row_num, half_width-2, curses.ACS_VLINE) # unfortunately the clrtoeol wipes out the vertical box line character
            win.refresh()
            remote_session.commit()
            #update_solr(task)

        elif c == 'k':
            win.addstr(row_num, 1, " ")  #k
            row_num-=1
            if row_num==0:
                page = (page - 1) if page > 0 else last_page
                draw()  
                page_max_rows = max_rows if not page==last_page else last_page_max_rows
                row_num = page_max_rows
            win.addstr(row_num, 1, ">")  #k
            win.refresh()
            task = tasks[page*max_rows+row_num-1]
            draw_note(task)

        elif c == 'j':
            win.addstr(row_num, 1, " ")  #j
            row_num+=1
            if row_num==page_max_rows+1:
                page = (page + 1) if page < last_page else 0
                draw()  
                row_num = 1
                page_max_rows = max_rows if not page==last_page else last_page_max_rows
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows+row_num-1]
            draw_note(task)

        elif c == 'h':
            win.addstr(row_num, 1, " ")  #j
            page = (page - 1) if page > 0 else last_page
            draw()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        elif c == 'l':
            win.addstr(row_num, 1, " ")  #j
            page = (page + 1) if page < last_page else 0
            draw()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        screen.move(0, size[1]-50)
        screen.clrtoeol()
        screen.addstr(0, size[1]-50, f"task num = {row_num}; char = {c}",
                      curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
            
        #size_current = screen.getmaxyx()
        #if size != size_current:
        #    size = size_current
        #    screen.addstr(0,0, f"screen size = x:{size[1]},y:{size[0]} max_rows = {max_rows}", curses.A_BOLD)

        time.sleep(.05)

if __name__ == "__main__":
    open_display_preview("not work")
