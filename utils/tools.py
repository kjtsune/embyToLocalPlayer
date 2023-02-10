import json
import os.path
import re
import signal
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer
from typing import Union

from utils.configs import configs, MyLogger

_logger = MyLogger()


def run_server(req_handler):
    server_address = ('127.0.0.1', 58000)
    httpd = HTTPServer(server_address, req_handler)
    _logger.info('serving at %s:%d' % server_address)
    httpd.serve_forever()


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


def open_local_folder(data):
    if os.name != 'nt':
        _logger.info('open folder only work in windows')
        return
    from utils.windows_tool import open_in_explore
    path = data['info'][0]['content_path']
    translate_path = translate_path_by_ini(path)
    open_in_explore(translate_path)
    _logger.info('open folder', translate_path)


def play_media_file(data):
    save_path = data['info'][0]['save_path']
    big_file = sorted(data['file'], key=lambda i: i['size'], reverse=True)[0]['name']
    file_path = os.path.join(save_path, big_file)
    media_path = translate_path_by_ini(file_path)
    cmd = get_player_cmd(media_path)
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


def activate_window_by_pid(pid, is_mpv=False, scrip_name='autohotkey_tool', sleep=1.5):
    if os.name != 'nt':
        time.sleep(sleep)
        return
    if not is_mpv:
        # mpv vlc 不支持此模式
        # win32 api 激活窗口到前台的前提是：提出请求的进程需要在前台之类的。或者有输入什么的。
        pass
    #     time.sleep(1)
    #     log('active by win32 api mode')
    #     from windows_tool import activate_window_by_win32
    #     # time.sleep(0.5)
    #     activate_window_by_win32(pid)
    #     return
    # log('active by autohotkey mode')
    for script_type in '.exe', '.ahk':
        script_path = os.path.join(configs.cwd, 'utils', f'{scrip_name}{script_type}')
        if os.path.exists(script_path):
            _logger.info(script_path)
            subprocess.run([script_path, 'activate', str(pid)], shell=True)
            return


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
    path_match = [file_path.startswith(path) for path in enable_path]
    if any(path_match) or not enable_path:
        return True
    _logger.error(f'dandanplay {enable_path=} \n{path_match=}')


def translate_path_by_ini(file_path):
    config = configs.raw
    if 'src' in config and 'dst' in config and not file_path.startswith('http'):
        src = config['src']
        dst = config['dst']
        # 貌似是有序字典
        for k, src_prefix in src.items():
            if src_prefix not in file_path:
                continue
            dst_prefix = dst[k]
            tmp_path = file_path.replace(src_prefix, dst_prefix, 1)
            if os.path.exists(tmp_path):
                file_path = os.path.abspath(tmp_path)
                break
            else:
                _logger.debug(tmp_path, 'not found')
    return file_path


def get_player_cmd(media_path, dandan=False):
    config = configs.raw
    player = config['emby']['player']
    exe = config['exe'][player]
    exe = config['dandan']['exe'] if dandan else exe
    result = [exe, media_path]
    _logger.info(result, 'cmd')
    if not media_path.startswith('http') and not os.path.exists(media_path):
        raise FileNotFoundError(media_path)
    return result


