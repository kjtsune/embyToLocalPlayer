import os.path
import sys
import time
import typing

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
except Exception:
    pass

from utils.configs import configs, MyLogger
from utils.bangumi_sync import api_client_via_stream_url, get_emby_season_watched_ep_key

logger = MyLogger()


def fill_trakt_ep_ids_by_series(trakt, emby, eps_data, force=False):
    from utils.trakt_api import TraktApi
    trakt: TraktApi
    eps_data = eps_data if isinstance(eps_data, list) else [eps_data]
    fist_ep = eps_data[0]
    _type = fist_ep['Type'].lower()
    if _type == 'movie' or fist_ep['server'] == 'plex':
        return eps_data
    providers = ['imdb', 'tvdb']
    all_pvd_ids = [{k.lower(): v for k, v in ep['ProviderIds'].items() if k.lower() in providers}
                   for ep in eps_data]
    all_pvd_ids = [i for i in all_pvd_ids if i]
    if len(all_pvd_ids) == len(eps_data) and not force:
        return eps_data

    series_info = emby.get_item(fist_ep['SeriesId'])
    season_num = fist_ep['ParentIndexNumber']
    series_pvd_ids = {k.lower(): v for k, v in series_info['ProviderIds'].items() if k.lower() in providers}
    if not series_pvd_ids:
        logger.info(f'trakt: not {providers} id in series_info')
        return eps_data
    tk_eps_ids = []
    if s_imdb_id := series_pvd_ids.get('imdb'):
        tk_eps_ids = trakt.get_series_single_season(ser_id=s_imdb_id, season_num=season_num)
    if not tk_eps_ids:
        tk_sr_id = None
        if tvdb_sr_id := series_pvd_ids.get('tvdb'):
            tk_sr_id = trakt.id_lookup(provider='tvdb', _id=tvdb_sr_id, _type='show')
        if tk_sr_id and tk_sr_id[0]['show']['ids']['tvdb'] == int(series_pvd_ids['tvdb']):
            tk_sr_id = tk_sr_id[0]['show']['ids']['trakt']
            tk_eps_ids = trakt.get_series_single_season(ser_id=tk_sr_id, season_num=season_num)
        else:
            logger.info(f'trakt: trakt series id not found via tvdb id')
            return eps_data
    tk_eps_ids = {i['number']: (i['ids'], i['title']) for i in tk_eps_ids}
    for ep in eps_data:
        ep_index = ep.get('index') or ep.get('IndexNumber')  # sync via stream 不是 index
        if not tk_eps_ids.get(ep_index):
            logger.info(f'fill_trakt_ep_ids_by_series: trakt info not found, {ep_index=}')
            continue
        ep['trakt_ids'], ep['trakt_title'] = tk_eps_ids[ep_index]
    return eps_data


def sync_ep_or_movie_to_trakt(trakt, eps_data, emby=None):
    trakt_ids_list = []
    allow = ['episode', 'movie']
    eps_data = fill_trakt_ep_ids_by_series(trakt=trakt, emby=emby, eps_data=eps_data)
    trakt_ids = None
    for ep in eps_data:
        trakt_ids_via_series = ep.get('trakt_ids')
        name = ep.get('basename', ep.get('Name'))
        _type = ep['Type'].lower()
        if _type not in allow:
            raise ValueError(f'type not in {allow}')
        providers = ['tmdb', 'imdb', 'tvdb']
        # imdb tvdb 都可能请求报错 500, tmdb 没有分集 id
        # tvdb 搜索电影可能匹配错误，有处理但浪费请求。
        # ?电视 tvdb 优先，因为集数的 imdb id 只能查到主条目，而不是分集。
        if _type != 'movie':
            providers.reverse()
        provider_ids = {k.lower(): v for k, v in ep['ProviderIds'].items() if k.lower() in providers}
        if not provider_ids and not trakt_ids_via_series:
            logger.info(f'trakt: not any {providers} id, skip | {name}')
            continue

        trakt_ids = None
        tk_type = 'movie' if _type == 'movie' else 'show'
        for provider in providers:
            if provider not in provider_ids:
                continue
            provider_id = provider_ids[provider]
            __type = 'episode' if provider in ['tvdb', 'imdb'] and _type == 'episode' else ''
            __type = __type if _type != 'movie' else 'movie'
            _trakt_ids = trakt.id_lookup(provider, provider_id, _type=__type)
            if not _trakt_ids:
                logger.info(f'trakt: id lookup not result {provider} {provider_id} | {name}')
                continue
            _trakt_ids = _trakt_ids[0]
            res_id = _trakt_ids[_trakt_ids['type']]['ids'][provider]
            if str(res_id) != provider_id:
                logger.info(f'trakt: id lookup not match {provider} {provider_id} | {name}')
                continue
            trakt_ids = _trakt_ids
            trakt_url = f"https://trakt.tv/{tk_type}s/{trakt_ids[tk_type]['ids']['slug']}"
            logger.info(f'trakt: match success {name} {trakt_url}')
            break

        if provider_ids and not trakt_ids and not trakt_ids_via_series:
            # 刚上映的剧集，trakt ep 的 tvdb id 可能缺失
            eps_data = fill_trakt_ep_ids_by_series(trakt=trakt, emby=emby, eps_data=eps_data, force=True)
            ep = [i for i in eps_data if ep['basename'] == i['basename']][0]
            trakt_ids_via_series = ep.get('trakt_ids')
            logger.info('trakt: force fill_trakt_ep_ids_by_series')

        if not trakt_ids and trakt_ids_via_series:
            trakt_ids = trakt_ids_via_series
            logger.info(f'trakt: match by trakt_ids_via_series, {ep["trakt_title"]=}')

        if not trakt_ids:
            logger.info(f'trakt: not trakt_ids, skip | {name}')
            break

        watched = trakt.get_watch_history(trakt_ids)
        if watched:
            logger.info(f'trakt: watch history exists, skip | {name}')
            continue
        logger.info(f'trakt: sync {name}')
        trakt_ids_list.append(trakt_ids)
    if trakt_ids_list:
        res = trakt.add_ep_or_movie_to_history(trakt_ids_list)
        logger.info('trakt:', res)
    if trakt_ids:
        trakt_check_ep_miss_mark(trakt=trakt, emby=emby, eps_data=eps_data, trakt_ids=trakt_ids)


