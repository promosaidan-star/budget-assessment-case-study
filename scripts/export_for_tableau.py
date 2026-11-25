"""Shape the clean model into flat CSVs for Tableau.

Usage: python -I export_for_tableau.py <materials_dir> <tableau_data_dir>
  case_sales.csv          one row per sales line or budget cell (2018-2020 actuals + 2021 budget stacked)
  case_customers.csv      one row per customer (revenue by year, budget, step-up, status)
  case_summary.csv        small pre-calculated table behind the bridges, the customer share chart and the scenarios
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
from build_model import build

SALES_COLS = ["Date", "Period", "Month Num", "Quarter", "Half", "Scenario", "Customer", "Item", "Item Label", "Business", "Channel",
              "Brand Type", "Item Group", "State", "Customer Overlap", "Customer Status", "Customer Rank Band",
              "Top 15 Customer 2020", "Top 15 Item 2020", "Top 10 Item Budget Increase", "Top 15 Overlap Customer 2020",
              "Top 10 Cracker 2020", "Cases", "Revenue", "Pounds"]
CUST_COLS = ["Customer", "Channel", "State", "Customer Overlap", "Customer Status", "Step-up Group", "Customer Count",
             "Revenue 2018", "Revenue 2019", "Revenue 2020", "Budget 2021", "Step-up vs 2020", "Budget Above Best Year"]
SUM_COLS = ["Exhibit", "Label", "Sort Order", "Key", "Revenue", "Label Revenue", "Share of Revenue"]


def pvm(d, p0, p1):
    """Price / volume / mix between two periods.
    Volume = change in total pounds, valued at the old average price per lb.
    Price  = like-for-like price change on items sold in both periods, valued at the new pounds.
    Mix    = whatever is left: shift between items, plus new and dropped items."""
    g = d[d.Period.isin([p0, p1])].groupby(["Item", "Period"])[["Revenue", "Pounds"]].sum().unstack("Period").fillna(0)
    A0, A1, L0, L1 = g[("Revenue", p0)], g[("Revenue", p1)], g[("Pounds", p0)], g[("Pounds", p1)]
    both = (L0 > 0) & (L1 > 0)
    price = (((A1 / L1) - (A0 / L0)) * L1)[both].sum()
    vol = (L1.sum() - L0.sum()) * A0.sum() / L0.sum()
    return vol, price, (A1.sum() - A0.sum()) - vol - price


def bridge(name, steps):
    """Waterfall rows. steps: (label, kind, value). kind Actual/Budget = a total bar that starts at zero;
    delta = a change from the running level. Each change is three stacked pieces: an invisible Spacer up to the
    lower edge of the step, the change itself, then an invisible piece that holds the label.
    Sort Order sits on one piece only so SUM(Sort Order) orders the steps."""
    rows, level = [], 0.0
    pad = 0.19 * max(v for _, kind, v in steps if kind != "delta")     # width of the blank piece that carries a step's label
    for i, (label, kind, v) in enumerate(steps, 1):
        if kind == "delta":
            rows.append((name, label, 0, "Spacer", min(level, level + v), None, None))
            rows.append((name, label, i, "Increase" if v >= 0 else "Decrease", abs(v), None, None))
            rows.append((name, label, 0, "(label)", pad, v, None))     # third piece, also invisible: its label sits beside the step
            level += v
        else:
            rows.append((name, label, i, kind, v, v, None))
            level = v
    return rows


def summary(d, t):
    tot = d.groupby("Period").Revenue.sum()
    rows = []
    # 1. price / volume / mix: 2019 -> 2020 -> 2021 budget
    v1, p1, m1 = pvm(d, "2019", "2020")
    v2, p2, m2 = pvm(d, "2020", "2021 Budget")
    rows += bridge("PVM bridge", [
        ("2019 actual", "Actual", tot["2019"]), ("2020: volume", "delta", v1), ("2020: price", "delta", p1), ("2020: mix", "delta", m1),
        ("2020 actual", "Actual", tot["2020"]), ("2021: volume", "delta", v2), ("2021: price", "delta", p2), ("2021: mix", "delta", m2),
        ("2021 budget", "Budget", tot["2021 Budget"])])
    # 2. 2020 -> 2021 budget by customer status
    ch = t["Budget 2021"] - t["Revenue 2020"]
    st = t["Customer Status"]
    act = st == "Active in 2020"
    rows += bridge("Customer bridge", [
        ("2020 actual", "Actual", tot["2020"]),
        ("Active: budgeted up", "delta", ch[act & (ch > 0)].sum()),
        ("Active: budgeted down", "delta", ch[act & (ch <= 0)].sum()),
        ("Lapsed: budgeted back", "delta", ch[st == "Lapsed in 2020"].sum()),
        ("New: no sales history", "delta", ch[st == "New in 2021"].sum()),
        ("No customer named", "delta", ch[st == "No customer"].sum()),
        ("Left out of budget", "delta", ch[st == "Not in budget"].sum()),
        ("2021 budget", "Budget", tot["2021 Budget"])])
    # 3. per item: the 2020 -> 2021 budget change split into price (at budget pounds) and volume (the rest)
    g = d[d.Period.isin(["2020", "2021 Budget"])].groupby(["Item Label", "Period"])[["Revenue", "Pounds"]].sum().unstack("Period").fillna(0)
    A0, A1, L0, L1 = g[("Revenue", "2020")], g[("Revenue", "2021 Budget")], g[("Pounds", "2020")], g[("Pounds", "2021 Budget")]
    both = (L0 > 0) & (L1 > 0)
    pr = (((A1 / L1) - (A0 / L0)) * L1).where(both, 0.0)
    vo = (A1 - A0) - pr
    for lab in (A1 - A0).abs().nlargest(8).index:
        rows.append(("Item price volume", lab, 0, "Volume", vo[lab], None, None))
        rows.append(("Item price volume", lab, 0, "Price", pr[lab], None, None))
    # 4. share of revenue held by the largest customers
    for per in ("2019", "2020", "2021 Budget"):
        r = d[(d.Period == per) & (d.Customer != "UNASSIGNED")].groupby("Customer").Revenue.sum().sort_values(ascending=False)
        for i, n in enumerate((1, 5, 10, 25, 50), 1):
            rows.append(("Customer share", f"Top {n}", i, per, None, None, r.head(n).sum() / tot[per]))
    # 4b. tiers: share of revenue from the top 10%, next 40% and bottom 50% of the customers (or items) that sold
    periods = ("2018", "2019", "2020", "2021 Budget")
    for exhibit, by in (("Customer tiers", "Customer"), ("Item tiers", "Item")):
        for i, per in enumerate(periods, 1):
            r = d[(d.Period == per) & (d.Customer != "UNASSIGNED")].groupby(by).Revenue.sum() if by == "Customer" \
                else d[d.Period == per].groupby(by).Revenue.sum()
            r = r[r > 0].sort_values(ascending=False)
            k10, k50 = round(len(r) * 0.1), round(len(r) * 0.5)
            for name, part in (("Top 10%", r.iloc[:k10]), ("Next 40%", r.iloc[k10:k50]), ("Bottom 50%", r.iloc[k50:])):
                rows.append((exhibit, per, i, name, None, None, part.sum() / r.sum()))
    # 4c. mix shares the budget reverses: Retail, Private Label and Cookies as a share of revenue
    for i, per in enumerate(periods, 1):
        dp = d[d.Period == per]
        for name, col in (("Retail", "Channel"), ("Private Label", "Brand Type"), ("Cookies", "Item Group")):
            rows.append(("Mix shares", per, i, name, None, None, dp.loc[dp[col] == name, "Revenue"].sum() / tot[per]))
    # 5. scenarios for 2021
    q4 = d[d.Quarter == "Q4"].groupby("Period").Revenue.sum()
    rec = q4["2020"] / q4["2019"]
    new = t.loc[st == "New in 2021", "Budget 2021"].sum()
    scen = [("2021 budget as submitted", "Budget", tot["2021 Budget"]),
            ("Without the 5 new customers", "Scenario", tot["2021 Budget"] - new),
            ("Each customer capped at its best year", "Scenario", tot["2021 Budget"] - t["Budget Above Best Year"].sum()),
            ("2019 at the Q4 2020 recovery rate", "Scenario", tot["2019"] * rec),
            ("2020 actual", "Actual", tot["2020"])]
    for i, (lab, ser, v) in enumerate(scen, 1):
        rows.append(("Scenarios", lab, i, ser, v, v, None))
    facts = dict(pvm_2019_2020=(v1, p1, m1), pvm_2020_budget=(v2, p2, m2), q4_recovery=rec, new_customer_budget=new)
    return pd.DataFrame(rows, columns=SUM_COLS), facts


def export(src, out):
    fs, bud, di, dc, _ = build(src)
    os.makedirs(out, exist_ok=True)
    a = fs[["Date", "Customer", "Item", "Business", "Channel", "BrandPL", "ItemGroup", "State", "Cases", "Amount", "Lbs"]].copy()
    a["Scenario"] = "Actual"; a["Period"] = a.Date.dt.year.astype(str)
    b = bud[["Date", "Customer", "Item", "Business", "Channel", "BrandPL", "ItemGroup", "Cases", "Amount", "Lbs"]].copy()
    b = b[(b.Cases != 0) | (b.Amount != 0)]                       # drop empty budget cells
    b["Scenario"] = "Budget"; b["Period"] = "2021 Budget"; b["State"] = b.Customer.map(dc.set_index("Customer").State)
    d = pd.concat([a, b], ignore_index=True)
    d["Channel"] = d.Channel.replace({"Distributor": "Food Service"})    # 12 rows, $61K: distributors resell to food service
    d["Brand Type"] = d.BrandPL.map({"Branded": "Branded", "PL": "Private Label"}).fillna("Branded")
    d["Item Group"] = d.ItemGroup.where(d.ItemGroup.isin(["Crackers", "Cookies", "Crisps", "Muffins"]), "Other")
    d["Month Num"] = d.Date.dt.month; d["Quarter"] = "Q" + d.Date.dt.quarter.astype(str)
    d["Half"] = np.where(d.Date.dt.month <= 6, "H1", "H2")
    d["Item Label"] = d.Item + " " + d["Item Group"]
    d = d.rename(columns={"Amount": "Revenue", "Lbs": "Pounds"}); d["Pounds"] = d.Pounds.fillna(0)

    # ---- customer level
    t = d.pivot_table(index="Customer", columns="Period", values="Revenue", aggfunc="sum").reindex(columns=["2018", "2019", "2020", "2021 Budget"]).fillna(0)
    t.columns = ["Revenue 2018", "Revenue 2019", "Revenue 2020", "Budget 2021"]
    nbiz = fs.groupby("Customer").Business.nunique()
    t["Customer Overlap"] = np.where(t.index.map(lambda c: nbiz.get(c, 0) > 1), "Both A and B", "One business")
    hist = t[["Revenue 2018", "Revenue 2019", "Revenue 2020"]]
    t["Customer Status"] = np.select(                             # short member names: Tableau legends cut long ones
        [t.index == "UNASSIGNED", t["Budget 2021"] <= 0, hist.sum(axis=1) <= 0, t["Revenue 2020"] <= 0],
        ["No customer", "Not in budget", "New in 2021", "Lapsed in 2020"], "Active in 2020")
    t["Step-up vs 2020"] = t["Budget 2021"] - t["Revenue 2020"]
    t["Budget Above Best Year"] = (t["Budget 2021"] - hist.max(axis=1)).clip(lower=0)
    t["Step-up Group"] = np.where(t["Step-up vs 2020"].rank(ascending=False, method="first") <= 15, "Top 15 step-ups", "All other customers")
    ch = d.groupby("Customer").Channel.first(); st = dc.set_index("Customer").State
    t["Channel"] = ch; t["State"] = st.reindex(t.index); t["Customer Count"] = 1
    t = t.reset_index()

    # ---- flags back onto the row-level file
    m = t.set_index("Customer")
    d["Customer Overlap"] = d.Customer.map(m["Customer Overlap"]); d["Customer Status"] = d.Customer.map(m["Customer Status"])
    rk = d.groupby(["Period", "Customer"]).Revenue.sum().groupby(level=0).rank(ascending=False, method="first")
    band = pd.cut(rk, [0, 10, 25, 50, 1e9], labels=["1. Top 10", "2. Next 15", "3. Next 25", "4. All others"]).astype(str)
    d["Customer Rank Band"] = pd.MultiIndex.from_frame(d[["Period", "Customer"]]).map(band)
    by_item = d.pivot_table(index="Item", columns="Period", values="Revenue", aggfunc="sum").fillna(0)
    top_c = set(m["Revenue 2020"].nlargest(15).index)
    top_i = set(by_item["2020"].nlargest(15).index)
    top_up = set((by_item["2021 Budget"] - by_item["2020"]).nlargest(10).index)
    top_o = set(m[m["Customer Overlap"] == "Both A and B"]["Revenue 2020"].nlargest(15).index)
    d["Top 15 Customer 2020"] = np.where(d.Customer.isin(top_c), "Top 15", "Other")
    d["Top 15 Item 2020"] = np.where(d.Item.isin(top_i), "Top 15", "Other")
    d["Top 10 Item Budget Increase"] = np.where(d.Item.isin(top_up), "Top 10", "Other")
    d["Top 15 Overlap Customer 2020"] = np.where(d.Customer.isin(top_o), "Top 15", "Other")
    # the ten largest cracker items by 2020 revenue, for the crackers page
    top_k = set(d[(d["Item Group"] == "Crackers") & (d.Period == "2020")].groupby("Item").Revenue.sum().nlargest(10).index)
    d["Top 10 Cracker 2020"] = np.where(d.Item.isin(top_k), "Top 10", "Other")
    d["Date"] = d.Date.dt.strftime("%Y-%m-%d")
    d[SALES_COLS].to_csv(os.path.join(out, "case_sales.csv"), index=False)
    t[CUST_COLS].to_csv(os.path.join(out, "case_customers.csv"), index=False)
    sm, facts = summary(d, t)
    sm.to_csv(os.path.join(out, "case_summary.csv"), index=False)
    return d, t, sm, facts


if __name__ == "__main__":
    d, t, sm, facts = export(sys.argv[1], sys.argv[2])
    pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    print("rows", len(d), "customers", len(t), "summary rows", len(sm))
    print((d.groupby("Period")[["Revenue", "Pounds", "Cases"]].sum() / 1e6).round(2).to_string())
    print(t.groupby("Customer Status")[["Customer Count", "Revenue 2020", "Budget 2021", "Budget Above Best Year"]].sum().round(0).to_string())
    show = sm.copy(); show["Revenue"] = show.Revenue / 1e6; show["Label Revenue"] = show["Label Revenue"] / 1e6
    print(show.to_string())
    print({k: (tuple(round(x / 1e6, 2) for x in v) if isinstance(v, tuple) else round(float(v), 4)) for k, v in facts.items()})
    print((d.groupby(["Period", "Half"]).Revenue.sum() / 1e6).round(2).unstack().to_string())
    print((d.groupby(["Period", "Customer Overlap"]).Revenue.sum() / 1e6).round(2).unstack().to_string())
    by = d.pivot_table(index="Item Label", columns="Period", values="Revenue", aggfunc="sum").fillna(0)
    by["up"] = by["2021 Budget"] - by["2020"]
    print((by.nlargest(10, "up") / 1e6).round(2).to_string())
    print("top 10 item increases total", round(by.up.nlargest(10).sum() / 1e6, 2), "| total increase", round(by.up.sum() / 1e6, 2))
    print("2020 top 10 items: share of 2020", round(by["2020"].nlargest(10).sum() / by["2020"].sum(), 3),
          "share of budget", round(by.loc[by["2020"].nlargest(10).index, "2021 Budget"].sum() / by["2021 Budget"].sum(), 3))
    print("nulls:", d[SALES_COLS].isna().sum()[lambda s: s > 0].to_dict(), t[CUST_COLS].isna().sum()[lambda s: s > 0].to_dict())
