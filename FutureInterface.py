import time

import win32gui

from f import *
from f import _get_screen_center_window, _Detail

try:
    from exception_logger import *

    l = create_logger()
    own_l = create_logger("ownLog", "./own.log")
except ImportError:
    l = None
    def exception(l):
        def decorator(function):
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                return function(*args, **kwargs)

            return wrapper

        return decorator


class FutureInterface:
    def __del__(self):
        for each in self.threadList:
            each.terminate()

    @exception(l)
    def __init__(self, account="", key=""):
        self.threadList = []
        self.lock = mp.Lock()
        self.account = (account, key)
        if os.path.exists("keys_future.json"):
            with open("keys_future.json", "r") as f:
                keys = json.load(f)
        else:
            keys = {
                "合约": (46, 436, 182, 450),
                "价格": (63, 518, 184, 538),
                "数量": (63, 488, 133, 508),
                "开仓": (43, 461, 102, 479),
                "平仓": (104, 461, 162, 479),
                "平今": (164, 461, 223, 479),
                "自动": (238, 461, 298, 479),
                "FOK": (208, 519, 244, 539),
                "FAK": (251, 519, 287, 539),
                "交易类型": (240, 436, 274, 450),
                "买入": (91, 583, 187, 653),
                "卖出": (199, 583, 295, 653),
                "全撤": (933, 903, 955, 1009),
                # "收益信息栏": (1100, 33, 1795, 73),

                "_可撤标签": (62, 667, 116, 686),
                "_可用资金": (816, 52, 910, 73),
                "_风险度": (912, 52, 1006, 73),
                "_当前权益": (15, 52, 105, 73),
                "_权益变化": (107, 52, 206, 73),
                "_持仓": (1102, 550, 1204, 575),
                "_可撤": (331, 807, 435, 841),
            }
        reposition(keys)
        with open("keys_future.json", "w") as f:
            json.dump(keys, f)
        from typing import Dict
        self.Component: Dict[str, _Detail] = {}  # 组件
        self.TrackArea = []  # 追踪窗口
        self.mainWindow = None
        self.tradeWindowBig = None
        self.centerWindow = None

        self.getWindow(keys)
        if "edit" in win32gui.GetClassName(self.Component["合约"].handle).lower():
            print("Got EditBox")
            self.contractEdit: _Detail = self.Component["合约"]  # self.getEditBox(self.contract.handle)
            self.contract: _Detail = self.Component["合约"] # self.Component["合约"]
        else:
            self.contract: _Detail = self.Component["合约"]
            self.contractEdit: _Detail = self.getEditBox(self.contract.handle)
        if "edit" in win32gui.GetClassName(self.Component["交易类型"].handle).lower():
            print("Got EditBox")
            self.tradeTypeEdit: _Detail = self.Component["交易类型"]  # self.getEditBox(self.contract.handle)
            self.tradeType: _Detail = self.Component["交易类型"] # self.Component["合约"]
        else:
            self.tradeType: _Detail = self.Component["交易类型"]
            self.tradeTypeEdit: _Detail = self.getEditBox(self.contract.handle)
        self.openPosition: _Detail = self.Component["开仓"]
        self.closePosition: _Detail = self.Component["平仓"]
        self.closeTodayPosition: _Detail = self.Component["平今"]
        self.amount: _Detail = self.Component["数量"]
        self.price: _Detail = self.Component["价格"]
        self.net: _Detail = self.Component["自动"]


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

    def refresh(self):
        win32gui.FindWindow(None, "闪电王")
        return

    def getWindow(self, key_pos, process_title="闪电王"):
        # <editor-fold desc="w=主窗口">
        w = win32gui.FindWindow(None, process_title)
        print(w)
        if w == 0:
            w = win32gui.FindWindow(None, "闪电王")
        assert w != 0
        print(w)
        self.mainWindow = w
        print("Process HandleID {}".format(w))
        if any(filter(lambda x: x < -10000, win32gui.GetWindowRect(w))):
            raise AssertionError("{}\nMaximize The Window".format(win32gui.GetWindowRect(w)))
        # win32gui.BringWindowToTop(w) TODO enable this or SetForegroundWindow
        # win32gui.SetForegroundWindow(w)
        children=EnumChildWindows(w)
        for each in children:
            if '资金显示' in win32gui.GetWindowText(each):
                self.tradeWindowBig=each
        assert self.tradeWindowBig!=0

        self.centerWindow = _get_screen_center_window()
        # </editor-fold>
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
        # safeBtn_moveClick(self.contract.handle,self.contract.center)
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
        prev_p = None
        s = time.time()
        while 1:
            if time.time() - s > 1:
                raise AssertionError("等太久了")
            text = getText(editBoxHdl)
            if len(text) == 0:
                time.sleep(0.001)
            if contract == text:
                break
            if contract.startswith(text):
                p = "等待输入完成 " + text
                if prev_p != p:
                    print(p)
                    prev_p = p
                time.sleep(0.001)
                continue
            if onlyLength and len(text) >= len(contract):
                print(text, "/", contract)
                break

            moveClick(self.contract.center)
            time.sleep(0.01)
            typeNum("\t" * 12)
            raise AssertionError("Wrong Input" + text)
        print("confirmInput Wait Time: ", time.time() - s)

    def setContract(self, contract):
        contract = str(contract)
        text = getText(self.contractEdit.handle)
        if text == contract:
            return
        moveClick(self.contract.center)
        win32gui.SendMessage(self.contractEdit.handle, win32con.WM_SETTEXT, 0, contract)
        typeNum("\n")
        # TODO 最后一个onlyLength参数意义不明
        self.confirmInput(self.contractEdit.handle, contract, True)  # TODO confirm by popup edit
        self.contract.status.value = contract

    @exception(l)
    def external_setContract(self, contract):
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
        elif position == 1:
            c, o = self.closePosition, self.openPosition
        else:
            # 平今
            c=self.closeTodayPosition
        # if c.status.value == 1:
        #     return

        moveClick(c.center)

        # # TODO:verify checked
        # c.status.value = 1
        # o.status.value = 0

    def setAmount(self, amount):
        amount = int(amount)
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
        # btn=self.Component["复位"]#ONGOING
        # moveClick(btn.center,2,clickDelay=0.05)

    def setPrice(self, price):
        if getText(self.Component["价格"].handle) != "对手价":
            self.clickReset()
            l.exception("price not reseted")
        setText(self.Component["价格"].handle, str(price))
        # 需要回车来确认价格的输入
        moveClick(self.Component["价格"].center)
        typeNum("\n")
        current = getText(self.Component["价格"].handle)
        if current!= str(price):
            print(f"first check price fail :{current} != {str(price)}")
            self.clickReset()

            # 重新设置一次价格
            setText(self.Component["价格"].handle, str(price))
            # 需要回车来确认价格的输入
            moveClick(self.Component["价格"].center)
            typeNum("\n")
            current = getText(self.Component["价格"].handle)
            if current != str(price):
                print(f"final check price fail :{current} != {str(price)}")
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
        waitBtnCheck(self.Component["自动"].handle,net)
        self.net.status.value = net
        time.sleep(0.1)

    def setType(self, tradeType):
        text = getText(self.tradeTypeEdit.handle)
        if text == tradeType:
            return
        moveClick(self.tradeType.center)
        if tradeType==0:
            typename='投机'
        elif tradeType==1:
            typename='保值'
        elif tradeType == 2:
            typename = '套利'
        else:
            print("交易类型修改失败，类型不对,",tradeType)
            return
        win32gui.SendMessage(self.tradeTypeEdit.handle, win32con.WM_SETTEXT, 0, typename)
        typeNum("\n")
        # TODO 最后一个onlyLength参数意义不明
        self.confirmInput(self.tradeTypeEdit.handle, typename, True)  # TODO confirm by popup edit
        self.tradeType.status.value = tradeType

    def clickBuy(self, clickDelay):
        s = time.time()
        self.clickAndWait(self.Component["买入"])
        print("Buy takes ", time.time() - s)
        # moveClick(self.Component["买入"].center, clickDelay=clickDelay)

    def clickSell(self, clickDelay):
        s = time.time()
        self.clickAndWait(self.Component["卖出"])
        print("Sell takes ", time.time() - s)
        # moveClick(self.Component["卖出"].center, clickDelay=clickDelay)

    def _waitForeground(self):
        while not self.checkForeground():
            time.sleep(0.01)

    def secureForeground(self):
        if self.checkForeground():
            return
        # TODO 检查前排弹窗
        moveClick(self.contract.center)
        cur_w = win32gui.GetForegroundWindow()
        print("Cur_w ", cur_w)
        if cur_w == 0:
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

    def do(self, contract, position, net, amt, price, direction, uid=None,tradeType=0):
        print("->start do")
        self.lock.acquire()
        try:
            self._do(contract, position, net, amt, price, direction, 0.01,tradeType)
            return (uid, True), time.time()
        except Exception as e:
            l.exception(e)
            return (uid, False), time.time()
        finally:
            print("do done->")
            self.lock.release()

    # @exception(l)
    def _do(self, contract, position, net, amt, price, direction, delay,tradeType=0):
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
        print("setNet -> setType")
        self.setType(tradeType)
        print("setType -> setPos")
        self.setPosition(position)
        print("setPos ->setAmt")
        # time.sleep(0.01)
        self.setAmount(amt)
        print("setAmt -> setPrice")
        # time.sleep(0.01)
        self.setPrice(price)
        print("-> setDone")
        # time.sleep(0.03)
        getScreenShot(self.mainWindow, None, (0, 0), f"OrderSet.{time.time()}.bmp")
        if direction == 0:
            self.clickBuy(delay)
            # self.waitBtnDone(self.Component["买入"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickBuy, delay)
        else:
            self.clickSell(delay)
            # self.waitBtnDone(self.Component["卖出"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickSell, delay)
        self.clickReset()
        print("confirmTrade -> Print")
        # TODO wait back to state

        print("apply Do ", str(datetime.datetime.now()))

    #TODO 待更新期货对应确认版本
    def confirmTrade(self, func=None, arg=None, retry=False):
        _s = time.time()
        overtime = False
        print("Confirm Trade Applied")
        t = lambda: getText(self.price.handle) != "对手价"
        f = lambda: findPopWindowByClassName(self.mainWindow, "#32770")
        while t():
            print("Wait price reset")
            if time.time() - _s > 0.1:
                overtime = True
                break
            time.sleep(0.001)
        if overtime and not retry:
            l.exception("Over time")
            func(arg)
            self.confirmTrade(func, arg, True)
            return
        if not t():
            return

        resList = f()
        # assert len(res)==1
        # res=res[0]
        for res in resList:
            text = win32gui.GetWindowText(res)
            lo = EnumChildWindows(res, after_func=lambda x: [(win32gui.GetWindowText(each), each) for each in x])
            if text == "提示" and any(map(lambda text: "合约到期提醒" in text[0], lo)):
                print(lo)
                y_btn = list(filter(lambda text: text[0].startswith("是"), lo))
                assert len(y_btn) == 1
                safeBtn_moveClick(y_btn[0][1], Center(win32gui.GetWindowRect(y_btn[0][1])))
                # moveClick(Center(win32gui.GetWindowRect(y_btn[0][1])))
            else:
                # TODO 右下角窗口处理
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
        date = d.strftime("%Y-%m-%d")
        p = f'{os.environ["USERPROFILE"]}\\Documents\\持仓_{date}.csv'
        _ret = self._getExport(self.Component["_持仓"], 4, 5, p)
        if not len(_ret):
            own_l.info("Buy stock hold {} Empty Own")
            return {}, time.time()
        header = _ret.pop(0)
        keyIndex = header.index("合约")
        # ret = {each[keyIndex]: dict(zip(header, each)) for each in _ret}
        ret = {}
        for each in _ret:
            if len(each) == 0:
                continue
            if each[keyIndex] not in ret:
                ret[each[keyIndex]] = [dict(zip(header, each))]
            else:
                ret[each[keyIndex]].append(dict(zip(header, each)))
        own_l.info(str(_ret) + " \t " + str(ret))
        return ret, time.time()

    def _getExport(self, coord: _Detail, idx, total_idx, pName) -> List[List[str]]:
        try_remove(pName)
        self.lock.acquire()
        self.secureForeground()
        # Get popup menu
        # safeBtn_moveClick(coord.handle, coord.center, 1)
        # moveClick(coord.handle,coord.center,1)
        # print("before ",win32gui.WindowFromPoint((coord.center[0]+5,coord.center[1]+5)))
        moveClick(coord.center, 1, clickDelay=0.01)
        time.sleep(0.05)
        # print("after ",win32gui.WindowFromPoint((coord.center[0]+5,coord.center[1]+5)))
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
                os.rename(pName, pName)
                break
            except PermissionError:
                time.sleep(0.001)

        # File write done now
        with open(pName, newline='') as f:
            r = csv.reader(f, delimiter=',')
            _ret = [list(map(lambda x: x.strip(), line)) for line in r]
        try_remove(pName)
        return _ret

    @exception(l)
    def getCancelable(self):
        moveClick(self.Component["_可撤标签"].center, 0, clickDelay=0.01)
        # TODO 加个延迟，防止标签没切过去，延迟大小待定
        time.sleep(0.01)
        d = datetime.datetime.now()
        date = d.strftime("%Y-%m-%d")
        p = f'{os.environ["USERPROFILE"]}\\Documents\\当日委托_{date}.csv'
        _ret = self._getExport(self.Component["_可撤"], 5, 6, p)
        if not len(_ret):
            return {}, time.time()
        header = _ret.pop(0)
        keyIndex = header.index("合约")

        ret = {}
        for each in _ret:
            if len(each)==0:
                continue
            if each[keyIndex] not in ret:
                ret[each[keyIndex]] = [dict(zip(header, each))]
            else:
                ret[each[keyIndex]].append(dict(zip(header, each)))
        return ret, time.time()

    def _screenshotPara(self, name, fileName=None):
        if fileName == -1:
            fileName = name + str(time.time()) + ".bmp"
        c = self.Component[name]
        e = win32gui.ScreenToClient(self.tradeWindowBig, tuple(c.rect[:2]))
        return self.tradeWindowBig, Size(c.rect), e, fileName

    def getStatusBarPara(self):
        c = win32gui.GetParent(self.tradeWindowBig)
        c_rect = win32gui.GetWindowRect(c)
        e = win32gui.ScreenToClient(self.tradeWindowBig, c_rect[:2])
        l, t, r, h = win32gui.GetWindowRect(self.tradeWindowBig)
        return self.tradeWindowBig, (r-l, h-t), (0, 0), None

    def getScreenshotParas(self):
        return {
            "bar": self.getStatusBarPara(),
            "当前权益": self._screenshotPara("_当前权益"),
            "权益变化": self._screenshotPara("_权益变化"),
            "风险度": self._screenshotPara("_风险度"),
            "可用资金": self._screenshotPara("_可用资金"),
        }

    def locate(self):
        bar = getScreenShot(*self.getStatusBarPara())
        bound0 = getScreenShot(*self._screenshotPara("_当前权益"))
        bound1 = getScreenShot(*self._screenshotPara("_权益变化"))
        bound2 = getScreenShot(*self._screenshotPara("_可用资金"))
        bound3 = getScreenShot(*self._screenshotPara("_风险度"))
        return bar, bound0, bound1, bound2

    @exception(l)
    def cancelAll(self):
        self.lock.acquire()
        try:
            # moveClick(self.Component["全撤单"].center,clickDelay=0.3)
            s = time.time()
            moveClick(self.Component['全撤'].center,clickDelay=0.3)
            print("cancel All Wait Takes ", time.time() - s)
            self.secureForeground()
        except Exception as err:
            l.debug(self.Component['全撤'])
            l.exception(err)
        finally:
            self.lock.release()

    def clickAndWait(self, item: _Detail):
        conditional_moveClick(item.center, before=partial(_condition_BST_HOT, hdl=item.handle, pos=item.center)
                              , mid=partial(_condition_BST_PUSHED, hdl=item.handle))
        return
        _move(item.center)
        t = thread.Process(target=waitBtnDone, args=(item.handle,))
        t.start()
        _leftPress()
        t.join()
        _move(item.center)
        _leftRelease()

