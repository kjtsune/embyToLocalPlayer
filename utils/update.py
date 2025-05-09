import os.path
import shutil
import sys
import zipfile
from configparser import ConfigParser

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.configs import configs
from utils.net_tools import requests_urllib


def check_ini_diff(old_path, new_path, diff_path):
    print('diff checking...')
    old_conf = ConfigParser(allow_no_value=True)
    old_conf.read(old_path, encoding='utf-8-sig')
    new_conf = ConfigParser(allow_no_value=True)
    new_conf.read(new_path, encoding='utf-8-sig')
    diff_conf = ConfigParser(allow_no_value=True)

    have_diff = False
    for new_sect in new_conf.sections():
        new_se_d = new_conf[new_sect]
        if not old_conf.has_section(new_sect):
            diff_conf[new_sect] = new_se_d
            continue

        old_se_d = old_conf[new_sect]
        diff_se_d = {k: v for k, v in new_se_d.items() if k not in old_se_d or v != old_se_d.get(k)}
        if diff_se_d:
            diff_conf[new_sect] = diff_se_d
            have_diff = True

    if have_diff:
        print(f'diff {diff_path}')
        with open(diff_path, 'w', encoding='utf-8-sig') as f:
            diff_conf.write(f)


def main():
    url = 'https://github.com/kjtsune/embyToLocalPlayer/releases/latest/download/embyToLocalPlayer.zip'
    cwd = configs.cwd

    ini_old = configs.path
    ini_example = os.path.join(cwd, 'embyToLocalPlayer_example.ini')
    diff_path = os.path.join(cwd, 'embyToLocalPlayer_diff.ini')
    print('#' * 50)

    print(f'{configs.script_proxy=}')
    print('downloading...')
    zip_path = os.path.join(cwd, 'embyToLocalPlayer.zip')
    requests_urllib(url, save_path=zip_path)

    pycache = os.path.join(cwd, 'utils', '__pycache__')
    shutil.rmtree(pycache, ignore_errors=True)

    print('unpacking...')
    is_nt = os.name == 'nt'
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.startswith('embyToLocalPlayer_config'):
                continue
            if is_nt and name.startswith('etlp_run'):
                continue
            z.extract(name)
        print(f'\nnew example {ini_example}')
        with z.open('embyToLocalPlayer_config.ini', ) as z_f, open(ini_example, 'wb', ) as i_f:
            i_f.write(z_f.read())

    check_ini_diff(old_path=ini_old, new_path=ini_example, diff_path=diff_path)
    print()


if __name__ == '__main__':
    os.chdir(configs.cwd)
    main()
