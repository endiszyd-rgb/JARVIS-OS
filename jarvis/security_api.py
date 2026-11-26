"""Owner-managed local identities; passwords and session secrets never enter audit."""
import uuid
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from . import identity

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Credentials(Strict):
    username:str=Field(pattern=r'^[a-z][a-z0-9_.-]{2,63}$')
    password:SecretStr

class Login(Credentials):
    otp:SecretStr|None=None  # TOTP or backup code for accounts with a second factor

class UserCreate(Credentials):
    role:str=Field(min_length=1,max_length=40)

class MfaCode(Strict):
    code:SecretStr

class MfaDisable(Strict):
    password:SecretStr
    code:SecretStr

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
            result=identity.issue_session(c,body.username,body.password.get_secret_value(),config.session_minutes*60,
                                          otp=body.otp.get_secret_value() if body.otp is not None else None)
            mfa_required=result==identity.MFA_REQUIRED
            detail={'success':isinstance(result,dict)}
            if mfa_required:detail['mfa_required']=True
            if isinstance(result,dict):detail.update(subject=result['user']['id'],mfa=result['mfa'])
            audit(c,'identity.login',detail)
        if mfa_required:raise HTTPException(401,'Second factor required')
        if result is None:raise HTTPException(401,'Invalid credentials')
        return result

    @router.get('/auth/me')
    def me(principal=Depends(self_auth)):
        return {'id':principal.id,'kind':principal.kind,'role':principal.role,
                'scopes':sorted(principal.scopes),'username':principal.username,'expires_at':principal.expires_at,
                'mfa':principal.mfa}

    def account(principal):
        if principal.kind!='session':raise HTTPException(409,'Second factor belongs to an account; log in with a username')
        return principal

    @router.get('/auth/mfa')
    def mfa_status(principal=Depends(self_auth)):
        principal=account(principal)
        with db() as c:return identity.mfa_status(c,principal.id)

    @router.post('/auth/mfa/setup')
    def mfa_setup(principal=Depends(self_auth)):
        principal=account(principal)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            result=identity.mfa_begin(c,principal.id,principal.username)
            audit(c,'identity.mfa_setup_started',{'subject':principal.id})
        return result

    @router.post('/auth/mfa/enable')
    def mfa_enable(body:MfaCode,principal=Depends(self_auth)):
        principal=account(principal)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            result=identity.mfa_enable(c,principal.id,body.code.get_secret_value())
            audit(c,'identity.mfa_enabled',{'subject':principal.id})
        return result

    @router.post('/auth/mfa/disable')
    def mfa_disable(body:MfaDisable,principal=Depends(self_auth)):
        principal=account(principal)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                result=identity.mfa_disable(c,principal.id,body.password.get_secret_value(),body.code.get_secret_value())
            except HTTPException as exc:
                if exc.status_code!=401:raise
                c.rollback()
                with db() as log:audit(log,'identity.mfa_disable_failed',{'subject':principal.id})
                raise
            audit(c,'identity.mfa_disabled',{'subject':principal.id})
        return result

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

    @router.delete('/security/users/{ident}/mfa',dependencies=[Depends(owner_auth)])
    def reset_mfa(ident:uuid.UUID):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            result=identity.mfa_reset(c,str(ident))
            audit(c,'identity.mfa_reset',{'id':str(ident),'removed':result['reset']})
        return result

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
