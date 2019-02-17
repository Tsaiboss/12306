import smtplib
from email.mime.text import MIMEText

def sendEmail(receivers):
    mail_host = "smtp.163.com"      # SMTP服务器
    mail_user = "用户名"                 # 用户名
    mail_pass = "授权密码，非登录密码"               # 授权密码，非登录密码
    sender = '发件人邮箱'    # 发件人邮箱(最好写全, 不然会失败)

    title   = "订票助手提交订单成功通知"
    content = '恭喜恭喜，抢到票啦！恭喜恭喜，抢到票啦！'  # 邮件主题
 
    message = MIMEText(content, 'plain', 'utf-8')  # 内容, 格式, 编码
    message['From'] = "{}".format(sender)
    message['To'] = ",".join(receivers)
    message['Subject'] = title
 
    try:
        smtpObj = smtplib.SMTP_SSL(mail_host, 465)  # 启用SSL发信, 端口一般是465
        smtpObj.login(mail_user, mail_pass)  # 登录验证
        smtpObj.sendmail(sender, receivers, message.as_string())  # 发送
        print("mail has been send successfully.")
    except smtplib.SMTPException as e:
        print(e)
