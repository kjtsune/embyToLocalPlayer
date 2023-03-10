import os.path
import re


def path_translator():
    print('前提条件：当前电脑可以看到文件。文件在本地或者已经通过 smb 等挂载。\n')
    src_raw = input('请输入 emby 上显示的视频文件路径\n比如：/disk/e/movie/movie name (2000)/a_movie_file.mkv\n').strip()
    dst_raw = input('\n请输入当前电脑上对应的文件夹或文件路径\n比如：E:\\movie\\movie name (2000)\n').strip()
    src_split = re.split(r'[\\/]', src_raw)
    src_keep_sep = re.split(r'([\\/])', src_raw)
    dst_split = re.split(r'[\\/]', dst_raw)
    dst_keep_sep = re.split(r'([\\/])', dst_raw)
    src_pre = ''
    dst_pre = ''
    for src_node in src_split:
        if not src_node or src_node not in dst_split:
            continue
        src_index = src_keep_sep.index(src_node)
        src_pre = ''.join(src_keep_sep[:src_index])
        dst_index = dst_keep_sep.index(src_node)
        dst_pre = ''.join(dst_keep_sep[:dst_index])
        break
    if not src_pre:
        print('\n输入错误，请重试\n')
    else:
        print(f'\n[src]前缀是:\n{src_pre}')
        print(f'\n[dst]前缀是:\n{dst_pre}')
        print(f'\n替换后路径是:\n{os.path.normpath(src_raw.replace(src_pre, dst_pre, 1))}\n')
        return True


if __name__ == '__main__':
    while True:
        if path_translator():
            break
