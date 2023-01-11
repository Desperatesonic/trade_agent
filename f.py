import csv
import functools
import json
import os
import random
import tkinter
import traceback
import warnings
import win32api
import win32gui, win32ui, win32con
import multiprocessing as mp
import multiprocessing.dummy as thread
import win32process
from datetime import datetime
from importlib import reload
import numpy as np
import pywintypes
from functools import partial
from collections import namedtuple
# from matplotlib import pyplot as plt
import win32gui_struct

import time, signal
from typing import List

import cv2

from tesseract import Tesseract

try:
    from exception_logger import *
    l=create_logger()
    own_l=create_logger("ownLog","./own.log")
except ImportError:
    l=None
    def exception(l):
        def decorator(function):
            @functools.wraps(function)
            def wrapper(*args,**kwargs):
                return function(*args,**kwargs)
            return wrapper
        return decorator

class Status:
    def __init__(self, value=None):
        self.value = value


_Detail = namedtuple("Detail", ["handle", "status", "rect", "center"])
Center = lambda r: (int(r[0] + (r[2] - r[0]) / 2), int(r[1] + (r[3] - r[1]) / 2))
Size = lambda r: (r[2] - r[0], r[3] - r[1])
Detail = lambda h, r: _Detail(h, Status(), r, Center(r))


def reposition(drawHdlDict: dict):
    w, h = _get_screen_width_height()
    widgets = {}
    canvas = tkinter.Canvas(bg='white', width=w, height=h)
    canvas.create_rectangle(w / 2 - 50, h / 2 - 50, w / 2 + 50, h / 2 + 50, outline="Red", fill="Red", tags="Done")
    canvas.create_text(w / 2, h / 2, text="Done")

    cur_move = []

    # 响应拖动事件
    def callback(event):
        if not len(cur_move):
            c = canvas.find_overlapping(event.x, event.y, event.x, event.y)
            if not len(c) or len(canvas.gettags(c)) < 2:
                return
            cur_move.append(c[0])
        c_x, c_y, c_xM, c_yM = canvas.coords(cur_move[0])
        c_x += (c_xM - c_x) / 2
        c_y += (c_yM - c_y) / 2
        shift_x = event.x - c_x
        shift_y = event.y - c_y
        canvas.move(cur_move[0], shift_x, shift_y)
        e = canvas.gettags(cur_move[0])
        for each in e:
            if each == "current":
                continue
            canvas.move(each, shift_x, shift_y)

    # 响应松开鼠标即停止拖动事件
    # 保存矩形块当前位置
    def callback2(event):
        if len(cur_move) == 1:
            c = cur_move[0]
            t_c = canvas.gettags(c)
            t_c = list(filter(lambda x: x != "current", t_c))
            assert len(t_c) == 1
            t_c = t_c[0]
            drawHdlDict[canvas.itemcget(t_c, "text")] = canvas.bbox(c)
        cur_move.clear()

    # 点击done按钮，结束当前canvas
    def callback3(event):
        if not len(cur_move):
            c = canvas.find_overlapping(event.x, event.y, event.x, event.y)
            if not len(c):
                return
            print(c)
            if "Done" not in canvas.gettags(c):
                return
            canvas.delete(c)
            canvas.master.destroy()

            # canvas.master.wm_attributes("-transparentcolor", "white")
            # canvas.master.wm_attributes("-disabled", True)
            # hWindow = _get_tk_handle(canvas.master)
            # _set_transparent(hWindow)

    # 配置不同待拖动矩形块
    for k, v in drawHdlDict.items():
        r_text = canvas.create_text(*v[:2], text=k)
        r = canvas.create_rectangle(*v, outline="yellow", fill="yellow", tags=r_text)
        canvas.tag_lower(r)
    # 绑定鼠标动作对应的响应事件
    canvas.bind("<B1 Motion>", callback)
    canvas.bind("<ButtonRelease - 1>", callback2)
    canvas.bind("<ButtonPress - 1>", callback3)
    canvas.master.wm_attributes("-transparentcolor", "white")
    canvas.master.attributes("-alpha", 0.7)

    canvas.master.overrideredirect(True)

    # canvas.master.geometry("+250+250")
    canvas.master.lift()
    canvas.master.wm_attributes("-topmost", True)
    # 渲染canvas
    canvas.pack()
    canvas.mainloop()


def setText(handle, text):
    r = win32gui.SendMessage(handle, win32con.WM_SETTEXT, 255, text)
    if r != 1:
        raise AssertionError("setText Error")
    # win32gui.PostMessage(handle,win32con.WM_SETTEXT,255,text)


def getText(handle):
    buffer = win32gui.PyMakeBuffer(255)
    length = win32gui.SendMessage(handle,
                                  win32con.WM_GETTEXT, 255, buffer)
    result = _decode_win32_buffer(buffer, length)
    return result


def _decode_win32_buffer(buffer, length):
    return buffer[0:length * 2].tobytes().decode("UTF-16")


def lookupWindowName(subHdl, result, word):
    s = win32gui.FindWindowEx(subHdl, 0, None, word)
    if s != 0:
        if win32gui.IsWindowVisible(s):
            result.append(s)


def lookupWindowClass(subHdl, result, className):
    if win32gui.GetClassName(subHdl) == className:
        result.append(subHdl)


