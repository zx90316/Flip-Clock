"""Bounded UART bench client. Only dev.py opens the port; no movement on module import."""
import binascii
import json
import secrets
import struct
import time

def frame(op,session,seq=0,args=(0,0,0,0)):
    body=struct.pack('<BBBBIIIIIIH',0xa5,1,op,0,session,seq,*args,0)
    return body+struct.pack('<H',binascii.crc_hqx(body,0xffff))

def decode(data):
    if len(data)!=32 or data[:2]!=b'\xa5\x01' or binascii.crc_hqx(data[:30],0xffff)!=struct.unpack_from('<H',data,30)[0]:
        raise ValueError('Invalid bench frame')
    return {'state':data[2],'flags':data[3],'session':struct.unpack_from('<I',data,4)[0],
            'job':struct.unpack_from('<I',data,8)[0],'executed':struct.unpack_from('<i',data,12)[0],
            'remaining':struct.unpack_from('<I',data,16)[0],'processed':struct.unpack_from('<I',data,20)[0],
            'error':data[28],'phase':data[29]}

class BenchClient:
    def __init__(self,device):
        self.device=device; self.session=secrets.randbelow(0xffffffff)+1; self.seq=0
    def read(self,seq=None):
        deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            line=self.device.readline().decode('ascii',errors='replace').strip()
            if line.startswith('E_'): raise RuntimeError(line)
            if not line.startswith('F '): continue
            value=decode(bytes.fromhex(line[2:]))
            if value['session']!=self.session: raise RuntimeError('Uno session changed; position unknown; no replay')
            if seq is None or value['processed']==seq: return value
        raise RuntimeError('No valid application response; no new movement sequence will be guessed')
    def send(self,op,args=(0,0,0,0)):
        if op in (1,3): seq=0
        else: self.seq+=1; seq=self.seq
        data=frame(op,self.session,seq,args)
        self.device.write(b'FRAME '+data.hex().encode()+b'\n')
        return self.read(None if op in (1,3) else seq)
    def poll(self):
        self.device.write(b'POLL\n'); return self.read()

    def run(self,steps=16,rate=30):
        if not 1<=steps<=256 or not 10<=rate<=50: raise ValueError('Bench requires 1..256 positive half-steps and 10..50 steps/s')
        self.device.write(b'BENCH ON\n')
        deadline=time.monotonic()+2; entered=False
        while time.monotonic()<deadline:
            line=self.device.readline().decode('ascii',errors='replace').strip()
            if line=='BENCH_ON': entered=True; break
            if line.startswith('E_'): raise RuntimeError(line+'; disconnect ESP I2C and reset Uno before bench')
        if not entered: raise RuntimeError('BENCH_ON not acknowledged')
        done=False
        try:
            self.send(1); self.send(3); self.send(0x13); self.send(3)
            armed=self.send(2,(rate,10000,0,0))
            if armed['error'] or not armed['flags']&2: raise RuntimeError('ARM rejected')
            status=self.send(0x10,(steps,rate,100,10000)); job=self.seq
            if status['error']: raise RuntimeError('MOVE rejected')
            deadline=time.monotonic()+12; next_beat=time.monotonic()
            while time.monotonic()<deadline:
                if time.monotonic()>=next_beat:
                    status=self.send(3); next_beat=time.monotonic()+0.25
                else: status=self.poll()
                if status['error'] or status['state']==5: raise RuntimeError('Uno fault: '+str(status))
                if status['state']==3:
                    if status['job']!=job or status['executed']!=steps or status['remaining'] or not status['flags']&8:
                        raise RuntimeError('DONE does not match submitted job')
                    stopped=self.send(0x12)
                    if stopped['error'] or stopped['flags']&2 or not stopped['flags']&8: raise RuntimeError('DISARM not confirmed')
                    done=True
                    return {'steps_sent':steps,'rate':rate,'position':'unknown','coil_outputs_zero':True,
                            'armed':False,'status':stopped,'mechanical_result':'operator observation required'}
                time.sleep(0.05)
            raise RuntimeError('Bench timeout')
        finally:
            if not done:
                try: self.send(0x11)
                except Exception: pass
            self.device.write(b'BENCH OFF\n')
            self.device.flush()
