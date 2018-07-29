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
import os
import curses
from datetime import datetime, timedelta
import time
import json
import textwrap
from SolrClient import SolrClient
import requests
from config import SOLR_URI
from lmdb_p import *
import xml.etree.ElementTree as ET
import tempfile
from subprocess import call, run, PIPE
import threading

def check():
    while 1:
        c = remote_session.connection() #########
        try:
            c.execute("select 1")
        except (sqla_exc.ResourceClosedError, sqla_exc.StatementError) as e:
            print(f"{datetime.now()} - {e}")
        time.sleep(500)


remote_session = new_remote_session()
th = threading.Thread(target=check, daemon=True)
th.start()

#actions = {'n':'note', 't':'title', 's':'star', 'c':'completed', '\n':'select', 'q':None}
actions = {'\n':'select', 'q':None}
keymap = {258:'j', 259:'k', 260:'h', 261:'l'}
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
    if root[0][0].text == '0':
        return f"{task.id} success"
    else:
        return f"{task.id} failure"

def open_display_preview(query):
    # {'type':'context':'param':'not work'} or {'type':find':'param':'esp32'} or {'type':'recent':'param':'all'}
    screen = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(4, 15, -1)
    color_map = {'{blue}':3, '{red}':1, '{green}':2,'{white}':4}
    curses.curs_set(0) # cursor not visible
    curses.cbreak() # respond to keys without needing Enter
    curses.noecho()
    screen.keypad(True) #claims to catch arrow keys -- we'll see
    size = screen.getmaxyx()
    screen.nodelay(True)
    half_width = size[1]//2
    win = curses.newwin(size[0]-2, half_width-1, 1, 1)
    win2 = curses.newwin(size[0]-2, half_width-1, 1, half_width+1)
    win3 = curses.newwin(15, 30, 1, half_width-15)
    win4 = curses.newwin(20, 60, 1, half_width-30)

    page = 0
    row_num = 1
    max_chars_line = half_width - 5
    max_rows = size[0]-4
    
    type_ = query['type']
    if type_ == 'context':
    
        tasks = remote_session.query(Task).join(Context).\
                filter(Context.title==query['param'], Task.deleted==False).\
                       order_by(desc(Task.modified)).all()

    elif type_ == 'find':

        s0 = query['param'].split()
        s1 = 'title:' + ' OR title:'.join(s0)
        s2 = 'note:' + ' OR note:'.join(s0)
        s3 = 'tag:' + ' OR tag:'.join(s0)
        q = s1 + ' OR ' + s2 + ' OR ' + s3
        #print(q)
        result = solr.query(collection, {
                'q':q, 'rows':50, 'fl':['score', 'id', 'title', 'tag', 'star', 
                'context', 'completed'], 'sort':'score desc'})
        items = result.docs
        count = result.get_results_count()
        if count==0:
            return

        solr_ids = [x['id'] for x in items]
        tasks = remote_session.query(Task).filter(
                     Task.deleted==False, Task.id.in_(solr_ids))

        order_expressions = [(Task.id==i).desc() for i in solr_ids]
        tasks = tasks.order_by(*order_expressions).all()

    elif type_ == 'recent':    

        tasks = remote_session.query(Task).filter(Task.deleted==False)
        s = query['param']
        if not s or s == 'all':
            tasks = tasks.filter(
                    Task.modified > (datetime.now()
                    -timedelta(days=2))).order_by(desc(Task.modified)).all()

        elif s == 'created' or s == 'new':
            tasks = tasks.filter(
                    Task.created > (datetime.now()
                    -timedelta(days=2)).date()).order_by(desc(Task.modified)).all()

        elif s == 'completed':
            tasks = tasks.filter(
                    Task.completed > (datetime.now()
                    -timedelta(days=2)).date()).order_by(desc(Task.modified)).all()

        elif s == 'modified':
            tasks = tasks.filter(
                    and_(
                    Task.modified > (datetime.now()
                    -timedelta(days=2)),
                    ~(Task.created > (datetime.now()-
                    timedelta(days=2)).date())
                    )).order_by(desc(Task.modified)).all()

    last_page = len(tasks)//max_rows
    last_page_max_rows = len(tasks)%max_rows

    contexts = remote_session.query(Context).filter(Context.id!=1).all()
    contexts.sort(key=lambda c:str.lower(c.title))
    no_context = remote_session.query(Context).filter_by(id=1).one()
    contexts = [no_context] + contexts

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

    def draw_tasks():
        win.clear()
        win.box()
        page_tasks = tasks[max_rows*page:max_rows*(page+1)]
        n = 1
        for i,task in enumerate(page_tasks, page*max_rows+1):

            if n+2 == size[0]:
                break

            c = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL
            win.addstr(n, 2, f"{i}. {task.title[:max_chars_line-14]} ({task.id}){c}", font)  #(y,x)

            n+=1

        win.refresh() 

    def new():
        task = Task(priority=3, title='<new task>')
        task.startdate = datetime.today().date() 
        task.note = '<new task note>'
        if type_ == 'context':
            context = remote_session.query(Context).filter_by(title=query['param']).first()
            task.context = context

        remote_session.add(task)
        remote_session.commit()
        tasks.insert(0, task)
        last_page = len(tasks)//max_rows
        last_page_max_rows = len(tasks)%max_rows
        page = 0
        row_num = 1
        draw_tasks()
        draw_note(tasks[0])
        win.addstr(row_num, 1, ">")  #j
        win.refresh()

        solr_result = ''

    def draw_context():
        # would not have to draw every time if you didn't want to show what context the current task has
        #contexts = remote_session.query(Context).filter(Context.id!=1).all()
        #contexts.sort(key=lambda c:str.lower(c.title))
        #no_context = remote_session.query(Context).filter_by(id=1).one()
        #contexts = [no_context] + contexts
        task = tasks[(page*max_rows)+row_num-1]
        n = 2
        for i,context in enumerate(contexts, 1):
            font = curses.color_pair(2)|curses.A_BOLD if task.context == context else curses.A_NORMAL
            win3.addstr(n, 2, f"{i}. {context.title}", font)  #(y,x)
            n+=1
            
        win3.box()
        win3.refresh()

    def draw_info():
        '''Info on the currently selected task or for a task id that you provide'''
        task = tasks[(page*max_rows)+row_num-1]
        if task:
            text = "\n"
            text+= f": {task.id}\n"
            text+= f": {task.title[:50]}\n"
            text+= f": {task.priority}\n"
            text+= f": {task.star}\n"
            text+= f": {task.context.title}\n"
            text+= f": {', '.join(k.name for k in task.keywords)}\n"
            text+= f": {task.tag}\n"
            text+= f": {task.completed}\n"
            text+= f": {task.deleted}\n"
            text+= f": {task.created}\n"
            text+= f": {task.modified}\n"
            text+= f": {task.startdate}\n"
            text+= f": {task.note[:50] if task.note else ''}"
            win4.addstr(1, 1, text)  #(y,x)

        win4.box()
        win4.refresh()

    # draw the surrounding screen text
    screen.clear()
    screen.addstr(0,0,
                 f"Hello Steve. screen size=x:{size[1]},y:{size[0]} "\
                 f"max_rows={max_rows} last_page={last_page} "\
                 f"query={query['type']}-{query['param']}",
                 curses.A_BOLD)

    s = "n->edit [n]ote t->edit [t]itle ENTER-> select item i->[i]nfo  "\
        "q->[q]uit without selecting item d->[d]elete j->page down k->page up "\
        "h->page left l->page right"

    if len(s) > size[1]:
        s = s[:size[1]-1]
    screen.addstr(size[0]-1, 0, s, curses.color_pair(3)|curses.A_BOLD)
    screen.refresh()

    draw_tasks()
    draw_note(tasks[0])
    win.addstr(row_num, 1, ">")  #j
    win.refresh()

    solr_result = ''
    accum = [] 
    command = None 
    page_max_rows = max_rows if last_page else last_page_max_rows
    msg = ''
    while 1:
        n = screen.getch()
        if n == -1:
            continue

        c = keymap.get(n, chr(n))

        if command:
            if c == '\n':
                action = ''.join(accum)
                accum = []
                c = ''
                #getattr(open_display_preview, action)() #can't do this on functions
                if 'new'.startswith(action):
                    command = None
                    new()
                elif 'context'.startswith(action):
                    draw_context() # need to redraw to show the current task's context
                    command = 'context'
                elif 'open'.startswith(action):
                    draw_context() # need to redraw to show the current task's context
                    command = 'open'
                elif action.isdigit():
                    if command == 'context':
                        task = tasks[(page*max_rows)+row_num-1]
                        task.context = contexts[int(action)-1]
                        remote_session.commit()
                        screen.redrawwin()
                        screen.refresh()
                        win.redrawwin()
                        win.refresh()
                        win2.redrawwin()
                        win2.refresh()
                        command = None
                        solr_result = update_solr(task)
                        msg = f"{task.id} was given the context {context.title} and solr was updated {solr_result}"
                    elif command == 'open':
                        context = contexts[int(action)-1]
                        open_display_preview({'type':'context', 'param':context.title})
                        command = None
                        #curses.doupdate() # am sure it's my fault but this is causing screen to overwrite windows.
                    else:
                        command = None # if someone types :25 - nothing will happen but won't be stuck
                elif action == 'test':
                    command = None 
                    win3.redrawwin()
                    win3.refresh()
                # assumes anything else is a find string 
                # means you can't find 'new' or find 'context' because
                # they'll match specific commands - this could be fixed
                else:
                    command = None 
                    open_display_preview({'type':'find', 'param':action})
            else:
                accum.append(c)
        elif c == ':':  #in [':','/']: 
            command = True
            
        #if c in ['s', 'n', 't', 'c', '\n', 'q']:
        elif n == 27:
            screen.redrawwin()
            screen.refresh()
            win.redrawwin()
            win.refresh()
            win2.redrawwin()
            win2.refresh()
            command = None
            c = 'E'
        elif c in ['\n', 'q']:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            task = tasks[(page*max_rows)+row_num-1]
            call(['reset'])
            return {'action':actions[c], 'task_id':task.id}

        elif c == 'i':
            draw_info()

        # edit note in vim
        elif c == 'n':
            task = tasks[(page*max_rows)+row_num-1]
            note = task.note if task.note else ''  # if you want to set up the file somehow
            EDITOR = os.environ.get('EDITOR','vim') #that easy!

            note = task.note if task.note else ''  # if you want to set up the file somehow

            with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
                tf.write(note.encode("utf-8"))
                tf.flush()
                call([EDITOR, tf.name])

                screen.keypad(True)

                # editing in vim and return here
                tf.seek(0)
                new_note = tf.read().decode("utf-8")   # self.task.note =

            if new_note != note:
                task.note = new_note
                draw_note(task)
                remote_session.commit()
                solr_result = update_solr(task)

        # edit title in vim
        elif c == 't':
            task = tasks[(page*max_rows)+row_num-1]
            title = task.title

            EDITOR = os.environ.get('EDITOR','vim') 

            with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
                tf.write(title.encode("utf-8"))
                tf.flush()

                # call editor (vim)
                call([EDITOR, tf.name])


                # editing in vim and return here
                tf.seek(0)
                new_title = tf.read().decode("utf-8").strip()   # self.task.note =

            if new_title != title:
                task.title = new_title
                comp = ' [c]' if task.completed else ''
                font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL

                # the following refresh redraw update sequence seems to work
                # ? reason needed is that we are trying to update one line of win
                # and that seems to cause problems with other windows
                # if title isn't updated no need to do any of this so that's why under the 'if'
                win.redrawwin() # this is needed or you don't get a redraw until you 'scroll' with i,j
                win.move(row_num, 2)
                win.clrtoeol()
                win.addstr(row_num, 2, 
                   f"{page*max_rows+row_num}. {task.title[:max_chars_line-7]}{comp}",
                   font)  #(y,x)
                win.addch(row_num, half_width-2, curses.ACS_VLINE) 
                win.noutrefresh() # update data structure but not screen
                win2.redrawwin() # this is needed even though win2 isn't touched
                screen.redrawln(0,1)
                screen.redrawln(size[0]-1, size[0])
                screen.keypad(True) # makes keys like arrow into one character (v. sequence of three)
                curses.curs_set(0) # cursor not visible
                curses.doupdate() # update all physical windows
                remote_session.commit()
                solr_result = update_solr(task)

        # toggle star
        elif c == 's':
            task = tasks[(page*max_rows)+row_num-1]
            task.star = not task.star
            comp = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL
            win.move(row_num, 2)
            win.clrtoeol()
            win.addstr(row_num, 2, 
                f"{page*max_rows+row_num}. {task.title[:max_chars_line-7]}{comp}",
                font)  #(y,x)
            win.addch(row_num, half_width-2, curses.ACS_VLINE) 
            win.refresh()
            remote_session.commit()
            solr_result = update_solr(task)
            msg = f"{task.id} is {'starred' if task.star else 'is not starred'} and {solr_result} updated in solr"

        # toggle completed
        elif c == 'c':
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
            win.addstr(row_num, 2, 
              f"{page*max_rows+row_num}. {task.title[:max_chars_line-7]}{comp}", font) #(y,x)

            # unfortunately the clrtoeol wipes out the vertical box line character
            win.addch(row_num, half_width-2, curses.ACS_VLINE) 
            win.refresh()
            remote_session.commit()
            solr_result = update_solr(task)
            msg = f"{task.id} is {'completed' if task.completed else 'is not completed'} and {solr_result} updated in solr"

        elif c == 'd':
            task = tasks[(page*max_rows)+row_num-1]
            task.deleted = True
            remote_session.commit()
            del tasks[(page*max_rows)+row_num-1]

            last_page = len(tasks)//max_rows
            last_page_max_rows = len(tasks)%max_rows
            page = 0
            row_num = 1
            draw_tasks()
            draw_note(tasks[0])
            win.addstr(row_num, 1, ">")  #j
            win.refresh()

            solr_result = ''
            msg = f"{task.id} was marked for deletion but solr was not updated"

        # using "vim keys" for navigation
        elif c == 'k':
            win.addstr(row_num, 1, " ")  #k
            row_num-=1
            if row_num==0:
                page = (page - 1) if page > 0 else last_page
                draw_tasks()  
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
                draw_tasks()  
                row_num = 1
                page_max_rows = max_rows if not page==last_page else last_page_max_rows
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows+row_num-1]
            draw_note(task)

        elif c == 'h':
            win.addstr(row_num, 1, " ")  #j
            page = (page - 1) if page > 0 else last_page
            draw_tasks()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        elif c == 'l':
            win.addstr(row_num, 1, " ")  #j
            page = (page + 1) if page < last_page else 0
            draw_tasks()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        screen.move(0, 0)
        screen.clrtoeol()
        screen.addstr(0,0, msg,  curses.A_BOLD)
        screen.addstr(0, size[1]-50,
                f"page:{page} row num:{row_num} char:{c} command {''.join(accum)} solr:{solr_result}",
                curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
            
        time.sleep(.05)

if __name__ == "__main__":
    open_display_preview({'type':'context', 'param':'todo'})
