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
DRAIN_BEGIN, DRAIN_ACK = 10, 11
OWNER_DRAIN_TIMEOUT = 25
MAX_FRAME_BYTES = 65536
MAX_CONNECTIONS = 16
PER_CHANNEL_QUEUE_BYTES = 1024 * 1024
AGGREGATE_QUEUE_BYTES = 4 * 1024 * 1024
# Two readexactly representations during its final bytes conversion plus one
# concurrent encoded output frame; raw FD adapters add no read-ahead queue.
FRAME_HEADROOM_BYTES = 3 * MAX_FRAME_BYTES
MAX_H2_STREAMS = 1024
MAX_TERMINAL_CONTROLS = 64
PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def metadata(payload):
    value = json.loads(payload.decode('utf-8'))
    if not isinstance(value, dict) or canonical(value) != payload:
        raise ValueError('Noncanonical metadata frame')
    return value


def validate(kind, channel, length):
    if type(kind) is not int or kind not in range(1, 12):
        raise ValueError('Unknown frame type')
    if type(channel) is not int or not 0 <= channel <= MAX_CONNECTIONS:
        raise ValueError('Channel bound')
    if (kind in (FINISH, FINISHED, READY, DRAIN_BEGIN, DRAIN_ACK)) != (channel == 0):
        raise ValueError('Owner/channel frame mismatch')
    if type(length) is not int or not 0 <= length <= MAX_FRAME_BYTES:
        raise ValueError('Frame payload bound')
    if kind in (OPEN, OPENED, HALF_CLOSE, FINISH, DRAIN_BEGIN, DRAIN_ACK) and length:
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
    Active RST_STREAM is counted; idle EOF rejects it. Only the declared
    pre-retirement upload CANCEL on a proved normally closed ID is separate.
    """
    def __init__(self):
        self.directions = {name: {'preface': 0 if name == 'upload' else len(PREFACE),
            'buffer': bytearray(), 'frame': None, 'continuation': None,
            'retirement_at_frame_start': None,
            'settings': False, 'frames': 0, 'bytes': 0, 'wire_bytes': 0, 'max_frame': 16384}
            for name in ('upload', 'download')}
        self.streams = {}
        self.last_stream = 0
        self.closed_streams = self.resets = 0
        self.reset_records = []
        self.goaway = {'upload': None, 'download': None}
        self.error = None
        self.retirement_streams = None
        self.retirement_last_stream = None
        self.first_rejection = None
        self._normal_close_proofs = {}
        self._normal_close_evicted = False
        self.terminal_control_records = []

    def begin_retirement(self):
        """Freeze the original stream frontier, before any shutdown payload.

        The returned value is a detached pre-retirement snapshot. No later
        FINISH, stream close or reset can extend its authorized stream set.
        Partial framing remains visible and must finish before final closure.
        """
        if self.retirement_streams is not None:
            raise ValueError('Duplicate HTTP/2 retirement')
        if self.error or self.resets:
            raise ValueError('HTTP/2 retirement follows reset or error')
        frontier = self.summary()
        self.retirement_streams = frozenset(self.streams)
        self.retirement_last_stream = self.last_stream
        return frontier

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
            state['preface'] += count; state['wire_bytes'] += count; view = view[count:]
        while view:
            if state['frame'] is None:
                if not state['buffer']:
                    state['retirement_at_frame_start'] = self.retirement_streams is not None
                count = min(9 - len(state['buffer']), len(view))
                state['buffer'].extend(view[:count]); view = view[count:]
                state['wire_bytes'] += count
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
                                  'flags': flags, 'stream': stream, 'prefix': bytearray(),
                                  'retirement_at_start': state['retirement_at_frame_start']}
            frame = state['frame']
            count = min(frame['left'], len(view))
            limit = 384 if frame['kind'] == 4 else 8
            frame['prefix'].extend(view[:min(count, max(0, limit - len(frame['prefix'])))])
            view = view[count:]; frame['left'] -= count; state['wire_bytes'] += count
            if frame['left']:
                return
            self._complete(direction, frame)
            state['frames'] += 1; state['frame'] = None

    def _complete(self, direction, frame):
        state = self.directions[direction]
        kind, flags, stream, size, prefix = (frame[n] for n in ('kind','flags','stream','size','prefix'))
        position = {'frame': state['frames'] + 1, 'end_byte': state['wire_bytes']}
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
                    if self.retirement_streams is not None:
                        # Retain only the fixed structural identity of the first
                        # rejected frame; never its prefix, headers or payload.
                        if self.first_rejection is None:
                            self.first_rejection = {
                                'schema': 'campaign002-h2-rejection-1',
                                'direction': direction, 'frame_type': kind,
                                'flags': flags, 'stream_id': stream,
                                'payload_length': size,
                                'active_at_rejection': stream in self.streams,
                                'in_original_frontier': stream in self.retirement_streams,
                                'original_last_stream_id': self.retirement_last_stream}
                        raise ValueError('HTTP/2 new stream after retirement')
                    if stream % 2 != 1 or stream <= self.last_stream or len(self.streams) >= MAX_H2_STREAMS:
                        raise ValueError('HTTP/2 stream reuse/order/bound')
                    self.last_stream = stream
                    self.streams[stream] = {'upload': False, 'download': False, 'download_headers': False,
                        'opened_upload': position, 'upload_closed': None, 'download_closed': None}
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
            if self.streams[stream][direction] and state['continuation'] is None:
                self.streams[stream][direction + '_closed'] = position
            self._retire(stream)
        elif kind == 3:
            if stream not in self.streams:
                code = int.from_bytes(prefix, 'big')
                if (direction == 'upload' and flags == 0 and code == 8
                        and self.retirement_streams is None and not frame['retirement_at_start']
                        and stream in self._normal_close_proofs
                        and not any(row['stream_id'] == stream for row in self.terminal_control_records)):
                    if len(self.terminal_control_records) >= MAX_TERMINAL_CONTROLS:
                        raise ValueError('HTTP/2 terminal control bound')
                    self.terminal_control_records.append({
                        'direction': direction, 'stream_id': stream, 'error_code': code,
                        **position,
                        'normal_close': {name: dict(value) for name, value in self._normal_close_proofs[stream].items()},
                        'opposite_observed_frames': self.directions['download']['frames']})
                    return
                if self.first_rejection is None:
                    self.first_rejection = {
                        'schema': 'campaign002-h2-reset-rejection-1',
                        'direction': direction, 'frame_type': kind,
                        'flags': flags, 'stream_id': stream,
                        'payload_length': size, 'error_code': int.from_bytes(prefix, 'big'),
                        'active_at_rejection': stream in self.streams,
                        'retiring': self.retirement_streams is not None,
                        'in_original_frontier': (stream in self.retirement_streams
                                                 if self.retirement_streams is not None else None),
                        'original_last_stream_id': self.retirement_last_stream,
                        'last_stream_id': self.last_stream,
                        'observed_normal_close': stream in self._normal_close_proofs,
                        'observed_reset': any(row['stream_id'] == stream for row in self.reset_records),
                        'normal_close_history_evicted': self._normal_close_evicted}
                raise ValueError('HTTP/2 reset on unavailable stream')
            code = int.from_bytes(prefix, 'big')
            if self.retirement_streams is not None and not frame['retirement_at_start']:
                raise ValueError('HTTP/2 reset began before retirement')
            if self.retirement_streams is not None and (code != 8 or stream not in self.retirement_streams):
                raise ValueError('HTTP/2 reset outside original retirement frontier')
            self.resets += 1; del self.streams[stream]
            if self.resets > MAX_H2_STREAMS:
                raise ValueError('HTTP/2 reset bound')
            self.reset_records.append({'direction': direction, 'stream_id': stream,
                                       'error_code': code})
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
            self._normal_close_proofs[stream] = {name: dict(value[name]) for name in
                                                ('opened_upload', 'upload_closed', 'download_closed')}
            if len(self._normal_close_proofs) > MAX_H2_STREAMS:
                del self._normal_close_proofs[min(self._normal_close_proofs)]
                self._normal_close_evicted = True

    def summary(self):
        frames = {d:not s['buffer'] and s['frame'] is None for d,s in self.directions.items()}
        headers = {d:s['continuation'] is None for d,s in self.directions.items()}
        settings = {d:s['settings'] for d,s in self.directions.items()}
        preface = self.directions['upload']['preface'] == len(PREFACE)
        value = {'schema': 'campaign002-passive-h2-3', 'error': self.error,
            'preface_complete': preface, 'settings_complete': all(settings.values()),
            'frames_complete': all(frames.values()), 'headers_complete': all(headers.values()),
            'frame_complete':frames, 'header_complete':headers, 'settings_by_direction':settings,
            'upload_complete':self.error is None and preface and settings['upload'] and frames['upload'] and headers['upload'],
            'open_streams': len(self.streams), 'closed_streams': self.closed_streams,
            'active_stream_ids': sorted(self.streams),
            'last_stream_id': self.last_stream, 'retiring': self.retirement_streams is not None,
            'reset_streams': self.resets, 'goaway': dict(self.goaway),
            'reset_records': [dict(row) for row in self.reset_records],
            'terminal_control_records': [{**row, 'normal_close': {
                name: dict(position) for name, position in row['normal_close'].items()}}
                for row in self.terminal_control_records],
            'frames': {d: s['frames'] for d,s in self.directions.items()},
            'bytes': {d: s['bytes'] for d,s in self.directions.items()}, 'max_streams': MAX_H2_STREAMS}
        # Successful and unrelated-failure schemas remain unchanged. The
        # existing endpoint snapshots carry this additive failed-run evidence.
        if self.first_rejection is not None:
            value['first_rejection'] = dict(self.first_rejection)
        return value

    def upload_eof(self):
        """Prove only the retired upload boundary; downloads may still drain."""
        value = self.summary()
        if not value['upload_complete']:
            raise ValueError('HTTP/2 upload EOF has incomplete structure')
        return value

    def idle_eof(self):
        value = self.summary()
        if (value['error'] or not all(value[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete'))
                or value['open_streams'] or value['reset_streams']):
            raise ValueError('HTTP/2 EOF is not proven clean and idle')
        return value
