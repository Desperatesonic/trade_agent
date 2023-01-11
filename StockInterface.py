import time

from pywinauto import application

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


class Status:
    def __init__(self, value=None):
        self.value = value



class StockInterface:
    def __del__(self):
        for each in self.threadList:
            each.terminate()

    @exception(l)
    def __init__(self, account="", key=""):
        self.holder_map = {"SH": "A426634881", "SZ": "0259731971"}
        self.threadList = []
        self.lock = mp.Lock()
        self.account = (account, key)
        if os.path.exists("keys_stock.json"):
            with open("keys_stock.json", "r") as f:
                keys = json.load(f)
        else:
            keys = {

                "证券代码": (211, 687, 304, 707),
                "价格": (211, 733, 318, 753),
                "数量": (211, 805, 316, 825),
                "买入下单": (286, 831, 344, 852),
                "卖出下单": (286, 831, 344, 852),
                "重填": (191, 830, 249, 851),
                "类型切换按钮": (2, 634, 157, 654),
                "股东代码": (211, 664, 354, 684),
                "委托": (554, 737, 754, 757),
                "可撤-委托按钮": (537, 829, 558, 988),
                # "全撤单" anchored in for positioning,
                "_买入标签": (25, 663, 75, 677),
                "_卖出标签": (25, 682, 72, 702),
                "_可用资金": (306, 634, 365, 653),
                "_总资产": (169, 636, 221, 655),
                "_浮动盈亏": (448, 636, 510, 655),
                "_持仓": (1102, 740, 1204, 772),
                "_可撤": (1117, 897, 1219, 929),
                "_订单筛选": (554, 831, 654, 852),
                "_撤单标签": (25, 722, 75, 742),
                "_撤单按钮": (563, 664, 623, 684),
                "_全选按钮": (648, 664, 708, 684),
            }
        reposition(keys)
        with open("keys_stock.json", "w") as f:
            json.dump(keys, f)
        from typing import Dict
        self.Component: Dict[str, _Detail] = {}  # 组件
        self.TrackArea = []  # 追踪窗口
        self.mainWindow = None
        self.tradeWindowBig = None
        self.centerWindow = None
        self.direction = None

        # 用于委托筛选的listbox
        self.orderListBox = None

        self.getWindow(keys)
        if "edit" in win32gui.GetClassName(self.Component["证券代码"].handle).lower():
            print("Got EditBox")
            self.contractEdit: _Detail = self.Component["证券代码"]  # self.getEditBox(self.contract.handle)
            self.contract: _Detail = self.Component["证券代码"] # self.Component["合约"]
        else:
            self.contract: _Detail = self.Component["证券代码"]
            self.contractEdit: _Detail = self.getEditBox(self.contract.handle)
        self.amount: _Detail = self.Component["数量"]
        self.price: _Detail = self.Component["价格"]

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
        if w == 0:
            w = win32gui.FindWindow(None, "华泰股票期权 - [期权T型报价]")
        assert w != 0
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
        _where = findGrandChildWindowsByName(tradeWindowBig, "重填")
        if len(_where) != 1:
            s = "可能交易界面锁定 或底层布局发生变化"
            raise AssertionError("{}\n{}".format(s, _where))
        tradeArea = win32gui.GetParent(_where[0])
        print("tradeArea", tradeArea)
        # </editor-fold>

        # 股票没有全撤单的按钮
        # <editor-fold desc="_cancel=撤单hdl">
        # _cancel = findGrandChildWindowsByName(tradeWindowBig, "全撤单")
        # if len(_where) != 1:
        #     raise AssertionError(_where)
        # _cancel = _cancel[0]
        # #  </editor-fold>
        #
        # key_pos["全撤单"] = win32gui.GetWindowRect(_cancel)

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
        if self.contract.status.value == contract:
            return
        # 不点击合约区的话，联想结果中可能同ID指数排在第一个
        moveClick(self.contract.center)
        # win32gui.SetFocus(self.contractEdit.handle)
        # print("Set Done")

        # self.waitFocus()
        win32gui.SendMessage(self.contractEdit.handle, win32con.WM_SETTEXT, 0, contract)
        # popHdl = self.waitPopup()
        # s = time.time()
        # typeNum(contract)
        # print("Input Time:" + str(time.time() - s))
        typeNum("\n")
        # s = time.time()
        # _i = 0
        # while win32gui.GetParent(win32gui.WindowFromPoint(self.contract.center)) == popHdl:
        #     time.sleep(0.001)
        #     _i += 1
        #     if _i % 10 == 0:
        #         _i = 0
        #         print("Waiting invis")
        #
        # print("Invis Wait Time:" + str(time.time() - s))

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
        else:
            c, o = self.closePosition, self.openPosition
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
        self.clickAndWait(self.Component["重填"])
        return
        # btn=self.Component["复位"]#ONGOING
        # moveClick(btn.center,2,clickDelay=0.05)

    def setPrice(self, price):
        if getText(self.Component["数量"].handle) != "":
            self.setAmount(0)
            l.exception("Amount not reseted")
        # TODO reset
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
        if self.net.status.value == net:
            return
        moveClick(self.net.center)
        self.net.status.value = net
        time.sleep(0.1)

    def clickBuy(self, clickDelay):
        s = time.time()
        self.clickAndWait(self.Component["买入下单"])
        print("Buy takes ", time.time() - s)
        # moveClick(self.Component["买入"].center, clickDelay=clickDelay)

    def clickSell(self, clickDelay):
        s = time.time()
        self.clickAndWait(self.Component["卖出下单"])
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

    def do(self, contract, position, net, amt, price, direction, uid=None, tradeType=0):
        print("->start do")
        self.lock.acquire()
        try:
            self._do(contract, position, net, amt, price, direction, 0.01)
            return (uid, True), time.time()
        except Exception as e:
            l.exception(e)
            return (uid, False), time.time()
        finally:
            print("do done->")
            self.lock.release()

    # @exception(l)
    def _do(self, contract, position, net, amt, price, direction, delay):
        print("-> secure")
        self.secureForeground()
        print("secure -> setDirection")
        # 切换买卖标签页
        if direction == 0:
            self.clickBuyLabel()
            self.contract.status.value = ''
        else:
            self.clickSellLabel()
            self.contract.status.value = ''
        print("setDirection -> setCon")
        def getHolderCode(contract):
            if int(contract) >= 600000 or contract.startswith("204") :
                return "SH"
            else:
                return "SZ"
        self.changeHolderCode(self.holder_map[getHolderCode(contract)])
        try:
            self.setContract(contract)
        except Exception as e:
            l.exception(e)
            l.debug("retry setContract once")
            self.setContract(contract)

        print("setCon -> setPrice")
        # time.sleep(0.01)
        self.setPrice(price)
        print("setPrice -> setAmt")
        # time.sleep(0.01)
        self.setAmount(amt)
        print("-> setDone")
        # time.sleep(0.03)
        if direction == 0:
            self.clickBuy(delay)
            time.sleep(0.05)
            getScreenShot(self.mainWindow, None, (0, 0), f"OrderSet.{time.time()}.bmp")
            # self.waitBtnDone(self.Component["买入"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickBuy, delay)
        else:
            self.clickSell(delay)
            time.sleep(0.05)
            getScreenShot(self.mainWindow, None, (0, 0), f"OrderSet.{time.time()}.bmp")
            # self.waitBtnDone(self.Component["卖出"].handle)
            print("-> confirmTrade")
            self.confirmTrade(self.clickSell, delay)
        # self.clickReset()
        print("confirmTrade -> Print")
        # TODO wait back to state

        print("apply Do ", str(datetime.datetime.now()))

    #通过数量框重置为空白来确认
    def confirmTrade(self, func=None, arg=None, retry=False):
        _s = time.time()
        overtime = False
        print("Confirm Trade Applied")
        t = lambda: getText(self.amount.handle) != ""
        f = lambda: findPopWindowByClassName(self.mainWindow, "#32770")
        while t():
            print("Wait amount reset")
            if time.time() - _s > 0.1:
                overtime = True
                break
            time.sleep(0.001)
        if overtime and not retry:
            l.exception("Over time")
            # func(arg)
            l.info("Amount reset over time , click again")
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
            #类似这种 600000 合约的涨停价：9.99 跌停价：8.17 下单价：8.15 超过涨跌停，是否继续下单?
            if text == "提示" and any(map(lambda text: "超过涨跌停" in text[0], lo)):
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

        print("Wait amount reset after popup")
        self.clickReset()
        while t():
            time.sleep(0.001)
        print("Confirmed")

    @exception(l)
    def getOwned(self):
        d = datetime.datetime.now()
        p = f'{os.environ["USERPROFILE"]}\\Documents\\{d.year}年{d.month}月{d.day}日证券持仓报表.csv'
        _ret = self._getExport(self.Component["_持仓"], 0, 2, p)
        if not len(_ret):
            own_l.info("Buy stock hold {} Empty Own")
            return {}, time.time()
        header = _ret.pop(0)
        keyIndex = header.index("证券代码")
        ret = {each[keyIndex]: dict(zip(header, each)) for each in _ret}
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
        # 检查是否处于可撤页签，而非委托页签
        tag = getText(self.Component['可撤-委托按钮'].handle)
        if tag!='可撤—委托':
            self.clickAndWait(self.Component['可撤-委托按钮'])
            time.sleep(0.01)
            tag = getText(self.Component['可撤-委托按钮'].handle)
            if tag != '可撤—委托':
                self.clickAndWait(self.Component['可撤-委托按钮'])
                time.sleep(0.01)
                tag = getText(self.Component['可撤-委托按钮'].handle)
                if tag != '可撤—委托':
                    l.error("切换可撤页签失败,查询全部订单")
        d = datetime.datetime.now()
        p = f'{os.environ["USERPROFILE"]}\\Documents\\{d.year}年{d.month}月{d.day}日证券委托报表.csv'
        _ret = self._getExport(self.Component["_可撤"], 3, 5, p)
        if not len(_ret):
            return {}, time.time()
        header = _ret.pop(0)
        keyIndex = header.index("证券代码")

        ret = {}
        for each in _ret:
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
        c = win32gui.GetParent(self.contract.handle)
        c_rect = win32gui.GetWindowRect(c)
        e = win32gui.ScreenToClient(self.tradeWindowBig, c_rect[:2])
        _, _, r, _ = win32gui.GetWindowRect(self.tradeWindowBig)
        return self.tradeWindowBig, (r, e[1]), (0, 0), None

    def getScreenshotParas(self):
        return {
            "bar": self.getStatusBarPara(),
            "总资产": self._screenshotPara("_总资产"),
            "可用资金": self._screenshotPara("_可用资金"),
            "浮动盈亏": self._screenshotPara("_浮动盈亏"),
        }

    def locate(self):
        bar = getScreenShot(*self.getStatusBarPara())
        bound0 = getScreenShot(*self._screenshotPara("_总资产"))
        bound1 = getScreenShot(*self._screenshotPara("_可用资金"))
        bound2 = getScreenShot(*self._screenshotPara("_浮动盈亏"))
        return bar, bound0, bound1, bound2

    @exception(l)
    def cancelAll(self):
        self.secureForeground()
        self.clickAndWait(self.Component["_撤单标签"])
        time.sleep(0.01)
        # 确保切换页签成功
        button_cancel = win32gui.WindowFromPoint(self.Component["_撤单按钮"].center)
        if getText(button_cancel) != '撤单':
            self.clickAndWait(self.Component["_撤单标签"])
            time.sleep(0.01)
            button_cancel = win32gui.WindowFromPoint(self.Component["_撤单按钮"].center)
            if getText(button_cancel) != '撤单':
                raise AssertionError("切换撤单界面失败")
        # 选中全部订单
        button_select_all = win32gui.WindowFromPoint(self.Component["_全选按钮"].center)
        if getText(button_select_all) != '取消全选':
            self.clickAndWait(self.Component["_全选按钮"])
            time.sleep(0.01)
            button_select_all = win32gui.WindowFromPoint(self.Component["_全选按钮"].center)
            if getText(button_select_all) != '取消全选':
                raise AssertionError("选中全部委托失败")

        self.clickAndWait(self.Component["_撤单按钮"])
        self.clickAndWait(self.Component["_买入标签"])
        time.sleep(0.01)


    @exception(l)
    def cancelAll_old(self):
        self.lock.acquire()
        try:
            # moveClick(self.Component["全撤单"].center,clickDelay=0.3)
            s = time.time()
            moveClick(self.Component['_可撤'].center,1,clickDelay=0.3)
            time.sleep(0.05)
            # 右键全选。如果已经是全选状态就不再重复点击
            if openRightClickSelectWindow(1,5):
                moveClick(self.Component['_可撤'].center,1,clickDelay=0.3)
                # 右键点击撤销
                openRightClickWindow(0,5)
                print("cancel All Wait Takes ", time.time() - s)
            else:
                print("cancel All Fail Takes ", time.time() - s)
            self.secureForeground()
        except Exception as err:
            l.debug(self.Component['_可撤'])
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

    def clickBuyLabel(self):
        # 本地存储当前状态的话，万一某一次状态与实际情况不一致可能会有问题
        # if self.direction == 'buy':
        #     return
        if getText(self.Component["买入下单"].handle) == '买入下单':
            return
        s = time.time()
        self.clickAndWait(self.Component["_买入标签"])
        if getText(self.Component["买入下单"].handle)!='买入下单':
            print("first buy label set fail!")
            self.clickAndWait(self.Component["_买入标签"])
            if getText(self.Component["买入下单"].handle) != '买入下单':
                assert AssertionError("买入标签切换失败")
        self.direction = 'buy'
        print("Change label to buy ", time.time() - s)

    def clickSellLabel(self):
        # 本地存储当前状态的话，万一某一次状态与实际情况不一致可能会有问题
        # if self.direction == 'sell':
        #     return
        if getText(self.Component["卖出下单"].handle) == '卖出下单':
            return
        s = time.time()
        self.clickAndWait(self.Component["_卖出标签"])
        if getText(self.Component["卖出下单"].handle)!='卖出下单':
            print("first sell label set fail!")
            self.clickAndWait(self.Component["_卖出标签"])
            if getText(self.Component["卖出下单"].handle) != '卖出下单':
                assert AssertionError("_卖出标签切换失败")
        self.direction = 'sell'
        print("Change label to sell ", time.time() - s)

    def changeTpye(self):
        i= random.randint(0, 2)
        if i>1:
            self.chengeToOption()
        else:
            self.changeToStock()

    def chengeToOption(self):
        changeComboIndex(self.Component['类型切换按钮'].handle,'股票期权')

    def changeToStock(self):
        changeComboIndex(self.Component['类型切换按钮'].handle,'普通证券')

    # 查找委托区域的listBox组件，用于后面筛选
    def findOrderListBox(self):
        childrens = EnumChildWindows(self.Component['委托'].handle,after_func=lambda x: [(win32gui.GetClassName(each),each) for each in x])
        for class_name,handle in childrens:
            if class_name=='ListBox':
                self.orderListBox = handle
                return

    def findOrder(self, text):
        if self.orderListBox == None:
            return None
        return win32gui.SendMessage(self.orderListBox, win32con.LB_FINDSTRING, 0, text)

    # 筛选指定订单
    def selectOrder(self, order_id):
        # 使用pywinauto连接到对应程序
        # pip install -U pywinauto
        app = application.Application().connect(handle=self.mainWindow)
        # 初始化查找listBox
        self.findOrderListBox()
        listbox = app.window(handle=self.orderListBox)

        # 检查listbox的可见性
        time_now = time.time()
        while not listbox.is_visible():
            # 在笔记本上跑的时候0.1可能会不够，改成0.2试试
            if time.time()-time_now>0.2:
                break
            self.click_order_filter()
            time.sleep(0.005)
        # if not listbox.is_visible():
        #     # 不可见时点击筛选项，显示listbox
        #     self.click_order_filter()
        #     # 加点延迟，防止响应慢导致后续检查继续失败
        #     # TODO 可以做成循环检查直到超时或成功
        #     time.sleep(0.01)
        if not listbox.is_visible():
            raise AssertionError("打开筛选列表失败")
        # 检查指定订单是否在筛选条件中
        orders = listbox.wrapper_object().item_texts()
        if order_id not in orders:
            print(f"{order_id} not in {orders}")
            raise AssertionError("待撤销订单错误")
        listbox.wrapper_object().select(order_id)

    def click_order_filter(self):
        moveClick(self.Component['_订单筛选'].center,0)

    # 撤销指定订单
    def cancelOrder(self, orderID):
        self.selectOrder(orderID)
        # 借助全撤单来实现筛选后的订单撤销
        # 需要注意，右键点击撤单时需要位于选中订单上，所以这里默认把右键位置即“可撤"按钮位置放于第一条订单处
        self.cancelAll_old()
        # 检查是否撤销成功,可以通过再次筛选该订单来查询是否撤销成功
        # 撤单成功后，委托编号也不会消失，不能直接通过这里判断
        # try:
        #     self.selectOrder(orderID)
        #     raise AssertionError("撤销失败，订单仍可以查到")
        # except AssertionError as e:
        #     if e.args[0] == "待撤销订单错误":
        #         return
        #     else:
        #         raise e
        # 需要重置筛选条件，防止影响后续可撤查询
        self.selectOrder('取消')

    def changeHolderCode(self, code):
        changeComboIndex(self.Component['股东代码'].handle, str(code))

