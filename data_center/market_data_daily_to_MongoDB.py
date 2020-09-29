# -*- coding: utf-8 -*-

from os import listdir, path
from pandas import read_csv
from re import sub
from json import loads

from data_center.mongodb_conn import MongoConn
from core.const import DatabaseName


db_name = DatabaseName.MARKET_DATA_DAILY.value
my_conn = MongoConn()
db = my_conn.connect_db(db_name)
root_path = "D:/python projects/quandomo/data/"
market_list = ["SH", "SZ"]

for market in market_list:
    files = listdir(root_path + market)
    for file_num in range(len(files)):
        if not path.isdir(files[file_num]):
            # print(files[file_num])
            collection_data = read_csv(root_path + market + "/" + files[file_num], sep=",", encoding="utf8")
            collection_name = str(sub(r"\D", "", files[file_num])) + "." + market
            print(collection_name)

            collection_data = collection_data.sort_values(axis=0, ascending=True, by="timetag")
            collection_data_list = loads(collection_data.T.to_json()).values()
            collection_data_list_sort = sorted(collection_data_list, key=lambda x: x.__getitem__("timetag"))
            # print(collection_data_list)

            # 插入数据
            if collection_data_list_sort:
                my_conn.insert(db_name, collection_name, collection_data_list_sort)
