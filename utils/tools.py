import json
import os.path
import re
import signal
import subprocess
import threading
import time
import urllib.parse
from typing import Union

import unicodedata

from utils.configs import configs, MyLogger

_logger = MyLogger()


def logger_setup(api_key, netloc):
    if not configs.raw.getboolean('dev', 'mix_log', fallback=True):
        MyLogger.need_mix = False
        return
    MyLogger.api_key = api_key
    MyLogger.netloc = netloc
    MyLogger.netloc_replace = MyLogger.mix_host_gen(netloc)


def safe_deleter(file, ext: Union[str, list, tuple] = ('mkv', 'mp4', 'srt', 'ass')):
    ext = [ext] if isinstance(ext, str) else ext
    *_, f_ext = os.path.splitext(file)
    if f_ext.replace('.', '') in ext and os.path.exists(file):
        os.remove(file)
        return True


def clean_tmp_dir():
    tmp = os.path.join(configs.cwd, '.tmp')
    if os.path.isdir(tmp):
        for file in os.listdir(tmp):
            os.remove(os.path.join(tmp, file))


def scan_cache_dir():
    """:return dict(_id=i.name, path=i.path, stat=i.stat())"""
    return [dict(_id=i.name, path=i.path, stat=i.stat()) for i in os.scandir(configs.cache_path) if i.is_file()]


def load_json_file(file, error_return='list', encoding='utf-8'):
    try:
        with open(file, encoding=encoding) as f:
            _json = json.load(f)
    except (FileNotFoundError, ValueError):
        print(f'load json file fail, fallback to {error_return}')
        return dict(list=[], dict={})[error_return]
    else:
        return _json


def dump_json_file(obj, file, encoding='utf-8'):
    with open(file, 'w', encoding=encoding) as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


class ThreadWithReturnValue(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs, daemon=daemon)
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self):
        threading.Thread.join(self)
        return self._return


def open_local_folder(data):
    path = data.get('full_path') or data['info'][0]['content_path']
    translate_path = translate_path_by_ini(path)
    path = os.path.normpath(translate_path)
    # isdir = os.path.isdir(path)
    isdir = False if os.path.splitext(path)[1] else True
    windows = f'explorer "{path}"' if isdir else f'explorer /select, "{path}"'
    # -R 确保前台显示
    darwin = f'open -R "{path}"'
    linux = f'xdg-open "{path}"' if isdir else f'xdg-open "{os.path.dirname(path)}"'
    cmd = dict(windows=windows, darwin=darwin, linux=linux)[configs.platform.lower()]
    _logger.info(cmd)
    os.system(cmd)


def play_media_file(data):
    server_token = configs.raw.get('dev', 'http_server_token', fallback='')
    nas_href = configs.raw.get('dev', 'server_side_href', fallback='').strip().strip('/')
    href = data.get('href', '').rsplit(':', maxsplit=1)[0].strip('/')
    if not href:
        _logger.info('qb open file: userscript update needed.')
        return
    href = nas_href or f'{href}:58000'
    save_path = data['info'][0]['save_path']
    big_file = sorted(data['file'], key=lambda i: i['size'], reverse=True)[0]['name']
    file_path = os.path.join(save_path, big_file)
    media_path = translate_path_by_ini(file_path)
    if server_token and not os.path.exists(media_path):
        _, ext = os.path.splitext(file_path)
        params = {'token': server_token,
                  'file_path': file_path}
        params = {key: urllib.parse.quote(str(value)) for key, value in params.items()}
        query_str = '&'.join(f'{key}={value}' for key, value in params.items())
        media_path = f'{href}/play_media_file{ext}' + '?' + query_str
        _logger.info(f'{file_path=}')
    cmd = get_player_cmd(media_path, file_path=file_path)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid)


def kill_multi_process(name_re, not_re=None):
    if os.name == 'nt':
        from utils.windows_tool import list_pid_and_cmd
        pid_cmd = list_pid_and_cmd(name_re)
    else:
        ps_out = subprocess.Popen(['ps', '-eo', 'pid,command'], stdout=subprocess.PIPE,
                                  encoding='utf-8').stdout.readlines()
        pid_cmd = [i.strip().split(maxsplit=1) for i in ps_out[1:]]
        pid_cmd = [(int(pid), cmd) for (pid, cmd) in pid_cmd if re.search(name_re, cmd)]
    pid_cmd = [(int(pid), cmd) for (pid, cmd) in pid_cmd if not re.search(not_re, cmd)] if not_re else pid_cmd
    my_pid = os.getpid()
    for pid, _ in pid_cmd:
        if pid != my_pid:
            _logger.info('kill', pid, _)
            os.kill(pid, signal.SIGABRT)
    time.sleep(1)


