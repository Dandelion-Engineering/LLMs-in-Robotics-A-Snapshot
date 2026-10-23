"""Exact robot-only request vocabulary shared by all three broker layers.

No URL, destination, operator token, filesystem path or redirect is accepted.
The trusted Windows parent freezes the destination and robot capability for one
invocation; validation here is an additional boundary, not authentication.
"""
import json
import re

MAX_BODY = 65536
MAX_RESPONSE = 1048576
MAX_REQUEST_FRAME = 524288
MAX_RESPONSE_FRAME = 8 * 1048576
MAX_CONTINUITY = 32768


def allowed_route(method, path):
    if type(path) is not str or len(path) > 256:
        return False
    if method == 'POST':
        return path in ('/command', '/observe', '/handback', '/continuity')
    if method != 'GET':
        return False
    if path in ('/status', '/continuity', '/history'):
        return True
    if re.fullmatch(r'/command/[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', path):
        return True
    if re.fullmatch(r'/observation/overhead-[1-9][0-9]{0,19}\.png', path):
        return True
    match = re.fullmatch(r'/history\?after=(0|[1-9][0-9]{0,19})&limit=([1-9][0-9]{0,2})', path)
    return bool(match and int(match[2]) <= 200)


def finite_json(raw):
    def reject(value):
        raise ValueError('non-finite JSON')
    return json.loads(raw, parse_constant=reject)


def validate_request(request):
    if type(request) is not dict or set(request) != {'method', 'path', 'capability', 'body'}:
        raise ValueError('request fields')
    method, path, token, body = (request[k] for k in ('method', 'path', 'capability', 'body'))
    if not allowed_route(method, path):
        raise PermissionError('broker_route_denied')
    if type(token) is not str or len(token) > 256 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('capability format')
    if type(body) is not str or len(body.encode('utf-8')) > MAX_BODY:
        raise ValueError('body limit')
    if method == 'GET' and body:
        raise ValueError('GET body forbidden')
    if method == 'POST':
        decoded = finite_json(body) if body else {}
        if type(decoded) is not dict:
            raise ValueError('body must be object')
        if path == '/continuity':
            content = decoded.get('content')
            if set(decoded) != {'content'} or type(content) is not str or len(content.encode('utf-8')) > MAX_CONTINUITY:
                raise ValueError('continuity body limit')
    return request


def validate_response(response):
    if type(response) is not dict or set(response) != {'status', 'body'}:
        raise ValueError('response fields')
    if type(response['status']) is not int or not 200 <= response['status'] <= 599:
        raise ValueError('response status')
    if type(response['body']) is not str or len(response['body'].encode('utf-8')) > MAX_RESPONSE:
        raise ValueError('response limit')
    decoded = finite_json(response['body'])
    if type(decoded) is not dict or type(decoded.get('ok')) is not bool:
        raise ValueError('response JSON')
    return response


def error_response(status, code):
    return {'status': status, 'body': json.dumps({'ok': False, 'error': {'code': code}})}
