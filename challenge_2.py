#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re
import json
import string
import xlwings
import requests
import threading
import subprocess
from lxml import etree
from time import sleep
from pathlib import Path
from random import randint
from urllib.parse import quote
from playsound import playsound
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, create_engine


# 创建对象的基类:
Base = declarative_base()


# 定义Bank对象:
class Bank(Base):
    # 表的名字:
    __tablename__ = 'banks'
    '''表的结构:
        id | catagory | content | options[item0, item1, item2, item3] | answer | note | bounds
        序号 |  题型  |   题干   |                  选项               |  答案  | 注释 | 位置(保存时丢弃)
    '''
    id = Column(Integer, primary_key=True)
    catagory = Column(String(128), default='radio')  # radio check blank challenge
    content = Column(Text, default='content')
    # options的处理，每个item用空格分隔开，若item本身包含空格，则replace为顿号(、)
    options = Column(Text, default='')
    answer = Column(String(256), nullable=True, default='')
    note = Column(Text, nullable=True, default='')
    bounds = Column(String(128), nullable=True, default='')

    def __init__(self, catagory, content, options, answer, note, bounds):
        self.catagory = catagory or 'radio'  # 挑战答题-挑战题, 每日答题-单选题、多选题、填空题
        self.content = content or 'default content'
        self.options = options or ''
        self.answer = answer.upper() or ''
        self.note = note or ''
        self.bounds = bounds or ''

    def __repr__(self):
        return f'<Bank {self.content}>'

    def __str__(self):
        maxlen = 42
        if len(self.content) > maxlen:
            content = f'{self.content[:maxlen]}...'
        else:
            content = self.content
        content = re.sub(r'\s', '_', content)
        options = ''
        if self.options:
            options = f'O: {self.options}\n'
        return f'I: {self.id} {self.catagory}\nQ: {content:<50}\n{options}A: {self.answer}\n'

    def __eq__(self, other):
        return self.content == other.content

    @classmethod
    def from_challenge(cls, content, options='', answer='', note='', bounds=''):
        str_options = '|'.join(options)
        return cls(catagory='挑战题', content=content, options=str_options, answer=answer, note=note, bounds=bounds)

    @classmethod
    def from_daily(cls, catagory, content, options, answer, note):
        return cls(catagory=catagory, content=content, options=options, answer=answer, note=note, bounds='')

    def to_array(self):
        options = self.options.split('|')
        array_bank = [self.id, self.answer, self.content]
        array_bank.extend(options)
        # array_bank.append(self.note)
        return array_bank

    def to_dict(self):
        json_bank = {
            "id": self.id,
            "catagory": self.catagory,
            "content": self.content,
            "options": self.options,
            "answer": self.answer,
            "note": self.note
        }
        return json_bank

    @classmethod
    def from_dict(cls, data):
        return cls(data['catagory'], data['content'], re.sub(r'\s', '|', re.sub(r'|', '', data['options'])),
                   data['answer'], data['note'], '')


class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(Text, index=True, default='title')

    def __repr__(self):
        return f'{self.title}'

    def __str__(self):
        return f'[{self.id}] {self.title}'


class Xlser(object):
    def __init__(self, paths):
        self.path = paths

    def load(self):
        data = []
        app = xlwings.App(visible=False, add_book=False)
        wb = app.books.open(self.path)
        ws = wb.sheets['bank']
        rng = ws.used_range
        print(rng.rows[0].value)
        for row in rng.rows[1:]:
            res = (row.value[1]).replace(u'\xa0', ' ')
            bank = Bank.from_challenge(content=res, answer=row.value[6])
            data.append(bank)
        wb.close()
        app.quit()
        return data

    def save(self, data):
        app = xlwings.App(visible=False, add_book=False)
        wb = app.books.add()
        ws = wb.sheets['Sheet1']
        # 写入数据
        print(f'{len(data)}条数据正在导出...')
        ws.range(1, 1).value = ['序号', '答案', '题干', '选项A', '选项B', '选项C', '选项D', '说明']
        try:
            for i, item in enumerate(data):
                ws.range(i + 2, 1).value = item.to_array()
        except Exception:
            print(f'xls写入失败')
        finally:
            wb.save(self.path)
            wb.close()
            app.quit()
        return 0


