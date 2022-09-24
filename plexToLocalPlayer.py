import os.path
import urllib.parse
import urllib.request


def plex_to_local_player(receive_info):
    mount_disk_mode = True if receive_info['mountDiskEnable'] == 'true' else False
    url = urllib.parse.urlparse(receive_info['playbackUrl'])
    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    api_key = query['X-Plex-Token']
    client_id = query['X-Plex-Client-Identifier']
    netloc = url.netloc
    scheme = url.scheme
    meta = receive_info['playbackData']['MediaContainer']['Metadata'][0]
    data = meta['Media'][0]
    item_id = data['id']
    duration = data['duration']
    file_path = data['Part'][0]['file']
    stream_path = data['Part'][0]['key']
    stream_mkv_url = f'{scheme}://{netloc}{stream_path}?download=1&X-Plex-Token={api_key}'
    sub_path = [i['key'] for i in data['Part'][0]['Stream'] if i.get('key') and i.get('selected')]
    sub_file = f'{scheme}://{netloc}{sub_path[0]}?download=1&X-Plex-Token={api_key}' if sub_path else None
    media_path = file_path if mount_disk_mode else stream_mkv_url
    media_title = os.path.basename(file_path) if not mount_disk_mode else None  # 播放 http 时覆盖标题

    seek = meta.get('viewOffset')
    rating_key = meta['ratingKey']
    start_sec = int(seek) // (10 ** 3) if seek and not query.get('extrasPrefixCount') else 0

    result = dict(
        server='plex',
        mount_disk_mode=mount_disk_mode,
        api_key=api_key,
        scheme=scheme,
        netloc=netloc,
        media_path=media_path,
        start_sec=start_sec,
        sub_file=sub_file,
        media_title=media_title,
        item_id=item_id,
        client_id=client_id,
        duration=duration,
        rating_key=rating_key,
    )
    return result