def lookupWindowsSon(subHdl, result, owner):
    try:
        if win32gui.GetParent(subHdl) == owner:
            result.append(subHdl)
    except:
        traceback.print_exc()


def get_hmenu(t):
    return win32gui.SendMessage(t, 0x01E1, None, None)


def findGrandChildWindowsByName(w, word):
    _where = []
    lookup = partial(lookupWindowName, word=word)
    win32gui.EnumChildWindows(w, lookup, _where)
    return _where


def _append(hdl, ret):
    ret.append(hdl)


def EnumChildWindows(w, func=_append,
                     after_func=lambda x:x):
    _where = []
    win32gui.EnumChildWindows(w, func, _where)
    return after_func(_where)


def findPopWindowByClassName(w, className):
    _where = []
    lookup = partial(lookupWindowsSon, owner=w)
    win32gui.EnumWindows(lookup, _where)
    if className == None:
        return _where
    _where = list(filter(lambda x: className == win32gui.GetClassName(x) and win32gui.IsWindowVisible(x)
                         , _where))
    return _where

# 根据线程ID查询指定窗口
def getPopWindowByThreadID(thread_id,class_name='#32770',is_visible=True):
    _where = []
    def lookup(hdl, ret):
        ret.append(hdl)
    win32gui.EnumThreadWindows(thread_id,lookup, _where)
    _where = list(filter(lambda x: win32gui.GetClassName(x)==class_name and win32gui.IsWindowVisible(x)==is_visible
                         , _where))
    return _where

# 根据句柄查找对应的线程ID
# GetWindowThreadProcessId 返回值为[9456, 10048]类型数组，分别对应线程ID、进程ID
def getThreadIDByHandle(hdl):
    return win32process.GetWindowThreadProcessId(hdl)[0]

# 根据句柄查询除自己外的弹出窗口
def checkPopWindowByHdl(hdl,callback=None):
    pop_window=getPopWindowByThreadID(getThreadIDByHandle(hdl))
    if len(pop_window)>1:
        pop_window.remove(hdl)
        if callback is not None:
            for each in pop_window:
                callback(each)
        return pop_window
    else:
        return None

def getScreenShotByHdl(hdl,name=f"screenShot.{time.time()}.bmp"):
    getScreenShot(hdl, None, (0, 0), name)

def highlight(drawHdlDict: dict):
    t = mp.Process(target=_highlight, args=(drawHdlDict,))
    t.start()
    # time.sleep(1.5)
    return t


def _highlight(drawHdlDict: dict):
    w, h = _get_screen_width_height()
    label = tkinter.Canvas(bg='white', width=w, height=h)
    # label.create_rectangle(50, 25, 150, 75, outline="yellow")
    for key, rect in drawHdlDict.items():
        # rect = win32gui.GetWindowRect(each)
        label.create_rectangle(*rect, outline="blue", width=2)
        label.create_text(rect[0:2], text=key)
    label.master.overrideredirect(True)
    # label.master.geometry("+250+250")
    label.master.lift()
    label.master.wm_attributes("-topmost", True)
    label.master.wm_attributes("-disabled", True)
    label.master.wm_attributes("-transparentcolor", "white")
    #
    hWindow = _get_tk_handle(label.master)
    _set_transparent(hWindow)
    label.pack()
    label.mainloop()


def _get_tk_handle(t):
    hWindow = pywintypes.HANDLE(int(t.frame(), 16))
    return hWindow


def _get_screen_width_height():
    w = win32api.GetSystemMetrics(0)
    h = win32api.GetSystemMetrics(1)
    return w, h


def _get_screen_center_window():
    w, h = _get_screen_width_height()
    w, h = int(w / 2), int(h / 2)
    return win32gui.WindowFromPoint((w, h))


def _set_transparent(hWindow):
    # http://msdn.microsoft.com/en-us/library/windows/desktop/ff700543(v=vs.85).aspx
    # The WS_EX_TRANSPARENT flag makes events (like mouse clicks) fall through the window.
    exStyle = win32con.WS_EX_COMPOSITED | win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT
    exStyle = win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT
    win32api.SetWindowLong(hWindow, win32con.GWL_EXSTYLE, exStyle)


keystart = 0x30
keymap = {}
vstart = ord(str(0))
for i in range(10):
    keymap[str(i)] = keystart + i
keymap = {
    **keymap,
    "-": win32con.VK_SUBTRACT,
    ".": win32con.VK_DECIMAL,
    "\n": win32con.VK_RETURN,
    "\t": win32con.VK_BACK
}
assert win32con.KEYEVENTF_KEYUP == 2


