"""Wyoming speech adapter. Explicit uploads only; no wake word or background mic.
Uses upstream MIT event/audio classes; engines run as independent services.
"""
import asyncio
from contextlib import asynccontextmanager
import io
import ipaddress
import json
import os
import socket
from urllib.parse import urlsplit
import wave
from fastapi import HTTPException
from wyoming.event import async_read_event,async_write_event
from wyoming.audio import AudioStart,AudioChunk,AudioStop
from wyoming.asr import Transcribe,Transcript
from wyoming.tts import Synthesize,SynthesizeVoice
from .network import allowed_networks,permitted

MAX_INPUT=2*1024*1024
MAX_OUTPUT=4*1024*1024


def enabled():
    if os.getenv('JARVIS_VOICE_ENABLED','false').lower()!='true':
        raise HTTPException(503,'Enable and configure local Wyoming voice services first')


async def target(variable):
    value=os.getenv(variable,'')
    p=urlsplit(value)
    try:
        port=p.port
        if p.scheme!='tcp' or not p.hostname or not port or p.username or p.password or p.path not in ('','/') or p.query or p.fragment:
            raise ValueError()
    except ValueError:raise HTTPException(503,'Configure a tcp://host:port Wyoming endpoint')
    records=await asyncio.to_thread(socket.getaddrinfo,p.hostname,port,0,socket.SOCK_STREAM)
    ips=list(dict.fromkeys(r[4][0] for r in records))
    networks=allowed_networks()
    if not ips or any(not permitted(ip,networks) or ipaddress.ip_address(ip).is_global for ip in ips):
        raise HTTPException(403,'Wyoming requires an allowed local/private IP; it has no built-in authentication or TLS')
    return ips[0],port


class LimitedReader:
    """Limit event allocations before upstream JSONL/PCM decoder reads a peer length."""
    def __init__(self,reader):self.reader=reader;self.total=0
    async def readline(self):
        line=await self.reader.readline()
        if len(line)>16384:raise ValueError('Oversized Wyoming event header')
        self.total+=len(line)
        if self.total>MAX_OUTPUT+262144:raise ValueError('Wyoming response too large')
        return line
    async def readexactly(self,n):
        if type(n) is not int or not 0<=n<=1024*1024 or self.total+n>MAX_OUTPUT+262144:
            raise ValueError('Invalid Wyoming event length')
        self.total+=n
        return await self.reader.readexactly(n)


@asynccontextmanager
async def connection(variable):
    host,port=await target(variable)
    reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port,limit=16384),5)
    try:yield LimitedReader(reader),writer
    finally:
        writer.close()
        try:await asyncio.wait_for(writer.wait_closed(),2)
        except (OSError,TimeoutError):pass


def pcm_from_wav(data):
    try:
        if len(data)>MAX_INPUT:raise ValueError()
        with wave.open(io.BytesIO(data),'rb') as wav:
            if (wav.getframerate(),wav.getsampwidth(),wav.getnchannels(),wav.getcomptype())!=(16000,2,1,'NONE'):
                raise ValueError()
            frames=wav.getnframes()
            if not 1<=frames<=16000*60:raise ValueError()
            pcm=wav.readframes(frames)
            if len(pcm)!=frames*2:raise ValueError()
        return pcm
    except (wave.Error,EOFError,ValueError):
        raise HTTPException(422,'Use a complete PCM WAV: 16 kHz, 16-bit, mono, up to 60 seconds')


async def transcribe(data):
    enabled();pcm=pcm_from_wav(data)
    try:
        async with asyncio.timeout(90):
            async with connection('WYOMING_STT_URI') as (reader,writer):
                await async_write_event(Transcribe(language='pl').event(),writer)
                await async_write_event(AudioStart(rate=16000,width=2,channels=1).event(),writer)
                for offset in range(0,len(pcm),3200):
                    await async_write_event(AudioChunk(rate=16000,width=2,channels=1,audio=pcm[offset:offset+3200]).event(),writer)
                await async_write_event(AudioStop().event(),writer)
                for _ in range(100):
                    event=await async_read_event(reader)
                    if event is None:break
                    if Transcript.is_type(event.type):
                        text=Transcript.from_event(event).text
                        if not isinstance(text,str) or len(text)>8000:raise ValueError('Invalid transcript')
                        return {'text':text,'language':'pl','source':'wyoming_stt','executed':False,'review_required':True}
                    if event.type=='error':raise ValueError('Speech service returned error')
        raise ValueError('No transcript returned')
    except HTTPException:raise
    except TimeoutError:raise HTTPException(504,'Speech service timed out')
    except Exception:raise HTTPException(502,'Wyoming speech recognition failed')


async def synthesize(text):
    enabled()
    if not text.strip() or len(text)>1000:raise HTTPException(422,'Use 1–1000 characters for speech')
    voice_name=os.getenv('WYOMING_TTS_VOICE','').strip()
    selected=SynthesizeVoice(name=voice_name) if voice_name else SynthesizeVoice(language='pl')
    try:
        async with asyncio.timeout(60):
            async with connection('WYOMING_TTS_URI') as (reader,writer):
                await async_write_event(Synthesize(text=text,voice=selected).event(),writer)
                fmt=None;audio=bytearray()
                for _ in range(2048):
                    event=await async_read_event(reader)
                    if event is None:break
                    if AudioStart.is_type(event.type):
                        if fmt is not None:raise ValueError('Duplicate audio start')
                        start=AudioStart.from_event(event)
                        fmt=(start.rate,start.width,start.channels)
                        if type(start.rate) is not int or not 8000<=start.rate<=48000 or start.width!=2 or start.channels not in (1,2):raise ValueError('Unsupported audio format')
                    elif AudioChunk.is_type(event.type):
                        chunk=AudioChunk.from_event(event)
                        if fmt!=(chunk.rate,chunk.width,chunk.channels) or len(chunk.audio)%(chunk.width*chunk.channels):raise ValueError('Audio format mismatch')
                        audio.extend(chunk.audio)
                        if len(audio)>MAX_OUTPUT or len(audio)>fmt[0]*fmt[1]*fmt[2]*120:raise ValueError('Audio too large')
                    elif AudioStop.is_type(event.type):
                        if not fmt or not audio:raise ValueError('No audio returned')
                        out=io.BytesIO()
                        with wave.open(out,'wb') as wav:
                            wav.setframerate(fmt[0]);wav.setsampwidth(fmt[1]);wav.setnchannels(fmt[2]);wav.writeframes(audio)
                        return out.getvalue()
                    elif event.type=='error':raise ValueError('Speech service error')
        raise ValueError('Incomplete speech response')
    except HTTPException:raise
    except TimeoutError:raise HTTPException(504,'Speech service timed out')
    except Exception:raise HTTPException(502,'Wyoming speech synthesis failed')
