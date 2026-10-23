"""Fixed, bounded private framing and passive HTTP/2 lifecycle witness.

No application payload is interpreted, retained, rewritten or replayed.
"""
import asyncio
import hashlib
import json
import struct

MAGIC, VERSION = b'RCM3', 3
HEADER = struct.Struct('!4sBBII')
OPEN, OPENED, DATA, HALF_CLOSE, CLOSED, ERROR, FINISH, FINISHED, READY = range(1, 10)
MAX_FRAME_BYTES = 65536
MAX_CONNECTIONS = 16
PER_CHANNEL_QUEUE_BYTES = 1024 * 1024
AGGREGATE_QUEUE_BYTES = 4 * 1024 * 1024
# Two readexactly representations during its final bytes conversion plus one
# concurrent encoded output frame; raw FD adapters add no read-ahead queue.
FRAME_HEADROOM_BYTES = 3 * MAX_FRAME_BYTES
MAX_H2_STREAMS = 1024
PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def metadata(payload):
    value = json.loads(payload.decode('utf-8'))
    if not isinstance(value, dict) or canonical(value) != payload:
        raise ValueError('Noncanonical metadata frame')
    return value


def validate(kind, channel, length):
    if type(kind) is not int or kind not in range(1, 10):
        raise ValueError('Unknown frame type')
    if type(channel) is not int or not 0 <= channel <= MAX_CONNECTIONS:
        raise ValueError('Channel bound')
    if (kind in (FINISH, FINISHED, READY)) != (channel == 0):
        raise ValueError('Owner/channel frame mismatch')
    if type(length) is not int or not 0 <= length <= MAX_FRAME_BYTES:
        raise ValueError('Frame payload bound')
    if kind in (OPEN, OPENED, HALF_CLOSE, FINISH) and length:
        raise ValueError('Control payload must be empty')
    if kind in (DATA, CLOSED, ERROR, FINISHED, READY) and not length:
        raise ValueError('Missing frame payload')


def encode_frame(kind, channel, payload=b''):
    if not isinstance(payload, bytes):
        raise TypeError('Frame payload must be bytes')
    validate(kind, channel, len(payload))
    return HEADER.pack(MAGIC, VERSION, kind, channel, len(payload)) + payload


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()
        self.pending = None

    def feed(self, data):
        frames = []
        view = memoryview(data)
        while view:
            target = HEADER.size if self.pending is None else self.pending[2]
            take = min(target - len(self.buffer), len(view))
            self.buffer.extend(view[:take]); view = view[take:]
            if len(self.buffer) != target:
                break
            if self.pending is None:
                magic, version, kind, channel, length = HEADER.unpack(self.buffer)
                self.buffer.clear()
                if magic != MAGIC or version != VERSION:
                    raise ValueError('Frame magic/version differs')
                validate(kind, channel, length)
                self.pending = (kind, channel, length)
                if length:
                    continue
            kind, channel, _ = self.pending
            frames.append((kind, channel, bytes(self.buffer)))
            self.buffer.clear(); self.pending = None
        return frames

    def finish(self):
        if self.pending is not None or self.buffer:
            raise ValueError('Partial framing EOF')


async def read_frame(reader):
    try:
        header = await reader.readexactly(HEADER.size)
    except asyncio.IncompleteReadError as error:
        if not error.partial:
            return None
        raise ValueError('Partial framing header EOF') from error
    magic, version, kind, channel, length = HEADER.unpack(header)
    if magic != MAGIC or version != VERSION:
        raise ValueError('Frame magic/version differs')
    validate(kind, channel, length)
    try:
        return kind, channel, await reader.readexactly(length)
    except asyncio.IncompleteReadError as error:
        raise ValueError('Partial framing payload EOF') from error


async def write_frame(writer, kind, channel, payload=b''):
    writer.write(encode_frame(kind, channel, payload))
    await writer.drain()


class ByteCounter:
    def __init__(self):
        self.bytes, self.digest = 0, hashlib.sha256()

    def add(self, data):
        self.bytes += len(data); self.digest.update(data)

    def summary(self):
        return {'bytes': self.bytes, 'sha256': self.digest.hexdigest()}


