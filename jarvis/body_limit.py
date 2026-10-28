"""Bound HTTP request bodies before JSON/WAV parsing, including chunked uploads."""
class BodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        path=scope['path']
        if path.startswith('/api/v1/'):
            path='/api/'+path[len('/api/v1/'):]
        maximum=2*1024*1024 if path=='/api/voice/transcribe' and scope['method']=='POST' else 65536
        chunks=[];size=0
        while True:
            event=await receive()
            if event['type']=='http.disconnect':return
            block=event.get('body',b'');size+=len(block)
            if size>maximum:
                await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'text/plain'),(b'cache-control',b'no-store')]})
                return await send({'type':'http.response.body','body':b'Request too large'})
            chunks.append(block)
            if not event.get('more_body'):break
        body=b''.join(chunks);del chunks
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)
