import base64
import os.path
import platform
import subprocess
import threading
import time
import urllib.parse
from html.parser import HTMLParser

from utils.configs import configs, MyLogger
from utils.downloader import Downloader
from utils.net_tools import (requests_urllib, update_server_playback_progress, sync_third_party_for_eps, list_episodes,
                             save_sub_file, get_redirect_url, updating_playing_progress)
from utils.python_mpv_jsonipc import MPV
from utils.tools import activate_window_by_pid

logger = MyLogger()
prefetch_data = dict(on=True, running=False, stop_sec_dict={}, done_list=[])
pipe_port_stack = list(reversed(range(25)))
mpv_play_speed = {'media_title': 'speed'}


# *_player_start 返回获取播放时间等操作所需参数字典
# stop_sec_* 接收字典参数

def get_pipe_or_port_str(get_pipe=False):
    pipe_port = 'pipe_name' if get_pipe else 58423
    num = pipe_port_stack.pop()
    pipe_port_stack.insert(0, num)
    pipe_port = pipe_port + num if isinstance(pipe_port, int) else pipe_port + chr(65 + num)
    return str(pipe_port)


class PlayerManager:
    def __init__(self, data, player_name=None, player_path=None):
        self.data = data
        self.player_name = player_name
        self.player_path = player_path
        self.player_kwargs = {}
        self.playlist_data = {}
        self.playlist_time = {}
        self.is_http_sub = bool(data.get('sub_file'))

    def start_player(self, **kwargs):
        try:
            self.player_kwargs = player_start_func_dict[self.player_name](**kwargs)
        except FileNotFoundError:
            raise FileNotFoundError(f'player not exists, check config ini file, {kwargs["cmd"][0]}') from None

    def playlist_add(self, eps_data=None):
        playlist_fun = dict(mpv=playlist_add_mpv,
                            iina=playlist_add_mpv,
                            vlc=playlist_add_vlc,
                            mpc=playlist_add_mpc,
                            potplayer=playlist_add_pot,
                            dandanplay=playlist_add_dandan)
        limit = configs.raw.getint('playlist', 'item_limit', fallback=-1)
        if limit > 0:
            self.player_kwargs['limit'] = limit
        self.playlist_data = playlist_fun[self.player_name](data=self.data, eps_data=eps_data, **self.player_kwargs)

        threading.Thread(target=self.prefetch_next_ep_loop, daemon=True).start()
        threading.Thread(target=self.redirect_next_ep_loop, daemon=True).start()
        threading.Thread(target=self.playing_feedback_loop, daemon=True).start()

    def playing_feedback_loop(self):
        mpv = self.player_kwargs.get('mpv')
        if not mpv or not configs.check_str_match(self.data['netloc'], 'dev', 'playing_feedback_host', log=True):
            return
        if self.data['server'] == 'plex':
            logger.info('playing_feedback not support plex, skip')
            return
        stop_sec_dict = prefetch_data['stop_sec_dict']
        prefetch_data['on'] = True
        last_key = None
        req_sec = 0
        interval = 5
        pause_sec = 0
        last_ep = None
        while prefetch_data['on']:
            try:
                key = mpv.command('get_property', 'media-title')
                speed = mpv.command('get_property', 'speed')
                if mpv.command('get_property', 'pause'):
                    pause_sec += interval
                else:
                    pause_sec = 0
            except Exception:
                break
            cur_sec = stop_sec_dict.get(key)
            ep = self.playlist_data.get(key)
            if not all([cur_sec, ep]):
                continue
            if key != last_key:
                if last_ep:
                    last_sec = stop_sec_dict[last_key]
                    logger.debug(f'updating end {last_sec=} {last_ep["basename"]}')
                    updating_playing_progress(data=last_ep, cur_sec=last_sec, method='end')
                    last_ep['update_success'] = True
                updating_playing_progress(data=ep, cur_sec=cur_sec, method='start')
                last_ep = ep
                last_key = key
                req_sec = cur_sec
                time.sleep(interval)
                logger.debug(f'updating start {cur_sec=} {last_ep["basename"]}')
                continue
            after_sec = cur_sec - req_sec
            if 180 < pause_sec or 0 < after_sec < 30 * speed:  # 尽量增加汇报间隔
                time.sleep(interval)
                continue
            updating_playing_progress(data=ep, cur_sec=cur_sec)
            req_sec = cur_sec
            time.sleep(interval)

    def redirect_next_ep_loop(self):
        # 未兼容播放器多开，暂不处理
        mpv = self.player_kwargs.get('mpv')
        if not mpv or not configs.check_str_match(self.data['netloc'], 'dev', 'redirect_check_host', log=False):
            return
        if len(self.playlist_data) == 1:
            return

        done_list = []
        stop_sec_dict = prefetch_data['stop_sec_dict']
        prefetch_data['on'] = True
        while prefetch_data['on']:
            for key, stop_sec in stop_sec_dict.copy().items():
                ep = self.playlist_data.get(key)
                if not ep:
                    continue
                if not ep['media_path'].startswith('http'):
                    return
                if not key or not stop_sec or key in done_list:
                    continue
                if stop_sec / ep['total_sec'] < 0.5:
                    continue
                # mix_sO 可能造成 index 重复
                # next_ep = [e for e in self.playlist_data.values() if e['index'] == ep['index'] + 1]
                # 字典目前保持插入顺序
                # playlist_data 条目数量可能大于实际数量。(目前 mpv 不会)
                list_playlist_data = list(self.playlist_data.values())
                if ep == list_playlist_data[-1]:
                    break
                next_ep_index = list_playlist_data.index(ep) + 1
                next_ep_key = list(self.playlist_data.keys())[next_ep_index]
                next_ep = list_playlist_data[next_ep_index]
                try:
                    playlist = mpv.command('get_property', 'playlist')
                except Exception:
                    logger.info('redirect_next_ep: mpv exception found, exit')
                    return
                ne_url = next_ep['stream_url']
                cu_url = ep['stream_url']
                cu_re_url = self.data['stream_url'] if ep['file_path'] == self.data['file_path'] \
                    else ep.get('redirect_url', '')
                cu_mpv_list = [i for i in playlist if i.get('playing')
                               and i['filename'] in (cu_url, cu_re_url)]
                if not cu_mpv_list:
                    logger.info('redirect_next_ep: mpv cur playing filename not match playlist_data, may need check')
                    # 可能是起播时，集进度超50，在未获取重定向就进入下一集了。导致 stop_sec_dict 有未完成的条目，未进入 done_list。
                    done_list.append(key)
                    continue
                cu_mpv_index = playlist.index(cu_mpv_list[0])
                if cu_mpv_index == (len(playlist) - 1):
                    return
                if playlist[cu_mpv_index + 1]['filename'] != ne_url:
                    logger.info('redirect_next_ep: mpv next filename not match playlist_data, may need check')
                    continue
                mpv_cmd = next_ep['mpv_cmd']
                ne_re_url = get_redirect_url(ne_url, follow_redirect=True)
                mpv_cmd[1] = ne_re_url
                try:
                    mpv.command(*mpv_cmd)
                    mpv.command('playlist-move', len(playlist), cu_mpv_index + 1)
                    mpv.command('playlist-remove', cu_mpv_index + 2)
                except Exception:
                    logger.info('redirect_next_ep: mpv exception found, exit')
                    return
                self.playlist_data[next_ep_key]['redirect_url'] = ne_re_url
                # logger.info(f'redirect_next_ep: {next_ep_index=} {next_ep_key=}')
                logger.info(f'redirect_next_ep: {mpv_cmd}')
                done_list.append(key)
                # pprint.pprint(mpv.command('get_property', 'playlist'))
            time.sleep(5)

    def prefetch_next_ep_loop(self):
        prefetch_percent = configs.raw.getfloat('playlist', 'prefetch_percent', fallback=100)
        prefetch_type = configs.raw.get('playlist', 'prefetch_type', fallback='null')
        if prefetch_data['running'] or prefetch_percent == 100:
            return
        if len(self.playlist_data) == 1:
            return
        prefetch_data['running'] = True
        prefetch_data['on'] = True
        stop_sec_dict = prefetch_data['stop_sec_dict']
        done_list = prefetch_data['done_list']
        prefetch_host = configs.raw.get('playlist', 'prefetch_host', fallback='').replace('，', ',')
        prefetch_path = configs.raw.get('playlist', 'prefetch_path', fallback='').replace('，', ',')
        prefetch_path = tuple(p.strip() for p in prefetch_path.split(',') if p.strip())
        while prefetch_data['on']:
            for key, stop_sec in stop_sec_dict.copy().items():
                ep = self.playlist_data.get(key)
                if not ep:
                    continue
                if not ep['media_path'].startswith('http'):
                    return
                if not key or not stop_sec or key in done_list:
                    continue
                if prefetch_host and not configs.check_str_match(ep['netloc'], 'playlist', 'prefetch_host',
                                                                 log_by=False):
                    prefetch_data['running'] = False
                    return
                if prefetch_path and not ep['file_path'].startswith(prefetch_path):
                    logger.info(f'{ep["file_path"]} not startswith {prefetch_path=} skip prefetch')
                    prefetch_data['running'] = False
                    return
                total_sec = ep['total_sec']
                position = stop_sec / total_sec
                if position * 100 <= prefetch_percent:
                    continue
                list_playlist_data = list(self.playlist_data.values())
                if ep == list_playlist_data[-1]:
                    break
                next_ep_index = list_playlist_data.index(ep) + 1
                ep = list_playlist_data[next_ep_index]
                if prefetch_type == 'sequence':
                    ep['gui_cmd'] = 'download_only'
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                elif prefetch_type == 'first_last':
                    ep['gui_cmd'] = 'download_not_play'
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                else:
                    null_file = 'NUL' if os.name == 'nt' else '/dev/null'
                    dl = Downloader(ep['stream_url'], ep['basename'], save_path=null_file)
                    threading.Thread(target=dl.percent_download, args=(0, 0.08), daemon=True).start()
                    threading.Thread(target=dl.percent_download, args=(0.98, 1), daemon=True).start()
                done_list.append(key)
            time.sleep(5)
        prefetch_data['running'] = False

    def http_sub_auto_next_ep_time_loop(self, key_field):
        playlist_data = tuple(self.playlist_data.items())
        fist_ep = True
        for index, (key, ep) in enumerate(playlist_data):
            if fist_ep and key != self.data[key_field]:
                continue
            next_title, next_ep = playlist_data[index + 1] if index < len(playlist_data) - 1 else (None, None)
            stop_sec = stop_sec_function_dict[self.player_name](stop_sec_only=True, **self.player_kwargs)
            self.playlist_time[key] = stop_sec
            fist_ep = False
            if not next_ep or not stop_sec:
                break
            next_media_title = next_ep['media_title']
            if stop_sec / ep['total_sec'] < 0.9:
                logger.info(f'skip play {next_media_title}, because watch progress < 0.9')
                break
            # if show_confirm_button('Click To Stop Play Next EP', 200, 40, result=True, fallback=False, timeout=2):
            #     logger.info('Stop Play Next EP by button')
            #     break
            self.player_kwargs = player_start_func_dict[self.player_name](
                cmd=[self.player_path, next_ep['media_path']], sub_file=next_ep.get('sub_file'),
                media_title=next_media_title, mount_disk_mode=False)
            activate_window_by_pid(self.player_kwargs['pid'])
            logger.info(f'auto play: {next_media_title}')

    def update_playlist_time_loop(self):
        if configs.raw.getboolean('dev', 'http_sub_auto_next_ep', fallback=False) and (
                (self.is_http_sub and self.player_name == 'potplayer')
                or (self.is_http_sub and self.player_name == 'vlc' and os.name != 'nt')):
            key_field_map = {'potplayer': 'media_title', 'vlc': 'media_basename'}
            logger.info('disable playlist cuz http sub, auto next ep mode enabled')
            self.http_sub_auto_next_ep_time_loop(key_field=key_field_map[self.player_name])
        else:
            self.playlist_time = stop_sec_function_dict[self.player_name](stop_sec_only=False, **self.player_kwargs)
        # 未兼容播放器多开，暂不处理
        prefetch_data['on'] = False
        prefetch_data['stop_sec_dict'].clear()

    def update_playback_for_eps(self):
        need_update_eps = []
        if not self.playlist_data:
            logger.error(f'skip update progress: playlist_data not found')
            return
        for key, _stop_sec in self.playlist_time.items():
            ep = self.playlist_data.get(key)
            if not ep:
                logger.error(f'skip update progress: {key=} {_stop_sec=} not in playlist_data')
                continue
            if not _stop_sec:
                continue
            update_server_playback_progress(stop_sec=_stop_sec, data=ep)

            ep['_stop_sec'] = _stop_sec
            need_update_eps.append(ep)
        for provider in 'trakt', 'bangumi':
            if configs.raw.get(provider, 'enable_host', fallback=''):
                threading.Thread(target=sync_third_party_for_eps,
                                 kwargs={'eps': need_update_eps, 'provider': provider}, daemon=True).start()


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


