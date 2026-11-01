import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dev',ROOT/'tools/dev.py')
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)

class FakeSerial:
    port='COM_TEST'
    def __init__(self, lines): self.lines=list(lines); self.writes=[]
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def readline(self): return self.lines.pop(0) if self.lines else b''
    def write(self,value): self.writes.append(value)

class DevTests(unittest.TestCase):
    def test_no_port_does_not_guess(self):
        with patch.object(dev,'ports',return_value=[]),patch.object(dev,'settings',return_value={}):
            with self.assertRaises(RuntimeError): dev.choose_port('esp32_clock')
    def test_one_port_and_saved_selection(self):
        with patch.object(dev,'ports',return_value=[SimpleNamespace(device='COM7')]),patch.object(dev,'settings',return_value={}):
            self.assertEqual(dev.choose_port('esp32_clock'),'COM7')
        with patch.object(dev,'ports',return_value=[SimpleNamespace(device='COM7'),SimpleNamespace(device='COM8')]),patch.object(dev,'settings',return_value={'esp32_clock_port':'COM8'}):
            self.assertEqual(dev.choose_port('esp32_clock'),'COM8')
    def test_wifi_password_only_sent_to_device(self):
        device=FakeSerial([b'WIFI_SAVED\n']); output=io.StringIO()
        with patch.object(dev,'open_serial',return_value=device),patch('builtins.input',return_value='test-network'),patch.object(dev.getpass,'getpass',return_value='not-a-real-password'),contextlib.redirect_stdout(output):
            dev.wifi()
        self.assertNotIn('not-a-real-password',output.getvalue())
        self.assertEqual(json.loads(device.writes[0].decode()[5:])['password'],'not-a-real-password')

if __name__=='__main__': unittest.main()
