import multiprocessing
import queue
import re
import time,datetime
import traceback
from functools import partial
from multiprocessing import Process, Queue
from queue import Empty
from multiprocessing.managers import BaseManager
import multiprocessing as mp
import multiprocessing.dummy as thread

from StockInterface import StockInterface
from exception_logger import *
from FutureInterface import FutureInterface, getBound_future
from mail_server import send_mail_with_file

l = create_logger()
commandGot=create_logger("command","./command.log")
resultSend=create_logger_fileonly_append("result", "./result-"+str(datetime.date.today())+".log", True)
dataSend=create_logger_fileonly_append("fundData", "./fundData-"+str(datetime.date.today())+".log", True)
from tesseract import Tesseract
from f import TradeInterface, getScreenShot, getBound, save_as_img, exception, checkPopWindowByHdl, getScreenShotByHdl
import os

# 期货交易程序和股票期权交易程序切换开关
isFuture=True

# debug开关
debugFlag = False

# # 发送任务的队列
# task_queue = mp.Queue()
# # 接收结果的队列
# result_queue = mp.Queue()
#
#
class RManager(BaseManager): pass

def is_auction():
    if datetime.datetime.now().hour == 9 and datetime.datetime.now().minute < 30 and datetime.datetime.now().minute >= 25:
        return True
    if datetime.datetime.now().hour == 14  and datetime.datetime.now().minute > 57:
        return True
    else:
        return False

