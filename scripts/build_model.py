"""Clean the three client extracts into a star schema (CSV) for Power BI. Usage: python -I build_model.py <materials_dir> <out_dir>"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from load import load

def norm_code(x):
    """Item/customer codes arrive as int, float or zero-padded text; make them one plain text key."""
    if pd.isna(x): return "UNASSIGNED"
    t = str(x).strip()
    if t.endswith(".0"): t = t[:-2]
    return t.lstrip("0") or "0"

def build(src):
    s, w, braw = load(src)
    # ---------- sales
    s = s.copy()  # one fully identical row exists, but the extract is order-level (1,777 repeated customer:item:month keys), so it is kept
    s["Item"] = s["ItemCode"].map(norm_code); s["Customer"] = s["Customer code"].map(norm_code)
    s["Date"] = pd.to_datetime(dict(year=s["Year"].astype(int), month=s["Month"].astype(int), day=1))
    for c in ["Quantity", "Total Amt", "LBSperCase", "Lbs"]: s[c] = pd.to_numeric(s[c])
    s["Business"] = s["Business Line"].str.strip()
    s["ChannelRaw"] = s["Channel"].str.strip()
    s["Channel"] = s["ChannelRaw"].replace({"Retail Private Label": "Retail"})   # budget only knows Retail / Food Service
    # ---------- weights
    w = w.dropna(subset=["ItemCode"]).copy(); w["Item"] = w["ItemCode"].map(norm_code); w["CaseWeight"] = pd.to_numeric(w["CaseWeight"])
    wmap = w.drop_duplicates("Item").set_index("Item")["CaseWeight"]
    # sales extract carries a 2-decimal weight; the ops Excel is rounded to 1 decimal. Prefer sales precision, fall back to the Excel.
    s_w = s[s["LBSperCase"] > 0].groupby("Item")["LBSperCase"].first()
    best_w = s_w.combine_first(wmap[wmap > 0])
    s["LbsPerCase"] = s["Item"].map(best_w)
    s["LbsClean"] = s["Quantity"] * s["LbsPerCase"]
    # ---------- budget (wide -> long)
    b = braw.iloc[5:].reset_index(drop=True)
    dims = b[[1, 2, 3, 4, 5, 6]].copy(); dims.columns = ["Customer", "Item", "Business", "Channel", "BrandPL", "ItemGroup"]
    dims["Customer"] = dims["Customer"].map(norm_code); dims["Item"] = dims["Item"].map(norm_code)
    dims["BrandPL"] = dims["BrandPL"].replace({"Private Label": "PL"})
    recs = []
    for m in range(12):
        t = dims.copy(); t["Date"] = pd.Timestamp(2021, m + 1, 1)
        t["Cases"] = pd.to_numeric(b[7 + m]).values; t["Amount"] = pd.to_numeric(b[20 + m]).values
        recs.append(t)
    bud = pd.concat(recs, ignore_index=True)
    bud["LbsPerCase"] = bud["Item"].map(best_w); bud["Lbs"] = bud["Cases"] * bud["LbsPerCase"]
    # ---------- dims
    item_attr = s.groupby("Item").agg(ItemGroup=("Item Group", "first"), BrandPL=("Branded/PL", lambda x: x.dropna().iloc[0] if x.notna().any() else None), Business=("Business", "first"))
    bud_item = dims.groupby("Item").agg(ItemGroup=("ItemGroup", "first"), BrandPL=("BrandPL", "first"), Business=("Business", "first"))
    dim_item = item_attr.combine_first(bud_item); dim_item["LbsPerCase"] = best_w.reindex(dim_item.index); dim_item["InWeightFile"] = dim_item.index.isin(wmap.index)
    s["BrandPL"] = s["Item"].map(dim_item["BrandPL"]); s["ItemGroup"] = s["Item"].map(dim_item["ItemGroup"])
    last_state = s.dropna(subset=["StateS"]).sort_values("Date").groupby("Customer")["StateS"].last()
    cust = s.groupby("Customer").agg(Channel=("Channel", "first"), NBusiness=("Business", "nunique"))
    budc = dims.groupby("Customer").agg(Channel=("Channel", "first"), NBusiness=("Business", "nunique"))
    dim_cust = cust.combine_first(budc); dim_cust["State"] = last_state.reindex(dim_cust.index)
    both = s.groupby("Customer")["Business"].nunique()
    dim_cust["BuysBothBusinesses"] = dim_cust.index.map(lambda c: bool(both.get(c, 0) > 1))
    dim_cust["InHistory"] = dim_cust.index.isin(s["Customer"])
    fact_sales = s[["Date", "Customer", "Item", "Business", "Channel", "ChannelRaw", "BrandPL", "ItemGroup", "StateS", "Quantity", "Total Amt", "LbsClean"]].rename(columns={"Quantity": "Cases", "Total Amt": "Amount", "LbsClean": "Lbs", "StateS": "State"})
    return fact_sales, bud, dim_item.reset_index(), dim_cust.reset_index(), s

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
    fs, bud, di, dc, _ = build(src)
    fs.to_csv(os.path.join(out, "fact_sales.csv"), index=False); bud.to_csv(os.path.join(out, "fact_budget.csv"), index=False)
    di.to_csv(os.path.join(out, "dim_item.csv"), index=False); dc.to_csv(os.path.join(out, "dim_customer.csv"), index=False)
    d = pd.DataFrame({"Date": pd.date_range("2018-01-01", "2021-12-01", freq="MS")}); d["Year"] = d.Date.dt.year; d["MonthNum"] = d.Date.dt.month; d["Month"] = d.Date.dt.strftime("%b"); d["Quarter"] = "Q" + d.Date.dt.quarter.astype(str)
    d.to_csv(os.path.join(out, "dim_date.csv"), index=False)
    print("sales", fs.shape, round(fs.Amount.sum(), 2), "| budget", bud.shape, round(bud.Amount.sum(), 2), "| items", len(di), "| customers", len(dc))
    print("sales rows missing lbs:", fs.Lbs.isna().sum(), "| budget rows missing lbs:", bud.Lbs.isna().sum(), "budget $ w/o lbs:", bud[bud.Lbs.isna()].Amount.sum())
    print("items without weight:", di[di.LbsPerCase.isna()].to_dict("records"))
