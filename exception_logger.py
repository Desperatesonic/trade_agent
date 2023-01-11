import datetime
import functools
import logging




def create_logger(*args):
    '''
        指定保存日志的文件路径，日志级别，以及调用文件
        将日志存入到指定的文件中
    '''
    if(len(args)<2):
        args=["commonLog","./common.log"]
    # 创建一个logger
    logger = logging.getLogger(args[0]+".log")

    # 清空logger
    for each_handler in logger.handlers:
        # print(f"remove handler : {each_handler}")
        logger.removeHandler(each_handler)

    logger.setLevel(logging.DEBUG)

    # fh = logging.FileHandler(args[1], 'a')  # 追加模式  这个是python2的
    fh = logging.FileHandler(args[1], 'a', encoding='utf-8')  # 这个是python3的
    fh.setLevel(logging.INFO)

    # 再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # 定义handler的输出格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(filename)s->%(funcName)s line:%(lineno)d [%(levelname)s]%(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(fh)
    logger.addHandler(ch)

    # 添加下面一句，在记录日志之后移除句柄
    # logger.removeHandler(ch)
    # logger.removeHandler(fh)
    # 关闭打开的文件
    fh.close()
    ch.close()
    return logger

def create_logger_fileonly(*args):
    '''
        指定保存日志的文件路径，日志级别，以及调用文件
        将日志存入到指定的文件中
    '''
    if(len(args)<2):
        args=["commonLog","./common.log"]
    # 创建一个logger
    logger = logging.getLogger(args[0]+".log")

    # 清空logger
    for each_handler in logger.handlers:
        # print(f"remove handler : {each_handler}")
        logger.removeHandler(each_handler)

    logger.setLevel(logging.DEBUG)

    # fh = logging.FileHandler(args[1], 'a')  # 追加模式  这个是python2的
    fh = logging.FileHandler(args[1], 'w', encoding='utf-8')  # 这个是python3的
    fh.setLevel(logging.INFO)

    # 定义handler的输出格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(filename)s->%(funcName)s line:%(lineno)d [%(levelname)s]%(message)s')
    fh.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(fh)

    # 添加下面一句，在记录日志之后移除句柄
    # logger.removeHandler(ch)
    # logger.removeHandler(fh)
    # 关闭打开的文件
    fh.close()
    return logger

def create_logger_fileonly_append(logger_name='commonLog', filename='./common.log', append=False):
    '''
        指定保存日志的文件路径，日志级别，以及调用文件
        将日志存入到指定的文件中
    '''
    args = [logger_name, filename]
    # 创建一个logger
    logger = logging.getLogger(args[0]+".log")

    # 清空logger
    for each_handler in logger.handlers:
        logger.removeHandler(each_handler)

    logger.setLevel(logging.DEBUG)

    write_mode = 'a' if append else 'w'

    # fh = logging.FileHandler(args[1], 'a')  # 追加模式  这个是python2的
    fh = logging.FileHandler(args[1], write_mode, encoding='utf-8')  # 这个是python3的
    fh.setLevel(logging.INFO)

    # 定义handler的输出格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(filename)s->%(funcName)s line:%(lineno)d [%(levelname)s]%(message)s')
    fh.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(fh)

    # 关闭打开的文件
    fh.close()
    return logger

def exception(l):
        def decorator(function):
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                try:
                    return function(*args, **kwargs)
                except Exception as e:
                    l.exception(e)
            return wrapper
        return decorator