def mpv_player_start(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True, mount_disk_mode=None,
                     data=None):
    intro_start, intro_end = data.get('intro_start'), data.get('intro_end')
    is_darwin = True if platform.system() == 'Darwin' else False
    is_iina = True if 'iina-cli' in cmd[0] else False
    is_mpvnet = True if 'mpvnet' in cmd[0] else False
    pipe_name = get_pipe_or_port_str(get_pipe=True)
    cmd_pipe = fr'\\.\pipe\{pipe_name}' if os.name == 'nt' else f'/tmp/{pipe_name}.pipe'
    pipe_name = pipe_name if os.name == 'nt' else cmd_pipe
    osd_title = '${path}' if mount_disk_mode else media_title
    if sub_file:
        if not is_iina and not is_mpvnet:
            # https://github.com/iina/iina/issues/1991
            # https://github.com/kjtsune/embyToLocalPlayer/issues/26
            cmd.append(f'--sub-files-toggle={sub_file}')
        if is_iina and not mount_disk_mode:
            srt = save_sub_file(url=sub_file)
            cmd.append(f'--sub-files={srt}')
    if mount_disk_mode and is_iina:
        # iina 读盘模式下 media-title 会影响下一集
        pass
    else:
        cmd.append(f'--force-media-title={media_title}')
        cmd.append(f'--osd-playing-msg={osd_title}')
    if not mount_disk_mode:
        if proxy := configs.player_proxy:
            cmd.append(f'--http-proxy=http://{proxy}')
    if start_sec is not None:
        if is_iina and mount_disk_mode:
            # iina 读盘模式下 start_sec 会影响下一集
            pass
        else:
            cmd.append(f'--start={start_sec}')
    if is_darwin:
        cmd.append('--focus-on-open')
    cmd.append(fr'--input-ipc-server={cmd_pipe}')
    cmd.append('--script-opts-append=autoload-disabled=yes')
    if configs.fullscreen:
        cmd.append('--fullscreen=yes')
    if configs.disable_audio:
        cmd.append('--no-audio')
        # cmd.append('--no-video')
    cmd = ['--mpv-' + i.replace('--', '', 1) if is_darwin and is_iina and i.startswith('--') else i for i in cmd]
    logger.info(f'{cmd[:2]}\nargs={cmd[2:]}')
    player = subprocess.Popen(cmd, env=os.environ)
    activate_window_by_pid(player.pid)

    mpv = init_player_instance(MPV, start_mpv=False, ipc_socket=pipe_name)
    if sub_file and is_mpvnet and mpv:
        _cmd = ['sub-add', sub_file]
        mpv.command(*_cmd)
    if mpv and intro_end:
        chapter_list = [{'title': 'intro', 'time': intro_start}, {'title': 'main', 'time': intro_end}]
        mpv.command('set_property', 'chapter-list', chapter_list)
    if speed := mpv_play_speed.get(media_title):
        mpv.command('set_property', 'speed', speed)
    if not get_stop_sec:
        return
    if mpv:
        mpv.is_iina = is_iina
        mpv.is_mpvnet = is_mpvnet
    return dict(mpv=mpv)


