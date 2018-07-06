#!bin/python
'''
python3 script: displays infoboxes with key determing which box is displayed
See below for mapping from pos (int) to topic of infobox
'''
import sys
import curses
import json
import textwrap
from datetime import datetime
import time
import re
import argparse
from lmdb_p import *

parser = argparse.ArgumentParser(description='Process tasks.')
parser.add_argument('task_ids', metavar='N', type=int, nargs='+',
                    help='an integer that represents the task id`')
args = parser.parse_args()
print(args.task_ids)  #[234, 128, 712, 3456]

#tasks = remote_session.query(Task).join(Context).filter(Context.title=='test')
tasks = []
for task_id in args.task_ids:
    task = remote_session.query(Task).get(task_id)
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

#boxes = {}
#for b in info_boxes:
#    boxes[b] = curses.newwin(size[0]-2, size[1]-1, 1, 1)
#    boxes[b].box()
#    boxes[b].addstr(2, 2, f"No content received yet for {b}", 
#                    curses.color_pair(3)|curses.A_BOLD) 

win = curses.newwin(size[0]-2, size[1]-1, 1, 1)
win.box()
win.addstr(2,2, "No content yet", curses.color_pair(3)|curses.A_BOLD)

task_num = 0
max_chars_line = size[1] - 10
#phrases = [(u'{}', u'the holy grail '), (u'{blue}', u' is very nice '),...
#...(u'{red}', u' is it?')]
def get_phrases(line, start='{}'):

    if line.find('{') == -1:
        #print("phrases =", [(start, line)])
        return [(start, line)]

    if line[0]!='{':
        line = start+line

    line = line+'{}'

    z = re.finditer(r'{(.*?)}', line)
    s = [[m.group(), m.span()] for m in z]
    if not s:
        return [('{}', line)]
    phrases = []
    for j in range(len(s)-1):
        phrases.append((s[j][0],line[s[j][1][1]:s[j+1][1][0]]))
    return phrases

def draw(task_num):
    #global selected_pos
    win.clear()
    win.box()
    task = tasks[task_num]

    header = task.title
    note = task.note
    paras = note.splitlines()
    lines = textwrap.wrap(note, max_chars_line)
    win.addstr(1, 1, header, curses.A_BOLD)

    n = 2

    #for l,line in enumerate(lines):

    #    if n+2 == size[0]:
    #        break

    #    font = curses.A_NORMAL

    #    if l:
    #        phrases = get_phrases(line, phrase[0])
    #    else:
    #        phrases = get_phrases(line)

    #    xx = 0
    #    for phrase in phrases:
    #        try:
    #            win.addstr(n, 1 + xx, phrase[1],  #(y,x)
    #              curses.color_pair(color_map.get(phrase[0], 4))|font) 
    #        except Exception as e:
    #             pass
    #        xx+= len(phrase[1])

    #    n+=1

    for para in paras:
        for line in textwrap.wrap(para, max_chars_line):

            if n+2 == size[0]:
                break

            try:
                win.addstr(n, 1, line)  #(y,x)
            except Exception as e:
                 pass

            n+=1
    # item is the last item and if the last item is white space n gets
    # incremented unnecessarily and this 'un'increments it
    #if not item.strip():
    #    n-=1

    # put time in upper right of box
    t = datetime.now().strftime("%I:%M %p")
    t = t[1:] if t[0] == '0' else t
    t = t[:-2] + t[-2:].lower()
    win.addstr(1, size[1]-10, t, curses.color_pair(3)|curses.A_BOLD) 
    win.refresh()

    #if pos==selected_pos:
    #    win.refresh()
    #elif pos==8: #switch to lyrics info box if new lyrics show up
    #    selected_pos = 8
    #    win.refresh()
    #    screen.move(0, size[1]-8)
    #    screen.clrtoeol()
    #    screen.addstr(0, size[1]-8, "key=8", curses.color_pair(3)|curses.A_BOLD)
    #    screen.refresh()

screen.clear()
screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]}", curses.A_BOLD)
#screen.addstr(6, 2, f"No content received yet for {selected_pos}", 
#                curses.color_pair(3)|curses.A_BOLD) 
s = "0:temp 1:news 2:quote 3:todos 4:gmail 5:sales forecast 6:blank 7:artist image 8:lyrics 9:track info"
if len(s) > size[1]:
    s = s[:size[1]-1]
screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
screen.refresh()

while 1:
    #client.loop(timeout = 0.25) #was 1.0
    redraw = False
    n = screen.getch()
    if n != -1:
        c = chr(n)
        if c.isnumeric():
            task_num = int(c)
            redraw = True
        elif c == 'h':
            task_num = task_num-1 if task_num > 0 else len(tasks)-1
            c = task_num
            redraw = True
        elif c == 'l':
            task_num = task_num+1 if task_num < len(tasks)-1  else 0
            c = task_num
            redraw = True
        elif c == 'q':
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            sys.exit()
        if redraw:
            draw(task_num)
            win.redrawwin()
            win.refresh()

        screen.move(0, size[1]-8)
        screen.clrtoeol()
        screen.addstr(0, size[1]-8, f"key={c}", curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
        
    size_current = screen.getmaxyx()
    if size != size_current:
        size = size_current
        screen.addstr(0,0, f"Hello Steve. screen size = x:{size[1]},y:{size[0]}", curses.A_BOLD)
    time.sleep(.1)
