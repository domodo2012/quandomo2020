# -*- coding: utf-8 -*-
"""
通过湘财版 tushare 接口，获取 wd 数据库中的数据，并在本地保存成 csv 文件
"""
import akshare as ak
import xcsc_tushare as xcts
import tushare as ts
import pandas as pd
import time
from datetime import timedelta


def get_hs300_members_xctushare(begin_date, end_date, pname, fields):
    all_data = []
    cur_begin_date = begin_date
    cur_end_date = begin_date
    while cur_begin_date <= end_date:
        print(cur_begin_date)

        cur_end_date1 = pd.to_datetime(str(cur_end_date)) + timedelta(days=30)
        cur_end_date = int(cur_end_date1.strftime('%Y%m%d'))

        df = pro.index_weight(start_date=cur_begin_date, end_date=cur_end_date, fields=fields)

        cur_begin_date = cur_end_date
        all_data.append(df)

    all_data_df = pd.concat(all_data, names=[fields])
    all_data_df = all_data_df.drop_duplicates()
    all_data_df = all_data_df.sort_values(['trade_date', 'con_ts_code'])
    all_data_df = all_data_df.reset_index(drop=True)
    all_data_df.to_pickle(pname)


def get_index_members_akshare(exchange: str, index_code: str, pname: str):
    cur_index_members_df = ak.index_stock_cons(index=index_code)
    cimd = cur_index_members_df[['品种代码', '纳入日期']]
    cimd.columns = ['stock_code', 'in_date']
    cimd['out_date'] = 'nan'

    index_member_hist_df = ak.index_stock_hist(index=exchange + index_code)
    index_members = pd.concat([cimd, index_member_hist_df], axis=0)
    index_members = index_members.reset_index(drop=True)

    all_data = []
    for _, row in index_members.iterrows():
        if row['stock_code'][0] == '6':
            cur_symbol = row['stock_code'] + '.SH'
        else:
            cur_symbol = row['stock_code'] + '.SZ'

        in_date = pd.to_datetime(row['in_date'])
        cur_in_date = int(in_date.strftime('%Y%m%d'))

        if row['out_date'] == 'nan':
            cur_out_date = 0
        else:
            out_date = pd.to_datetime(row['out_date'])
            cur_out_date = int(out_date.strftime('%Y%m%d'))

        all_data.append([cur_symbol, cur_in_date, cur_out_date])
    index_members2 = pd.DataFrame(all_data, columns=index_members.columns)
    index_members2 = index_members2.drop_duplicates(['stock_code', 'in_date', 'out_date']).sort_values(['stock_code', 'in_date', 'out_date']).reset_index(drop=True)
    index_members2.to_pickle(pname)


def get_sw_index_data():
    pass


def get_zx_index_data():
    pass


if __name__ == '__main__':
    token_xcts_prd = '2a876aa6da3590a5ebebc55e4f852cd5e17813a3390bd3cd642ec29e'
    token_ts = '9cbff072025ae17a12e05b84235202a7af807f3a3e074124c8a0aae0'
    xcts.set_token(token_xcts_prd)
    pro = xcts.pro_api(env='prd')

    begin_date = 20060410     # xctushare 的数据开始日期
    end_date = 20201029
    root_path = 'D:/python projects/quandomo/data_center/data/xctushare/'

    # trade_dt = pro.trade_cal(exchange='SSE', start_date=begin_date, end_date=end_date)
    # trade_date_list = list(trade_dt['trade_date'].values)

    # 下载300指数成分股及其权重数据
    # fields = "con_ts_code,trade_date,i_weight"
    # get_hs300_members_xctushare(begin_date, end_date, root_path + r'hs300_classify.pkl', fields)

    # 从 akshare 获取沪深300成分股
    exchange = 'sh'
    index_code = '000300'
    get_index_members_akshare(exchange, index_code, root_path + r'hs300_members.pkl')