def playlist_add_mpv(mpv: MPV, data, eps_data=None, limit=10):
    playlist_data = {}
    if not mpv:
        logger.error('mpv not found skip playlist_add_mpv')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    is_iina = getattr(mpv, 'is_iina')
    mount_disk_mode = data['mount_disk_mode']
    # 检查是否是新版loadfile命令
    # https://github.com/mpv-player/mpv/commit/c678033
    new_loadfile_cmd = False
    if not is_iina:
        try:
            for c in mpv.command('get_property', 'command-list'):
                if c['name'] == 'loadfile':
                    for a in c['args']:
                        if a['name'] == 'index':
                            new_loadfile_cmd = True
        except Exception:
            pass
    for ep in episodes:
        basename = ep['basename']
        media_title = ep['media_title']
        if is_iina and mount_disk_mode:
            playlist_data[basename] = ep
        else:
            playlist_data[media_title] = ep
        if basename == data['basename']:
            append = True
            continue
        # iina 添加不上
        if not append or limit <= 0 or is_iina:
            continue
        limit -= 1

        sub_cmd = ''
        main_ep_sub = data.get('sub_file', '')
        if sub_file := ep['sub_file']:
            # mpvnet 不支持 sub-files-toggle
            if main_ep_sub and not getattr(mpv, 'is_mpvnet'):
                sub_cmd = f',sub-files-remove={main_ep_sub},sub-files-append={main_ep_sub}'
                sub_cmd = sub_cmd + f',sub-files-append={sub_file}'
            else:
                sub_cmd = f',sub-file={sub_file}'

        if intro_end := ep.get('intro_end'):
            # chapter_list = [{'title': 'intro', 'time': ep['intro_start']}, {'title': 'main', 'time': intro_end}]
            # mpv.command('set_property', 'chapter-list', chapter_list)
            chapters_text = f''';FFMETADATA1
[CHAPTER]
TIMEBASE=1/1
START={ep['intro_start']}
END={intro_end}
title=intro
[CHAPTER]
TIMEBASE=1/1
START={intro_end}
END=9999
title=main
'''
            _tmp = os.path.join(configs.cwd, '.tmp')
            chap_path = os.path.join(_tmp, f'{basename}-chapters.txt')
            chap_cmd = f',chapters-file="{chap_path}"'
            if not os.path.exists(_tmp):
                os.mkdir(_tmp)
            with open(chap_path, 'w', encoding='utf-8') as f:
                f.write(chapters_text)
        else:
            chap_cmd = ''

        try:
            options = (f'title="{media_title}",force-media-title="{media_title}"'
                       f',osd-playing-msg="{media_title}",start=0{sub_cmd}{chap_cmd}')
            mpv_cmd = ['loadfile', ep['media_path'], 'append', '-1', options]
            if not new_loadfile_cmd:
                del mpv_cmd[-2]
            mpv.command(*mpv_cmd)
            ep['mpv_cmd'] = mpv_cmd
        except OSError:
            logger.error('mpv exit: by playlist_add_mpv: except OSError')
            return {}
    return playlist_data


