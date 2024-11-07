import os
import re
import urllib.parse

from utils.configs import configs, MyLogger
from utils.net_tools import multi_thread_requests, requests_urllib, get_redirect_url
from utils.tools import (show_version_info, main_ep_to_title, main_ep_intro_time, logger_setup, version_prefer_emby,
                         match_version_range, sub_via_other_media_version, force_disk_mode_by_path,
                         translate_path_by_ini, debug_beep_win32)

logger = MyLogger()


def parse_received_data_emby(received_data):
    extra_data = received_data['extraData']
    show_version_info(extra_data=extra_data)
    main_ep_info = extra_data['mainEpInfo']
    episodes_info = extra_data['episodesInfo']
    playlist_info = extra_data['playlistInfo']
    # 随机播放剧集媒体库时，油猴没获取其他集的 Emby 标题，导致第一集回传数据失败，暂不处理。
    emby_title = main_ep_to_title(main_ep_info) if not playlist_info else None
    intro_time = main_ep_intro_time(main_ep_info)
    api_client = received_data['ApiClient']
    mount_disk_mode = True if received_data['mountDiskEnable'] == 'true' else False
    url = urllib.parse.urlparse(received_data['playbackUrl'])
    headers = received_data['request'].get('headers', {})
    is_emby = True if '/emby/' in url.path else False
    jellyfin_auth = headers.get('X-Emby-Authorization', headers.get('Authorization')) if not is_emby else ''
    jellyfin_auth = [i.replace('\'', '').replace('"', '').strip().split('=')
                     for i in jellyfin_auth.split(',')] if not is_emby else []
    jellyfin_auth = dict((i[0], i[1]) for i in jellyfin_auth if len(i) == 2)

    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    item_id = [str(i) for i in url.path.split('/')]
    item_id = item_id[item_id.index('Items') + 1]
    media_source_id = query.get('MediaSourceId')
    api_key = query['X-Emby-Token'] if is_emby else jellyfin_auth['Token']
    scheme, netloc = api_client['_serverAddress'].split('://')
    device_id = query['X-Emby-Device-Id'] if is_emby else jellyfin_auth['DeviceId']
    sub_index = int(query.get('SubtitleStreamIndex', -1))
    logger_setup(api_key=api_key, netloc=netloc)

    data = received_data['playbackData']
    media_sources = data['MediaSources']
    play_session_id = data['PlaySessionId']
    if media_source_id:
        media_source_info = [i for i in media_sources if i['Id'] == media_source_id][0]
    else:
        media_source_info = version_prefer_emby(media_sources) \
            if len(media_sources) > 1 and is_emby else media_sources[0]
        media_source_id = media_source_info['Id']
    file_path = media_source_info['Path']
    # stream_url = f'{scheme}://{netloc}{media_source_info["DirectStreamUrl"]}' # 可能为转码后的链接
    container = os.path.splitext(file_path)[-1]
    extra_str = '/emby' if is_emby else ''
    server_version = api_client['_serverVersion']
    _a, _b, _c, *_d = [int(i) for i in server_version.split('.')]
    stream_name = 'original' if match_version_range(server_version, ver_range='4.8.0.40-9') else 'stream'
    if media_source_info.get('Container') == 'bluray':  # emby
        container = '.m2ts'
    if media_source_info.get('VideoType') == 'BluRay':  # jellyfin
        stream_name = 'main'
        container = '.m3u8'
        logger.info('WARNING: bluray bdmv found, may trigger transcode')
    stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/{stream_name}{container}' \
                 f'?DeviceId={device_id}&MediaSourceId={media_source_id}' \
                 f'&PlaySessionId={play_session_id}&api_key={api_key}&Static=true'

    if configs.check_str_match(netloc, 'dev', 'redirect_check_host'):
        _stream_url = get_redirect_url(stream_url)
        if stream_url != _stream_url:
            stream_url = _stream_url
            logger.info(f'url redirect to {stream_url}')

    if configs.check_str_match(netloc, 'dev', 'stream_prefix', log=False):
        stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
        stream_url = f'{stream_prefix}{stream_url}'

    if stream_redirect := configs.ini_str_split('dev', 'stream_redirect'):
        stream_redirect = zip(stream_redirect[0::2], stream_redirect[1::2])
        for (_raw, _jump) in stream_redirect:
            stream_url = stream_url.replace(_raw, _jump)

    # 避免将内置字幕转为外挂字幕，内置字幕选择由播放器决定
    media_streams = media_source_info['MediaStreams']
    sub_index = sub_index if sub_index < 0 or media_streams[sub_index]['IsExternal'] else -2
    if not mount_disk_mode and sub_index == -1:
        sub_dict_list = [s for s in media_streams
                         if not mount_disk_mode and s['Type'] == 'Subtitle' and s['IsExternal']]
        for _sub in sub_dict_list:
            _sub['Order'] = configs.check_str_match(
                f"{str(_sub.get('Title', '') + ',' + _sub['DisplayTitle']).lower()}",
                'dev', 'subtitle_priority', log=False, order_only=True)
        sub_dict_list = [i for i in sub_dict_list if i['Order'] != 0]
        sub_dict_list.sort(key=lambda s: s['Order'])
        sub_dict = sub_dict_list[0] if sub_dict_list else {}
        sub_index = sub_dict.get('Index', sub_index)

    sub_jellyfin_str = '' if is_emby \
        else f'{item_id[:8]}-{item_id[8:12]}-{item_id[12:16]}-{item_id[16:20]}-{item_id[20:]}/'
    if not mount_disk_mode and sub_index >= 0:
        sub_emby_str = f'/{media_source_id}' if is_emby else ''
        # sub_data = media_source_info['MediaStreams'][sub_index]
        sub_data = [i for i in media_streams if i['Index'] == sub_index][0]
        fallback_sub = f'{extra_str}/videos/{sub_jellyfin_str}{item_id}{sub_emby_str}/Subtitles' \
                       f'/{sub_index}/0/Stream.{sub_data["Codec"]}?api_key={api_key}'
        sub_delivery_url = sub_data['Codec'] != 'sup' and sub_data.get('DeliveryUrl') or fallback_sub
    else:
        sub_delivery_url = None
    if not sub_delivery_url and configs.raw.get('dev', 'sub_extract_priority', fallback='') and main_ep_info:
        if sub_all_match := sub_via_other_media_version(main_ep_info['MediaSources']):
            _sub_source_id, _sub_index, _sub_codec = list(sub_all_match.values())[0]
            if not sub_all_match.get(media_source_id):
                sub_emby_str = f'/{_sub_source_id}' if is_emby else ''
                sub_delivery_url = f'{extra_str}/videos/{sub_jellyfin_str}{item_id}{sub_emby_str}/Subtitles' \
                                   f'/{_sub_index}/0/Stream.{_sub_codec}?api_key={api_key}'
                logger.info(f'other version sub found, url={sub_delivery_url}')
    sub_file = f'{scheme}://{netloc}{sub_delivery_url}' if sub_delivery_url else None
    mount_disk_mode = True if force_disk_mode_by_path(file_path) else mount_disk_mode
    media_path = translate_path_by_ini(file_path, debug=True) if mount_disk_mode else stream_url
    basename = os.path.basename(file_path)
    media_basename = os.path.basename(media_path)
    if '.m3u8' in file_path:
        media_path = stream_url = file_path

    pretty_title = configs.raw.getboolean('dev', 'pretty_title', fallback=True)
    media_title = f'{emby_title}  |  {basename}' if pretty_title and emby_title else basename
    media_title = media_title.replace('"', '”')

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
        media_source_id=media_source_id,
        file_path=file_path,
        stream_url=stream_url,
        fake_name=fake_name,
        position=position,
        total_sec=total_sec,
        user_id=user_id,
        basename=basename,
        media_basename=media_basename,
        main_ep_info=main_ep_info,
        episodes_info=episodes_info,
        playlist_info=playlist_info,
        intro_start=intro_time.get('intro_start'),
        intro_end=intro_time.get('intro_end'),
        server_version=server_version
    )
    return result


