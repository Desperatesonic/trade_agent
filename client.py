import concurrent
import random
import threading
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from multiprocessing import Queue
from multiprocessing.managers import BaseManager
import multiprocessing as mp
import multiprocessing.dummy as thread

import multiprocessing.connection
import socket
from typing import List
import logging

c_log=logging.getLogger(name="client")
stderr=logging.StreamHandler()
fileout=logging.FileHandler("/data/log/client.log")
fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(fmt)
fileout.setFormatter(formatter)
c_log.addHandler(stderr)
c_log.addHandler(fileout)
c_log.setLevel(logging.INFO)


def SocketClient(address):
    '''
    Return a connection object connected to the socket given by `address`
    '''
    family = multiprocessing.connection.address_type(address)
    with socket.socket( getattr(socket, family) ) as s:
        s.setblocking(True)
        s.connect(address)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return multiprocessing.connection.Connection(s.detach())
multiprocessing.connection.SocketClient=SocketClient
import sys

class RManager(BaseManager): pass


def trans(qin,qout,idx):
    """

    Args:
        qin (Queue):
        qout (Queue): Queue
        idx (int)
    """
    while True:
        try:
            qout.put( [idx, qin.get()] )
            # previously tuple
        except Exception as e:
            c_log.exception(e)
def trans_bc(qin,qout,idx=None):
    """
    Args:
        qin (Queue):
        qout (Queue): Queue
    """
    while True:
        try:
            qout.put(qin.get())
        except Exception as e:
            c_log.exception(e)

from exec_2019 import client_config
# 发送任务的队列
task_queue = [mp.Queue() for _ in range(len(client_config))]
# 接收结果的队列
result_queue = [mp.Queue() for _ in range(len(client_config))]

def get_task_queue(server_id):
    return task_queue[server_id]
def get_result_queue(server_id):
    return result_queue[server_id]

RManager.register('get_task_queue', callable=get_task_queue)
RManager.register('get_result_queue', callable=get_result_queue)

# 封装BaseClient，在从server读写失败时，进行__ext_init__操作，实现重连
class ReconnWorker:
    def __init__(self, server_id, host, port, authkey):
        self.host = host
        self.port = port
        self.authkey = authkey

        self.task = Queue()
        self.res = Queue()

        self.ready = False

        self.ext_res = result_queue[server_id]
        self.ext_task = task_queue[server_id]

        self.manager_starter = threading.Thread(target=self.__manager_init)
        self.manager_starter.start()

    def __manager_init(self):
        manager = RManager(address=(self.host, self.port), authkey=self.authkey)
        while 1:
            print("Start Manager")
            s = manager.get_server()
            s.serve_forever()

            print("!X")
            # 关闭服务器

    def connect(self):
        self.__ext_init__(firstStart=True)
        # 输入、输出内容转发
        self.res_midware = threading.Thread(target=self.res_listener)
        self.task_midware = threading.Thread(target=self.task_listener)
        self.res_midware.start()
        self.task_midware.start()
        self.ready = True

    # firstStart来标记是否曾经初始化，即是否绑定了res_midware、task_midware转发线程
    # 已绑定过的__ext_init__之后就可以认为ready，否则需要等到绑定后才算ready
    def __ext_init__(self, firstStart=False):
        self.ready = False
        worker=None
        try:
            print("Start connecting {}".format(self.host), flush=True)

            print("Wait RemoteInterface init done {}".format(self.host), flush=True)
            _start_time=time.time()
            # 登录，循环获取登录结果，直到登录成功
            while True:
                if time.time()-_start_time > 300:
                    raise TimeoutError
                self.ext_task.put(["secureForeground"])
                self.ext_task.put(["isLogin"])
                r = [None]
                _response_start_time = time.time()
                while r[0] != "isLogin":
                    try:
                        # r = self.ext_res.get(timeout=250)
                        # TODO deamon thread if needed
                        r = self.ext_res.get_nowait()
                        print(self.host, " : ", r, flush=True)
                    except Exception:
                        if time.time()-_response_start_time > 250:
                            raise
                        time.sleep(1)
                if r[1] is True:
                    break
                print(self.host, " : ", r, flush=True)
                time.sleep(1)
        except Exception:
            print(self.host, "Fail\n", flush=True)
            # if worker:
            #     worker.shutdown
            time.sleep(15)
            print(self.host, "Retrying -----\n", traceback.format_exc(chain=False),"\n-----", flush=True)
            self.__ext_init__(firstStart=firstStart)
            return
        print("Init done {}".format(self.host), flush=True)

        if not firstStart:
            self.ready = True
        print(self.host,self.ready)

    # 在从server读写失败时，进行__ext_init__操作，实现重连
    def res_listener(self):  # 接收远端交易界面信息的函数
        while True:
            try:
                r = self.ext_res.get()
            except Exception:
                traceback.print_exc()
                print("res listener restart")
                self.__ext_init__()
                continue
            self.res.put(r)
    # 在从server读写失败时，进行__ext_init__操作，实现重连
    def task_listener(self):
        while True:
            t = self.task.get()
            while True:
                try:
                    self.ext_task.put(t)
                    break
                except Exception:
                    traceback.print_exc()
                    print("task listener restart")
                    self.__ext_init__()


