import json
import os.path
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Union

from utils.configs import configs, MyLogger

ssl_context = ssl.SSLContext() if configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False) else None
bangumi_api_cache = {'cache_time': time.time(), 'bangumi': None}
sync_third_party_done_ids = {'trakt': [],
                             'bangumi': []}

logger = MyLogger()
redirect_url_cache = {}


def tg_notify(msg, silence=False):
    base_url = configs.raw.get('tg_notify', 'base_url', fallback='https://api.telegram.org')
    bot_token = configs.raw.get('tg_notify', 'bot_token', fallback='')
    chat_id = configs.raw.get('tg_notify', 'chat_id', fallback='')
    silence_time = configs.ini_str_split('tg_notify', 'silence_time', fallback='')
    if not bot_token:
        return
    if not chat_id and msg == '_get_chat_id':
        res = requests_urllib(f'{base_url}/bot{bot_token}/getUpdates', get_json=True, timeout=8)
        print(res, f'\n_get_chat_id')
        if result := res['result']:
            from_id = result[0]['message']['from']['id']
            chat_id = result[0]['message']['chat']['id']
            if from_id == chat_id:
                msg = f'`chat_id = {chat_id}`'
    if not chat_id:
        return
    if msg == '_get_chat_id':
        msg = f'message test success\n`chat_id = {chat_id}`\nneed to set `get_chat_id \= no`'
    if silence_time:
        silence_time = [range(int(start), int(end)) for (start, end) in
                        [time_range.split('-') for time_range in silence_time]]
        silence_time = [str(hour) for hours in silence_time for hour in hours]
        silence = True if time.strftime('%H') in silence_time else False

    if not msg:
        return
    requests_urllib(f'{base_url}/bot{bot_token}/sendMessage',
                    params={'chat_id': chat_id, 'text': msg, 'disable_notification': silence,
                            'parse_mode': 'MarkdownV2'}, decode=True, timeout=8)


def safe_url(url):
    parts = urllib.parse.urlsplit(url)
    quoted_path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        quoted_path,
        parts.query,
        parts.fragment,
    ))


def requests_urllib(host, params=None, _json=None, decode=False, timeout=5.0, headers=None, req_only=False,
                    http_proxy='', get_json=False, save_path='', retry=5, silence=False, res_only=False,
                    method=None):
    _json = json.dumps(_json).encode('utf-8') if _json else None
    params = urllib.parse.urlencode(params) if params else None
    host = host + '?' + params if params else host
    host = safe_url(host)
    req = urllib.request.Request(host, method=method)
    http_proxy = http_proxy or configs.script_proxy
    if http_proxy and not host.startswith(('http://127.0.0.1', 'http://localhost')):
        if 'plex.direct' not in host:
            req.set_proxy(http_proxy, 'http')
        if host.startswith('https'):
            req.set_proxy(http_proxy, 'https')
    req.add_header('User-Agent', 'embyToLocalPlayer/1.1')
    headers and [req.add_header(k, v) for k, v in headers.items()]
    if _json or get_json:
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        req.add_header('Accept', 'application/json')
    if req_only:
        return req

    response = None
    for try_times in range(1, retry + 1):
        try:
            response = urllib.request.urlopen(req, _json, timeout=timeout, context=ssl_context)
            if res_only:
                return response
            break
        except socket.timeout:
            logger.error(f'urllib timeout {try_times=} {host=}', silence=silence)
            if try_times == retry:
                raise TimeoutError(f'{try_times=} {host=}') from None
        except urllib.error.URLError as e:
            logger.error(f'urllib {try_times=} {host=}\n{str(e)[:100]}', silence=silence)
            if try_times == retry:
                raise ConnectionError(f'{try_times=} {host=} \n{str(e)[:100]}') from None
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


class SkipHTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return


class FollowHTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, hdrs):
        # 避免重复301，原因未知
        return


def check_miss_runtime_start_sec(netloc, item_id, basename, start_sec=0, stop_sec=None):
    href = configs.raw.get('dev', 'server_side_href', fallback='').strip().strip('/')
    href = href or 'http://127.0.0.1:58000'
    url = f'{href}/miss_runtime_start_sec'
    params = {'netloc': netloc, 'item_id': item_id, 'basename': basename}
    get_json = True
    if stop_sec is not None:
        params['stop_sec'] = stop_sec
        get_json = False
    try:
        res = requests_urllib(url, params=params, get_json=get_json, timeout=3, retry=3)
        if res and start_sec == 0:
            return res['start_sec']
    except Exception:
        logger.info('check_miss_runtime: can not connect to server, check server_side_href setting')


