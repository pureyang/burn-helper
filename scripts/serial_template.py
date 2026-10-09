import os, termios, time, select
fd = os.open('/dev/cu.usbmodem21101', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
import tty; tty.setraw(fd)
def rd(t=1.0):
    out=b''; end=time.time()+t
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.1)
        if r:
            try: out+=os.read(fd,4096); end=time.time()+0.4
            except BlockingIOError: pass
    return out.decode(errors='replace')
os.write(fd,b'\x03\x03'); rd(1)
os.write(fd,b'\x01'); rd(0.5)   # raw REPL
code = r'''
import sys, os, gc, machine
print(sys.version)
print(os.uname())
print("impl:", sys.implementation)
print("freq MHz:", machine.freq()/1e6)
gc.collect(); print("heap free/alloc:", gc.mem_free(), gc.mem_alloc())
try:
    s=os.statvfs('/'); print("flash fs total/free KB:", s[0]*s[2]//1024, s[0]*s[3]//1024)
except Exception as e: print(e)
print("files:", os.listdir('/'))
print("modules:", [m for m in ("badgeware","picographics","pimoroni","network","bluetooth","wifi","jpegdec","pngdec","qrcode","micropython") ])
help('modules')
'''
os.write(fd, code.encode()+b'\x04')
print(rd(4))
os.write(fd,b'\x02')