def stop_sec_mpv(mpv: MPV, stop_sec_only=True, **_):
    if not mpv:
        logger.error('mpv not found, skip stop_sec_mpv')
        return None if stop_sec_only else {}
    stop_sec = None
    name_stop_sec_dict = {}
    while True:
        try:
            media_title = mpv.command('get_property', 'media-title')
            tmp_sec = mpv.command('get_property', 'time-pos')
            speed = mpv.command('get_property', 'speed')
            if not tmp_sec:
                print('.', end='')
            else:
                mpv_play_speed[media_title] = speed
                stop_sec = tmp_sec
                if not stop_sec_only:
                    name_stop_sec_dict[media_title] = tmp_sec
                    prefetch_data['stop_sec_dict'][media_title] = tmp_sec
            time.sleep(0.5)
        except Exception:
            logger.info(f'mpv exit, return stop sec')
            return stop_sec if stop_sec_only else name_stop_sec_dict


def vlc_player_start(cmd: list, start_sec=None, sub_file=None, get_stop_sec=True, mount_disk_mode=None, **_):
    is_nt = True if os.name == 'nt' else False
    port = get_pipe_or_port_str()
    if mount_disk_mode:
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
    return dict(vlc=vlc, pid=player.pid)


class VLCHttpApi:
    def __init__(self, port, passwd, exe=None):
        passwd = f':{passwd}'
        self.exe = exe
        self.url = f'http://127.0.0.1:{port}/requests/'
        self.headers = dict(Authorization=f'Basic {base64.b64encode(passwd.encode("ascii")).decode()}', )
        _test = self.get_status()['version']

    def get(self, path='', params=None, silence=False):
        params = '?' + '&'.join(f'{k}={v}' for k, v in params.items()) if params else ''
        host = f'{self.url}{path}.json' + params
        return requests_urllib(host=host, headers=self.headers, get_json=True, timeout=0.5, silence=silence)

    def get_status(self):
        return self.get('status')

    def command(self, cmd: str, **params):
        _params = dict(command=cmd)
        _params.update(params)
        return self.get(path='status', params=_params)

    def playlist_add(self, path):
        return self.command('in_enqueue', input=path)


