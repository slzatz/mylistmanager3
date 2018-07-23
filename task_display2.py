#!bin/python
'''
A version of task_display that doesn't require calling a separate script but just imports this script
Runs curses-based script until it returns and tears everything down so cmd can continue running
'''
import sys
import curses
import textwrap
from datetime import datetime
import time
import json
import argparse
from lmdb_p import *

actions = {'n':'note', 't':'title', 's':'select'}
keys = {'B':'j', 'A':'k', 'C':'l', 'D':'h'}

def task_display2(tasks):
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

    task_num = 1 ####
    max_chars_line = size[1] - 10

    screen.clear()
    screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]}", curses.A_BOLD)

    s = "h:move left l:move right n:edit [n]ote t:edit [t]itle q:quit and return without editing"
    if len(s) > size[1]:
        s = s[:size[1]-1]
    screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
    screen.refresh()

    def draw(task_num):
        win.clear()
        win.box()
        #task = tasks[task_num]
        task = tasks[task_num-1] #####

        win.addstr(1, 1, task.title, curses.A_BOLD)
        note = task.note if task.note else ""
        paras = note.splitlines()

        n = 2

        for para in paras:
            # this handles blank lines
            if not para:
                n+=1
                continue

            for line in textwrap.wrap(para, max_chars_line):

                if n+2 == size[0]:
                    break

                try:
                    win.addstr(n, 1, line)  #(y,x)
                except Exception as e:
                     pass

                n+=1

        win.refresh() #? needed but not tested

    draw(task_num)
    accum = []
    arrow = False
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
        elif c == '\n': #10:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            return

        if c in ['s', 'n', 't']:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            task = tasks[task_num-1]
            return {'action':actions[c], 'task_id':task.id}

        elif c == 'k':
            task_num = task_num-1 if task_num > 1 else len(tasks) #####
            draw(task_num)

        elif c == 'j':
            task_num = task_num+1 if task_num < len(tasks) else 1 #####
            draw(task_num)

        screen.move(0, size[1]-50)
        screen.clrtoeol()
        screen.addstr(0, size[1]-50, f"task num = {task_num}; char = {c}",
                      curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
            
        time.sleep(.05)