def try_remove(pName):
    try:
        os.remove(pName)
    except Exception as e:
        pass

def saveExportFile(mainW):
    while 1:
        r = findPopWindowByClassName(mainW, "#32770")
        if not len(r):
            time.sleep(0.001)
            continue
        if '选择输出文件' not in map(lambda x:win32gui.GetWindowText(x),r):
            time.sleep(0.001)
            continue
        if len(r)!=1:
            r=list(filter(lambda x:win32gui.GetWindowText(x)=='选择输出文件',r))
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


def waitBtnChecked(hdl):
    prev = None
    while not (win32con.BST_CHECKED & win32gui.SendMessage(hdl, win32con.BM_GETCHECK)):
        now = win32gui.SendMessage(hdl, win32con.BM_GETCHECK)
        if prev != now:
            prev = now
            print(now)
        time.sleep(0.001)

def waitBtnCheck(hdl,status):
    prev = None
    while not (status==win32gui.SendMessage(hdl, win32con.BM_GETCHECK)):
        now = win32gui.SendMessage(hdl, win32con.BM_GETCHECK)
        if prev != now:
            prev = now
            print(now)
        time.sleep(0.001)


def waitBtnDone(hdl):
    _s = time.time()
    while not (win32con.BST_PUSHED & win32gui.SendMessage(hdl, win32con.BM_GETSTATE)):
        if time.time() - _s > 0.2:
            break
        time.sleep(0.001)