# 获取下单结果弹窗内容
# 弹窗结果不够即时，多个订单连续失败时也只有一个弹窗，先不关注
def getPopWindowText(handle):
    childWindows = EnumChildWindows(handle)
    import ctypes
    result = []
    for each in childWindows:
        class_name = win32gui.GetClassName(each)
        if class_name != 'ListBox':
            continue
        count = win32gui.SendMessage(each, win32con.LB_GETCOUNT)
        for i in range(0,count):
            text_len = win32gui.SendMessage(each, win32con.LB_GETTEXTLEN, 0)
            text = ctypes.create_unicode_buffer(text_len + 1)
            lParamAddress = ctypes.addressof(text)
            win32gui.SendMessage(each, win32con.LB_GETTEXT, 0, lParamAddress)
            result.append(text.value.replace('\u200e', ''))


def openRightClickWindow(click_idx, idx_count):
    mii, extra = win32gui_struct.EmptyMENUITEMINFO()
    while 1:
        t = findPopWindowByClassName(0, "#32768")
        if len(t):
            assert len(t) == 1
            print(win32gui.IsWindowVisible(t[0]))
            h = get_hmenu(t[0])
            print(win32gui.GetMenuItemCount(h))
            print("*************")
            print(idx_count)
            assert win32gui.GetMenuItemCount(h) == idx_count
            _, rect = win32gui.GetMenuItemRect(0, h, click_idx)

            win32gui.GetMenuItemInfo(h, click_idx, 1, mii)
            s_info = win32gui_struct.UnpackMENUITEMINFO(mii)
            if s_info.fState != 0:
                warnings.warn(f"{s_info.text} is disabled!", RuntimeWarning)
                return False
            time.sleep(0.05)
            print("->Click")
            #moveClick(Center(rect),clickDelay=0.01)


            def _before_cond():
                mi, extra = win32gui_struct.EmptyMENUITEMINFO()
                win32gui.GetMenuItemInfo(h, click_idx, 1, mi)
                s_info = win32gui_struct.UnpackMENUITEMINFO(mi)
                return win32con.MFS_HILITE | s_info.fState
            conditional_moveClick(Center(rect),before=_before_cond)
            print("Click->")
            break
        time.sleep(0.001)
        print("openExportWindow Looping")
    print("return openExportWindow->")
    return True


