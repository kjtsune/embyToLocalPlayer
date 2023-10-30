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
from http.server import HTTPServer
from typing import Union

from utils.configs import configs, MyLogger
from utils.tools import translate_path_by_ini

ssl_context = ssl.SSLContext() if configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False) else None
bangumi_api_cache = {'cache_time': time.time(), 'bangumi': None}
sync_third_party_done_ids = {'trakt': [],
                             'bangumi': []}

logger = MyLogger()


def run_server(req_handler):
    server_address = ('127.0.0.1', 58000)
    httpd = HTTPServer(server_address, req_handler)
    logger.info('serving at %s:%d' % server_address)
    httpd.serve_forever()


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


def requests_urllib(host, params=None, _json=None, decode=False, timeout=5.0, headers=None, req_only=False,
                    http_proxy='', get_json=False, save_path='', retry=5, silence=False, res_only=False):
    _json = json.dumps(_json).encode('utf-8') if _json else None
    params = urllib.parse.urlencode(params) if params else None
    host = host + '?' + params if params else host
    req = urllib.request.Request(host)
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
            logger.error(f'urllib {try_times=} {host=}', silence=silence)
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


def change_emby_play_position(scheme, netloc, item_id, api_key, stop_sec, play_session_id, device_id, **_):
    if stop_sec > 10 * 60 * 60:
        logger.error('stop_sec error, check it')
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
        logger.error('stop_sec error, check it')
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
        return
    if server == 'emby':
        change_emby_play_position(stop_sec=stop_sec, **data)
    elif server == 'jellyfin':
        change_jellyfin_play_position(stop_sec=stop_sec, **data)
    elif server == 'plex':
        change_plex_play_position(stop_sec=stop_sec, **data)


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

    main_ep_info = requests_urllib(f'{scheme}://{netloc}{extra_str}/Users/{user_id}/Items/{data["item_id"]}',
                                   params=params, headers=headers, get_json=True)
    # if video is movie
    if 'SeasonId' not in main_ep_info:
        data['Type'] = main_ep_info['Type']
        data['ProviderIds'] = main_ep_info['ProviderIds']
        return [data]
    season_id = main_ep_info['SeasonId']
    series_id = main_ep_info['SeriesId']

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
        data['ParentIndexNumber'] = item.get('ParentIndexNumber')
        data['SeriesId'] = item['SeriesId']
        data['SeasonId'] = season_id
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
                    if not mount_disk_mode:
                        i['media_path'] = i['stream_url']
                break
    return episodes


def sync_third_party_for_eps(eps, provider):
    if not eps:
        return
    if not configs.check_str_match(eps[0]['netloc'], provider, 'enable_host', log=True):
        return
    useful_items = []
    for ep in eps:
        item_id = ep['item_id']
        if item_id in sync_third_party_done_ids[provider]:
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
