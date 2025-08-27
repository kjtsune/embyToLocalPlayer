import os
import platform
import threading
import time
import typing
import urllib.parse

from utils.configs import configs, MyLogger
from utils.emby_api_thin import EmbyApiThin
from utils.net_tools import requests_urllib, tg_notify
from utils.tools import (load_json_file, dump_json_file, scan_cache_dir, safe_deleter, version_prefer_emby,
                         load_dict_jsons_in_folder, create_sparse_file)

logger = MyLogger()

if platform.system() == 'Windows':
    import msvcrt
else:
    import fcntl


class TaskFileManager:
    def __init__(self, task_path):
        self.task_path = task_path
        self.lock_path = task_path + '.lock'
        self.lock_fd = None
        self.has_lock = False

    def acquire_lock(self, blocking=True):
        self.lock_fd = open(self.lock_path, 'a+')
        try:
            if platform.system() == 'Windows':
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(self.lock_fd.fileno(), mode, 1)
            else:
                flags = fcntl.LOCK_EX
                if not blocking:
                    flags |= fcntl.LOCK_NB
                fcntl.flock(self.lock_fd, flags)
            self.has_lock = True
            return True
        except (OSError, BlockingIOError):
            return False

    def release_lock(self):
        if self.lock_fd:
            try:
                if platform.system() == 'Windows':
                    msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            finally:
                self.lock_fd.close()
                self.lock_fd = None
                self.has_lock = False

    # def __del__(self):
    #     self.release_lock()


