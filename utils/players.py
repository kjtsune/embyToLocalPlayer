import base64
import os.path
import platform
import re
import subprocess
import threading
import time
import urllib.parse
from html.parser import HTMLParser

from utils.configs import configs, MyLogger
from utils.downloader import Downloader
from utils.python_mpv_jsonipc import MPV
from utils.tools import (activate_window_by_pid, requests_urllib, update_server_playback_progress,
                         translate_path_by_ini, multi_thread_requests)

logger = MyLogger()
prefetch_data = dict(on=True, running=False, stop_sec_dict={}, done_list=[], playlist_data={})
pipe_port_stack = list(reversed(range(25)))
trakt_emby_done_ids = []


# *_player_start 返回获取播放时间等操作所需参数字典
# stop_sec_* 接收字典参数
# media_title is None 可以用来判断是不是 mount_disk_mode

def get_pipe_or_port_str(get_pipe=False):
    pipe_port = 'pipe_name' if get_pipe else 58423
    num = pipe_port_stack.pop()
    pipe_port_stack.insert(0, num)
    pipe_port = pipe_port + num if isinstance(pipe_port, int) else pipe_port + chr(65 + num)
    return str(pipe_port)


def save_sub_file(url, name='tmp_sub.srt'):
    srt = os.path.join(configs.cwd, '.tmp', name)
    requests_urllib(url, save_path=srt)
    return srt


class PlayerManager:
    def __init__(self, data=None, player_name=None, player_path=None):
        self.data = data
        self.player_name = player_name
        self.player_path = player_path
        self.player_kwargs = {}
        self.playlist_data = {}
        self.playlist_time = {}

    def start_player(self, **kwargs):
        self.player_kwargs = player_function_dict[self.player_name](**kwargs)

    def playlist_add(self, data=None, eps_data=None):
        data = data or self.data
        playlist_fun = dict(mpv=playlist_add_mpv,
                            iina=playlist_add_mpv,
                            vlc=playlist_add_vlc,
                            mpc=playlist_add_mpc,
                            potplayer=playlist_add_pot,
                            dandanplay=playlist_add_dandan)
        limit = configs.raw.getint('playlist', 'item_limit', fallback=-1)
        if limit > 0:
            self.player_kwargs['limit'] = limit
        self.playlist_data = playlist_fun[self.player_name](data=data, eps_data=eps_data, **self.player_kwargs)

        prefetch_data['playlist_data'] = self.playlist_data
        threading.Thread(target=self.prefetch_loop, daemon=True).start()

    @staticmethod
    def prefetch_loop():
        prefetch_percent = configs.raw.getfloat('playlist', 'prefetch_percent', fallback=100)
        prefetch_type = configs.raw.get('playlist', 'prefetch_type', fallback='null')
        if prefetch_data['running'] or prefetch_percent == 100:
            return
        playlist_data = prefetch_data['playlist_data']
        if len(playlist_data) == 1:
            return
        prefetch_data['running'] = True
        prefetch_data['on'] = True
        stop_sec_dict = prefetch_data['stop_sec_dict']
        done_list = prefetch_data['done_list']
        prefetch_tuple = configs.raw.get('playlist', 'prefetch_path', fallback='').replace('，', ',')
        prefetch_tuple = tuple(p.strip() for p in prefetch_tuple.split(',') if p.strip())
        while prefetch_data['on']:
            for key, stop_sec in stop_sec_dict.items():
                ep = playlist_data.get(key)
                if not key or not stop_sec or key in done_list:
                    continue
                if prefetch_tuple and not ep['file_path'].startswith(prefetch_tuple):
                    logger.info(f'{ep["file_path"]} not startswith {prefetch_tuple=} skip prefetch')
                    prefetch_data['running'] = False
                    return
                total_sec = ep['total_sec']
                position = stop_sec / total_sec
                if position * 100 <= prefetch_percent:
                    continue
                next_ep = [e for e in playlist_data.values() if e['index'] == ep['index'] + 1]
                if not next_ep:
                    break
                ep = next_ep[0]
                if prefetch_type == 'sequence':
                    ep['gui_cmd'] = 'download_only'
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                elif prefetch_type == 'first_last':
                    ep['gui_cmd'] = 'download_not_play'
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                else:
                    null_file = 'NUL' if os.name == 'nt' else '/dev/null'
                    dl = Downloader(ep['stream_url'], ep['basename'], save_path=null_file)
                    threading.Thread(target=dl.percent_download, args=(0, 0.02), daemon=True).start()
                    threading.Thread(target=dl.percent_download, args=(0.98, 1), daemon=True).start()
                done_list.append(key)
            time.sleep(5)
        prefetch_data['running'] = False

    def update_playlist_time_loop(self):
        self.playlist_time = stop_sec_function_dict[self.player_name](stop_sec_only=False, **self.player_kwargs)
        prefetch_data['on'] = False
        prefetch_data['stop_sec_dict'].clear()

    def update_playback_for_eps(self):
        update_trakt_eps = []
        if not self.playlist_data:
            logger.error(f'playlist_data not found skip update progress')
            return
        is_fist = True
        for key, _stop_sec in self.playlist_time.items():
            ep = self.playlist_data[key]
            if not _stop_sec:
                continue
            logger.info(f'update {ep["basename"]} {_stop_sec=}')
            update_server_playback_progress(stop_sec=_stop_sec, data=ep, store=is_fist)
            is_fist = False

            ep['_stop_sec'] = _stop_sec
            update_trakt_eps.append(ep)
        if configs.raw.get('trakt', 'enable_host', fallback=''):
            self.update_trakt_for_eps(update_trakt_eps)

    @staticmethod
    def update_trakt_for_eps(eps):
        if not eps:
            return
        if not configs.check_str_match(eps[0]['netloc'], 'trakt', 'enable_host', log=True):
            return
        useful_items = []
        for ep in eps:
            item_id = ep['item_id']
            if item_id in trakt_emby_done_ids:
                continue
            if ep['_stop_sec'] / ep['total_sec'] > 0.9:
                trakt_emby_done_ids.append(item_id)
                useful_items.append(ep)
        if useful_items:
            from utils.trakt_sync import local_import_sync_ep_or_movie_to_trakt
            res = local_import_sync_ep_or_movie_to_trakt(emby_items=useful_items)
            if res:
                names = [i['basename'] for i in useful_items]
                logger.info(f'sync trakt {names}')