# 初始化界面模拟类、接收并分发client传来的命令
class InterfaceWorker(Process):
    def __init__(self, q, p, internal) :
        self.q: Queue = q
        self.p: Queue = p
        self.internal: Queue = internal
        super(InterfaceWorker, self).__init__()

    # 根据标志分别启动期货、期权（股票）界面模拟类，在各自类中执行具体命令
    def run(self):
        if not isFuture:
            self.option()
        else:
            self.future()

    def option(self):
        pool = thread.Pool(1)
        # 初始化并切换到期权界面
        t = TradeInterface()
        print("TradeInterface init done")
        t.changeToStock()
        # 初始化并切换到股票界面
        stock = StockInterface()
        print("StockInterface init done")
        # stock.chengeToOption()
        # 向界面类下发截屏参数
        self.internal.put(t.getScreenshotParas())
        self.internal.put(stock.getScreenshotParas())
        print("Screenshot set")
        # 向界面类下发配置完成提示
        self.p.put(["Set"])
        print("-Ready-")
        commandGot.info("-Ready-")
        while 1:
            print("Waiting Command")
            # n = self.q.get()
            try:
                # 尝试接收命令
                # 超时1s，设置超时可以定期切换股票、期权界面
                n = self.q.get(True, 1)
            except:
                # 超时后切换股票、期权界面
                # t.changeTpye()
                continue
            # self.p.put((n,time.time()))
            commandGot.info(n)
            t.changeToStock()

            # 存在弹出窗口，不进行后续操作
            now=time.time()
            if checkPopWindow(t.mainWindow,f"Option.{now}.bmp"):
                send_mail_with_file("checkPopWindow fail",filename=f"Option.{now}.bmp")
                continue
            if checkPopWindow(stock.mainWindow,f"Stock.{time.time()}.bmp"):
                send_mail_with_file("checkPopWindow fail", filename=f"Stock.{now}.bmp")
                continue

            timestamp = n[1]
            n = n[0]
            if n[0] == "do":
                # pool.apply_async(t.do, args=n[1])
                print("->get do", str(datetime.datetime.now()))
                # 收到2s前的命令，直接返回false
                # TODO 这里需要根据实际下单速度与下单数量来调整阈值，连续交易时段3S一次depth
                # 集合竞价阶段门限宽一点，其他时间先按3s处理
                timeout_config=240 if is_auction() else 3
                if time.time() - timestamp > timeout_config:
                    commandGot.warning("late answer, pass")
                    print("late answer, pass")
                    self.p.put(["do", (n[1][-2], False), time.time()])
                    continue
                #     判断类型为股票还是期权，根据类型切换界面，并传递参数
                if n[1][0] == 0:
                    t.changeToOption()
                    res = t.do(*n[1][1:])
                    if not res[0][1]:
                        commandGot.warning("fail")
                    self.p.put(["do", *res])
                    # t.do(*n[1])
                elif n[1][0] == 1:
                    # stock.changeToStock()
                    res = stock.do(*n[1][1:])
                    if not res[0][1]:
                        commandGot.warning("fail")
                    self.p.put(["do", *res])
                    # t.do(*n[1])
                else:
                    commandGot.warning("wrong type:%s", n[0][1][0])
                    print("late answer, pass")
            # 根据类型查询对应持仓数据
            elif n[0] == "own":
                if n[1] == 0:
                    t.changeToOption()
                    pool.apply_async(self.p.put, args=(["own", *t.getOwned()],))
                    print("->get Check own ", str(datetime.datetime.now()))
                    # self.p.put(["own",*t.getOwned()])
                elif n[1] == 1:
                    stock.changeToStock()
                    try:
                        pool.apply_async(self.p.put, args=(["own", *stock.getOwned()],))
                        print("->get Check own ", str(datetime.datetime.now()))
                    except:
                        traceback.print_exc()
                        print("->get Check own fail", str(datetime.datetime.now()))
                    # self.p.put(["own",*t.getOwned()])
                else:
                    commandGot.warning("wrong type:%s", n[1])
                    print("late answer, pass")
            # 根据类型查询对应可撤单数据
            elif n[0] == "cancelable":
                if n[1] == 0:
                    t.changeToOption()
                    pool.apply_async(self.p.put, args=(["cancelable", *t.getCancelable()],))
                    print("->get Check cancelable ", str(datetime.datetime.now()))
                    # self.p.put(["cancelable",*t.getCancelable()])
                elif n[1] == 1:
                    stock.changeToStock()
                    try:
                        pool.apply_async(self.p.put, args=(["cancelable", *stock.getCancelable()],))
                        print("->get Check cancelable ", str(datetime.datetime.now()))
                    except:
                        traceback.print_exc()
                        print("->get Check cancelable fail", str(datetime.datetime.now()))
                    # self.p.put(["cancelable",*t.getCancelable()])
                else:
                    commandGot.warning("wrong type:%s", n[1])
                    print("late answer, pass")
            # 设置合约
            elif n[0] == "set_contract":
                if n[1] == 0:
                    t.changeToOption()
                    pool.apply_async(t.external_setContract, args=(n[2],))
                    print("->get Set contract ", str(datetime.datetime.now()))
                    # t.external_setContract(n[1])
                elif n[1] == 1:
                    stock.changeToStock()
                    pool.apply_async(stock.external_setContract, args=(n[2],))
                    print("->get Set contract ", str(datetime.datetime.now()))
                    # t.external_setContract(n[1])
                else:
                    commandGot.warning("wrong type:%s", n[1])
                    print("late answer, pass")
            # 撤销全部委托
            elif n[0] == "cancelAll":
                if n[1] == 0:
                    t.changeToOption()
                    pool.apply_async(t.cancelAll)
                    print("->get Cancel", str(datetime.datetime.now()))
                    # t.cancelAll()
                elif n[1] == 1:
                    stock.changeToStock()
                    pool.apply_async(stock.cancelAll)
                    print("->get Cancel", str(datetime.datetime.now()))
                    # t.cancelAll()
                else:
                    commandGot.warning("wrong type:%s", n[1])
                    print("late answer, pass")
            # 撤销指定委托
            elif n[0] == "cancelOrder":
                if n[1] == 1:
                    stock.changeToStock()
                    try:
                        print("->get CancelOrder",n[2], str(datetime.datetime.now()))
                        stock.cancelOrder(n[2])
                        pool.apply_async(self.p.put(["CancelOrder", (n[2], True), time.time()]))
                    except Exception as e:
                        print("cancel order fail,exception:",e)
                        traceback.print_exc()
                        pool.apply_async(self.p.put(["CancelOrder", (n[2], False), time.time()]))
                    # t.cancelAll()
                else:
                    commandGot.warning("wrong type:%s", n[1])
                    print("late answer, pass")
            # 开始截屏
            elif n[0] == "startCap":
                self.internal.put("go")
            elif n[0] == "shutdown":
                self.internal.put("shutdown")
            # 处理登录消息
            elif n[0] == "isLogin":
                self.p.put(["isLogin", True])
                pool.apply_async(self.p.put, args=(["isLogin", True],))

            elif n[0] == "pauseCap":
                self.internal.put("pauseCap")
                pool.apply_async(self.p.put, args=(["pauseCap", True],))

            else:
                pass
                # TODO log it

    def future(self):
        pool = thread.Pool(1)

        future = FutureInterface()
        print("FutureInterface init done")

        self.internal.put(future.getScreenshotParas())
        print("Screenshot set")
        self.p.put(["Set"])
        print("-Ready-")
        commandGot.info("-Ready-")
        while 1:
            print("Waiting Command")
            # n = self.q.get()
            try:
                n = self.q.get(True, 60)
            except:
                future.refresh()
                continue
            # self.p.put((n,time.time()))
            commandGot.info(n)

            # 存在弹出窗口，不进行后续操作
            now=time.time()
            if checkPopWindow(future.mainWindow, f"Future.{now}.bmp"):
                send_mail_with_file("checkPopWindow fail", filename=f"Future.{now}.bmp")
                continue

            timestamp = n[1]
            n = n[0]
            if n[0] == "do":
                # pool.apply_async(t.do, args=n[1])
                print("->get do", str(datetime.datetime.now()))
                # start_time = datetime.datetime.now()
                if time.time() - timestamp > 1:
                    commandGot.warning("late answer, pass")
                    print("late answer, pass")
                    self.p.put(["do", (n[1][-2], False), time.time()])
                    continue
                if n[1][0] == 2:
                    res = future.do(*n[1][1:])
                    if not res[0][1]:
                        commandGot.warning("fail")
                    self.p.put(["do", *res])
                    # t.do(*n[1])
                else:
                    commandGot.warning("wrong type for future:%s", n[0][1][0])
                    print("late answer, pass")
                # print(f"耗时:{datetime.datetime.now()-start_time},order:{n[1][1:]}")

            elif n[0] == "own":
                if n[1] == 2:
                    pool.apply_async(self.p.put, args=(["own", *future.getOwned()],))
                    print("->get Check own ", str(datetime.datetime.now()))
                    # self.p.put(["own",*t.getOwned()])
                else:
                    commandGot.warning("wrong type for future:%s", n[1])
                    print("late answer, pass")

            elif n[0] == "cancelable":
                if n[1] == 2:
                    pool.apply_async(self.p.put, args=(["cancelable", *future.getCancelable()],))
                    print("->get Check cancelable ", str(datetime.datetime.now()))
                    # self.p.put(["cancelable",*t.getCancelable()])
                else:
                    commandGot.warning("wrong type for future:%s", n[1])
                    print("late answer, pass")

            elif n[0] == "set_contract":
                if n[1] == 2:
                    pool.apply_async(future.external_setContract, args=(n[2],))
                    print("->get Set contract ", str(datetime.datetime.now()))
                    # t.external_setContract(n[1])
                else:
                    commandGot.warning("wrong type for future:%s", n[1])
                    print("late answer, pass")

            elif n[0] == "cancelAll":
                if n[1] == 2:
                    pool.apply_async(future.cancelAll)
                    print("->get Cancel", str(datetime.datetime.now()))
                    # t.cancelAll()
                else:
                    commandGot.warning("wrong type for future:%s", n[1])
                    print("late answer, pass")

            elif n[0] == "startCap":
                self.internal.put("go")
            elif n[0] == "shutdown":
                self.internal.put("shutdown")
            elif n[0] == "isLogin":
                self.p.put(["isLogin", True])
                pool.apply_async(self.p.put, args=(["isLogin", True],))

            elif n[0] == "pauseCap":
                self.internal.put("pauseCap")
                pool.apply_async(self.p.put, args=(["pauseCap", True],))
            else:
                pass
                # TODO log it

