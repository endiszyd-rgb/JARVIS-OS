"""Explicit memory search: SQLite FTS5 + optional Ollama embeddings + RRF fusion.
No automatic extraction from private conversations or third-party memory service.
"""
import hashlib
import json
import math
import os
import re
import unicodedata
from fastapi import HTTPException
from . import network


def lexical_terms(query):return re.findall(r'\w{2,64}',query.lower(),flags=re.UNICODE)[:20]


def setup(c,rebuild=False):
    c.executescript('''CREATE TABLE IF NOT EXISTS memory_vectors(memory_id TEXT NOT NULL REFERENCES memory(id) ON DELETE CASCADE,namespace TEXT NOT NULL,text_hash TEXT NOT NULL,vector TEXT NOT NULL,PRIMARY KEY(memory_id,namespace));''')
    try:
        c.executescript('''
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text,content='memory',content_rowid='rowid',tokenize='unicode61 remove_diacritics 2');
        CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN INSERT INTO memory_fts(rowid,text) VALUES(new.rowid,new.text); END;
        CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN INSERT INTO memory_fts(memory_fts,rowid,text) VALUES('delete',old.rowid,old.text); END;
        CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN INSERT INTO memory_fts(memory_fts,rowid,text) VALUES('delete',old.rowid,old.text);INSERT INTO memory_fts(rowid,text) VALUES(new.rowid,new.text);END;
        ''')
        if rebuild:c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        return 'fts5'
    except Exception as exc:
        # Supported Python distributions usually have FTS5. Keep base memory usable if absent.
        if 'no such module: fts5' not in str(exc):raise
        return 'token_overlap'


def embedding_config():
    if os.getenv('JARVIS_EMBEDDINGS_ENABLED','false').lower()!='true':raise HTTPException(503,'Enable a configured embedding model before semantic search')
    url=os.getenv('OLLAMA_EMBED_URL',os.getenv('OLLAMA_URL','http://127.0.0.1:11434')).rstrip('/')
    model=os.getenv('OLLAMA_EMBED_MODEL','').strip()
    network.validate_origin(url)
    if not model or len(model)>150 or model.lower().endswith(':cloud'):raise HTTPException(503,'Set an explicit local embedding model; :cloud models are disabled here')
    revision=os.getenv('MEMORY_EMBEDDING_REVISION','1')
    namespace=hashlib.sha256((url+'\0'+model+'\0'+revision).encode()).hexdigest()
    return url,model,namespace


def vector(value):
    if not isinstance(value,list) or not 1<=len(value)<=4096 or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):raise ValueError('Invalid embedding')
    norm=math.sqrt(sum(float(x)*x for x in value))
    if not math.isfinite(norm) or norm<=0:raise ValueError('Empty embedding')
    return [float(x)/norm for x in value]


async def embed(texts,config):
    url,model,_=config
    async with network.client(url,timeout=40) as client:
        async with client.stream('POST',url+'/api/embed',json={'model':model,'input':texts,'truncate':False}) as response:
            response.raise_for_status();data=bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data)>1024*1024:raise ValueError('Embedding response too large')
    values=json.loads(data).get('embeddings')
    if not isinstance(values,list) or len(values)!=len(texts):raise ValueError('Embedding count mismatch')
    result=[vector(v) for v in values]
    if len({len(v) for v in result})!=1:raise ValueError('Embedding dimensions differ')
    return result