def parse_received_data_plex(received_data):
    extra_data = received_data.get('extraData', {})
    show_version_info(extra_data=extra_data)
    mount_disk_mode = True if received_data['mountDiskEnable'] == 'true' else False
    url = urllib.parse.urlparse(received_data['playbackUrl'])
    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    api_key = query['X-Plex-Token']
    client_id = query['X-Plex-Client-Identifier']
    front_end_ver = query['X-Plex-Version']
    netloc = url.netloc
    scheme = url.scheme
    logger_setup(api_key=api_key, netloc=netloc)
    metas = received_data['playbackData']['MediaContainer']['Metadata']
    _file = metas[0]['Media'][0]['Part'][0]['file']
    mount_disk_mode = True if force_disk_mode_by_path(_file) else mount_disk_mode
    base_info_dict = dict(
        server='plex',
        mount_disk_mode=mount_disk_mode,
        api_key=api_key,
        scheme=scheme,
        netloc=netloc,
        client_id=client_id,
        server_version=f'?;front_end/{front_end_ver}'
    )
    res_list = []
    meta_error = False
    for _index, meta in enumerate(metas):
        res = base_info_dict.copy()
        data = meta['Media'][0]
        item_id = data['id']
        duration = data.get('duration')
        if not duration:
            duration = 10 ** 12
            if not meta_error:
                meta_error = True
                logger.info('plex: some metadata missing, external subtitles and other functions may not work')
        file_path = data['Part'][0]['file']
        size = data['Part'][0]['size']
        stream_path = data['Part'][0]['key']
        stream_url = f'{scheme}://{netloc}{stream_path}?download=0&X-Plex-Token={api_key}'
        sub_dict_list = [i for i in data['Part'][0].get('Stream', []) if i.get('streamType') == 3 and i.get('key')]
        sub_selected = None
        sub_key = None
        if _index == 0:
            if sub_selected := [i for i in sub_dict_list if i.get('selected')]:
                sub_key = sub_selected[0].get('key')
        if (_index == 0 and not sub_selected) or _index != 0:
            for _sub in sub_dict_list:
                _sub['order'] = configs.check_str_match(
                    (_sub.get('title', '') + ',' + _sub['displayTitle']).lower(),
                    'dev', 'subtitle_priority', log=False, order_only=True)
            sub_dict_list = [i for i in sub_dict_list if i['order'] != 0]
            sub_dict = sub_dict_list[0] if sub_dict_list else {}
            sub_key = sub_dict.get('key')
        sub_file = f'{scheme}://{netloc}{sub_key}?download=0&X-Plex-Token={api_key}' \
            if not mount_disk_mode and sub_key else None
        media_path = translate_path_by_ini(file_path) if mount_disk_mode else stream_url
        basename = os.path.basename(file_path)
        media_basename = os.path.basename(media_path)
        title = meta.get('title', basename)
        media_title = title if title == basename else f'{title} | {basename}'
        media_title = media_title.replace('"', '”')

        seek = meta.get('viewOffset')
        rating_key = meta['ratingKey']
        start_sec = int(seek) // (10 ** 3) if seek and not query.get('extrasPrefixCount') else 0

        fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
        total_sec = duration // (10 ** 3)
        position = start_sec / total_sec

        provider_ids = [tuple(i['id'].split('://')) for i in meta['Guid']] if meta.get('Guid') else []
        provider_ids = {k.title(): v for (k, v) in provider_ids}

        trakt_emby_ver_dict = dict(
            Type=meta['type'],
            ProviderIds=provider_ids
        )

        playlist_diff_dict = dict(
            basename=basename,
            media_basename=media_basename,
            item_id=item_id,  # 视频流的 ID
            file_path=file_path,
            stream_url=stream_url,
            media_path=media_path,
            fake_name=fake_name,
            total_sec=total_sec,
            sub_file=sub_file,
            index=meta['index'] if meta['type'] == 'episode' else _index,  # 可能会有小数点吗
            size=size
        )

        other_info_dict = dict(
            start_sec=start_sec,
            media_title=media_title,
            duration=duration,
            rating_key=rating_key,
            position=position,
        )
        res.update(trakt_emby_ver_dict)
        res.update(playlist_diff_dict)
        res.update(other_info_dict)
        res_list.append(res)

    result = res_list[0].copy()
    result['list_eps'] = res_list
    return result


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
        sub_file = f'{scheme}://{netloc}{sub_path[0]}?download=0&X-Plex-Token={api_key}' if sub_path else None
        ep['sub_file'] = sub_file
    return result