# 判断当前是否有弹出窗口遮挡
def checkPopWindow(hdl,name=f"Stock.{time.time()}.bmp"):
    pop_window=checkPopWindowByHdl(hdl,partial(getScreenShotByHdl,name=name))
    if pop_window is not None:
        print(f"当前存在弹出窗口{pop_window}，请检查")
        return True
    return False


# 初始化截屏功能
def init_tess():
    try:
        r = Tesseract()
    except Exception as e:
        print(e)
        r = Tesseract(lib_path=f"{os.getcwd()}/libtesseract3052")
    return r

# 命令转发类
class ResendWorker(Process):
    def __init__(self,q,p):
        self.q=q
        self.p=p
        self.force_exit_flag = False
        super(ResendWorker, self).__init__()
    def force_exit(self):
        self.force_exit_flag =True
    # @exception(l)
    def run(self):
        while 1:
            if self.force_exit_flag:
                break
            try:
                payload = self.q.get(True, 60)
                commandGot.info("Got command:"+str(payload))
                self.p.put((payload, time.time()))
            except Empty:
                continue
            except:
                break
# 数据转发类
class DataResendWorker(Process):
    def __init__(self,q,p):
        self.q=q
        self.p=p
        self.force_exit_flag = False
        super(DataResendWorker, self).__init__()
    def force_exit(self):
        self.force_exit_flag =True
    # @exception(l)
    def run(self):
        while 1:
            if self.force_exit_flag:
                break
            try:
                payload = self.q.get()
                if "update" in payload:
                    dataSend.info(payload)
                else:
                    resultSend.info(payload)
                self.p.put(payload)
            except:
                break

