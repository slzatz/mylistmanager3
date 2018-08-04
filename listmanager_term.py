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

def update_solr_(task=None):
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
    document['star'] = task.star # haven't used this yet; schema doesn't currently reflect it

    #note that I didn't there was any value in indexing or storing context and folder
    document['context'] = task.context.title
    document['folder'] = task.folder.title

    json_docs = json.dumps([document])
    response = solr.index_json(collection, json_docs)

    # response = solr.commit(collection, waitSearcher=False) # doesn't actually seem to work
    # Since solr.commit didn't seem to work, substituted the below, which works
    url = SOLR_URI + '/solr/' + collection + '/update'
    r = requests.post(url, data={"commit":"true"})
    root = ET.fromstring(r.text)
    if root[0][0].text == '0':
        return f"{task.id} updated"
    else:
        return f"{task.id} failure"

def open_display_preview(query):
    # {'type':'context':'param':'not work'} or {'type':find':'param':'esp32'} 
    # or {'type':'recent':'param':'all'}
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
    win = curses.newwin(size[0]-1, half_width-1, 1, 1)
    win2 = curses.newwin(size[0]-1, half_width-1, 1, half_width+1)
    win3 = curses.newwin(15, 30, 1, half_width-15)
    win4 = curses.newwin(22, 60, 1, half_width-30)
    win5 = curses.newwin(29, 30, 1, half_width-15)
    win6 = curses.newwin(50, 30, 1, half_width-15)
    win7 = curses.newwin(size[0]-1, half_width, 1, half_width//2)

    page = 0
    row_num = 1
    max_chars_line = half_width - 5
    max_rows = size[0]-3

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

            if n > max_rows:
                break

            c = ' [c]' if task.completed else ''
            font = curses.color_pair(2)|curses.A_BOLD if task.star else \
                   curses.A_NORMAL
            win.addstr(n, 2,
              f"{i}. {task.title[:max_chars_line-14]} ({task.id}){c}",
              font)  #(y,x)

            n+=1

        win.refresh() 

    def draw_context():
        # would not have to draw every time if you didn't want to show what
        # context the current task has
        #task = tasks[(page*max_rows)+row_num-1]
        win3.addstr(2, 2, "0. Do nothing")
        n = 3
        for i,context in enumerate(contexts, 1):
            font = curses.color_pair(2)|curses.A_BOLD if task.context == context else curses.A_NORMAL
            win3.addstr(n, 2, f"{i}. {context.title}", font)  #(y,x)
            n+=1
            
        win3.box()
        win3.refresh()

    def draw_info():
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
            win4.addstr(1, 1, "Item Info",curses.color_pair(2)|curses.A_BOLD)
            win4.addstr(3, 1, s)  #(y,x)
            win4.addstr(20, 1, "ESCAPE to close", curses.color_pair(3))  #(y,x)

        win4.box()
        win4.refresh()
        return win4

    def draw_keywords():
        # Believe it is better to just look at keywords with a Context
        #task = tasks[(page*max_rows)+row_num-1]
        keywords = remote_session.query(Keyword).join(
            TaskKeyword,Task,Context).filter(
            Context.title==task.context.title).all()
        keywords.sort(key=lambda x:str.lower(x.name))

        #n = 2
        win6.addstr(2, 2, "0. Do nothing")
        n = 3
        for i,keyword in enumerate(keywords, 1):
            if n > 45:
                break
            font = curses.color_pair(2)|curses.A_BOLD if keyword in task.keywords else curses.A_NORMAL
            #font = curses.A_NORMAL
            win6.addstr(n, 2, f"{i}. {keyword.name}", font)  #(y,x)
            n+=1
            
        win6.box()
        win6.refresh()
        return keywords

    def show_log():
        win7.clear()
        win7.box()

        paras = log.splitlines()

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
                    win7.addstr(n, 3, line)  #(y,x)
                except Exception as e:
                     pass

                n+=1

        win7.refresh()
        return win7

    def draw_help():
        s = "n->edit [n]ote\n t->edit [t]itle\n x->toggle completed\n"\
        " w->key[w]ords\n c->[c]ontext\n d->[d]elete\n N->[N]ew item\n"\
        " i->[i]nfo\n q->[q]uit\n\n"\
        " j->page down\n k->page up\n h->page left\n l->page right\n"

        win5.addstr(1, 1, "Keymapping",curses.color_pair(2)|curses.A_BOLD)
        win5.addstr(3, 1, s)  #(y,x)
        win5.addstr(19, 1, "Commands\n",curses.color_pair(2)|curses.A_BOLD)
        s = ":help->show help screen\n :open [context]\n :solr->update db\n :log->show log\n :find [search string]"
        win5.addstr(21, 1, s)  #(y,x)
        win5.addstr(27, 1, "ESCAPE to close", curses.color_pair(3))  #(y,x)
        win5.box()
        win5.refresh()
        return win5

    def redraw(w):
        if w:
            w.erase()
            w.noutrefresh()
        win.redrawwin()
        win.noutrefresh()
        win2.redrawwin()
        win2.noutrefresh()
        curses.doupdate()
        
    # draw the surrounding screen text
    screen.clear()
    screen.addstr(0,0,
                 f"Hello Steve. screen size=x:{size[1]},y:{size[0]} "\
                 f"max_rows={max_rows} last_page={last_page} "\
                 f"query={query['type']}-{query['param']}",
                 curses.A_BOLD)

    screen.refresh()

    draw_tasks()
    task = tasks[0]
    draw_note(task)
    win.addstr(row_num, 1, ">")  
    win.refresh()

    accum = [] 
    command = None 
    page_max_rows = max_rows if last_page else last_page_max_rows
    msg = ''
    log = ''
    cur_win = None
    while 1:
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
                            log = f"{datetime.now().isoformat(' ')}: {msg}\n" + log

                        redraw(win3)
                        command = None
                    elif command == 'open':
                        p = int(chars) - 1
                        if p < 0 or p > len(contexts):
                            msg = "do nothing"
                            redraw(win3)
                            command = None
                        else:
                            context = contexts[p]
                            command = None
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
                                log = f"{datetime.now().isoformat(' ')}: {msg}\n" + log

                        redraw(win6)
                        command = None
                    else:
                        # typing a number will produce a search
                        # if command != open or context
                        command = None
                        open_display_preview({'type':'find', 'param':chars})

                # assumes anything else is a find string 
                elif "help".startswith(chars):
                    #win5.refresh()    
                    cur_win = draw_help()
                    command = None
                elif "solr".startswith(chars):
                    result = update_solr()
                    log =  result + log
                    msg = result.split('\n')[0]
                    command = None
                elif "open".startswith(chars):
                    draw_context() # need to redraw to show the current task's context
                    command = 'open'
                elif "log".startswith(chars):
                    curwin = show_log()
                    command = None
                elif "find".startswith(chars.split(' ', 1)[0]):
                    command = None
                    open_display_preview({'type':'find', 'param':chars.split(' ', 1)[1]})
                else:
                    command = None
                    #open_display_preview({'type':'find', 'param':chars})
                    msg = "I don't know what you typed"
            else:
                accum.append(c)

        elif c == ':': 
            command = True
            
        elif n == 27: #escape
            redraw(cur_win)
            #screen.redrawwin()
            #screen.refresh()
            #win.redrawwin()
            #win.refresh()
            #win2.redrawwin()
            #win2.refresh()
            command = None
            cur_win = None
            c = 'E'

        #elif c in ['\n', 'q']:
        elif c == 'q':  
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
            #task = tasks[(page*max_rows)+row_num-1]
            call(['reset'])
            #action = actions[c]
            #c = ''
            #return {'action':action, 'task_id':task.id}
            return

        #elif c == 'o':
        #    draw_context() # need to redraw to show the current task's context
        #    command = 'open'

        elif c == 'r':
            open_display_preview({'type':'recent', 'param':'all'})

        elif c == 'c':
            draw_context() # need to redraw to show the current task's context
            command = 'context'

        elif c == 'w':
            keywords = draw_keywords()
            command = 'keywords'

        elif c == 'i':
            cur_win = draw_info()

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
            #win.addstr(row_num, 1, " ")  #j
            win.addstr(row_num, 1, " ")
            last_page = len(tasks)//max_rows
            last_page_max_rows = len(tasks)%max_rows
            page = 0
            row_num = 1
            draw_tasks()
            draw_note(tasks[0])
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            log = f"task {task.id} added" + log

        # edit note in vim
        elif c == 'n':
            #task = tasks[(page*max_rows)+row_num-1]
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
                draw_note(task)

            win.noutrefresh() # update data structure but not screen
            win2.redrawwin() # this is needed even though win2 isn't touched
            screen.redrawln(0,1)
            screen.redrawln(size[0]-1, size[0])
            curses.doupdate() # update all physical windows

            screen.keypad(True)
            curses.curs_set(0) # cursor not visible

        # edit title in vim
        elif c == 't':
            #task = tasks[(page*max_rows)+row_num-1]
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
                comp = ' [c]' if task.completed else ''
                font = curses.color_pair(2)|curses.A_BOLD if task.star else curses.A_NORMAL

                win.redrawwin() 
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
            curses.doupdate() # update all physical windows

            screen.keypad(True)
            curses.curs_set(0) # cursor not visible

        # toggle star
        elif c == 's':
            #task = tasks[(page*max_rows)+row_num-1]
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
            msg = f"{task.id} is {'starred' if task.star else 'is not starred'}"
            log = f"{datetime.now().isoformat()}: {msg}" + log

        # toggle completed
        elif c == 'x':
            #task = tasks[(page*max_rows)+row_num-1]

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

            # the clrtoeol wipes out the vertical box line character
            win.addch(row_num, half_width-2, curses.ACS_VLINE) 
            win.refresh()
            remote_session.commit()
            msg = f"{task.id} is {'completed' if task.completed else 'is not completed'} "
            log = f"{datetime.now().isoformat()}: {msg}" + log

        elif c == 'd':
            #task = tasks[(page*max_rows)+row_num-1]
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

            msg = f"{task.id} was marked for deletion"
            log = f"{datetime.now().isoformat()}: {msg}" + log

        elif c == 'v':
            #task = tasks[(page*max_rows)+row_num-1]

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
            win.addstr(row_num, 1, " ")
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
            win.addstr(row_num, 1, " ")
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
            win.addstr(row_num, 1, " ")
            page = (page - 1) if page > 0 else last_page
            draw_tasks()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
            page_max_rows = max_rows if not page==last_page else last_page_max_rows

        elif c == 'l':
            win.addstr(row_num, 1, " ")
            page = (page + 1) if page < last_page else 0
            draw_tasks()  
            row_num = 1
            win.addstr(row_num, 1, ">")  #j
            win.refresh()
            task = tasks[page*max_rows]
            draw_note(task)
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

if __name__ == "__main__":
    open_display_preview({'type':'context', 'param':'todo'})
