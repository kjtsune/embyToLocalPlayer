import datetime
import os
import re

from utils.configs import configs, MyLogger
from utils.tools import ThreadWithReturnValue

logger = MyLogger()


def emby_bgm_season_date_check(emby_info, bgm_info):
    emby_date = emby_info.get('PremiereDate', '')[:10]
    bgm_date = bgm_info['date']
    if not emby_date:
        logger.info(f'bgm: emby season air date not found')
        return False
    emby_date = datetime.date.fromisoformat(emby_date)
    bgm_date = datetime.date.fromisoformat(bgm_date)
    diff = emby_date - bgm_date
    if abs(diff.days) > 15:
        logger.info(f'bgm: check {emby_date=} {bgm_date=} diff greater than 15')
        return False
    return True


def bangumi_sync(emby, bgm, emby_eps: list = None, emby_ids: list = None):
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.emby_api import EmbyApi
    bgm: BangumiApiEmbyVer
    emby: EmbyApi

    item_infos = emby_eps if emby_eps else [emby.get_item(i) for i in emby_ids]
    item_info = item_infos[0]
    if item_info['Type'] != 'Episode':
        logger.info('bgm: episode support only, skip')
        return

    season_num = item_info['ParentIndexNumber']
    index_key = 'index' if emby_eps else 'IndexNumber'
    ep_nums = [i[index_key] for i in item_infos]
    if not season_num or season_num == 0 or 0 in ep_nums:
        logger.error(f'bgm: {season_num=} {ep_nums=} contain zero, skip')
        return
    series_id = item_info['SeriesId']
    series_info = emby.get_item(series_id)
    genres = series_info['Genres']
    gen_re = configs.raw.get('bangumi', 'genres', fallback='动画|anime')
    if not re.search(gen_re, ''.join(genres), flags=re.I):
        logger.error(f'bgm: {genres=} not match {gen_re=}, skip')
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

    bgm_data = bgm.emby_search(title=emby_title, ori_title=ori_title, premiere_date=premiere_date)
    # 旧 api 可能返回第二季的数据，下面有 season_date_check，偷懒暂不处理
    if not bgm_data:
        logger.error(f'bgm: skip, bgm_data not found or not match\nbgm: {emby_title=} {ori_title=} {premiere_date=}')
        return

    bgm_data = bgm_data[0]
    emby_se_info_t = ThreadWithReturnValue(target=emby.get_item, args=(item_info['SeasonId'],))
    emby_se_info_t.start()

    subject_id = bgm_data['id']
    bgm_se_id, bgm_ep_ids = bgm.get_target_season_episode_id(
        subject_id=subject_id, target_season=season_num, target_ep=ep_nums)
    if not bgm_ep_ids:
        logger.info(f'bgm: {subject_id=} {season_num=} {ep_nums=}, not exists or too big, skip')
        return

    if max(ep_nums) < 12 or not bgm_data.get('rank'):
        emby_se_info = emby_se_info_t.join()
        bgm_se_info = bgm.get_subject(bgm_se_id)
        if not emby_bgm_season_date_check(emby_se_info, bgm_se_info):
            logger.info(f'bgm: season_date_check failed, skip | https://bgm.tv/subject/{bgm_se_id}')
            return

    logger.info(f'bgm: get {bgm_data["name"]} S0{season_num}E{ep_nums} https://bgm.tv/subject/{bgm_se_id}')
    for bgm_ep_id, ep_num in zip(bgm_ep_ids, ep_nums):
        bgm.mark_episode_watched(subject_id=bgm_se_id, ep_id=bgm_ep_id)
        logger.info(f'bgm: sync {ori_title} S0{season_num}E{ep_num} https://bgm.tv/ep/{bgm_ep_id}')


def bangumi_sync_main(bangumi=None, eps_data: list = None, test=False, use_ini=False):
    if not eps_data and not use_ini and not test:
        raise ValueError('not eps_data and not test')
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.emby_api import EmbyApi
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
            logger.error(f'bangumi_sync_by_eps not support {server=}')
            return bgm
        emby = EmbyApi(host=f"{fist_ep['scheme']}://{fist_ep['netloc']}",
                       api_key=fist_ep['api_key'],
                       user_id=fist_ep['user_id'],
                       http_proxy=configs.script_proxy,
                       cert_verify=(not configs.raw.getboolean('dev', 'skip_certificate_verify', fallback=False))
                       )
    bangumi_sync(emby=emby, bgm=bgm, emby_eps=eps_data)
    return bgm


if __name__ == '__main__':
    os.chdir('..')
    bangumi_sync_main(use_ini=True)
