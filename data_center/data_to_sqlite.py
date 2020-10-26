# -*- coding: utf-8 -*-
"""
将从 wd 数据库取到并保存到本地的 csv 数据保存入本地 sqlite 数据库中
"""
import sqlite3
from os import listdir
from pandas import read_table
from const import *

unique_keys = {
    'AINDEXMEMBERS': 'S_INFO_WINDCODE,S_CON_INDATE',
    'AShareBalanceSheet': 'S_INFO_WINDCODE,REPORT_PERIOD',
    'ASHARECALENDAR': 'TRADE_DAYS,S_INFO_EXCHMARKET',
    'ASHARECAPITALIZATION': 'S_INFO_WINDCODE,CHANGE_DT',
    'AShareCashFlow': 'S_INFO_WINDCODE,REPORT_PERIOD',
    'AShareEXRightDividendRecord': 'S_INFO_WINDCODE,EX_DATE',
    'ASHAREINCOME': 'S_INFO_WINDCODE,REPORT_PERIOD',
    'ASHAREPROFITEXPRESS': 'S_INFO_WINDCODE,REPORT_PERIOD',
    'ASHAREPROFITNOTICE': 'S_INFO_WINDCODE,S_PROFITNOTICE_PERIOD,S_PROFITNOTICE_STYLE',
    'ASWSINDEXEOD': 'S_INFO_WINDCODE,TRADE_DT',
    'SWINDEXMEMBERS': 'S_INFO_WINDCODE,S_CON_INDATE'
}


def data_to_sqlite(root_path, sub_path, db_name):
    """将市场数据写入 sqlite 数据库中"""

    files = listdir(root_path + sub_path)
    if len(files) > 0:
        try:
            cx = sqlite3.connect(root_path + db_name)
            cur = cx.cursor()
            print('数据库 {0} 连接成功！'.format(db_name))
            print(' ')
        except BaseException:
            print('数据库 {0} 连接失败！'.format(db_name))
        else:
            with cx:
                for file in files:
                    if file.split('.')[-1] in ['csv']:      # 只处理 .csv 文件
                        file_name = file.split('.')[0]
                        chunksize = 100000
                        data = read_table(root_path + sub_path + file,
                                          chunksize=chunksize,
                                          sep=',',
                                          encoding='gbk',
                                          low_memory=False)
                        cnt = 0
                        for chunk in data:      # 取第一批数据时新建表、设定表属性
                            if cnt < 1:
                                columns = chunk.columns.tolist()
                                types = chunk.dtypes
                                field = []  # 用来接收字段名称的列表
                                table = []  # 用来接收字段名称和字段类型的列表
                                for item in columns:
                                    if 'int' in str(types[item])[:3]:
                                        char = item + ' INT'
                                    elif 'float' in str(types[item]):
                                        char = item + ' FLOAT'
                                    elif 'object' in str(types[item]):
                                        char = item + ' VARCHAR(255)'
                                    elif 'datetime' in str(types[item]):
                                        char = item + ' DATETIME'
                                    else:
                                        char = item + ' VARCHAR(255)'
                                    table.append(char)
                                    field.append(item)
                                tables = ','.join(table)
                                fields = ','.join(field)

                                # 新建与文件同名的表
                                table_sql = 'CREATE TABLE IF NOT EXISTS {0}' \
                                            '(id0 INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,{1},UNIQUE({2}));'. \
                                    format(file_name, tables, unique_keys[file_name])
                                cur.execute(table_sql)
                                cx.commit()

                                print('数据库 {0} 中表 {1} 已创建'.format(db_name, file_name))
                            cnt += 1

                            # 批量插入数据
                            s = ','.join(['?' for _ in range(len(chunk.columns))])
                            values = chunk.values.tolist()
                            insert_sql = 'insert or ignore into {0}({1}) values({2})'.format(file_name, fields, s)
                            cur.executemany(insert_sql, values)
                            cx.commit()
                        print('数据库 {0} 中表 {1} 数据导入完成'.format(db_name, file_name))
            # cur.close()
            # cx.close()


if __name__ == '__main__':
    root_path = "D:/python projects/quandomo/data_center/data/"
    db_name_list = [DATABASE_SQLITE_MARKET,
                    DATABASE_SQLITE_BASE,
                    DATABASE_SQLITE_FACTOR]
    sub_path = ['market/',
                'basic/',
                'factor/']

    # 数据写入 sqlite 中
    for ii in range(len(db_name_list)):
        data_to_sqlite(root_path, sub_path[ii], db_name_list[ii])
