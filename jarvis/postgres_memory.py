"""Optional durable scoped memory, using checked runtime transactions and pgvector.

This repository performs no embedding I/O, schema creation or automatic import
of legacy SQLite memory. Scope is always private OR one explicit workshop.
"""
import re
from fastapi import HTTPException
from psycopg import sql
from .postgres_store import PostgresStore, _ident, _revision
from .recall import vector

_FIELDS = '''id,owner_id,workshop_id,content,category,source,source_id,revision,text_hash,
             embedding_namespace,(embedding IS NOT NULL) AS indexed,created_at,updated_at'''
_NAMESPACE = re.compile(r'[0-9a-f]{64}\Z')
_CATEGORY = re.compile(r'[a-z_]{1,40}\Z')


def content_values(content, category='note', source='manual', source_id=''):
    if (not isinstance(content, str) or not content.strip() or len(content)>8000
            or not isinstance(category, str) or not _CATEGORY.fullmatch(category)
            or source not in ('manual','session','import')
            or not isinstance(source_id, str) or len(source_id)>120):
        raise HTTPException(422, 'Invalid memory content or provenance')
    try:
        content.encode('utf-8'); source_id.encode('utf-8')
    except UnicodeError:
        raise HTTPException(422, 'Invalid memory text encoding') from None
    return content, category, source, source_id


def embedding_value(value, namespace):
    if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
        raise HTTPException(422, 'Invalid memory embedding namespace')
    try:
        normalized = vector(value)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, 'Invalid memory embedding') from None
    # A parameterized text cast avoids adding a global psycopg type adapter.
    return '['+','.join(str(x) for x in normalized)+']', len(normalized)


def _page(limit, offset=0):
    if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=100000:
        raise HTTPException(422, 'Invalid memory page')


def _scope(workshop_id):
    return (sql.SQL('workshop_id IS NULL'), ()) if workshop_id is None else (
        sql.SQL('workshop_id=%s'), (_ident(workshop_id),))


