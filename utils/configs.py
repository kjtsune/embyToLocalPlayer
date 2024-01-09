import os
import platform
import sys
import time
from configparser import ConfigParser


# def MyLogger():
#     logger = logging.getLogger(__name__)
#     logger.setLevel(logging.INFO)
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.INFO)
#     logger.addHandler(ch)
#     return logger

def mini_conf():
    cwd = os.path.dirname(os.path.dirname(__file__))
    path = [os.path.join(cwd, 'embyToLocalPlayer' + ext) for ext in (
        f'-{platform.system()}.ini', '.ini', '_config.ini')]
    path = [i for i in path if os.path.exists(i)][0]
    config = ConfigParser()
    config.read(path, encoding='utf-8-sig')
    return config

raw_stdout = sys.stdout
raw_stdout.reconfigure(encoding='utf-8-sig', errors='replace')


class Stdout:

    def __init__(self):
        self.log_file = mini_conf().get('dev', 'log_file', fallback='')
        if self.log_file:
            if self.log_file.startswith('./'):
                cwd = os.path.dirname(os.path.dirname(__file__))
                self.log_file = os.path.join(cwd, self.log_file.split('./', 1)[1])
            mode = 'a' if os.path.exists(self.log_file) and os.path.getsize(self.log_file) < 10 * 1024000 else 'w'
            if not os.path.exists(self.log_file):
                os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            self.log_file = open(self.log_file, mode, encoding='utf-8')

    def write(self, *args, end=''):
        log = str(*args) + end
        if MyLogger.need_mix:
            log = MyLogger.mix_args_str(log)[0]
        raw_stdout.write(log)
        if self.log_file:
            self.log_file.write(log)
            self.log_file.flush()

    def flush(self):
        pass


if mini_conf().get('dev', 'log_file', fallback=''):
    sys.stdout = Stdout()
    sys.stderr = sys.stdout


class MyLogger:
    need_mix = True
    api_key = '_hide_api_key_'
    netloc = '_mix_netloc_'
    netloc_replace = '_mix_netloc_'
    user_name = os.getlogin()

    def __init__(self):
        self.debug_mode = configs.debug_mode

    @staticmethod
    def mix_host_gen(netloc):
        host, *port = netloc.split(':')
        port = ':' + port[0] if port else ''
        new = host[:len(host) // 2] + '_mix_host_' + port
        return new

    @staticmethod
    def mix_args_str(*args):
        return [str(i).replace(MyLogger.api_key, '_hide_api_key_')
                .replace(MyLogger.netloc, MyLogger.netloc_replace)
                .replace(MyLogger.user_name, '_hide_user_')
                for i in args]

    @staticmethod
    def log(*args, end=None, silence=False):
        if silence:
            return
        t = f"[{time.strftime('%D %H:%M:%S', time.localtime())}] "
        args = ' '.join(str(i) for i in args)
        print(t + args, end=end)

    def info(self, *args, end=None, silence=False):
        if not silence and MyLogger.need_mix:
            args = self.mix_args_str(*args)
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
        MyLogger.log(MyLogger.mix_args_str(f'Python path: {sys.executable}'))
        MyLogger.log(MyLogger.mix_args_str(f'ini path: {self.path}'))
        MyLogger.log(f'{platform.platform(True)} Python-{platform.python_version()}')
        self.raw: ConfigParser = self.update()
        self.fullscreen = self.raw.getboolean('emby', 'fullscreen', fallback=True)
        self.speed_limit = self.raw.getfloat('dev', 'speed_limit', fallback=0)
        self.debug_mode = self.raw.getboolean('dev', 'debug', fallback=False)
        self.disable_audio = self.raw.getboolean('dev', 'disable_audio', fallback=False)  # test in vm
        self.gui_is_enable = self.raw.getboolean('gui', 'enable', fallback=False)
        self.cache_path = self.raw.get('gui', 'cache_path', fallback=None)
        self.cache_db = self._get_cache_db()
        self.sys_proxy = self._get_sys_proxy()
        self.dl_proxy = self._get_proxy('download')
        self.script_proxy = self._get_proxy('script')
        self.player_proxy = self._get_proxy('player')
        if self.debug_mode:
            print('dl_proxy:', self.dl_proxy)
            print('cache_db:', self.cache_db)

    def ini_str_split(self, section, option, fallback=''):
        ini = self.raw.get(section, option, fallback=fallback).replace('，', ',')
        ini = [i.strip() for i in ini.split(',') if i.strip()]
        return ini

    def _get_cache_db(self):
        _cache_db = os.path.join(self.cache_path, '.embyToLocalPlayer.json') if self.cache_path else None
        _dev_cache_db = os.path.join(self.cwd, 'z_cache.json')
        return _dev_cache_db if os.path.exists(_dev_cache_db) else _cache_db

    def _get_sys_proxy(self):
        if not self.raw.getboolean('dev', 'use_system_proxy', fallback=True):
            return
        import urllib.request
        proxy = urllib.request.getproxies().get('http')
        if not proxy:
            return
        print(f'system proxy: {proxy}')
        proxy = proxy.split('://')
        proxy = proxy[1] if len(proxy) == 2 else proxy[0]
        return proxy

    def _get_proxy(self, for_what):
        if self.sys_proxy:
            return self.sys_proxy
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
        self.fullscreen = self.raw.getboolean('emby', 'fullscreen', fallback=True)
        self.debug_mode = self.raw.getboolean('dev', 'debug', fallback=False)
        self.disable_audio = self.raw.getboolean('dev', 'disable_audio', fallback=False)  # test in vm
        self.gui_is_enable = self.raw.getboolean('gui', 'enable', fallback=False)
        self.sys_proxy = self._get_sys_proxy()
        self.dl_proxy = self._get_proxy('download')
        self.script_proxy = self._get_proxy('script')
        self.player_proxy = self._get_proxy('player')
        return config

    def check_str_match(self, _str, section, option, return_value=False, log=True):
        ini_list = self.ini_str_split(section, option, fallback='')
        match_list = [i for i in ini_list if i in _str]
        if ini_list and any(match_list):
            result = match_list[0] if return_value else True
        else:
            result = False
        _log = {True: "match", False: "not match"}[bool(result)]
        if log:
            _log = f'{_str} {_log}: {section}[{option}] {ini_list}'
            if MyLogger.need_mix:
                _log = MyLogger.mix_args_str(_log)
            MyLogger.log(_log)
        return result


configs = Configs()