class SingleRemoteInterface:
    @property
    def ready(self):
        return self.recWorker.ready if self.res else False
    # 初始化
    def __init__(self, hpaPack):
        # self.ready=False
        server_id, host, port, authkey = hpaPack
        self.recWorker = ReconnWorker(server_id, host, port, authkey)
        self.task = self.recWorker.task
        self.res = self.recWorker.res

        init_thread = threading.Thread(target=self.__finit__, args=(hpaPack,))
        init_thread.start()
    # 连接server
    def __finit__(self,hpaPack):
        server_id, host, port, authkey = hpaPack
        print("Start init {}".format(host))
        self.recWorker.connect()

    # 开始抓取资金情况
    def startCap(self):
        """
        ["update",{name:float},timestamp]
        ["update",{"净资产":100.01},1234555666.001]
        ["update",{"可用保证金":100.01},1234555666.001]
        :return:
        """
        print("startCap ", time.time())
        self.task.put(["startCap"])
    # 未实现
    def pauseCap(self):
        print("pauseCap ", time.time())
        self.task.put(["pauseCap"])

    # 将窗口置于前台，保障后续操作实现，server端对应操作前已有保障，暂不需要手动调用
    def secureForeground(self):
        self.task.put(["secureForeground"])

    # 买卖指令下发
    def do(self, trade_type,contract, position, net, amt, price, direction,tradeType=0,uid=None):
        """
        将从Queue中得到返回值["do",uid,True,timestamp] 或 ["do",uid,False,timestamp] False代表出现错误

        :param trade_type: [0,1] 0:期权，1：股票,2:期货
        :param contract: int
        :param position: [0,1,2] 0:开仓 1:平仓, 2:平今（上期所需要用来平当天仓位）
        :param net: [0,1] 0:不净仓 1:净仓
        :param amt: int
        :param price: float
        :param direction: [0,1] 0:买入 1:卖出
        :param tradeType: 期货中的交易类型，[0,1,2] 0:投机,1:保值,2套利
        :param uid: 唯一标识符
        :return:
        """
        if not uid:
            uid=time.time()
        print("Now ",time.time())

        print("put do -> ",str(datetime.now()))
        sys.stderr.flush()
        sys.stdout.flush()
        self.task.put(["do", (trade_type,contract, position, net, amt, price, direction,uid,tradeType), time.time()])

    # 持仓情况查询
    def getOwn(self,trade_type):

        #:param trade_type: [0,1] 0:期权，1：股票
        """
        ["own",Dict{代码:{代码:xxx,...}},timestamp]
        ["own",{},123.123]
        ["own",{'10001417': {'市场名称': '上海股票期权', '代码': '10001417', '名称': '50ETF购3月2352A', '类别': '认购', '买卖': '买', '备兑属性': '非备兑', '持仓': '2', '可用': '2', '开仓均价': '0.4259', '最新价': '0.4258', '市值': '8688.02', '估算浮动盈亏': '-2.04', '保证金': '0.', '持仓类别': '权利仓', 'Delta': '2.0000', 'Gamma': '0.0000', 'Rho': '0.0773', 'Theta': '-0.2068', 'Vega': '0.0000', '时间价值': '0.0016', '': ''}},123.123]

        :return:
        """
        self.task.put(["own",trade_type])

    # 可撤单情况查询
    def getCancelable(self,trade_type):
        # :param trade_type: [0,1] 0:期权，1：股票
        """
        ["cancelable",Dict{合约代码:[{x},{y},{z}]},timestamp]
        ["cancelable",{'10001417': [{'委托时间': '14:39:27', '市场名称': '上海股票期权', '委托号': '1', '合约代码': '10001417', '合约名称': '50ETF购3月2352A', '买卖': '买', '开平': '开仓', '委托价格': '0.3995', '委手': '1', '成手': '0', '成交均价': '0.', '状态信息': '已申报', '合约类别': '认购', '期权备兑标志': '非备兑', '备注': '', '': ''},]},123456.123]

        :return:
        """
        self.task.put(["cancelable",trade_type])

    # 输入证券代码
    def setContract(self, trade_type,contract):
        self.task.put(["set_contract",trade_type, contract])

    # 撤销全部可撤销委托
    def cancelAll(self,trade_type):
        self.task.put(["cancelAll",trade_type])

    # 撤销指定委托
    def cancelOrder(self, trade_type, order_id):
        self.task.put(["cancelOrder", trade_type, order_id])

    # while 1:
    #     print("Server ", time.time())
    #     task.put(time.time())
    #     time.sleep(1)
    #     print("---")