def openRightClickSelectWindow(click_idx, idx_count):
    mii, extra = win32gui_struct.EmptyMENUITEMINFO()
    while 1:
        t = findPopWindowByClassName(0, "#32768")
        if len(t):
            assert len(t) == 1
            print(win32gui.IsWindowVisible(t[0]))
            h = get_hmenu(t[0])
            assert win32gui.GetMenuItemCount(h) == idx_count
            _, rect = win32gui.GetMenuItemRect(0, h, click_idx)

            win32gui.GetMenuItemInfo(h, click_idx, 1, mii)
            s_info = win32gui_struct.UnpackMENUITEMINFO(mii)
            if s_info.fState != 0:
                warnings.warn(f"{s_info.text} is disabled!", RuntimeWarning)
                return False
            if s_info.text=='全部取消选中':
                warnings.warn(f"{s_info.text},cancel first!", RuntimeWarning)
                def _before_cond():
                    mi, extra = win32gui_struct.EmptyMENUITEMINFO()
                    win32gui.GetMenuItemInfo(h, click_idx, 1, mi)
                    s_info = win32gui_struct.UnpackMENUITEMINFO(mi)
                    return win32con.MFS_HILITE | s_info.fState
                conditional_moveClick(Center(rect), before=_before_cond)
            elif s_info.text!='全部选中':
                warnings.warn(f"{s_info.text} unknown", RuntimeWarning)
                return False
            time.sleep(0.05)
            print("->Click")
            #moveClick(Center(rect),clickDelay=0.01)


            def _before_cond():
                mi, extra = win32gui_struct.EmptyMENUITEMINFO()
                win32gui.GetMenuItemInfo(h, click_idx, 1, mi)
                s_info = win32gui_struct.UnpackMENUITEMINFO(mi)
                return win32con.MFS_HILITE | s_info.fState
            conditional_moveClick(Center(rect),before=_before_cond)
            print("Click->")
            break
        time.sleep(0.001)
        print("openExportWindow Looping")
    print("return openExportWindow->")
    return True