def list_playlist_or_mix_s0(data):
    scheme = data['scheme']
    netloc = data['netloc']
    api_key = data['api_key']
    user_id = data['user_id']
    extra_str = '/emby' if data['server'] == 'emby' else ''
    device_id, play_session_id = data['device_id'], data['play_session_id']
    playlist_info = data['playlist_info']  # 电影或者音乐视频
    episodes_info = data['episodes_info']  # 可能是混合了S0的正确集数

    params = {'X-Emby-Token': api_key, }
    headers = {'accept': 'application/json', }
    headers.update(data['headers'])

    ids = [ep['Id'] for ep in playlist_info]
    params.update({'Fields': 'MediaSources,Path,ProviderIds',
                   'Ids': ','.join(ids), })
    playlist_data = requests_urllib(
        f'{scheme}://{netloc}{extra_str}/Users/{user_id}/Items',
        params=params, headers=headers, get_json=True)
    return playlist_data


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

    playlist_info = data.get('playlist_info')
    playlist_info and logger.info('playlist_info found')
    main_ep_info = data.get('main_ep_info') or requests_urllib(
        f'{scheme}://{netloc}{extra_str}/Users/{user_id}/Items/{data["item_id"]}',
        params=params, headers=headers, get_json=True)
    # if video is movie
    if not playlist_info and 'SeasonId' not in main_ep_info:
        data['Type'] = main_ep_info['Type']
        data['ProviderIds'] = main_ep_info['ProviderIds']
        return [data]
    season_id = main_ep_info.get('SeasonId')
    stream_name = 'original' if match_version_range(data['server_version'], ver_range='4.8.0.40-9') else 'stream'

    def version_filter(file_path, episodes_data):
        if playlist_info:
            return episodes_data
        ver_re = configs.raw.get('playlist', 'version_filter', fallback='').strip().strip('|')
        if not ver_re:
            return episodes_data
        try:
            def ep_to_key(_ep):
                return f"{_ep['ParentIndexNumber']}-{_ep['IndexNumber']}"

            ep_seq_cur_list = list(
                dict.fromkeys([ep_to_key(i) for i in episodes_data]))
            ep_num = len(ep_seq_cur_list)
        except KeyError:
            logger.error('version_filter: KeyError: some ep not IndexNumber')
            return episodes_data

        if ep_num == len(episodes_data):
            return episodes_data

        _ep_current = [i for i in episodes_data if i['Path'] == file_path][0]
        _current_key = ep_to_key(_ep_current)
        _cut_cur_list = ep_seq_cur_list[ep_seq_cur_list.index(_current_key):]
        _eps_after = [i for i in episodes_data if ep_to_key(i) in _cut_cur_list]
        _ep_index_list = sorted(list({i['IndexNumber'] for i in episodes_data}))
        official_rule = file_path.rsplit(' - ', 1)
        official_rule = official_rule[-1] if len(official_rule) == 2 else None
        clean_path = re.split(r'E\d\d?', file_path, maxsplit=1)[-1].strip()

        def check_with_sequence(__ep_data):
            __ep_success = []
            _cut_ep_data = __ep_data[__ep_data.index(_ep_current):]
            if len(_cut_cur_list) == 1:
                return [_ep_current]
            for _ep, _ep_cur in zip(_cut_ep_data, _cut_cur_list):
                if ep_to_key(_ep) == _ep_cur:
                    __ep_success.append(_ep)
            return __ep_success

        for _eps_data in (episodes_data, _eps_after):
            _cur_list = ep_seq_cur_list if _eps_data == episodes_data else _cut_cur_list
            for rule in (official_rule, clean_path):
                if not rule:
                    continue
                _ep_data = [i for i in _eps_data if rule in i['Path']]
                if len(_ep_data) == len(_cur_list):
                    logger.info(f'version_filter: success with {rule=}, pass {len(_cur_list)}')
                    return _ep_data
                else:
                    _success = check_with_sequence(_ep_data)
                    if len(_success) > 1:
                        logger.info(f'version_filter: success with {rule=}, seq pass {len(_success)}')
                        return _success
                    logger.info(f'version_filter: fail, {rule=}, pass {len(_ep_data)}, not equal {len(_cur_list)}')

        ini_re = re.findall(ver_re, file_path, re.I)
        ver_re = re.compile('|'.join(ini_re))
        _ep_data = [i for i in episodes_data if len(ver_re.findall(i['Path'])) == len(ini_re)]
        _ep_data_num = len(_ep_data)
        if _ep_data_num == ep_num:
            logger.info(f'version_filter: success with {ini_re=}')
            return _ep_data
        elif _ep_data_num == 0:
            logger.info(f'disable playlist, cuz version_filter: fail, ini regex match nothing. \n{file_path=}')
            return [_ep_current]
        else:
            _ep_success = check_with_sequence(_ep_data)
            _success = True if len(_ep_success) > 1 else False
            if _success:
                logger.info(f'version_filter: success with {ini_re=}, pass {len(_ep_success)} ep')
                return _ep_success
            else:
                if len(_cut_cur_list) > 1:
                    logger.info(f'disable playlist, cuz version_filter: fail, {ini_re=}')
                return [_ep_current]

    title_intro_map_fail = False

    def title_intro_index_map():
        nonlocal title_intro_map_fail
        _res = _title_map, _start_map, _end_map = {}, {}, {}
        if playlist_info:
            return _res
        episodes_info = data.get('episodes_info') or []
        title_intro_map_fail = not episodes_info

        for ep in episodes_info:
            if 'ParentIndexNumber' not in ep or 'IndexNumber' not in ep:
                title_intro_map_fail = True
                logger.info('disable title_intro_index_map, cuz season or ep index num error found')
                return _res
            if 'IndexNumberEnd' in ep:
                _t = f"{ep['SeriesName']} S{ep['ParentIndexNumber']}" \
                     f":E{ep['IndexNumber']}-{ep['IndexNumberEnd']} - {ep['Name']}"
            else:
                _t = f"{ep['SeriesName']} S{ep['ParentIndexNumber']}:E{ep['IndexNumber']} - {ep['Name']}"
            _key = f"{ep['ParentIndexNumber']}-{ep['IndexNumber']}"
            _title_map[_key] = _t

            if not ep.get('Chapters'):
                continue
            chapters = [i for i in ep['Chapters'][:5] if i.get('MarkerType')
                        and not str(i['StartPositionTicks']).endswith('000000000')
                        and not (i['StartPositionTicks'] == 0 and i['MarkerType'] == 'Chapter')]
            if not chapters or len(chapters) > 2:
                continue
            for i in chapters:
                if i['MarkerType'] == 'IntroStart':
                    _start_map[_key] = i['StartPositionTicks'] // (10 ** 7)
                elif i['MarkerType'] == 'IntroEnd':
                    _end_map[_key] = i['StartPositionTicks'] // (10 ** 7)

        return _res

    title_data, start_data, end_data = title_intro_index_map()
    pretty_title = configs.raw.getboolean('dev', 'pretty_title', fallback=True)

    def parse_item(item):
        source_info = item['MediaSources'][0]
        media_source_id = source_info["Id"]
        file_path = source_info['Path']
        fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
        item_id = item['Id']
        container = os.path.splitext(file_path)[-1]
        stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/{stream_name}{container}' \
                     f'?DeviceId={device_id}&MediaSourceId={media_source_id}' \
                     f'&PlaySessionId={play_session_id}&api_key={api_key}&Static=true'
        media_path = translate_path_by_ini(file_path) if mount_disk_mode else stream_url
        basename = os.path.basename(file_path)
        index = item.get('IndexNumber', 0)
        unique_key = f"{item.get('ParentIndexNumber')}-{index}"
        emby_title = title_data.get(unique_key)
        media_title = f'{emby_title}  |  {basename}' if pretty_title and emby_title else basename
        media_title = media_title.replace('"', '”')
        media_basename = os.path.basename(media_path)
        total_sec = int(source_info['RunTimeTicks']) // 10 ** 7

        media_streams = source_info['MediaStreams']
        sub_dict_list = [s for s in media_streams
                         if not mount_disk_mode and s['Type'] == 'Subtitle' and s['IsExternal']]
        for _sub in sub_dict_list:
            _sub['Order'] = configs.check_str_match(
                f"{str(_sub.get('Title', '') + ',' + _sub['DisplayTitle']).lower()}",
                'dev', 'subtitle_priority', log=False, order_only=True)
        sub_dict_list = [i for i in sub_dict_list if i['Order'] != 0]
        sub_dict_list.sort(key=lambda s: s['Order'])
        sub_dict = sub_dict_list[0] if sub_dict_list else {}
        sub_file = f'{scheme}://{netloc}/Videos/{item_id}/{source_info["Id"]}/Subtitles' \
                   f'/{sub_dict["Index"]}/Stream{os.path.splitext(sub_dict["Path"])[-1]}' if sub_dict else None
        sub_file = None if mount_disk_mode else sub_file

        result = data.copy()
        result['Type'] = item['Type']
        result['ProviderIds'] = item['ProviderIds']
        result['ParentIndexNumber'] = item.get('ParentIndexNumber')
        if not playlist_info:
            result['SeriesId'] = item['SeriesId']
            result['SeasonId'] = season_id
        result.update(dict(
            basename=basename,
            media_basename=media_basename,
            item_id=item_id,
            media_source_id=media_source_id,
            file_path=file_path,
            stream_url=stream_url,
            media_path=media_path,
            fake_name=fake_name,
            total_sec=total_sec,
            sub_file=sub_file,
            index=index,
            size=source_info['Size'],
            media_title=media_title,
            intro_start=start_data.get(unique_key),
            intro_end=end_data.get(unique_key),
        ))
        return result

    if playlist_info:
        def chunk_list(lst, chunk_size):
            for i in range(0, len(lst), chunk_size):
                yield lst[i:i + chunk_size]

        ids = [ep['Id'] for ep in playlist_info]
        _eps_parts = []
        for _ids in chunk_list(ids, 500):
            params.update({'Fields': 'MediaSources,Path,ProviderIds',
                           'Ids': ','.join(_ids), })
            _episodes = requests_urllib(
                f'{scheme}://{netloc}{extra_str}/Users/{user_id}/Items',
                params=params, headers=headers, get_json=True)
            _eps_parts.append(_episodes)
        episodes = _eps_parts[0]
        if len(_eps_parts) > 1:
            for _part in _eps_parts[1:]:
                episodes['Items'].extend(_part['Items'])
            logger.info(f'playlist_info items count: {len(ids)}, may too large')

    else:
        params.update({'Fields': 'MediaSources,Path,ProviderIds',
                       'SeasonId': season_id, })
        series_id = main_ep_info['SeriesId']
        url = f'{scheme}://{netloc}{extra_str}/Shows/{series_id}/Episodes'
        episodes = requests_urllib(url, params=params, headers=headers, get_json=True)
    # dump_json_file(episodes, 'z_playlist_movie.json')
    eps_error = [i for i in episodes['Items'] if 'Path' not in i or 'RunTimeTicks' not in i]
    if eps_error:
        ids_error = [i['MediaSources'][0]['Id'] for i in eps_error]
        eps_error = [f"{i['Name']}-{i['Id']}" for i in eps_error]
        logger.error(f'some ep miss path or runtime data, may leak error\n{eps_error}')
        if data['media_source_id'] in ids_error:
            logger.error(f'disable playlist and sync third party')  # total_sec 没有，不方便判断进度。
            data['eps_error'] = True
            return [data]
    episodes = [i for i in episodes['Items'] if 'Path' in i and 'RunTimeTicks' in i]
    episodes = version_filter(data['file_path'], episodes) if data['server'] == 'emby' else episodes
    episodes = [parse_item(i) for i in episodes]
    if title_intro_map_fail:
        debug_beep_win32()
        logger.info('pretty title: title_intro_map_fail')
        _file_path = data['file_path']
        for ep in episodes:
            if ep['file_path'] == _file_path:
                ep['media_title'] = data['media_title']

    if stream_redirect := configs.ini_str_split('dev', 'stream_redirect'):
        stream_redirect = zip(stream_redirect[0::2], stream_redirect[1::2])
        for (_raw, _jump) in stream_redirect:
            if _raw in episodes[0]['stream_url']:
                for i in episodes:
                    i['stream_url'] = i['stream_url'].replace(_raw, _jump)
                    if not mount_disk_mode:
                        i['media_path'] = i['stream_url']
                break

    if configs.check_str_match(netloc, 'dev', 'stream_prefix', log=False):
        stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
        for i in episodes:
            if i['stream_url'].startswith(stream_prefix):
                continue
            i['stream_url'] = f"{stream_prefix}{i['stream_url']}"
            if not mount_disk_mode:
                i['media_path'] = i['stream_url']

    return episodes
