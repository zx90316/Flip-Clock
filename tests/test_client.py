import asyncio
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ble_client', ROOT / 'tools/ble_client.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Transport:
    address = 'simulation-only'
    boot = 'abcdef01'
    def __init__(self):
        self.buffer = bytearray()
        self.frames = []
        self.sizes = []
        self.client = None
        self.drop = 0
    async def read_gatt_char(self, uuid):
        return ('1|0.1.0|' + self.boot).encode()
    async def write_gatt_char(self, uuid, value, response):
        assert response is True
        self.sizes.append(len(value))
        self.buffer.extend(value)
        if not self.buffer.endswith(b'\n'):
            return
        data = bytes(self.buffer)
        self.buffer.clear()
        self.frames.append(data)
        if self.drop:
            self.drop -= 1
            return
        obj = json.loads(data)
        parts = 3 if obj['op'] == 'get_status' else 1
        for part in range(1, parts + 1):
            result = {'v': 1, 'id': obj['id'], 'phase': 'completed', 'part': part, 'parts': parts, 'text': '繁體中文'}
            wire = (json.dumps(result, ensure_ascii=False) + '\n').encode()
            for pos in range(0, len(wire), 20):
                self.client.receive(None, wire[pos:pos + 20])

class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.build')
        self.state = Path(self.temp.name) / 'ids.json'
        self.transport = Transport()
        self.client = module.Client(self.transport, self.state)
        self.transport.client = self.client
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()
    async def asyncTearDown(self):
        self.silence.__exit__(None, None, None)
        self.temp.cleanup()
    async def test_minimum_mtu_and_multipart_utf8(self):
        result = await self.client.request('get_status')
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]['text'], '繁體中文')
        self.assertTrue(all(1 <= n <= 20 for n in self.transport.sizes))
    async def test_retry_is_byte_identical(self):
        self.transport.drop = 1
        await self.client.request('stop', accept_timeout=0.03)
        self.assertEqual(len(self.transport.frames), 2)
        self.assertEqual(self.transport.frames[0], self.transport.frames[1])
    async def test_reboot_does_not_send_motion(self):
        await self.client.request('get_config')
        count = len(self.transport.frames)
        self.transport.boot = 'abcdef02'
        with self.assertRaisesRegex(RuntimeError, 'restarted'):
            await self.client.request('jog_steps', steps=4)
        self.assertEqual(count, len(self.transport.frames))
    async def test_ids_survive_client_restart(self):
        await self.client.request('get_config')
        first = json.loads(self.transport.frames[-1])['id']
        other = module.Client(self.transport, self.state)
        self.transport.client = other
        await other.request('get_config')
        self.assertGreater(json.loads(self.transport.frames[-1])['id'], first)
    async def test_client_owns_identifiers(self):
        with self.assertRaises(ValueError):
            await self.client.request('stop', id=1)
        self.assertEqual(self.transport.frames, [])
    async def test_byte_limit(self):
        with self.assertRaises(ValueError):
            await self.client.request('set_config', value='繁' * 300)
        self.assertEqual(self.transport.frames, [])
    async def test_nonblocking_request(self):
        result = await self.client.request('jog_steps', steps=4, wait=False)
        self.assertEqual(result[0]['phase'], 'completed')
        await asyncio.sleep(0)
        self.assertEqual(self.client.pending, {})

if __name__ == '__main__':
    unittest.main()
