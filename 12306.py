# -*- coding:utf-8 -*-
import re
import os
import sys
import time
import json
import yaml
import random
import requests
from urllib import parse
from send_email import sendEmail

def get_file_info(file):
    dirname   = os.path.dirname(__file__)
    file = os.path.join(dirname,file)
    load_func = [json.load,yaml.load][file.endswith('.yaml')]
    with open(file,'r',encoding = "utf-8") as fp:
        datas = load_func(fp)
    return datas

def get_point_360(imgbase64):
    """调用第三方识别验证码，返回验证码坐标"""
    url     = "http://60.205.200.159/api"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36',}
    res     = requests.post(url,headers = headers,json = {"base64":imgbase64,}).json()
    data    = {
        '=':'',
        'check':res['check'],
        'img_buf':imgbase64,
        'logon':1,
        'type':'D',}
    url = "http://check.huochepiao.360.cn/img_vcode"
    res =  requests.post(url,json = data,headers = headers).json()
    res = res['res']
    res = res.replace('(','').replace(')','')
    return res

class BuyTicket(object):
    def __init__(self,config = None):
        self.index              = 1
        self.islogin            = False
        self.train_info         = dict()
        self.seat_type          = ''
        self.passengers         = ''
        self.oldpassengerStr    = ''
        self.passengerTicketStr = ''
        self.session            = requests.Session()
        self.config             = config
        self.headers            = {
            'Host': 'kyfw.12306.cn',
            'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36',
            }
        

    def check_captcha(self):
        """调用第三方接口识别验证码"""
        captcha_url = 'https://kyfw.12306.cn/passport/captcha/captcha-image64'
        random_data = random.random()
        params = {
        'login_site':'E',
        'module':'login',
        'rand':'sjrand',
        '_':random_data,
        }

        response = self.session.get(captcha_url,params = params,headers = self.headers)
        try:
            img_base64 = response.json()['image']
        except:
            print ("验证码获取失败!")
            return False

        points = get_point_360(img_base64)
        params.pop('module')
        params['_'] = int(1000 * time.time())
        params['answer'] = points

        check_captcha = 'https://kyfw.12306.cn/passport/captcha/captcha-check'
        response = self.session.get(check_captcha,params = params,headers = self.headers)
        data = response.json()
        if data['result_code'] == '4':
            return True
        else:
            return False
        
        
    def login_12306(self):
        """登录"""
        captcha = self.check_captcha()
        if captcha is False:
            return

        login_url = 'https://kyfw.12306.cn/passport/web/login'
        form_data = self.config['form_data']
        response = self.session.post(login_url, data = form_data,headers = self.headers)
        res = response.json()
        if res["result_code"]:
            print ('登录失败!')
            return
        uamtk_url = 'https://kyfw.12306.cn/passport/web/auth/uamtk'
        response = self.session.post(uamtk_url, data={'appid': 'otn'})
        res = response.json()
        if res["result_code"]:
            print ('认证失败!')
            return

        check_token_url = 'https://kyfw.12306.cn/otn/uamauthclient'
        response = self.session.post(check_token_url, data={'tk': res['newapptk']})
        data = response.json()
        print (f"{data['result_message']}!欢迎你:{data['username']}!")
        return
    
    
    def login_state_check(self):
        """登录状态检查"""
        login_state_url = 'https://kyfw.12306.cn/otn/login/checkUser'
        jsondata = self.session.post(login_state_url,headers = self.headers,data = {"_json_att":'',})
        try:
            return jsondata.json()['data']['flag']
        except:
            return False

    def getleftTickets(self,stations,train_date,from_station,to_station):
        """余票查询"""
        query_url   = 'https://kyfw.12306.cn/otn/leftTicket/queryX'
        Ticket_data = {
            "leftTicketDTO.train_date":  train_date,
            "leftTicketDTO.from_station":from_station,
            "leftTicketDTO.to_station":  to_station,
            "purpose_codes":             "ADULT",
            }
        headers     = {
                'Host': 'kyfw.12306.cn',
                'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36',
                }
        data = requests.get(query_url,params = Ticket_data,headers = headers)
     
        if data is None:
            print ("访问异常!")
            return None
        
        first_time,last_time = self.config['ticket_info']['train_times'].split('-')
        seat_type = self.config['ticket_info']['seat_type']

        best_sell = ''
        left_ticket = 0
        
        lists = data.json()["data"]["result"]
        for items in lists:
            ticket_info = dict()
            item = items.split('|')#用"|"进行分割

            start_time = item[8]
            if first_time >  start_time or start_time > last_time:
                continue
            
            ticket_info['station_train_code'] = item[3]     #车次在3号位置
            ticket_info['from_station_name']  = stations[item[6]]     #始发站信息在6号位置
            ticket_info['to_station_name']    = stations[item[7]]     #终点站信息在7号位置
            ticket_info['start_time']         = item[8]     #出发时间信息在8号位置
            ticket_info['arrive_time']        = item[9]     #抵达时间在9号位置
            ticket_info['last_time']          = item[10]    #经历时间在10号位置
            ticket_info['商务座']             = item[32] or item[25] # 特别注意：商务座在32或25位置
            ticket_info['一等座']             = item[31]    #一等座信息在31号位置
            ticket_info['二等座']             = item[30]    #二等座信息在30号位置
            ticket_info['高级软卧']           = item[21]    #高级软卧信息在31号位置
            ticket_info['软卧']               = item[23]    #软卧信息在23号位置
            ticket_info['动卧']               = item[27]    #动卧信息在27号位置
            ticket_info['硬卧']               = item[28]    #硬卧信息在28号位置
            ticket_info['软座']               = item[24]    #软座信息在24号位置
            ticket_info['硬座']               = item[29]    #硬座信息在29号位置
            ticket_info['无座']               = item[26]    #无座信息在26号位置
            ticket_info['其他']               = item[22]    #其他信息在22号位置

            if ticket_info[seat_type] in [None,'','无','*']:
                continue
            elif ticket_info[seat_type] == '有':   #查询到有票马上返回
                best_sell = items
                break
            else:
                ticket = int(ticket_info[seat_type])
                if ticket > left_ticket:
                    left_ticket = ticket
                    best_sell = items
        return best_sell

        
    def order(self,best_sell,from_station, to_station, date):
        """提交订单"""
        secretStr,*_ = best_sell.split('|')
        secretStr = parse.unquote(secretStr)
        back_train_date = time.strftime("%Y-%m-%d", time.localtime())
        form = {
            'secretStr':               secretStr,  # 'secretStr':就是余票查询中你选的那班车次的result的那一大串余票信息的|前面的字符串再url解码
            'train_date':              date,  # 出发日期(2018-04-08)
            'back_train_date':         back_train_date,  # 查询日期
            'tour_flag':               'dc',  # 固定的
            'purpose_codes':           'ADULT',  # 成人票
            'query_from_station_name': from_station,  # 出发地
            'query_to_station_name':   to_station,  # 目的地
            'undefined':               ''  # 固定的
        }
        order_url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
        html_order = self.session.post(order_url, data=form, headers=self.headers).json()
        
        return html_order['status']
            
      
    def get_token_info(self):
        """获取各种需要提交的oken"""
        token_url = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        html_token = self.session.post(token_url,data= {"_json_att":'',}, headers=self.headers).text

        token,*_ = re.findall(r"var globalRepeatSubmitToken = '(.*?)';", html_token)
        leftTicket,*_ = re.findall(r"'leftTicketStr':'(.*?)',", html_token)
        key_check_isChange,*_ = re.findall(r"'key_check_isChange':'(.*?)',", html_token)
        train_no,*_  = re.findall(r"'train_no':'(.*?)',", html_token)
        stationTrainCode,*_ = re.findall(r"'station_train_code':'(.*?)',", html_token)
        fromStationTelecode,*_  = re.findall(r"'from_station_telecode':'(.*?)',", html_token)
        toStationTelecode,*_   = re.findall(r"'to_station_telecode':'(.*?)',", html_token)

        date_temp,*_ = re.findall(r"'to_station_no':'.*?','train_date':'(.*?)',", html_token)
        timeArray = time.strptime(date_temp, "%Y%m%d")
        timeStamp = int(time.mktime(timeArray))
        time_local = time.localtime(timeStamp)
        train_date_temp = time.strftime("%a %b %d %Y %H:%M:%S", time_local)
        train_date = train_date_temp + ' GMT+0800 (中国标准时间)'
        
        train_location,*_= re.findall(r"tour_flag':'.*?','train_location':'(.*?)'", html_token)
        purpose_codes,*_ = re.findall(r"'purpose_codes':'(.*?)',", html_token)

        self.train_info['train_date']          = train_date
        self.train_info['train_no']            = train_no
        self.train_info['stationTrainCode']    = stationTrainCode
        self.train_info['fromStationTelecode'] = fromStationTelecode
        self.train_info['toStationTelecode']   = toStationTelecode
        self.train_info['leftTicket']          = leftTicket
        self.train_info['purpose_codes']       = purpose_codes
        self.train_info['train_location']      = train_location
        self.train_info['token']               = token
        self.train_info['key_check_isChange']  = key_check_isChange

    def get_passengers(self):
        '''打印乘客信息'''
        form = {
            '_json_att':           '',
            'REPEAT_SUBMIT_TOKEN': self.train_info['token']
                }

        passages_url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        html_pass = self.session.post(passages_url, data=form, headers=self.headers).json()
        self.passengers = html_pass['data']['normal_passengers']



    def get_passenger_Str(self):
        """获取乘客信息"""
        self.oldpassengerStr    = ''
        self.passengerTicketStr = ''
        seat_dict = {'无座': '1', '硬座': '1','软座':'2', '硬卧': '3', '软卧': '4', '高级软卧': '6', '动卧': 'F', '二等座': 'O', '一等座': 'M','商务座': '9',}
        
        self.seat_type = seat_dict[self.config['ticket_info']['seat_type']]
        
        passengers = self.config['ticket_info']["passengers"].split()
        if not self.passengers:
            self.get_passengers()
        for person in passengers:
            for passenger in self.passengers:
                if person != passenger['passenger_name']:
                    continue
                self.oldpassengerStr    += ','.join([passenger['passenger_name'],passenger['passenger_type'],passenger['passenger_id_no'],'1_'])
                self.passengerTicketStr += ','.join([self.seat_type,'0,1',passenger['passenger_name'],passenger['passenger_type'],passenger['passenger_id_no'],passenger['mobile_no'],'N'])
            if person != passengers[-1]:
                self.passengerTicketStr += '_'
                

    def get_leftticket_info(self):
        """获取余票信息"""
        form = {
            'train_date':          self.train_info['train_date'],
            'train_no':            self.train_info['train_no'],
            'stationTrainCode':    self.train_info['stationTrainCode'],
            'seatType':            self.seat_type,
            'fromStationTelecode': self.train_info['fromStationTelecode'],
            'toStationTelecode':   self.train_info['toStationTelecode'],
            'leftTicket':          self.train_info['leftTicket'],
            'purpose_codes':       self.train_info['purpose_codes'],
            'train_location':      self.train_info['train_location'],
            '_json_att':           '',
            'REPEAT_SUBMIT_TOKEN': self.train_info['token']
        }

        count_url = 'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount'
        html_count = self.session.post(count_url, data=form, headers=self.headers).json()
        if html_count['status'] == True:
            count = html_count['data']['ticket']
            print(f'此座位类型还有余票{count}张。')
        else:
            print(f"查看余票数量失败!\n{html_count['messages']}")
        return html_count['status']
    
            
    def get_seat_info(self):
        '''选择乘客和座位'''
        if not self.passengerTicketStr:
            self.get_passenger_Str()
        form = {
            'cancel_flag':         '2',
            'bed_level_order_num': '000000000000000000000000000000',
            'passengerTicketStr':  self.passengerTicketStr,
            'oldPassengerStr':     self.oldpassengerStr,
            'tour_flag':           'dc',
            'randCode':            '',
            'whatsSelect':         '1',
            '_json_att':           '',
            'REPEAT_SUBMIT_TOKEN': self.train_info['token'],
        }
        checkorder_url = 'https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo'
        html_checkorder = self.session.post(checkorder_url, data=form, headers=self.headers).json()
        

    def confirm(self):
        '''最终确认订单'''
        form = {
            'passengerTicketStr':  self.passengerTicketStr,
            'oldPassengerStr':     self.oldpassengerStr,
            'randCode':            '',
            'key_check_isChange':  self.train_info['key_check_isChange'],
            'choose_seats':        '',
            'seatDetailType':      '000',
            'leftTicketStr':       self.train_info['leftTicket'],
            'purpose_codes':       self.train_info['purpose_codes'],
            'train_location':      self.train_info['train_location'],
            '_json_att':           '',
            'whatsSelect':         '1',
            'roomType':            '00',
            'dwAll':               'N',
            'REPEAT_SUBMIT_TOKEN': self.train_info['token']
        }

        confirm_url = 'https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue'
        html_confirm = self.session.post(confirm_url, data=form, headers=self.headers).json()
        try:
            errMsg = html_confirm['data']['errMsg']
            print(errMsg)
            return False
        except:
            return html_confirm['status']
        
    def queryOrderWaitTime(self):
        """查询时间等待"""
        form={
            "REPEAT_SUBMIT_TOKEN": self.train_info['token'],    #获取过
            "_json_att":           "",   #空
            "random":              str(time.time()),#随机值
            "tourFlag":            "dc"  #固定值
            }

        waittime_url = 'https://kyfw.12306.cn/otn/confirmPassenger/queryOrderWaitTime'
        WaitTime = self.session.post(waittime_url,data = form,headers=self.headers).json()
        return WaitTime

        