class QueueBudget:
    def __init__(self, headroom_bytes=FRAME_HEADROOM_BYTES):
        if type(headroom_bytes) is not int or not 0 <= headroom_bytes < PER_CHANNEL_QUEUE_BYTES:
            raise ValueError('Invalid fixed framing headroom')
        self.headroom_bytes = headroom_bytes
        self.channels, self.total, self.maximum = {}, 0, 0
        self.channel_maximum = {}

    def reserve(self, channel, count):
        if type(count) is not int or count < 0:
            raise ValueError('Invalid queue count')
        value = self.channels.get(channel, 0) + count
        if value + self.headroom_bytes > PER_CHANNEL_QUEUE_BYTES or self.total + count + self.headroom_bytes > AGGREGATE_QUEUE_BYTES:
            raise ValueError('Channel queue bound')
        self.channels[channel] = value
        self.total += count
        self.maximum = max(self.maximum, self.total)
        self.channel_maximum[channel] = max(value, self.channel_maximum.get(channel,0))

    def release(self, channel, count):
        if count < 0 or self.channels.get(channel, 0) < count:
            raise ValueError('Queue accounting underflow')
        self.channels[channel] -= count; self.total -= count


class H2Witness:
    """Passive structural witness; bounded state, no HPACK or gRPC interpretation.

    Unknown extensions and PUSH_PROMISE fail closed. Large DATA is consumed
    incrementally. Only small control prefixes and <=64 SETTINGS are retained.
    RST_STREAM is counted, never converted to success; idle EOF rejects it.
    """
    def __init__(self):
        self.directions = {name: {'preface': 0 if name == 'upload' else len(PREFACE),
            'buffer': bytearray(), 'frame': None, 'continuation': None,
            'settings': False, 'frames': 0, 'bytes': 0, 'max_frame': 16384}
            for name in ('upload', 'download')}
        self.streams = {}
        self.last_stream = 0
        self.closed_streams = self.resets = 0
        self.reset_records = []
        self.goaway = {'upload': None, 'download': None}
        self.error = None

    def feed(self, direction, data):
        if self.error:
            raise ValueError(self.error)
        try:
            self._feed(direction, data)
        except (ValueError, KeyError) as error:
            self.error = str(error)
            raise ValueError(self.error) from error

    def _feed(self, direction, data):
        state = self.directions[direction]
        state['bytes'] += len(data)
        view = memoryview(data)
        if state['preface'] < len(PREFACE):
            count = min(len(view), len(PREFACE) - state['preface'])
            if view[:count] != PREFACE[state['preface']:state['preface'] + count]:
                raise ValueError('Invalid HTTP/2 preface')
            state['preface'] += count; view = view[count:]
        while view:
            if state['frame'] is None:
                count = min(9 - len(state['buffer']), len(view))
                state['buffer'].extend(view[:count]); view = view[count:]
                if len(state['buffer']) < 9:
                    return
                header = bytes(state['buffer']); state['buffer'].clear()
                size = int.from_bytes(header[:3], 'big')
                kind, flags = header[3], header[4]
                stream = int.from_bytes(header[5:], 'big')
                if stream & 0x80000000 or size > state['max_frame']:
                    raise ValueError('Invalid HTTP/2 frame bound/stream')
                if kind not in (0, 1, 2, 3, 4, 6, 7, 8, 9):
                    raise ValueError('Unsupported HTTP/2 frame type')
                allowed = {0: 9, 1: 45, 2: 0, 3: 0, 4: 1, 6: 1, 7: 0, 8: 0, 9: 4}[kind]
                if flags & ~allowed:
                    raise ValueError('Unknown HTTP/2 flags')
                if not state['settings'] and (kind != 4 or flags):
                    raise ValueError('HTTP/2 initial SETTINGS missing')
                pending = state['continuation']
                if pending is not None and (kind != 9 or stream != pending):
                    raise ValueError('Unfinished HTTP/2 header block')
                if kind == 9 and pending != stream:
                    raise ValueError('Unexpected HTTP/2 CONTINUATION')
                if (kind in (4, 6, 7)) != (stream == 0) and kind != 8:
                    raise ValueError('Invalid HTTP/2 stream scope')
                if kind == 4 and (size % 6 or size > 384 or flags and size):
                    raise ValueError('Invalid/bounded HTTP/2 SETTINGS')
                if kind in (2, 3, 6, 8) and size != {2: 5, 3: 4, 6: 8, 8: 4}[kind]:
                    raise ValueError('Invalid HTTP/2 control length')
                if kind == 7 and size < 8:
                    raise ValueError('Invalid HTTP/2 GOAWAY')
                state['frame'] = {'size': size, 'left': size, 'kind': kind,
                                  'flags': flags, 'stream': stream, 'prefix': bytearray()}
            frame = state['frame']
            count = min(frame['left'], len(view))
            limit = 384 if frame['kind'] == 4 else 8
            frame['prefix'].extend(view[:min(count, max(0, limit - len(frame['prefix'])))])
            view = view[count:]; frame['left'] -= count
            if frame['left']:
                return
            self._complete(direction, frame)
            state['frames'] += 1; state['frame'] = None

    def _complete(self, direction, frame):
        state = self.directions[direction]
        kind, flags, stream, size, prefix = (frame[n] for n in ('kind','flags','stream','size','prefix'))
        if kind == 4:
            state['settings'] = True
            if not flags:
                for offset in range(0, size, 6):
                    key = int.from_bytes(prefix[offset:offset+2], 'big')
                    value = int.from_bytes(prefix[offset+2:offset+6], 'big')
                    if key == 2 and value not in (0, 1) or key == 4 and value > 0x7fffffff:
                        raise ValueError('Invalid HTTP/2 setting value')
                    if key == 5:
                        if not 16384 <= value <= 16777215:
                            raise ValueError('Invalid HTTP/2 maximum frame')
                        opposite = 'download' if direction == 'upload' else 'upload'
                        self.directions[opposite]['max_frame'] = value
        elif kind in (0, 1, 9):
            if flags & 8 and (not size or prefix[0] >= size - (5 if kind == 1 and flags & 32 else 0)):
                raise ValueError('Invalid HTTP/2 padding')
            if kind == 1 and flags & 32:
                start = 1 if flags & 8 else 0
                if size < start + 5 or int.from_bytes(prefix[start:start+4], 'big') & 0x7fffffff == stream:
                    raise ValueError('Invalid HTTP/2 header priority')
            if kind == 1:
                if direction == 'upload' and stream not in self.streams:
                    if stream % 2 != 1 or stream <= self.last_stream or len(self.streams) >= MAX_H2_STREAMS:
                        raise ValueError('HTTP/2 stream reuse/order/bound')
                    self.last_stream = stream
                    self.streams[stream] = {'upload': False, 'download': False, 'download_headers': False}
                if stream not in self.streams or self.streams[stream][direction]:
                    raise ValueError('HTTP/2 headers on unavailable stream')
                if direction == 'download': self.streams[stream]['download_headers'] = True
                if not flags & 4: state['continuation'] = stream
            elif kind == 0:
                if stream not in self.streams or self.streams[stream][direction] or direction == 'download' and not self.streams[stream]['download_headers']:
                    raise ValueError('HTTP/2 DATA on unavailable stream')
            elif flags & 4:
                state['continuation'] = None
            if kind in (0, 1) and flags & 1:
                self.streams[stream][direction] = True
            self._retire(stream)
        elif kind == 3:
            if stream not in self.streams:
                raise ValueError('HTTP/2 reset on unavailable stream')
            self.resets += 1; del self.streams[stream]
            if self.resets > MAX_H2_STREAMS:
                raise ValueError('HTTP/2 reset bound')
            self.reset_records.append({'direction': direction, 'stream_id': stream,
                                       'error_code': int.from_bytes(prefix, 'big')})
        elif kind == 7:
            last = int.from_bytes(prefix[:4], 'big')
            if last & 0x80000000 or int.from_bytes(prefix[4:8], 'big'):
                raise ValueError('HTTP/2 GOAWAY error')
            if self.goaway[direction] is not None and last > self.goaway[direction]:
                raise ValueError('HTTP/2 GOAWAY increased last stream')
            self.goaway[direction] = last
        elif kind == 8 and (int.from_bytes(prefix, 'big') & 0x7fffffff) == 0:
            raise ValueError('HTTP/2 zero window increment')
        elif kind == 2 and int.from_bytes(prefix[:4], 'big') & 0x7fffffff == stream:
            raise ValueError('HTTP/2 priority self-dependency')

    def _retire(self, stream):
        value = self.streams.get(stream)
        if value and value['upload'] and value['download'] and all(s['continuation'] != stream for s in self.directions.values()):
            del self.streams[stream]; self.closed_streams += 1

    def summary(self):
        return {'schema': 'campaign002-passive-h2-3', 'error': self.error,
            'preface_complete': self.directions['upload']['preface'] == len(PREFACE),
            'settings_complete': all(s['settings'] for s in self.directions.values()),
            'frames_complete': all(not s['buffer'] and s['frame'] is None for s in self.directions.values()),
            'headers_complete': all(s['continuation'] is None for s in self.directions.values()),
            'open_streams': len(self.streams), 'closed_streams': self.closed_streams,
            'active_stream_ids': sorted(self.streams),
            'reset_streams': self.resets, 'goaway': dict(self.goaway),
            'reset_records': [dict(row) for row in self.reset_records],
            'frames': {d: s['frames'] for d,s in self.directions.items()},
            'bytes': {d: s['bytes'] for d,s in self.directions.items()}, 'max_streams': MAX_H2_STREAMS}

    def idle_eof(self):
        value = self.summary()
        if (value['error'] or not all(value[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete'))
                or value['open_streams'] or value['reset_streams']):
            raise ValueError('HTTP/2 EOF is not proven clean and idle')
        return value