def playlist_add_vlc(vlc: VLCHttpApi, data, eps_data=None, limit=5, **_):
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
                # add_path = urllib.parse.quote(media_path)
                # vlc.playlist_add(path=add_path)
                # 目前采用自动连播方案，故含 http_sub 时，禁用播放列表。
                continue
            sub_ext = sub_file.rsplit('.', 1)[-1]
            sub_file = save_sub_file(sub_file, f'{os.path.splitext(ep["basename"])[0]}.{sub_ext}')
            cmd = [vlc.exe, media_path,
                   '--one-instance', '--playlist-enqueue',
                   f':sub-file={sub_file}']
            subprocess.run(cmd)
        # media_title = os.path.basename(ep['file_path']) # 找不到方法添加标题，命令行，api
    return playlist_data


def stop_sec_vlc(vlc: VLCHttpApi, stop_sec_only=True, **_):
    if not vlc:
        logger.error('vlc not found skip stop_sec_vlc')
        return None if stop_sec_only else {}
    stop_sec = None
    name_stop_sec_dict = {}
    # rc interface 的 get_tile 会受到视频文件内置的标题影响。若采用 get_length 作为 id，动漫可能无法正常使用,故放弃，
    # 而 http api 的话，又不能设置标题
    while True:
        try:
            stat = vlc.get('status', silence=True)
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


