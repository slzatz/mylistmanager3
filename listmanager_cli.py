#!bin/python
'''
note have to figure out if the number should be the 'find number' or the task id
so should this be task = remote_session.query(Task).get(self.task_ids[int(s)])
Currently using task.id in most places except do_select -- that actually may be 
the right way to do it to only use 'view id' with select and task.id everywhere else.

'''
from cmd2 import Cmd
from cmd2.parsing import StatementParser
from SolrClient import SolrClient
from config import SOLR_URI
from lmdb_p import *
import tempfile
import sys
import os
from subprocess import call, check_output, run, PIPE
import json
import datetime
import requests
import xml.etree.ElementTree as ET

solr = SolrClient(SOLR_URI + '/solr')
collection = 'listmanager'
session = remote_session

def bold(text):
    return "\033[1m" + text + "\033[0m"

def myparser():
    parser = StatementParser(terminators=[';', '&'])
    return parser

class Listmanager(Cmd):

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True

    def __init__(self):
        self.raw = "Nothing"
        self.intro = "Welcome to ListManager"
        self.quit = False
        self.task = None
        self.msg = ''
        self.task_ids = []

        super().__init__(use_ipython=False) #, startup_script='sonos_cli2_startup')
        # need to run super before the line below
        self.prompt = self.colorize("> ", 'red')

    def preparse_(self, s):
        # this is supposed to be called before any parsing of input
        # apparently do to a bug this is never called
        print("1:preparse:self.raw =",s)
        self.raw = s
        print("2:preparse:self.raw =",s)
        self.msg = ''
        return s

    def task_id_check(self, s):
        if s.isdigit(): # works if no s (s = '')
            task = remote_session.query(Task).get(int(s))
            if not task:
                self.msg = self.colorize("That was not a valid task.id", 'red')
                return
        elif self.task:
            task = self.task
        else:
            self.msg = self.colorize(
                f"The command needs a task.id or for self.task to be defined", 'red')
            return

        self.msg = ""
        return task

    def update_solr(self, task=None):
        solr = SolrClient(SOLR_URI + '/solr/')
        collection = 'listmanager'

        if not task:
            task = self.task

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
            print(self.colorize("solr update successful", 'yellow'))
        else:
            print(self.colorize("there was a problem with the solr update", 'yellow'))

    def do_open(self, s):
        '''Retrive tasks by context'''

        contexts = remote_session.query(Context).filter(Context.id!=1).all()
        contexts.sort(key=lambda c:str.lower(c.title))
        no_context = remote_session.query(Context).filter_by(id=1).one()
        contexts = [no_context] + contexts
        z = [(context,f"{context.title}") for context  in contexts]
        context = self.select(z, "Select a context to display: ")
        if not context:
            self.msg = ''
            return
        tasks = remote_session.query(Task).join(Context).filter(Task.context==context, Task.deleted==False).order_by(desc(Task.modified)).limit(40)
        self.task_ids = [task.id for task in tasks]
        #z = [(task,f"{'*' if task.star else ' '}{task.title}({task.id})") for task in tasks]
        z = [(task, bold(f"*{task.title}({task.id})")) if task.star else \
             (task, f"{task.title} ({task.id})") for task in tasks]
        task = self.select(z, bold(self.colorize("Choose (or ENTER if you want to create a set of tasks for the view command)? ", 'cyan')))
        if task:
            self.msg = ""
            self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
            self.task = task
            #self.do_view(myparser().parse(f"view {task.id}")) #######################################
        else:
            self.msg = ""
            self.prompt = self.colorize("> ", 'red')
            self.task = None

    def do_find(self, s):
        '''Find tasks via seach; ex: find esp32 wifit'''

        if not s:
            self.msg = "You didn't type any search terms"
            return

        s0 = s.split()
        s1 = 'title:' + ' OR title:'.join(s0)
        s2 = 'note:' + ' OR note:'.join(s0)
        s3 = 'tag:' + ' OR tag:'.join(s0)
        q = s1 + ' OR ' + s2 + ' OR ' + s3
        #print(q)
        result = solr.query(collection, {'q':q, 'rows':50, 'fl':['score', 'id', 'title', 'tag', 'star', 'context', 'completed'], 'sort':'score desc'})
        items = result.docs
        count = result.get_results_count()
        if count==0:
            self.msg = "Did not find any matching items"
            return


        # change to 1 if you want to see what's happening with the search
        if 0:
            text = "item count = {}\n\n".format(count)
            for n,item in enumerate(items[:5],1):
                try:
                    text+= "{}\n".format(n)
                    text+= "score: {}\n".format(str(item['score']))
                    text+= "id: {}\n".format(str(item['id']))
                    text+= "title: {}\n".format(item['title'])
                    text+= "tag: {}\n".format(item.get('teg', ''))
                    text+= "star: {}\n".format(str(item['star']))
                    text+= "context: {}\n".format(item['context'])
                    text+= "completed: {}\n\n".format(str(item['completed']))
                except Exception as e:
                    text+= e
            print(text)

        solr_ids = [x['id'] for x in items]
        #print(self.colorize(repr(solr_ids), 'yellow')) 
        # note that (unfortunately) some solr ids exist for tasks that have been deleted -- need to fix that
        # important: since we are dealing with server using 'id' not 'tid'
        order_expressions = [(Task.id==i).desc() for i in solr_ids]
        tasks = session.query(Task).filter(Task.deleted==False,
                        Task.id.in_(solr_ids)).order_by(*order_expressions)
        self.task_ids = [task.id for task in tasks]
        z = [(task,f"{task.id}:{'*' if task.star else ' '}{task.title}") for task in tasks]
        task = self.select(z, bold(self.colorize("Choose (or ENTER if you want to create a set of tasks for the view command)? ", 'cyan')))
        if task:
            self.msg = ""
            self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
            self.task = task
            # the below works but for now let's not automatically go to the ncurses version of the note
            #self.do_view(myparser().parse(f"view {task.id}")) #######################################
        else:
            self.msg = ""
            self.prompt = self.colorize("> ", 'red')
            self.task = None

    def do_note(self, s):
        '''modify the note of either the currently selected task or task_id; ex: note 4433'''

        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        EDITOR = os.environ.get('EDITOR','vim') #that easy!

        note = task.note if task.note else ''  # if you want to set up the file somehow

        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(note.encode("utf-8"))
            tf.flush()
            call([EDITOR, tf.name])
            #command = tf.name + " -c 'set linebreak'"
            #call([EDITOR, command]) #<-- this doesn't work

            # editing in vim and return here
            tf.seek(0)
            #new_note = tf.read()   # self.task.note =
            new_note = tf.read().decode("utf-8")   # self.task.note =
            #task.note = new_note.decode("utf-8")
            #session.commit()

        if new_note != note:
            task.note = new_note
            session.commit()
            self.update_solr(task)
            self.msg = self.colorize("note updated", 'green')
        else:
            self.msg = self.colorize("note was not changed", 'red')

    def do_viewall(self, s):
        '''provide task ids or view the current task list; ex: view 4482 4455 4678'''
        if s:
            task_ids = s.split()
        elif self.task_ids:
            task_ids = [str(id_) for id_ in self.task_ids][:20]

        z = ['./task_display.py']
        z.extend(task_ids)
        response = run(z, check=True, stderr=PIPE) # using stderr because stdout is used by task_display.py
        if response.stderr:
            command = json.loads(response.stderr)
            #print(self.colorize(response.stderr.decode('utf-8'), 'yellow'))
            self.do_edit(myparser().parse(f"edit {command['action']} {command['task_id']}"))

        #self.msg = '' # generally calling another method that can produce message

    def do_info(self, s):
        '''Info on the currently selected task or for a task id that you provide'''
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "There is no task selected"
            return

        text = f"id: {task.id}\n"
        text+= f"title: {task.title}\n"
        text+= f"priority: {task.priority}\n"
        text+= f"star: {task.star}\n"
        text+= f"context: {task.context.title}\n"
        text+= f"keywords: {', '.join(k.name for k in task.keywords)}\n"
        text+= f"tag: {task.tag}\n"
        text+= f"completed: {task.completed}\n"
        text+= f"deleted: {task.deleted}\n"
        text+= f"created: {task.created}\n"
        text+= f"modified: {task.modified}\n"
        text+= f"note: {task.note[:30] if task.note else ''}"

        self.msg = text

    def do_new(self, s):
        
        if not s:
            self.msg = self.colorize("You need to provide a title", 'red')
            return

        task = Task(priority=3, title=s)
        remote_session.add(task)
        remote_session.commit()
        self.task = task
        self.prompt = bold(self.colorize(f"[{task.id}: {task.title[:25]}...]> ", 'magenta'))
        self.update_solr()
        self.msg = "New task created"
        self.do_context() # msg = "slkfldsf" so it could then be added to the context msg

    def do_recent(self, s):
        tasks = remote_session.query(Task).filter(Task.deleted==False)
        if not s or s == 'all':
            tasks = tasks.filter(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)))
        elif s == 'created':
            tasks = tasks.filter(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
        elif s == 'completed':
            tasks = tasks.filter(Task.completed > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
        elif s == 'modified':
            tasks = tasks.filter(and_(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)), ~(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())))


        self.task_ids = [task.id for task in tasks]
        #z = [(task,f"{task.id}: {task.title}") for task  in tasks]
        z = [(task,f"{task.id}:{'*' if task.star else ' '}{task.title}") for task in tasks]
        z = [(task,f"{task.id}:{'*' if task.star else ' '}{task.title}") for task in tasks]
        task = self.select(z, bold(self.colorize("Choose (or ENTER if you want to create a set of tasks for the view command)? ", 'cyan')))
        if task:
            self.msg = ""
            self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
            self.task = task
            #self.do_view(myparser().parse(f"view {task.id}")) #######################################
        else:
            self.msg = ""
            self.prompt = self.colorize("> ", 'red')
            self.task = None

    def do_test(self, s):
        print(s)
        print(type(s))
        print(dir(s))
        print(f"args: {s.args}") #s.args seems same as s
        print(f"command: {s.command}")
        print(f"argv: {s.argv}")
        print(f"raw: {s.raw}")

    def do_delete(self, s):
        task = self.task_id_check(s)
        if not task:
            return

        task = remote_session.query(Task).get(int(s))
        task.deleted = not task.deleted
        remote_session.commit()
        self.msg = f"{task.title} - deleted {task.deleted}"

    def do_title(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        EDITOR = os.environ.get('EDITOR','vim') #that easy!

        #initial_message = task.title 

        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(task.title.encode("utf-8"))
            tf.flush()
            call([EDITOR, tf.name])

            # editing in vim and return here
            tf.seek(0)
            new_title = tf.read().strip()   # self.task.note =

        task.title = new_title.decode("utf-8")
        self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''} {task.title[:25]}...]> ", 'magenta'))
        session.commit()

        self.update_solr(task)
        self.msg = self.colorize("title updated", 'green')

    def do_context(self, s=None):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        contexts = remote_session.query(Context).filter(Context.id!=1).all()
        contexts.sort(key=lambda c:str.lower(c.title))
        no_context = remote_session.query(Context).filter_by(id=1).one()
        contexts = [no_context] + contexts
        z = [(context,f"{context.title}") for context  in contexts]
        context = self.select(z, "Select a context for the current task? ")
        if context:
            task.context = context
            remote_session.commit()
            self.update_solr(task)
            self.msg = f"{task.id}: {task.title} now has context {context.title}"
        else:
            self.msg = self.colorize("You did not select a context", 'red')
        
    def do_colors(self, s):
        text = self.colorize("red\n", 'red')
        text+= self.colorize("green\n", 'green')
        text+= self.colorize("magenta\n", 'magenta')
        text+= self.colorize("cyan\n", 'cyan')
        text+= self.colorize("yellow\n", 'yellow')
        text+= bold(self.colorize("red bold\n", 'red'))
        text+= bold(self.colorize("green bold\n", 'green'))
        text+= bold(self.colorize("magenta bold\n", 'magenta'))
        text+= bold(self.colorize("cyan bold\n", 'cyan'))
        text+= bold(self.colorize("yellow bold\n", 'yellow'))

        self.msg = text

    def do_tags(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        #keywords = remote_session.query(Keyword).all() # better to just look at context's keywords
        keywords = remote_session.query(Keyword).join(TaskKeyword,Task,Context).filter(Context.title==task.context.title).all()
        keywords.sort(key=lambda x:str.lower(x.name))
        keyword_names = [keyword.name for keyword in keywords]
        z = [(keyword, f"{keyword.id}: {keyword.name}" \
             if keyword not in task.keywords \
             else self.colorize( f"{keyword.id}: {keyword.name}", 'green')) \
             for keyword in keywords]

        keyword = self.select(z, "Select a keyword for the current task? ")
        if keyword:
            if keyword in task.keywords:
                self.msg = self.colorize(f"{keyword.name} already attached to {task.title}!", 'red')
                return
            taskkeyword = TaskKeyword(task, keyword)
            remote_session.add(taskkeyword)
            task.tag = ','.join(kwn.name for kwn in task.keywords) #######
            remote_session.commit()
            self.update_solr(task)
            self.msg = self.colorize(f"You added {keyword.name} to {task.title}", 'green')
        else:
            self.msg = self.colorize("You didn't select a keyword", 'red')

    def do_edit(self, s):
        '''The edit command requires (right now) that a task be selected
        The two options are edit note and edit title
        '''
        if len(s.argv) < 2:
            self.msg = self.colorize("You need to indicate whether editing a note or the title", 'red')
            return

        p = s.argv[2] if len(s.argv) == 3 else ''
        
        if s.argv[1] == 'note':
            self.do_note(myparser().parse("note "+p))
        elif s.argv[1] == 'title':
            self.do_title(myparser().parse("title "+p))
        elif s.argv[1] == 'context':
            self.do_context(myparser().parse("context "+p))

    def do_select(self, s):
        if not s.isdigit:
            self.msg = self.colorize(f"You need to enter a task number between 1 and {len(self.task_ids)}", 'red')
            return
        else:
            task_id = self.task_ids[int(s)-1]
            self.task = task = remote_session.query(Task).get(task_id)
        self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
        self.msg = ""

    def do_view(self, s):
        if not s:
            if not self.task:
                return
            task = self.task
        elif not s.isdigit():
            self.msg = self.colorize(f"You need to enter a valid number from 1 to {len(self.task_ids)}", 'red')
            return
        else:
            task_id = self.task_ids[int(s)-1]
            self.task = task = remote_session.query(Task).get(task_id)
        z = ['./task_display.py']
        z.append(str(task.id))
        response = run(z, check=True, stderr=PIPE) # using stderr because stdout is used by task_display.py
        if response.stderr:
            command = json.loads(response.stderr)
            #print(self.colorize(response.stderr.decode('utf-8'), 'yellow'))
            self.do_edit(myparser().parse(f"edit {command['action']} {command['task_id']}"))
        self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
        #self.do_view(myparser().parse(f"view {task.id}")) #######################################
        self.msg = ""

    def do_star(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return
        
        task.star = not task.star
        remote_session.commit()
        self.update_solr(task)
        self.prompt = bold(self.colorize(f"[{task.id}: {'*' if task.star else ''}{task.title[:25]}...]> ", 'magenta'))
        self.msg = ''

    def do_html(self, s):
        task = self.task_id_check(s)
        if not task:
            return

        note = task.note if task.note else ''
        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(note.encode("utf-8"))
            tf.flush()
            fn = tf.name
            call(['mkd2html', fn])
            html_fn  = fn[:fn.find('.')] + '.html'
            #call(['lynx', html_fn])
            #call(['chromium', '-new-window', html_fn])
            #call(['chromium', '-new-tab', html_fn])
            call(['chromium', html_fn]) # default is -new-tab
        
    def do_quit(self, s):
        self.quit = True

    def postcmd(self, stop, s):
        if self.quit:
            return True
        # the below prints the appropriate message after each command
        print(self.msg)

if __name__ == '__main__':
    c = Listmanager()
    c.cmdloop()