class Model():
    def __init__(self, database_uri):
        # 初始化数据库连接:
        engine = create_engine(database_uri)
        # 创建DBSession类型:
        Session = sessionmaker(bind=engine)

        Base.metadata.create_all(engine)
        self.session = Session()

    # 数据库检索记录
    def query(self, ids=None, content=None, catagory='挑战题 单选题 多选题 填空题'):
        catagory = catagory.split(' ')
        if ids and isinstance(id, int):
            return self.session.query(Bank).filter_by(id=id).one_or_none()
        if content and isinstance(content, str):
            content = re.sub(r'\s+', '%', content)
            return self.session.query(Bank).filter(Bank.catagory.in_(catagory)).filter(
                Bank.content.like(content)).one_or_none()
        return self.session.query(Bank).filter(Bank.catagory.in_(catagory)).all()

    # 数据库添加纪录
    def add(self, item):
        result = self.query(content=item.content, catagory=item.catagory)
        if result:
            print(f'数据库已存在此纪录，无需添加纪录！')
        else:
            self.session.add(item)
            self.session.commit()
            print(f'数据库添加记录成功！')

    def has_article(self, title):
        return self.session.query(Article).filter_by(title=title).one_or_none() is not None

    def print_arcitles(self):
        items = self.session.query(Article).all()
        for item in items:
            print(item)

    def len_articles(self):
        return len(self.session.query(Article).all())

    def add_article(self, title):
        if '' == title:
            raise ValueError('文章标题不能为空')
        if self.has_article(title):
            raise RuntimeError('文章标题已在数据库中')
        else:
            article = Article(title=title)
            self.session.add(article)
            self.session.commit()
            print(f'数据库添加成功！ {title}')

    def _to_json(self, path, catagory='挑战题 单选题 多选题 填空题'):
        datas = self.query(catagory=catagory)
        # print(len(datas))
        output = [data.to_dict() for data in datas]
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(output, fp, indent=4, ensure_ascii=False)
        print(f'JSON数据{len(datas)}条成功导出{path}')
        return True

    def _from_json(self, path, catagory='挑战题 单选题 多选题 填空题'):
        if path.exists():
            with open(path, 'r', encoding='utf-8') as fp:
                res = json.load(fp)
            for r in res:
                bank = Bank.from_dict(r)
                if '填空题' == bank.catagory:
                    if str(len(bank.answer.split(' '))) != bank.options:
                        continue
                self.add(bank)
            print(f'JSON数据成功导入{path}')
            return True
        else:
            print(f'JSON数据{path}不存在')
            return False

    def _to_md(self, paths, catagory='挑战题'):
        db = Model('sqlite:///./xuexi/data-dev.sqlite')
        items = db.query(catagory=catagory)
        with open(paths, 'w', encoding='utf-8') as fp:
            fp.write(f'# 学习强国 挑战答题 题库 {len(items):>4} 题\n')
            for item in items:
                content = re.sub(r'\s\s+', '\_\_\_\_', re.sub(r'[\(（]出题单位.*', '', item.content))
                options = "\n\n".join([f'+ **{x}**' if i == ord(item.answer) - 65 else f'+ {x}' for i, x in
                                       enumerate(item.options.split('|'))])
                fp.write(f'{item.id}. {content}  *{item.answer}*\n\n{options}\n\n')
        with open(paths.with_name('data-grid.md'), 'w', encoding='utf-8') as fp2:
            fp2.write(f'# 学习强国 挑战答题 题库 {len(items):>4} 题\n')
            fp2.write(f'|序号|答案|题干|选项A|选项B|选项C|选项D|\n')
            fp2.write(f'|:--:|:--:|--------|----|----|----|----|\n')
            for item in items:
                content = re.sub(r'\s\s+', '\_\_\_\_', re.sub(r'[\(（]出题单位.*', '', item.content))
                options = " | ".join([f'**{x}**' if i == ord(item.answer) - 65 else f'{x}' for i, x in
                                      enumerate(item.options.split('|'))])
                fp2.write(f'| {item.id} | {item.answer} | {content} | {options} |\n')

        return 0

    def _to_xls(self, paths, catagory='挑战题 单选题 多选题 填空题'):
        data = self.query(catagory=catagory)
        xs = Xlser(paths)
        xs.save(data)

    def upload(self, path, catagory='挑战题 单选题 多选题 填空题'):
        if '.json' == path.suffix:
            self._from_json(path, catagory)
        elif path.suffix not in ('.xls', '.xlsx'):
            print(f'不被支持的文件类型: {path.suffix}')

    def download(self, path, catagory='挑战题 单选题 多选题 填空题'):
        ext = path.suffix
        if '.json' == ext:
            self._to_json(path, catagory)
        elif ext in ('.xls', '.xlsx'):
            self._to_xls(path, catagory)
        elif '.md' == ext:
            self._to_md(path, catagory)
        else:
            print(f'不被支持的文件类型: {ext}')


