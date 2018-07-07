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

parser = argparse.ArgumentParser(description='Process tasks.')
parser.add_argument('task_ids', metavar='N', type=int, nargs='+',
                    help='an integer that represents the task id`')
args = parser.parse_args()
print(args.task_ids)  #[234, 128, 712, 3456]

tasks = []
for task_id in args.task_ids:
    task = remote_session.query(Task).get(task_id)
    if task:
        tasks.append(task)

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

task_num = 0
max_chars_line = size[1] - 10

def draw(task_num):
    win.clear()
    win.box()
    task = tasks[task_num]

    header = task.title
    note = task.note if task.note else ""
    paras = note.splitlines()
    lines = textwrap.wrap(note, max_chars_line)
    win.addstr(1, 1, header, curses.A_BOLD)

    n = 2

    for para in paras:
        for line in textwrap.wrap(para, max_chars_line):

            if n+2 == size[0]:
                break

            try:
                win.addstr(n, 1, line)  #(y,x)
            except Exception as e:
                 pass

            n+=1

    win.refresh() #? needed but not tested

screen.clear()
screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]}", curses.A_BOLD)

s = "h:move left l:move right n:edit [n]ote t:edit [t]itle q:quit and return without editing"
if len(s) > size[1]:
    s = s[:size[1]-1]
screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
screen.refresh()

draw(task_num)

while 1:
    redraw = False
    n = screen.getch()
    if n != -1:
        c = chr(n)
        if c in ['q', 'n', 't']:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            task = tasks[task_num]

            if c == 'n':
                sys.stderr.write(json.dumps({'action':'note', 'task_id':task.id}))
            elif c == 't':
                sys.stderr.write(json.dumps({'action':'title', 'task_id':task.id}))

            sys.exit()

        if c.isnumeric():
            task_num = int(c)
            if task_num < len(tasks):
                draw(task_num)
        elif c == 'h':
            task_num = task_num-1 if task_num > 0 else len(tasks)-1
            c = task_num
            draw(task_num)
        elif c == 'l':
            task_num = task_num+1 if task_num < len(tasks)-1 else 0
            c = task_num
            draw(task_num)

        screen.move(0, size[1]-8)
        screen.clrtoeol()
        screen.addstr(0, size[1]-8, f"key/task num ={c}", curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
        
    size_current = screen.getmaxyx()
    if size != size_current:
        size = size_current
        screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]}", curses.A_BOLD)
    time.sleep(.05)