def check_redirect_cache_expired_loop():
    redirect_time = {}
    ini_dict = configs.get_match_value('', 'dev', 'redirect_expire_minute', get_ini_dict=True)
    if not ini_dict:
        return
    ini_dict = {k:int(v) for k,v in ini_dict.items()}
    logger.info(f'redirect_cache_expire: {ini_dict}')
    pattern = re.compile('|'.join(ini_dict.keys()))
    while True:
        now = time.time()
        for url in list(redirect_url_cache.keys()):
            match = pattern.search(url)
            if not match:
                continue
            if before := redirect_time.get(url):
                expire = ini_dict[match[0]] * 60
                if (before + expire) < now:
                    del redirect_url_cache[url]
                    del redirect_time[url]
                    logger.info(f'redirect_cache_expired: {url}')
            else:
                redirect_time[url] = now
                continue

        time.sleep(300)


def get_redirect_url(url, key_trim='PlaySessionId', follow_redirect=False):
    jump_url = url
    key = url.split(key_trim)[0] if key_trim else url
    if cache := redirect_url_cache.get(key):
        return cache
    start = time.time()
    try:
        redirect_handler = FollowHTTPRedirectHandler if follow_redirect else SkipHTTPRedirectHandler
        # FollowHTTPRedirectHandler, # 系统代理有可能很慢，默认不启用
        timeout = 30 if follow_redirect else 5
        handlers = [
            urllib.request.HTTPSHandler(context=ssl_context),
            redirect_handler,
        ]
        opener = urllib.request.build_opener(*handlers)
        jump_url = opener.open(requests_urllib(url, req_only=True), timeout=timeout).url
    except urllib.error.HTTPError as e:
        if e.code in [301, 302]:
            jump_url = e.headers['Location'] if e.url == url else e.url
        else:
            logger.error(f'{e.code=} get_redirect_url: {str(e)[:100]}')
            jump_url = e.url
    except Exception as e:
        logger.error(f'disable redirect: code={getattr(e, "code", None)} get_redirect_url: {str(e)[:100]}')
    _log = f'get_redirect_url: used time={str(time.time() - start)[:4]}'
    if jump_url != url:
        logger.info(f'{_log} success')
        redirect_url_cache[key] = jump_url
    else:
        logger.info(f'{_log} fail\nredirect not found, may need to disable it')
    return jump_url


def multi_thread_requests(urls: Union[list, tuple, dict], **kwargs):
    return_list = False

    def dict_requests(key, url):
        return {key: requests_urllib(host=url, **kwargs)}

    if not isinstance(urls, dict):
        return_list = True
        urls = dict(zip(range(len(urls)), urls))

    result = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        for future in as_completed([executor.submit(dict_requests, key, url) for (key, url) in urls.items()]):
            result.update(future.result())
    if return_list:
        return [i[1] for i in sorted(result.items())]
    return result


def change_emby_play_position(scheme, netloc, item_id, api_key, stop_sec, play_session_id, device_id, **kwargs):
    if stop_sec > 10 * 60 * 60:
        logger.error('stop_sec error, check it')
        return
    ticks = stop_sec * 10 ** 7
    params = {
        'X-Emby-Token': api_key,
        'X-Emby-Device-Id': device_id,
        'X-Emby-Client': 'embyToLocalPlayer',
        'X-Emby-Device-Name': 'embyToLocalPlayer',
    }
    if not kwargs.get('update_success'):  # 由实时回传功能标记
        # 若省略该请求，低版本 Emby/4.8.0.64 继续观看无法新增条目，高版本 Emby 直接回传失败。
        requests_urllib(f'{scheme}://{netloc}/emby/Sessions/Playing',
                        params=params,
                        _json={
                            'ItemId': item_id,
                            'PlaySessionId': play_session_id,
                        })
    requests_urllib(f'{scheme}://{netloc}/emby/Sessions/Playing/Stopped',
                    params=params,
                    _json={
                        'PositionTicks': ticks,
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                    })


def change_jellyfin_play_position(scheme, netloc, item_id, stop_sec, play_session_id, headers, **kwargs):
    if stop_sec > 10 * 60 * 60:
        logger.error('stop_sec error, check it')
        return
    ticks = stop_sec * 10 ** 7
    if not kwargs.get('update_success'):  # 由实时回传功能标记
        # 若省略该请求，新版 Jellyfin 继续观看新增条目会跑到末端。
        requests_urllib(f'{scheme}://{netloc}/Sessions/Playing',
                        headers=headers,
                        _json={
                            'ItemId': item_id,
                            'PlaySessionId': play_session_id,
                        })
    requests_urllib(f'{scheme}://{netloc}/Sessions/Playing/Stopped',
                    headers=headers,
                    _json={
                        'PositionTicks': ticks,
                        'ItemId': item_id,
                        'PlaySessionId': play_session_id,
                    })


