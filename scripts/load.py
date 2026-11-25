import os, pandas as pd, numpy as np
def load(d):
    s = pd.read_excel(os.path.join(d, "Assignment-HistoricalSales.xlsx"), sheet_name="Data", header=1, engine="openpyxl")
    s.columns = [str(c).strip() for c in s.columns]
    w = pd.read_excel(os.path.join(d, "Assignment-CaseWeights.xlsx"), sheet_name="Net Wt", header=2, engine="openpyxl")
    w.columns = ["ItemCode", "CaseWeight"]
    braw = pd.read_excel(os.path.join(d, "Assignment-Budget.xlsx"), sheet_name="Data", header=None, engine="openpyxl")
    return s, w, braw