# 定期查询资金类
class ScheduleWorker(Process):
    def __init__(self, q, p):
        self.q: Queue = q
        self.p: Queue = p
        super(ScheduleWorker, self).__init__()

    @exception(l)
    def run(self):
        self.getInfo()

    # 根据不同类型查询对应资金
    @exception(l)
    def getInfo(self):
        if not isFuture:
            self.getOption()
        else:
            self.getFuture()

    def getOption(self):
        # 调用初始化Tesseract
        t = init_tess()
        # 接收两次，分别接收期权、股票截屏参数
        rec_dict_option: dict = self.q.get()
        rec_dict_stock: dict = self.q.get()
        print("Got Screenshot parameters")
        # 接收"set"关键字，确认参数发送完毕并启动
        self.q.get()
        print("Screenshot Start")
        "Start to send"


        # thread_list = []
        # for key, item in rec_dict.items():
        #     thread_list.append(thread.Process(target=captureAndRecognize,
        #                                       args=(t, self.p, lock, key, item))
        #                        )
        # for each in thread_list:
        #     each.start()
        isPause = False

        while 1:
            try:
                task = self.q.get(True, 1)
                if task == 'pauseCap':
                    isPause = True
                elif task == 'go':
                    isPause = False
            except:
                pass
            if isPause:
                continue
            try:
                #尝试获取期权相关截图信息
                barPara = rec_dict_option["bar"]
                bound0 = getScreenShot(*rec_dict_option["净资产"])
                bound1 = getScreenShot(*rec_dict_option["可用保证金"])
                bound2 = getScreenShot(*rec_dict_option["估算浮盈"])

                barImg = getScreenShot(*barPara)
                _s: str = t.recongnize(barImg)
                if '保证金' in _s:
                    v01 = getBound(barImg, bound0, bound1)
                    _start_time = time.time()
                    _s: str = t.recongnize(barImg[v01[1]:v01[3], v01[0]:v01[2], :].copy())
                    _s = _s.strip()
                    # s = _s.replace(" ", ".")
                    s=re.sub('[ .]+','.',_s).replace("'","")
                    self.p.put(["update", {"净资产": float(s)}, _start_time])
                    print("净资产:", s)

                    v12 = getBound(barImg, bound1, bound2)
                    _s: str = t.recongnize(barImg[v12[1]:v12[3], v12[0]:v12[2], :].copy())
                    _s = _s.strip()
                    # s = _s.replace(" ", ".")
                    s = re.sub('[ .]+', '.', _s).replace("'","")
                    self.p.put(["update", {"可用保证金": float(s)}, _start_time])
                    print("可用保证金:", s)
                # else:
                #     print("没找到保证金:",_s)


                # 尝试获取期权相关截图参数
                # 后续会按照给定的这几个参数分别进行截图、并对比判断出截图的差异部分，作为图像识别的输入
                barPara = rec_dict_stock["bar"]
                barImg = getScreenShot(*barPara)
                bound0 = getScreenShot(*rec_dict_stock["总资产"])
                bound1 = getScreenShot(*rec_dict_stock["可用资金"])
                bound2 = getScreenShot(*rec_dict_stock["浮动盈亏"])
                # 通过Tesseract识别对应资金数据
                _s: str = t.recongnize(barImg)
                if '可用资金' in _s:
                    # 通过对比截图，获取数据所在部分
                    v01 = getBound(barImg, bound0, bound1)
                    _start_time = time.time()
                    _s: str = t.recongnize(barImg[v01[1]:v01[3], v01[0]:v01[2], :].copy())
                    # 去除空格等影响数字转换的符号
                    _s = _s.strip()
                    # s = _s.replace(" ", ".")
                    s = re.sub('[ .]+', '.', _s).replace("'","")
                    self.p.put(["update", {"总资产": float(s)}, _start_time])
                    print("总资产:", s)

                    v12 = getBound(barImg, bound1, bound2)
                    _s: str = t.recongnize(barImg[v12[1]:v12[3], v12[0]:v12[2], :].copy())
                    _s = _s.strip()
                    # s = _s.replace(" ", ".")
                    s = re.sub('[ .]+', '.', _s).replace("'","")
                    self.p.put(["update", {"可用资金": float(s)}, _start_time])
                    print("可用资金:", s)
                # else:
                #     print("没找到资金:",_s)

            except Exception as e:
                l.exception(e)
                # 保存未能识别截图
                save_as_img(barImg, str(time.time()) + ".fail.screenshot.bmp")
            time.sleep(3)

    def getFuture(self):
        t = init_tess()
        rec_dict_future: dict = self.q.get()
        print("Got Screenshot parameters")
        self.q.get()
        print("Screenshot Start")
        "Start to send"

        isPause = False

        while 1:
            try:
                task = self.q.get(True, 1)
                if task == 'pauseCap':
                    isPause = True
                elif task == 'go':
                    isPause = False
            except:
                pass
            if isPause:
                continue

            try:
                # 尝试获取期货相关截图信息
                # 与期权不同的是，因为软件布局不一样，这里直接截取数据所在位置，直接进行识别
                barPara = rec_dict_future["bar"]
                bound0 = getScreenShot(*rec_dict_future["当前权益"])
                bound1 = getScreenShot(*rec_dict_future["权益变化"])
                bound2 = getScreenShot(*rec_dict_future["可用资金"])
                bound3 = getScreenShot(*rec_dict_future["风险度"])

                barImg = getScreenShot(*barPara)
                # _s: str = t.recongnize(barImg)
                # v01 = getBound_future(barImg, bound0, bound1)
                _start_time = time.time()
                _s: str = t.recongnize_num(bound0)
                _s = _s.strip().replace("'","").replace("(","").replace(")","").replace(",","")
                # s = _s.replace(" ", ".")
                s = re.sub('[ .]+', '.', _s)
                self.p.put(["update", {"当前权益": float(s)}, _start_time])
                print("当前权益:", s)

                # v12 = getBound_future(barImg, bound2, bound3)
                _s: str = t.recongnize_num(bound2)
                _s = _s.strip().replace("'","").replace("(","").replace(")","").replace(",","")
                # s = _s.replace(" ", ".")
                s = re.sub('[ .]+', '.', _s)
                self.p.put(["update", {"可用资金": float(s)}, _start_time])
                print("可用资金:", s)

            except Exception as e:
                l.exception(e)
                save_as_img(barImg, str(time.time()) + ".fail.screenshot.bmp")
            time.sleep(3)

    def getStock(self):
        t = init_tess()
        rec_dict: dict = self.q.get()
        print("Got Screenshot parameters")
        self.q.get()
        print("Screenshot Start")
        "Start to send"
        barPara = rec_dict["bar"]

        bound0 = getScreenShot(*rec_dict["总资产"])
        bound1 = getScreenShot(*rec_dict["可用资金"])
        bound2 = getScreenShot(*rec_dict["浮动盈亏"])

        # thread_list = []
        # for key, item in rec_dict.items():
        #     thread_list.append(thread.Process(target=captureAndRecognize,
        #                                       args=(t, self.p, lock, key, item))
        #                        )
        # for each in thread_list:
        #     each.start()
        while 1:
            try:
                # FLAG
                stock = False

                barImg = getScreenShot(*barPara)
                _s: str = t.recongnize(barImg)
                if '资金' in _s:
                    stock = True
                else:
                    continue
                v01 = getBound(barImg, bound0, bound1)
                _start_time = time.time()
                _s: str = t.recongnize(barImg[v01[1]:v01[3], v01[0]:v01[2], :].copy())
                _s = _s.strip()
                s = _s.replace(" ", ".").replace("'","")
                self.p.put(["update", {"总资产": float(s)}, _start_time])
                print("总资产:", s)

                v12 = getBound(barImg, bound1, bound2)
                _s: str = t.recongnize(barImg[v12[1]:v12[3], v12[0]:v12[2], :].copy())
                _s = _s.strip()
                s = _s.replace(" ", ".").replace("'","")
                self.p.put(["update", {"可用资金": float(s)}, _start_time])
                print("可用资金:", s)
            except Exception as e:
                l.exception(e)
                save_as_img(barImg, str(time.time()) + ".fail.screenshot.bmp")
            time.sleep(3)