def change_plex_play_position(scheme, netloc, api_key, stop_sec, rating_key, client_id, duration, **_):
    if stop_sec > 10 * 60 * 60:
        logger.error('stop_sec error, check it')
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


def realtime_playing_request_sender(data, cur_sec, method='playing'):
    is_emby = (data['server'] == 'emby')
    emby_str = '/emby' if is_emby else ''
    ticks = int(cur_sec * 10 ** 7)
    url_path = {
        'start': 'Sessions/Playing',
        'playing': 'Sessions/Playing/Progress',
        'end': 'Sessions/Playing/Stopped',
    }[method]
    params = {
        'X-Emby-Token': data['api_key'],
        'X-Emby-Device-Id': data['device_id'],
        'X-Emby-Device-Name': 'embyToLocalPlayer',
    }
    _json = {
        'EventName': 'timeupdate',
        'ItemId': data['item_id'],
        'MediaSourceId': data['media_source_id'],
        'PlayMethod': 'DirectStream',
        'PlaySessionId': data['play_session_id'],
        'PositionTicks': ticks,
        'RepeatMode': 'RepeatNone',
    }
    try:
        requests_urllib(f'{data["scheme"]}://{data["netloc"]}{emby_str}/{url_path}',
                        params=params,
                        _json=_json,
                        headers=data['headers'],
                        timeout=10)
    except Exception:
        time.sleep(30)
        pass


emby_last_dict = dict(watched=True, stop_sec=0, data={}, normal_file=True)


def update_server_playback_progress(stop_sec, data):
    if not configs.raw.getboolean('emby', 'update_progress', fallback=True):
        return
    if stop_sec is None:
        logger.error('stop_sec is None skip update progress')
        return
    file_path = data['file_path']
    ext = os.path.splitext(file_path)[-1].lower()
    # iso 回传会被标记已观看。
    normal_file = False if ext.endswith(('.iso', '.m3u8')) else True
    server = data['server']
    stop_sec = int(stop_sec)
    stop_sec = stop_sec - 2 if stop_sec > 5 else stop_sec

    if not normal_file:
        logger.info(f'skip update progress because media is {ext}')
        return
    if server == 'emby':
        change_emby_play_position(stop_sec=stop_sec, **data)
    elif server == 'jellyfin':
        change_jellyfin_play_position(stop_sec=stop_sec, **data)
    elif server == 'plex':
        change_plex_play_position(stop_sec=stop_sec, **data)
    logger.info(f'update progress: {data["basename"]} {stop_sec=}')


def sync_third_party_for_eps(eps, provider):
    if not eps:
        return
    if not configs.check_str_match(eps[0]['netloc'], provider, 'enable_host', log=True):
        return
    useful_items = []
    for ep in eps:
        item_id = ep['item_id']
        if item_id in sync_third_party_done_ids[provider]:
            logger.info(f"{provider}: skip, cuz updated previously. {ep['basename']}")
            continue
        if ep['_stop_sec'] / ep['total_sec'] > 0.9:
            sync_third_party_done_ids[provider].append(item_id)
            useful_items.append(ep)
    if not useful_items:
        return

    if provider == 'trakt':
        from utils.trakt_sync import trakt_sync_main
        trakt_sync_main(eps_data=useful_items)

    if provider == 'bangumi':
        from utils.bangumi_sync import bangumi_sync_main
        bgm = bangumi_api_cache.get(provider)
        if bgm:
            bgm.username = configs.raw.get('bangumi', 'username', fallback='')
            bgm.private = configs.raw.getboolean('bangumi', 'private', fallback=True)
            bgm.access_token = configs.raw.get('bangumi', 'access_token', fallback='')
            bgm.http_proxy = configs.script_proxy
            bgm.init()
        bgm = bangumi_sync_main(bangumi=bgm, eps_data=useful_items)
        bangumi_api_cache[provider] = bgm
        if bangumi_api_cache['cache_time'] + 86400 < time.time():
            bangumi_api_cache.update({'cache_time': time.time(), 'bangumi': None})


def save_sub_file(url, name='tmp_sub.srt'):
    srt = os.path.join(configs.cwd, '.tmp', name)
    requests_urllib(url, save_path=srt)
    return srt