def activate_window_by_pid(pid, sleep=0):
    if os.name != 'nt':
        time.sleep(1.5)
        return

    from utils.windows_tool import activate_window_by_win32

    def activate_loop():
        for _ in range(100):
            time.sleep(0.5)
            if activate_window_by_win32(pid):
                return

    threading.Thread(target=activate_loop).start()
    time.sleep(sleep)


def force_disk_mode_by_path(file_path):
    ini_str = configs.raw.get('dev', 'force_disk_mode_path', fallback='').replace('，', ',')
    if not ini_str:
        return False
    ini_tuple = tuple(i.strip() for i in ini_str.split(',') if i)
    check = file_path.startswith(ini_tuple)
    _logger.info('disk_mode check', check)
    return check


def use_dandan_exe_by_path(file_path):
    config = configs.raw
    dandan = config['dandan'] if 'dandan' in config.sections() else {}
    if not dandan or not file_path or not dandan.getboolean('enable'):
        return False
    enable_path = dandan.get('enable_path', '').replace('，', ',')
    enable_path = [i.strip() for i in enable_path.split(',') if i]
    path_match = [path in file_path for path in enable_path]
    if any(path_match) or not enable_path:
        return True
    _logger.error(f'dandanplay {enable_path=} \n{path_match=}')


def translate_path_by_ini(file_path, debug=False):
    config = configs.raw
    path_check = config.getboolean('dev', 'path_check', fallback=False)
    if 'src' in config and 'dst' in config and not file_path.startswith('http'):
        src = config['src']
        dst = config['dst']
        # 貌似是有序字典
        for k, src_prefix in src.items():
            if not file_path.startswith(src_prefix):
                continue
            dst_prefix = dst[k]
            tmp_path = file_path.replace(src_prefix, dst_prefix, 1)
            if not path_check:
                file_path = os.path.abspath(tmp_path)
                break
            elif os.path.exists(tmp_path):
                file_path = os.path.abspath(tmp_path)
                break
            else:
                # path_check = True and debug = True and exists = False
                _log = _logger.info if debug else _logger.debug
                _log('debug: dev > path_check: fail >', tmp_path)
    return file_path if file_path.startswith('http') else unicodedata.normalize('NFC', file_path)


def select_player_by_path(file_path):
    data = configs.raw.get('dev', 'player_by_path', fallback='')
    if not data:
        return False
    data = data.replace('：', ':').replace('，', ',').replace('；', ';')
    data = [i.strip() for i in data.split(';') if i]
    path_map = {}
    for rule in data:
        player, path = [i.strip() for i in rule.split(':', maxsplit=1)]
        for p in [i.strip() for i in path.split(',') if i]:
            path_map[p] = player
    result = [player for path, player in path_map.items() if path in file_path]
    return result[0] if result else False


def get_player_cmd(media_path, file_path):
    config = configs.raw
    player = config['emby']['player']
    try:
        exe = config['exe'][player]
    except KeyError:
        raise ValueError(f'{player=}, {player} not found, check config ini file') from None
    exe = config['dandan']['exe'] if use_dandan_exe_by_path(file_path) else exe
    if player_by_path := select_player_by_path(file_path):
        exe = config['exe'][player_by_path]
    result = [exe, media_path]
    _logger.info('command line:', result)
    if not media_path.startswith('http') and not os.path.exists(media_path):
        raise FileNotFoundError(f'{media_path}\nmay need to disable read disk mode, '
                                f'or enable path_check, see detail in FAQ')
    return result


def version_prefer_emby(sources):
    rules = configs.ini_str_split('dev', 'version_prefer')
    if not rules:
        return sources[0]
    rules = [i.lower() for i in rules]
    name_list = [os.path.basename(i).lower() for i in [s['Path'] for s in sources]]
    join_str = '_|_'
    name_all = join_str.join(name_list)
    for rule in rules:
        if rule not in name_all:
            continue
        name_all = name_all[:name_all.index(rule)]
        name_list = name_all.split(join_str)
        index = len(name_list) - 1
        _logger.info(f'version_prefer: success with {rule=}')
        return sources[index]
    _logger.info(f'version_prefer: fail')
    return sources[0]