def list_episodes_plex(data: dict):
    result = data['list_eps']
    if not data['sub_file'] or data['mount_disk_mode']:
        return result

    scheme = data['scheme']
    netloc = data['netloc']
    api_key = data['api_key']

    key_url_dict = {
        ep['rating_key']: f'{scheme}://{netloc}/library/metadata/{ep["rating_key"]}?X-Plex-Token={api_key}'
        for ep in result if not ep['sub_file']}
    key_sub_dict = multi_thread_requests(key_url_dict, get_json=True)
    logger.info(f'send {len(key_url_dict)} requests to check subtitles')

    for ep in result:
        if ep['sub_file']:
            continue
        streams = key_sub_dict[ep['rating_key']]['MediaContainer']['Metadata'][0]['Media'][0]['Part'][0]['Stream']
        sub_path = [s['key'] for s in streams if s.get('key')
                    and configs.check_str_match(s.get('displayTitle'), 'playlist', 'subtitle_priority', log=False)]
        sub_file = f'{scheme}://{netloc}{sub_path[0]}?download=1&X-Plex-Token={api_key}' if sub_path else None
        ep['sub_file'] = sub_file
    return result


def list_episodes(data: dict):
    if data['server'] == 'plex':
        return list_episodes_plex(data)
    scheme = data['scheme']
    netloc = data['netloc']
    api_key = data['api_key']
    user_id = data['user_id']
    mount_disk_mode = data['mount_disk_mode']
    extra_str = '/emby' if data['server'] == 'emby' else ''
    device_id, play_session_id = data['device_id'], data['play_session_id']

    params = {'X-Emby-Token': api_key, }
    headers = {'accept': 'application/json', }
    headers.update(data['headers'])

    response = requests_urllib(f'{scheme}://{netloc}{extra_str}/Users/{user_id}/Items/{data["item_id"]}',
                               params=params, headers=headers, get_json=True)
    # if video is movie
    if 'SeasonId' not in response:
        data['Type'] = response['Type']
        data['ProviderIds'] = response['ProviderIds']
        return [data]
    season_id = response['SeasonId']
    series_id = response['SeriesId']

    def version_filter(file_path, episodes_data):
        ver_re = configs.raw.get('playlist', 'version_filter', fallback='').strip().strip('|')
        if not ver_re:
            return episodes_data
        try:
            ep_num = len(set([i['IndexNumber'] for i in episodes_data]))
        except KeyError:
            logger.error('version_filter: KeyError: some ep not IndexNumber')
            return episodes_data

        if ep_num == len(episodes_data):
            return episodes_data

        official_rule = file_path.rsplit(' - ', 1)
        official_rule = official_rule[-1] if len(official_rule) == 2 else None
        if official_rule:
            _ep_data = [i for i in episodes_data if official_rule in i['Path']]
            if len(_ep_data) == ep_num:
                logger.info(f'version_filter: success with {official_rule=}')
                return _ep_data
            else:
                logger.info(f'version_filter: fail, {official_rule=}, pass {len(_ep_data)}, not equal {ep_num=}')

        ini_re = re.findall(ver_re, file_path, re.I)
        ver_re = re.compile('|'.join(ini_re))
        _ep_current = [i for i in episodes_data if i['Path'] == file_path][0]
        _ep_data = [i for i in episodes_data if len(ver_re.findall(i['Path'])) == len(ini_re)]
        _ep_data_num = len(_ep_data)
        if _ep_data_num == ep_num:
            logger.info(f'version_filter: success with {ini_re=}')
            return _ep_data
        elif _ep_data_num > ep_num:
            logger.info(f'version_filter: fail, {ini_re=}, pass {_ep_data_num}, {ep_num=}, disable playlist')
            return [_ep_current]
        else:
            index = _ep_current['IndexNumber']
            _ep_success = []
            for _ep in _ep_data:
                if _ep['IndexNumber'] == index:
                    _ep_success.append(_ep)
                    index += 1
            _success = True if len(_ep_success) > 1 else False
            if _success:
                logger.info(f'version_filter: success with {ini_re=}, pass {len(_ep_success)} ep')
                return _ep_success
            else:
                logger.info(f'version_filter: fail, {ini_re=}, disable playlist')
                return [_ep_current]

    def parse_item(item):
        source_info = item['MediaSources'][0]
        file_path = source_info['Path']
        fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
        item_id = item['Id']
        container = os.path.splitext(file_path)[-1]
        stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/stream{container}' \
                     f'?DeviceId={device_id}&MediaSourceId={source_info["Id"]}&Static=true' \
                     f'&PlaySessionId={play_session_id}&api_key={api_key}'
        media_path = translate_path_by_ini(file_path) if mount_disk_mode else stream_url
        basename = os.path.basename(file_path)
        media_basename = os.path.basename(media_path)
        total_sec = int(source_info['RunTimeTicks']) // 10 ** 7
        index = item.get('IndexNumber', 0)

        media_streams = source_info['MediaStreams']
        sub_dict_list = [dict(title=s['DisplayTitle'], index=s['Index'], path=s['Path'])
                         for s in media_streams
                         if not mount_disk_mode and s['Type'] == 'Subtitle' and s['IsExternal']]
        sub_dict_list = [s for s in sub_dict_list
                         if configs.check_str_match(s['title'], 'playlist', 'subtitle_priority', log=False)]
        sub_dict = sub_dict_list[0] if sub_dict_list else {}
        sub_file = f'{scheme}://{netloc}/Videos/{item_id}/{source_info["Id"]}/Subtitles' \
                   f'/{sub_dict["index"]}/Stream{os.path.splitext(sub_dict["path"])[-1]}' if sub_dict else None
        sub_file = None if mount_disk_mode else sub_file

        data['Type'] = item['Type']
        data['ProviderIds'] = item['ProviderIds']
        result = data.copy()
        result.update(dict(
            basename=basename,
            media_basename=media_basename,
            item_id=item_id,
            file_path=file_path,
            stream_url=stream_url,
            media_path=media_path,
            fake_name=fake_name,
            total_sec=total_sec,
            sub_file=sub_file,
            index=index,
            size=source_info['Size']
        ))
        return result

    params.update({'Fields': 'MediaSources,Path,ProviderIds',
                   'SeasonId': season_id, })
    url = f'{scheme}://{netloc}{extra_str}/Shows/{series_id}/Episodes'
    episodes = requests_urllib(url, params=params, headers=headers, get_json=True)
    # dump_json_file(episodes, 'z_ep_parse.json')
    episodes = [i for i in episodes['Items'] if 'Path' in i and 'RunTimeTicks' in i]
    episodes = version_filter(data['file_path'], episodes) if data['server'] == 'emby' else episodes
    episodes = [parse_item(i) for i in episodes]

    if stream_redirect := configs.ini_str_split('dev', 'stream_redirect'):
        stream_redirect = zip(stream_redirect[0::2], stream_redirect[1::2])
        for (_raw, _jump) in stream_redirect:
            if _raw in episodes[0]['stream_url']:
                for i in episodes:
                    i['stream_url'] = i['stream_url'].replace(_raw, _jump)
                break
    return episodes