def trakt_check_ep_miss_mark(trakt, emby, eps_data, trakt_ids):
    # 不支持 Plex。
    if not emby:
        return
    em_keys = get_emby_season_watched_ep_key(emby=emby, eps_data=eps_data)
    if not em_keys:
        return
    tr_keys = trakt.get_season_watched_via_ep_ids(trakt_ids, get_keys=True)
    tr_ids_map = trakt.get_season_via_ep_ids(trakt_ids, get_key_map=True)
    miss_keys = set(em_keys) - set(tr_keys)
    miss_ids = [tr_ids_map.get(k) for k in miss_keys if tr_ids_map.get(k)]
    for miss_id in miss_ids:  # 若遇到未上映却实际看过时（个别平台提前播放），该数据会有误，故再次检查。
        if trakt.check_is_watched(miss_id, _type='episode'):
            miss_ids.remove(miss_id)
    if miss_ids:
        logger.info(f'trakt: miss sync {miss_keys}, re sync {len(miss_ids)} item')
        trakt.add_ep_or_movie_to_history(miss_ids)
        if len(miss_keys) != len(miss_ids):
            loss_keys = [k for k in miss_keys if not tr_ids_map.get(k)]
            logger.info(f'trakt: loss sync {loss_keys}, may need check it manually')


def trakt_api_client(received_code=None):
    code_received = bool(received_code)
    from utils.trakt_api import TraktApi
    user_id = configs.raw.get('trakt', 'user_name', fallback='')
    client_id = configs.raw.get('trakt', 'client_id', fallback='')
    client_secret = configs.raw.get('trakt', 'client_secret', fallback='')
    if received_code:
        oauth_code = received_code
    else:
        oauth_code = configs.raw.get('trakt', 'oauth_code', fallback='').split('code=')
        oauth_code = oauth_code[1] if len(oauth_code) == 2 else oauth_code[0]
    if not all([user_id, client_id, client_secret]):
        raise ValueError('trakt: require user_name, client_id, client_secret')
    trakt = TraktApi(
        user_id=user_id,
        client_id=client_id,
        client_secret=client_secret,
        oauth_code=oauth_code,
        token_file=os.path.join(configs.cwd, 'trakt_token.json'),
        http_proxy=configs.script_proxy,
        code_received=code_received)
    return trakt


def trakt_sync_main(trakt=None, emby=None, eps_data=None, test=False):
    trakt = trakt or trakt_api_client()
    if test:
        trakt.test()
        return trakt
    else:
        if not emby:
            from utils.emby_api import EmbyApi
            eps_data = eps_data if isinstance(eps_data, list) else [eps_data]
            fist_ep = eps_data[0]
            if fist_ep['server'] != 'plex':
                emby = EmbyApi(host=f"{fist_ep['scheme']}://{fist_ep['netloc']}",
                               api_key=fist_ep['api_key'],
                               user_id=fist_ep['user_id'],
                               http_proxy=configs.script_proxy,
                               cert_verify=(not configs.raw.getboolean('dev', 'skip_certificate_verify',
                                                                       fallback=False))
                               )
        sync_ep_or_movie_to_trakt(trakt=trakt, emby=emby, eps_data=eps_data)
    return trakt


def emby_eps_data_generator(emby, item_id: typing.Union[str, list]):
    from utils.emby_api import EmbyApi
    emby: EmbyApi
    item_ids = [item_id] if isinstance(item_id, str) else item_id
    eps_data = emby.get_items(ids=item_ids,
                              types='Movie,Series,Video,Episode',
                              ext_params={'HasTmdbId': None}
                              )['Items']
    for ep in eps_data:
        ep['server'] = 'emby'
        ep['basename'] = os.path.basename(ep['Path'])
    return eps_data


def trakt_sync_via_stream_url(url):
    emby, item_id, parsed_url = api_client_via_stream_url(url)
    if not emby:
        time.sleep(1)
        return
    if not configs.check_str_match(parsed_url.netloc, 'trakt', 'enable_host', log=True):
        time.sleep(1)
        return
    eps_data = emby_eps_data_generator(emby=emby, item_id=item_id)
    trakt = trakt_api_client()
    trakt_sync_main(trakt=trakt, emby=emby, eps_data=eps_data, test=False)
    time.sleep(1)


def run_via_console():
    argv = sys.argv
    logger.info(f'{argv=}')
    if len(argv) == 2:
        trakt_sync_via_stream_url(url=argv[1])


if __name__ == '__main__':
    os.chdir(configs.cwd)
    run_via_console()
