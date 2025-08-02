import time
import tkinter as tk
import tkinter.font as tk_front

from utils.configs import configs, MyLogger
from utils.net_tools import requests_urllib
from utils.tools import scan_cache_dir, load_dict_jsons_in_folder

logger = MyLogger()


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('embyToLocalPlayer')
        self.root.attributes('-topmost', True)
        self.root.bind('<Motion>', lambda i: self.root.attributes('-topmost', False))
        self._ft_family = [i for i in ['Hiragino Sans GB', '微软雅黑', 'Microsoft YaHei', 'WenQuanYi Micro Hei']
                           if i in tk_front.families()]
        self._ft_family = self._ft_family[0] if self._ft_family else None
        self.ft = tk_front.Font(family=self._ft_family, size=10)
        self.width = None
        self.height = None
        self._bt_fg = '#000000'
        self._bt_bg = '#f0f0f0'
        # print(tk_front.families())
        # print(f'{self._ft_family=}')

    def set_window_size(self, width, height):
        screenwidth = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        align_str = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
        logger.trace(f'{align_str=}')
        self.width = width
        self.height = height
        self.root.geometry(align_str)
        self.root.resizable(width=False, height=False)

    def send_data_with_cmd(self, data, gui_cmd, destroy=True):
        data['gui_cmd'] = gui_cmd
        requests_urllib('http://127.0.0.1:58000/gui', _json=data)
        if destroy:
            self.root.destroy()

    def set_style(self, item, fg=None, bg=None, ft=None, ):
        ft = ft or self.ft
        if isinstance(item, tk.Button):
            fg = fg or self._bt_fg
            bg = bg or self._bt_bg
            item['fg'] = fg
            item['bg'] = bg
            item['font'] = ft

    def button_factory(self, width, height, text_cmd, x=0, y=0, row=None, column=None, fg=None, bg=None, ft=None, ):
        bt_num = len(text_cmd)
        r = row or 1
        c = column or 1
        if not row and not column:
            r = bt_num
        if row == 1 and not column:
            c = bt_num
        w = width // c
        h = height // r

        x_list = list(range(x, width + x, w))
        y_list = list(range(y, height + y, h))
        xy_list = [(x, y) for x in x_list for y in y_list]
        # print(f'{width=}\n{height=}\n{r=}\n{c=}\n{w=}\n{h=}\n{x_list=}\n{y_list=}\n{xy_list=}')
        result = []
        for index, (text, cmd) in enumerate(text_cmd):
            _x, _y = xy_list[index]
            bt = tk.Button(self.root)
            self.set_style(bt, fg=fg, bg=bg, ft=ft)
            bt['justify'] = 'center'
            bt['text'] = text
            bt.place(x=_x, y=_y, width=w, height=h)
            bt['command'] = cmd
            result.append(bt)
        return result

    def show_ask_button(self, data):
        width = 222
        height = 222
        # self.set_window_size(width=157, height=125)
        self.set_window_size(width=width, height=height)
        self.button_factory(width=width, height=height, row=6, column=None,
                            text_cmd=[
                                ('播放', lambda: self.send_data_with_cmd(data, 'play_check')),
                                ('下载 1% 后播放', lambda: self.send_data_with_cmd(data, 'download_play')),
                                ('下载（首尾优先）', lambda: self.send_data_with_cmd(data, 'download_not_play')),
                                ('下载（顺序下载）', lambda: self.send_data_with_cmd(data, 'download_only')),
                                ('删除当前下载', lambda: self.send_data_with_cmd(data, 'delete')),
                                ('下载管理器', self.show_task_manager),
                            ])

    def show_task_manager(self, sort=None):
        db = load_dict_jsons_in_folder(configs.cache_path, required_key='_id')
        db = {i['_id']: i for i in db}
        file_list = [i for i in scan_cache_dir() if i['_id'] in db]
        [i.update(db[i['_id']]) for i in file_list]
        if sort == 'name':
            file_list.sort(key=lambda i: (i['_id']))
        else:
            file_list.sort(key=lambda i: (i['progress'], i['stat'].st_mtime))
        item_list = []
        id_list = []
        for file in file_list:
            path = file['_id']
            id_list.append(path)
            progress = int(file['progress'] * 100)
            t = time.strftime('%m-%d %H:%M', time.localtime(file['stat'].st_mtime))
            item = f"{progress:0>3}% | {t} | {path}"
            item_list.append(item)

        self.root.title('缓存任务管理')
        self.set_window_size(888, 600)

        list_box = tk.Listbox(self.root, width=108, height=16, selectmode=tk.EXTENDED)

        scrollbar = tk.Scrollbar(self.root, orient='vertical')
        scrollbar.config(command=list_box.yview)
        scrollbar.place(x=self.width - 20, y=0, height=self.height - 30)

        list_box.config(yscrollcommand=scrollbar.set)
        # for x in range(50):
        #     list_box.insert(tkinter.END, str(x))
        for _ in item_list:
            logger.all(_)
            list_box.insert(tk.END, _)

        list_box['borderwidth'] = '0px'
        list_box['font'] = self.ft
        list_box['fg'] = '#333333'
        list_box['justify'] = 'left'
        list_box.place(x=0, y=0, width=self.width - 17, height=self.height - 27)

        def selection_event(operate):
            nonlocal id_list
            operate_id_index_list = []
            for _i in list_box.curselection()[::-1]:
                logger.debug(f'gui: select {list_box.get(_i)}')
                if operate == 'delete':
                    list_box.delete(_i)
                operate_id_index_list.append(id_list[_i])
            logger.info(f'gui: {operate} {operate_id_index_list}')
            if operate == 'delete':
                id_list = [i for i in id_list if i not in operate_id_index_list]
                data = dict(_id=operate_id_index_list)
                self.send_data_with_cmd(data=data, gui_cmd='delete_by_id', destroy=False)
            elif operate in ['resume', 'pause']:
                data_list = []
                for _id in operate_id_index_list:
                    _dict = dict(fake_name=_id, position=None)
                    _dict.update(db[_id])
                    data_list.append(_dict)
                data = dict(operate=operate, data_list=data_list)
                self.send_data_with_cmd(data=data, gui_cmd='resume_or_pause', destroy=False)

        text_cmd = [
            ('刷新列表', self.show_task_manager),
            ('暂停选中', lambda: selection_event('pause')),
            ('恢复选中', lambda: selection_event('resume')),
            ('名称排序', lambda: self.show_task_manager(sort='name')),
            ('删除选中', lambda: selection_event('delete')),
        ]
        self.button_factory(x=0, y=self.height - 30, width=self.width + 2, height=30, column=len(text_cmd),
                            text_cmd=text_cmd)


def show_ask_button(data):
    root = tk.Tk()
    app = App(root)
    app.show_ask_button(data)
    root.mainloop()


def play_by_timeout(root, sec=3):
    time.sleep(sec)
    root.destroy()


def show_task_manager():
    root = tk.Tk()
    app = App(root)
    app.show_task_manager()
    root.mainloop()

if __name__ == '__main__':
    _root = tk.Tk()
    _app = App(_root)
    _app.show_task_manager()
    # _app.show_ask_button(data={})
    _root.mainloop()
    pass
