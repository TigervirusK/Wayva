"""Bound JSON API request bodies, including streamed requests, before parsing."""
from starlette.responses import JSONResponse

MAX_API_BODY_BYTES = 128 * 1024


class ApiBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api') or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > MAX_API_BODY_BYTES:
                response = JSONResponse({'detail': 'This request is too large. Keep submitted data below 128 KiB.'}, status_code=413,
                                        headers={'Cache-Control': 'no-store, private', 'X-Content-Type-Options': 'nosniff'})
                return await response(scope, receive, send)
            chunks.append(message.get('body', b''))
            if not message.get('more_body', False):
                break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, bounded_receive, send)