def init_player_instance(function, **kwargs):
    init_times = 1
    player = None
    while init_times <= 5:
        try:
            time.sleep(1)
            player = function(**kwargs)
            break
        except Exception as e:
            logger.error(f'{str(e)[:40]} init_player: {init_times=}')
            init_times += 1
    return player


def mpv_player_start(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    is_darwin = True if platform.system() == 'Darwin' else False
    is_iina = True if 'iina-cli' in cmd[0] else False
    pipe_name = get_pipe_or_port_str(get_pipe=True)
    cmd_pipe = fr'\\.\pipe\{pipe_name}' if os.name == 'nt' else f'/tmp/{pipe_name}.pipe'
    pipe_name = pipe_name if os.name == 'nt' else cmd_pipe
    # if sub_file:
    #     if is_iina:
    #         # https://github.com/iina/iina/issues/1991
    #         pass
    #     # 全局 sub_file 会影响播放列表下一集
    #     # cmd.append(f'--sub-file={sub_file}')
    if media_title:
        if proxy := configs.player_proxy:
            cmd.append(f'--http-proxy=http://{proxy}')
        cmd.append(f'--force-media-title={media_title}')
        cmd.append(f'--osd-playing-msg={media_title}')
    elif not is_iina:
        # iina 读盘模式下 media-title 会影响下一集
        cmd.append(f'--force-media-title={os.path.basename(cmd[1])}')
        cmd.append('--osd-playing-msg=${path}')
    if start_sec is not None:
        if is_iina and not media_title:
            # iina 读盘模式下 start_sec 会影响下一集
            pass
        else:
            cmd.append(f'--start={start_sec}')
    if is_darwin:
        cmd.append('--focus-on-open')
    cmd.append(fr'--input-ipc-server={cmd_pipe}')
    if configs.fullscreen:
        cmd.append('--fullscreen=yes')
    if configs.disable_audio:
        cmd.append('--no-audio')
        # cmd.append('--no-video')
    cmd = ['--mpv-' + i.replace('--', '', 1) if is_darwin and is_iina and i.startswith('--') else i for i in cmd]
    logger.info(cmd)
    player = subprocess.Popen(cmd, env=os.environ)
    activate_window_by_pid(player.pid)

    mpv = init_player_instance(MPV, start_mpv=False, ipc_socket=pipe_name)
    if sub_file and not is_iina and mpv:
        _cmd = ['sub-add', sub_file]
        mpv.command(*_cmd)

    if not get_stop_sec:
        return
    if mpv:
        mpv.is_iina = is_iina
    return dict(mpv=mpv)


def playlist_add_mpv(mpv: MPV, data, eps_data=None, limit=10):
    playlist_data = {}
    if not mpv:
        logger.error('mpv not found skip playlist_add_mpv')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    for ep in episodes:
        basename = ep['basename']
        playlist_data[basename] = ep
        if basename == data['basename']:
            append = True
            continue
        # iina 添加不上
        if not append or limit <= 0 or getattr(mpv, 'is_iina'):
            continue
        limit -= 1
        sub_file = ep['sub_file'] or ''
        mpv.command(
            'loadfile', ep['media_path'], 'append',
            f'title="{basename}",force-media-title="{basename}",osd-playing-msg="{basename}"'
            f',start=0,sub-file={sub_file}')
    return playlist_data


def stop_sec_mpv(*_, mpv, stop_sec_only=True):
    if not mpv:
        logger.error('mpv not found, skip stop_sec_mpv')
        return None if stop_sec_only else {}
    stop_sec = None
    name_stop_sec_dict = {}
    while True:
        try:
            basename = mpv.command('get_property', 'media-title')
            tmp_sec = mpv.command('get_property', 'time-pos')
            if not tmp_sec:
                print('.', end='')
            else:
                stop_sec = tmp_sec
                if not stop_sec_only:
                    name_stop_sec_dict[basename] = tmp_sec
                    prefetch_data['stop_sec_dict'][basename] = tmp_sec
            time.sleep(0.5)
        except Exception:
            logger.info(f'mpv exit, return stop sec')
            return stop_sec if stop_sec_only else name_stop_sec_dict


def vlc_player_start(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    is_nt = True if os.name == 'nt' else False
    # file_is_http = bool(media_title)
    port = get_pipe_or_port_str()
    if not media_title:
        cmd[1] = f'file:///{cmd[1]}'
        # base_name = os.path.basename(cmd[1])
        # media_title = base_name
    cmd = [cmd[0], '-I', 'qt', '--extraintf', 'http', '--http-host', '127.0.0.1',
           '--http-port', port, '--http-password', 'embyToLocalPlayer',
           '--one-instance', '--playlist-enqueue',
           # '--extraintf', 'rc', '--rc-quiet', '--rc-host', f'127.0.0.1:{port}'
           ] + cmd[1:]
    if not is_nt or not configs.raw.getboolean('dev', 'one_instance_mode', fallback=True):
        cmd.remove('--one-instance')
        cmd.remove('--playlist-enqueue')
    if sub_file:
        srt = save_sub_file(url=sub_file)
        cmd.append(f':sub-file={srt}')  # vlc不支持http字幕
    if start_sec is not None:
        cmd += [f':start-time={start_sec}']

    # -- 开头是全局选项，会覆盖下一集标题，换成 : 却不生效，原因未知。故放弃添加标题。
    # cmd.append(f':input-title-format={media_title}')
    # cmd.append(f':video-title={media_title}')

    cmd += ['--play-and-exit']
    if configs.fullscreen:
        cmd.append('--fullscreen')
    cmd = cmd if is_nt else [i for i in cmd if i not in ('-I', 'qt', '--rc-quiet')]
    logger.info(cmd)
    player = subprocess.Popen(cmd, env=os.environ)
    activate_window_by_pid(player.pid)
    if not get_stop_sec:
        return

    vlc = init_player_instance(VLCHttpApi, port=port, passwd='embyToLocalPlayer', exe=cmd[0])
    return dict(vlc=vlc)


class VLCHttpApi:
    def __init__(self, port, passwd, exe=None):
        passwd = f':{passwd}'
        self.exe = exe
        self.url = f'http://127.0.0.1:{port}/requests/'
        self.headers = dict(Authorization=f'Basic {base64.b64encode(passwd.encode("ascii")).decode()}', )
        _test = self.get_status()['version']

    def get(self, path='', params=None):
        params = '?' + '&'.join(f'{k}={v}' for k, v in params.items()) if params else ''
        host = f'{self.url}{path}.json' + params
        return requests_urllib(host=host, headers=self.headers, get_json=True, timeout=0.5)

    def get_status(self):
        return self.get('status')

    def command(self, cmd: str, **params):
        _params = dict(command=cmd)
        _params.update(params)
        return self.get(path='status', params=_params)

    def playlist_add(self, path):
        return self.command('in_enqueue', input=path)


def playlist_add_vlc(vlc: VLCHttpApi, data, eps_data=None, limit=5):
    playlist_data = {}
    if not vlc:
        logger.error('vlc not found skip playlist_add')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    data_path = data['media_path']
    mount_disk_mode = data['mount_disk_mode']
    limit = 10 if limit == 5 and mount_disk_mode else limit
    for ep in episodes:
        media_path = ep['media_path']
        key = os.path.basename(media_path)
        playlist_data[key] = ep
        # stream.mkv...
        if key in data_path:
            append = True
            continue
        if not append or limit <= 0:
            continue
        limit -= 1
        sub_file = ep['sub_file']
        if mount_disk_mode or not sub_file:
            add_path = urllib.parse.quote(media_path)
            vlc.playlist_add(path=add_path)
        # api 貌似不能添加字幕
        else:
            if os.name != 'nt':
                # 非 nt 的 vlc 经常不支持 '--one-instance', '--playlist-enqueue'
                add_path = urllib.parse.quote(media_path)
                vlc.playlist_add(path=add_path)
                continue
            sub_ext = sub_file.rsplit('.', 1)[-1]
            sub_file = save_sub_file(sub_file, f'{os.path.splitext(ep["basename"])[0]}.{sub_ext}')
            cmd = [vlc.exe, media_path,
                   '--one-instance', '--playlist-enqueue',
                   f':sub-file={sub_file}']
            subprocess.run(cmd)
        # media_title = os.path.basename(ep['file_path']) # 找不到方法添加标题，命令行，api
    return playlist_data


def stop_sec_vlc(*_, vlc: VLCHttpApi, stop_sec_only=True):
    if not vlc:
        logger.error('vlc not found skip stop_sec_vlc')
        return None if stop_sec_only else {}
    stop_sec = None
    name_stop_sec_dict = {}
    # rc interface 的 get_tile 会受到视频文件内置的标题影响。若采用 get_length 作为 id，动漫可能无法正常使用,故放弃，
    # 而 http api 的话，又不能设置标题
    while True:
        try:
            stat = vlc.get_status()
            tmp_sec = stat['time']
            file_name = stat['information']['category']['meta']['filename']
            if tmp_sec:
                stop_sec = tmp_sec
                if not stop_sec_only:
                    name_stop_sec_dict[os.path.basename(file_name)] = stop_sec
                    prefetch_data['stop_sec_dict'][file_name] = tmp_sec
                time.sleep(0.3)
        except Exception:
            logger.info('stop', stop_sec)
            return stop_sec if stop_sec_only else name_stop_sec_dict
        time.sleep(0.2)


def mpc_player_start(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    port = get_pipe_or_port_str()
    if sub_file:
        cmd += ['/sub', f'"{sub_file}"']
    if start_sec is not None:
        cmd += ['/start', f'"{int(start_sec * 1000)}"']
    if media_title:
        pass
    cmd[1] = f'"{cmd[1]}"'
    if configs.fullscreen:
        cmd.append('/fullscreen')
    cmd += ['/play', '/close']
    cmd += ['/webport', port]
    logger.info(cmd)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid)
    if not get_stop_sec:
        return

    mpc = init_player_instance(MPCHttpApi, port=port)
    return dict(mpc=mpc, mpc_path=cmd[0])


class MPCHTMLParser(HTMLParser):
    id_value_dict = {}
    _id = None

    def handle_starttag(self, tag: str, attrs: list):
        if attrs and attrs[0][0] == 'id':
            self._id = attrs[0][1]

    def handle_data(self, data):
        if self._id is not None:
            data = int(data) if data.isdigit() else data.strip()
            self.id_value_dict[self._id] = data
            self._id = None


class MPCHttpApi:
    def __init__(self, port):
        self.url = f'http://localhost:{port}/variables.html'
        self.parser = MPCHTMLParser()
        _test = self.get('version')

    def get(self, key, timeout=0.5, return_list=False):
        # key: str -> value
        # key: iterable object -> value dict
        context = requests_urllib(self.url, decode=True, timeout=timeout)
        self.parser.feed(context)
        data = self.parser.id_value_dict
        if isinstance(key, str):
            return data[key]
        elif return_list:
            return [data[k] for k in key]
        else:
            return {k: data[k] for k in key}


def playlist_add_mpc(mpc_path, data, eps_data=None, limit=4, **_):
    playlist_data = {}
    if not mpc_path:
        logger.error('mpc_path not found skip playlist_add_mpv')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    eps_list = []
    mount_disk_mode = data['mount_disk_mode']
    limit = 10 if limit == 4 and mount_disk_mode else limit
    for ep in episodes:
        basename = ep['basename']
        playlist_data[os.path.basename(ep['media_path'])] = ep
        if basename == data['basename']:
            append = True
            continue
        if not append or limit <= 0:
            continue
        limit -= 1
        sub_file = ep['sub_file']
        add_list = ['/add', ep['media_path'], '/sub', f'"{sub_file}"'] if sub_file else ['/add', ep['media_path']]
        if mount_disk_mode:
            eps_list += add_list
        else:
            # 若一次性添加会导致字幕有问题
            cmd = [mpc_path, *add_list]
            subprocess.run(cmd)
    if eps_list:
        cmd = [mpc_path, *eps_list]
        subprocess.run(cmd)
    return playlist_data


def stop_sec_mpc(mpc: MPCHttpApi, stop_sec_only=True, **_):
    if not mpc:
        logger.error('mpc not found skip stop_sec_mpc')
        return None if stop_sec_only else {}
    stop_stack = [None, None]
    path_stack = [None, None]
    name_stop_sec_dict = {}
    while True:
        try:
            state, position, media_path = mpc.get(['state', 'position', 'filepath'], return_list=True)
            if state == '-1':
                time.sleep(0.3)
                continue
            stop_sec = position // 1000
            stop = stop_stack.pop(0)
            stop_stack.append(stop_sec)
            path = path_stack.pop(0)
            path_stack.append(media_path)
            if not stop_sec_only and path:
                # emby 播放多版本时，PlaybackInfo 返回的数据里，不同版本 DirectStreamUrl 的 itemid 都一样（理应不同）。
                # 所以用 basename 去除 itemid 来保证数据准确性。
                path = os.path.basename(path)
                name_stop_sec_dict[path] = stop
                prefetch_data['stop_sec_dict'][path] = stop
        except Exception:
            logger.info('final stop', stop_stack[-2], stop_stack)
            # 播放器关闭时，webui 可能返回 0
            name_stop_sec_dict = {k: v for k, v in name_stop_sec_dict.items() if k is not None}
            return stop_stack[-2] if stop_sec_only else name_stop_sec_dict
        time.sleep(0.5)


def pot_player_start(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    if sub_file:
        cmd.append(f'/sub={sub_file}')
    if start_sec is not None:
        format_time = time.strftime('%H:%M:%S', time.gmtime(int(start_sec)))
        cmd += [f'/seek={format_time}']
    if media_title:
        cmd += [f'/title={media_title}']
    logger.info(cmd)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid, sleep=1)
    if not get_stop_sec:
        return

    return dict(pot_pid=player.pid, pot_path=cmd[0])


def playlist_add_pot(pot_path, data, eps_data=None, limit=5, **_):
    playlist_data = {}
    if not pot_path:
        logger.error('pot_path not found skip playlist_add_mpv')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    mount_disk_mode = data['mount_disk_mode']
    for ep in episodes:
        basename = ep['basename']
        playlist_data[basename] = ep
        if basename == data['basename']:
            append = True
            continue
        if not append or mount_disk_mode or limit <= 0:
            continue
        limit -= 1
        # f'/sub={ep["sub_file"]}' pot 下一集会丢失字幕
        # /add /title 不能复用，会丢失 /title
        time.sleep(1)
        subprocess.run([pot_path, '/add', ep['media_path'], f'/title={basename}', ])
    return playlist_data


def stop_sec_pot(pot_pid, stop_sec_only=True, **_):
    if not pot_pid:
        logger.error('pot pid not found skip stop_sec_mpc')
        return None if stop_sec_only else {}
    import ctypes
    from utils.windows_tool import user32, EnumWindowsProc, process_is_running_by_pid

    def potplayer_time_title_updater(_pid):
        def send_message(hwnd):
            nonlocal stop_sec, name_stop_sec_dict
            target_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
            if _pid == target_pid.value:
                message = user32.SendMessageW(hwnd, 0x400, 0x5004, 1)
                if message:
                    stop_sec = message // 1000

                    length = user32.GetWindowTextLengthW(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.replace(' - PotPlayer', '')
                    name_stop_sec_dict[title] = stop_sec
                    prefetch_data['stop_sec_dict'][title] = stop_sec

        def for_each_window(hwnd, _):
            send_message(hwnd)
            return True

        proc = EnumWindowsProc(for_each_window)
        user32.EnumWindows(proc, 0)

    stop_sec = None
    name_stop_sec_dict = {}
    while True:
        if not process_is_running_by_pid(pot_pid):
            logger.debug('pot not running')
            break
        potplayer_time_title_updater(pot_pid)
        logger.debug(f'pot {stop_sec=}')
        time.sleep(0.3)
    return stop_sec if stop_sec_only else name_stop_sec_dict


def dandan_player_start(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    if sub_file:
        pass
    if media_title:
        cmd[1] += f'|filePath={media_title}'
    if cmd[1].startswith('http'):
        cmd[0] = 'start'
        cmd[1] = 'ddplay:' + urllib.parse.quote(cmd[1])
        subprocess.run(cmd, shell=True)
        is_http = True
        from utils.windows_tool import find_pid_by_process_name
        time.sleep(1)
        activate_window_by_pid(find_pid_by_process_name('dandanplay.exe'))
    else:
        player = subprocess.Popen(cmd)
        activate_window_by_pid(player.pid)
        is_http = False
    logger.info(cmd)

    if not get_stop_sec:
        return

    return dict(start_sec=start_sec, is_http=is_http)


def playlist_add_dandan(data, eps_data=None, **_):
    playlist_data = {}
    episodes = eps_data or list_episodes(data)
    for ep in episodes:
        size = ep['size']
        playlist_data[size] = ep
    return playlist_data


def stop_sec_dandan(*_, start_sec=None, is_http=None, stop_sec_only=True):
    config = configs.raw
    dandan = config['dandan']
    api_key = dandan['api_key']
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else None
    stop_sec = None
    base_url = f'http://127.0.0.1:{dandan["port"]}'
    status = f'{base_url}/api/v1/current/video'
    time.sleep(5)
    from utils.windows_tool import find_pid_by_process_name, process_is_running_by_pid
    pid = find_pid_by_process_name('dandanplay.exe')
    while True:
        try:
            if requests_urllib(status, headers=headers, decode=True, timeout=0.2, retry=1, silence=True):
                break
        except Exception:
            print('.', end='')
            if not process_is_running_by_pid(pid):
                logger.info('dandan player exited')
                return start_sec if stop_sec_only else {}
            time.sleep(0.3)
    if start_sec and is_http and dandan.getboolean('http_seek'):
        seek_time = f'{base_url}/api/v1/control/seek/{start_sec * 1000}'
        requests_urllib(seek_time, headers=headers)
    logger.info('\n', 'dandan api started')
    library = requests_urllib(f'{base_url}/api/v1/library', headers=headers, get_json=True)
    library = {i['EpisodeId']: i['Size'] for i in library}
    size_stop_sec_dict = {}
    stop_flag = False
    while True:
        try:
            api_data = requests_urllib(status, headers=headers, get_json=True, timeout=0.2, retry=1, silence=True)
            position = api_data['Position']
            duration = api_data['Duration']
            ep_id = api_data['EpisodeId']
            tmp_sec = int(duration * position // 1000)
            stop_sec = tmp_sec if tmp_sec else stop_sec
            size_stop_sec_dict[ep_id] = stop_sec
            stop_flag = not api_data['Seekable'] and position > 0
            if position > 0.98 and is_http or (stop_flag and is_http):
                break
            else:
                time.sleep(0.5)
        except Exception:
            if stop_flag:
                logger.info('stop_flag found, exit')
                break
            if process_is_running_by_pid(pid):
                print('_', end='')
                time.sleep(1)
                continue
            break
    size_stop_sec_dict = {int(k): v for k, v in size_stop_sec_dict.items() if k}
    size_stop_sec_dict = {library[k]: v for k, v in size_stop_sec_dict.items() if k in library}
    logger.info(f'dandanplay exit, return stop sec')
    return stop_sec if stop_sec_only else size_stop_sec_dict


player_function_dict = dict(mpv=mpv_player_start,
                            iina=mpv_player_start,
                            mpc=mpc_player_start,
                            vlc=vlc_player_start,
                            potplayer=pot_player_start,
                            dandanplay=dandan_player_start)
stop_sec_function_dict = dict(mpv=stop_sec_mpv,
                              iina=stop_sec_mpv,
                              mpc=stop_sec_mpc,
                              vlc=stop_sec_vlc,
                              potplayer=stop_sec_pot,
                              dandanplay=stop_sec_dandan)