def main_ep_to_title(main_ep_info):
    # movie
    if 'SeasonId' not in main_ep_info:
        if 'ProductionYear' not in main_ep_info:
            return f"{main_ep_info['Name']}"
        return f"{main_ep_info['Name']} ({main_ep_info['ProductionYear']})"
    # episode
    if 'ParentIndexNumber' not in main_ep_info or 'IndexNumber' not in main_ep_info:
        return f"{main_ep_info['SeriesName']} - {main_ep_info['Name']}"
    if 'IndexNumberEnd' not in main_ep_info:
        return f"{main_ep_info['SeriesName']} S{main_ep_info['ParentIndexNumber']}" \
               f":E{main_ep_info['IndexNumber']} - {main_ep_info['Name']}"
    return f"{main_ep_info['SeriesName']} S{main_ep_info['ParentIndexNumber']}" \
           f":E{main_ep_info['IndexNumber']}-{main_ep_info['IndexNumberEnd']} - {main_ep_info['Name']}"


def main_ep_intro_time(main_ep_info):
    res = {}
    chapters = [i for i in main_ep_info['Chapters'][:5] if i.get('MarkerType')
                and not str(i['StartPositionTicks']).endswith('000000000')
                and not (i['StartPositionTicks'] == 0 and i['MarkerType'] == 'Chapter')]
    if not chapters or len(chapters) > 2:
        return res
    for i in chapters:
        if i['MarkerType'] == 'IntroStart':
            res['intro_start'] = i['StartPositionTicks'] // (10 ** 7)
        elif i['MarkerType'] == 'IntroEnd':
            res['intro_end'] = i['StartPositionTicks'] // (10 ** 7)
    return res


def show_version_info(extra_data):
    py_script_version = '2024.06.06'
    gm_info = extra_data.get('gmInfo')
    user_agent = extra_data.get('userAgent')
    if not gm_info:
        _logger.info('userscript info not found, userscript update or reinstall needed')
        return
    _logger.info(f"PyScript/{py_script_version} UserScript/{gm_info['script']['version']}"
                 f" {gm_info['scriptHandler']}/{gm_info['version']}")
    _logger.info(user_agent)


def match_version_range(ver_str, ver_range='4.6.7.0-4.7.14.0'):
    def compare_version(version1, version2):
        v1_parts = [int(i) for i in version1.split('.')]
        v2_parts = [int(i) for i in version2.split('.')]
        max_length = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_length - len(v1_parts)))
        v2_parts.extend([0] * (max_length - len(v2_parts)))

        for v1, v2 in zip(v1_parts, v2_parts):
            if v1 < v2:
                return '<'
            elif v1 > v2:
                return '>'
        return '='

    ver_min, ver_max = ver_range.strip().split('-')
    if compare_version(ver_str, ver_min) in '>=' and compare_version(ver_str, ver_max) in '<=':
        return True
    return False


def sub_via_other_media_version(media_sources):
    if len(media_sources) == 1:
        return
    sub_match = {}
    for source in media_sources:
        media_streams = source['MediaStreams']
        sub_dict_list = [s for s in media_streams
                         if s['Type'] == 'Subtitle']
        for _sub in sub_dict_list:
            _sub['Order'] = configs.check_str_match(
                f"{str(_sub.get('Title', '') + ',' + _sub['DisplayTitle']).lower()}",
                'dev', 'sub_extract_priority', log=False, order_only=True)
        sub_dict_list = [i for i in sub_dict_list if i['Order'] != 0]
        sub_dict_list.sort(key=lambda s: s['Order'])
        sub_dict = sub_dict_list[0] if sub_dict_list else {}
        if sub_index := sub_dict.get('Index'):
            sub_match[f"{source['Id']}"] = source['Id'], sub_index, sub_dict['Codec']
    return sub_match


def show_confirm_button(message, width, height, result, fallback, timeout=3):
    import tkinter as tk
    res = fallback

    def _main():
        root = tk.Tk()
        root.title('Confirm Button')
        root.attributes('-topmost', True)
        root.bind('<Motion>', lambda i: root.attributes('-topmost', False))
        screenwidth = root.winfo_screenwidth()
        screenheight = root.winfo_screenheight()
        align_str = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
        root.geometry(align_str)
        root.resizable(width=False, height=False)

        def click():
            nonlocal res
            res = result
            root.destroy()

        tk.Button(root, height=height - 5, width=width - 5, text=message, command=click).pack()
        root.after(timeout * 1000, root.destroy)
        root.mainloop()

    _main()
    return res


def debug_beep_win32():
    if configs.debug_mode and os.name == 'nt':
        import winsound

        winsound.Beep(500, 2000)
