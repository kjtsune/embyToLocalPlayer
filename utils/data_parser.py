import os
import re
import urllib.parse

from utils.configs import configs, MyLogger
from utils.net_tools import multi_thread_requests, requests_urllib, get_redirect_url
from utils.tools import (show_version_info, main_ep_to_title, main_ep_intro_time, logger_setup, version_prefer_emby,
                         match_version_range, sub_via_other_media_version, force_disk_mode_by_path,
                         translate_path_by_ini, debug_beep_win32, version_prefer_for_playlist)

logger = MyLogger()


def _get_sub_order_by_ini(_sub_list):
    for _sub in _sub_list:
        _sub['Order'] = configs.check_str_match(
            f"{str(_sub.get('Title', '') + ',' + _sub['DisplayTitle']).lower()}",
            'dev', 'subtitle_priority', log=False, order_only=True)


def subtitle_checker(media_streams, sub_index, mount_disk_mode, log=False):
    sub_inner_idx = 0
    sub_dict = {}
    # sub_index > 0 选中字幕；-1 未选中字幕；-3 用于播放列表仅检测外挂字幕，内置字幕由播放器决定
    sub_dict_list = [s for s in media_streams if s['Type'] == 'Subtitle']
    sub_ext_list = [s for s in sub_dict_list if s['IsExternal']]
    sub_inner_list = [s for s in sub_dict_list if not s['IsExternal']]

    if sub_index == -1 and not sub_ext_list and sub_inner_list:
        _get_sub_order_by_ini(sub_inner_list)
        sub_inner_match = [i for i in sub_inner_list if i['Order'] != 0]
        if sub_inner_match:  # 可能影响多版本补充备选时的字幕顺序，问题不大，先不管。
            sub_inner_match.sort(key=lambda s: s['Order'])
            sub_inner_match = sub_inner_match[0]
            sub_inner_idx = sub_inner_list.index(sub_inner_match) + 1
            log and logger.info(
                f"subtitles: cuz unspecified and not external -> subtitle_priority: --sid={sub_inner_idx} "
                f"(mpv only): {sub_inner_match.get('Title', '')},{sub_inner_match['DisplayTitle']}")

    if sub_index > 0:
        sub_dict = media_streams[sub_index]
        select_external = sub_dict.get('IsExternal')
        if not select_external:
            sub_inner_idx = sub_inner_list.index(sub_dict) + 1
        if select_external and mount_disk_mode:
            sub_dict = {}

    if sub_index in (-1, -3) and not mount_disk_mode:
        _get_sub_order_by_ini(sub_ext_list)
        sub_ext_list = [i for i in sub_ext_list if i['Order'] != 0]
        sub_ext_list.sort(key=lambda s: s['Order'])
        sub_dict = sub_ext_list[0] if sub_ext_list else {}
        sub_index = sub_dict.get('Index', sub_index)

    return sub_index, sub_inner_idx, sub_dict

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
    if media_source_id and media_source_id != 'undefined': # jellyfin 10.10.6
        media_source_info = [i for i in media_sources if i['Id'] == media_source_id][0]
    else:
        media_source_info = version_prefer_emby(media_sources) \
            if len(media_sources) > 1 and is_emby else media_sources[0]
        media_source_id = media_source_info['Id']
    # strm 多版本似乎找不到其他版本服务器文件路径，需要额外请求分集数据。不过不需要读盘模式，还好。
    # 因此 strm 多版本 且 is_http_source 时，正确播放，但文件标题只有一种，先不处理。
    source_path = media_source_info['Path']  # strm 的时候和 file_path 不一致，是 strm 里的地址文本
    file_path = source_path if main_ep_info.get('Type') == 'TvChannel' else  main_ep_info['Path']  # 多版本时候有误，直播源时没有。
    is_strm = file_path != source_path and file_path.endswith('.strm') or media_source_info.get('Container') == 'strm'
    is_http_source =  source_path.startswith('http')
    strm_direct = configs.check_str_match(netloc, 'dev', 'strm_direct_host', log_by=True)
    if not is_strm or (is_strm and not is_http_source):
        file_path = source_path

    if is_strm and is_http_source and len(media_sources) > 1 and media_source_info['Name'] not in file_path:
        basename = os.path.basename(file_path)
        # Season 0/S0E04-ver-a.strm Specials/S0E04-ver-b.strm 这种情况也可能导致路径文件夹名称拼装错误。
        for _m in media_sources:
            if _m['Name'] in basename:  # S01E01.mkv 这种无解
                file_path = file_path.replace(_m['Name'], media_source_info['Name'])
                break

    # stream_url = f'{scheme}://{netloc}{media_source_info["DirectStreamUrl"]}' # 可能为转码后的链接
    basename = os.path.basename(file_path)
    container = os.path.splitext(file_path)[-1]
    extra_str = '/emby' if is_emby else ''
    server_version = api_client['_serverVersion']
    _a, _b, _c, *_d = [int(i) for i in server_version.split('.')]
    stream_name = 'original' if match_version_range(server_version, ver_range='4.8.0.40-9') else 'stream'
    if media_source_info.get('Container') == 'bluray':  # emby bdmv 根据路径选播放器也够用了，先不管
        container = '.m2ts'
    if media_source_info.get('VideoType') == 'BluRay':  # jellyfin
        stream_name = 'main'
        container = '.m3u8'
        logger.info('WARNING: bluray bdmv found, may trigger transcode')
    stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/{stream_name}{container}' \
                 f'?DeviceId={device_id}&MediaSourceId={media_source_id}' \
                 f'&PlaySessionId={play_session_id}&api_key={api_key}&Static=true'
    stream_netloc = netloc
    if is_http_direct_strm := is_strm and strm_direct and is_http_source:
        stream_url = source_path
        stream_netloc = urllib.parse.urlparse(stream_url).netloc

    mount_disk_mode = received_data['mountDiskEnable'] == 'true'
    if not mount_disk_mode or is_http_direct_strm:
        stream_url = configs.string_replace_by_ini_pair(stream_url, 'dev', 'stream_redirect')

        if configs.check_str_match(stream_netloc, 'dev', 'redirect_check_host'):
            _stream_url = get_redirect_url(stream_url)
            if stream_url != _stream_url:
                logger.info(f'url redirect found {stream_url}')
                stream_url = _stream_url

        if configs.check_str_match(stream_netloc, 'dev', 'stream_prefix', log=False):
            stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
            stream_url = f'{stream_prefix}{stream_url}'

    if is_strm and not strm_direct or is_http_source:
        mount_disk_mode = False
    if not is_http_source and force_disk_mode_by_path(file_path):
        mount_disk_mode = True
    if is_strm and not is_http_source:
        logger.info(f'{source_path=}')

    if mount_disk_mode:  # 肯定不会是 http
        if is_strm:
            if strm_direct:
                media_path = translate_path_by_ini(source_path)
            else:  # strm 文件无法直接播放
                media_path = stream_url
                mount_disk_mode = False
        else:
            media_path = translate_path_by_ini(file_path)
    else:
        if is_strm and strm_direct and not is_http_direct_strm:
            media_path = source_path
        else:
            media_path = stream_url

    media_streams = media_source_info['MediaStreams']
    # mpv 可传递首集内封字幕选中序号，其他播放器由播放器自身规则决定。
    sub_index, sub_inner_idx, sub_dict = subtitle_checker(media_streams, sub_index, mount_disk_mode, log=True)
    sub_jellyfin_str = '' if is_emby \
        else f'{item_id[:8]}-{item_id[8:12]}-{item_id[12:16]}-{item_id[16:20]}-{item_id[20:]}/'
    if sub_dict:
        sub_emby_str = f'/{media_source_id}' if is_emby else ''
        # sub_data = media_source_info['MediaStreams'][sub_index]
        fallback_sub = f'{extra_str}/videos/{sub_jellyfin_str}{item_id}{sub_emby_str}/Subtitles' \
                       f'/{sub_index}/0/Stream.{sub_dict["Codec"]}?api_key={api_key}'
        sub_delivery_url = sub_dict['Codec'] != 'sup' and sub_dict.get('DeliveryUrl') or fallback_sub
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
    if '.m3u8' in file_path:
        media_path = stream_url = file_path

    pretty_title = configs.raw.getboolean('dev', 'pretty_title', fallback=True)
    media_title = f'{emby_title}  |  {basename}' if pretty_title and emby_title else basename
    title_trans = configs.media_title_translate(get_trans=True)
    if title_trans:
        media_title = media_title.translate(title_trans)
        _title_trans = {chr(k): v for k, v in title_trans.items()}
        logger.info(f'media_title_translate {_title_trans}')

    seek = query['StartTimeTicks']
    start_sec = int(seek) // (10 ** 7) if seek else 0
    server = 'emby' if is_emby else 'jellyfin'

    fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
    total_sec = int(media_source_info.get('RunTimeTicks', 0)) // 10 ** 7 or 3600 * 24
    position = start_sec / total_sec
    user_id = query['UserId']
    media_basename = os.path.basename(media_path)
    size = int(media_source_info.get('Size', 0)) or 0

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
        server_version=server_version,
        is_strm=is_strm,
        strm_direct=strm_direct,
        is_http_source=is_http_source,
        source_path=source_path,
        is_http_direct_strm=is_http_direct_strm,
        sub_inner_idx=sub_inner_idx,
        size=size,
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
    title_trans = configs.media_title_translate(get_trans=True)
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
        if title_trans:
            media_title = media_title.translate(title_trans)

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

    def fill_data_type_provider_ids(): # sync trakt required
        data.update(main_ep_info)
        return data

    # if video is movie
    if not playlist_info and 'SeasonId' not in main_ep_info:
        return [fill_data_type_provider_ids()]
    season_id = main_ep_info.get('SeasonId')
    stream_name = 'original' if match_version_range(data['server_version'], ver_range='4.8.0.40-9') else 'stream'

    main_ep_basename = data['basename']
    is_strm = data['is_strm']
    is_http_source = data['is_http_source']
    strm_direct = data['strm_direct']
    is_http_direct_strm = data['is_http_direct_strm']

    def strm_file_name_sync(file_path, episodes_data):
        if is_strm and not is_http_source:
            for i in episodes_data:
                i['Path'] = i['MediaSources'][0]['Path']

        return episodes_data


    def version_filter(file_path, episodes_data):
        if playlist_info:
            return episodes_data
        ver_re = configs.raw.get('playlist', 'version_filter', fallback='').strip().strip('|')
        if not ver_re:
            return episodes_data
        try:
            def ep_to_key(_ep):
                return f"{_ep['ParentIndexNumber']}-{_ep['IndexNumber']}"

            ep_raw_cur_list = [ep_to_key(i) for i in episodes_data]
            ep_seq_cur_list = list(dict.fromkeys(ep_raw_cur_list))
            ep_num = len(ep_seq_cur_list)
        except KeyError:
            logger.error('version_filter: KeyError: some ep not IndexNumber')
            return episodes_data

        if ep_num == len(episodes_data):
            return episodes_data

        _ep_current = [i for i in episodes_data if file_path in (i['Path'], i['MediaSources'][0]['Path'])][0]
        _current_key = ep_to_key(_ep_current)
        _cur_count = ep_raw_cur_list.count(_current_key)
        if _cur_count > 1:  # 适配首集多版本但过于相似的情况
            _cur_raw_index = ep_raw_cur_list.index(_current_key)
            del episodes_data[_cur_raw_index + 1:_cur_raw_index + _cur_count]
            del ep_raw_cur_list[_cur_raw_index + 1:_cur_raw_index + _cur_count]
            episodes_data[_cur_raw_index] = _ep_current
            if ep_num == len(episodes_data):  # 只有首集是多版本时
                return episodes_data
        _cut_cur_list = ep_seq_cur_list[ep_seq_cur_list.index(_current_key):]
        _eps_after = [i for i in episodes_data if ep_to_key(i) in _cut_cur_list]
        _ep_index_list = sorted(list({i['IndexNumber'] for i in episodes_data}))
        official_rule = file_path.rsplit(' - ', 1)
        official_rule = official_rule[-1] if len(official_rule) == 2 else None
        clean_path = re.split(r'E\d\d?', file_path, maxsplit=1)[-1].strip()
        if len(clean_path) <= 5:  # 仅文件格式的话，不够严谨
            clean_path = None

        # 会禁用前向播放列表。
        def check_with_sequence(__ep_data):
            __ep_success = []
            _cut_ep_data = __ep_data[__ep_data.index(_ep_current):]
            if len(_cut_cur_list) == 1:
                return [_ep_current]
            for _ep, _ep_cur in zip(_cut_ep_data, _cut_cur_list):
                if ep_to_key(_ep) == _ep_cur:
                    __ep_success.append(_ep)
            return __ep_success

        builtin_res = []
        for _eps_data in (episodes_data, _eps_after):
            if builtin_res:
                break
            _cur_list = ep_seq_cur_list if _eps_data == episodes_data else _cut_cur_list
            for rule in (official_rule, clean_path):
                if not rule:
                    continue
                _ep_data = [i for i in _eps_data if rule in i['Path']]
                if len(_ep_data) == len(_cur_list) and len(_cur_list) > 1:
                    logger.info(f'version_filter: success with {rule=}, pass {len(_cur_list)}')
                    return _ep_data
                else:
                    _success = check_with_sequence(_ep_data)
                    if len(_success) > 1:
                        logger.info(f'version_filter: success with {rule=}, seq pass {len(_success)}')
                        builtin_res = _success
                        break

        ver_re = ''.join(ver_re.split('\n'))  # 多行转单行
        ini_re = re.findall(ver_re, file_path, re.I)
        ver_re = re.compile('|'.join(ini_re))
        _ep_data = [i for i in episodes_data if len(ver_re.findall(i['Path'])) == len(ini_re)]
        _ep_data_num = len(_ep_data)
        if _ep_data_num == ep_num:
            logger.info(f'version_filter: success with {ini_re=}')
            return _ep_data
        ini_res = []
        _ep_success_map = {ep_to_key(i): i for i in _ep_data}
        prefer_eps = version_prefer_for_playlist(_ep_success_map, _current_key, file_path, ep_raw_cur_list,
                                                 episodes_data)
        if _ep_data_num == 0:
            if not prefer_eps:
                if builtin_res:
                    return builtin_res
                else:
                    logger.info(f'disable playlist, cuz version_filter: fail, ini regex match nothing. \n{file_path=}')
                    return [_ep_current]
        else:
            _ep_success = check_with_sequence(_ep_data)
            _success = True if len(_ep_success) > 1 else False
            if not prefer_eps:
                if _success:
                    logger.info(f'version_filter: success with {ini_re=}, pass {len(_ep_success)} ep')
                    if len(builtin_res) > len(_ep_success):
                        return builtin_res
                    return _ep_success
                else:
                    if builtin_res:
                        return builtin_res
                    if len(_cut_cur_list) > 1:
                        logger.info(f'disable playlist, cuz version_filter: fail, {ini_re=}')
                    return [_ep_current]
            else:
                ini_res = _ep_success
        filter_res = ini_res if len(ini_res) > len(builtin_res) else builtin_res
        if len(filter_res) <= 1:
            return prefer_eps
        fist_cur, last_cur = ep_to_key(filter_res[0]), ep_to_key(filter_res[-1])
        fist_index, last_index = ep_seq_cur_list.index(fist_cur), ep_seq_cur_list.index(last_cur)
        fist_part, last_part = prefer_eps[:fist_index], prefer_eps[last_index + 1:]
        res = fist_part + filter_res + last_part
        return res

    title_intro_map_fail = False

    def title_intro_index_map():
        nonlocal title_intro_map_fail
        _res = _title_map, _start_map, _end_map = {}, {}, {}
        if playlist_info:
            return _res
        episodes_info = data.get('episodes_info') or []
        title_intro_map_fail = not episodes_info

        for ep in episodes_info:
            if ep['SeasonId'] != season_id:  # 影响S0混播，使用频率过低，先不管
                continue
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
    need_check_inner_sub = {True: -1, False: -3}[bool(data.get('sub_inner_idx'))]

    def parse_item(item, order):
        source_info = item['MediaSources'][0]
        media_source_id = source_info["Id"]
        file_path = item['Path']
        source_path = source_info['Path']
        fake_name = os.path.splitdrive(file_path)[1].replace('/', '__').replace('\\', '__')
        item_id = item['Id']
        container = os.path.splitext(file_path)[-1]
        stream_url = f'{scheme}://{netloc}{extra_str}/videos/{item_id}/{stream_name}{container}' \
                     f'?DeviceId={device_id}&MediaSourceId={media_source_id}' \
                     f'&PlaySessionId={play_session_id}&api_key={api_key}&Static=true'
        if is_http_direct_strm:
            stream_url = source_path

        if mount_disk_mode:  # 肯定不会是 http
            if is_strm:
                if strm_direct:
                    media_path = translate_path_by_ini(source_path)
                else:  # strm 文件无法直接播放
                    media_path = stream_url
            else:
                media_path = translate_path_by_ini(file_path)
        else:
            if is_strm and strm_direct and not is_http_direct_strm:
                media_path = source_path
            else:
                media_path = stream_url

        basename = os.path.basename(file_path)
        index = item.get('IndexNumber', 0)
        unique_key = f"{item.get('ParentIndexNumber')}-{index}"
        emby_title = title_data.get(unique_key)
        media_title = f'{emby_title}  |  {basename}' if pretty_title and emby_title else basename
        media_title = media_title.replace('"', '”')
        media_basename = os.path.basename(media_path)
        total_sec = int(source_info.get('RunTimeTicks', 0)) // 10 ** 7 or 3600 * 24
        size = int(source_info.get('Size', 0)) or 0

        media_streams = source_info['MediaStreams']
        sub_index, sub_inner_idx, sub_dict = subtitle_checker(media_streams, need_check_inner_sub, mount_disk_mode)

        sub_file = None
        if sub_dict:
            sub_file = f'{scheme}://{netloc}/Videos/{item_id}/{source_info["Id"]}/Subtitles' \
                       f'/{sub_dict["Index"]}/Stream{os.path.splitext(sub_dict["Path"])[-1]}'

        result = data.copy()
        result['Type'] = item['Type']
        result['ProviderIds'] = item['ProviderIds']
        result['ParentIndexNumber'] = item.get('ParentIndexNumber')
        if not playlist_info:
            result['SeriesId'] = item['SeriesId']
            result['SeasonId'] = season_id
        if basename != main_ep_basename:
            for none_key in ['start_sec', 'main_ep_info', 'episodes_info']:
                result[none_key] = None
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
            size=size,  # Jellyfin strm 没有这个键
            media_title=media_title,
            intro_start=start_data.get(unique_key),
            intro_end=end_data.get(unique_key),
            order=order,
            sub_inner_idx=sub_inner_idx,
        ))
        return result

    if playlist_info:
        # jellyfin 花絮 疑似也会被当作播放列表数据。
        def chunk_list(lst, chunk_size):
            for i in range(0, len(lst), chunk_size):
                yield lst[i:i + chunk_size]
        # 限制随机播放列表条目数量避免 HTTP Error 414: URI Too Long
        ids = [ep['Id'] for ep in playlist_info][:200]
        _eps_parts = []
        for _ids in chunk_list(ids, 200):
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
        # 改用 season_id，避免S0命名不规范导致美化标题失败，不知道会不会影响S0混播。
        url = f'{scheme}://{netloc}{extra_str}/Shows/{season_id}/Episodes'
        episodes = requests_urllib(url, params=params, headers=headers, get_json=True)
    # dump_json_file(episodes, 'z_playlist_movie.json')
    eps_error = [i for i in episodes['Items'] if 'Path' not in i or 'RunTimeTicks' not in i]
    path_error = [i for i in eps_error if 'Path' not in i]
    if eps_error:
        # total_sec 没有，不方便判断进度。
        ids_error = [i['MediaSources'][0]['Id'] for i in path_error]
        try:
            eps_error = [f"E{i['IndexNumber']}-{i['Name']}-id={i['Id']}" for i in eps_error]
        except KeyError:
            logger.error('disable playlist, IndexNumber miss')
            return [fill_data_type_provider_ids()]
        logger.error(f'some ep miss path or runtime data, may leak error\n{eps_error}')
        if data['media_source_id'] in ids_error:
            logger.error(f'disable playlist, Path miss')
            return [fill_data_type_provider_ids()]

    episodes = [i for i in episodes['Items'] if 'Path' in i]
    episodes = strm_file_name_sync(data['file_path'], episodes)
    episodes = version_filter(data['file_path'], episodes) if data['server'] == 'emby' else episodes
    episodes = [parse_item(i, o) for (o, i) in enumerate(episodes)]

    if title_intro_map_fail:
        debug_beep_win32()
        logger.info('pretty title: title_intro_map_fail')
        _file_path = data['file_path']
        for ep in episodes:
            if ep['file_path'] == _file_path:
                ep['media_title'] = data['media_title']

    stream_redirect = configs.check_str_match(episodes[0]['stream_url'], 'dev', 'stream_redirect', get_pair=True)
    title_trans = configs.media_title_translate(get_trans=True, log=False)
    if stream_redirect or title_trans:
        for i in episodes:
            if stream_redirect:
                i['stream_url'] = i['stream_url'].replace(stream_redirect[0], stream_redirect[1])
                if not mount_disk_mode:
                    i['media_path'] = i['stream_url']
            if title_trans:
                i['media_title'] = i['media_title'].translate(title_trans)

    if configs.check_str_match(netloc, 'dev', 'stream_prefix', log=False):
        stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
        for i in episodes:
            if i['stream_url'].startswith(stream_prefix):
                continue
            i['stream_url'] = f"{stream_prefix}{i['stream_url']}"
            if not mount_disk_mode:
                i['media_path'] = i['stream_url']

    return episodes