def mpc_player_start(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True, **_):
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

    mpc = init_player_instance(MPCHttpApi, port=port, pid=player.pid)
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
    def __init__(self, port, pid=None):
        from utils.windows_tool import process_is_running_by_pid
        self.url = f'http://localhost:{port}/variables.html'
        self.parser = MPCHTMLParser()
        self.pid = pid
        self.is_running = lambda: process_is_running_by_pid(pid)
        _test = self.get('version')

    def get(self, key, timeout=0.5, return_list=False, retry=3):
        # key: str -> value
        # key: iterable object -> value dict
        if self.pid:
            for _ in range(15):
                try:
                    context = requests_urllib(self.url, decode=True, timeout=1, retry=1, silence=True)
                    break
                except Exception:
                    if not self.is_running():
                        raise ConnectionAbortedError('mpc is not running') from None
                    print('.', end='')
                    pass
                time.sleep(1)
            else:
                raise TimeoutError('MPCHttpApi Connection timeout')
        else:
            context = requests_urllib(self.url, decode=True, timeout=timeout, retry=retry)
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


def pot_player_start(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True, **_):
    if sub_file:
        if 'Plex-Token' in sub_file:
            sub_file = save_sub_file(sub_file, name='pot sub.srt')
        cmd.append(f'/sub={sub_file}')
    if start_sec is not None:
        format_time = time.strftime('%H:%M:%S', time.gmtime(int(start_sec)))
        cmd += [f'/seek={format_time}']
    if media_title:
        cmd += [f'/title={media_title}']
    if pot_conf := configs.raw.get('dev', 'pot_conf', fallback=''):
        cmd += [f'config={pot_conf.strip()}']

    logger.info(cmd)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid, sleep=1)
    if not get_stop_sec:
        return

    return dict(pid=player.pid, player_path=cmd[0])


