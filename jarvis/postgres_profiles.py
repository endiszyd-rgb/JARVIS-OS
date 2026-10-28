"""Scoped owner profiles and immutable version reads, without model I/O."""
from fastapi import HTTPException
from psycopg import sql
from .postgres_store import _ident,_revision,PostgresStore
from .postgres_memory import _scope,_page
from .postgres_context import text

_FIELDS='id,owner_id,workshop_id,name,instructions,revision,created_at,updated_at'

class PostgresProfiles:
    def __init__(self,storage:PostgresStore):
        if not isinstance(storage,PostgresStore):raise ValueError('PostgresProfiles requires checked PostgresStore')
        self.storage=storage
    @staticmethod
    def _event(c,subject,row,event):
        c.execute('INSERT INTO jarvis.memory_profile_events(subject,profile_id,event,revision) VALUES(%s,%s,%s,%s)',(subject,row['id'],event,row['revision']))
    @staticmethod
    def _get(c,ident):
        row=c.execute('SELECT '+_FIELDS+' FROM jarvis.memory_profiles WHERE id=%s',(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Memory profile missing')
        return row
    @classmethod
    def _failure(cls,c,ident,revision):
        row=cls._get(c,ident)
        if row['revision']!=revision:raise HTTPException(409,'Profile revision changed; refresh')
        raise HTTPException(403,'Profile operation is not permitted')
    def get(self,subject,ident):
        with self.storage._connection(_ident(subject)) as c:return self._get(c,_ident(ident))
    def list(self,subject,*,workshop_id=None,limit=50,offset=0):
        _page(limit,offset);scope,args=_scope(workshop_id)
        with self.storage._connection(_ident(subject)) as c:
            return c.execute(sql.SQL('SELECT '+_FIELDS+' FROM jarvis.memory_profiles WHERE {} ORDER BY created_at DESC,id LIMIT %s OFFSET %s').format(scope),(*args,limit,offset)).fetchall()
    def create(self,subject,name,instructions,*,workshop_id=None):
        subject=_ident(subject);scope=_ident(workshop_id) if workshop_id is not None else None
        text(name,100);text(instructions,4000)
        with self.storage._connection(subject) as c:
            row=c.execute('INSERT INTO jarvis.memory_profiles(owner_id,workshop_id,name,instructions) VALUES(%s,%s,%s,%s) RETURNING '+_FIELDS,(subject,scope,name,instructions)).fetchone()
            self._event(c,subject,row,'created');return row
    def update(self,subject,ident,revision,name,instructions):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision);text(name,100);text(instructions,4000)
        with self.storage._connection(subject) as c:
            row=c.execute('UPDATE jarvis.memory_profiles SET name=%s,instructions=%s,revision=revision+1 WHERE id=%s AND revision=%s RETURNING '+_FIELDS,(name,instructions,ident,revision)).fetchone()
            if row is None:self._failure(c,ident,revision)
            self._event(c,subject,row,'updated');return row
    def delete(self,subject,ident,revision):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        with self.storage._connection(subject) as c:
            row=c.execute('DELETE FROM jarvis.memory_profiles WHERE id=%s AND revision=%s RETURNING id,revision',(ident,revision)).fetchone()
            if row is None:self._failure(c,ident,revision)
            self._event(c,subject,row,'deleted');return {'deleted':str(ident)}
    def history(self,subject,ident,limit=50,offset=0):
        _page(limit,offset);ident=_ident(ident)
        with self.storage._connection(_ident(subject)) as c:
            self._get(c,ident)
            return c.execute('SELECT * FROM jarvis.memory_profile_versions WHERE profile_id=%s ORDER BY revision DESC LIMIT %s OFFSET %s',(ident,limit,offset)).fetchall()
    def memory_history(self,subject,ident,limit=50,offset=0):
        _page(limit,offset);ident=_ident(ident)
        with self.storage._connection(_ident(subject)) as c:
            row=c.execute('SELECT id,revision FROM jarvis.memory_records WHERE id=%s',(ident,)).fetchone()
            if row is None:raise HTTPException(404,'Memory record missing')
            versions=c.execute('SELECT * FROM jarvis.memory_versions WHERE memory_id=%s ORDER BY revision DESC LIMIT %s OFFSET %s',(ident,limit,offset)).fetchall()
            return {'id':ident,'current_revision':row['revision'],'versions':versions,'history_before_feature3_available':False}