# 提示语音
def attention(paths, repeat=2):
    # 语音提示：https://developer.baidu.com/vcast导出音频
    for i in range(repeat):
        playsound(paths)


class Alarm:
    def __init__(self, filename, repeat=2):
        paths = Path('./xuexi/src/sounds')
        t = threading.Thread(target=attention, args=(str(paths / filename), repeat))  # 创建线程
        t.start()


class ChallengeQuiz(object):
    def __init__(self, rules, ad, xm):
        self.rules = rules
        # filename是文件challenge.json的路径
        self.filename = Path('./xuexi/src/json/challenge.json')
        self.ad = ad
        self.xm = xm
        self.db = Model(r'E:\AutoXue-master\xuexi\data-dev.sqlite')
        self.has_bank = False
        self.is_user = True
        self.content = ''
        self.options = ''
        self.note = ''
        self.answer = ''
        self.pos = ''
        self.p_back = 0j
        self.p_return = 0j
        self.p_share = 0j

    # 开始答题
    def _enter(self):
        self._fresh()
        pos = self.xm.pos('//node[@text="挑战答题"]/@bounds')
        self.ad.tap(pos)
        print(f'挑战答题，开始！')
        sleep(2)

    def _fresh(self):
        self.ad.uiautomator()
        self.xm.load()

    # 加载json文件
    def _load(self):
        filename = self.filename
        res = []
        if self.filename.exists():
            with open(filename, 'r', encoding='utf-8') as fp:
                try:
                    res = json.load(fp)
                except Exception:
                    print(f'加载JSON数据失败')
            print(f'载入JSON数据{filename}')
            return res
        else:
            print('JSON文件{filename}不存在')
            return res

    # 保存json文件
    def _dump(self):
        filename = self.filename
        with open(filename, 'w', encoding='utf-8') as fp:
            json.dump(self.json_blank, fp, indent=4, ensure_ascii=False)
        print(f'导出JSON数据{filename}')
        return True

    # 去百度搜索
    def _search(self):
        print(f'search - {self.content}')
        Alarm('challenge.mp3', 1)
        # 搜索引擎检索题目
        content = re.sub(r'[\(（]出题单位.*', "", self.content)
        print(f'\n[挑战题] {content}')
        url = quote('https://www.baidu.com/s?wd=' + content, safe=string.printable)
        headers = {
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
        }
        response = requests.get(url, headers=headers).text
        counts = []
        for i, option in zip(['A', 'B', 'C', 'D'], self.options):
            count = response.count(option)
            counts.append((count, i))
            print(f'{i}. {option}: {count}')
        counts = sorted(counts, key=lambda x: x[0], reverse=True)
        bank = None
        for item in self.json_blank:
            if item['content'] == self.content:
                bank = item
                break
            else:
                continue
        if bank:
            for c in counts:
                if c[1] in bank['note']:
                    continue
                else:
                    _, self.answer = c
                    break
        else:
            _, self.answer = counts[0]
        print(f'试探性提交答案 {self.answer} 延时10秒中...')
        sleep(5)
        return ord(self.answer)-65

    # 题目内容，返回值res
    def _content(self):
        res = self.xm.content('//node[@class="android.widget.ListView"]/preceding-sibling::node[1]/@text')
        print(res)
        return res

    # 选项
    def _options(self):
        res = self.xm.options('//node[@class="android.widget.ListView"]/node//node[@index="1" '
                              'and @class="android.view.View"]/@text')
        print(res)
        return res

    # 选项的坐标范围
    def _pos(self):
        res = self.xm.pos('//node[@class="android.widget.ListView"]/node/@bounds')
        print(res)
        return res

    # 提交
    def _submit(self):
        self._fresh()
        self.content = self._content()    # 答题内容
        self.options = self._options()    # 选项（文字）
        self.note = ''
        self.pos = self._pos()            # 选项的坐标
        # 去数据库检索
        bank = self.db.query(content=self.content, catagory='挑战题')
        # 如果数据库里面存在这个数据
        if bank is not None:
            # char()内置函数，把数字ASCII码转换为字符
            options = "\n".join([f'{chr(i+65)}. {x}' for i, x in enumerate(self.options)])
            # for i, x in enumerate(self.options):
            #     options = "\n".join(f'{chr(i + 65)}. {x}')
            # [挑战题]题干...
            # 选项的内容
            print(f'\n[挑战题] {self.content[:45]}...\n{options}')
            self.has_bank = True
            # ord()内置函数，返回ASCII值
            cursor = ord(bank.answer) - 65
            print(f'自动提交答案 {bank.answer}')

            # 延时功能
            challenge_delay = 0
            if 0 == challenge_delay:
                delay_seconds = randint(0, 5)
            else:
                delay_seconds = challenge_delay
            sleep(delay_seconds)

        # 如果bank是None则去百度搜索
        else:
            self.has_bank = False
            cursor = self._search()
            
        print(f'正确选项下标 {cursor}')
        # 点击正确选项
        while 0j == self.pos[cursor]:
            self.ad.draw('up')
            self._fresh()
            self.pos = self._pos()
        # 现在可以安全点击(触摸)
        self.ad.tap(self.pos[cursor])
    
    def _db_add(self):
        # from_challenge(cls, content, options, answer='',note='', bounds='')
        if not self.has_bank:
            bank = Bank.from_challenge(content=self.content, options=self.options,
                                       answer=self.answer, note='', bounds='')
            self.db.add(bank)
            if self.is_user:
                self.json_blank.append(bank.to_dict())

    def _reopened(self, repeat: bool = False) -> bool:
        # 默认使用复活权,不使用再来一局
        # sleep(2)
        self._fresh()
        # 本题答对否
        if not self.xm.pos('//node[@text="分享就能复活" or @text="再来一局"]/@bounds'):
            self._db_add()
            return True
        else:
            # 在note中追加一个错误答案，以供下次遇到排除
            temp = None
            for item in self.json_blank:
                if item['content'] == self.content:
                    temp = item
            if temp:
                temp['note'] += self.answer
            else:
                temp = Bank.from_challenge(content=self.content, options=self.options,
                                           answer='', note=self.answer, bounds='')
                self.json_blank.append(temp.to_dict())
                print(f'错题加入错题集JSON文件中')
            print(f'不要那么贪心，闪动的复活按钮不好点击，就此结束吧')
            return False

    def _commet(self):
        maxlen = len(self.options)
        try:
            ch = input(f'请输入正确的答案: ').upper()
            assert ch in 'NABCD'[:maxlen+1], f"输入的项目不存在，请输入A-DN"
        except Exception as ex:
            print(f"输入错误:", ex)
        if ch in 'ABCD':
            self.answer = ch
            self._db_add()
        return ch

    def _run(self, count):
        sub_count = count
        self._enter()
        while sub_count:
            self._submit()
            if self._reopened():   # 回答正确
                sub_count = sub_count - 1
            else:
                break
        else:
            print(f'已达成目标题数，延时30秒等待死亡中...')
            sleep(30)
        self.ad.back()   
        return sub_count

    def run(self, count):
        while True:
            self.json_blank = self._load()
            if 0 == self._run(count):
                print(f'已达成目标题数 {count} 题，退出挑战')
                break
            else:
                sleep(3)
                print(f'未达成目标题数，再来一局')
            self._dump()

    def runonce(self, sub_count):
        while sub_count:
            self._submit()
            if self._reopened():   # 回答正确
                sub_count = sub_count - 1
            else:
                break


