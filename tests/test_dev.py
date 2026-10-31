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
            with self.assertRaises(RuntimeError): dev.choose_port('uno_motor')
    def test_one_port_and_saved_selection(self):
        with patch.object(dev,'ports',return_value=[SimpleNamespace(device='COM7')]),patch.object(dev,'settings',return_value={}):
            self.assertEqual(dev.choose_port('uno_motor'),'COM7')
        with patch.object(dev,'ports',return_value=[SimpleNamespace(device='COM7'),SimpleNamespace(device='COM8')]),patch.object(dev,'settings',return_value={'uno_motor_port':'COM8'}):
            self.assertEqual(dev.choose_port('uno_motor'),'COM8')
    def test_status_is_read_only_and_checks_version(self):
        device=FakeSerial([b'{"board":"UNO","firmware":"0.3.0","protocol":1,"armed":false,"coil_mask":0}\n'])
        with patch.object(dev,'open_serial',return_value=device),contextlib.redirect_stdout(io.StringIO()):
            result=dev.uno_status(record=False)
        self.assertFalse(result['armed'])
        self.assertEqual(device.writes,[b'STATUS\n'])
    def test_wrong_version_is_not_reported_as_success(self):
        device=FakeSerial([b'{"board":"UNO","firmware":"0.1.0","protocol":1,"armed":false,"coil_mask":0}\n'])
        with patch.object(dev,'open_serial',return_value=device),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError): dev.uno_status(record=False)
    def test_armed_is_not_safe_standby(self):
        device=FakeSerial([b'{"board":"UNO","firmware":"0.3.0","protocol":1,"armed":true,"coil_mask":1}\n'])
        with patch.object(dev,'open_serial',return_value=device),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError): dev.uno_status(record=False)
    def test_wifi_password_only_sent_to_device(self):
        device=FakeSerial([b'WIFI_SAVED\n']); output=io.StringIO()
        with patch.object(dev,'open_serial',return_value=device),patch('builtins.input',return_value='test-network'),patch.object(dev.getpass,'getpass',return_value='not-a-real-password'),contextlib.redirect_stdout(output):
            dev.wifi()
        self.assertNotIn('not-a-real-password',output.getvalue())
        self.assertEqual(json.loads(device.writes[0].decode()[5:])['password'],'not-a-real-password')

if __name__=='__main__': unittest.main()
