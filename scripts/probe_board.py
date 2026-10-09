import os, termios, time, select
fd = os.open('/dev/cu.usbmodem21101', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
import tty; tty.setraw(fd)
IDLE=0.4
def rd(t=1.0):
    out=b''; end=time.time()+t
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.1)
        if r:
            try: out+=os.read(fd,4096); end=time.time()+IDLE
            except BlockingIOError: pass
            except OSError: return out.decode(errors='replace')
    return out.decode(errors='replace')
os.write(fd,b'\x03\x03'); rd(1)
os.write(fd,b'\x01'); rd(0.5)   # raw REPL
code = r'''
import machine, rp2, os
wdt = machine.WDT(timeout=8000)
print("rp2:", [n for n in dir(rp2) if not n.startswith("_")])
try: print("bootsel_button:", rp2.bootsel_button())
except Exception as e: print("bootsel err", e)
try:
    f = rp2.Flash(); print("flash size MB:", f.ioctl(4,0)*f.ioctl(5,0)/1048576)
except Exception as e: print("flash err", e)
print("/system writable test:")
try:
    open("/system/.wtest","w").write("x"); os.remove("/system/.wtest"); print("  yes")
except Exception as e: print("  no", e)
try:
    st = os.statvfs("/system"); print("system fs KB total/free:", st[0]*st[2]//1024, st[0]*st[3]//1024)
except Exception as e: print(e)
print("mounts:", os.listdir("/"))
machine.reset()
'''
IDLE=15
os.write(fd, code.encode()+b'\x04')
print(rd(60))

