# -*- coding: utf-8 -*-
"""
从数据库中取数据，用于策略运行
"""
import pandas as pd
import sqlite3
from abc import ABCMeta, abstractmethod, ABC

from data_center.mongodb_conn import MongoConn
from core.const import Interval, MongoDbName, SqliteDbName
from core.utility import date_str_to_int

sqlite_config = {
    'db_path': 'D:/python projects/quandomo/data_center/data/'
}


class GetDBData(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def get_all_market_data(self):
        """从数据库取数据"""
        pass

    @abstractmethod
    def get_market_data(self):
        """从 dataframe 解析数据成最终的数据格式"""
        pass

    @abstractmethod
    def get_end_timestamp(self):
        """取最后一个 bar/tick 的时间"""
        pass


class GetSqliteData(GetDBData, ABC):
    def __init__(self):
        super().__init__()
        self.conn = sqlite3.connect(sqlite_config['db_path'] + SqliteDbName.DB.value)

    def get_all_market_data(self, all_symbol_code=None, field=None, start=None, end=None, interval=Interval.DAILY):
        """从 sqlite 取数据"""

        if all_symbol_code is None:
            all_symbol_code = []
        if field is None:
            field = []
        if interval == Interval.DAILY:
            index_table_name = 'AINDEXEODPRICES'
            symbol_table_name = 'ASHAREEODPRICES'
            index_code = all_symbol_code[-1]
            symbol_code = all_symbol_code[:-1]
            field_sql = ['s_dq_' + i for i in field]
            field.extend(['s_info_windcode', 'trade_dt'])
            field_sql.extend(['s_info_windcode', 'trade_dt'])
            fields = ','.join(field_sql)

            # 取股票数据
            all_symbol_data_list = []
            for stock in symbol_code:
                get_data_sql = 'select {0} from {1} where s_info_windcode="{2}" ' \
                               'and trade_dt>={3} and trade_dt<={4}'.format(fields,
                                                                            symbol_table_name,
                                                                            stock,
                                                                            start,
                                                                            end)
                cur = self.conn.execute(get_data_sql)
                data = cur.fetchall()
                all_symbol_data_list.extend(data)

            # 取指数数据
            get_index_sql = 'select {0} from {1} where s_info_windcode="{2}" ' \
                            'and trade_dt>={3} and trade_dt<={4}'.format(fields,
                                                                         index_table_name,
                                                                         index_code,
                                                                         start,
                                                                         end)
            cur = self.conn.execute(get_index_sql)
            data = cur.fetchall()
            all_symbol_data_list.extend(data)

            market_data = pd.DataFrame(all_symbol_data_list, columns=field)
            market_data = market_data.set_index(['s_info_windcode', 'trade_dt'])
        else:
            market_data = None

        return market_data

    def get_market_data(self, market_data, all_symbol_code=None, field=None, start="", end="", count=-1):
        """
        从 dataframe 解析数据成最终的数据格式
        因为停牌或者其他原因取不到数据的，１　２　３　返回的是－１，其他返回的是 pandas 的空或者 NaN，所以可以使用　＞０判断是否取到值
        """
        if start != "":
            if isinstance(start, str):
                start = date_str_to_int(start)
        else:
            start = 0
        if end != "":
            if isinstance(end, str):
                end = date_str_to_int(end)
        else:
            end = 0
        # （１）代码-1，字段-1，时间-1,  return float
        if len(all_symbol_code) == 1 and len(field) == 1 and (start == end) and count == -1:
            try:
                return market_data[field[0]].loc[all_symbol_code[0], end]
            # 停牌或者其他情情况取不到数据的返回-1
            except BaseException:
                return -1
        # （２）代码-n，字段-1，时间-1,  return Series
        elif len(all_symbol_code) > 1 and len(field) == 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in all_symbol_code:
                try:
                    result_dict[stock] = market_data[field[0]].loc[stock, end]
                except BaseException:
                    result_dict[stock] = -1
            return pd.Series(result_dict)
        # （３）代码-1，字段-n，时间-1,  return Series
        elif len(all_symbol_code) == 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for field_one in field:
                try:
                    result_dict[field_one] = market_data[field_one].loc[all_symbol_code[0], end]
                except BaseException:
                    result_dict[field_one] = -1
            return pd.Series(result_dict)
        # （４）代码-1，字段-1，时间-n,  return Series
        elif len(all_symbol_code) == 1 and len(field) == 1 and (start != end) and count == -1:
            try:
                series = market_data[field[0]].loc[all_symbol_code[0]]
            except KeyError:
                return pd.Series()

            series = series[series.index >= start]
            series = series[series.index <= end]
            return series
        # （５）代码-n，字段-1，时间-n,  return dataframe 行-timestamp，列-代码
        elif len(all_symbol_code) > 1 and len(field) == 1 and (start != end) and count == -1:
            result_dict = {}
            for stock in all_symbol_code:
                index = market_data.loc[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data[field[0]].loc[stock][index]
            return pd.DataFrame(result_dict)
        # （６）代码-n，字段-n，时间-1,  return dataframe 行-字段，列-代码
        elif len(all_symbol_code) > 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in all_symbol_code:
                try:
                    result_dict[stock] = market_data.loc[stock, end]
                except BaseException:
                    result_dict[stock] = pd.Series()
            return pd.DataFrame(result_dict).loc[field]
        # （７）代码-1，字段-n，时间-n,  return dataframe 行-timestamp，列-字段
        elif len(all_symbol_code) == 1 and len(field) > 1 and (start != end) and count == -1:
            index = market_data.loc[all_symbol_code[0]].index
            index = index[index <= end]
            index = index[index >= start]
            return market_data.ix[all_symbol_code[0]][field].loc[index]
        # 代码-n，字段-n，时间-n,  return dataframe 行-代码-timestamp(多层索引)，列-字段
        else:
            result_dict = {}
            for stock in all_symbol_code:
                index = market_data.loc[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data.loc[stock][field].loc[index]
            return pd.concat(result_dict, keys=all_symbol_code)

    def get_ex_rights_data(self, table_name: str, fields: list, date_field: str = None, start_date: str = None):
        """
        取所有股票的除权除息数据，返回两层结构的 dict
        第一层的 key 是股票代码，第二层的 key 是日期
        """
        get_data_sql = 'select {0} from {1} where {2} >= {3}'.format(','.join(fields),
                                                                     table_name,
                                                                     date_field,
                                                                     start_date)

        cur = self.conn.execute(get_data_sql)
        data = cur.fetchall()

        # ssym = ''
        # data_dict = {}
        # cur_dict = {}
        # for datal in data:
        #     if ssym != datal[0]:
        #         if ssym not in data_dict.keys():
        #             data_dict[datal[0]] = {}
        #         else:
        #             data_dict[ssym] = cur_dict
        #             data_dict[datal[0]] = {}
        #             cur_dict = {}
        #         ssym = datal[0]
        #
        #         cur_dict[datal[1]] = {
        #             'CASH_DIVIDEND_RATIO': datal[2],
        #             'BONUS_SHARE_RATIO': datal[3],
        #             'RIGHTSISSUE_RATIO': datal[4],
        #             'RIGHTSISSUE_PRICE': datal[5],
        #             'CONVERSED_RATIO': datal[6]
        #         }
        #     else:
        #         cur_dict[datal[1]] = {
        #             'CASH_DIVIDEND_RATIO': datal[2],
        #             'BONUS_SHARE_RATIO': datal[3],
        #             'RIGHTSISSUE_RATIO': datal[4],
        #             'RIGHTSISSUE_PRICE': datal[5],
        #             'CONVERSED_RATIO': datal[6]
        #         }

        data_df = pd.DataFrame(data, columns=fields)
        data_df = data_df.fillna(0)
        data_dict = {}
        for name, group in data_df.groupby('S_INFO_WINDCODE'):
            v_dict = {}
            for vv in group.values:
                v_dict[vv[1]] = {
                        'CASH_DIVIDEND_RATIO': vv[2],
                        'BONUS_SHARE_RATIO': vv[3],
                        'RIGHTSISSUE_RATIO': vv[4],
                        'RIGHTSISSUE_PRICE': vv[5],
                        'CONVERSED_RATIO': vv[6]
                }
            data_dict[name] = v_dict
        return data_dict


class GetMongoData(GetDBData):
    def __init__(self):
        super().__init__()
        self.conn = MongoConn()

    def get_all_market_data(self, stock_code=None, field=None, start="", end="", interval=Interval.DAILY):
        """从mongodb取数据"""

        if interval == Interval.DAILY:
            db_name = MongoDbName.MARKET_DATA_DAILY.value
            if isinstance(start, str):
                start = date_str_to_int(start)
                end = date_str_to_int(end)
            values = []
            colum = {"_id": 0, "timetag": 1}
            for i in field:
                colum[i] = 1
            for stock in stock_code:
                self.conn.check_connected()
                stock_market_data = self.conn.select_colum(db_name=db_name,
                                                           table=stock,
                                                           value={"timetag": {"$gte": start, "$lte": end}},
                                                           colum=colum)
                stock_market_data_list = list(stock_market_data)
                if stock_market_data_list:
                    df = pd.DataFrame(stock_market_data_list)
                    values.append(pd.DataFrame(df[field].values, index=df['timetag'], columns=field))
            market_data = pd.concat(values, keys=stock_code)
        else:
            market_data = None

        return market_data

    def get_market_data(self, market_data, stock_code=None, field=None, start="", end="", count=-1):
        """
        从 dataframe 解析数据成最终的数据格式
        因为停牌或者其他原因取不到数据的，１　２　３　返回的是－１，其他返回的是 pandas 的空或者 NaN，所以可以使用　＞０判断是否取到值
        """
        if start != "":
            if isinstance(start, str):
                start = date_str_to_int(start)
        else:
            start = 0
        if end != "":
            if isinstance(end, str):
                end = date_str_to_int(end)
        else:
            end = 0
        # （１）代码-1，字段-1，时间-1,  return float
        if len(stock_code) == 1 and len(field) == 1 and (start == end) and count == -1:
            try:
                return market_data[field[0]].loc[stock_code[0], end]
            # 停牌或者其他情情况取不到数据的返回-1
            except BaseException:
                return -1
        # （２）代码-n，字段-1，时间-1,  return Series
        elif len(stock_code) > 1 and len(field) == 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in stock_code:
                try:
                    result_dict[stock] = market_data[field[0]].loc[stock, end]
                except BaseException:
                    result_dict[stock] = -1
            return pd.Series(result_dict)
        # （３）代码-1，字段-n，时间-1,  return Series
        elif len(stock_code) == 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for field_one in field:
                try:
                    result_dict[field_one] = market_data[field_one].loc[stock_code[0], end]
                except BaseException:
                    result_dict[field_one] = -1
            return pd.Series(result_dict)
        # （４）代码-1，字段-1，时间-n,  return Series
        elif len(stock_code) == 1 and len(field) == 1 and (start != end) and count == -1:
            try:
                series = market_data[field[0]].loc[stock_code[0]]
            except KeyError:
                return pd.Series()

            series = series[series.index >= start]
            series = series[series.index <= end]
            return series
        # （５）代码-n，字段-1，时间-n,  return dataframe 行-timestamp，列-代码
        elif len(stock_code) > 1 and len(field) == 1 and (start != end) and count == -1:
            result_dict = {}
            for stock in stock_code:
                index = market_data.loc[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data[field[0]].loc[stock][index]
            return pd.DataFrame(result_dict)
        # （６）代码-n，字段-n，时间-1,  return dataframe 行-字段，列-代码
        elif len(stock_code) > 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in stock_code:
                try:
                    result_dict[stock] = market_data.loc[stock, end]
                except BaseException:
                    result_dict[stock] = pd.Series()
            return pd.DataFrame(result_dict).loc[field]
        # （７）代码-1，字段-n，时间-n,  return dataframe 行-timestamp，列-字段
        elif len(stock_code) == 1 and len(field) > 1 and (start != end) and count == -1:
            index = market_data.loc[stock_code[0]].index
            index = index[index <= end]
            index = index[index >= start]
            return market_data.ix[stock_code[0]][field].loc[index]
        # 代码-n，字段-n，时间-n,  return dataframe 行-代码-timestamp(多层索引)，列-字段
        else:
            result_dict = {}
            for stock in stock_code:
                index = market_data.loc[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data.loc[stock][field].loc[index]
            return pd.concat(result_dict, keys=stock_code)

    def get_end_timestamp(self, benchmark, interval=Interval.DAILY):
        # if interval == Interval_DAILY:
        db_name = MongoDbName.MARKET_DATA_DAILY

        colum = {"_id": 0, "timetag": 1}
        end_timestamp_list = self.conn.select_colum(db_name=db_name,
                                                    table=benchmark,
                                                    value={},
                                                    colum=colum)
        if end_timestamp_list:
            end_timestamp = str(int(max([i["timetag"] for i in list(end_timestamp_list)])))
        else:
            end_timestamp = None
        return end_timestamp[:4] + "-" + end_timestamp[4:6] + "-" + end_timestamp[6:]


if __name__ == "__main__":
    aa = GetMongoData()
    stock_list = ['000300.SH', '000001.SZ', '000002.SZ', '600000.SH', '600001.SH']
    daily_data = aa.get_all_market_data(stock_code=stock_list,
                                        field=["open", "high", "low", "close", "order_volume", "amount"],
                                        start="2005-01-04",
                                        end="2008-02-22",
                                        interval=Interval.DAILY)
    print(daily_data)

    # data_1 = aa.get_market_data(daily_data, stock_code=["000002.SZ"], field=["open"], start="2018-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_1)
    #
    # data_2 = aa.get_market_data(daily_data, stock_code=["000002.SZ", "000001.SH"], field=["open"], start="2018-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_2)
    #
    # data_3 = aa.get_market_data(daily_data, stock_code=["000002.SZ"], field=["open", "high"], start="2018-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_3)
    # data_4 = aa.get_market_data(daily_data, stock_code=["000002.SZ"], field=["open"], start="2017-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_4)
    #
    # data_5 = aa.get_market_data(daily_data, stock_code=["000002.SZ", "000001.SH"], field=["open"], start="2017-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_5)
    #
    # data_6 = aa.get_market_data(daily_data, stock_code=["000002.SZ", "000001.SH"], field=["open", "high"],
    #                             start="2019-01-02", end="2019-01-02", count=-1)
    # # print(data_6)
    #
    # data_7 = aa.get_market_data(daily_data, stock_code=["000002.SZ"], field=["open", "high"], start="2017-01-02",
    #                             end="2018-01-02", count=-1)
    # # print(data_7)
    # data_8 = aa.get_market_data(daily_data, stock_code=["000002.SZ", "000001.SH"], field=["open", "high"],
    #                             start="2017-01-02",
    #                             end="2018-01-02", count=-1)
    # #print(data_8)
