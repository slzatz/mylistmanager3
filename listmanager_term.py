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
color pair 0 is hard-wired to white on black and on my terminal is different than curses.COLOR_WHITE, curese.COLOR_BLACK

0:black, 1:red, 2:green, 3:yellow, 4:blue, 5:magenta, 6:cyan, and 7:white

Other ways to change text:
A_BLINK	Blinking text
A_BOLD	Extra bright or bold text
A_DIM	Half bright text
A_REVERSE	Reverse-video text
A_STANDOUT	The best highlighting mode available
A_UNDERLINE	Underlined text

if I don't want to turn this into a class can use nonlocal to access any variables
changed by inner functions
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
from subprocess import call
import threading
from update_solr import update_solr

def now():
    return datetime.now().isoformat(' ').split('.')[0]

def check():
    while 1:
        c = remote_session.connection() 
        try:
            c.execute("select 1")
        except (sqla_exc.ResourceClosedError, sqla_exc.StatementError) as e:
            print(f"{datetime.now()} - {e}")
        time.sleep(500)


remote_session = new_remote_session()
th = threading.Thread(target=check, daemon=True)
th.start()

#actions = {'n':'note', 't':'title', 's':'star', 'c':'completed', '\n':'select', 'q':None}
#actions = {'\n':'select', 'q':None}
keymap = {258:'j', 259:'k', 260:'h', 261:'l'}
solr = SolrClient(SOLR_URI + '/solr')
collection = 'listmanager'

