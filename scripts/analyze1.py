import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from load import load
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
s, w, braw = load(sys.argv[1])
# ---- budget tidy
hdr = braw.iloc[4]
b = braw.iloc[5:].copy()
print("col19 'a' values:", b[19].value_counts(dropna=False).to_dict(), "| col32 'x':", b[32].value_counts(dropna=False).to_dict())
print("budget rows with null customer:"); print(b[b[1].isna()].to_string())
dims = b[[1,2,3,4,5,6]]; dims.columns = ["Customer","Item","Business","Channel","BrandPL","ItemGroup"]
cases = b[list(range(7,19))].apply(pd.to_numeric, errors="coerce"); dollars = b[list(range(20,32))].apply(pd.to_numeric, errors="coerce")
print("non-numeric cases:", cases.isna().sum().sum(), "dollars:", dollars.isna().sum().sum())
for c in dims.columns[2:]: print("\n## budget", c); print(dims[c].value_counts(dropna=False).to_string())
print("\nbudget customers types:", dims["Customer"].map(type).value_counts().to_dict(), "items:", dims["Item"].map(type).value_counts().to_dict())
print("non-numeric customers:", [x for x in dims["Customer"].unique() if not str(x).isdigit()][:30])
print("non-numeric items:", [x for x in dims["Item"].unique() if not str(x).isdigit()][:30])
bm = pd.DataFrame({"cases": cases.sum().values, "dollars": dollars.sum().values}, index=range(1,13))
print("\n## budget by month"); print(bm.to_string()); print("TOTAL", bm.sum().to_dict())
print("dup budget cust/item rows:", dims.duplicated(["Customer","Item"]).sum())
# ---- history totals
s["Year"]=s["Year"].astype(int); s["Month"]=s["Month"].astype(int)
for c in ["Quantity","Total Amt","Lbs","LBSperCase"]: s[c]=pd.to_numeric(s[c])
print("\n## history by year"); y = s.groupby("Year")[["Quantity","Total Amt","Lbs"]].sum(); y["$/lb"]=y["Total Amt"]/y["Lbs"]; y["$/case"]=y["Total Amt"]/y["Quantity"]; print(y.to_string())
print("\n## zero-amount rows by year (qty>0):"); z = s[(s["Total Amt"]==0)]; print(z.groupby("Year")[["Quantity","Lbs"]].agg(["count","sum"]).to_string())
print(z.groupby(["Channel","Branded/PL"],dropna=False).size().to_string())
print("\n## zero LBSperCase rows:"); zl = s[s["LBSperCase"]==0]; print(zl.groupby(["ItemCode","Item Group"])[["Quantity","Total Amt"]].agg(["count","sum"]).to_string())
print("\n## negative rows"); print(s[s["Total Amt"]<0].to_string())
print("\n## null brand rows"); print(s[s["Branded/PL"].isna()].to_string())
print("\n## Distributor / Other rows"); print(s[(s["Channel"]=="Distributor")|(s["Item Group"]=="Other")].to_string())
print("\n## channel x brand revenue by year"); print(s.pivot_table(index=["Channel","Branded/PL"],columns="Year",values="Total Amt",aggfunc="sum",dropna=False).to_string())
print("\n## business x year"); print(s.pivot_table(index=["Business Line"],columns="Year",values=["Total Amt","Lbs"],aggfunc="sum").to_string())
# budget dims
dd = pd.concat([dims.reset_index(drop=True), pd.Series(cases.sum(axis=1).values,name="cases"), pd.Series(dollars.sum(axis=1).values,name="dollars")],axis=1)
print("\n## budget by business/channel/brand"); print(dd.groupby(["Business","Channel","BrandPL"],dropna=False)[["cases","dollars"]].sum().to_string())
print("\n## budget by item group"); print(dd.groupby(["ItemGroup"],dropna=False)[["cases","dollars"]].sum().to_string())
print("\n## hist by item group x year"); print(s.pivot_table(index="Item Group",columns="Year",values="Total Amt",aggfunc="sum").to_string())
# item codes join check
si = set(s["ItemCode"].astype(str)); bi = set(dd["Item"].dropna().astype(str)); wi=set(w["ItemCode"].dropna().astype(str))
print("\nbudget items:",len(bi),"in sales:",len(bi&si),"in weights:",len(bi&wi),"not in weights:",sorted(bi-wi)[:30], "not in sales:", sorted(bi-si)[:40])
sc = set(s["Customer code"].astype(str)); bc = set(dd["Customer"].dropna().astype(str))
print("budget customers:",len(bc),"in sales:",len(bc&sc),"new:",len(bc-sc))
new = dd[~dd["Customer"].astype(str).isin(sc)]
print("budget $ from customers never seen in history:", new["dollars"].sum(), "rows", len(new))
c20 = set(s[s["Year"]==2020]["Customer code"].astype(str))
print("budget $ from customers with no 2020 sales:", dd[~dd["Customer"].astype(str).isin(c20)]["dollars"].sum())
k20 = set(s[s["Year"]==2020]["Customer code"].astype(str)+":"+s[s["Year"]==2020]["ItemCode"].astype(str))
dd["key"]=dd["Customer"].astype(str)+":"+dd["Item"].astype(str)
print("budget $ from cust:item combos with no 2020 sales:", dd[~dd["key"].isin(k20)]["dollars"].sum())
