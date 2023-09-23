import os.path

from utils.configs import configs, MyLogger

logger = MyLogger()


def sync_ep_or_movie_to_trakt(trakt, emby=None, emby_ids=None, eps_data=None):
    emby_ids = emby_ids if not emby_ids or isinstance(emby_ids, list) else [emby_ids]
    eps_data = eps_data if not eps_data or isinstance(eps_data, list) else [eps_data]
    objs = eps_data or emby_ids
    trakt_ids_list = []
    allow = ['episode', 'movie']
    for obj in objs:
        name = obj.get('basename', obj.get('Name'))
        item = obj if eps_data else emby.get_item(obj)
        _type = item['Type'].lower()
        if _type not in allow:
            raise ValueError(f'type not in {allow}')
        providers = ['imdb', 'tvdb']
        provider_ids = {k.lower(): v for k, v in item['ProviderIds'].items() if k.lower() in providers}
        if not provider_ids:
            logger.info(f'trakt: not {providers} id, skip | {name}')
            continue

        trakt_ids = None
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
            tk_type = 'movie' if _type == 'movie' else 'show'
            trakt_url = f"https://trakt.tv/{tk_type}s/{trakt_ids[tk_type]['ids']['slug']}"
            logger.info(f'trakt: match success {name} {trakt_url}')
            break

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