def open_display_preview(query, hide_completed=False, hide_deleted=True, sort='modified'):
    # {'type':'context':'param':'not work'} or {'type':find':'param':'esp32'} 
    # or {'type':'recent':'param':'all'}
    screen = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.curs_set(0) # cursor not visible
    curses.cbreak() # respond to keys without needing Enter
    curses.noecho()
    screen.keypad(True) #claims to catch arrow keys -- we'll see
    size = screen.getmaxyx()
    screen.nodelay(True)
    half_width = size[1]//2
    task_win = curses.newwin(size[0]-1, half_width-1, 1, 1)
    note_win = curses.newwin(size[0]-1, half_width-1, 1, half_width+1)
    context_win = curses.newwin(15, 30, 1, half_width-15)
    info_win = curses.newwin(22, 60, 1, half_width-30)
    help_win = curses.newwin(34, 34, 1, half_width-15)
    keywords_win = curses.newwin(50, 30, 1, half_width-15)
    log_win = curses.newwin(size[0]-1, half_width+20, 1, -10+half_width//2)

    page = 0
    row_num = 1
    max_chars_line = half_width - 5
    max_rows = size[0]-3

    type_ = query['type']
    if type_ == 'context':
    
        tasks = remote_session.query(Task).join(Context).\
                filter(Context.title==query['param']) #.\
                       #order_by(desc(Task.modified))
                #filter(Context.title==query['param'], Task.deleted==False).\

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
                     Task.id.in_(solr_ids))
                     #Task.deleted==False, Task.id.in_(solr_ids))

        if not sort:
            order_expressions = [(Task.id==i).desc() for i in solr_ids]
            tasks = tasks.order_by(*order_expressions)

    elif type_ == 'recent':    

        tasks = remote_session.query(Task).filter(Task.deleted==False)
        s = query['param']
        if not s or s == 'all':
            tasks = tasks.filter(
                    Task.modified > (datetime.now()
                    -timedelta(days=2))).order_by(desc(Task.modified))

        elif s == 'created' or s == 'new':
            tasks = tasks.filter(
                    Task.created > (datetime.now()
                    -timedelta(days=2)).date()).order_by(desc(Task.modified))

        elif s == 'completed':
            tasks = tasks.filter(
                    Task.completed > (datetime.now()
                    -timedelta(days=2)).date()).order_by(desc(Task.modified))

        elif s == 'modified':
            tasks = tasks.filter(
                    and_(
                    Task.modified > (datetime.now()
                    -timedelta(days=2)),
                    ~(Task.created > (datetime.now()-
                    timedelta(days=2)).date())
                    )).order_by(desc(Task.modified))

    if hide_completed:
        tasks = tasks.filter(Task.completed==None)
    if hide_deleted:
        tasks = tasks.filter(Task.deleted==False)
    if sort:
        tasks = tasks.order_by(desc(getattr(Task, sort)))
    tasks = tasks.all()
    last_page = len(tasks)//max_rows
    last_page_max_rows = len(tasks)%max_rows

    contexts = remote_session.query(Context).filter(Context.id!=1).all()
    contexts.sort(key=lambda c:str.lower(c.title))
    no_context = remote_session.query(Context).filter_by(id=1).one()
    contexts = [no_context] + contexts

    def show_note(task):
        note_win.clear()
        note_win.box()

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
                    note_win.addstr(n, 3, line)  #(y,x)
                except Exception as e:
                     pass

                n+=1

        note_win.refresh()

    def redraw_task():
            cp = 1 if task.deleted else 4 if task.completed else 0
            font = curses.color_pair(cp)|curses.A_BOLD if task.star else \
                   curses.color_pair(cp)
            task_win.move(row_num, 2)
            task_win.clrtoeol()
            task_win.addstr(row_num, 2, 
                  #f"{page*max_rows+row_num}. {task.title[:max_chars_line-14]}"\
                  f"{task.title[:max_chars_line-6]}"\
                  f"({task.id})", font)  

            # the clrtoeol wipes out the vertical box line character
            task_win.addch(row_num, half_width-2, curses.ACS_VLINE) 
            task_win.refresh()
         
    def show_tasks():
        task_win.clear()
        task_win.box()
        page_tasks = tasks[max_rows*page:max_rows*(page+1)]
        n = 1
        for i,task in enumerate(page_tasks, page*max_rows+1):

            if n > max_rows:
                break

            cp = 1 if task.deleted else 4 if task.completed else 0
            font = curses.color_pair(cp)|curses.A_BOLD if task.star else \
                   curses.color_pair(cp)
            task_win.addstr(n, 2,
              #f"{i}. {task.title[:max_chars_line-14]} ({task.id}){c}",
              #f"{i}. {task.title[:max_chars_line-14]} ({task.id})",
              f"{task.title[:max_chars_line-6]} ({task.id})",
              font)  #(y,x)

            n+=1

        task_win.refresh() 

    def show_context():
        context_win.addstr(2, 2, "0. Do nothing")
        n = 3
        for i,context in enumerate(contexts, 1):
            font = curses.color_pair(2)|curses.A_BOLD if task.context == context else curses.A_NORMAL
            context_win.addstr(n, 2, f"{i}. {context.title}", font)  #(y,x)
            n+=1
            
        context_win.box()
        context_win.refresh()

    def show_info():
        '''Info on the currently selected task''' 

        task = tasks[(page*max_rows)+row_num-1]
        if task:
            # space in front of lines necessary to indent
            s = f"id: {task.id}\n"
            s += f" title: {task.title[:50]}\n"
            s += f" priority: {task.priority}\n"
            s += f" star: {task.star}\n"
            s += f" context: {task.context.title}\n"
            s += f" keywords: {', '.join(k.name for k in task.keywords)}\n"
            s += f" tag: {task.tag}\n"
            s += f" completed: {task.completed}\n"
            s += f" deleted: {task.deleted}\n"
            s += f" created: {task.created}\n"
            s += f" modified: {task.modified}\n"
            s += f" startdate: {task.startdate}\n"
            s += f" note: {task.note[:50] if task.note else ''}"
            info_win.addstr(1, 1, "Item Info",curses.color_pair(2)|curses.A_BOLD)
            info_win.addstr(3, 1, s)  #(y,x)
            info_win.addstr(20, 1, "ESCAPE to close", curses.color_pair(3))  #(y,x)

        info_win.box()
        info_win.refresh()
        return info_win

    def show_keywords():
        # Believe it is better to just look at keywords with a Context
        keywords = remote_session.query(Keyword).join(
            TaskKeyword,Task,Context).filter(
            Context.title==task.context.title).all()
        keywords.sort(key=lambda x:str.lower(x.name))

        #n = 2
        keywords_win.addstr(2, 2, "0. Do nothing")
        n = 3
        for i,keyword in enumerate(keywords, 1):
            if n > 45:
                break
            font = curses.color_pair(2)|curses.A_BOLD if keyword in task.keywords else curses.A_NORMAL
            #font = curses.A_NORMAL
            keywords_win.addstr(n, 2, f"{i}. {keyword.name}", font)  #(y,x)
            n+=1
            
        keywords_win.box()
        keywords_win.refresh()
        return keywords

    def show_log():
        log_win.clear()
        log_win.box()

        paras = log.splitlines()

        n = 1

        for para in paras:
            # this handles blank lines
            if not para:
                n+=1
                continue

            #for line in textwrap.wrap(para, max_chars_line):
            for line in textwrap.wrap(para, 60):

                if n > max_rows:
                    break

                try:
                    log_win.addstr(n, 3, line)  #(y,x)
                except Exception as e:
                     pass

                n+=1

        log_win.refresh()
        return log_win

    def show_help():
        s = "n->edit [n]ote\n t->edit [t]itle\n x->toggle completed\n"\
        " w->key[w]ords\n c->[c]ontext\n d->[d]elete\n i->[i]nfo\n\n"\
        " N->[N]ew item\n\n"\
        " j->page down\n k->page up\n h->page left\n l->page right"

        help_win.addstr(1, 1, "Key map",curses.color_pair(2)|curses.A_BOLD)
        help_win.addstr(3, 1, s)  #(y,x)
        help_win.addstr(18, 1, "Commands\n",curses.color_pair(2)|curses.A_BOLD)
        s = ":help->show this window\n :open [context]\n :solr->update solr db\n :log->show log\n :find [search string]\n"\
            " :recent->created or modified\n :refresh->refresh display\n :show/hide [completed|deleted]\n :sort [modified|startdate]\n :quit->duh"
        help_win.addstr(20, 1, s)  #(y,x)
        help_win.addstr(32, 1, "ESCAPE to close", curses.color_pair(3))  #(y,x)
        help_win.box()
        help_win.refresh()
        return help_win

    def redraw(w):
        if w:
            w.erase()
            w.noutrefresh()
        task_win.redrawwin()
        task_win.noutrefresh()
        note_win.redrawwin()
        note_win.noutrefresh()
        curses.doupdate()
        
    # draw the surrounding screen text
    screen.clear()
    screen.addstr(0,0,
                 f"screen=x:{size[1]},y:{size[0]} "\
                 f"max_rows={max_rows} last_page={last_page} "\
                 f"q={query['type']}-{query['param']} "\
                 f"sort={sort} hide_c={hide_completed} hide_d={hide_deleted}",
                 curses.A_BOLD)

    screen.refresh()

    show_tasks()
    task = tasks[0]
    show_note(task)
    task_win.addstr(row_num, 1, ">")  
    task_win.refresh()

    accum = [] 
    command = None 
    page_max_rows = max_rows if last_page else last_page_max_rows
    msg = ''
    log = ''
    cur_win = None
    run = True
    #while 1:
    while run:
        n = screen.getch()
        if n == -1:
            continue

        c = keymap.get(n, chr(n))

        if command:
            if c == '\n':
                chars = ''.join(accum)
                accum = []
                c = '' # is necessary or you try to print return
                if chars.isdigit():
                    if command == 'context':
                        #task = tasks[(page*max_rows)+row_num-1]
                        p = int(chars) - 1
                        if p < 0 or p > len(contexts):
                            msg = "do nothing"
                        else:
                            task.context = contexts[p]
                            remote_session.commit()
                            msg = f"{task.id} new context = {task.context.title}"
                            log = f"{now()}: {msg}\n" + log

                        redraw(context_win)
                        command = None
                    elif command == 'open':
                        p = int(chars) - 1
                        if p < 0 or p > len(contexts):
                            msg = "do nothing"
                            redraw(context_win)
                            command = None
                        else:
                            context = contexts[p]
                            command = None
                            run = False
                            open_display_preview({'type':'context', 'param':context.title})

                    elif command == 'keywords':
                        p = int(chars) - 1
                        if p < 0 or p > len(keywords):
                            msg = "do nothing"
                        else:
                            keyword = keywords[p]
                            if keyword in task.keywords:
                                msg = f"{keyword.name} already attached to {task.title}!"
                            else:
                                taskkeyword = TaskKeyword(task, keyword)
                                remote_session.add(taskkeyword)
                                task.tag = ','.join(kwn.name for kwn in task.keywords) #######
                                remote_session.commit()
                                msg = f"{task.id} given keyword = {keyword.name}"
                                log = f"{now()}: {msg}\n" + log

                        redraw(keywords_win)
                        command = None
                    else:
                        command = None
                        msg = f"Typing '{chars}' won't do anything"

                elif "help".startswith(chars):
                    cur_win = show_help()
                    command = None
                elif "solr".startswith(chars):
                    result,num_tasks = update_solr()
                    log =  result + log
                    msg = f"{num_tasks+1} updated in solr"
                    command = None
                # may want to use chars.split so can go open work and default to showing list
                elif "open".startswith(chars):
                    show_context() # need to redraw to show the current task's context
                    command = 'open'
                elif "log".startswith(chars):
                    command = None
                    curwin = show_log()
                elif "find".startswith(chars.split(' ', 1)[0]):
                    #command = None
                    run = False
                    open_display_preview({'type':'find', 'param':chars.split(' ', 1)[1]}, sort=None)
                elif "refresh".startswith(chars):
                    #command = None
                    run = False
                    open_display_preview({'type':type_, 'param':query['param']})
                elif "recent".startswith(chars):
                    run = False
                    open_display_preview({'type':'recent', 'param':'all'})
                elif "sort".startswith(chars.split(' ', 1)[0]):
                    run = False
                    if "modified".startswith(chars.split(' ', 1)[1]):
                        open_display_preview({'type':type_, 'param':query['param']},
                                          sort = 'modified')
                    else:
                        open_display_preview({'type':type_, 'param':query['param']},
                                          sort = 'startdate')
                        
                elif "hide".startswith(chars.split(' ', 1)[0]):
                    run = False
                    if "completed".startswith(chars.split(' ', 1)[1]):
                        open_display_preview({'type':type_, 'param':query['param']},
                                         hide_completed=True)
                    else:
                        open_display_preview({'type':type_, 'param':query['param']},
                                         hide_deleted=True)
                elif "show".startswith(chars.split(' ', 1)[0]):
                    run = False
                    if "completed".startswith(chars.split(' ', 1)[1]):
                        open_display_preview({'type':type_, 'param':query['param']},
                                         hide_completed=False)
                    else:
                        open_display_preview({'type':type_, 'param':query['param']},
                                         hide_deleted=False)
                elif "quit".startswith(chars):
                    run = False
                else:
                    command = None
                    msg = "I don't know what you typed"
            else:
                accum.append(c)

        elif c == ':': 
            command = True
            
        elif n == 27: #escape
            redraw(cur_win)
            command = None
            cur_win = None
            c = 'E'

        elif c == 'c':
            show_context() # need to redraw to show the current task's context
            command = 'context'

        elif c == 'w':
            keywords = show_keywords()
            command = 'keywords'

        elif c == 'i':
            cur_win = show_info()

        elif c == 'N':
            task = Task(priority=3, title='<new task>')
            task.startdate = datetime.today().date() 
            task.note = '<new task note>'
            if type_ == 'context':
                context = remote_session.query(Context).filter_by(
                          title=query['param']).first()
                task.context = context

            remote_session.add(task)
            remote_session.commit()
            tasks.insert(0, task)
            task_win.addstr(row_num, 1, " ")
            last_page = len(tasks)//max_rows
            last_page_max_rows = len(tasks)%max_rows
            page = 0
            row_num = 1
            show_tasks()
            show_note(tasks[0])
            task_win.addstr(row_num, 1, ">")  #j
            task_win.refresh()
            log = f"task {task.id} added" + log

        # edit note in vim
        elif c == 'n':
            note = task.note if task.note else ''  # if you want to set up the file somehow
            EDITOR = os.environ.get('EDITOR','vim') #that easy!

            note = task.note if task.note else ''  # if you want to set up the file somehow

            with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
                tf.write(note.encode("utf-8"))
                tf.flush()

                #curses.savetty()

                call([EDITOR, tf.name])

                #curses.resetty()
                screen.keypad(True)
                curses.curs_set(0) # cursor not visible
                #curses.noecho()

                # editing in vim and return here
                tf.seek(0)
                new_note = tf.read().decode("utf-8")   # self.task.note =

            if new_note != note:
                task.note = new_note
                remote_session.commit()
                show_note(task)

            task_win.noutrefresh() # update data structure but not screen
            note_win.redrawwin() # this is needed even though note_win isn't touched
            screen.redrawln(0,1)
            screen.redrawln(size[0]-1, size[0])
            curses.doupdate() # update all physical windows

            screen.keypad(True)
            curses.curs_set(0) # cursor not visible

        # edit title in vim
        elif c == 't':
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
                remote_session.commit()
                redraw_task()

            task_win.redrawwin() # this is needed 
            task_win.noutrefresh() # update data structure but not screen
            note_win.redrawwin() # this is needed even though note_win isn't touched
            screen.redrawln(0,1)
            screen.redrawln(size[0]-1, size[0])
            curses.doupdate() # update all physical windows

            screen.keypad(True)
            curses.curs_set(0) # cursor not visible

        # toggle star
        elif c == 's':
            task.star = not task.star
            remote_session.commit()
            redraw_task()
            msg = f"{task.id} is {'starred' if task.star else 'is not starred'}"
            log = f"{now()}: {msg}\n" + log

        # toggle completed
        elif c == 'x':
            task.completed = None if task.completed else datetime.now().date()
            remote_session.commit()
            redraw_task()
            msg = f"{task.id} is {'completed' if task.completed else 'is not completed'} "
            log = f"{now()}: {msg}\n" + log

        elif c == 'd':
            task.deleted = not task.deleted
            remote_session.commit()
            redraw_task()
            msg = f"{task.id} was {'deleted' if task.deleted else 'undeleted'}"
            log = f"{now()}: {msg}\n" + log

        elif c == 'v':
            note = task.note if task.note else ''
            with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
                tf.write(note.encode("utf-8"))
                tf.flush()
                fn = tf.name
                call(['mkd2html', fn])
                html_fn  = fn[:fn.find('.')] + '.html'
                # below doesn't work so not sure how to eliminate error message
                #call(['chromium', '--single-process', html_fn]) # default is -new-tab
                call(['chromium', '--single-process', html_fn]) # default is -new-tab

        # using "vim keys" for navigation

        elif c == 'k':
            task_win.addstr(row_num, 1, " ")
            row_num-=1
            if row_num==0:
                page = (page - 1) if page > 0 else last_page
                show_tasks()  
                page_max_rows = max_rows if not page==last_page else last_page_max_rows
                row_num = page_max_rows
            task_win.addstr(row_num, 1, ">")  #k
            task_win.refresh()
            task = tasks[page*max_rows+row_num-1]
            show_note(task)

        elif c == 'j':
            task_win.addstr(row_num, 1, " ")
            row_num+=1
            if row_num==page_max_rows+1:
                page = (page + 1) if page < last_page else 0
                show_tasks()  
                row_num = 1
                page_max_rows = max_rows if not page==last_page else last_page_max_rows
            task_win.addstr(row_num, 1, ">")  #j
            task_win.refresh()
            task = tasks[page*max_rows+row_num-1]
            show_note(task)

        elif c == 'h':
            task_win.addstr(row_num, 1, " ")
            page = (page - 1) if page > 0 else last_page
            show_tasks()  
            row_num = 1
            task_win.addstr(row_num, 1, ">")  #j
            task_win.refresh()
            task = tasks[page*max_rows]
            show_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        elif c == 'l':
            task_win.addstr(row_num, 1, " ")
            page = (page + 1) if page < last_page else 0
            show_tasks()  
            row_num = 1
            task_win.addstr(row_num, 1, ">")  #j
            task_win.refresh()
            task = tasks[page*max_rows]
            show_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        elif c == '\n':
            c = 'N'

        screen.move(0, 0)
        screen.clrtoeol()
        screen.addstr(0,0, msg,  curses.A_BOLD)
        screen.addstr(0, size[1]-56,
                f"page:{page} row num:{row_num} char:{c} command: "\
                f"{''.join(accum)}",
                curses.color_pair(3)|curses.A_BOLD)
        screen.refresh()
            
        time.sleep(.05)

    # could any of these be moved below - somehow we initscr muliple times
    curses.nocbreak()
    screen.keypad(False)
    curses.echo()
    curses.endwin()

if __name__ == "__main__":
    open_display_preview({'type':'context', 'param':'todo'})
    call(['reset'])
