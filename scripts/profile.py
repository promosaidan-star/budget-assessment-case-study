import sys, glob, os
import pandas as pd
d = sys.argv[1]
for f in sorted(glob.glob(os.path.join(d, "*.xlsx"))):
    print("=" * 100); print(os.path.basename(f))
    xl = pd.ExcelFile(f, engine="openpyxl")
    for s in xl.sheet_names:
        df = xl.parse(s, header=None, nrows=8)
        full = xl.parse(s)
        print("--- sheet:", s, "| shape:", full.shape)
        print(df.to_string(max_cols=30, max_colwidth=28))
        print("dtypes:"); print(full.dtypes.to_string())
        print("nulls:"); print(full.isna().sum().to_string())
        print("nunique:"); print(full.nunique().to_string())
