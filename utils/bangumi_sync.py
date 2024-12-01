import datetime
import os
import re
import sys
import time
import urllib.parse

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
except Exception:
    pass

from utils.configs import configs, MyLogger
from utils.tools import ThreadWithReturnValue

logger = MyLogger()


def bgm_season_date_check(media_server_date, bgm_info, diff_day):
    bgm_date = bgm_info['date']
    if not media_server_date:
        logger.info(f'bgm: media_server_date not found')
        return False
    media_server_date = datetime.date.fromisoformat(media_server_date)
    bgm_date = datetime.date.fromisoformat(bgm_date)
    diff = media_server_date - bgm_date
    if abs(diff.days) > diff_day:
        logger.info(f'bgm: check {media_server_date=} {bgm_date=} diff greater than {diff_day}')
        return False
    return True


def bangumi_sync_emby(emby, bgm, emby_eps: list = None, emby_ids: list = None):
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.emby_api import EmbyApi
    bgm: BangumiApiEmbyVer
    emby: EmbyApi

    item_infos = emby_eps if emby_eps else [emby.get_item(i) for i in emby_ids]
    item_info = item_infos[0]
    if item_info['Type'] != 'Episode':
        logger.info('bgm: skip, episode support only')
        return

    season_num = item_info['ParentIndexNumber']
    index_key = 'index' if emby_eps else 'IndexNumber'
    ep_nums = [i[index_key] for i in item_infos]
    if not season_num or season_num == 0 or 0 in ep_nums:
        logger.error(f'bgm: skip, {season_num=} {ep_nums=} contain zero')
        return
    series_id = item_info['SeriesId']
    series_info = emby.get_item(series_id)
    genres = series_info['Genres']
    gen_re = configs.raw.get('bangumi', 'genres', fallback='动画|anime')
    if not re.search(gen_re, ''.join(genres), flags=re.I):
        logger.error(f'bgm: skip, {genres=} not match {gen_re=}')
        return

    premiere_date = series_info['PremiereDate']
    emby_title = series_info['Name']
    ori_title = series_info.get('OriginalTitle', '')
    re_split = re.compile(r'[／/]')
    if re_split.search(ori_title):
        ori_title = re_split.split(ori_title)
        for _t in ori_title:
            if any((bool(0x3040 <= ord(i) <= 0x30FF)) for i in _t):
                ori_title = _t
                break
        else:
            ori_title = ori_title[0]

    emby_season_thread = ThreadWithReturnValue(target=emby.get_item, args=(item_info['SeasonId'],))
    search_and_sync(bgm=bgm, title=emby_title, ori_title=ori_title, premiere_date=premiere_date,
                    season_num=season_num, ep_nums=ep_nums, emby_season_thread=emby_season_thread,
                    emby=emby, eps_data=item_infos)


def bangumi_sync_plex(plex, bgm, plex_eps: list = None, rating_keys: list = None):
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.plex_api import PlexApi
    bgm: BangumiApiEmbyVer
    plex: PlexApi

    # api 的原始数据，非解析后的
    item_infos = [plex.get_metadata(i) for i in [_['rating_key'] for _ in plex_eps]] if plex_eps else [
        plex.get_metadata(i) for i in rating_keys]
    item_info = item_infos[0]
    if item_info.get('type') != 'episode':
        logger.info('bgm: skip, episode support only')
        return

    season_num = item_info['parentIndex']
    index_key = 'index'
    ep_nums = [i[index_key] for i in item_infos]
    if not season_num or season_num == 0 or 0 in ep_nums:
        logger.error(f'bgm: skip, {season_num=} {ep_nums=} contain zero')
        return
    series_id = item_info['grandparentRatingKey']
    series_info = plex.get_metadata(series_id)
    genres = [i['tag'] for i in series_info['Genre']]
    gen_re = configs.raw.get('bangumi', 'genres', fallback='动画|anime')
    if not re.search(gen_re, ''.join(genres), flags=re.I):
        logger.error(f'bgm: skip, {genres=} not match {gen_re=}')
        return

    premiere_date = series_info['originallyAvailableAt']
    emby_title = series_info['title']
    ori_title = series_info.get('originalTitle', '')
    search_and_sync(bgm=bgm, title=emby_title, ori_title=ori_title, premiere_date=premiere_date,
                    season_num=season_num, ep_nums=ep_nums)


