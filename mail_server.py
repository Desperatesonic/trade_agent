# -*- coding: utf-8 -*-
# @Time         : 2021/12/10 9:26
# @Author       : ydl
# @File         : mail_server.py
# @Description  : 发送邮件相关函数


import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from_address = ''  # 发件人邮箱账号
password_filrdir = ''
with open(password_filrdir, 'r') as filex:
    password = filex.read()
to_address = ''  # 收件人邮箱账号，我这边发送给自己

# 测试函数
def mail():
    ret = True
    try:
        msg = MIMEText('填写邮件内容', 'plain', 'utf-8')
        msg['From'] = formataddr(("FromRunoob", from_address))  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        msg['To'] = formataddr(("FK", to_address))  # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject'] = "菜鸟教程发送邮件测试"  # 邮件的主题，也可以说是标题

        # server=smtplib.SMTP("smtp.126.com", 25)
        server = smtplib.SMTP_SSL("smtp.163.com", 465)  # 发件人邮箱中的SMTP服务器，端口是25
        server.login(from_address, password)  # 括号中对应的是发件人邮箱账号、邮箱密码
        server.sendmail(from_address, [to_address, ], msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()  # 关闭连接
    except Exception as e:  # 如果 try 中的语句没有执行，则会执行下面的 ret=False
        ret = False
    return ret

# 初始化server
def init_mail_server():
    # server = smtplib.SMTP("smtp.126.com", 25)  # 发件人邮箱中的SMTP服务器，端口是465
    server = smtplib.SMTP_SSL("smtp.163.com", 465)
    server.login(from_address, password)            # 括号中对应的是发件人邮箱账号、邮箱授权码
    return server

# 发送纯文本邮件
def send_mail(title,msg="",to_address=to_address):
    try:
        if type(to_address)==str:
            to_address=[to_address,]

        server=init_mail_server()

        msg = MIMEText(msg, 'plain', 'utf-8')
        msg['From'] = formataddr(("Exec_Mail", from_address))  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        msg['To'] = formataddr(("Admin", to_address))  # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject'] = title  # 邮件的主题，也可以说是标题

        server.sendmail(from_address, to_address, msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()  # 关闭连接
    except Exception as e:
        print(e)
        return False

# 发送带有附件的邮件
def send_mail_with_file(title,msg="",filename=None,to_address=to_address):
    if filename is None:
        send_mail(title,msg,to_address)
        return

    if type(to_address) == str:
        to_address = [to_address, ]
    message = MIMEMultipart()
    message['From'] = Header("Exec_mail", 'utf-8')
    message['To'] = Header("Admin", 'utf-8')
    subject = title
    message['Subject'] = Header(subject, 'utf-8')

    # 邮件正文内容
    message.attach(MIMEText(msg, 'plain', 'utf-8'))

    try:
        # 构造附件
        if type(filename)==str:
            filename=[filename]
        for each in filename:
            att1 = MIMEApplication(open(each, 'rb').read())
            att1["Content-Type"] = 'application/octet-stream'
            # 这里的filename可以任意写，写什么名字，邮件中显示什么名字
            att1["Content-Disposition"] = f"attachment; filename={each}"
            message.attach(att1)

        server = init_mail_server()
        server.sendmail(from_address, to_address, message.as_string())
        print("邮件发送成功")
        server.quit()
    except Exception as e:
        print(e)
        return False

if __name__ == '__main__':
    send_mail_with_file("test","test_content",filename=['Future.1639101036.4207056.bmp','Future.1639040536.7765608.bmp'])