@exception(l)
def captureAndRecognize(t: Tesseract, queue: Queue, lock: mp.Lock, name: str, para: tuple):
    while 1:
        lock.acquire()
        try:
            img = getScreenShot(*para)
            _start_time = time.time()
            _s: str = t.recongnize(img)
            _s=_s.strip()
            s = _s.replace(" ", ".")
            queue.put(["update", {name: float(s)}, _start_time])
        except AssertionError:
            pass
        except AttributeError:
            print("Maximize")
        except Exception as e:
            print('"',_s,'"')
            raise
            # TODO log it
            pass
        finally:
            lock.release()
        time.sleep(0.9)

def start_worker(host, port, authkey):
    # 由于这个BaseManager只从网络上获取queue，所以注册时只提供名字
    from multiprocessing.managers import BaseProxy
    if (host, port) in BaseProxy._address_to_local:
        try:
            del BaseProxy._address_to_local[(host, port)][0].connection
            # del BaseProxy._address_to_local[(host, port)]
        except Exception as e:
            traceback.print_exc()
            with open("a_multiprocess_error.log","w") as f:
                f.write(traceback.format_exc())
        # del BaseProxy._address_to_local[(host, port)][0].connection
        # Remove the fking cache

    # 注册关键字，从而获取对应输入输出队列
    BaseManager.register('get_task_queue')
    BaseManager.register('get_result_queue')
    print('Connect to server %s' % host)
    # 注意，端口port和验证码authkey必须和manager服务器设置的完全一致
    worker = RManager(address=(host, port), authkey=authkey)
    # 连接服务器
    worker.connect()
    return worker

