import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from build_model import build
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
fs, bud, di, dc, _ = build(sys.argv[1])
fs["Year"] = fs.Date.dt.year; fs["M"] = fs.Date.dt.month
YRS = (2018, 2019, 2020)

def pv(df, by):
    g = df.groupby(by + ["Year"]).agg(Amt=("Amount", "sum"), Lbs=("Lbs", "sum")).unstack("Year")
    out = pd.DataFrame(index=g.index)
    for y in YRS:
        out[f"$M{y}"] = g[("Amt", y)] / 1e6; out[f"Mlb{y}"] = g[("Lbs", y)] / 1e6; out[f"$/lb{y}"] = g[("Amt", y)] / g[("Lbs", y)]
    out["lbs%19v18"] = (g[("Lbs", 2019)] / g[("Lbs", 2018)] - 1) * 100; out["lbs%20v19"] = (g[("Lbs", 2020)] / g[("Lbs", 2019)] - 1) * 100
    out["px%19v18"] = (out["$/lb2019"] / out["$/lb2018"] - 1) * 100; out["px%20v19"] = (out["$/lb2020"] / out["$/lb2019"] - 1) * 100
    return out

print("=== Q1 TOTAL"); fs["All"] = "All"; print(pv(fs, ["All"]).T.to_string())
for by in (["Channel"], ["BrandPL"], ["Business"], ["Channel", "BrandPL"], ["ItemGroup"], ["ItemGroup", "BrandPL"]):
    print("\n=== Q1/Q3 by", by); print(pv(fs, by).to_string())

# price / volume / mix bridge 2019 -> 2020 at item level
g = fs.groupby(["Item", "Year"]).agg(A=("Amount", "sum"), L=("Lbs", "sum")).unstack("Year").fillna(0)
A19, A20, L19, L20 = g[("A", 2019)], g[("A", 2020)], g[("L", 2019)], g[("L", 2020)]
both = (L19 > 0) & (L20 > 0)
p19 = (A19 / L19).where(both); p20 = (A20 / L20).where(both)
price = ((p20 - p19) * L20)[both].sum(); avg19 = A19.sum() / L19.sum()
vol = (L20.sum() - L19.sum()) * avg19; mix = (A20.sum() - A19.sum()) - price - vol
print(f"\n=== PVM 2019->2020: total {A20.sum()-A19.sum():,.0f} | volume {vol:,.0f} | price (like-for-like items) {price:,.0f} | mix + new/lost items {mix:,.0f}")

# Q2 concentration
for key in ("Customer", "Item"):
    for y in (2019, 2020):
        r = fs[fs.Year == y].groupby(key).Amount.sum().sort_values(ascending=False); r = r[r > 0]; c = r.cumsum() / r.sum()
        print(f"\n=== Q2 {key} {y}: n={len(r)} top1 {r.iloc[0]/r.sum():.1%} top5 {c.iloc[4]:.1%} top10 {c.iloc[9]:.1%} top20 {c.iloc[19]:.1%} | n for 80% = {(c<0.8).sum()+1} | n for 95% = {(c<0.95).sum()+1} | under $10K: {(r<10000).sum()}")
t = fs.pivot_table(index="Customer", columns="Year", values="Amount", aggfunc="sum").fillna(0)
t = t.join(bud.groupby("Customer").Amount.sum().rename("Bud21"), how="outer").fillna(0)
t = t.join(dc.set_index("Customer")[["Channel", "State", "BuysBothBusinesses"]])
NUM = [2018, 2019, 2020, "Bud21"]
print("\n=== top 20 customers by 2019 rev ($K)"); x = t.sort_values(2019, ascending=False).head(20).copy(); x[NUM] /= 1e3
x["20v19%"] = (x[2020] / x[2019] - 1) * 100; x["B21v20%"] = (x["Bud21"] / x[2020] - 1) * 100; x["B21v19%"] = (x["Bud21"] / x[2019] - 1) * 100; print(x.to_string())
ti = fs.pivot_table(index="Item", columns="Year", values="Amount", aggfunc="sum").fillna(0)
ti = ti.join(bud.groupby("Item").Amount.sum().rename("Bud21"), how="outer").fillna(0).join(di.set_index("Item")[["ItemGroup", "BrandPL", "Business"]])
print("\n=== top 15 items by 2019 rev ($K)"); x = ti.sort_values(2019, ascending=False).head(15).copy(); x[NUM] /= 1e3; print(x.to_string())

