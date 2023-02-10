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
    def log(*args, end=None, silence=False):
        if silence:
            return
        t = time.strftime('%D %H:%M', time.localtime())
        print(t, *args, end=end)

    def info(self, *args, end=None, silence=False):
        self.log(*args, end=end, silence=silence)

    def debug(self, *args, end=None, silence=False):
        if self.debug_mode:
            self.log(*args, end=end, silence=silence)

    def error(self, *args, end=None, silence=False):
        self.log(*args, end=end, silence=silence)


class Configs:
    def __init__(self):
        self.platform = platform.system()
        self.cwd = os.path.dirname(os.path.dirname(__file__))
        self.path = [os.path.join(self.cwd, 'embyToLocalPlayer' + ext) for ext in (
            f'-{self.platform}.ini', '.ini', '_config.ini')]
        self.path = [i for i in self.path if os.path.exists(i)][0]
        print(f'ini path: {self.path}')
        self.raw: ConfigParser = self.update()
        self.fullscreen = self.raw.getboolean('emby', 'fullscreen', fallback=True)
        self.speed_limit = self.raw.getfloat('dev', 'speed_limit', fallback=0)
        self.debug_mode = self.raw.getboolean('dev', 'debug', fallback=False)
        self.disable_audio = self.raw.getboolean('dev', 'disable_audio', fallback=False)  # test in vm
        self.gui_is_enable = self.raw.getboolean('gui', 'enable', fallback=False)
        self.cache_path = self.raw.get('gui', 'cache_path', fallback=None)
        self.cache_db = self._get_cache_db()
        self.dl_proxy = self._get_proxy('download')
        self.script_proxy = self._get_proxy('script')
        self.player_proxy = self._get_proxy('player')
        if self.debug_mode:
            print('dl_proxy:', self.dl_proxy)
            print('cache_db:', self.cache_db)

    def _get_cache_db(self):
        _cache_db = os.path.join(self.cache_path, '.embyToLocalPlayer.json') if self.cache_path else None
        _dev_cache_db = os.path.join(self.cwd, 'z_cache.json')
        return _dev_cache_db if os.path.exists(_dev_cache_db) else _cache_db

    def _get_proxy(self, for_what):
        p_map = dict(download=['gui', 'http_poxy', ''],
                     script=['dev', 'script_proxy', ''],
                     player=['dev', 'player_proxy', ''])
        *args, fallback = p_map[for_what]
        proxy = self.raw.get(*args, fallback=fallback)
        if 'socks' in proxy.lower():
            raise ValueError('only support http proxy')
        proxy = proxy.split('://')
        proxy = proxy[1] if len(proxy) == 2 else proxy[0]
        return proxy

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
