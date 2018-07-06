#!bin/python

from cmd2 import Cmd
from SolrClient import SolrClient
from config import SOLR_URI
from lmdb_p import *
import tempfile
import sys
import os
from subprocess import call
import json
import datetime
import requests

solr = SolrClient(SOLR_URI + '/solr')
collection = 'listmanager'
#session = local_session
session = remote_session

#solr_ids = [] #10 Only here because ini/config has tab

def bold(text):
    return "\033[1m" + text + "\033[0m"

class Listmanager(Cmd):

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True

    def __init__(self):
        self.raw = "Nothing"
        self.intro = "Welcome to ListManager"
        self.quit = False
        self.task = None
        self.msg = ''
        self.solr_ids = []

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
        document['tag'] =[k.name for k in task.keywords]

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
        print(r.text)

    def do_find(self, s):
        '''Select the master speaker that will be controlled; no arguments'''

        if not s:
            self.msg = "You didn't type any search terms"
            return

        s0 = s.split()
        s1 = 'title:' + ' OR title:'.join(s0)
        s2 = 'note:' + ' OR note:'.join(s0)
        s3 = 'tag:' + ' OR tag:'.join(s0)
        q = s1 + ' OR ' + s2 + ' OR ' + s3
        #print(q)
        result = solr.query(collection, {'q':s, 'rows':50, 'fl':['score', 'id', 'title', 'tag', 'star', 'context', 'completed'], 'sort':'score desc'})
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

        self.solr_ids = [x['id'] for x in items]

        # important: since we are dealing with server using 'id' not 'tid'
        order_expressions = [(Task.id==i).desc() for i in self.solr_ids]
        tasks = session.query(Task).filter(Task.id.in_(self.solr_ids)).order_by(*order_expressions)
        z = [(task,f"{task.id}: {task.title}") for task  in tasks]
        task = self.select(z, bold(self.colorize("\nWhich one? ", 'cyan')))
        if task:
            #self.msg = "edit the 'note' or the 'title'"
            self.msg = ""
            self.prompt = bold(self.colorize(f"[{task.id}: {task.title[:25]}...]> ", 'magenta'))
            self.task = task
        else:
            #self.msg = "There is currently no task selected"
            self.msg = ""
            self.prompt = self.colorize("> ", 'red')
            self.task = None

    def do_title___(self, s):
        if not self.task:
            self.msg = "There is no task selected"
            return
        if s:
            self.task.title = s
            session.commit()
            self.update_solr()
            self.msg = "Item updated with new title: "+self.colorize(s, 'green')
        else:
            self.msg = "You didn't provide any new text for the title"

    def do_note(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        EDITOR = os.environ.get('EDITOR','vim') #that easy!

        initial_message = self.task.note if self.task.note else ''  # if you want to set up the file somehow

        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(initial_message.encode("utf-8"))
            #tf.write(initial_message)
            tf.flush()
            call([EDITOR, tf.name])

            # do the parsing with `tf` using regular File operations.
            # for instance:
            tf.seek(0)
            edited_message = tf.read()   # self.task.note =
            self.task.note = edited_message.decode("utf-8")
            session.commit()

        self.update_solr(task)
        self.msg = "note updated"

    def do_view(self, s):
        if s:
            task_ids = s.split()
        elif self.solr_ids:
            task_ids = [str(id_) for id_ in self.solr_ids][:10]

        z = ['./task_display.py']
        z.extend(task_ids)
        #call(['./task_display.py', '2000', '3000'])
        call(z)

    def do_info(self, s):
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
        
        task = Task(priority=3, title=s)
        remote_session.add(task)
        remote_session.commit()
        self.task = task
        self.prompt = bold(self.colorize(f"[{task.id}: {task.title[:25]}...]> ", 'magenta'))
        self.update_solr()
        self.msg = "New task created"
        self.do_context() # msg = "slkfldsf" so it could then be added to the context msg

    def do_recent(self, s):
        tasks = remote_session.query(Task)
        if not s or s == 'all':
            tasks = tasks.filter(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)))
        elif s == 'created':
            tasks = tasks.filter(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
        elif s == 'completed':
            tasks = tasks.filter(Task.completed > (datetime.datetime.now()-datetime.timedelta(days=2)).date())
        elif s == 'modified':
            tasks = tasks.filter(and_(Task.modified > (datetime.datetime.now()-datetime.timedelta(days=2)), ~(Task.created > (datetime.datetime.now()-datetime.timedelta(days=2)).date())))

        z = [(task,f"{task.id}: {task.title}") for task  in tasks]
        task = self.select(z, "Which item? ")
        if task:
            self.msg = "edit the 'note' or the 'title'"
            self.prompt = bold(self.colorize(f"[{task.id}: {task.title[:25]}...]> ", 'magenta'))
            self.task = task
        else:
            self.msg = "There is currently no task selected"
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
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        task.deleted = not task.deleted
        remote_session.commit()
        self.msg = f"{task.title} - deleted {task.deleted}"

    def do_title(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
            print("Got here")
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        EDITOR = os.environ.get('EDITOR','vim') #that easy!

        #initial_message = self.task.note if self.task.note else ''  # if you want to set up the file somehow
        initial_message = task.title 

        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(initial_message.encode("utf-8"))
            #tf.write(initial_message)
            tf.flush()
            call([EDITOR, tf.name])

            # do the parsing with `tf` using regular File operations.
            # for instance:
            tf.seek(0)
            edited_message = tf.read().strip()   # self.task.note =
            #self.task.note = edited_message.decode("utf-8")

        task.title = edited_message.decode("utf-8")
        session.commit()

        self.update_solr(task)
        self.msg = "title updated"

    def do_context(self, s=None):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        #if not self.task:
        #    self.msg = self.colorize("You have to select a task first", 'red')
        #    return
        #if s:
        #    context = remote_session.query(Context).filter_by(title=s).first()
        #else:
        #    contexts = remote_session.query(Context).filter(Context.id!=1).all()
        #    contexts.sort(key=lambda c:str.lower(c.title))
        #    no_context = session.query(Context).filter_by(id=1).one()
        #    contexts = [no_context] + contexts
        #    z = [(context,f"{context.id}: {context.title}") for context  in contexts]
        #    context = self.select(z, "Select a context for the current task? ")

        contexts = remote_session.query(Context).filter(Context.id!=1).all()
        contexts.sort(key=lambda c:str.lower(c.title))
        no_context = session.query(Context).filter_by(id=1).one()
        contexts = [no_context] + contexts
        z = [(context,f"{context.id}: {context.title}") for context  in contexts]
        context = self.select(z, "Select a context for the current task? ")
        if context:
            task.context = context
            self.msg = f"{task.id}: {task.title} now has context {context.title}"
        else:
            self.msg = self.colorize("You did not select a context", 'red')
        
    def do_colors(self, s):
        text = self.colorize("red\n", 'red')
        text+= self.colorize("green\n", 'green')
        text+= self.colorize("magenta\n", 'magenta')
        text+= self.colorize("cyan\n", 'cyan')
        text+= bold(self.colorize("red bold\n", 'red'))
        text+= bold(self.colorize("green bold\n", 'green'))
        text+= bold(self.colorize("magenta bold\n", 'magenta'))
        text+= bold(self.colorize("cyan bold\n", 'cyan'))

        self.msg = text

    def do_tags(self, s):
        if s:
            task = remote_session.query(Task).get(int(s))
        elif self.task:
            task = self.task
        else:
            self.msg = "You didn't provide an id and there was no selected task"
            return

        #keywords = remote_session.query(Keyword).all()
        keywords = remote_session.query(Keyword).join(TaskKeyword,Task,Context).filter(Context.title==task.context.title).all()
        keywords.sort(key=lambda x:str.lower(x.name))
        keyword_names = [keyword.name for keyword in keywords]
        #z = [(keyword,keyword.name) for keyword in keywords]
        #z = [(keyword, f"{keyword.id}: {keyword.name}") for keyword in keywords]
        #z = [(keyword, f"{keyword.id}: {keyword.name}" if keyword not in task.keywords else self.colorize( f"{keyword.id}: {keyword.name}", 'green')) for keyword in keywords]
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
            remote_session.commit()
            self.update_solr(task)
            self.msg = f"You added {keyword.name}to {task.title}"
        else:
            self.msg = self.colorize("You didn't select a keyword", 'red')

    def do_edit(self, s):
        '''The edit command requires (right now) that a task be selected
        The two options are edit note and edit title
        '''
        if len(s.argv) < 2:
            self.msg = self.colorize("You need to indicate whether editing a note or the title", 'red')
            return

        p = int(s.argv[2]) if len(s.argv) == 3 else ''
        
        if s.argv[1] == 'note':
            self.do_note(p)
        elif s.argv[1] == 'title':
            self.do_title(p)

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
