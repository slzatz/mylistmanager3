'''
This script reloaded and reindexed listmanger data in solr using the data in RDS listmanager
'''

from SolrClient import SolrClient
import requests
import json
from config import ec_uri
from lmdb_p import *

solr = SolrClient(ec_uri+':8983/solr/')
collection = 'listmanager'

tasks = remote_session.query(Task)
print(tasks.count())
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

    #response = solr.commit(collection, waitSearcher=False) # doesn't actually seem to work

    # Since solr.commit didn't seem to work, substituted the below, which works
    url = ec_uri+":8983/solr/"+collection+"/update"
    r = requests.post(url, data={"commit":"true"})
    print(r.text)

    print("Tasks {} to {}".format(s,n))
    s = n

