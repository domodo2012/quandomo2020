"""
将一个 dataframe 转换成三重嵌套的 dict，采用三种不同的方法，完全不采用 dataframe，而是对纯 dict 进行处理的方式用时最少
method 1 -- sum of time:  7.329394340515137
method 2 -- sum of time:  1.2476661205291748
method 3 -- sum of time:  0.05086255073547363
"""
import pickle
import pandas as pd
import json
import time


if __name__ == "__main__":
    start = time.time()
    data_dict = {}
    # df = pickle.load(open("d:/download/data_df.pkl", "rb"))
    df = pd.read_pickle(r"d:/download/data_df.pkl")
    grouped = df.groupby("S_INFO_WINDCODE")
    for name, group in grouped:
        time_dict = {}
        group.sort_values(by="EX_DATE")
        for _, row in group.iterrows():
            element_dict = dict(row)
            del element_dict["S_INFO_WINDCODE"]
            del element_dict["EX_DATE"]
            time_dict[str(row["EX_DATE"])] = element_dict
        data_dict[name] = time_dict
    end = time.time()
    print("method 1 -- sum of time: ", end - start)
    print("method 1 -- data_dict size {0}".format(len(data_dict)))
    # json.dump(data_dict, open("d:/download/my_data_dict.json", "w"), indent=4, ensure_ascii=False)

    start = time.time()
    data_df = pd.read_pickle(r'd:/download/data_df.pkl')
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
    end = time.time()
    print("method 2 -- sum of time: ", end - start)
    print("method 2 -- data_dict size {0}".format(len(data_dict)))

    start = time.time()
    data = pd.read_pickle(r'd:/download/data_list.pkl')
    ssym = ''
    data_dict = {}
    cur_dict = {}
    for datal in data:
        if ssym != datal[0]:
            if ssym not in data_dict.keys():
                data_dict[datal[0]] = {}
            else:
                data_dict[ssym] = cur_dict
                data_dict[datal[0]] = {}
                cur_dict = {}
            ssym = datal[0]

            cur_dict[datal[1]] = {
                'CASH_DIVIDEND_RATIO': datal[2],
                'BONUS_SHARE_RATIO': datal[3],
                'RIGHTSISSUE_RATIO': datal[4],
                'RIGHTSISSUE_PRICE': datal[5],
                'CONVERSED_RATIO': datal[6]
            }
        else:
            cur_dict[datal[1]] = {
                'CASH_DIVIDEND_RATIO': datal[2],
                'BONUS_SHARE_RATIO': datal[3],
                'RIGHTSISSUE_RATIO': datal[4],
                'RIGHTSISSUE_PRICE': datal[5],
                'CONVERSED_RATIO': datal[6]
            }
    end = time.time()
    print("method 3 -- sum of time: ", end - start)
    print("method 3 -- data_dict size {0}".format(len(data_dict)))
