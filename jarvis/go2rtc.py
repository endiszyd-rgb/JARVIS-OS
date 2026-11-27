"""Built-in go2rtc for camera previews (bundled with the Windows installer).

JARVIS writes ``<data>/go2rtc/go2rtc.yaml`` from the cameras configured in the panel and runs
``go2rtc.exe -config go2rtc.yaml`` as a child process listening only on 127.0.0.1. The binary paths come
from ``JARVIS_GO2RTC_BIN`` / ``JARVIS_FFMPEG_BIN`` (set by the Windows launcher to the bundled
``tools`` folder); without them the built-in mode reports "not installed" and nothing is started.

The generated file holds the camera secrets (Tuya client secret, RTSP passwords) — it lives in the
private data folder next to the database, is rewritten on every change and is never served by JARVIS.
"""
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from . import cameras

log = logging.getLogger('jarvis.go2rtc')


def tuya_source(camera, tuya):
    """go2rtc Tuya Cloud API source: tuya://openapi.tuyaeu.com?device_id=..&uid=..&client_id=..&client_secret=.."""
    host = urlsplit(tuya.endpoint).hostname or 'openapi.tuyaeu.com'
    query = urlencode({'device_id': camera.device_id, 'uid': camera.uid, 'client_id': tuya.access_id,
                       'client_secret': tuya.access_secret, 'resolution': camera.resolution})
    return 'tuya://' + host + '?' + query


def render(config, tuya=None, ffmpeg=None):
    """Return (yaml_text, problems). JSON is valid YAML, which avoids any quoting/injection issues."""
    streams, problems = {}, []
    for camera in config.cameras:
        if not camera.enabled or camera.source == 'go2rtc':
            continue
        if camera.source == 'rtsp':
            if camera.rtsp_url:
                streams[camera.id] = camera.rtsp_url
            else:
                problems.append(camera.id + ': brak adresu RTSP')
        elif camera.source == 'tuya':
            if tuya is None or not tuya.access_id or not tuya.access_secret:
                problems.append(camera.id + ': zapisz dane chmury Tuya (Ustawienia → Brama → Setti / Tuya przez chmurę)')
            elif not camera.uid:
                problems.append(camera.id + ': kliknij „Sprawdź kamerę”, aby pobrać UID')
            else:
                streams[camera.id] = tuya_source(camera, tuya)
    document = {
        'api': {'listen': f'127.0.0.1:{cameras.BUILTIN_PORT}', 'origin': ''},
        'rtsp': {'listen': ''},          # JARVIS needs no RTSP server
        'log': {'level': 'info', 'format': 'text'},
        'streams': streams,
    }
    if ffmpeg:
        document['ffmpeg'] = {'bin': str(ffmpeg)}
    return json.dumps(document, indent=2, ensure_ascii=False) + '\n', problems


class Manager:
    """Starts, restarts and stops the bundled go2rtc. Safe to call from request handlers."""

    def __init__(self, data_dir, binary=None, ffmpeg=None, popen=None):
        self.folder = Path(data_dir) / 'go2rtc'
        self.binary = Path(binary) if binary else None
        self.ffmpeg = Path(ffmpeg) if ffmpeg else None
        self.popen = popen or subprocess.Popen
        self.process = None
        self.digest = None
        self.problems = []
        self.error = None
        self.lock = threading.Lock()
        self.reaped = False

    @classmethod
    def from_env(cls, data_dir):
        return cls(data_dir, os.environ.get('JARVIS_GO2RTC_BIN') or None, os.environ.get('JARVIS_FFMPEG_BIN') or None)

    @property
    def available(self):
        return self.binary is not None and self.binary.is_file()

    def running(self):
        return self.process is not None and self.process.poll() is None

    def status(self):
        return {'available': self.available, 'running': self.running(), 'ffmpeg': bool(self.ffmpeg and self.ffmpeg.is_file()),
                'problems': list(self.problems), 'error': self.error}

    def apply(self, config, tuya=None):
        """Bring go2rtc in line with the camera configuration; restarts only when the file changes."""
        with self.lock:
            wanted = config.mode == 'builtin' and config.enabled and any(c.enabled for c in config.cameras)
            if not wanted or not self.available:
                self._stop()
                self.problems = []
                self.error = None if self.available or not wanted else 'go2rtc nie jest zainstalowany'
                return self.status()
            text, self.problems = render(config, tuya, self.ffmpeg if self.ffmpeg and self.ffmpeg.is_file() else None)
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest == self.digest and self.running():
                return self.status()
            self._stop()
            self.folder.mkdir(parents=True, exist_ok=True)
            if not self.reaped:
                self.reaped = True
                self._reap_orphan()
            path = self.folder / 'go2rtc.yaml'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(text, encoding='utf-8')
            os.replace(temporary, path)
            try:
                logfile = open(self.folder / 'go2rtc.log', 'ab')
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
                self.process = self.popen([str(self.binary), '-config', str(path)], cwd=str(self.folder), stdin=subprocess.DEVNULL,
                                          stdout=logfile, stderr=subprocess.STDOUT, creationflags=flags)
                logfile.close()
                self.digest, self.error = digest, None
                (self.folder / 'go2rtc.pid').write_text(str(self.process.pid), encoding='ascii')
            except OSError as exc:
                self.process, self.digest = None, None
                self.error = 'Nie udało się uruchomić go2rtc: ' + exc.__class__.__name__
                log.warning('go2rtc start failed: %s', exc)
            return self.status()

    @staticmethod
    def _is_go2rtc(pid):
        """Only a process whose image really is go2rtc may be closed (PIDs get reused)."""
        try:
            if sys.platform == 'win32':
                output = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                                        timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
                return '"go2rtc.exe"' in output.lower()
            return 'go2rtc' in Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace')
        except (OSError, subprocess.SubprocessError, ValueError):
            return False

    def _reap_orphan(self):
        """A go2rtc left behind by a killed JARVIS would keep port 1984 with an old configuration."""
        marker = self.folder / 'go2rtc.pid'
        try:
            pid = int(marker.read_text(encoding='ascii').strip())
        except (OSError, ValueError):
            return
        if pid > 0 and pid != os.getpid() and self._is_go2rtc(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                log.info('Closed go2rtc left from a previous run (pid %s)', pid)
                time.sleep(0.5)
            except OSError:
                pass
        marker.unlink(missing_ok=True)

    def _stop(self):
        process, self.process, self.digest = self.process, None, None
        if process is None:
            return  # keep a marker from a previous run for _reap_orphan
        (self.folder / 'go2rtc.pid').unlink(missing_ok=True)
        if process.poll() is not None:
            return
        process.terminate()
        deadline = time.time() + 5
        while process.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            process.kill()

    def stop(self):
        with self.lock:
            self._stop()
