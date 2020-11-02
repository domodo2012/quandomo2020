import vaex
import numpy as np
import pandas as pd

for i, chunk in enumerate(vaex.read_csv(r'D:\python projects\quandomo\data_center\data\market\ASHAREEODPRICES.csv', chunksize=100_000)):
    df_chunk = vaex.from_pandas(chunk, copy_index=False)
    export_path = f'D:/python projects/quandomo/data_center/data/market/part_{i}.hdf5'
    df_chunk.export_hdf5(export_path)

df = vaex.open('D:/python projects/quandomo/data_center/data/market/part*')
df.export_hdf5('D:/python projects/quandomo/data_center/data/market/Final.hdf5')
