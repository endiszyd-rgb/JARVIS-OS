"""Owner-managed local identities; passwords and session secrets never enter audit."""
import uuid
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from . import identity

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Login(Strict):
    username:str=Field(pattern=r'^[a-z][a-z0-9_.-]{2,63}$')
    password:SecretStr

class UserCreate(Login):
    role:str=Field(min_length=1,max_length=40)

class UserChange(Strict):
    revision:int=Field(ge=0,strict=True)
    role:str|None=Field(default=None,min_length=1,max_length=40)
    enabled:bool|None=Field(default=None,strict=True)


def mount(router,db,owner_auth,self_auth,audit,config,ready):
    @router.post('/auth/login')
    def login(body:Login):
        if not ready():raise HTTPException(503,'Owner bootstrap configuration is incomplete')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            result=identity.issue_session(c,body.username,body.password.get_secret_value(),config.session_minutes*60)
            detail={'success':result is not None}
            if result:detail['subject']=result['user']['id']
            audit(c,'identity.login',detail)
        if result is None:raise HTTPException(401,'Invalid credentials')
        return result

    @router.get('/auth/me')
    def me(principal=Depends(self_auth)):
        return {'id':principal.id,'kind':principal.kind,'role':principal.role,
                'scopes':sorted(principal.scopes),'username':principal.username,'expires_at':principal.expires_at}

    @router.post('/auth/logout')
    def logout(principal=Depends(self_auth),x_jarvis_key:str|None=Header(default=None)):
        if principal.kind!='session':raise HTTPException(409,'Only a login session can be logged out here')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            ident=identity.logout(c,x_jarvis_key)
            if ident is None:raise HTTPException(401,'Unauthorized')
            audit(c,'identity.logout',{'id':ident})
        return {'revoked':ident}

    @router.get('/security/users',dependencies=[Depends(owner_auth)])
    def users():
        with db() as c:return identity.list_users(c)

    @router.post('/security/users',dependencies=[Depends(owner_auth)],status_code=201)
    def create_user(body:UserCreate):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            user=identity.create_user(c,body.username,body.password.get_secret_value(),body.role)
            audit(c,'identity.user_created',{'id':user['id'],'role':user['role']})
            return user

    @router.patch('/security/users/{ident}',dependencies=[Depends(owner_auth)])
    def change_user(ident:uuid.UUID,body:UserChange):
        if body.role is None and body.enabled is None:raise HTTPException(422,'Specify role or enabled')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            user=identity.change_user(c,str(ident),body.revision,role=body.role,enabled=body.enabled)
            audit(c,'identity.user_changed',{'id':user['id'],'role':user['role'],'enabled':user['enabled']})
            return user

    @router.get('/security/sessions',dependencies=[Depends(owner_auth)])
    def sessions():
        with db() as c:return identity.list_sessions(c)

    @router.delete('/security/sessions/{ident}',dependencies=[Depends(owner_auth)])
    def revoke(ident:uuid.UUID):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not identity.revoke_session(c,str(ident)):raise HTTPException(404,'Session missing')
            audit(c,'identity.session_revoked',{'id':str(ident)})
        return {'revoked':str(ident)}
