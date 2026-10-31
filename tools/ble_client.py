#!/usr/bin/env python3
"""Minimum-MTU BLE acceptance client. Pair via OS passkey prompt; no motor action on connect."""
import argparse
import asyncio
import json
from pathlib import Path
import time

SERVICE = 'b50c1000-7e6b-4e67-a540-a06c4fe1b201'
RX = 'b50c1001-7e6b-4e67-a540-a06c4fe1b201'
TX = 'b50c1002-7e6b-4e67-a540-a06c4fe1b201'
INFO = 'b50c1003-7e6b-4e67-a540-a06c4fe1b201'
STATE = Path(__file__).resolve().parents[1] / '.build/client-state.json'

class Client:
    def __init__(self, transport, state=STATE):
        self.transport = transport
        self.state_path = Path(state)
        self.boot = None
        self.counter = 0
        self.buffer = bytearray()
        self.pending = {}
        self.lock = asyncio.Lock()
        self.preview = None

    async def info(self):
        raw = bytes(await self.transport.read_gatt_char(INFO)).decode('ascii')
        version, firmware, boot = raw.split('|')
        if version != '1' or len(boot) != 8:
            raise RuntimeError('Unsupported device protocol')
        old = self.boot
        self.boot = boot
        if old is not None and old != boot:
            self.preview = None
            for future, _ in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError('Device restarted; inspect position before moving.'))
            self.pending.clear()
            raise RuntimeError('Device restarted. Command was not sent. Read status and reconfirm position.')
        return firmware, boot

    def next_id(self):
        key = f'{self.transport.address}|{self.boot}'
        try:
            data = json.loads(self.state_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            data = {}
        self.counter = max(self.counter + 1, int(data.get(key, 0)) + 1, int(time.time()))
        if self.counter > 0xFFFFFFFF:
            raise RuntimeError('Request ID exhausted; safe restart/reconfirm required')
        data[key] = self.counter
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temp.replace(self.state_path)
        return self.counter

    def receive(self, _characteristic, value):
        self.buffer.extend(value)
        if len(self.buffer) > 4096:
            raise RuntimeError('Device stream exceeded bounded receive buffer')
        while b'\n' in self.buffer:
            line, _, tail = self.buffer.partition(b'\n')
            self.buffer = bytearray(tail)
            if len(line) > 512:
                raise RuntimeError('Device JSON line exceeds 512 bytes')
            message = json.loads(line.decode('utf-8'))
            print(json.dumps(message, ensure_ascii=False), flush=True)
            if 'plan_id' in message:
                self.preview = message
            item = self.pending.get(message.get('id'))
            if item:
                future, messages = item
                messages.append(message)
                parts = message.get('parts', 1)
                received_parts = {m.get('part', 1) for m in messages if m.get('phase') == 'completed'}
                terminal = message.get('phase') == 'error' or len(received_parts) == parts
                if terminal and not future.done():
                    future.set_result(list(messages))

    async def request(self, op, wait=True, timeout=180, accept_timeout=4, **values):
        if any(k in values for k in ['id', 'v', 'boot_id', 'op']):
            raise ValueError('Client supplies protocol/session identifiers automatically')
        await self.info()
        request_id = self.next_id()
        payload = {'v': 1, 'id': request_id, 'boot_id': self.boot, 'op': op, **values}
        data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(data) > 512:
            raise ValueError('Command exceeds 512 UTF-8 bytes')
        data += b'\n'
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = (future, [])
        async def send_same():
            async with self.lock:
                # Exact same bytes and ID for every retry; check boot before each retransmission.
                await self.info()
                for start in range(0, len(data), 20):
                    await self.transport.write_gatt_char(RX, data[start:start + 20], response=True)
        try:
            for attempt in range(4):
                await send_same()
                try:
                    # Wait for an application response. GATT write ACK does not count.
                    deadline = asyncio.get_running_loop().time() + accept_timeout
                    while not self.pending[request_id][1] and not future.done():
                        if asyncio.get_running_loop().time() >= deadline:
                            raise asyncio.TimeoutError
                        await asyncio.sleep(0.02)
                    break
                except asyncio.TimeoutError:
                    if attempt == 3:
                        raise RuntimeError('No application response; inspect status. Do not resend with a new ID.')
            if not wait:
                # Completion indications continue to print while the REPL can send STOP.
                future.add_done_callback(lambda f, rid=request_id: self.pending.pop(rid, None))
                return self.pending.get(request_id, (None, []))[1]
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        finally:
            if wait or future.done():
                self.pending.pop(request_id, None)

    def disconnected(self):
        self.buffer.clear()
        for future, _ in self.pending.values():
            if not future.done():
                future.set_exception(RuntimeError('BLE disconnected; inspect status before another movement.'))

async def interactive(client):
    print('status, config, time, display HH:MM, jog N, pages N, preview, resume [large], pause, stop, save, clear, JSON, quit')
    while True:
        try:
            text = (await asyncio.to_thread(input, 'clock> ')).strip()
            if text in {'quit', 'exit'}:
                return
            if not text:
                continue
            args = text.split()
            names = {'status': 'get_status', 'config': 'get_config', 'preview': 'preview_sync',
                     'pause': 'pause', 'stop': 'stop', 'save': 'save_config', 'clear': 'clear_fault'}
            if args[0] in names:
                await client.request(names[args[0]], wait=args[0] not in {'pause', 'stop', 'save', 'clear'})
            elif args[0] == 'time':
                await client.request('set_time', utc_s=int(time.time()))
            elif args[0] == 'display':
                hour, minute = map(int, args[1].split(':'))
                await client.request('set_display', hour=hour, minute=minute, aligned=True)
            elif args[0] == 'jog':
                await client.request('jog_steps', steps=int(args[1]), wait=False)
            elif args[0] == 'pages':
                await client.request('advance_pages', pages=int(args[1]), wait=False)
            elif args[0] == 'resume':
                if not client.preview:
                    raise ValueError('Run preview first')
                await client.request('resume', plan_id=client.preview['plan_id'], confirm_large=args[1:] == ['large'])
            elif text.startswith('{'):
                obj = json.loads(text)
                op = obj.pop('op')
                if any(k in obj for k in ['id', 'boot_id', 'v']):
                    raise ValueError('Client supplies v/id/boot_id automatically')
                await client.request(op, **obj)
            else:
                print('Unknown command')
        except (ValueError, KeyError, IndexError, RuntimeError, asyncio.TimeoutError) as error:
            print(str(error))
        except EOFError:
            return

async def main():
    from bleak import BleakClient, BleakScanner
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address')
    parser.add_argument('--scan', action='store_true')
    parser.add_argument('--op', help='One operation; defaults to interactive session')
    parser.add_argument('--values', default='{}', help='JSON object of operation arguments')
    args = parser.parse_args()
    devices = await BleakScanner.discover(timeout=8, return_adv=True)
    matches = [d for d, advertisement in devices.values() if
               SERVICE in [s.lower() for s in advertisement.service_uuids] or (d.name or '').startswith('FlipClock-')]
    if args.scan:
        for device in matches:
            print(device.address, device.name)
        return
    device = next((d for d in matches if not args.address or d.address.lower() == args.address.lower()), None)
    if device is None or (not args.address and len(matches) != 1):
        raise RuntimeError('Use --scan and select one device with --address')
    client = None
    def disconnect(_):
        if client:
            client.disconnected()
    async with BleakClient(device, pair=True, timeout=120, disconnected_callback=disconnect) as transport:
        client = Client(transport)
        firmware, boot = await client.info()
        print('Connected firmware', firmware, 'boot', boot)
        await transport.start_notify(TX, client.receive)
        if args.op:
            await client.request(args.op, **json.loads(args.values))
        else:
            await client.request('get_status')
            await interactive(client)

if __name__ == '__main__':
    asyncio.run(main())