def search_and_sync(bgm, title, ori_title, premiere_date, season_num, ep_nums, emby_season_thread=None,
                    emby=None, eps_data=None):
    bgm_data = bgm.emby_search(title=title, ori_title=ori_title, premiere_date=premiere_date)
    # 旧 api 可能返回第二季的数据，下面有 season_date_check，偷懒暂不处理
    if not bgm_data:
        logger.error(f'bgm: skip, bgm_data not found or not match\nbgm: {title=} {ori_title=} {premiere_date=}')
        return
    bgm_data = bgm_data[0]
    is_emby = bool(emby_season_thread)
    if is_emby:
        emby_season_thread.start()

    subject_id = bgm_data['id']
    bgm_sea_id, bgm_ep_ids = bgm.get_target_season_episode_id(
        subject_id=subject_id, target_season=season_num, target_ep=ep_nums)
    if not bgm_ep_ids:
        logger.info(f'bgm: skip, {subject_id=} {season_num=} {ep_nums=}, not exists or too big'
                    f' | https://bgm.tv/subject/{bgm_sea_id or subject_id}')
        return

    if max(ep_nums) < 12 or not bgm_data.get('rank'):
        bgm_sea_info = bgm.get_subject(bgm_sea_id)
        if is_emby:
            season_date = emby_season_thread.join().get('PremiereDate', '')[:10]
            if not bgm_season_date_check(season_date, bgm_sea_info, diff_day=15):
                logger.info(f'bgm: skip, season date check failed | https://bgm.tv/subject/{bgm_sea_id}')
                return
        else:
            if not bgm_season_date_check(premiere_date, bgm_sea_info, diff_day=180):
                logger.info(f'bgm: skip, episode date check failed | https://bgm.tv/subject/{bgm_sea_id}')
                return

    logger.info(f'bgm: get {bgm_data["name"]} S0{season_num}E{ep_nums} https://bgm.tv/subject/{bgm_sea_id}')
    bgm.mark_episode_watched(subject_id=bgm_sea_id, ep_id=bgm_ep_ids)
    log = f'bgm: sync {ori_title} S0{season_num}E{ep_nums}'
    for bgm_ep_id, ep_num in zip(bgm_ep_ids, ep_nums):
        log += f'\nS0{season_num}E{ep_num} https://bgm.tv/ep/{bgm_ep_id}'
    logger.info(log)
    bgm_check_ep_miss_mark(bgm=bgm, emby=emby, eps_data=eps_data, bgm_sea_id=bgm_sea_id)


def get_emby_season_watched_ep_key(emby, eps_data):
    if not emby.user_id:  # sync_via_stream_url 没有 user_id
        emby.user_id = configs.check_str_match(emby.host, 'dev', 'stream_userid', get_next=True)
    from utils.emby_api import EmbyApi
    emby: EmbyApi
    fist_ep = eps_data[0]
    ser_id, sea_id = fist_ep.get('SeriesId'), fist_ep.get('SeasonId')
    if not sea_id:
        return
    try:
        eps_data = emby.get_episodes(item_id=ser_id, season_id=sea_id, get_user_data=True)['Items']
    except ValueError as e:
        logger.error(f'skip get_emby_season_watched_ep_key: {str(e)[:50]}')
        return
    watched = []
    for ep in eps_data:
        if not ep['UserData']['Played']:
            continue
        ep_num, sea_num = ep.get('IndexNumber'), ep.get('ParentIndexNumber')
        if not all([ep_num, sea_num]):
            continue
        key = f'{sea_num}-{ep_num}'
        watched.append(key)
    return watched


def bgm_check_ep_miss_mark(bgm, emby, eps_data, bgm_sea_id):
    # 不支持 Plex。
    if not emby:
        return
    em_keys = get_emby_season_watched_ep_key(emby=emby, eps_data=eps_data)
    if not em_keys:
        return
    sea_num = int(em_keys[0].split('-')[0])
    bgm_eps_map = bgm.get_user_eps_collection(bgm_sea_id, map_state=True)
    bgm_keys = [f'{sea_num}-{ep_num}' for ep_num, stat in bgm_eps_map.items() if stat['watched']]
    miss_keys = set(em_keys) - set(bgm_keys)
    miss_keys = [int(i.split('-')[1]) for i in miss_keys]
    miss_ids = [bgm_eps_map.get(k)['id'] for k in miss_keys if bgm_eps_map.get(k)]
    if miss_ids:
        logger.info(f'bgm: miss sync {miss_keys}, re sync {len(miss_ids)} item')
        bgm.mark_episode_watched(subject_id=bgm_sea_id, ep_id=miss_ids)
        if len(miss_keys) != len(miss_ids):
            loss_keys = [k for k in miss_keys if not bgm_eps_map.get(k)]
            logger.info(f'bgm: loss sync {loss_keys}, may need check it manually')


