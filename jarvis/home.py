"""Home Assistant REST state reader. No service calls are implemented."""
import asyncio
import os
import re
from fastapi import HTTPException
from . import network

ENTITY=re.compile(r'^[a-z_]+\.[a-z0-9_]+$')


def config():
    if os.getenv('HA_READONLY_ENABLED','false').lower()!='true':
        raise HTTPException(503,'Home Assistant read-only integration disabled')
    url=os.getenv('HA_URL','').rstrip('/')
    token=os.getenv('HA_TOKEN','')
    entities={x.strip() for x in os.getenv('HA_ALLOWED_ENTITIES','').split(',') if x.strip()}
    try:
        network.validate_origin(url)
        if not token or not token.isascii() or any(ord(c) < 32 for c in token) or len(token)>4096 or not entities or len(entities)>100 or any(not ENTITY.fullmatch(x) for x in entities):
            raise ValueError()
    except ValueError:
        raise HTTPException(503,'Configure HA_URL, HA_TOKEN and HA_ALLOWED_ENTITIES')
    return url,token,entities


async def states(entity=None):
    url,token,allowed=config()
    if entity and entity not in allowed:
        raise HTTPException(403,'Entity not on allowlist')
    async with asyncio.timeout(20):
        result=await network.json_request(url,'GET','/api/states'+('/'+entity if entity else ''),headers={'Authorization':'Bearer '+token})
    if entity:
        if not isinstance(result,dict) or result.get('entity_id')!=entity: raise ValueError('Invalid entity response')
        result=[result]
    elif not isinstance(result,list):
        raise ValueError('Invalid state response')
    return filtered(result, {entity} if entity else allowed)


def filtered(result, allowed):
    if not isinstance(result,list) or len(result)>10000:
        raise ValueError('Invalid state response')
    states=[]
    seen=set()
    for row in result:
        if not isinstance(row,dict) or row.get('entity_id') not in allowed:
            continue
        ident=row['entity_id']
        if ident in seen or not isinstance(row.get('state'),str) or len(row['state'])>4096:
            raise ValueError('Invalid state')
        attrs=row.get('attributes',{})
        if not isinstance(attrs,dict):raise ValueError('Invalid attributes')
        public={key:attrs[key] for key in ('friendly_name','unit_of_measurement') if isinstance(attrs.get(key),str)}
        item={'entity_id':ident,'state':row['state'],'attributes':public}
        if isinstance(row.get('last_changed'),str):item['last_changed']=row['last_changed']
        states.append(item);seen.add(ident)
    return {'mode':'live_readonly','states':states,'controls_enabled':False}
