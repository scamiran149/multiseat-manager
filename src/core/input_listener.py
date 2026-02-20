import os
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

class InputListenerThread(QThread):
    # Emits the persistent_id of the device that was touched
    device_identified = pyqtSignal(str)

    def __init__(self, hardware_inputs):
        super().__init__()
        self.hardware_inputs = hardware_inputs
        self._running = True
        self.process = None

    def run(self):
        args = []
        for inp in self.hardware_inputs:
            # We only track valid "human" input devices passed from scanner
            if "error" in inp:
                continue
                
            for node in inp.get("nodes", []):
                args.append(f"/dev/input/{node}|{inp.get('persistent_id')}")

        if not args:
            return

        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        python_exec = os.path.join(app_dir, ".venv", "bin", "python3")
        listener_script = os.path.join(app_dir, "src", "core", "evdev_listener.py")
        
        cmd = ["pkexec", python_exec, listener_script] + args

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
            
            while self._running:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                
                pid = line.strip()
                if pid:
                    self.device_identified.emit(pid)
                    # Yield explicitly back to UI to prevent runaway loops if multiple keys are hit
                    self.msleep(100) 
                    
        except Exception:
            pass
        finally:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()

    def stop(self):
        self._running = False
        if self.process and self.process.stdin and not self.process.stdin.closed:
            try:
                self.process.stdin.close()  # Signal evdev_listener daemon thread to gracefully shut down
            except Exception:
                pass
        self.wait()