def requests_urllib(host, params=None, _json=None, decode=False, timeout=2.0, headers=None, req_only=False,
                    http_proxy='', get_json=False, save_path='', retry=3, silence=False):
    _json = json.dumps(_json).encode('utf-8') if _json else None
    params = urllib.parse.urlencode(params) if params else None
    host = host + '?' + params if params else host
    req = urllib.request.Request(host)
    http_proxy = http_proxy or configs.script_proxy
    http_proxy and req.set_proxy(http_proxy, 'http')
    req.add_header('User-Agent', 'embyToLocalPlayer/1.1')
    headers and [req.add_header(k, v) for k, v in headers.items()]
    if _json:
        req.add_header('Content-Type', 'application/json; charset=utf-8')
    if req_only:
        return req

    response = None
    for try_times in range(1, retry + 1):
        try:
            response = urllib.request.urlopen(req, _json, timeout=timeout)
            break
        except socket.timeout:
            _logger.error(f'urllib {try_times=}', silence=silence)
            if try_times == retry:
                raise TimeoutError(f'{try_times=} {host=}')
        except Exception as e:
            _logger.info(f'urllib unknown error {try_times=}\n{host=}\n{str(e)[:50]}')
    if decode:
        return response.read().decode()
    if get_json:
        return json.loads(response.read().decode())
    if save_path:
        folder = os.path.dirname(save_path)
        if not os.path.exists(folder):
            os.mkdir(folder)
        with open(save_path, 'wb') as f:
            f.write(response.read())
        return save_path


def change_emby_play_position(scheme, netloc, item_id, api_key, stop_sec, play_session_id, device_id, **_):
    if stop_sec > 10 * 60 * 60:
        _logger.error('stop_sec error, check it')
        return
    ticks = stop_sec * 10 ** 7
    requests_urllib(f'{scheme}://{netloc}/emby/Sessions/Playing',
                    params={
                        'X-Emby-Token': api_key,
                        'X-Emby-Device-Id': device_id,
                    },
                    _json={
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                    })
    requests_urllib(f'{scheme}://{netloc}/emby/Sessions/Playing/Stopped',
                    params={
                        'X-Emby-Token': api_key,
                        'X-Emby-Device-Id': device_id,
                    },
                    _json={
                        'PositionTicks': ticks,
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                        # 'PlaylistIndex': 0,
                        # 'PlaybackRate': 1,
                        # 'PlaylistLength': 1,
                    })


def change_jellyfin_play_position(scheme, netloc, item_id, stop_sec, play_session_id, headers, **_):
    if stop_sec > 10 * 60 * 60:
        _logger.error('stop_sec error, check it')
        return
    ticks = stop_sec * 10 ** 7
    requests_urllib(f'{scheme}://{netloc}/Sessions/Playing',
                    headers=headers,
                    _json={
                        # 'PositionTicks': ticks,
                        # 'PlaybackStartTimeTicks': ticks,
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                        # 'MediaSourceId': 'a43d6333192f126508d93240ae5683c5',
                    })
    requests_urllib(f'{scheme}://{netloc}/Sessions/Playing/Stopped',
                    headers=headers,
                    _json={
                        'PositionTicks': ticks,
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                        # 'MediaSourceId': 'a43d6333192f126508d93240ae5683c5',
                    })


def change_plex_play_position(scheme, netloc, api_key, stop_sec, rating_key, client_id, duration, **_):
    if stop_sec > 10 * 60 * 60:
        _logger.error('stop_sec error, check it')
        return
    ticks = stop_sec * 10 ** 3
    requests_urllib(f'{scheme}://{netloc}/:/timeline',
                    decode=True,
                    headers={'Accept': 'application/json'},
                    params={
                        'ratingKey': rating_key,
                        'state': 'stopped',
                        # 'state': 'playing',
                        'time': ticks,
                        'duration': duration,
                        'X-Plex-Client-Identifier': client_id,
                        'X-Plex-Token': api_key,
                    })
    if stop_sec > 30:
        return
    requests_urllib(f'{scheme}://{netloc}/:/unscrobble',
                    headers={'Accept': 'application/json'},
                    params={
                        'key': rating_key,
                        'X-Plex-Client-Identifier': client_id,
                        'X-Plex-Token': api_key,
                        'identifier': 'com.plexapp.plugins.library',
                    })


emby_last_dict = dict(watched=True, stop_sec=0, data={}, normal_file=True)


