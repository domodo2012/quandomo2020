# -*- coding: utf-8 -*-
"""
向mongodb中写入基础数据（未完成）
"""

from os import listdir, path
from pandas import read_csv, DataFrame
from re import sub
from json import loads

from data_center.mongodb_conn import MongoConn
from core.const import DatabaseName


column_name_list = []
with open('./backtest_data/financial_data/financial_data_index_df.txt') as column:
    for i in column.readlines():
        column_name_list.append(i.strip("\n"))
print(len(column_name_list))

exist_collection_list = []
with open('./backtest_data/financial_data/exist_collection.txt') as exist_collection:
    for i in exist_collection.readlines():
        exist_collection_list.append(i.strip("\n"))

db_name = DatabaseName.FINANCIAL_DATA.value
my_conn = MongoConn()
db = my_conn.connect_db(db_name)
root_path = "./backtest_data/financial_data/"
market_list = ["SZ"]

for market in market_list:
    files = listdir(root_path + market)

    # 记录完成数量
    insert_num = 0

    # 防止内存不足，控制每次写入数量
    for file_num in files[1400:]:
        if not path.isdir(file_num):
            insert_num += 1
            collection_data = read_csv(root_path + market + "/" + file_num, sep=",", encoding="utf8")
            collection_name = str(sub(r"\D", "", file_num)) + "." + market
            # print(collection_name)

            # 清除掉多余的时间戳
            collection_data_wash = DataFrame(collection_data, columns=column_name_list)
            # db_admin.command('shardcollection', db_name + '.' + collection_name, key={'_id': 1})

            # 根据时间戳排序
            collection_data_wash = collection_data_wash.sort_values(axis=0, ascending=True, by="timetag")
            collection_data_list = loads(collection_data_wash.T.to_json()).values()

            # 根据时间戳排序
            collection_data_list_sort = sorted(collection_data_list, key=lambda x: x.__getitem__("timetag"))

            # 插入数据
            if collection_data_list_sort:
                my_conn.insert(db_name, collection_name, collection_data_list_sort)