# 封装SingleRemoteInterface，实现同时连接多个server
class RemoteInterface(SingleRemoteInterface):
    def __init__(self, hpaList, *args):
        """

        Args:
            hpaList (list): List of (host,port,authkey)

            返回值 (机器号,原返回值)
        """
        # self.task = Queue()
        self.res = Queue()
        # 统一输入参数格式
        if args:
            hpaList = [(hpaList, *args)]  # BC

        # 根据多组参数实现多个client实例
        self.servers = []
        with ThreadPoolExecutor(max_workers=len(hpaList)) as executor:
            res = executor.map(SingleRemoteInterface, hpaList)
        # print(res)
        self.servers = list(res)

        self.trans_midware = []

        # 多服务器和单服务器输出结果格式不同，单服务器直接输出，多服务器格式为[idx, qin.get()]
        if args:
            trans_func = trans_bc  # BC 当输入单个remote interface时使用的中转信息函数
        else:
            trans_func = trans  # 当输入多个remote interface时使用的中转信息函数

        not_ready = self.servers.copy()  # 浅拷贝list
        start_time = time.time()
        while time.time()-start_time < 300:  # 5分钟的时间作初始化
            for idx, each in zip(range(len(hpaList)), self.servers):
                if each not in not_ready or not each.ready:
                    continue
                # 转发各个服务器的结果到统一出口self.res
                _c = threading.Thread(target=trans_func, args=(each.res, self.res, idx))
                self.trans_midware.append(_c)
                _c.start()
                not_ready.remove(each)
            if not len(not_ready):
                print("All init complete")
                break
            time.sleep(1)
        if len(not_ready):
            print("Not Ready List: ", not_ready)
        print("List init Done")

    def ready(self, i=0):
        """

        Args:
            i:

        Returns:
            is i th server ready
        """
        return self.servers[i].ready

    def readyList(self):
        return [x.ready for x in self.servers]

    # a.setContract(123) -> a.server[1].setContract(123)
    def startCap(self, i=0):
        self.servers[i].startCap()

    def pauseCap(self, i=0):
        self.servers[i].pauseCap()

    def secureForeground(self, i=0):
        self.servers[i].secureForeground()

    def do(self, trade_type, contract, position, net, amt, price, direction,uid=None, i=0):
        c_log.info(f"do {time.time()},trade_type:{trade_type},contract:{contract},position:{position},net:{net},amt:{amt},price:{price},direction:{direction},uid:{uid},account_id:{i}")
        self.servers[i].do(trade_type, contract, position, net, amt, price, direction, uid=uid)

    def getOwn(self,trade_type, i=0):
        c_log.info(f"getOwn {time.time()},trade_type:{trade_type},account_id:{i}")
        self.servers[i].getOwn(trade_type)

    def getCancelable(self,trade_type, i=0):
        c_log.info(f"getCancelable {time.time()},trade_type:{trade_type},account_id:{i}")
        self.servers[i].getCancelable(trade_type)

    def setContract(self, trade_type,contract, i=0):
        self.servers[i].setContract(trade_type,contract)

    def cancelAll(self,trade_type, i=0):
        c_log.info(f"cancelAll {time.time()},trade_type:{trade_type},account_id:{i}")
        self.servers[i].cancelAll(trade_type)

    def cancelOrder(self,trade_type, order_id, i=0):
        c_log.info(f"cancelOrder {time.time()},trade_type:{trade_type},order_id:{order_id},account_id:{i}")
        self.servers[i].cancelOrder(trade_type, order_id)