def str2complex(s):
    x0, y0, x1, y1 = [int(x) for x in re.findall(r'\d+', s)]
    print(f'({x0}, {y0}) -> ({x1}, {y1})')
    res = complex((x0+x1)//2, (y0+y1)//2)
    print(res)
    return res


class Xmler(object):
    def __init__(self, paths=Path('./xuexi/src/xml/reader.xml')):
        self.path = paths
        self.root = None

    def load(self):
        self.root = etree.parse(str(self.path))

    def texts(self, rule: str) -> list:
        # return list<str>
        res = [x.replace(u'\xa0', u' ') for x in self.root.xpath(rule)]
        res = [' ' if '' == x else x for x in res]
        print(res)
        return res

    def pos(self, rule: str) -> list:
        # return list<complex>
        print(rule)
        res = self.texts(rule)
        print(res)
        points = [str2complex(x) for x in res]
        if len(points) == 1:
            res = points[0]
        else:
            res = points
        print(res)
        return res

    def content(self, rule: str) -> str:
        # return str
        print(rule)
        # res = self.texts(rule) # list<str>
        # res = ' '.join([" ".join(x.split()) for x in self.texts(rule)])
        res = ''.join(self.texts(rule))
        print(res)
        return res

    def options(self, rule: str) -> list:
        res = [re.sub(r'\|', '_', x) for x in self.root.xpath(rule)]
        print(res)
        return res

    def count(self, rule: str) -> int:
        # return int
        print(rule)
        res = self.root.xpath(rule)
        return len(res)


class Adble(object):
    def __init__(self, paths=Path('./ui.xml'), is_virtual: bool = True, host='127.0.0.1', port=7555):
        # subprocess.Popen(f'adb version', shell=True)
        self.path = paths
        self.is_virtual = is_virtual
        self.host = host
        self.port = port
        if self.is_virtual:
            self._connect()
        else:
            print(f'请确保安卓手机连接手机并打开USB调试!')
        self.device = self._getDevice()
        if self.device is not None:
            print(f'当前设备 {self.device}')
            self.ime = self._getIME()
            self.wmsize = self._size()
            self._setIME('com.android.adbkeyboard/.AdbIME')
        else:
            print(f'未连接设备')
            raise RuntimeError(f'未连接任何设备')

    def _connect(self):
        # 连接模拟器adb connect host:port
        print(f'正在连接模拟器{self.host}:{self.port}')
        subprocess.check_call(f'adb connect {self.host}:{self.port}', shell=True, stdout=subprocess.PIPE)

    def _disconnect(self):
        # 连接模拟器adb connect host:port
        print(f'正在断开模拟器{self.host}:{self.port}')
        if 0 == subprocess.check_call(f'adb disconnect {self.host}:{self.port}', shell=True, stdout=subprocess.PIPE):
            print(f'断开模拟器{self.host}:{self.port} 成功')
        else:
            print(f'断开模拟器{self.host}:{self.port} 失败')

    def draw(self, orientation='down', distance=100, duration=500):
        height, width = max(self.wmsize), min(self.wmsize)  # example: [1024, 576]
        # 中点 三分之一点 三分之二点
        x0, x1, x2 = width // 2, width // 3, width // 3 * 2
        y0, y1, y2 = height // 2, height // 3, height // 3 * 2
        if 'down' == orientation:
            self.swipe(x0, y1, x0, y1 + distance, duration)
        elif 'up' == orientation:
            self.swipe(x0, y2, x0, y2 - distance, duration)
        elif 'left' == orientation:
            self.swipe(x2, y0, x2 - distance, y0, duration)
        elif 'right' == orientation:
            self.swipe(x1, y0, x1 + distance, y0, duration)
        else:
            print(f'没有这个方向 {orientation} 无法划动')
        return 0

    def _size(self):
        res = subprocess.check_output(f'adb -s {self.device} shell wm size', shell=False)
        if isinstance(res, bytes):
            wmsize = re.findall(r'\d+', str(res, 'utf-8'))
        else:
            wmsize = re.findall(r'\d+', res)
        print(f'屏幕分辨率：{wmsize}')
        res = [int(x) for x in wmsize]
        return res

    def _setIME(self, ime):
        print(f'设置输入法 {ime}')
        print(f'正在设置输入法 {ime}')
        if 0 == subprocess.check_call(f'adb -s {self.device} shell ime set {ime}', shell=True, stdout=subprocess.PIPE):
            print(f'设置输入法 {ime} 成功')
        else:
            print(f'设置输入法 {ime} 失败')

    def _getIME(self) -> list:
        print(f'获取系统输入法list')
        res = subprocess.check_output(f'adb -s {self.device} shell ime list -s', shell=False)
        if isinstance(res, bytes):
            # ime = re.findall(r'\d+', str(res, 'utf-8'))
            ime = re.findall(r'\S+', str(res, 'utf-8'))
        else:
            ime = re.findall('\S+', res)
        print(f'系统输入法：{ime}')
        return ime[0]

    def _getDevice(self) -> str:
        print(f'获取连接的设备信息')
        res = subprocess.check_output(f'adb devices')
        if isinstance(res, bytes):
            res = str(res, 'utf-8')
        devices = re.findall(r'(.*)\tdevice', res)
        print(f'已连接设备 {devices}')
        if self.is_virtual and f'{self.host}:{self.port}' in devices:
            return f'{self.host}:{self.port}'
        elif 0 == len(devices):
            return None
        else:
            return devices[0]

    def uiautomator(self, path=None, filesize=10240):
        if not path:
            path = self.path
        for i in range(3):
            if path.exists():
                path.unlink()
            else:
                print('文件不存在,无需删除')
            subprocess.check_call(f'adb -s {self.device} shell uiautomator dump /sdcard/ui.xml', shell=True,
                                  stdout=subprocess.PIPE)
            # sleep(1)
            subprocess.check_call(f'adb -s {self.device} pull /sdcard/ui.xml {path}', shell=True,
                                  stdout=subprocess.PIPE)
            if filesize < path.stat().st_size:
                break
            else:
                sleep(1)

    def screenshot(self, paths=None):
        if not paths:
            paths = self.path
        subprocess.check_call(f'adb -s {self.device} shell screencap -p /sdcard/ui.png', shell=True,
                              stdout=subprocess.PIPE)
        # sleep(1)
        subprocess.check_call(f'adb -s {self.device} pull /sdcard/ui.png {paths}', shell=True, stdout=subprocess.PIPE)

    def swipe(self, sx, sy, dx, dy, duration):
        #  swipe from (sx, xy) to (dx, dy) in duration ms
        # adb shell input swipe 500 500 500 200 500
        print(f'滑动操作 ({sx}, {sy}) --{duration}ms-> ({dx}, {dy})')
        res = subprocess.check_call(f'adb -s {self.device} shell input swipe {sx} {sy} {dx} {dy} {duration}',
                                    shell=True, stdout=subprocess.PIPE)
        # sleep(1)
        return res

    def slide(self, begin, end, duration=500):
        # 接收complex参数坐标
        print(f'滑动操作 {begin} --{duration}ms-> {end}')
        sx, sy = int(begin.real), int(begin.imag)
        dx, dy = int(end.real), int(end.imag)
        res = subprocess.check_call(f'adb -s {self.device} shell input swipe {sx} {sy} {dx} {dy} {duration}',
                                    shell=True, stdout=subprocess.PIPE)
        # sleep(1)
        return res

    def tap(self, x, y=None, duration=50):
        # subprocess.check_call(f'adb shell input tap {x} {y}', shell=True, stdout=subprocess.PIPE)
        # 改进tap为长按50ms，避免单击失灵'''
        if y is not None:
            if isinstance(x, int) and isinstance(y, int):
                dx, dy = int(x), int(y)
            else:
                print(f'输入坐标有误')
        else:
            try:
                dx, dy = int(x.real), int(x.imag)
            except Exception as e:
                raise AttributeError(f'{x} 不是可点击的坐标')
        print(f'触摸操作 ({dx}, {dy})')
        return self.swipe(dx, dy, dx, dy, duration)

    def back(self):
        # adb shell input keyevent 4 
        print(f'adb 触发<返回按钮>事件')
        subprocess.check_call(f'adb -s {self.device} shell input keyevent 4', shell=True, stdout=subprocess.PIPE)

    def input(self, msg):
        print(f'输入文本 {msg}')
        # subprocess.check_call(f'adb shell input text {msg}', shell=True, stdout=subprocess.PIPE)
        subprocess.check_call(f'adb -s {self.device} shell am broadcast -a ADB_INPUT_TEXT --es msg {msg}', shell=True,
                              stdout=subprocess.PIPE)

    def close(self):
        self._setIME(self.ime)
        if self.is_virtual:
            self._disconnect()


if __name__ == "__main__":
    from argparse import ArgumentParser
    print('运行challenge.py')
    parse = ArgumentParser()
    parse.add_argument('-c', '--count', metavar='count', type=int, default=10, help='挑战答题题数')
    parse.add_argument('-v', '--virtual', metavar='virtual', nargs='?', const=True,
                       type=bool, default=False, help='是否模拟器')

    args = parse.parse_args()
    path = Path('./xuexi/src/xml/challenge.xml')
    ad = Adble(path, args.virtual)
    xm = Xmler(path)
    cg = ChallengeQuiz('nox', ad, xm)
    cg.runonce(args.count)
    ad.close()
