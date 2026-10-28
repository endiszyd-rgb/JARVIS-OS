"""Optional local-notification scheduler; does not control external systems."""
import os
import time
import httpx

if __name__ == '__main__':
    key=os.getenv('JARVIS_SCHEDULER_TOKEN','')
    if len(key)<24:
        raise RuntimeError('Create a scheduler:tick token in Control Center and set JARVIS_SCHEDULER_TOKEN')
    while True:
        try:
            r = httpx.post(os.environ['CORE_URL']+'/api/automations/tick', headers={'X-Jarvis-Key': key}, json={}, timeout=10, trust_env=False)
            print('scheduler', r.status_code, flush=True)
        except httpx.HTTPError:
            print('scheduler: core unavailable; retrying', flush=True)
        time.sleep(30)
