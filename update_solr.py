#!bin/python
from datetime import datetime, timedelta
import json
from SolrClient import SolrClient
import requests
from config import SOLR_URI
from lmdb_p import *
remote_session = new_remote_session()
def update_solr():

    solr = SolrClient(SOLR_URI + '/solr/')
    collection = 'listmanager'
    solr_sync = remote_session.query(Sync).get('solr')
    last_solr_sync = solr_sync.timestamp
    log = f"{datetime.now().isoformat(' ')}: last Solr sync = {last_solr_sync.isoformat(' ')}\n"
    tasks = remote_session.query(Task).filter(Task.modified > last_solr_sync)
    log = f"{datetime.now().isoformat(' ')}: number of tasks modified since "\
          f"last sync = {str(tasks.count())}\n" + log
    max = round(tasks.count(), -2) + 200
    s = 0
    for n in range(100, max, 100):

        documents = []
        for task in tasks[s:n]:
            document = {}
            document['id'] = task.id
            document['title'] = task.title
            document['note'] = task.note if task.note else ''
            document['tag'] =[t for t in task.tag.split(',')] if task.tag else []

            document['completed'] = task.completed != None
            document['star'] = task.star # haven't used this yet and schema doesn't currently reflect it

            #note that I didn't there was any value in indexing or storing context and folder
            document['context'] = task.context.title
            document['folder'] = task.folder.title

            documents.append(document)

        json_docs = json.dumps(documents)
        response = solr.index_json(collection, json_docs)

        # response = solr.commit(collection, waitSearcher=False) # doesn't actually seem to work
        # Since solr.commit didn't seem to work, substituted the below, which works
        url = SOLR_URI + '/solr/' + collection + '/update'
        r = requests.post(url, data={"commit":"true"})
        #print(r.text)

        #print("Tasks {} to {}".format(s,n))
        s = n

    solr_sync.timestamp = datetime.now() + timedelta(seconds=2)
    remote_session.commit()
    log = f"{datetime.now().isoformat(' ')}: new Solr sync = "\
           f"{solr_sync.timestamp.isoformat(' ')}\n" + log
    return log

if __name__ == "__main__":
    log = update_solr()
    print(log)