class Recall:
    def __init__(self,db,audit,engine):self.db=db;self.audit=audit;self.engine=engine

    def lexical(self,query,limit):
        terms=lexical_terms(query)
        if not terms:return []
        with self.db() as c:
            if self.engine=='fts5':
                expression=' OR '.join('"'+t+'"' for t in terms)
                return [dict(r) for r in c.execute('SELECT m.id,m.text,m.created FROM memory_fts JOIN memory m ON m.rowid=memory_fts.rowid WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts),m.id LIMIT ?',(expression,limit))]
            rows=[dict(r) for r in c.execute('SELECT * FROM memory ORDER BY created DESC LIMIT 1000')]
        scored=[(len(set(terms)&set(lexical_terms(r['text']))),r) for r in rows]
        return [r for score,r in sorted(scored,key=lambda item:(-item[0],item[1]['id'])) if score>0][:limit]

    async def index(self,limit=20,offset=0,force=False):
        try:config=embedding_config()
        except HTTPException:raise
        except Exception:raise HTTPException(503,'Invalid embedding configuration')
        with self.db() as c:
            condition='' if force else 'WHERE NOT EXISTS(SELECT 1 FROM memory_vectors v WHERE v.memory_id=m.id AND v.namespace=?)'
            args=() if force else (config[2],)
            rows=[dict(r) for r in c.execute('SELECT m.id,m.text FROM memory m '+condition+' ORDER BY m.created DESC,m.id LIMIT ? OFFSET ?',(*args,limit,offset))]
        if not rows:return {'indexed':0,'namespace':config[2]}
        try:values=await embed([r['text'] for r in rows],config)
        except Exception:raise HTTPException(502,'Embedding service failed; notes unchanged')
        count=0
        with self.db() as c:
            for row,val in zip(rows,values):
                current=c.execute('SELECT text FROM memory WHERE id=?',(row['id'],)).fetchone()
                if not current or current[0]!=row['text']:continue
                digest=hashlib.sha256(row['text'].encode()).hexdigest()
                c.execute('INSERT INTO memory_vectors VALUES(?,?,?,?) ON CONFLICT(memory_id,namespace) DO UPDATE SET text_hash=excluded.text_hash,vector=excluded.vector',(row['id'],config[2],digest,json.dumps(val)))
                count+=1
            self.audit(c,'memory.indexed',{'count':count})
        return {'indexed':count,'namespace':config[2]}

    async def search(self,query,mode='lexical',limit=5):
        lexical=self.lexical(query,30);semantic=[];valid={r['id']:r for r in lexical}
        if mode=='hybrid':
            try:config=embedding_config()
            except HTTPException:raise
            except Exception:raise HTTPException(503,'Invalid embedding configuration')
            with self.db() as c:
                rows=[dict(r) for r in c.execute('SELECT m.id,m.text,m.created,v.text_hash,v.vector FROM memory_vectors v JOIN memory m ON m.id=v.memory_id WHERE v.namespace=? ORDER BY m.created DESC,m.id LIMIT 1000',(config[2],))]
            try:query_vector=(await embed([query],config))[0]
            except Exception:raise HTTPException(502,'Embedding service failed; no silent semantic fallback')
            scored=[]
            for row in rows:
                if hashlib.sha256(row['text'].encode()).hexdigest()!=row['text_hash']:continue
                try:values=vector(json.loads(row['vector']))
                except ValueError:continue
                if len(values)!=len(query_vector):continue
                similarity=sum(a*b for a,b in zip(values,query_vector))
                if similarity<=0:continue
                scored.append((similarity,row));valid[row['id']]={k:row[k] for k in ('id','text','created')}
            semantic=[row['id'] for score,row in sorted(scored,key=lambda item:(-item[0],item[1]['id']))[:30]]
        ranks={}
        for source,ids in [('lexical',[r['id'] for r in lexical]),('semantic',semantic)]:
            for rank,ident in enumerate(ids,1):
                entry=ranks.setdefault(ident,{'score':0,'sources':[]});entry['score']+=1/(60+rank);entry['sources'].append(source)
        results=[dict(valid[ident],score=round(details['score'],8),sources=details['sources']) for ident,details in sorted(ranks.items(),key=lambda item:(-item[1]['score'],item[0]))[:limit]]
        with self.db() as c:self.audit(c,'memory.searched',{'mode':mode,'count':len(results)})
        return {'mode':mode,'lexical_engine':self.engine,'results':results,'semantic_candidates':len(semantic)}
