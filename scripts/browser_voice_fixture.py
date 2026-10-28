"""Loopback-only synthetic services for the optional Chromium voice check.

No inference or physical audio devices: Core, HTTP reply fixture and Wyoming
protocol fixture all run locally against a TemporaryDirectory database.
"""
import asyncio
from contextlib import nullcontext
import json
import math
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
KEY = 'browser-voice-synthetic-owner-key-32-chars'


def listening_socket():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    sock.setblocking(False)
    return sock


def microphone_wav(path):
    rate = 48000
    samples = []
    for index in range(rate * 4):
        second = index / rate
        # Silence and a clearly audible synthetic tone, never real speech.
        amplitude = 0.28 if 0.7 <= second < 2.2 else 0.0
        value = amplitude * math.sin(2 * math.pi * 440 * second)
        samples.append(struct.pack('<h', int(value * 32767)))
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, rate, 0, 'NONE', 'NONE'))
        output.writeframes(b''.join(samples))


async def run(folder):
    import uvicorn
    from fastapi import FastAPI, Request
    from wyoming.asr import Transcript
    from wyoming.audio import AudioStart, AudioChunk, AudioStop
    from wyoming.event import async_read_event, async_write_event

    state = {'stt': 0, 'tts': 0, 'model_requests': [], 'stt_bytes': [], 'failures': []}
    done = asyncio.Event()
    tasks = []

    async def wyoming(reader, writer):
        task = asyncio.current_task()
        tasks.append(task)
        try:
            first = await async_read_event(reader)
            if first.type == 'transcribe':
                size = 0
                for _ in range(1024):
                    event = await async_read_event(reader)
                    if event is None:
                        raise ValueError('incomplete synthetic input')
                    if event.type == 'audio-chunk':
                        chunk = AudioChunk.from_event(event)
                        assert (chunk.rate, chunk.width, chunk.channels) == (16000, 2, 1)
                        size += len(chunk.audio)
                    if event.type == 'audio-stop':
                        break
                assert size > 3200
                state['stt'] += 1
                state['stt_bytes'].append(size)
                texts = ['Jak działasz?', 'Druga wypowiedź', 'koniec rozmowy']
                text = texts[min(state['stt'] - 1, len(texts) - 1)]
                await async_write_event(Transcript(text=text).event(), writer)
            else:
                assert first.type == 'synthesize'
                state['tts'] += 1
                pcm = b''.join(struct.pack('<h', int(1500 * math.sin(2 * math.pi * 660 * index / 16000))) for index in range(4800))
                for event in (AudioStart(rate=16000, width=2, channels=1),
                              AudioChunk(rate=16000, width=2, channels=1, audio=pcm), AudioStop()):
                    await async_write_event(event.event(), writer)
        except Exception as error:
            state['failures'].append(type(error).__name__ + ': ' + str(error))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            tasks.remove(task)

    model_app = FastAPI()

    @model_app.post('/api/chat')
    async def model_reply(request: Request):
        data = await request.json()
        state['model_requests'].append(data)
        return {'message': {'content': 'Kontrolowana odpowiedź przeglądarki ' + str(len(state['model_requests'])) + '.'}}

    mic_path = Path(folder) / 'synthetic-microphone.wav'
    microphone_wav(mic_path)
    core_sock, model_sock = listening_socket(), listening_socket()
    stt_server = await asyncio.start_server(wyoming, '127.0.0.1', 0)
    wyoming_port = stt_server.sockets[0].getsockname()[1]
    core_port, model_port = core_sock.getsockname()[1], model_sock.getsockname()[1]
    os.environ.update(
        JARVIS_POSTGRES_DSN='', JARVIS_DB=str(Path(folder) / 'core.db'), JARVIS_API_KEY=KEY,
        JARVIS_VOICE_ENABLED='true', WYOMING_STT_URI=f'tcp://127.0.0.1:{wyoming_port}',
        WYOMING_TTS_URI=f'tcp://127.0.0.1:{wyoming_port}',
        JARVIS_NETWORK_ALLOWLIST='127.0.0.1/32', OLLAMA_URL=f'http://127.0.0.1:{model_port}',
        OLLAMA_ALLOWED_MODELS='browser:synthetic', OLLAMA_MODEL='browser:synthetic',
        JARVIS_RECEPTION_AI_ENABLED='false', JARVIS_EMBEDDINGS_ENABLED='false',
        TWILIO_WEBHOOK_ENABLED='false', HA_READONLY_ENABLED='false',
        AUTOLOGIKA_READONLY_ENABLED='false', AUTOLOGIKA_SNAPSHOT_ENABLED='false',
    )
    from jarvis.main import create_app
    app = create_app(Path(folder) / 'core.db', KEY)

    @app.get('/browser-fixture/state')
    def fixture_state():
        return state

    core = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, proxy_headers=False))
    model = uvicorn.Server(uvicorn.Config(model_app, log_level='error', access_log=False))
    # This harness owns signals, both servers share one loop.
    core.capture_signals = lambda: nullcontext()
    model.capture_signals = lambda: nullcontext()
    core_task = asyncio.create_task(core.serve(sockets=[core_sock]))
    model_task = asyncio.create_task(model.serve(sockets=[model_sock]))
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, done.set)
        except (NotImplementedError, RuntimeError):
            pass
    try:
        for _ in range(200):
            if core.started and model.started:
                break
            if core_task.done() or model_task.done():
                raise RuntimeError('synthetic server startup failed')
            await asyncio.sleep(0.025)
        else:
            raise RuntimeError('synthetic server startup timed out')
        print(json.dumps({'url': f'http://127.0.0.1:{core_port}', 'key': KEY,
                          'microphone': str(mic_path), 'source': 'synthetic_fixture'}), flush=True)
        await done.wait()
    finally:
        core.should_exit = model.should_exit = True
        stt_server.close()
        await stt_server.wait_closed()
        for task in tasks[:]:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.wait_for(asyncio.gather(core_task, model_task, return_exceptions=True), 10)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='jarvis-browser-voice-') as folder:
        asyncio.run(run(folder))
