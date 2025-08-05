import datetime
import os
import pathlib
import platform
import queue
import re
import shutil
import sys
import threading
import typing
from configparser import ConfigParser


def mini_conf():
    cwd = os.path.dirname(os.path.dirname(__file__))
    _platform = 'Android' if hasattr(sys, 'getandroidapilevel') else platform.system()
    path = [os.path.join(cwd, 'embyToLocalPlayer' + ext) for ext in (
        f'-{_platform}.ini', '.ini', '_config.ini') if ext]
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

LOG_LEVELS = {
    'ALL': 0,
    'TRACE': 5,
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}


class MyLogger:
    need_mix = True
    api_key = '_hide_api_key_'
    netloc = '_mix_netloc_'
    netloc_replace = '_mix_netloc_'
    user_name = os.getlogin()
    _log_queue = queue.SimpleQueue()

    def __init__(self):
        self.level = configs.log_level

    @staticmethod
    def log_printer_thread_start():
        def printer():
            while True:
                _str, end = MyLogger._log_queue.get()
                print(_str, end=end)

        threading.Thread(target=printer, daemon=True).start()

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
        t = f"[{datetime.datetime.now().strftime('%m-%d %H:%M:%S.%f')[:16]}] "
        args = ' '.join(str(i) for i in args)
        MyLogger._log_queue.put((t + args, end))

    def _log(self, *args, level=20, end=None, silence=False):
        if level >= self.level:
            self.log(*args, end=end, silence=silence)

    def all(self, *args, end=None, silence=False):
        self._log(*args, level=0, end=end, silence=silence)

    def trace(self, *args, end=None, silence=False):
        self._log(*args, level=5, end=end, silence=silence)

    def debug(self, *args, end=None, silence=False):
        self._log(*args, level=10, end=end, silence=silence)

    def info(self, *args, end=None, silence=False):
        if not silence and MyLogger.need_mix:
            args = self.mix_args_str(*args)
        self._log(*args, level=20, end=end, silence=silence)

    def warn(self, *args, end=None, silence=False):
        self._log(*args, level=30, end=end, silence=silence)

    def error(self, *args, end=None, silence=False):
        self._log(*args, level=40, end=end, silence=silence)


MyLogger.log_printer_thread_start()


