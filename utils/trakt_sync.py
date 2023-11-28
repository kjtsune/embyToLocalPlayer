import os.path

from utils.configs import configs, MyLogger

logger = MyLogger()


def fill_trakt_ep_ids_by_series(trakt, eps_data, force=False):
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

    from utils.emby_api import EmbyApi
    emby = EmbyApi(host=f"{fist_ep['scheme']}://{fist_ep['netloc']}",
                   api_key=fist_ep['api_key'],
                   user_id=fist_ep['user_id'],
                   http_proxy=configs.script_proxy,
                   cert_verify=(not configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False))
                   )
    series_info = emby.get_item(fist_ep['SeriesId'])
    season_num = fist_ep['ParentIndexNumber']
    series_pvd_ids = {k.lower(): v for k, v in series_info['ProviderIds'].items() if k.lower() in providers}
    if not series_pvd_ids:
        logger.info(f'trakt: not {providers} id in series_info')
        return eps_data
    if s_imdb_id := series_pvd_ids.get('imdb'):
        tk_eps_ids = trakt.get_single_season(_id=s_imdb_id, season_num=season_num)
    else:
        tk_sr_id = trakt.id_lookup(provider='tvdb', _id=series_pvd_ids['tvdb'], _type='show')
        if tk_sr_id and tk_sr_id[0]['show']['ids']['tvdb'] == int(series_pvd_ids['tvdb']):
            tk_sr_id = tk_sr_id[0]['show']['ids']['trakt']
            tk_eps_ids = trakt.get_single_season(_id=tk_sr_id, season_num=season_num)
        else:
            logger.info(f'trakt: trakt series id not found via tvdb id')
            return eps_data
    tk_eps_ids = {i['number']: (i['ids'], i['title']) for i in tk_eps_ids}
    for ep in eps_data:
        ep['trakt_ids'], ep['trakt_title'] = tk_eps_ids[ep['index']]
    return eps_data


def sync_ep_or_movie_to_trakt(trakt, eps_data):
    eps_data = eps_data if isinstance(eps_data, list) else [eps_data]
    trakt_ids_list = []
    allow = ['episode', 'movie']
    eps_data = fill_trakt_ep_ids_by_series(trakt=trakt, eps_data=eps_data)
    for ep in eps_data:
        trakt_ids_via_series = ep.get('trakt_ids')
        name = ep.get('basename', ep.get('Name'))
        _type = ep['Type'].lower()
        if _type not in allow:
            raise ValueError(f'type not in {allow}')
        providers = ['imdb', 'tvdb']
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
            __type = 'episode' if provider == 'tvdb' and _type == 'episode' else ''
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
            eps_data = fill_trakt_ep_ids_by_series(trakt=trakt, eps_data=eps_data, force=True)
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
        return res


def trakt_sync_main(trakt=None, eps_data=None, test=False):
    from utils.trakt_api import TraktApi
    user_id = configs.raw.get('trakt', 'user_name', fallback='')
    client_id = configs.raw.get('trakt', 'client_id', fallback='')
    client_secret = configs.raw.get('trakt', 'client_secret', fallback='')
    oauth_code = configs.raw.get('trakt', 'oauth_code', fallback='').split('code=')
    oauth_code = oauth_code[1] if len(oauth_code) == 2 else oauth_code[0]
    if not all([user_id, client_id, client_secret]):
        raise ValueError('trakt: require user_name, client_id, client_secret')
    trakt = trakt or TraktApi(
        user_id=user_id,
        client_id=client_id,
        client_secret=client_secret,
        oauth_code=oauth_code,
        token_file=os.path.join(configs.cwd, 'trakt_token.json'),
        http_proxy=configs.script_proxy)
    if test:
        trakt.test()
        return trakt
    else:
        res = sync_ep_or_movie_to_trakt(trakt=trakt, eps_data=eps_data)
        res and logger.info('trakt:', res)
    return trakt