if __name__ == "__main__":
    mp.freeze_support()

    host = ''
    port = 0
    with open('password.txt', 'rb') as f:
        authkey = f.read()
    Server_id = 0
    # t,stock=init_interface()

    internalQueue = Queue()
    resendQueue = Queue()
    dataResendQueue =Queue()

    iw = InterfaceWorker(resendQueue, dataResendQueue, internalQueue)
    print("Start Server")
    sw = ScheduleWorker(internalQueue, dataResendQueue)
    iw.start()
    sw.start()
    rw=None
    dw=None
    while 1:
        try:
            worker = start_worker(host, port, authkey)
            # 发送任务的队列
            task_queue = worker.get_task_queue(Server_id)
            # 接收结果的队列
            result_queue = worker.get_result_queue(Server_id)
            rw = ResendWorker(task_queue, resendQueue)
            dw = DataResendWorker(dataResendQueue,result_queue)
            rw.start()
            dw.start()
            while rw.is_alive() and dw.is_alive():
                time.sleep(1)
        except Exception as e:
            print(f"Reconnecting after 10s .... {host}:{port}")
            time.sleep(10)
            continue
        finally:
            # 不能直接调用 terminate()
            # 参考 https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.terminate
            if rw:rw.force_exit()
            if dw:dw.force_exit()


    # # 启动manager服务器
    # # 设置host,绑定端口port，设置验证码为authkey
    # manager = RManager(address=(host, port), authkey=authkey)
    # while 1:
    #     print("Start Server")
    #     sw = ScheduleWorker(internalQueue, result_queue)
    #     sw.start()
    #
    #     # 启动manager服务器
    #     #manager.start()
    #     #while manager._state.value != 2:
    #     #    time.sleep(5)
    #     s = manager.get_server()
    #     s.serve_forever()
    #
    #     print("!X")
    #     sw.terminate()
    #     # 关闭服务器