# Q4 overlap between Business A and Business B
ov = fs.groupby("Customer").Business.nunique(); ovc = list(ov[ov > 1].index)
print(f"\n=== Q4 overlap customers (bought from both A and B, any year): {len(ovc)} of {fs.Customer.nunique()}")
o = fs[fs.Customer.isin(ovc)].pivot_table(index="Business", columns="Year", values="Amount", aggfunc="sum", margins=True); print((o / 1e6).to_string())
print("share of total revenue by year:", (fs[fs.Customer.isin(ovc)].groupby("Year").Amount.sum() / fs.groupby("Year").Amount.sum()).round(4).to_dict())
for y in YRS:
    fy = fs[fs.Year == y]; oy = fy.groupby("Customer").Business.nunique(); oyc = oy[oy > 1].index; r = fy[fy.Customer.isin(oyc)].Amount.sum()
    print(y, "same-year overlap customers:", len(oyc), "rev $M:", round(r / 1e6, 2), "share", round(r / fy.Amount.sum(), 4))
print("overlap by channel:", dc[dc.Customer.isin(ovc)].Channel.value_counts().to_dict())
print("budget $M on overlap customers:", round(bud[bud.Customer.isin(ovc)].Amount.sum() / 1e6, 2), "| customers budgeted in both A and B:", int((bud[bud.Amount > 0].groupby("Customer").Business.nunique() > 1).sum()))
xo = t.loc[ovc].sort_values(2019, ascending=False).head(12).copy(); xo[NUM] /= 1e3; print(xo.to_string())
bsplit = fs[fs.Customer.isin(ovc)].pivot_table(index="Customer", columns=["Year", "Business"], values="Amount", aggfunc="sum").fillna(0) / 1e3
print(bsplit.loc[xo.index].to_string())

# Budget stress test
print("\n=== BUDGET vs HISTORY by month ($M)")
m = fs.pivot_table(index="M", columns="Year", values="Amount", aggfunc="sum") / 1e6; m["Bud21"] = bud.groupby(bud.Date.dt.month).Amount.sum() / 1e6
m["B21v19%"] = (m.Bud21 / m[2019] - 1) * 100; m["B21v20%"] = (m.Bud21 / m[2020] - 1) * 100; m["hist max"] = m[[2018, 2019, 2020]].max(axis=1); print(m.to_string())
print("H2 share:", {str(c): round(m[c].iloc[6:].sum() / m[c].sum(), 3) for c in NUM}, "| Q4 share:", {str(c): round(m[c].iloc[9:].sum() / m[c].sum(), 3) for c in NUM})
for by in (["Business"], ["Channel"], ["BrandPL"], ["Channel", "BrandPL"], ["ItemGroup"]):
    h = fs.pivot_table(index=by, columns="Year", values=["Amount", "Lbs"], aggfunc="sum"); bb = bud.groupby(by).agg(Amount=("Amount", "sum"), Lbs=("Lbs", "sum"))
    o = pd.DataFrame({"$M19": h[("Amount", 2019)] / 1e6, "$M20": h[("Amount", 2020)] / 1e6, "$MB21": bb.Amount / 1e6, "Mlb19": h[("Lbs", 2019)] / 1e6, "Mlb20": h[("Lbs", 2020)] / 1e6, "MlbB21": bb.Lbs / 1e6})
    o["$/lb19"] = o["$M19"] / o.Mlb19; o["$/lb20"] = o["$M20"] / o.Mlb20; o["$/lbB21"] = o["$MB21"] / o.MlbB21
    o["B$v20%"] = (o["$MB21"] / o["$M20"] - 1) * 100; o["B$v19%"] = (o["$MB21"] / o["$M19"] - 1) * 100; o["Blbv20%"] = (o.MlbB21 / o.Mlb20 - 1) * 100; o["Bpxv20%"] = (o["$/lbB21"] / o["$/lb20"] - 1) * 100
    print("\n=== BUDGET vs HIST by", by); print(o.to_string())
