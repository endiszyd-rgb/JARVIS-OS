"""Serve the built React application with a narrow, traversal-safe asset route."""
from pathlib import Path
import re
from fastapi import HTTPException
from fastapi.responses import FileResponse

ASSET = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.(?:js|css|svg|woff2|png|webp|ico)\Z')
DEFAULT_DIST = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'


def mount(app, directory=DEFAULT_DIST):
    base=Path(directory).resolve()

    @app.get('/control',include_in_schema=False)
    @app.get('/control/',include_in_schema=False)
    def index():
        path=base/'index.html'
        if not path.is_file():
            raise HTTPException(503,'Control Center is unavailable')
        return FileResponse(path,media_type='text/html')

    @app.get('/control/assets/{asset:path}',include_in_schema=False)
    def asset_file(asset:str):
        if not ASSET.fullmatch(asset):
            raise HTTPException(404,'Asset missing')
        path=(base/'assets'/asset).resolve()
        if not path.is_relative_to(base/'assets') or not path.is_file():
            raise HTTPException(404,'Asset missing')
        return FileResponse(path)