class PostgresMemory:
    def __init__(self, storage: PostgresStore):
        if not isinstance(storage, PostgresStore):
            raise ValueError('PostgresMemory requires checked PostgresStore')
        self.storage = storage

    def status(self):
        with self.storage._connection() as connection:
            row=connection.execute('SELECT jarvis.memory_schema_version() AS version').fetchone()
            if row is None or row['version'] not in (1,2,3,4):
                raise HTTPException(503, 'PostgreSQL memory migration is required')
            extension=connection.execute("SELECT e.extversion FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector' AND n.nspname='jarvis_extensions'").fetchone()
            if extension is None:
                raise HTTPException(503, 'PostgreSQL memory extension is unavailable')
        return {'enabled':True,'status':'ready','memory_schema_version':row['version'],'pgvector_version':extension['extversion']}

    @staticmethod
    def _event(connection, subject, event, row):
        connection.execute('INSERT INTO jarvis.memory_events(subject,event,memory_id,revision) VALUES(%s,%s,%s,%s)',
                           (subject,event,row['id'],row['revision']))

    @staticmethod
    def _failure(connection, ident, revision):
        row=connection.execute('SELECT revision FROM jarvis.memory_records WHERE id=%s',(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Memory record missing')
        if row['revision']!=revision:raise HTTPException(409,'Memory revision changed; refresh')
        raise HTTPException(403,'Memory operation is not permitted')

    def create(self, subject, content, *, workshop_id=None, category='note', source='manual', source_id=''):
        subject=_ident(subject); workshop=_ident(workshop_id) if workshop_id is not None else None
        values=content_values(content,category,source,source_id)
        with self.storage._connection(subject) as c:
            row=c.execute(sql.SQL('INSERT INTO jarvis.memory_records(owner_id,workshop_id,content,category,source,source_id) VALUES(%s,%s,%s,%s,%s,%s) RETURNING '+_FIELDS),
                          (subject,workshop,*values)).fetchone()
            self._event(c,subject,'created',row)
            return row

    def get(self, subject, ident):
        subject,ident=_ident(subject),_ident(ident)
        with self.storage._connection(subject) as c:
            row=c.execute(sql.SQL('SELECT '+_FIELDS+' FROM jarvis.memory_records WHERE id=%s'),(ident,)).fetchone()
            if row is None:raise HTTPException(404,'Memory record missing')
            return row

    def list(self, subject, *, workshop_id=None, limit=50, offset=0):
        subject=_ident(subject);_page(limit,offset);scope,args=_scope(workshop_id)
        with self.storage._connection(subject) as c:
            return c.execute(sql.SQL('SELECT '+_FIELDS+' FROM jarvis.memory_records WHERE {} ORDER BY created_at DESC,id LIMIT %s OFFSET %s').format(scope),(*args,limit,offset)).fetchall()

    def update(self, subject, ident, revision, content, *, category='note', source='manual', source_id=''):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        values=content_values(content,category,source,source_id)
        with self.storage._connection(subject) as c:
            row=c.execute(sql.SQL('UPDATE jarvis.memory_records SET content=%s,category=%s,source=%s,source_id=%s,revision=revision+1 WHERE id=%s AND revision=%s RETURNING '+_FIELDS),(*values,ident,revision)).fetchone()
            if row is None:self._failure(c,ident,revision)
            self._event(c,subject,'updated',row)
            return row

    def delete(self, subject, ident, revision):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        with self.storage._connection(subject) as c:
            row=c.execute('DELETE FROM jarvis.memory_records WHERE id=%s AND revision=%s RETURNING id,revision',(ident,revision)).fetchone()
            if row is None:self._failure(c,ident,revision)
            self._event(c,subject,'deleted',row)
            return {'deleted':str(ident)}

    def prepare_index(self, subject, ident, revision):
        """Check access/write permission before sending text to an embedding service."""
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        with self.storage._connection(subject) as c:
            row=c.execute(sql.SQL('SELECT '+_FIELDS+' FROM jarvis.memory_records WHERE id=%s'),(ident,)).fetchone()
            if row is None:raise HTTPException(404,'Memory record missing')
            if row['revision']!=revision:raise HTTPException(409,'Memory revision changed; refresh')
            if row['workshop_id'] is not None:
                member=c.execute('SELECT can_write FROM jarvis.memberships WHERE workshop_id=%s AND user_id=%s',
                                 (row['workshop_id'],subject)).fetchone()
                if not member or not member['can_write']:raise HTTPException(403,'Memory operation is not permitted')
            return row

    def index(self, subject, ident, revision, content_hash, embedding, namespace):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        if not isinstance(content_hash,str) or not _NAMESPACE.fullmatch(content_hash):
            raise HTTPException(422,'Invalid memory content hash')
        encoded,_=embedding_value(embedding,namespace)
        with self.storage._connection(subject) as c:
            row=c.execute(sql.SQL('UPDATE jarvis.memory_records SET embedding=%s::jarvis_extensions.vector,embedding_namespace=%s,revision=revision+1 WHERE id=%s AND revision=%s AND text_hash=%s RETURNING '+_FIELDS),
                          (encoded,namespace,ident,revision,content_hash)).fetchone()
            if row is None:
                self._failure(c,ident,revision)
            self._event(c,subject,'indexed',row)
            return row

    def semantic(self, subject, embedding, namespace, *, workshop_id=None, limit=5):
        subject=_ident(subject);_page(limit)
        encoded,dimensions=embedding_value(embedding,namespace);scope,args=_scope(workshop_id)
        with self.storage._connection(subject) as c:
            return c.execute(sql.SQL('''SELECT '''+_FIELDS+''',
                CASE WHEN embedding_namespace=%s AND jarvis_extensions.vector_dims(embedding)=%s
                THEN embedding OPERATOR(jarvis_extensions.<=>) %s::jarvis_extensions.vector END AS distance
                FROM jarvis.memory_records WHERE {} AND embedding_namespace=%s
                AND jarvis_extensions.vector_dims(embedding)=%s
                ORDER BY distance,id LIMIT %s''').format(scope),
                (namespace,dimensions,encoded,*args,namespace,dimensions,limit)).fetchall()