class Configs:

    def __init__(self):
        self.platform = 'Android' if hasattr(sys, 'getandroidapilevel') else platform.system()
        self.cwd = os.path.dirname(os.path.dirname(__file__))
        self.path = [os.path.join(self.cwd, 'embyToLocalPlayer' + ext) for ext in (
            f'-{self.platform}.ini', '.ini', '_config.ini') if ext]
        self.path = [i for i in self.path if os.path.exists(i)][0]
        self.raw: ConfigParser = self.update()
        self.fullscreen = self.raw.getboolean('emby', 'fullscreen', fallback=True)
        self.speed_limit = self.raw.getfloat('gui', 'speed_limit', fallback=0)
        self.log_level = self.raw.get('dev', 'log_level', fallback='INFO')
        self.log_level = LOG_LEVELS.get(self.log_level.upper(), LOG_LEVELS['INFO'])
        self.disable_audio = self.raw.getboolean('dev', 'disable_audio', fallback=False)  # test in vm
        self.gui_is_enable = self.raw.getboolean('gui', 'enable', fallback=False)
        self.cache_path = self.raw.get('gui', 'cache_path', fallback=None)
        self.cache_db = self._get_cache_db()
        self.sys_proxy = self._get_sys_proxy()
        self.dl_proxy = self._get_proxy('download')
        self.script_proxy = self._get_proxy('script')
        self.player_proxy = self._get_proxy('player')
        if self.log_level < 20:
            print('dl_proxy:', self.dl_proxy)
            print('cache_db:', self.cache_db)

    def print_version(self):
        from utils.tools import show_version_info
        MyLogger.log(MyLogger.mix_args_str(f'Python path: {sys.executable}'))
        MyLogger.log(MyLogger.mix_args_str(f'ini path: {self.path}'))
        MyLogger.log(f'{platform.platform(True)} Python-{platform.python_version()} PyScript-{show_version_info()}')

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

    def ini_str_split(self, section, option, fallback='', split_by=',', zip_it=False, re_split_by=None):
        ini = self.raw.get(section, option, fallback=fallback).replace('：', ':').replace('，', ',').replace('；', ';')
        ini = [i.strip() for i in ini.split(split_by) if i.strip()]
        if ini and zip_it:
            if re_split_by:
                raise ValueError('re_split_by can not zip')
            return zip(ini[0::2], ini[1::2])
        if ini and re_split_by:
            res = []
            for group in ini:
                res.append([i.strip() for i in group.split(re_split_by) if i.strip()])
            return res
        return ini

    def _pot_version_is_too_high(self, player_path=''):
        player = self.raw['emby']['player']
        exe = self.raw['exe'].get(player, fallback='')
        if player_path:
            exe = player_path
        if 'potplayer' not in exe.lower():
            return

        exe = pathlib.Path(exe)
        pot_history = exe.parent / 'History' / 'English.txt'
        if not pot_history.exists():
            return
        with open(pot_history, 'r', encoding='utf-8') as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break
                if line.strip().startswith('[') and line.strip().endswith(']'):
                    version = line.strip()[1:-1]
                    if version.isdigit() and int(version) > 240618:
                        return version

    def media_title_translate(self, media_title=None, get_trans=False, log=True, player_path=''):
        if '--|--' in str(None):
            if get_trans:
                return
            return media_title
        map_pair = self.raw.get('dev', 'media_title_translate', fallback='')
        if not map_pair:
            if pot_ver := self._pot_version_is_too_high(player_path=player_path):
                map_pair = """'，＇，"，＂， ，-"""
                log and MyLogger.log(f'{pot_ver=}, gather than 240618, trans title to fix error')
        if not map_pair:
            if get_trans:
                return
            return media_title
        map_pair = map_pair.strip('，').split('，')
        map_dict = dict(zip(map_pair[0::2], map_pair[1::2]))
        trans = str.maketrans(map_dict)
        if get_trans:
            return trans
        media_title = media_title.translate(trans)
        return media_title

    def get_match_value(self, _str, section, option, split_by=';', map_by=':', get_ini_dict=False):
        ini_list = self.ini_str_split(section, option, split_by=split_by)
        ini_list = [pair.split(map_by) for pair in ini_list]
        ini_dict = {k.strip(): v.strip() for (k, v) in ini_list}
        if get_ini_dict:
            return ini_dict
        if match := re.search('|'.join(ini_dict.keys()), _str):
            return ini_dict[match[0]]

    def check_str_match(self, _str, section, option, return_value=False, log=True,
                        log_by: typing.Literal[True, False] = None, order_only=False, get_next=False, get_pair=False):
        # 注意 order_only 在匹配失败时返回 0
        ini_list = self.ini_str_split(section, option, fallback='')
        match_list = [i for i in ini_list if i in _str]
        match_order = ini_list.index(match_list[0]) + 1 if match_list else 0
        if get_next or get_pair:
            if match_list and match_order:
                if match_order % 2 == 0:
                    return
                if get_next and get_pair:
                    raise ValueError('get_next and get_pair can not enable in same time')
                try:
                    if get_next:
                        return ini_list[match_order]
                    if get_pair:
                        return ini_list[match_order - 1], ini_list[match_order]
                except IndexError:
                    MyLogger.log(f'{section} -> {option} match {match_list[0]} but not next value')
            return
        if ini_list and any(match_list):
            result = match_list[0] if return_value else True
            if order_only:
                result = match_order
        else:
            result = 0 if order_only else False
        _log = {True: "match", False: "not match"}[bool(result)]
        if log and ini_list:
            if log_by is not None and bool(log_by) != bool(result):
                return result
            _log = f'{_str} {_log}: {section}[{option}] {ini_list}'
            if MyLogger.need_mix:
                _log = MyLogger.mix_args_str(_log)
            MyLogger.log(_log)
        return result

    def string_replace_by_ini_pair(self, _str, section, option):
        if replace_pair := self.check_str_match(_str, section=section, option=option, get_pair=True):
            _str = _str.replace(replace_pair[0], replace_pair[1])
        return _str

    def get_server_api_by_ini(self, specify='', use_thin_api=True, get_dict=True, specify_host=''):
        server_list = self.ini_str_split('dev', 'server_data_group', split_by=';', re_split_by=',')
        api_dict = {}
        for server in server_list:
            server_name, host, api_key, user_id = server
            if specify and specify != server_name:
                continue
            if specify_host and specify_host not in host:
                continue
            if use_thin_api:
                from utils.emby_api_thin import EmbyApiThin
                api = EmbyApiThin(data=None, host=host, api_key=api_key, user_id=user_id)
            else:
                from utils.emby_api import EmbyApi
                api = EmbyApi(host=host, api_key=api_key, user_id=user_id,
                              http_proxy=self.script_proxy,
                              cert_verify=(
                                  not self.raw.getboolean('dev', 'skip_certificate_verify', fallback=False)), )
            api_dict[server_name] = api
            if specify or specify_host:
                return api
        if get_dict:
            return api_dict

    def set_player_path_by_mpv_embed_(self):
        ini_mpv = configs.raw.get('exe', 'mpv_embed', fallback='')
        embed_mpv = os.path.join(self.cwd, 'mpv_embed', 'mpv.exe')
        if not os.path.exists(embed_mpv) or ini_mpv == embed_mpv:
            return
        self.overwrite_value_to_ini('exe', 'mpv_embed', embed_mpv)
        self.overwrite_value_to_ini('emby', 'player', 'mpv_embed')
        MyLogger.log(f'use mpv_embed and overwrite ini because mpv_embed folder exists\n{embed_mpv}')

    def overwrite_value_to_ini(self, section, option, value, new_comment='', delete_only=False):
        with open(self.path, encoding='utf-8') as f:
            liens = list(f.readlines())
        str_list = []
        start_section = False
        end_section = False
        sect_str = f'[{section}]'
        option_index = -1
        for line in liens:
            if end_section:
                str_list.append(line)
                continue
            if line.startswith(sect_str):
                start_section = True
                str_list.append(line)
                if not delete_only:
                    if new_comment:
                        str_list.append(f'# {new_comment}\n')
                    str_list.append(f'{option} = {value}\n')
                option_index = len(str_list) - 1
                continue
            if start_section and line.startswith('['):
                end_section = True
                str_list.append(line)
                continue
            if start_section and line.startswith(option) and '=' in line:
                line_op = line.split('=', maxsplit=1)[0].strip()
                if line_op == option:
                    old_comm_list = []
                    while True:
                        old_comment = str_list[-1]
                        if old_comment.startswith(('#', ';')):
                            old_comm_list.append(old_comment)
                            del str_list[-1]
                        else:
                            break
                    if not delete_only and old_comm_list:
                        str_list[option_index:option_index] = old_comm_list
                    end_section = True
                    continue
            str_list.append(line)
        str_res = ''.join(str_list)
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(str_res)

    def backup_ini_file(self):
        today = datetime.date.today().strftime('%y%m%d')
        new = f'{self.path}-{today}.bak'
        if os.path.exists(new):
            for i in range(99):
                new = f'{self.path}-{today}-{i}.bak'
                if not os.path.exists(new):
                    break
        shutil.copy2(self.path, new)
        MyLogger.log(f'backup ini to {new}')

    def necessary_setting_when_server_start(self):
        self.set_player_path_by_mpv_embed_()
        is_new_subtitle_priority = False
        sub_priority = '中英特效, 双语特效, 简中特效, 简体特效, 特效, 中上, 中英, 双语, 简, simp, 中, chi, ass, srt, sup, und, ('
        sub_p_comment = '''字幕未选中时，尝试按顺序规则加载外挂字幕，规则间逗号隔开。
# 这些字符串是浏览器里选择字幕时，显示的名称小写化后的一部分。'''
        if configs.raw.get('dev', 'sub_lang_check', fallback=''):
            configs.backup_ini_file()
            MyLogger.log('breaking change: [dev] > sub_lang_check was replaced'
                         f' by [dev] > subtitle_priority. overwriting...\n{sub_priority}')
            self.overwrite_value_to_ini('dev', 'sub_lang_check', '', delete_only=True)
            self.overwrite_value_to_ini('dev', 'subtitle_priority', sub_priority, new_comment=sub_p_comment)
            is_new_subtitle_priority = True
        if configs.raw.get('playlist', 'subtitle_priority', fallback=''):
            configs.backup_ini_file()
            MyLogger.log('breaking change: [playlist] > subtitle_priority was replaced'
                         f' by [dev] > subtitle_priority. overwriting...\n{sub_priority}')
            self.overwrite_value_to_ini('playlist', 'subtitle_priority', '', delete_only=True)
            if not is_new_subtitle_priority:
                self.overwrite_value_to_ini('dev', 'subtitle_priority', sub_priority, new_comment=sub_p_comment)
        if strm_direct := configs.raw.get('dev', 'strm_direct', fallback='').strip():
            configs.backup_ini_file()
            MyLogger.log('breaking change: [dev] > strm_direct was replaced'
                         f' by [dev] > strm_direct_host. overwriting...')
            self.overwrite_value_to_ini('dev', 'strm_direct', '', delete_only=True)
            if strm_direct == 'yes':
                strm_direct_host = 'local, .\n'
            else:
                strm_direct_host = '\n'
            strm_host_comment = '启用直接播放 strm 内的文件链接，避免 Emby 中转，的服务器域名的关键词，逗号隔开。'
            self.overwrite_value_to_ini('dev', 'strm_direct_host', strm_direct_host, new_comment=strm_host_comment)


configs = Configs()