def playlist_add_pot(pid, player_path, data, eps_data=None, limit=5, **_):
    mix_s0 = configs.raw.getboolean('playlist', 'mix_s0', fallback=False)
    from utils.windows_tool import process_is_running_by_pid
    playlist_data = {}
    if not player_path:
        logger.error('player_path not found skip playlist_add_pot')
        return {}
    episodes = eps_data or list_episodes(data)
    append = False
    mount_disk_mode = data['mount_disk_mode']
    limit = 12 if limit == 5 and mount_disk_mode and mix_s0 else limit
    is_http_sub = bool(data.get('sub_file'))
    is_http_sub and logger.info('disable playlist cuz is_http_sub')
    if not mount_disk_mode:
        while True:
            if stop_sec_pot(pid=pid, check_only=True):
                break
            if not process_is_running_by_pid(pid):
                break
            time.sleep(1)
    pot_cmds = []
    for ep in episodes:
        basename = ep['basename']
        media_title = ep['media_title']
        playlist_data[media_title] = ep
        playlist_data[basename] = ep
        if basename == data['basename']:
            append = True
            continue
        if not append or (mount_disk_mode and not mix_s0) or limit <= 0 or is_http_sub:
            continue
        limit -= 1
        # f'/sub={ep["sub_file"]}' pot 下一集会丢失字幕
        # /add /title 不能复用，会丢失 /title，选项要放后面，否则会有奇怪的问题。
        pot_cmds.append([player_path, ep['media_path'], '/add', f'/title={media_title}'])
    if pot_cmds:
        def add_thread():
            sleep_sec = 1 if mount_disk_mode else 5
            for cmd in pot_cmds:
                if not process_is_running_by_pid(pid):
                    break
                subprocess.run(cmd)
                time.sleep(sleep_sec)

        threading.Thread(target=add_thread, daemon=True).start()
    return playlist_data


def stop_sec_pot(pid, stop_sec_only=True, check_only=False, **_):
    if not pid:
        logger.error('pot pid not found skip stop_sec_pot')
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
                    if check_only:
                        stop_sec = 'check_only'
                        return
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
        if not process_is_running_by_pid(pid):
            logger.debug('pot not running')
            break
        if check_only and stop_sec == 'check_only':
            return True
        potplayer_time_title_updater(pid)
        logger.debug(f'pot {stop_sec=}')
        time.sleep(0.3)
    if check_only:
        return False
    return stop_sec if stop_sec_only else name_stop_sec_dict


def dandan_player_start(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True,
                        mount_disk_mode=None, **_):
    if sub_file:
        pass
    if not mount_disk_mode:
        file_name = media_title.split('  |  ')[-1]
        cmd[1] += f'|filePath={file_name}'
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
    try_sec = 0
    while True:
        try:
            if requests_urllib(status, headers=headers, decode=True, timeout=0.2, retry=1, silence=True):
                break
        except Exception:
            try_sec += 0.3
            print('.', end='')
            if not process_is_running_by_pid(pid):
                print()
                try_sec > 10 and logger.error('dandan api time out, may need set api_key or wait 10s after video play')
                logger.info('dandan player exited before dandan api started')
                return start_sec if stop_sec_only else {}
            time.sleep(0.3)
    seek_url = f'{base_url}/api/v1/control/seek/{start_sec * 1000}'
    if start_sec and is_http and dandan.getboolean('http_seek'):
        requests_urllib(seek_url, headers=headers)
    try_sec and print()
    logger.info('dandan api started')
    library = requests_urllib(f'{base_url}/api/v1/library', headers=headers, get_json=True)
    library = {i['EpisodeId']: i['Size'] for i in library}
    size_stop_sec_dict = {}
    stop_flag = False
    disk_mode_seek = not is_http
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
            if disk_mode_seek and tmp_sec > 120:
                disk_mode_seek = False
            if disk_mode_seek and tmp_sec < 30 and start_sec > 90:
                requests_urllib(seek_url, headers=headers)
                disk_mode_seek = False
                logger.info(f'seek by tmp_sec < 30 and start_sec > 90, {start_sec=} {tmp_sec=}')
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
    raw_dict = {int(k): v for k, v in size_stop_sec_dict.items() if k}
    size_stop_sec_dict = {library[k]: v for k, v in raw_dict.items() if k in library}
    if raw_dict and not size_stop_sec_dict:
        logger.error('media info not in dandan library, need to set dandan library auto add item')
    logger.info(f'dandanplay exit, return stop sec, {stop_sec=}')
    return stop_sec if stop_sec_only else size_stop_sec_dict


player_start_func_dict = dict(mpv=mpv_player_start,
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
