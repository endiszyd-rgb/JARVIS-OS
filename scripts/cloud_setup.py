"""Reproducible setup/checks for a separate Codex Cloud JARVIS repository."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import venv


def main():
    if sys.version_info[:2]!=(3,12):raise SystemExit('Use Python 3.12: python3.12 scripts/cloud_setup.py')
    root=Path(__file__).resolve().parents[1]
    folder=root/'.venv'
    python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():venv.EnvBuilder(with_pip=True).create(folder)
    def run(args,env=None):subprocess.run(args,cwd=root,env=env,check=True)
    run([str(python),'-c',"import sys; assert sys.version_info[:2]==(3,12), 'Recreate .venv using Python 3.12'"])
    run([str(python),'-m','pip','install','-r','requirements-dev.txt'])
    run([str(python),'-m','pip','check'])
    run([str(python),'scripts/check_master_plan.py'])
    with tempfile.TemporaryDirectory(prefix='jarvis-cloud-check-') as scratch:
        env=dict(os.environ,JARVIS_DB=str(Path(scratch)/'bootstrap.db'))
        # Force optional real integrations off during verification. Unit tests set their own configs.
        env.update(JARVIS_POSTGRES_DSN='',JARVIS_RECEPTION_AI_ENABLED='false',JARVIS_VOICE_ENABLED='false',JARVIS_EMBEDDINGS_ENABLED='false',TWILIO_WEBHOOK_ENABLED='false',HA_READONLY_ENABLED='false',AUTOLOGIKA_READONLY_ENABLED='false',AUTOLOGIKA_SNAPSHOT_ENABLED='false')
        run([str(python),'-m','pytest','-q'],env)
    if shutil.which('node'):
        npm = shutil.which('npm')
        if npm:
            run([npm,'--prefix','frontend','ci'])
            run([npm,'--prefix','frontend','test'])
            run([npm,'--prefix','frontend','run','build'])
        else:
            print('npm unavailable: React tests/build still required; Docker builds the UI independently.')
        for source in ('jarvis/app.js','jarvis/audio_client.js','jarvis/pcm_capture.js','jarvis/pcm_worklet.js','jarvis/audio_conversation.js','jarvis/voice_panel.js','jarvis/transport_panel.js'):run(['node','--check',source])
        for script in ('check_memory_ui.cjs','check_chat_memory_ui.cjs','check_audio_client.cjs','check_voice_ui.cjs','check_pcm_capture.cjs','check_audio_conversation.cjs','check_voice_panel.cjs','check_transport_panel.cjs'):
            run(['node','scripts/'+script])
    else:print('Node unavailable: JS syntax check still required before shipping UI changes.')

if __name__=='__main__':main()