class Downloader:
    def __init__(self, url, _id, size=None, cache_path=None, save_path=None):
        self.id = _id
        self.url = url
        self.file = save_path or os.path.join(cache_path, _id)
        self.file_is_busy = False
        self.download_only = False
        self.cancel = False
        self.pause = False
        self.size = size
        self.chunk_size = 1024 * 1024
        self.progress = 0
        self.is_done = False
        if not save_path:
            os.path.exists(cache_path) or os.mkdir(cache_path)

        self.task_file = os.path.join(cache_path, _id + '.json')
        self.file_lock = TaskFileManager(self.task_file)
        if os.path.exists(self.file) and not os.path.exists(self.file_lock.lock_path):
            self.is_done = True
            self.restore_state()
        elif configs.raw.getboolean('gui', 'read_only', fallback=False):
            self.restore_state()
        else:
            lock_acquired = self.file_lock.acquire_lock(blocking=False)
            if lock_acquired:
                logger.info(f'dl: lock success: {_id}')
                if self.restore_state():
                    pass
                else:
                    self.save_state()
            else:
                logger.info(f'dl: lock failed: already locked by another process. \n{_id}')
                self.restore_state()

    def save_state(self):
        state = dict(_id=self.id, stream_url=self.url, size=self.size,
                     download_only=self.download_only, pause=self.pause,
                     progress=self.progress)
        dump_json_file(state, self.task_file)

    def restore_state(self, ):
        state = load_json_file(self.task_file, error_return='dict', silence=True)
        self.progress = state.get('progress', self.progress)
        self.download_only = state.get('download_only', self.download_only)
        self.pause = state.get('pause', self.pause)
        self.size = state.get('size', self.size)
        return state

    def mark_done(self):
        self.is_done = True
        self.file_lock.release_lock()
        os.path.exists(self.file_lock.lock_path) and os.remove(self.file_lock.lock_path)

    def get_size(self):
        if self.size:
            return self.size
        resp = requests_urllib(self.url, http_proxy=configs.dl_proxy, res_only=True, method='HEAD', timeout=10)
        length = resp.getheader('Content-Length')
        if not length:
            print(resp.headers)
        self.size = int(length)
        return self.size

    def range_download(self, start: int, end: int, speed=0, update=False) -> int:
        self.get_size()
        sleep = 1 / speed if speed else 0
        if start == 0:
            if safe_deleter(self.file):
                logger.info(f'delete by start 0, {self.file}')
        open_mode = 'r+b' if os.path.exists(self.file) else 'wb'
        if open_mode == 'wb' and configs.raw.getboolean('gui', 'sparse_file_by_server', fallback=False):
            if server_href := configs.raw.get('dev', 'server_side_href', fallback=''):
                _res = requests_urllib(f'{server_href}/action/sparse_file',
                                       _json={'name': self.id, 'size': self.size}, get_json=True)
                if not _res.get('sparse_file'):
                    raise Exception('server sparse_file fail, check it.')
                for _ in range(10):
                    if os.path.exists(self.file):
                        open_mode = 'r+b'
                        break
                    else:
                        print('.', end='')
                        time.sleep(0.3)
        if open_mode == 'wb':
            create_sparse_file(self.file, size=self.size)
            open_mode = 'r+b'
        headers = {'Range': f'bytes={start}-{end}'}
        try:
            resp = requests_urllib(self.url, headers=headers, http_proxy=configs.dl_proxy, res_only=True, timeout=10)
        except Exception as e:
            logger.error(f'dl: range_download error {self.id} {str(e)[:50]}')
            return start
        logger.trace(headers)
        h_size = resp.getheader('Content-Length', resp.getheader('Content-Range'))
        if h_size.isdigit():
            h_size = int(h_size)
        else:
            _s, _e = h_size.split(' ')[1].split('/')[0].split('-')
            h_size = int(_e) - int(_s) + 1
        logger.trace('total_size', self.size, 'size', h_size, 'size_mb', h_size // 1024 // 1024, f'{open_mode=}')
        downloaded_size = 0
        with open(self.file, open_mode) as f:
            f.seek(start)
            logger.trace(f'seek {start=}')
            try:
                while chunk := resp.read(self.chunk_size):
                    if self.cancel or self.pause:
                        return start
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if start < self.size * 0.1:
                        f.flush()
                    start += len(chunk)
                    if update:
                        tmp_progress = start * 100 // self.size / 100
                        if tmp_progress >= self.progress:
                            self.progress = tmp_progress
                    if start > end:
                        break
                    sleep and time.sleep(sleep)
            except Exception as e:
                logger.error(f'dl: retry: {self.id} {str(e)[:50]}')
                return start
        if start > end + 1:
            raise ConnectionError(f'dl: {start=} is greater than {end=}, something wrong, check it')
        if downloaded_size < h_size:
            logger.error(f'dl: retry: range download failed. Expected {h_size}, got {downloaded_size}. {self.id}')
            return start
        return end

    def percent_download(self, start, end, speed=0, update=True):
        self.get_size()
        self.file_is_busy = True
        logger.info(f'dl: start {int(start * 100)}% end {int(end * 100)}% \n{self.id}')
        _start = int(float(self.size * start))
        _end = int(float(self.size * end))
        end_with = self.range_download(_start, _end, speed=speed, update=update)
        error_sleep = 1
        while end_with != _end:
            if self.cancel or self.pause:
                self.file_is_busy = False
                return
            error_sleep *= 2
            logger.info(f'dl: percent download error found, sleep {error_sleep}')
            time.sleep(error_sleep)
            _start = end_with
            end_with = self.range_download(_start, _end, speed=speed, update=update)
        if update:
            self.progress = end
            logger.trace(self.id, end, 'done')
        self.file_is_busy = False
        return True

    def download_fist_last(self):
        self.percent_download(0, 0.01, update=False)
        self.percent_download(0.99, 1, update=False)
        self.progress = 0.01

    def cancel_download(self, silence=False):
        self.cancel = True
        while self.file_is_busy:
            time.sleep(1)
        self.file_lock.release_lock()
        done = False
        for f in self.file_lock.lock_path, self.task_file, self.file:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    logger.info(f'dl: file is lock, can not delete on is machine, {str(e)[:30]}\n{self.id}')
                done = True
        done and not silence and logger.info(f'dl: delete done {self.id}')
        return done


class DownloadManager:
    def __init__(self, cache_path, speed_limit=0, max_concurrent=3, per_domain_limit=2):
        self.cache_path = cache_path
        self.tasks = {}
        self.db = {}
        self.db_path = configs.cache_db
        self.update_loop_lock = False
        self.speed_limit = speed_limit
        self.download_semaphore = threading.Semaphore(max_concurrent)
        self.per_domain_limit = per_domain_limit
        self.domain_semaphores = {}
        if configs.gui_is_enable:
            os.path.exists(cache_path) or os.mkdir(cache_path)
            threading.Thread(target=self.update_db_loop, daemon=True).start()
            if configs.raw.getboolean('gui', 'auto_resume', fallback=False):
                threading.Thread(target=self.resume_or_pause, kwargs={'resume_from_db': True}).start()

    def get_domain_semaphore(self, domain: str):
        if domain not in self.domain_semaphores:
            self.domain_semaphores[domain] = threading.BoundedSemaphore(self.per_domain_limit)
        return self.domain_semaphores[domain]

    def _get_fake_init_dl(self, _id, url=None, position=0.1234, get_fake_data=False):
        data = {'stream_url': url,
                'fake_name': _id,
                'position': position}
        if get_fake_data:
            return data
        return self._init_dl(data)

    def _init_dl(self, data, check_only=False):
        url, _id, pos = data['stream_url'], data['fake_name'], data['position']
        dl = self.tasks.get(_id) or Downloader(url, _id, cache_path=self.cache_path, size=data.get('size'))
        download_only = True if dl.download_only or data.get('download_only') else False
        dl.download_only = download_only
        if not check_only and dl.file_lock.has_lock and not self.tasks.get(_id) and not dl.is_done:
            self.tasks[_id] = dl
        logger.trace(f'init_dl {dl.download_only=}')
        return url, _id, pos, dl

    def _percent_download_with_limit(self, dl: Downloader, start, end, update=True):
        domain = urllib.parse.urlparse(dl.url).netloc
        domain_semaphore = self.get_domain_semaphore(domain)
        with self.download_semaphore, domain_semaphore:
            done = dl.percent_download(start=start, end=end, speed=self.speed_limit, update=update)
            return done

    def download_only(self, data):
        url, _id, pos, dl = self._init_dl(data)
        if not dl.file_lock.has_lock:
            logger.info(f'dlm: skip, already locked. {_id}')
            return
        if dl.progress == 1:
            logger.info(f'dlm: skip, already done {_id}')
            return
        dl.download_only = True
        if dl.file_is_busy:
            logger.info(f'dlm: skip, already downloading {_id}')
            return
        if self._percent_download_with_limit(dl, dl.progress, 1):
            dl.download_only = False

    def play_check(self, data):
        url, _id, pos, dl = self._init_dl(data, check_only=True)
        if not dl.download_only and dl.progress > pos:
            data['media_path'] = dl.file
        if not os.path.exists(dl.file):
            dl.cancel_download(silence=True)
        logger.info(f'dlm: play_check {dl.download_only=} {dl.progress=}')
        data['gui_cmd'] = 'play'
        requests_urllib('http://127.0.0.1:58000/gui', _json=data)

    def download_play(self, data, play=True):
        url, _id, pos, dl = self._init_dl(data)
        if dl.download_only:
            logger.info('download only detected, refuse play')
            return
        read_only = configs.raw.getboolean('gui', 'read_only', fallback=False)
        if dl.progress >= pos:
            if not read_only and dl.file_lock.has_lock and dl.progress == 0 and not dl.file_is_busy:
                dl.download_fist_last()
            if play:
                data['media_path'] = dl.file
                data['gui_cmd'] = 'play'
                if configs.raw.getboolean('gui', 'without_confirm', fallback=False):
                    data['gui_without_confirm'] = True
                requests_urllib('http://127.0.0.1:58000/dl', _json=data)
        else:
            if play:
                data['gui_cmd'] = 'play'
                requests_urllib('http://127.0.0.1:58000/dl', _json=data)
                logger.info(f'dlm: fallback to url, cuz: {pos=} > {dl.progress}')
        if not dl.file_is_busy and dl.progress != 1:
            if not dl.file_lock.has_lock:
                logger.info(f'dlm: already locked, skip dl. {_id}')
                return
            if read_only:
                return
            logger.info(f'dlm: start download {dl.id}')
            self._percent_download_with_limit(dl, dl.progress, 1)

    def delete(self, data=None, _id: typing.Union[str, list] = None):
        self.update_loop_lock = True
        dl = None
        if data:  # delete current
            url, _id, pos, dl = self._init_dl(data)
        _ids = _id if isinstance(_id, list) else [_id]
        logger.info(f'dlm: delete ids: {_ids=}')
        for _id in _ids:
            if _id in self.tasks:
                _dl = self.tasks[_id]
                _dl.cancel_download()
                del self.tasks[_id]
            else:
                if dl:  # delete current but not in tasks
                    dl.cancel_download()
                    break
                *_, _dl = self._get_fake_init_dl(_id=_id)
                _dl.cancel_download()
        self.update_loop_lock = False

    def get_all_json_task(self):
        return load_dict_jsons_in_folder(self.cache_path, required_key='_id')

    def resume_or_pause(self, data=None, resume_from_db=False):
        read_only = configs.raw.getboolean('gui', 'read_only', fallback=False)
        if read_only:
            logger.info('dlm: read_only mode, skip resume')
            return

        def fake_tasks_info():
            r = []
            for js in self.get_all_json_task():
                _d = self._get_fake_init_dl(_id=js['_id'], url=js['stream_url'], get_fake_data=True)
                r.append(_d)
            return r

        operate = data['operate'] if not resume_from_db else 'resume'
        data_list = data['data_list'] if not resume_from_db else fake_tasks_info()
        logger.trace(f'{operate=}\n{data_list=}')
        for data in data_list:
            url, _id, pos, dl = self._init_dl(data)
            if dl.progress == 1:
                continue
            if not dl.file_lock.has_lock:
                continue
            if operate == 'pause':
                dl.pause = True
            elif operate == 'resume':
                dl.pause = False
                if dl.progress == 0:
                    dl.download_fist_last()
                threading.Thread(target=self._percent_download_with_limit,
                                 kwargs=dict(dl=dl, start=dl.progress, end=1)).start()

    def cache_size_limit(self):
        limit = int(configs.raw.getint('gui', 'cache_size_limit') * 1024 ** 3)
        dir_info = scan_cache_dir()
        dir_info = [i for i in dir_info if i['stat'].st_size > 10 * 1024 ** 2]
        dir_size = sum([i['stat'].st_size for i in dir_info])
        if dir_size > limit:
            logger.info('out of cache limit')
            dir_info.sort(key=lambda i: i['stat'].st_mtime)
            _id = dir_info[0]['_id']
            self.delete(_id=_id)

    def update_db_loop(self):
        times = 0
        while True:
            if self.update_loop_lock:
                logger.info('update lock')
                time.sleep(1)
                continue
            times += 1
            if times > 10:
                self.cache_size_limit()
                times = 0
            for _id, dl in list(self.tasks.items()):
                dl: Downloader
                if dl.file_lock.has_lock:
                    dl.save_state()
                    if dl.progress == 1:
                        logger.info(f'{_id} completed, delete lock')
                        dl.mark_done()
                        del self.tasks[_id]
            time.sleep(3)


def prefetch_resume_tv():
    settings_all = configs.ini_str_split('dev', 'prefetch_conf', split_by=';', re_split_by=',')
    api_dict = configs.get_server_api_by_ini()
    for setting_single in settings_all:
        name, *startswith = setting_single
        fetch_type = ''
        if startswith[0] == 'first_last':
            fetch_type = 'first_last'
        if name not in api_dict:
            logger.info(f'ini incorrect: {name} not set in [dev] > server_data_group, see FAQ')
            continue
        logger.info(f'prefetch conf: {name=} {startswith=}')
        emby_thin = api_dict[name]
        threading.Thread(target=_prefetch_resume_tv, args=(emby_thin, startswith, fetch_type), daemon=True).start()


def _prefetch_resume_tv(emby_thin: EmbyApiThin, startswith, fetch_type=''):
    startswith = tuple(startswith)
    null_file = 'NUL' if os.name == 'nt' else '/dev/null'

    if configs.raw.getboolean('tg_notify', 'get_chat_id', fallback=False):
        tg_notify('_get_chat_id')

    item_done_stat = {}  # {item_id:[source_id,]}
    strm_done_list = []
    sleep_again = False
    while True:
        try:
            items_all = emby_thin.get_resume_items()
        except Exception:
            time.sleep(600)
            continue
        # dump_json_file(items, 'z_resume_emby.json')
        items_all = items_all['Items']
        items_fresh = [i for i in items_all if i.get('SeriesName') and i.get('PremiereDate')
                       and time.mktime(time.strptime(i['PremiereDate'][:10], '%Y-%m-%d')) > time.time() - 86400 * 7]
        resume_ids = [i['Id'] for i in items_all]
        item_done_stat = {k: v for k, v in item_done_stat.items() if k in resume_ids}
        notify_item_list = []
        for ep_index, ep in enumerate(items_all):
            item_id = ep['Id']
            ep_file_path = ep['Path']
            ep_basename = os.path.basename(ep_file_path)
            source_info = ep['MediaSources'][0] if 'MediaSources' in ep else ep
            source_path = source_info['Path']
            is_strm = source_path.startswith('http') or ep_file_path.endswith('.strm')
            if not ep_file_path.startswith(startswith) and '/' not in startswith and not is_strm:
                continue
            if item_id in strm_done_list:
                continue
            if item_id in item_done_stat.keys():
                if sleep_again:
                    sleep_again = False
                    continue
                else:
                    sleep_again = True
            else:
                item_done_stat[item_id] = []
                if ep in items_fresh:
                    notify_item_list.append(item_id)
            # if ep['UserData'].get('LastPlayedDate'):
            #     continue
            try:
                playback_info = emby_thin.get_playback_info(item_id)
                play_session_id = playback_info['PlaySessionId']
                host = emby_thin.host
                image = f'[ ]({host}/emby/Items/{item_id}/Images/Primary?maxHeight=282&maxWidth=500)'
                item_url = f"[emby]({host}/web/index.html#!/item?id={item_id}&serverId={ep['ServerId']})"
                notify_msg = f"{image}{ep['SeriesName']} \| `{time.ctime()}` \| {item_url}"

                media_sources = playback_info['MediaSources']
                ep_source_name = [m['Name'] for m in media_sources if m['Name'] in ep_basename][0]
                if fetch_type == 'fetch_type':
                    playback_info['MediaSources'] = [version_prefer_emby(media_sources)]

                for source_info in playback_info['MediaSources']:
                    source_path = source_info['Path']
                    file_path = ep_file_path
                    is_http_source = source_path.startswith('http')
                    if is_strm and is_http_source and source_info['Name'] not in ep_file_path:
                        file_path = ep_file_path.replace(ep_source_name, source_info['Name'])
                    fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
                    container = os.path.splitext(file_path)[-1]
                    source_id = source_info['Id']
                    if source_id in item_done_stat[item_id]:
                        continue
                    else:
                        item_done_stat[item_id].append(source_id)
                    # stream_url = f'{host}/videos/{ep["Id"]}/stream{container}' \
                    #              f'?MediaSourceId={source_info["Id"]}&Static=true&api_key={api_key}'
                    stream_url = f'{host}/emby/videos/{item_id}/stream{container}' \
                                 f'?DeviceId=embyToLocalPlayer&MediaSourceId={source_id}&Static=true' \
                                 f'&PlaySessionId={play_session_id}&api_key={emby_thin.api_key}'
                    strm_direct = configs.check_str_match(host, 'dev', 'strm_direct_host', log=False)
                    is_http_direct_strm = is_strm and strm_direct and is_http_source
                    if is_http_direct_strm:
                        stream_url = source_path
                    if stream_redirect := configs.ini_str_split('dev', 'stream_redirect'):
                        stream_redirect = zip(stream_redirect[0::2], stream_redirect[1::2])
                        for (_raw, _jump) in stream_redirect:
                            if _raw in stream_url:
                                stream_url = stream_url.replace(_raw, _jump)
                                break
                    root_dir = os.path.dirname(os.path.dirname((os.path.dirname(file_path))))
                    relative_path = file_path.replace(root_dir, '')[1:]
                    notify_msg += f'\n`{relative_path}`'
                    if configs.raw.getboolean('tg_notify', 'disable_prefetch', fallback=False):
                        logger.info(f'tg_notify, {relative_path}')
                        continue
                    if configs.check_str_match(host, 'dev', 'stream_prefix', log=False):
                        stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
                        stream_url = f'{stream_prefix}{stream_url}'
                    if fetch_type == 'first_last' and ep_index < 2:
                        if not configs.gui_is_enable:
                            continue
                        ep['stream_url'], ep['fake_name'], ep['position'] = stream_url, fake_name, 0.1
                        ep['gui_cmd'] = 'download_not_play'
                        requests_urllib('http://127.0.0.1:58000/gui', _json=ep)
                        continue
                    if is_strm:
                        strm_done_list.append(item_id)
                        logger.info(f'get playback info only, cuz is strm [{ep["Name"]}]{relative_path}')
                        continue
                    try:
                        logger.info(f'prefetch {relative_path} \n{stream_url[:100]}')
                        dl = Downloader(url=stream_url, _id=os.path.basename(file_path), save_path=null_file,
                                        size=ep.get('size'))
                        dl.percent_download(0, 0.05)
                        dl.percent_download(0.98, 1)
                    except Exception:
                        logger.error(f'prefetch error on download connection, skip\n{stream_url}')
                    print()
                if item_id in notify_item_list:
                    tg_notify(notify_msg)
            except Exception as e:
                logger.error(f'_prefetch_resume_tv error found {str(e)[:100]}')
                break
        time.sleep(600)