def update_server_playback_progress(stop_sec, data, update_last=False):
    if not configs.raw.getboolean('emby', 'update_progress', fallback=True):
        return
    if stop_sec is None:
        _logger.error('stop_sec is None skip update progress')
        return
    file_path = data['file_path']
    ext = os.path.splitext(file_path)[-1].lower()
    # iso 回传会被标记已观看。
    normal_file = False if ext.endswith(('.iso', '.m3u8')) else True
    server = data['server']
    stop_sec = int(stop_sec)
    stop_sec = stop_sec - 2 if stop_sec > 5 else stop_sec

    if server == 'emby':
        if normal_file:
            change_emby_play_position(stop_sec=stop_sec, **data)
        # 4.7.8 开始：播放 A 到一半后退出，不刷新浏览器，播放 B，会清空 A 播放进度，故重复回传。
        # 播放完毕记录到字典
        if not update_last:
            watched = bool(stop_sec / data['total_sec'] > 0.9)
            _logger.debug('update emby_last_dict', data['basename'])
            emby_last_dict.update(dict(
                watched=watched,
                stop_sec=stop_sec,
                data=data,
                normal_file=normal_file,
            ))
            return
        # 浏览器刷新后重置数据
        elif data['fist_time']:
            emby_last_dict.update(dict(watched=True, stop_sec=0, data={}, normal_file=False))
        # 第二次播放时，回传上个文件被重置的进度。
        if not data['fist_time'] and emby_last_dict['data'] \
                and not emby_last_dict['watched'] and emby_last_dict['normal_file']:
            _logger.info('update again by check_last', emby_last_dict['data']['basename'], emby_last_dict['stop_sec'])
            change_emby_play_position(stop_sec=emby_last_dict['stop_sec'], **emby_last_dict['data'])
    elif not normal_file:
        pass
    elif server == 'jellyfin':
        change_jellyfin_play_position(stop_sec=stop_sec, **data)
    elif server == 'plex':
        change_plex_play_position(stop_sec=stop_sec, **data)


def parse_received_data_emby(received_data):
    mount_disk_mode = True if received_data['mountDiskEnable'] == 'true' else False
    url = urllib.parse.urlparse(received_data['playbackUrl'])
    headers = received_data['request']['headers']
    is_emby = True if '/emby/' in url.path else False
    jellyfin_auth = headers['X-Emby-Authorization'] if not is_emby else ''
    jellyfin_auth = [i.replace('\'', '').replace('"', '').strip().split('=')
                     for i in jellyfin_auth.split(',')] if not is_emby else []
    jellyfin_auth = dict((i[0], i[1]) for i in jellyfin_auth if len(i) == 2)

    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    item_id = [str(i) for i in url.path.split('/')]
    item_id = item_id[item_id.index('Items') + 1]
    media_source_id = query.get('MediaSourceId')
    api_key = query['X-Emby-Token'] if is_emby else jellyfin_auth['Token']
    netloc = url.netloc
    scheme = url.scheme
    device_id = query['X-Emby-Device-Id'] if is_emby else jellyfin_auth['DeviceId']
    sub_index = int(query.get('SubtitleStreamIndex', -1))

    data = received_data['playbackData']
    media_sources = data['MediaSources']
    play_session_id = data['PlaySessionId']
    if media_source_id:
        media_source_info = [i for i in media_sources if i['Id'] == media_source_id][0]
    else:
        media_source_info = media_sources[0]
        media_source_id = media_source_info['Id']
    file_path = media_source_info['Path']
    # stream_url = f'{scheme}://{netloc}{media_source_info["DirectStreamUrl"]}'
    container = os.path.splitext(file_path)[-1]
    extra_str = '/emby' if is_emby else ''
    stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/stream{container}' \
                 f'?MediaSourceId={media_source_id}&Static=true&api_key={api_key}'
    # 避免将内置字幕转为外挂字幕，内置字幕选择由播放器决定
    sub_index = sub_index if sub_index < 0 or media_source_info['MediaStreams'][sub_index]['IsExternal'] else -1
    sub_delivery_url = media_source_info['MediaStreams'][sub_index]['DeliveryUrl'] if sub_index >= 0 else None
    sub_file = f'{scheme}://{netloc}{sub_delivery_url}' if sub_delivery_url else None
    mount_disk_mode = True if force_disk_mode_by_path(file_path) else mount_disk_mode
    media_path = translate_path_by_ini(file_path) if mount_disk_mode else stream_url
    basename = os.path.basename(file_path)
    media_basename = os.path.basename(media_path)
    if file_path.endswith('.m3u8'):
        media_path = stream_url = file_path

    media_title = basename if not mount_disk_mode else None  # 播放http时覆盖标题

    seek = query['StartTimeTicks']
    start_sec = int(seek) // (10 ** 7) if seek else 0
    server = 'emby' if is_emby else 'jellyfin'

    fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
    total_sec = int(media_source_info['RunTimeTicks']) // 10 ** 7 if 'RunTimeTicks' in media_source_info else 10 ** 12
    position = start_sec / total_sec
    user_id = query['UserId']

    result = dict(
        server=server,
        mount_disk_mode=mount_disk_mode,
        api_key=api_key,
        scheme=scheme,
        netloc=netloc,
        media_path=media_path,
        start_sec=start_sec,
        sub_file=sub_file,
        media_title=media_title,
        play_session_id=play_session_id,
        device_id=device_id,
        headers=headers,
        item_id=item_id,
        file_path=file_path,
        stream_url=stream_url,
        fake_name=fake_name,
        position=position,
        total_sec=total_sec,
        user_id=user_id,
        basename=basename,
        media_basename=media_basename,
        fist_time=received_data['fistTime'],
    )
    return result