def saveExportFile(mainW):
    while 1:
        r = findPopWindowByClassName(mainW, "#32770")
        if not len(r):
            time.sleep(0.001)
            continue
        if '另存为' not in map(lambda x:win32gui.GetWindowText(x),r):
            time.sleep(0.001)
            continue
        if len(r)!=1:
            r=list(filter(lambda x:win32gui.GetWindowText(x)=='另存为',r))
        assert len(r) == 1
        try:
            s = win32gui.FindWindowEx(r[0], 0, None, "保存(&S)")
            assert s != 0
        except AssertionError:
            _all_s=EnumChildWindows(r[0])
            _all_s_name=list(map(win32gui.GetWindowText,_all_s))
            print("Exception Got Alter it")
            print(_all_s_name)
            _idx=-1
            for i in range(len(_all_s_name)):
                if _all_s_name[i].startswith("保存"):
                   _idx=i
                   break
            assert _idx!=-1
            s=_all_s[_idx]

        time.sleep(0.1)
        # win32gui.SendMessage(s,win32con.WM_LBUTTONDOWN,0,0)
        # win32gui.SendMessage(s,win32con.WM_LBUTTONUP,0,0)
        # 云服务器上出现点击不生效的情况，先把鼠标挪过去再点击可以避免
        safeBtn_moveClick(s, Center(win32gui.GetWindowRect(s)))

        #moveClick(Center(win32gui.GetWindowRect(s)),clickDelay=0.01)
        break


def openExportWindow(export_idx, idx_count):
    mii, extra = win32gui_struct.EmptyMENUITEMINFO()
    while 1:
        t = findPopWindowByClassName(0, "#32768")
        if len(t):
            assert len(t) == 1
            print(win32gui.IsWindowVisible(t[0]))
            h = get_hmenu(t[0])
            assert win32gui.GetMenuItemCount(h) == idx_count
            _, rect = win32gui.GetMenuItemRect(0, h, export_idx)

            win32gui.GetMenuItemInfo(h, export_idx, 1, mii)
            s_info = win32gui_struct.UnpackMENUITEMINFO(mii)
            if s_info.fState != 0:
                warnings.warn(f"{s_info.text} is disabled!", RuntimeWarning)
                return False
            time.sleep(0.05)
            print("->Click")
            #moveClick(Center(rect),clickDelay=0.01)


            def _before_cond():
                mi, extra = win32gui_struct.EmptyMENUITEMINFO()
                win32gui.GetMenuItemInfo(h, export_idx, 1, mi)
                s_info = win32gui_struct.UnpackMENUITEMINFO(mi)
                return win32con.MFS_HILITE | s_info.fState
            conditional_moveClick(Center(rect),before=_before_cond)
            print("Click->")
            break
        time.sleep(0.001)
        print("openExportWindow Looping")
    print("return openExportWindow->")
    return True


def typeNum(s):
    for each in list(str(s)):
        win32api.keybd_event(keymap[each], 0, 0, 0)
        print("****")
        win32api.keybd_event(keymap[each], 0, 2, 0)


def moveClick(pos: tuple, action=0, delay=0, clickDelay=0):
    #print("Click on " + str(pos) + " " + str(action) + str(clickDelay))
    win32api.SetCursorPos(pos)
    while win32api.GetCursorPos()!=pos:
        win32api.SetCursorPos(pos)
    if delay != 0:
        time.sleep(delay)
    if action == 0:
        leftClick(clickDelay)
    elif action == 1:
        rightClick(clickDelay)
    elif action == 2:
        leftClick(clickDelay)
        leftClick(clickDelay)
    else:
        raise AssertionError
@exception(l)
def _condition(func):
    _s=time.time()
    while not func():
        if time.time()-_s>0.1:
            break
        time.sleep(0.001)
@exception(l)
def conditional_moveClick(pos:tuple,action=0,before=lambda:True,mid=lambda:True):
    #TODO: timeout
    t = thread.Process(target=_condition, args=(before,))
    t.start()
    win32api.SetCursorPos(pos)
    t.join()
    if action==0:
        _P=_leftPress
        _R=_leftRelease
    elif action == 1:
        _P=_rightPress
        _R=_rightRelease

    t = thread.Process(target=_condition, args=(mid,))
    t.start()
    _P()
    while t.is_alive():
        _P()
        t.join(timeout=0.03)
    _R()
def safeBtn_moveClick(handle:int, pos: tuple, action=0, delay=0, clickDelay=0,targetBtn=0):
    win32api.SetCursorPos(pos)
    while win32api.GetCursorPos()!=pos:
        win32api.SetCursorPos(pos)
    if targetBtn == 0:
        t = thread.Process(target=waitBtnDone, args=(handle,))
    else:
        raise AssertionError

    if action==0:
        _P=_leftPress
        _R=_leftRelease
    elif action == 1:
        _P=_rightPress
        _R=_rightRelease
    else:
        raise AssertionError

    if delay!=0:
        time.sleep(delay)
    t.start()
    _P()
    if clickDelay != 0:
        time.sleep(clickDelay)
    t.join()
    _R()



def leftClick(delay=0):
    win32api.mouse_event(0x0002, 0, 0)
    if delay != 0:
        time.sleep(delay)
    win32api.mouse_event(0x0004, 0, 0)
def _move(pos:tuple):
    while win32api.GetCursorPos()!=pos:
        win32api.SetCursorPos(pos)
def _leftPress():
    win32api.mouse_event(0x0002, 0, 0)
def _leftRelease():
    win32api.mouse_event(0x0004, 0, 0)
def _rightPress():
    win32api.mouse_event(0x0008, 0, 0)
def _rightRelease():
    win32api.mouse_event(0x0010, 0, 0)
def rightClick(delay=0):
    win32api.mouse_event(0x0008, 0, 0)
    if delay != 0:
        time.sleep(delay)
    win32api.mouse_event(0x0010, 0, 0)

