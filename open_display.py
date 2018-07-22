#!bin/python
'''
python3 script: displays infoboxes with key determing which box is displayed
See below for mapping from pos (int) to topic of infobox
'''
import sys
import curses
import textwrap
from datetime import datetime
import time
import json
import argparse
from lmdb_p import *

parser = argparse.ArgumentParser()
parser.add_argument('context')
args = parser.parse_args()
c_title = args.context
tasks = []
tasks = remote_session.query(Task).join(Context).\
            filter(Context.title==c_title, Task.deleted==False).\
                   order_by(desc(Task.modified)).all()



screen = curses.initscr()
curses.start_color()
curses.use_default_colors()
curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_WHITE)
curses.init_pair(4, 15, -1)
color_map = {'{blue}':3, '{red}':1, '{green}':2,'{white}':4}
curses.curs_set(0)
curses.cbreak() # respond to keys without needing Enter
curses.noecho()
size = screen.getmaxyx()
screen.nodelay(True)
font = curses.A_NORMAL

win = curses.newwin(size[0]-2, size[1]-1, 1, 1)

#page_tasks = tasks[page*9:page*9+9]
page = 0
row_num = 1
max_chars_line = size[1] - 10
max_rows = size[0]-4
last_page = len(tasks)//max_rows

def draw():
    win.clear()
    win.box()
    page_tasks = tasks[max_rows*page:max_rows*(page+1)]
    n = 1
    for i,task in enumerate(page_tasks, page*max_rows+1):

        if n+2 == size[0]:
            break

        try:
            win.addstr(n, 2, f"{i}. {task.title}")  #(y,x)
        except Exception as e:
             pass

        n+=1

    win.refresh() 

screen.clear()
screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]} max_rows = {max_rows} ", curses.A_BOLD)

s = "h:move left l:move right n:edit [n]ote t:edit [t]itle q:quit and return without editing"
if len(s) > size[1]:
    s = s[:size[1]-1]
screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
screen.refresh()

draw()
win.addstr(row_num, 1, ">")  #j
win.refresh()
accum = []
while 1:
    n = screen.getch()
    if n != -1:
        if n == 10:
            if accum:
                accum.reverse()
                row_num = sum((10**n)*accum[n] for n in range(len(accum)))

                if row_num < len(tasks):
                    draw(row_num)
                    task = tasks[row_num]
                accum = []
            else:
                curses.nocbreak()
                screen.keypad(False)
                curses.echo()
                curses.endwin()
                sys.stderr.write(json.dumps({'action':'ENTER', 'task_id':task.id}))
                sys.exit()
            
        c = chr(n) if n != 10 else '/'
        if c in ['q', 'n', 't']:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            task = tasks[row_num]

            if c == 'n':
                sys.stderr.write(json.dumps({'action':'note', 'task_id':task.id}))
            elif c == 't':
                sys.stderr.write(json.dumps({'action':'title', 'task_id':task.id}))

            sys.exit()

        if c.isnumeric():
            accum.append(int(c))
        elif c == 'k':
            win.addstr(row_num, 1, " ")  #k
            row_num-=1
            if row_num==0:
                page = (page - 1) if page > 0 else last_page
                row_num = max_rows
                draw()  
            
            win.addstr(row_num, 1, ">")  #k
            win.refresh()
        elif c == 'j':
            win.addstr(row_num, 1, " ")  #j
            row_num+=1
            if row_num==max_rows+1:
                page = (page + 1) if page < last_page else 0
                row_num = 1
                draw()  
            win.addstr(row_num, 1, ">")  #j
            win.refresh()

        elif c == 'h':
                page = (page - 1) if page > 0 else last_page
                draw()  
                win.addstr(row_num, 1, ">")  #j
                win.refresh()

        elif c == 'l':
            page = (page + 1) if page < last_page else 0
            draw()  
            win.addstr(row_num, 1, ">")  #j
            win.refresh()



        screen.move(0, size[1]-50)
        screen.clrtoeol()
        screen.addstr(0, size[1]-50, f"task num = {row_num}; char = {c}",
                      curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
        
    size_current = screen.getmaxyx()
    if size != size_current:
        size = size_current
        screen.addstr(0,0, f"screen size = x:{size[1]},y:{size[0]} max_rows = {max_rows}", curses.A_BOLD)
    time.sleep(.05)