def parse_received_data_plex(received_data):
    mount_disk_mode = True if received_data['mountDiskEnable'] == 'true' else False
    url = urllib.parse.urlparse(received_data['playbackUrl'])
    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    api_key = query['X-Plex-Token']
    client_id = query['X-Plex-Client-Identifier']
    netloc = url.netloc
    scheme = url.scheme
    meta = received_data['playbackData']['MediaContainer']['Metadata'][0]
    data = meta['Media'][0]
    item_id = data['id']
    duration = data['duration']
    file_path = data['Part'][0]['file']
    stream_path = data['Part'][0]['key']
    stream_url = f'{scheme}://{netloc}{stream_path}?download=1&X-Plex-Token={api_key}'
    sub_path = [i['key'] for i in data['Part'][0]['Stream'] if i.get('key') and i.get('selected')]
    sub_file = f'{scheme}://{netloc}{sub_path[0]}?download=1&X-Plex-Token={api_key}' if sub_path else None

    mount_disk_mode = True if force_disk_mode_by_path(file_path) else mount_disk_mode
    media_path = translate_path_by_ini(file_path) if mount_disk_mode else stream_url
    basename = os.path.basename(file_path)
    media_basename = os.path.basename(media_path)
    media_title = basename if not mount_disk_mode else None  # 播放http时覆盖标题

    seek = meta.get('viewOffset')
    rating_key = meta['ratingKey']
    start_sec = int(seek) // (10 ** 3) if seek and not query.get('extrasPrefixCount') else 0

    fake_name = os.path.splitdrive(file_path)[1].replace('/', '..').replace('\\', '..')
    total_sec = int(meta['duration']) // (10 ** 3)
    position = start_sec / total_sec

    result = dict(
        server='plex',
        mount_disk_mode=mount_disk_mode,
        api_key=api_key,
        scheme=scheme,
        netloc=netloc,
        media_path=media_path,
        start_sec=start_sec,
        sub_file=sub_file,
        media_title=media_title,
        item_id=item_id,
        client_id=client_id,
        duration=duration,
        rating_key=rating_key,
        file_path=file_path,
        stream_url=stream_url,
        fake_name=fake_name,
        position=position,
        total_sec=total_sec,
        basename=basename,
        media_basename=media_basename,
    )
    return result
