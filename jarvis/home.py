"""Home Assistant REST state reader. No service calls are implemented."""
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
        if not token or not entities or any(not ENTITY.fullmatch(x) for x in entities):
            raise ValueError()
    except ValueError:
        raise HTTPException(503,'Configure HA_URL, HA_TOKEN and HA_ALLOWED_ENTITIES')
    return url,token,entities


async def states(entity=None):
    url,token,allowed=config()
    if entity and entity not in allowed:
        raise HTTPException(403,'Entity not on allowlist')
    result=await network.json_request(url,'GET','/api/states'+('/'+entity if entity else ''),headers={'Authorization':'Bearer '+token})
    if entity:
        if not isinstance(result,dict) or result.get('entity_id')!=entity: raise ValueError('Invalid entity response')
        result=[result]
    elif not isinstance(result,list):
        raise ValueError('Invalid state response')
    # Return only whitelisted entities; don't expose the full house inventory.
    return {'mode':'live_readonly','states':[row for row in result if isinstance(row,dict) and row.get('entity_id') in allowed], 'controls_enabled':False}
