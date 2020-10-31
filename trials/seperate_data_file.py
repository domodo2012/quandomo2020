import os
import pandas as pd


# filename为文件路径，file_num为拆分后的文件行数
# 根据是否有表头执行不同程序，默认有表头的
def Data_split(filename, file_num, header=True):
    if header:
        # 设置每个文件需要有的行数,初始化为1000W
        chunksize = 10000
        data1 = pd.read_table(filename,chunksize=chunksize, sep=',', encoding='gbk')
        # print(data1)
        # num表示总行数
        num = 0
        for chunk in data1:
            num += len(chunk)
        # print(num)
        # chunksize表示每个文件需要分配到的行数
        chunksize = round(num/file_num+1)
        # print(chunksize)
        # 分离文件名与扩展名os.path.split(filename)
        head, tail = os.path.split(filename)
        data2 = pd.read_table(filename, chunksize=chunksize, sep=',', encoding='gbk')
        i = 0
        for chunk in data2:
            chunk.to_csv('{0}_{1}{2}'.format(head, i, tail), header=None, index=False)
            print('保存第{0}个数据'.format(i))
            i += 1
    else:
        # 获得每个文件需要的行数
        chunksize = 10000
        data1 = pd.read_table(filename, chunksize=chunksize, header=None, sep=',')
        num = 0
        for chunk in data1:
            num += len(chunk)
        chunksize = round(num/file_num+1)

        head, tail = os.path.split(filename)
        data2 = pd.read_table(filename, chunksize=chunksize, header=None, sep=',')
        i = 0
        for chunk in data2:
            chunk.to_csv('{0}_{1}{2}'.format(head, i, tail), header=None, index=False)
            print('保存第{0}个数据'.format(i))
            i += 1


filename = r'D:\python projects\quandomo\data_center\data\market\AINDEXEODPRICES.csv'
file_num = 3

# num为拆分为的文件个数
Data_split(filename, file_num, header=True)
