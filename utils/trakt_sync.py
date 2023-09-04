from utils.configs import configs, MyLogger

logger = MyLogger()


def sync_ep_or_movie_to_trakt(trakt, emby=None, emby_ids=None, emby_items=None):
    emby_ids = emby_ids if not emby_ids or isinstance(emby_ids, list) else [emby_ids]
    emby_items = emby_items if not emby_items or isinstance(emby_items, list) else [emby_items]
    objs = emby_items or emby_ids
    trakt_ids_list = []
    allow = ['episode', 'movie']
    for obj in objs:
        item = obj if emby_items else emby.get_item(obj)
        if item['Type'].lower() not in allow:
            raise ValueError(f'type not in {allow}')
        provider_ids = item['ProviderIds']
        trakt_ids = None
        if imdb_id := provider_ids.get('Imdb'):
            trakt_ids = trakt.id_lookup('imdb', imdb_id)
        if tvdb_id := provider_ids.get('Tvdb') and not trakt_ids:
            trakt_ids = trakt.id_lookup('tvdb', tvdb_id)
        if not trakt_ids:
            logger.info('not trakt_ids')
            continue
        trakt_ids = trakt_ids[0]
        watched = trakt.get_watch_history(trakt_ids)
        if watched:
            logger.info('trakt history exists, skip requests trakt')
            continue

        trakt_ids_list.append(trakt_ids)
    res = trakt.add_ep_or_movie_to_history(trakt_ids_list)
    return res


def local_import_sync_ep_or_movie_to_trakt(emby_items=None, test=False):
    from utils.trakt_api import TraktApi
    user_id = configs.raw.get('trakt', 'user_id', fallback='')
    client_id = configs.raw.get('trakt', 'client_id', fallback='')
    client_secret = configs.raw.get('trakt', 'client_secret', fallback='')
    oauth_code = configs.raw.get('trakt', 'oauth_code', fallback='').split('code=')
    oauth_code = oauth_code[1] if len(oauth_code) == 2 else oauth_code[0]
    if not all([user_id, client_id, client_secret]):
        raise ValueError('require user_id, client_id, client_secret')
    trakt = TraktApi(
        user_id=user_id,
        client_id=client_id,
        client_secret=client_secret,
        oauth_code=oauth_code)
    if test:
        trakt.test()
        return trakt
    else:
        res = sync_ep_or_movie_to_trakt(trakt=trakt, emby_items=emby_items)
        return res
