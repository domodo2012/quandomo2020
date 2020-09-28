# -*- coding: utf-8 -*-
"""
远程连接局域网内的oracle数据库（wd），并获取数据
"""
import cx_Oracle as co
import pandas as pd


class GetDataFromDb(object):
    def __init__(self, db_id, db_pw, db_ip):
        self.db_id = db_id
        self.db_pw = db_pw
        self.db_ip = db_ip
        self.conn = None
        self.cr = None
        self.rs = None
        self.connect_db()

    def connect_db(self):
        self.conn = co.connect(db_id, db_pw, db_ip)
        self.cr = self.conn.cursor()

    def get_data(self, sql_str: str, fpath: str, dt_type: str):
        self.cr.execute(sql_str)
        self.rs = self.cr.fetchall()

        col_name = [ii[0] for ii in self.cr.description]
        df = pd.DataFrame(self.rs, columns=col_name)
        df.to_csv(fpath, index=None)

        print('{0} 数据从初始数据库抽取并保存到本地完毕。'.format(dt_type))


if __name__ == '__main__':
    db_id = 'cxb1'
    db_pw = 'oracle'
    db_ip = '192.168.3.9:1521/orcl'
    begin_date = '20190101'
    end_date = '20190210'
    rootpath = 'D:/python projects/quandomo/data/'

    get_data_from_db = GetDataFromDb(db_id, db_pw, db_ip)

    # 取交易日历数据
    table_name = '交易日历'
    filename = r'ASHARECALENDAR.csv'
    sql_calendar = "select * from cxb1.ASHARECALENDAR order by s_info_exchmarket asc, trade_days asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_calendar, fpath_finance, table_name)

    # 取股票日K线数据
    table_name = '股票'
    sql_stk = "select * from cxb1.ashareeodprices where trade_dt >= '" + begin_date + "' and trade_dt <= '" + \
              end_date + "' order S_INFO_WINDCODE asc, by trade_dt asc"
    fpath_stk = rootpath + r'KLine_daily/ASHAREEODPRICES.csv'
    get_data_from_db.get_data(sql_stk, fpath_stk, table_name)

    # 取除权除息数据
    table_name = '除权除息'
    filename = r'AShareEXRightDividendRecord.csv'
    sql_right = "select * from cxb1.AShareEXRightDividendRecord order by S_INFO_WINDCODE asc, ex_date asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_right, fpath_finance, table_name)

    # 取股本数据
    table_name = '股本'
    filename = r'ASHARECAPITALIZATION.csv'
    sql_capital = "select * from cxb1.ASHARECAPITALIZATION order by S_INFO_WINDCODE asc, change_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_capital, fpath_finance, table_name)

    # 取宽基指数日K线数据
    table_name = '宽基指数'
    index_code = "('000001.SH', '000002.SH', '000003.SH', '000004.SH', '000005.SH', '000006.SH', '000007.SH', " \
                 "'000008.SH', '000010.SH', '000011.SH', '000012.SH', '000013.SH', '000016.SH', '000015.SH', " \
                 "'000300.SH', '000905.SH')"
    sql_index = "select * from cxb1.aindexeodprices where trade_dt >= '" + begin_date + "' and trade_dt <= '" + \
                end_date + "' and S_INFO_WINDCODE in " + index_code + " order by S_INFO_WINDCODE asc, trade_dt asc"
    fpath_index = rootpath + r'KLine_index_daily/AINDEXEODPRICES.csv'
    get_data_from_db.get_data(sql_index, fpath_index, table_name)

    # 取申万一级行业指数日线数据
    table_name = '申万行业指数'
    filename = r'ASWSINDEXEOD.csv'
    sql_swi = "select * from cxb1.aswsindexeod where trade_dt >= '" + begin_date + "' and trade_dt <= '" + \
              end_date + "' order by S_INFO_WINDCODE asc, trade_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_swi, fpath_finance, table_name)

    # 取指数成分股数据
    table_name = ['宽基指数成分股', '申万行业指数成分股']
    filename = [r'AINDEXMEMBERS.csv', r'SWINDEXMEMBERS.csv']
    sql_str = {'AINDEXMEMBERS': "select * from cxb1.AINDEXMEMBERS where s_con_indate >= '" + begin_date + \
                                "' and s_con_indate <= '" + end_date +
                                "' order by S_INFO_WINDCODE asc, s_con_indate asc",
               'SWINDEXMEMBERS': "select * from cxb1.SWINDEXMEMBERS where s_con_indate >= '" + begin_date + \
                                 "' and s_con_indate <= '" + end_date +
                                 "' order by S_INFO_WINDCODE asc, s_con_indate asc",
               }
    for ii in range(0, 2):
        fpath_finance = rootpath + r'finance/' + filename[ii]
        get_data_from_db.get_data(sql_str[filename[ii].split('.')[0]], fpath_finance, table_name[ii])

    # 取业绩预告数据
    table_name = '业绩预告'
    filename = r'ASHAREPROFITNOTICE.csv'
    sql_profit_notice = "select * from cxb1.ASHAREPROFITNOTICE where s_profitnotice_date >= '" + begin_date + \
                        "' and s_profitnotice_date <= '" + \
                        end_date + "' order by S_INFO_WINDCODE asc, s_profitnotice_date asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_profit_notice, fpath_finance, table_name)

    # 取业绩快报数据
    table_name = '业绩快报'
    filename = r'ASHAREPROFITEXPRESS.csv'
    sql_profit_express = "select * from cxb1.ASHAREPROFITEXPRESS where ann_dt >= '" + begin_date + \
                         "' and ann_dt <= '" + end_date + "' order by S_INFO_WINDCODE asc, ann_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_profit_express, fpath_finance, table_name)

    # 取利润表数据
    table_name = '利润表'
    filename = r'ASHAREINCOME.csv'
    sql_income = "select * from cxb1.ASHAREINCOME where ann_dt >= '" + begin_date + \
                 "' and ann_dt <= '" + end_date + "' order by S_INFO_WINDCODE asc, ann_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_income, fpath_finance, table_name)

    # 取现金流量表数据
    table_name = '现金流量表'
    filename = r'AShareCashFlow.csv'
    sql_cash_flow = "select * from cxb1.AShareCashFlow where ann_dt >= '" + begin_date + \
                    "' and ann_dt <= '" + end_date + "' order by S_INFO_WINDCODE asc, ann_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_cash_flow, fpath_finance, table_name)

    # 取资产负债表数据
    table_name = '资产负债表'
    filename = r'AShareBalanceSheet.csv'
    sql_balance = "select * from cxb1.AShareBalanceSheet where ann_dt >= '" + begin_date + \
                  "' and ann_dt <= '" + end_date + "' order by S_INFO_WINDCODE asc, ann_dt asc"
    fpath_finance = rootpath + r'finance/' + filename
    get_data_from_db.get_data(sql_balance, fpath_finance, table_name)

