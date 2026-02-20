#!/usr/bin/env python3
import evdev
import select
import sys
import threading

def check_stdin():
    # If stdin closes, the parent died or told us to stop
    sys.stdin.read()
    sys.exit(0)

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
        
    devices = {}
    try:
        epoll = select.epoll()
    except AttributeError:
        sys.exit(2)
        
    # Start a daemon thread to watch stdin so we know when to die gracefully
    t = threading.Thread(target=check_stdin, daemon=True)
    t.start()
        
    for arg in sys.argv[1:]:
        # format: /dev/input/eventX|persistent_id
        parts = arg.split("|", 1)
        if len(parts) == 2:
            path, pid = parts
            try:
                dev = evdev.InputDevice(path)
                devices[dev.fd] = (dev, pid)
                epoll.register(dev.fd, select.EPOLLIN)
            except Exception:
                pass
                
    if not devices:
        sys.exit(3)
        
    try:
        while True:
            events = epoll.poll(0.5)
            for fd, event_type in events:
                if fd in devices:
                    dev, pid = devices[fd]
                    try:
                        for event in dev.read():
                            if event.type == evdev.ecodes.EV_KEY:
                                if event.value != 0:  # Key down
                                    print(pid, flush=True)
                    except Exception:
                        pass
    except KeyboardInterrupt:
        pass
    finally:
        for fd, (dev, pid) in devices.items():
            try:
                epoll.unregister(fd)
                dev.close()
            except Exception:
                pass
        epoll.close()

if __name__ == "__main__":
    main()
