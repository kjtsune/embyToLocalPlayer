import os.path
from configparser import ConfigParser


class Configs:
    def __init__(self, cwd, file_name):
        self.path = [os.path.join(cwd, file_name + i) for i in ('.ini', '_config.ini')]
        self.path = [i for i in self.path if os.path.exists(i)][0]
        self.raw = None
        self.update()

    def update(self):
        config = ConfigParser()
        config.read(self.path, encoding='utf-8-sig')
        self.raw = config
        return config