def _condition_BST_PUSHED(hdl):
    print(win32gui.SendMessage(hdl, win32con.BM_GETSTATE))
    return win32con.BST_PUSHED & win32gui.SendMessage(hdl, win32con.BM_GETSTATE)


def _condition_BST_HOT(hdl, pos):
    print(win32gui.SendMessage(hdl, win32con.BM_GETSTATE))
    return win32gui.GetCursorPos() == pos

    return win32con.BST_FOCUS & win32gui.SendMessage(hdl, win32con.BM_GETSTATE)


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
    warnings.warn("Do not use this", DeprecationWarning)
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


def getBound_future(bar, bound0, bound1):
    r = cv2.matchTemplate(bar, bound0, cv2.TM_CCORR_NORMED)
    # 多个相似度相同的点的时候是否返回第一个点，要不没法保障
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if (confidence < 0.5):
        print("Low Confidence")
    leftBoundX=xy[0]
    leftBoundY = xy[1] + bound0.shape[0]  # Confirm

    r = cv2.matchTemplate(bar, bound1, cv2.TM_CCORR_NORMED)
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if (confidence < 0.5):
        print("Low Confidence")
    rightBoundX = xy[0]
    return leftBoundX, leftBoundY, rightBoundX, bar.shape[0]
    # recognize(item[1:3,0:2].copy())


def binify(r):
    return np.where(r > 128, 255, 0).astype(np.uint8)


def main():
    mp.freeze_support()
    a = FutureInterface()
    a.activate()
    a.secureForeground()
    a.locate()
    # a.getOwned()
    # time.sleep(1)
    # print(a.getCancelable())
    # time.sleep(0.5)
    # # a.cancelAll()
    # # print(a.getOwned())
    # # a.do(10001669, 1, 0, 3, 10, 1, 0)
    # # a.do(10001701, 0, 0, 1, 0.42, 0, 0.001)
    # # a.cancelAll()
    # # s = time.time()
    # # a.do(600000, 0, 0, 100, 8.17, 0, 1234)
    # time.sleep(5)
    # a.external_setContract('cu2108')
    # a.setType(0)
    #
    # a.setPosition(1)
    # a.setAmount(3)
    # a.setNet(1)
    # time.sleep(3)
    # a.setPrice(10)
    # s1 = time.time()
    # a.do(10001669, 0, 1, 4, 0.728, 0, 0.001)
    # s2 = time.time()
    # print(s2 - s1, " ", s1 - s)
    return a


if __name__ == '__main__':
    main()
