from setuptools import setup, find_packages

setup(
    name="cyrix86",
    version="0.0.1",
    author="madhanmaaz",
    description="cyrix86 client app using socket.io.",
    packages=find_packages(),
    py_modules=["cyrix86"],
    install_requires=[
        "websocket-client==1.7.0",
        "python-socketio==5.11.2",
        "requests==2.31.0",
        "keyboard==0.13.5",
        "mss==9.0.1",
        "setuptools"
    ],
)