if __name__ == "__main__":
    # host = '129.211.99.232'
    host = ''
    port = 0
    # authkey = b'\xb20j\xd9\xf8P\xc3\x88zw]6\x078\xd8\xcb5Gw\xb3U\xd3"#aC\xdc\xdb\xce\xa5\x12\t\x80\xc9\t'
    with open('password.txt', 'rb') as f:
        authkey = f.read()

    # 获取队列
    print("Got")
    a = RemoteInterface([0, host, port, authkey])
    # time.sleep(5)
    # a.getOwn(2)
    # time.sleep(0.5)
    # a.getCancelable(2)
    time.sleep(5)
    # # a.cancelAll(2)
    # time.sleep(0.5)
    # a.setContract(2, 'cl2108')
    # order_count_sum = -1
    # while order_count_sum >0:
    #     time.sleep(5)
    #     order_count_sum -= 1
    #     order_count=5
    #     while order_count>0:
    #         trade_type=2
    #         contract_set={0:'IF2201',1:'IH2201',2:'IC2201'}
    #         contract= contract_set[order_count%3]
    #         position= random.randint(0,1)
    #         net=random.randint(0,1)
    #
    #         direction=random.randint(0,1)
    #         accountid=0
    #         countcallback=0
    #         price = ("%.1f") % random.uniform(1.0, 4000.0)
    #         amt = str(random.randint(1, 10))
    #         a.do(trade_type, contract, position, net, amt, price, direction, str(accountid)+"-"+str(countcallback), accountid)
    #         order_count -= 1

    # countcallback += 1
    # contract = 'IH2201'
    # price=2960.0
    # a.do(trade_type, contract, position, net, amt, price, direction, str(accountid) + "-" + str(countcallback),
    #      accountid)

    # time.sleep(5)
    a.getCancelable(1)
    # time.sleep(0.5)
    a.getOwn(1)
    # time.sleep(0.5)
    # a.cancelAll(2)
    # time.sleep(0.5)
    # a.setContract(0,10001701)
    # time.sleep(5)
    # a.do(2,'cl2108',0,0,1,1,0,1324)
    # a.getCancelable(2)
    time.sleep(1)
    # a.do(10001800, 0, 0, 1, 0.9627, 1)
    # a.do(0,10001800, 0, 0, 1, 0.9627, 1)
    # a.do(1,10001800, 0, 0, 1, 0.9627, 1)
    print("Do")
    # a.secureForeground()
    # print("Sent")
    a.startCap()
    def print_result():
        while 1:
            result = a.res.get()
            # if "update" in result:
            #     continue
            print(result, " ", time.time())
    thread.Process(target=print_result).start()
    isPause=False
    # while 1:
    #     time.sleep(60)
    #     isPause = not isPause
    #     if isPause:
    #         a.startCap()
    #     else:
    #         a.pauseCap()
    while 1:
        try:
            order = input("请输入命令(多个订单以分号隔开):\n")
            time.sleep(1)
            print(time.time(),":",order,"\n")
            order = order.replace(" ","")
            # 提取命令类型，并格式化命令
            order_type = order.split(";")[0]
            order = order.replace(order_type + ";","")

            if order_type == "do":
                for each_order in order.split(";"):
                    each = each_order.split(",")
                    trade_type = int(each[0])
                    contract = each[1].replace("'","")
                    position = int(each[2])
                    net = int(each[3])
                    amt = each[4].replace("'","")
                    price = each[5].replace("'","")
                    direction = int(each[6])
                    uid = each[7].replace("'","")
                    account_id = int(each[8])
                    a.do(trade_type, contract, position, net, amt, price, direction, uid, account_id )
            elif order_type == 'cancelOrder':
                for each_order in order.split(";"):
                    each = each_order.split(",")
                    trade_type = int(each[0])
                    order_id = each[1]
                    account_id = int(each[2])
                    a.cancelOrder(trade_type, order_id, account_id)
            else:
                print(f"unknown order type!{order_type}:{order}")
        except Exception as e:
            print(e)

