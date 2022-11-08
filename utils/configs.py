import os.path
import platform
import time
from configparser import ConfigParser


# def MyLogger():
#     logger = logging.getLogger(__name__)
#     logger.setLevel(logging.INFO)
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.INFO)
#     logger.addHandler(ch)
#     return logger

class MyLogger:
    def __init__(self):
        self.debug_mode = configs.debug_mode

    @staticmethod
    def log(*args, end=None):
        t = time.strftime('%D %H:%M', time.localtime())
        print(t, *args, end=end)

    def info(self, *args, end=None):
        self.log(*args, end=end)

    def debug(self, *args, end=None):
        if self.debug_mode:
            self.log(*args, end=end)

    def error(self, *args, end=None):
        self.log(*args, end=end)


class Configs:
    def __init__(self):
        self.platform = platform.system()
        self.cwd = os.path.dirname(os.path.dirname(__file__))
        self.path = [os.path.join(self.cwd, 'embyToLocalPlayer' + ext) for ext in (
            f'-{self.platform}.ini', '.ini', '_config.ini')]
        self.path = [i for i in self.path if os.path.exists(i)][0]
        print(f'ini path: {self.path}')
        self.raw: ConfigParser = self.update()
        self.fullscreen = self.raw.getboolean('emby', 'fullscreen', fallback=False)
        self.speed_limit = self.raw.getfloat('dev', 'speed_limit', fallback=0)
        self.debug_mode = self.raw.getboolean('dev', 'debug', fallback=False)
        self.disable_audio = self.raw.getboolean('dev', 'disable_audio', fallback=False)  # test in vm
        self.gui_is_enable = self.raw.getboolean('gui', 'enable', fallback=False)
        self.cache_path = self.raw.get('gui', 'cache_path', fallback=None)
        _cache_db = os.path.join(self.cache_path, '.embyToLocalPlayer.json') if self.cache_path else None
        _dev_cache_db = os.path.join(self.cwd, 'z_cache.json')
        self.cache_db = _dev_cache_db if os.path.exists(_dev_cache_db) else _cache_db
        self.http_proxy = self.raw.get('gui', 'http_proxy', fallback=None)
        if self.debug_mode:
            print('http_proxy:', self.http_proxy)
            print('cache_db:', self.cache_db)

    def update(self):
        config = ConfigParser()
        config.read(self.path, encoding='utf-8-sig')
        self.raw = config
        return config

    def check_str_match(self, _str, section, option, return_value=False, log=True):
        ini_list = self.raw.get(section, option, fallback='').replace('，', ',')
        ini_list = [i.strip() for i in ini_list.split(',') if i]
        match_list = [i for i in ini_list if i in _str]
        if ini_list and any(match_list):
            result = match_list[0] if return_value else True
        else:
            result = False
        _log = {True: "match", False: "not match"}[bool(result)]
        if log:
            print(f'{_str} {_log}: {section}[{option}] {ini_list}')
        return result


configs = Configs()