def try_remove(pName):
    try:
        os.remove(pName)
    except Exception as e:
        pass


def waitBtnChecked(hdl):
    prev = None
    while not (win32con.BST_CHECKED & win32gui.SendMessage(hdl, win32con.BM_GETCHECK)):
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


def getBound(bar, bound0, bound1):
    r = cv2.matchTemplate(bar, bound0, cv2.TM_CCORR_NORMED)
    # 多个相似度相同的点的时候是否返回第一个点，要不没法保障
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if (confidence < 0.5):
        print("Low Confidence")
    leftBoundX = xy[0] + bound0.shape[1]  # Confirm

    r = cv2.matchTemplate(bar, bound1, cv2.TM_CCORR_NORMED)
    _, confidence, _, xy = cv2.minMaxLoc(r)
    if (confidence < 0.5):
        print("Low Confidence")
    rightBoundX = xy[0]
    return leftBoundX, xy[1], rightBoundX, xy[1] + bound0.shape[0]
    # recognize(item[1:3,0:2].copy())


def binify(r):
    return np.where(r > 128, 255, 0).astype(np.uint8)


def main():
    mp.freeze_support()
    a = StockInterface()
    a.activate()
    a.secureForeground()
    a.getOwned()
    time.sleep(1)
    print(a.getCancelable())
    time.sleep(0.5)
    # a.cancelAll()
    # print(a.getOwned())
    # a.do(10001669, 1, 0, 3, 10, 1, 0)
    # a.do(10001701, 0, 0, 1, 0.42, 0, 0.001)
    # a.cancelAll()
    # s = time.time()
    # a.do(600000, 0, 0, 100, 8.17, 0, 1234)
    a.cancelOrder('33014')
    a.cancelOrder('33079')
    time.sleep(5)
    a.external_setContract('600015')
    # s1 = time.time()
    # a.do(10001669, 0, 1, 4, 0.728, 0, 0.001)
    # s2 = time.time()
    # print(s2 - s1, " ", s1 - s)
    return a


if __name__ == '__main__':
    main()