print("\nTOTAL budget lbs M:", bud.Lbs.sum() / 1e6, "$/lb:", bud.Amount.sum() / bud.Lbs.sum(), "$/case:", bud.Amount.sum() / bud.Cases.sum())
t["gap20"] = t.Bud21 - t[2020]; t["gap19"] = t.Bud21 - t[2019]; t["peak"] = t[[2018, 2019, 2020]].max(axis=1); t["abovepeak"] = (t.Bud21 - t.peak).clip(lower=0)
K = NUM + ["gap20", "gap19", "peak", "abovepeak"]
print("\n=== customers with biggest budget step-up vs 2020 ($K)"); x = t.sort_values("gap20", ascending=False).head(20).copy(); x[K] /= 1e3; print(x.to_string())
print(f"\nbudget total {t.Bud21.sum()/1e6:.2f}M | sum of positive gaps vs 2020: {t.gap20.clip(lower=0).sum()/1e6:.2f}M, negative: {t.gap20.clip(upper=0).sum()/1e6:.2f}M | budget above each customer's best-ever year: {t.abovepeak.sum()/1e6:.2f}M across {(t.abovepeak>0).sum()} customers")
print("top 10 step-up customers share of total gap vs 2020:", round(t.gap20.sort_values(ascending=False).head(10).sum() / (t.Bud21.sum() - t[2020].sum()), 3))
print("customers with 2020 sales NOT in budget: n =", int(((t[2020] > 0) & (t.Bud21 == 0)).sum()), "2020 rev $M", round(t[(t.Bud21 == 0)][2020].sum() / 1e6, 2))
hist0 = t[[2018, 2019, 2020]].sum(axis=1) == 0
print("budgeted customers with zero 2020 revenue: n =", int(((t[2020] <= 0) & (t.Bud21 > 0)).sum()), "$M", round(t[(t[2020] <= 0)].Bud21.sum() / 1e6, 2), "| never in history: n =", int((hist0 & (t.Bud21 > 0)).sum()), "$M", round(t[hist0].Bud21.sum() / 1e6, 2))
nb = bud[bud.Customer.isin(t[hist0].index)].groupby(["Customer", "Item", "ItemGroup", "Channel", "BrandPL"]).Amount.sum(); print(nb.to_string())
# item-level: budget on customer:item pairs never sold
kh = set(fs.Customer + ":" + fs.Item); k20 = set(fs[fs.Year == 2020].Customer + ":" + fs[fs.Year == 2020].Item)
bk = bud.assign(key=bud.Customer + ":" + bud.Item)
print(f"budget $M on customer:item pairs never sold in 2018-20: {bk[~bk.key.isin(kh)].Amount.sum()/1e6:.2f} | not sold in 2020: {bk[~bk.key.isin(k20)].Amount.sum()/1e6:.2f}")
# customer churn
c18, c19, c20 = (set(fs[(fs.Year == y) & (fs.Amount > 0)].Customer) for y in YRS)
print(f"\nactive customers: 2018 {len(c18)}, 2019 {len(c19)}, 2020 {len(c20)} | lost 19->20: {len(c19-c20)} (2019 rev ${t.loc[list(c19-c20)][2019].sum()/1e6:.2f}M) | new in 2020: {len(c20-c19)} (2020 rev ${t.loc[list(c20-c19)][2020].sum()/1e6:.2f}M)")
# run-rate scenarios
q = fs.groupby([fs.Date.dt.quarter.rename("Q"), "Year"]).Amount.sum().unstack("Year") / 1e6; q["20v19"] = q[2020] / q[2019]; q["Bud21"] = bud.groupby(bud.Date.dt.quarter).Amount.sum() / 1e6; print("\n=== quarters $M"); print(q.to_string())
rec = q.loc[4, 2020] / q.loc[4, 2019]; h2 = (q.loc[3, 2020] + q.loc[4, 2020]) / (q.loc[3, 2019] + q.loc[4, 2019]); tot19 = fs[fs.Year == 2019].Amount.sum() / 1e6
print(f"Q4-20 / Q4-19 = {rec:.3f}; H2 = {h2:.3f}; 2019 x Q4 recovery = {tot19*rec:.1f}M; 2019 x H2 recovery = {tot19*h2:.1f}M; full 2019 = {tot19:.1f}M; budget {bud.Amount.sum()/1e6:.1f}M")
print("\n=== channel recovery by quarter, 2020 / 2019"); cq = fs.groupby(["Channel", fs.Date.dt.quarter.rename("Q"), "Year"]).Amount.sum().unstack("Year"); cq["r"] = cq[2020] / cq[2019]; print(cq["r"].unstack("Q").to_string())
print("\n=== channel x brand recovery by quarter, 2020 / 2019"); cq = fs.groupby(["Channel", "BrandPL", fs.Date.dt.quarter.rename("Q"), "Year"]).Amount.sum().unstack("Year"); cq["r"] = cq[2020] / cq[2019]; print(cq["r"].unstack("Q").to_string())
print("\n=== zero-$ shipments (free goods/samples) lbs share by year:", (fs[fs.Amount == 0].groupby("Year").Lbs.sum() / fs.groupby("Year").Lbs.sum()).round(4).to_dict())
print("\n=== state top 10 $M"); st = fs.pivot_table(index="State", columns="Year", values="Amount", aggfunc="sum").sort_values(2019, ascending=False).head(10) / 1e6; print(st.to_string())
