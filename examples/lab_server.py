"""Local synthetic integration lab: no devices or third-party accounts.
Run: python -m uvicorn examples.lab_server:app --host 127.0.0.1 --port 8765
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp=FastMCP('JARVIS synthetic lab',stateless_http=True,json_response=True)

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def read_temperature()->dict:
    """Read a synthetic temperature, not a physical sensor."""
    return {'entity_id':'sensor.lab_temperature','state':21.5,'unit':'°C','source':'synthetic_fixture'}

mcp_app=mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run(): yield

app=FastAPI(title='JARVIS synthetic lab',lifespan=lifespan)

@app.get('/lab/temperature',operation_id='read_temperature')
def temperature(): return read_temperature()

app.mount('/',mcp_app)