def changeComboIndex(handle, trade_type):
    index = win32gui.SendMessage(handle, win32con.CB_SELECTSTRING,-1,trade_type)
    if index <0 :
        raise AssertionError("findComboString Error")
    err= win32gui.SendMessage(handle, win32con.CB_SETCURSEL ,index,None)
    if err<0:
        raise AssertionError("setCursel Error")
    parent=win32gui.GetParent(handle)
    id=win32gui.GetDlgCtrlID(handle)+0x10000
    err= win32gui.SendMessage(parent, win32con.WM_COMMAND, id, handle)
    if err<0:
        raise AssertionError("CBN_SELCHANGE Error")

class TradeInterface:
    def __del__(self):
        for each in self.threadList:
            each.terminate()

    @exception(l)
    def __init__(self, account="", key=""):
        self.threadList=[]
        self.lock = mp.Lock()
        self.account = (account, key)
        self.flag=False
        # 用各个矩阵来标识不同操作区域
        if os.path.exists("keys.json"):
            with open("keys.json", "r") as f:
                keys = json.load(f)
        else:
            keys = {
                "合约": (201, 576, 282, 588),
                "开仓": (201, 598, 246, 616),
                "平仓": (257, 598, 302, 616),
                "净仓": (326, 598, 371, 616),
                "FOK": (326, 623, 371, 641),
                "备兑": (163, 623, 213, 641),
                "价格": (199, 648, 302, 668),
                "数量": (199, 675, 302, 695),
                "买入": (163, 744, 247, 800),
                "卖出": (270, 744, 354, 800),
                "类型切换按钮": (2, 634, 157, 654),
                # 部分不能通过坐标识别出组件的操作区域，带有_前缀
                # "全撤单" anchored in for positioning,
                "_可用保证金": (300, 540, 374, 557),
                "_净资产": (174, 540, 224, 557),
                "_估算浮盈": (450, 540, 510, 557),
                "_持仓": (481, 591, 577, 606),
                "_可撤": (485, 763, 543, 774),
            }
        # 支持拖动调整不同矩阵的位置
        reposition(keys)
        # 保存修改后的坐标到文件
        with open("keys.json", "w") as f:
            json.dump(keys, f)
        from typing import Dict
        self.Component: Dict[str, _Detail] = {}  # 组件
        self.TrackArea = []  # 追踪窗口
        self.mainWindow = None
        self.tradeWindowBig = None
        self.centerWindow = None

        # 根据坐标信息获取对应组件的窗口信息
        self.getWindow(keys)
        # 识别合约代码组件及对应编辑组件
        if "edit" in win32gui.GetClassName(self.Component["合约"].handle).lower():
            print("Got EditBox")
            self.contractEdit: _Detail = self.Component["合约"]  # self.getEditBox(self.contract.handle)
            self.contract: _Detail = self.getParent(self.contractEdit.handle)  # self.Component["合约"]
        else:
            self.contract: _Detail = self.Component["合约"]
            self.contractEdit: _Detail = self.getEditBox(self.contract.handle)
        self.openPosition: _Detail = self.Component["开仓"]
        self.closePosition: _Detail = self.Component["平仓"]
        self.amount: _Detail = self.Component["数量"]
        self.price: _Detail = self.Component["价格"]

        self.net: _Detail = self.Component["净仓"]
        self.net.status.value = 0

        self.activate()
        self._waitForeground()
        print("- - - init done- - -")
    @staticmethod
    def getEditBox(parentHdl):
        e = win32gui.FindWindowEx(parentHdl, 0, None, None)
        if win32gui.GetParent(e) != parentHdl:
            raise AssertionError
        return Detail(e, win32gui.GetWindowRect(e))

    @staticmethod
    def getParent(hdl):
        e = win32gui.GetParent(hdl)
        return Detail(e, win32gui.GetWindowRect(e))

    def checkForeground(self):
        """pop menu won't be detected"""
        return win32gui.GetForegroundWindow() == self.mainWindow

    def checkCenter(self):
        warnings.warn("Need obs", DeprecationWarning)
        print(hex(_get_screen_center_window()))
        return _get_screen_center_window() == self.centerWindow

    def getWindow(self, key_pos, process_title="华泰股票期权全真模拟 - [期权T型报价]"):
        # <editor-fold desc="w=主窗口">
        w = win32gui.FindWindow(None, process_title)
        print(w)
        if w==0:
            w = win32gui.FindWindow(None, "华泰股票期权 - [期权T型报价]")
        assert w!=0
        print(w)
        self.mainWindow = w
        print("Process HandleID {}".format(w))
        if any(filter(lambda x: x < -10000, win32gui.GetWindowRect(w))):
            raise AssertionError("{}\nMaximize The Window".format(win32gui.GetWindowRect(w)))
        # win32gui.BringWindowToTop(w) TODO enable this or SetForegroundWindow
        # win32gui.SetForegroundWindow(w)
        self.centerWindow = _get_screen_center_window()
        # </editor-fold>

        # <editor-fold desc="tradeArea=按键父节点 tradeWindowBig=上层节点">
        bottomPart = win32gui.FindWindowEx(w, 0, None, "状态条")
        tradeWindowBig = win32gui.FindWindowEx(bottomPart, 0, None, "交易")
        self.tradeWindowBig = tradeWindowBig
        print("tradeWindowBig {}".format(tradeWindowBig))
        # self.tradeWindowBig = tradeWindowBig
        _where = findGrandChildWindowsByName(tradeWindowBig, "卖出")
        if len(_where) != 1:
            s = "可能交易界面锁定 或底层布局发生变化"
            raise AssertionError("{}\n{}".format(s, _where))
        tradeArea = win32gui.GetParent(_where[0])
        print("tradeArea", tradeArea)
        # </editor-fold>

        # <editor-fold desc="_cancel=撤单hdl">
        _cancel = findGrandChildWindowsByName(tradeWindowBig, "全撤单")
        if len(_where) != 1:
            raise AssertionError(_where)
        _cancel = _cancel[0]
        #  </editor-fold>

        key_pos["全撤单"] = win32gui.GetWindowRect(_cancel)

        for k, v in key_pos.items():
            if k in self.Component:
                raise AssertionError("Same Name Exist")
            cur_hdl = win32gui.WindowFromPoint(Center(v))
            if cur_hdl == 0 or k[0] == "_":
                self.Component[k] = Detail(0, v)
                continue
            self.Component[k] = Detail(cur_hdl, win32gui.GetWindowRect(cur_hdl))

        print(self.Component)
        # self.threadList.append(highlight({k: v.rect for k, v in self.Component.items()}))
        logging.info("....")

    def activate(self):
        #safeBtn_moveClick(self.contract.handle,self.contract.center)
        moveClick(self.contract.center)

    def _setContract(self, contract):
        setText(self.contract.handle, str(contract) + "\n")

    def waitFocus(self):
        warnings.warn("Do not use", DeprecationWarning)
        time.sleep(0.05)
        return
        s = time.time()
        _i = 1
        while win32gui.GetFocus() != self.contractEdit.handle:
            time.sleep(0.001)
            print("Wait Focus {}/{}".format(win32gui.GetFocus(), self.contractEdit.handle))
            if _i % 100 == 0:
                raise AssertionError
            _i += 1
        print("Focus Wait Time:" + str(time.time() - s))

    def waitPopup(self):
        s = time.time()
        while win32gui.WindowFromPoint(self.contract.center) in (self.contract.handle, self.contractEdit.handle):
            time.sleep(0.001)

        # popList = []
        # while len(popList) == 0:
        #     popList = findPopWindowByClassName(self.mainWindow, "#32770")
        #     print("等待缓慢弹窗")
        # print(popList)
        # assert len(popList) == 1
        # popList = popList[0]
        print("Popup Wait Time:" + str(time.time() - s))
        # return popList
        return win32gui.WindowFromPoint(self.contract.center)
        # return win32gui.GetParent(win32gui.WindowFromPoint(self.contract.center))

    def confirmInput(self, editBoxHdl, contract, onlyLength=False):
        prev_p=None
        s=time.time()
        while 1:
            if time.time()-s>1:
                raise AssertionError("等太久了")
            text = getText(editBoxHdl)
            if len(text) == 0:
                time.sleep(0.001)
            if contract == text:
                break
            if contract.startswith(text):
                p="等待输入完成 " + text
                if prev_p!=p:
                    print(p)
                    prev_p=p
                time.sleep(0.001)
                continue
            if onlyLength and len(text) >= len(contract):
                print(text, "/", contract)
                break

            moveClick(self.contract.center)
            time.sleep(0.01)
            typeNum("\t"*12)
            raise AssertionError("Wrong Input" + text)
        print("confirmInput Wait Time: ",time.time()-s)

    def setContract(self, contract):
        contract = str(contract)
        text = getText(self.contractEdit.handle)
        if text == contract:
            return
        moveClick(self.contract.center)
        # win32gui.SetFocus(self.contractEdit.handle)
        # print("Set Done")

        # self.waitFocus()
        win32gui.SendMessage(self.contractEdit.handle, win32con.WM_SETTEXT, 0, contract[0])
        popHdl = self.waitPopup()
        s = time.time()
        typeNum(contract[1:])
        print("Input Time:" + str(time.time() - s))
        # self.confirmInput(popHdl,contract)
        typeNum("\n")
        s = time.time()
        _i = 0
        while win32gui.GetParent(win32gui.WindowFromPoint(self.contract.center)) == popHdl:
            time.sleep(0.001)
            _i += 1
            if _i % 10 == 0:
                _i = 0
                print("Waiting invis")
        # while win32gui.IsWindowVisible(popHdl):
        #     time.sleep(0.001)
        print("Invis Wait Time:" + str(time.time() - s))

        # res=win32gui.GetWindowText(self.Component["合约"].handle)
        self.confirmInput(self.contractEdit.handle, contract, True)  # TODO confirm by popup edit
        self.contract.status.value = contract
    @exception(l)
    def external_setContract(self,contract):
        self.lock.acquire()
        try:
            self.setContract(contract)
            print("extern set Contract Done")
        except Exception as err:
            l.debug("extern setContract Fail")
            l.exception(err)
        finally:
            self.lock.release()
    def setPosition(self, position):
        if position == 0:
            c, o = self.openPosition, self.closePosition
        else:
            c, o = self.closePosition, self.openPosition
        # if c.status.value == 1:
        #     return

        moveClick(c.center)

        # # TODO:verify checked
        # c.status.value = 1
        # o.status.value = 0

    def setAmount(self, amount):
        amount=int(amount)
        setText(self.Component["数量"].handle, str(amount))
        if getText(self.Component["数量"].handle) != str(amount):
            raise AssertionError("数量输入错误")

    def _Simulate_setAmount(self, amount):
        moveClick(self.Component["数量"].center)
        # typeNum("\t")
        time.sleep(0.2)
        typeNum(amount)
    def clickReset(self):
        return
        #btn=self.Component["复位"]#ONGOING
        #moveClick(btn.center,2,clickDelay=0.05)
    def setPrice(self, price):
        if getText(self.Component["价格"].handle) != "对手价":
            self.clickReset()
            l.exception("price not reseted")
        #TODO reset
        setText(self.Component["价格"].handle, str(price))
        if getText(self.Component["价格"].handle) != str(price):
            self.clickReset()
            raise AssertionError("价格输入错误")

    def _Simulate_setPrice(self, price):
        warnings.warn("", DeprecationWarning)
        moveClick(self.Component["价格"].center)
        typeNum("\t")
        typeNum("\t")
        typeNum("\t")
        typeNum(price)

    def setNet(self, net):
        now = win32gui.SendMessage(self.Component["自动"].handle, win32con.BM_GETCHECK)
        if now == net:
            return
        moveClick(self.net.center)
        self.net.status.value = net
        time.sleep(0.1)

    def clickBuy(self, clickDelay):
        s=time.time()
        self.clickAndWait(self.Component["买入"])
        print("Buy takes ",time.time()-s)
        # moveClick(self.Component["买入"].center, clickDelay=clickDelay)

    def clickSell(self, clickDelay):
        s = time.time()
        self.clickAndWait(self.Component["卖出"])
        print("Sell takes ", time.time() - s)
        #moveClick(self.Component["卖出"].center, clickDelay=clickDelay)

    def _waitForeground(self):
        while not self.checkForeground():
            time.sleep(0.01)

    def secureForeground(self):
        if self.checkForeground():
            return
        #TODO 检查前排弹窗
        moveClick(self.contract.center)
        cur_w = win32gui.GetForegroundWindow()
        print("Cur_w ",cur_w)
        if cur_w==0:
            print("Wait From 0")
            while not win32gui.GetForegroundWindow():
                time.sleep(0.01)
            print("Wait From 0 Done")
            return
        cur_w_name = win32gui.GetClassName(cur_w)
        cur_w_text = win32gui.GetWindowText(cur_w)
        if cur_w_text == "XXX":
            pass
            # Do xxx
        res = win32gui.SetForegroundWindow(self.mainWindow)
        print("secureForeground ", res)

    def do(self, contract, position, net, amt, price, direction, uid=None, tradeType=0):
        print("->start do")
        self.lock.acquire()
        try:
            self._do(contract, position, net, amt, price, direction, 0.01)
            return (uid,True),time.time()
        except Exception:
            return (uid,False),time.time()
        finally:
            print("do done->")
            self.lock.release()
    @exception(l)
    def _do(self, contract, position, net, amt, price, direction, delay):
        print("-> secure")
        self.secureForeground()
        print("secure -> setCon")
        try:
            self.setContract(contract)
        except Exception as e:
            l.exception(e)
            l.debug("retry setContract once")
            self.setContract(contract)
        print("setCon -> setNet")
        # time.sleep(0.02)
        self.setNet(net)
        print("setNet -> setPos")
        self.setPosition(position)
        print("setPos ->setAmt")
        # time.sleep(0.01)
        self.setAmount(amt)
        print("setAmt -> setPrice")
        # time.sleep(0.01)
        self.setPrice(price)
        print("-> setDone")
        # time.sleep(0.03)
        if direction == 0:
            self.clickBuy(delay)
            #self.waitBtnDone(self.Component["买入"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickBuy,delay)
        else:
            self.clickSell(delay)
            #self.waitBtnDone(self.Component["卖出"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickSell,delay)

        print("confirmTrade -> Print")
        # TODO wait back to state

        print("apply Do ",str(datetime.datetime.now()))

    def confirmTrade(self,func=None,arg=None,retry=False):
        _s=time.time()
        overtime=False
        print("Confirm Trade Applied")
        t=lambda:getText(self.price.handle) != "对手价"
        f=lambda:findPopWindowByClassName(self.mainWindow, "#32770")
        while t():
            print("Wait price reset")
            if time.time()-_s>0.1:
                overtime=True
                break
            time.sleep(0.001)
        if overtime and not retry:
            l.exception("Over time")
            func(arg)
            self.confirmTrade(func,arg,True)
            return
        if not t():
            return

        resList=f()
        #assert len(res)==1
        #res=res[0]
        for res in resList:
            text=win32gui.GetWindowText(res)
            lo = EnumChildWindows(res, after_func=lambda x: [(win32gui.GetWindowText(each), each) for each in x])
            if text=="提示" and any(map(lambda text:"合约到期提醒" in text[0],lo)):
                print(lo)
                y_btn=list(filter(lambda text: text[0].startswith("是"), lo))
                assert len(y_btn)==1
                safeBtn_moveClick(y_btn[0][1], Center(win32gui.GetWindowRect(y_btn[0][1])))
                #moveClick(Center(win32gui.GetWindowRect(y_btn[0][1])))
            else:
                #TODO 右下角窗口处理
                print("!Unknown Popup")
                print(res)
                print(f())
                getScreenShot(res, None, (0, 0), f"confirm.{time.time()}.bmp")
        print("Wait window disappear")
        self._waitForeground()

        print("Wait price reset after popup")
        while t():
            time.sleep(0.001)
        print("Confirmed")

    @exception(l)
    def getOwned(self):
        d = datetime.datetime.now()
        p = f'{os.environ["USERPROFILE"]}\\Documents\\{d.year}年{d.month}月{d.day}日期权持仓报表.csv'
        _ret=self._getExport(self.Component["_持仓"], 2, 4, p)
        if not len(_ret):
            own_l.info("{} Empty Own")
            return {},time.time()
        header = _ret.pop(0)
        keyIndex = header.index("代码")
        ret = {each[keyIndex]: dict(zip(header, each)) for each in _ret}
        own_l.info(str(_ret)+" \t "+str(ret))
        return ret,time.time()
    def _getExport(self, coord:_Detail, idx, total_idx, pName) -> List[List[str]]:
        try_remove(pName)
        self.lock.acquire()
        self.secureForeground()
        # Get popup menu
        #safeBtn_moveClick(coord.handle, coord.center, 1)
        #moveClick(coord.handle,coord.center,1)
        #print("before ",win32gui.WindowFromPoint((coord.center[0]+5,coord.center[1]+5)))
        moveClick(coord.center,1,clickDelay=0.01)
        time.sleep(0.05)
        #print("after ",win32gui.WindowFromPoint((coord.center[0]+5,coord.center[1]+5)))
        #TODO 文件已存在时会弹出确认框，需要处理一下
        # Click 导出
        if not openExportWindow(idx, total_idx):  # 被禁用
            moveClick(self.contract.center)
            self.lock.release()
            own_l.info("导出按钮被禁用")
            return []
        saveExportFile(self.mainWindow)
        # Set Location #Pass By Assertion
        # GetFileAddress #-
        self._waitForeground()
        self.lock.release()
        # Read File
        while not os.path.exists(pName):
            time.sleep(0.001)
            print("Wait File Gen")

        while 1:
            try:
                print("Wait File Done")
                os.rename(pName,pName)
                break
            except PermissionError:
                time.sleep(0.001)

        #File write done now
        with open(pName, newline='') as f:
            r= csv.reader(f, delimiter=',')
            _ret = [list(map(lambda x: x.strip(), line)) for line in r]
        try_remove(pName)
        return _ret

    @exception(l)
    def getCancelable(self):
        d = datetime.datetime.now()
        p = f'{os.environ["USERPROFILE"]}\\Documents\\{d.year}年{d.month}月{d.day}日期权委托报表.csv'
        _ret=self._getExport(self.Component["_可撤"], 5, 7, p)
        if not len(_ret):
            return {},time.time()
        header = _ret.pop(0)
        keyIndex = header.index("合约代码")

        ret={}
        for each in _ret:
            if each[keyIndex] not in ret:
                ret[each[keyIndex]]=[dict(zip(header, each))]
            else:
                ret[each[keyIndex]].append(dict(zip(header, each)))
        return ret,time.time()

    def _screenshotPara(self, name, fileName=None):
        if fileName == -1:
            fileName = name + str(time.time()) + ".bmp"
        c = self.Component[name]
        e = win32gui.ScreenToClient(self.tradeWindowBig, tuple(c.rect[:2]))
        return self.tradeWindowBig, Size(c.rect), e, fileName
    def getStatusBarPara(self):
        c = win32gui.GetParent(self.contract.handle)
        c_rect=win32gui.GetWindowRect(c)
        e=win32gui.ScreenToClient(self.tradeWindowBig, c_rect[:2])
        _, _, r, _=win32gui.GetWindowRect(self.tradeWindowBig)
        return self.tradeWindowBig,(r,e[1]),(0,0),None
    def getScreenshotParas(self):
        return {
            "bar": self.getStatusBarPara(),
            "净资产": self._screenshotPara("_净资产"),
            "可用保证金": self._screenshotPara("_可用保证金"),
            "估算浮盈": self._screenshotPara("_估算浮盈"),
        }

    def locate(self):
        bar = getScreenShot(*self.getStatusBarPara())
        bound0=getScreenShot(*self._screenshotPara("_净资产"))
        bound1=getScreenShot(*self._screenshotPara("_可用保证金"))
        bound2=getScreenShot(*self._screenshotPara("_估算浮盈"))
        return bar,bound0,bound1,bound2
    @exception(l)
    def cancelAll(self):
        self.lock.acquire()
        try:
            # moveClick(self.Component["全撤单"].center,clickDelay=0.3)
            s=time.time()
            self.clickAndWait(self.Component["全撤单"])
            print("cancel All Wait Takes ",time.time()-s)
            self.secureForeground()
        except Exception as err:
            l.debug(self.Component["全撤单"])
            l.exception(err)
        finally:
            self.lock.release()
    def clickAndWait(self,item:_Detail):
        conditional_moveClick(item.center,before=partial(_condition_BST_HOT,hdl=item.handle,pos=item.center)
                              ,mid=partial(_condition_BST_PUSHED,hdl=item.handle))
        return
        _move(item.center)
        t=thread.Process(target=waitBtnDone,args=(item.handle,))
        t.start()
        _leftPress()
        t.join()
        _move(item.center)
        _leftRelease()

    def changeTpye(self):
        i= random.randint(0, 2)
        if i>1:
            self.changeToOption()
        else:
            self.changeToStock()

    #TODO 加个确认，保证界面切换成功
    def changeToOption(self):
        changeComboIndex(self.Component['类型切换按钮'].handle, '股票期权')

    def changeToStock(self):
        changeComboIndex(self.Component['类型切换按钮'].handle, '普通证券')


