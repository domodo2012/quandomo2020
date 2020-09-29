# -*- coding: utf-8 -*-

import pandas as pd

from data_center.mongodb_conn import MongoConn
from core.const import DatabaseName, Interval
from core.utility import date_str_to_int


class GetData(object):
    def __init__(self):
        self.conn = MongoConn()

    def get_all_market_data(self, stock_code=[], field=[], start="", end="", interval=Interval.DAILY.value):
        """从mongodb取数据"""

        if interval == Interval.DAILY.value:
            db_name = DatabaseName.MARKET_DATA_DAILY.value
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

    def get_market_data(self, market_data, stock_code=[], field=[], start="", end="", count=-1):
        """
        从dataframe解析数据成最终的数据格式，count都在这里做
        因为停牌或者其他原因取不到数据的，１　２　３　返回的是－１，其他返回的是pandas的空或者NaN，所以可以使用　＞０判断是否取到值
        """
        if start != "":
            start = date_str_to_int(start)
        else:
            start = 0
        if end != "":
            end = date_str_to_int(end)
        else:
            end = 0
        # （１）代码-1，字段-1，时间-1,  return float
        if len(stock_code) == 1 and len(field) == 1 and (start == end) and count == -1:
            try:
                return market_data[field[0]].loc[stock_code[0], end]
            # 停牌或者其他情情况取不到数据的返回-1
            except:
                return -1
        # （２）代码-n，字段-1，时间-1,  return Series
        elif len(stock_code) > 1 and len(field) == 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in stock_code:
                try:
                    result_dict[stock] = market_data[field[0]].ix[stock, end]
                except:
                    result_dict[stock] = -1
            return pd.Series(result_dict)
        # （３）代码-1，字段-n，时间-1,  return Series
        elif len(stock_code) == 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for field_one in field:
                try:
                    result_dict[field_one] = market_data[field_one].ix[stock_code[0], end]
                except:
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
                index = market_data.ix[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data[field[0]].ix[stock][index]
            return pd.DataFrame(result_dict)
        # （６）代码-n，字段-n，时间-1,  return dataframe 行-字段，列-代码
        elif len(stock_code) > 1 and len(field) > 1 and (start == end) and count == -1:
            result_dict = {}
            for stock in stock_code:
                try:
                    result_dict[stock] = market_data.ix[stock].ix[end]
                except:
                    result_dict[stock] = pd.Series()
            return pd.DataFrame(result_dict).ix[field]
        # （７）代码-1，字段-n，时间-n,  return dataframe 行-timestamp，列-字段
        elif len(stock_code) == 1 and len(field) > 1 and (start != end) and count == -1:
            index = market_data.ix[stock_code[0]].index
            index = index[index <= end]
            index = index[index >= start]
            return market_data.ix[stock_code[0]][field].ix[index]
        # 代码-n，字段-n，时间-n,  return dataframe 行-代码-timestamp(多层索引)，列-字段
        else:
            result_dict = {}
            for stock in stock_code:
                index = market_data.ix[stock].index
                index = index[index <= end]
                index = index[index >= start]
                result_dict[stock] = market_data.ix[stock][field].ix[index]
            return pd.concat(result_dict, keys=stock_code)

    def get_end_timestamp(self, benchmark, interval=Interval.DAILY.value):
        if interval == Interval.DAILY.value:
            db_name = DatabaseName.MARKET_DATA_DAILY.value

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
    aa = GetData()
    stock_list = ['000300.SH', '000001.SZ', '000002.SZ', '600000.SH', '600001.SH']
    daily_data = aa.get_all_market_data(stock_code=stock_list,
                                        field=["open", "high", "low", "close", "volume", "amount"],
                                        start="2005-01-04",
                                        end="2008-02-22",
                                        interval=Interval.DAILY.value)
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