def bangumi_sync_main(bangumi=None, eps_data: list = None, test=False, use_ini=False):
    if not eps_data and not use_ini and not test:
        raise ValueError('not eps_data and not test')
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.emby_api import EmbyApi
    from utils.plex_api import PlexApi
    bgm = bangumi or BangumiApiEmbyVer(
        username=configs.raw.get('bangumi', 'username', fallback=''),
        private=configs.raw.getboolean('bangumi', 'private', fallback=True),
        access_token=configs.raw.get('bangumi', 'access_token', fallback=''),
        http_proxy=configs.script_proxy)
    if test:
        bgm.get_me()
        return bgm
    if use_ini:
        from embyBangumi.embyBangumi import emby_bangumi
        emby = emby_bangumi(get_emby=True)
    else:
        fist_ep = eps_data[0]
        server = fist_ep['server']
        if server == 'plex':
            plex = PlexApi(host=f"{fist_ep['scheme']}://{fist_ep['netloc']}",
                           api_key=fist_ep['api_key'])
            bangumi_sync_plex(plex=plex, bgm=bgm, plex_eps=eps_data)
            return bgm
        emby = EmbyApi(host=f"{fist_ep['scheme']}://{fist_ep['netloc']}",
                       api_key=fist_ep['api_key'],
                       user_id=fist_ep['user_id'],
                       http_proxy=configs.script_proxy,
                       cert_verify=(not configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False))
                       )
    bangumi_sync_emby(emby=emby, bgm=bgm, emby_eps=eps_data)
    return bgm


def api_client_via_stream_url(url):
    from utils.emby_api import EmbyApi
    parsed_url = urllib.parse.urlparse(url)
    netloc, path_spit = parsed_url.netloc, parsed_url.path.split('/')
    item_id = str(path_spit[-2])
    query = dict(urllib.parse.parse_qsl(parsed_url.query))
    query: dict

    plex_token = query.get('X-Plex-Token')
    is_plex = bool(plex_token)
    jelly_sp = f'/{path_spit[1]}' if len(item_id) > 20 and path_spit[2] == 'videos' else ''
    api_key = plex_token or query['api_key']

    if is_plex:
        # 没找到好的媒体文件 key 反查条目的方法。
        # plex = PlexApi(host=f"{parsed_url.scheme}://{netloc}",
        #                api_key=api_key)
        # media_key = 'library/parts/3814/1687966436/file.mp4'
        logger.error('third_party_sync_via_stream_url: not support plex')
        return None, None, None
    emby = EmbyApi(host=f"{parsed_url.scheme}://{netloc}{jelly_sp}",
                   api_key=api_key,
                   user_id=None,
                   http_proxy=configs.script_proxy,
                   cert_verify=(not configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False)), )
    return emby, item_id, parsed_url


def bgm_sync_via_stream_url(url):
    from utils.bangumi_api import BangumiApiEmbyVer
    emby, item_id, parsed_url = api_client_via_stream_url(url)
    if not emby:
        time.sleep(1)
        return
    if not configs.check_str_match(parsed_url.netloc, 'bangumi', 'enable_host', log=True):
        time.sleep(1)
        return
    bgm = BangumiApiEmbyVer(
        username=configs.raw.get('bangumi', 'username', fallback=''),
        private=configs.raw.getboolean('bangumi', 'private', fallback=True),
        access_token=configs.raw.get('bangumi', 'access_token', fallback=''),
        http_proxy=configs.script_proxy)
    bangumi_sync_emby(emby=emby, bgm=bgm, emby_ids=[item_id])
    time.sleep(1)


def run_via_console():
    argv = sys.argv
    logger.info(f'{argv=}')
    if len(argv) == 2:
        bgm_sync_via_stream_url(url=argv[1])


if __name__ == '__main__':
    os.chdir(configs.cwd)
    run_via_console()