def try_remove(pName):
    try:
        os.remove(pName)
    except Exception as e:
        pass

def waitBtnChecked(hdl):
    prev=None
    while not (win32con.BST_CHECKED & win32gui.SendMessage(hdl,win32con.BM_GETCHECK)):
        now=win32gui.SendMessage(hdl,win32con.BM_GETCHECK)
        if prev!=now:
            prev=now
            print(now)
        time.sleep(0.001)

def waitBtnDone(hdl):
    _s=time.time()
    while not (win32con.BST_PUSHED & win32gui.SendMessage(hdl,win32con.BM_GETSTATE)):
        if time.time()-_s>0.2:
            break
        time.sleep(0.001)
def _condition_BST_PUSHED(hdl):
    print(win32gui.SendMessage(hdl,win32con.BM_GETSTATE))
    return win32con.BST_PUSHED & win32gui.SendMessage(hdl,win32con.BM_GETSTATE)
def _condition_BST_HOT(hdl,pos):
    print(win32gui.SendMessage(hdl,win32con.BM_GETSTATE))
    return win32gui.GetCursorPos()==pos

    return win32con.BST_FOCUS & win32gui.SendMessage(hdl,win32con.BM_GETSTATE)
@exception(l)
def getScreenShot(hwnd, bottom_right_coord, start_top_left_coord, fileName):
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w = r - l
    h = b - t

    bottom_right_coord = bottom_right_coord if bottom_right_coord else (w, h)

    hwndDC = win32gui.GetWindowDC(hwnd)

    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, *bottom_right_coord)  # w, h)

    saveDC.SelectObject(saveBitMap)

    saveDC.BitBlt((0, 0), bottom_right_coord, mfcDC, start_top_left_coord, win32con.SRCCOPY)

    signedIntsArray = saveBitMap.GetBitmapBits(True)
    img = np.fromstring(signedIntsArray, dtype='uint8')
    img.shape = (bottom_right_coord[1], bottom_right_coord[0], 4)  # TODO Shape
    if fileName:
        saveBitMap.SaveBitmapFile(saveDC, fileName)
        # n_img = img[:, :, :3]
        # p = plt.imshow(n_img)
        # plt.show()
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    return img