if __name__ == "__main__":
    stations      = get_file_info('stations.json')
    config        = get_file_info('config.yaml')
    train_date    = config['ticket_info']['train_date']
    from_station  = stations[config['ticket_info']['from_station']]
    to_station    = stations[config['ticket_info']['to_station']]
    train_times   = config['ticket_info']['train_times']

    Ticket = BuyTicket(config = config)
    Ticket.login_12306()
    while 1:
        time.sleep(1)
        best_sell = Ticket.getleftTickets(stations,train_date,from_station,to_station)
        if not best_sell:
            sys.stdout.write(f"没有查询到满足条件的车次!第{Ticket.index}次查询。\r")
            sys.stdout.flush()
            Ticket.index += 1
            if Ticket.index % 100 == 0:
                islogin = Ticket.login_state_check()
                if not islogin:
                    Ticket.login_12306()
            continue
        print ("查询到满足条件的车次，正在努力订票中.....")
        is_success = Ticket.order(best_sell,from_station,to_station,train_date)
        if not is_success:
            print ("提交订单失败!\n")
            continue
        Ticket.get_token_info()
        Ticket.get_seat_info()
        get_leftticket = Ticket.get_leftticket_info()
        if not get_leftticket:
            continue
        html_confirm = Ticket.confirm()
        if html_confirm:
            while 1:
                WaitTime = Ticket.queryOrderWaitTime()
                waittime = WaitTime['data']['waitTime']
                orderId =  WaitTime['data']['orderId']
                if orderId:
                    print (f'恭喜!订票成功,订单号:{orderId}!请前往12306网站付款!')
                    sendEmail(config['email_address'])
                    break
                else:
                    if WaitTime['messages']:
                        print (f"{WaitTime['messages']}\n很遗憾，购票失败!")
                    else:
                        print (f"排队中.......大概需要{waittime}分钟！")
                    time.sleep(2)
            break
        else:
            print ("订票失败!")
