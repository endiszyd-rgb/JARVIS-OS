"""Twilio inbound verification. Message bodies are data, never commands."""
import os
import re
from urllib.parse import parse_qsl
from fastapi import HTTPException
from twilio.request_validator import RequestValidator
from .network import validate_origin

NUMBER=re.compile(r'^whatsapp:\+[1-9][0-9]{6,14}$')
SID=re.compile(r'^(SM|MM)[0-9a-fA-F]{32}$')


def verify(body,signature,query=b''):
    if os.getenv('TWILIO_WEBHOOK_ENABLED','false').lower()!='true':
        raise HTTPException(503,'Twilio webhook disabled')
    secret=os.getenv('TWILIO_AUTH_TOKEN','')
    base=os.getenv('TWILIO_PUBLIC_ORIGIN','').rstrip('/')
    try:
        origin=validate_origin(base)
        if origin[0]!='https' or not secret: raise ValueError()
    except ValueError:
        raise HTTPException(503,'Configure HTTPS TWILIO_PUBLIC_ORIGIN and TWILIO_AUTH_TOKEN')
    if query:
        raise HTTPException(400,'Unexpected query parameters')
    try:
        pairs=parse_qsl(body.decode('utf-8'),keep_blank_values=True,strict_parsing=True,max_num_fields=100)
    except (UnicodeDecodeError,ValueError):
        raise HTTPException(400,'Invalid form body')
    # This endpoint intentionally rejects ambiguous duplicate parameters.
    if len({k for k,v in pairs})!=len(pairs):
        raise HTTPException(400,'Duplicate form parameters')
    params=dict(pairs)
    canonical=base+'/webhooks/twilio/whatsapp'
    if not signature or not RequestValidator(secret).validate(canonical,params,signature):
        raise HTTPException(403,'Invalid Twilio signature')
    if not SID.fullmatch(params.get('MessageSid','')) or not NUMBER.fullmatch(params.get('From','')) or not NUMBER.fullmatch(params.get('To','')):
        raise HTTPException(422,'Invalid WhatsApp identity or message SID')
    if params.get('AccountSid')!=os.getenv('TWILIO_ACCOUNT_SID','') or params.get('To')!=os.getenv('TWILIO_WHATSAPP_FROM',''):
        raise HTTPException(403,'Unexpected Twilio account or destination')
    allowed={v.strip() for v in os.getenv('WHATSAPP_ALLOWED_SENDERS','').split(',') if v.strip()}
    if params['From'] not in allowed:
        raise HTTPException(403,'Sender not allowed')
    if len(params.get('Body',''))>8000:
        raise HTTPException(422,'Message too long')
    return params