def recognize(img):
    warnings.warn("Do not use this",DeprecationWarning)
    try:
        r = Tesseract()
    except Exception as e:
        print(e)
        r = Tesseract(lib_path=f"{os.getcwd()}/libtesseract3052")
    res = r.recongnize(img)
    del r
    return res

def save_as_img(ar, fname):
    from PIL import Image
    Image.fromarray(ar.round().astype(np.uint8)).save(fname)

# 图片示例：
# A-----B-----C-----D
# 通过对比bar(A-D)和bound0(A-B)获取A的坐标
# 通过对比bar(A-D)和bound0(B-C)获取B的坐标
# 结果图片的高度可以获取目标数据(A-B)的坐标参数
def getBound(bar,bound0,bound1):
    r = cv2.matchTemplate(bar, bound0, cv2.TM_CCORR_NORMED)
    #多个相似度相同的点的时候是否返回第一个点，要不没法保障
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if(confidence < 0.5):
        print("Low Confidence")
    leftBoundX = xy[0] + bound0.shape[1]  # Confirm

    r = cv2.matchTemplate(bar, bound1, cv2.TM_CCORR_NORMED)
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if(confidence < 0.5):
        print("Low Confidence")
    rightBoundX = xy[0]
    return leftBoundX, xy[1], rightBoundX, xy[1]+bound0.shape[0]
    # recognize(item[1:3,0:2].copy())


def binify(r):
    return np.where(r > 128, 255, 0).astype(np.uint8)

def main():
    mp.freeze_support()
    a = TradeInterface()
    a.activate()
    a.secureForeground()
    # print(a.getOwned())
    # a.do(10001669, 1, 0, 3, 10, 1, 0)
    # a.do(10001701, 0, 0, 1, 0.42, 0, 0.001)
    # a.external_setContract(10001669)
    s=time.time()
    # a.do(10001669, 0, 0, 2, 0.728, 0, 0.001)
    s1=time.time()
    a.do(10003505, 0, 0, 4, 0.001, 0, 0.001)
    s2=time.time()
    print(s2-s1," ",s1-s)
    return a


if __name__ == '__main__':
    main()
    # a.setContract(10001669)
    # import time
    #

    # for each in threadList:
    #     each.terminate()
