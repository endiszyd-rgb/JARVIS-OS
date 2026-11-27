"""CI check of the bundled camera tools: a fake RTSP camera → built-in go2rtc (managed by JARVIS) → JPEG frame.

Usage (Windows runner): python scripts/camera_e2e_check.py <payload>/tools <workdir>
A helper go2rtc publishes a test pattern (ffmpeg lavfi, Windows Media Foundation H.264 encoder — the
LGPL ffmpeg build has no libx264) on rtsp://127.0.0.1:18554/test; jarvis.go2rtc.Manager then starts the
bundled go2rtc with one RTSP camera and the script fetches /api/frame.jpeg exactly like JARVIS does.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jarvis import cameras, go2rtc  # noqa: E402


def main():
    tools, work = Path(sys.argv[1]), Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    ffmpeg = tools / 'ffmpeg.exe'
    source = {
        'api': {'listen': '127.0.0.1:11984'}, 'rtsp': {'listen': '127.0.0.1:18554'}, 'webrtc': {'listen': ''},
        'ffmpeg': {'bin': str(ffmpeg)},
        'streams': {'test': 'exec:' + str(ffmpeg) + ' -hide_banner -re -f lavfi -i testsrc=size=320x240:rate=10'
                    ' -pix_fmt nv12 -c:v h264_mf -g 10 -f rtsp {output}'},
    }
    (work / 'source.yaml').write_text(json.dumps(source), encoding='utf-8')
    helper = subprocess.Popen([str(tools / 'go2rtc.exe'), '-config', str(work / 'source.yaml')], cwd=work,
                              stdout=open(work / 'source.log', 'wb'), stderr=subprocess.STDOUT)
    manager = go2rtc.Manager(work / 'data', tools / 'go2rtc.exe', ffmpeg)
    try:
        config = cameras.CameraConfig(mode='builtin', enabled=True, cameras=[
            {'id': 'test', 'name': 'Test', 'source': 'rtsp', 'rtsp_url': 'rtsp://127.0.0.1:18554/test'}])
        status = manager.apply(config)
        print('manager', status)
        assert status['running'], status
        deadline, last = time.time() + 60, None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:1984/api/frame.jpeg?src=test', timeout=15) as response:
                    data = response.read()
                if data.startswith(b'\xff\xd8'):
                    print('frame OK', len(data), 'bytes')
                    return 0
                last = 'not a JPEG'
            except Exception as exc:  # noqa: BLE001 - report the last failure
                last = repr(exc)
            time.sleep(2)
        print('no frame:', last)
        return 1
    finally:
        manager.stop()
        helper.terminate()
        for log in ('source.log', 'data/go2rtc/go2rtc.log'):
            path = work / log
            if path.exists():
                print('---', log, '---')
                print(path.read_text(encoding='utf-8', errors='replace')[-3000:])


if __name__ == '__main__':
    sys.exit(main())
