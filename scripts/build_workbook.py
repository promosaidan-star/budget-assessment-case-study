"""Generate case_study.twb (Tableau 2026.2) over tableau/data/*.csv.

Usage: python -I build_workbook.py <tableau_dir> [level] [out_name] [front dashboard index]
  level 0 = sheets only, 1 = + dashboards, 2 = + colors/labels/formats (default 2)
Re-run export_for_tableau.py first whenever the cleaning logic changes.
"""
import csv, os, sys, textwrap, uuid
from xml.sax.saxutils import quoteattr, escape

DT = {"s": "string", "r": "real", "i": "integer", "d": "date"}
# key -> (file, {column: type}). Order must match the CSV header.
SOURCES = {
    "sales": ("case_sales.csv", {
        "Date": "d", "Period": "s", "Month Num": "i", "Quarter": "s", "Half": "s", "Scenario": "s", "Customer": "s", "Item": "s",
        "Item Label": "s", "Business": "s", "Channel": "s", "Brand Type": "s", "Item Group": "s", "State": "s",
        "Customer Overlap": "s", "Customer Status": "s", "Customer Rank Band": "s", "Top 15 Customer 2020": "s",
        "Top 15 Item 2020": "s", "Top 10 Item Budget Increase": "s", "Top 15 Overlap Customer 2020": "s", "Top 10 Cracker 2020": "s",
        "Cases": "r", "Revenue": "r", "Pounds": "r"}),
    "customers": ("case_customers.csv", {
        "Customer": "s", "Channel": "s", "State": "s", "Customer Overlap": "s", "Customer Status": "s",
        "Step-up Group": "s", "Customer Count": "i", "Revenue 2018": "r", "Revenue 2019": "r", "Revenue 2020": "r",
        "Budget 2021": "r", "Step-up vs 2020": "r", "Budget Above Best Year": "r"}),
    "summary": ("case_summary.csv", {
        "Exhibit": "s", "Label": "s", "Sort Order": "i", "Key": "s", "Revenue": "r", "Label Revenue": "r", "Share of Revenue": "r"}),
}
DIM_INTS = {"Month Num"}                      # integers used as discrete dimensions
# Tableau number formats: the two commas before the decimal point scale the value to millions.
MONEY = 'c"$"#,##0,,.0M;-"$"#,##0,,.0M'
CALCS = {  # key -> {calc name: (caption, formula, format)}
    "sales": {
        "Calculation_9100000000000001": ("Price per lb", "SUM([Revenue])/SUM([Pounds])", 'c"$"#,##0.00;("$"#,##0.00)'),
        "Calculation_9100000000000002": ("Budget change vs 2020",
                                         "ZN(SUM(IF [Period]='2021 Budget' THEN [Revenue] END)) - ZN(SUM(IF [Period]='2020' THEN [Revenue] END))",
                                         MONEY),
        # customers with a positive sale in the period; UNASSIGNED marks budget rows with no customer
        "Calculation_9100000000000003": ("Customers", "COUNTD(IF [Revenue] > 0 AND [Customer] <> 'UNASSIGNED' THEN [Customer] END)", "n#,##0")},
    "customers": {},
    "summary": {},
}
FORMATS = {"Revenue": MONEY, "Revenue 2018": MONEY, "Revenue 2019": MONEY, "Revenue 2020": MONEY, "Budget 2021": MONEY,
           "Step-up vs 2020": 'c"$"#,##0,,.00M;-"$"#,##0,,.00M', "Budget Above Best Year": MONEY, "Label Revenue": MONEY,
           "Share of Revenue": "p0%", "Pounds": 'n#,##0,,.0M;-#,##0,,.0M', "Cases": 'n#,##0,,.0M;-#,##0,,.0M'}
# Colour rules for the whole workbook: grey = actual, red = budget or budget risk. No other field uses red.
GREY, RED = "#8a8a8a", "#e15759"
STATUS = {"Active in 2020": GREY, "Lapsed in 2020": "#f28e2b", "New in 2021": RED, "No customer": "#b07aa1", "Not in budget": "#bab0ac"}
OVERLAP = {"Both A and B": "#1f4e79", "One business": "#bab0ac"}
PALETTES = {  # key -> {field: {member: hex}}
    "sales": {
        "Period": {"2018": "#c9c9c9", "2019": "#9d9d9d", "2020": "#6b6b6b", "2021 Budget": RED},
        "Scenario": {"Actual": GREY, "Budget": RED},
        "Brand Type": {"Branded": "#4e79a7", "Private Label": "#f28e2b"},
        "Channel": {"Food Service": "#59a14f", "Retail": "#b07aa1"},
        "Business": {"Business A": "#4e79a7", "Business B": "#76b7b2"},
        "Customer Overlap": OVERLAP,
        "Customer Status": STATUS,
        "Item Group": {"Cookies": "#edc948", "Crackers": "#9c755f", "Crisps": "#76b7b2", "Muffins": "#b07aa1", "Other": "#bab0ac"},
    },
    "customers": {"Customer Status": STATUS, "Customer Overlap": OVERLAP},
    "summary": {
        # Spacer and (label) are the invisible pieces of a waterfall step, so they are white.
        "Key": {"Actual": GREY, "Budget": RED, "Scenario": "#f0a5a6", "Increase": "#4e79a7", "Decrease": "#f28e2b", "Spacer": "#ffffff",
                "(label)": "#ffffff",
                   "Volume": "#76b7b2", "Price": "#b07aa1", "2019": "#c9c9c9", "2020": "#6b6b6b", "2021 Budget": RED,
                "Top 10%": "#1f4e79", "Next 40%": "#6b9ac4", "Bottom 50%": "#c6dbef",
                "Retail": "#b07aa1", "Private Label": "#f28e2b", "Cookies": "#edc948"},
    },
}
LEVEL = 2


def q(s):
    return quoteattr(s)


def check_headers(data_dir):
    for fn, cols in SOURCES.values():
        with open(os.path.join(data_dir, fn), encoding="utf-8") as f:
            hdr = next(csv.reader(f))
        assert hdr == list(cols), f"{fn}: header {hdr} != {list(cols)}"


def col_meta(key, col):
    """<column> element for a base or calculated field, as it appears in the datasource and in sheet dependencies."""
    if col in CALCS[key]:
        cap, formula, fmt = CALCS[key][col]
        f = f" default-format={q(fmt)}" if LEVEL >= 2 else ""
        return (f"<column caption={q(cap)} datatype='real'{f} name='[{col}]' role='measure' type='quantitative'>"
                f"<calculation class='tableau' formula={q(formula)} /></column>")
    t = SOURCES[key][1][col]
    if col in DIM_INTS:
        return f"<column datatype='integer' name='[{col}]' role='dimension' type='ordinal' />"
    role = "measure" if t in "ri" else "dimension"
    typ = "quantitative" if t in "ri" else ("ordinal" if t == "d" else "nominal")
    f = f" default-format={q(FORMATS[col])}" if (LEVEL >= 2 and col in FORMATS) else ""
    return f"<column datatype='{DT[t]}'{f} name='[{col}]' role='{role}' type='{typ}' />"


def palette_xml(key):
    if LEVEL < 2 or not PALETTES.get(key):
        return ""
    out = "    <style>\n      <style-rule element='mark'>\n"
    for field, mp in PALETTES[key].items():
        out += f"        <encoding attr='color' field='[none:{field}:nk]' type='palette'>\n"
        for member, hx in mp.items():
            out += f"          <map to='{hx}'><bucket>{escape(chr(34) + member + chr(34))}</bucket></map>\n"
        out += "        </encoding>\n"
    return out + "      </style-rule>\n    </style>\n"


def ds_xml(key, data_dir):
    fn, cols = SOURCES[key]
    rel_cols = "\n".join(f"            <column datatype='{DT[t]}' name={q(c)} ordinal='{i}' />" for i, (c, t) in enumerate(cols.items()))
    meta = "\n".join(f"    {col_meta(key, c)}" for c in list(cols) + list(CALCS[key]))
    table = f"[{fn.replace('.', '#')}]"
    # palettes are keyed on a field instance, so the datasource has to declare those instances
    pal_insts = "\n".join(f"    {instance(key, f)[1]}" for f in PALETTES.get(key, {})) if LEVEL >= 2 else ""
    obj_id = f"{fn}_{uuid.uuid5(uuid.NAMESPACE_URL, fn).hex.upper()}"
    rel_attrs = f"connection='textscan.{key}' name='{fn}' table='{table}' type='table'"
    cols_block = f"<columns character-set='UTF-8' header='yes' locale='en_US' separator=','>\n{rel_cols}\n        </columns>"
    return f"""  <datasource caption='{key}' inline='true' name='federated.{key}' version='18.1'>
    <connection class='federated'>
      <named-connections>
        <named-connection caption='{key}' name='textscan.{key}'>
          <connection class='textscan' directory={q(data_dir)} filename='{fn}' password='' server='' />
        </named-connection>
      </named-connections>
      <_.fcp.ObjectModelEncapsulateLegacy.false...relation {rel_attrs}>
        {cols_block}
      </_.fcp.ObjectModelEncapsulateLegacy.false...relation>
      <_.fcp.ObjectModelEncapsulateLegacy.true...relation {rel_attrs}>
        {cols_block}
      </_.fcp.ObjectModelEncapsulateLegacy.true...relation>
    </connection>
    <aliases enabled='yes' />
{meta}
    <_.fcp.ObjectModelTableType.true...column caption='{key}' datatype='table' name='[__tableau_internal_object_id__].[{obj_id}]' role='measure' type='quantitative' />
{pal_insts}
{palette_xml(key)}    <_.fcp.ObjectModelEncapsulateLegacy.true...object-graph>
      <objects>
        <object caption='{key}' id='{obj_id}'>
          <properties context=''>
            <relation {rel_attrs}>
              {cols_block}
            </relation>
          </properties>
        </object>
      </objects>
    </_.fcp.ObjectModelEncapsulateLegacy.true...object-graph>
  </datasource>"""


def instance(key, col):
    """(instance name, xml) for a field placed on a shelf. Measures aggregate with SUM; calcs are already aggregated."""
    if col in CALCS[key]:
        n = f"[usr:{col}:qk]"
        return n, f"<column-instance column='[{col}]' derivation='User' name='{n}' pivot='key' type='quantitative' />"
    t = SOURCES[key][1][col]
    if col in DIM_INTS:
        n = f"[none:{col}:ok]"
        return n, f"<column-instance column='[{col}]' derivation='None' name='{n}' pivot='key' type='ordinal' />"
    if t in "ri":
        n = f"[sum:{col}:qk]"
        return n, f"<column-instance column='[{col}]' derivation='Sum' name='{n}' pivot='key' type='quantitative' />"
    n = f"[none:{col}:nk]"
    return n, f"<column-instance column='[{col}]' derivation='None' name='{n}' pivot='key' type='nominal' />"


def calc_id(key, caption):
    for cid, (cap, _, _) in CALCS[key].items():
        if cap == caption:
            return cid
    return caption


def sheet(name, key, rows, cols, mark, color=None, filters=(), sort_by=None, labels=False, legend=True, text=None, header_width=None,
          all_labels=False):
    """rows/cols: field captions. filters: (field, [members]). sort_by: (dimension, measure[, 'ASC']), default descending.
    text: measure shown as the mark label in place of the bar's own value. header_width: pixels for the first row header.
    all_labels: keep every label even where two would touch."""
    ds = f"[federated.{key}]"
    used, cols_used = {}, set()

    def ref(cap):
        col = calc_id(key, cap)
        n, x = instance(key, col)
        used[n] = x
        cols_used.add(col)
        if col in CALCS[key]:
            cols_used.update(c for c in SOURCES[key][1] if f"[{c}]" in CALCS[key][col][1])
        return f"{ds}.{n}"

    r = " / ".join(ref(c) for c in rows)
    c = " / ".join(ref(cc) for cc in cols)
    enc = f"<color column='{ref(color)}' />" if color else ""
    if text:
        enc += f"<text column='{ref(text)}' />"
    extra, slices = "", []
    if sort_by:
        direction = sort_by[2] if len(sort_by) > 2 else "DESC"
        extra += f"\n          <computed-sort column='{ref(sort_by[0])}' direction='{direction}' using='{ref(sort_by[1])}' />"
    for fc, members in filters:
        full = ref(fc)
        level = full[len(ds) + 1:]
        attrs = "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'"
        if len(members) == 1:
            body = f"<groupfilter function='member' level='{level}' member={q(chr(34) + members[0] + chr(34))} {attrs} />"
        else:
            inner = "".join(f"<groupfilter function='member' level='{level}' member={q(chr(34) + m + chr(34))} />" for m in members)
            body = f"<groupfilter function='union' {attrs}>{inner}</groupfilter>"
        extra += f"\n          <filter class='categorical' column='{full}'>{body}</filter>"
        slices.append(full)
    if slices:
        extra += "\n          <slices>" + "".join(f"<column>{s}</column>" for s in slices) + "</slices>"
    lab, wstyle = "", "<style />"
    if LEVEL >= 2:
        if labels or text:
            # a waterfall keeps every label, even on a thin step; other charts drop labels that would collide
            cull = "false" if (text or all_labels) else "true"
            lab = ("<style><style-rule element='mark'><format attr='mark-labels-show' value='true' />"
                   f"<format attr='mark-labels-cull' value='{cull}' /></style-rule></style>")
        # the chart title already names the fields, so the "Period" / "Customer" header labels are hidden
        wstyle = ("<style><style-rule element='worksheet'><format attr='display-field-labels' scope='cols' value='false' />"
                  "<format attr='display-field-labels' scope='rows' value='false' /></style-rule>")
        if header_width:
            wstyle += f"<style-rule element='header'><format attr='width' field='{ref(rows[0])}' value='{header_width}' /></style-rule>"
        wstyle += "</style>"
    meta = "\n".join(f"            {col_meta(key, col)}" for col in sorted(cols_used))
    insts = "\n".join(f"            {x}" for x in used.values())
    return f"""    <worksheet name={q(name)}>
      <table>
        <view>
          <datasources><datasource caption='{key}' name='federated.{key}' /></datasources>
          <datasource-dependencies datasource='federated.{key}'>
{meta}
{insts}
          </datasource-dependencies>{extra}
          <aggregation value='true' />
        </view>
        {wstyle}
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='{mark}' />
            <encodings>{enc}</encodings>
            {lab}
          </pane>
        </panes>
        <rows>{r}</rows>
        <cols>{c}</cols>
      </table>
      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper()}}}' />
    </worksheet>"""


ZS = ("<zone-style><format attr='border-color' value='#000000' /><format attr='border-style' value='none' />"
      "<format attr='border-width' value='0' /><format attr='margin' value='4' /></zone-style>")


def text_zone(zid, x, y, w, h, text, size, bold=False, color=None, margin=4):
    """One line of text. Tableau clips a line that is taller than its zone, so tight blocks pass margin=0."""
    zs = ZS.replace("attr='margin' value='4'", f"attr='margin' value='{margin}'")
    attrs = (" bold='true'" if bold else "") + (f" fontcolor='{color}'" if color else "")
    return (f"\n          <zone h='{h}' id='{zid}' type-v2='text' w='{w}' x='{x}' y='{y}'><formatted-text>"
            f"<run{attrs} fontsize='{size}'>{escape(text)}</run></formatted-text>{zs}</zone>")


def dashboard(name, title, lines, grid, weights=None, col_weights=None):
    """Fixed tiled layout: headline, takeaway lines, then a grid of cells.
    A cell is a sheet name (one-line text title, the sheet with its own title hidden and, when it has a colour field,
    a legend strip on the right) or ("TEXT", title, [paragraphs]) for a block of plain text ("## " starts a sub-heading).
    Text zones here do not wrap, so long text is split into one zone per line.
    weights: relative row heights. col_weights: {row index: relative column widths}. Returns (xml, id of the first sheet zone)."""
    zid = [2]

    def nid():
        zid[0] += 1
        return zid[0]

    by_name = {s[0]: s for s in SHEETS}
    X0, W, LEG = 800, 98400, 11000
    TOP, T_H, S_H, C_T, P_LH, P_GAP = 1000, 5500, 3900, 3800, 3400, 900
    lines = [w for ln in lines for w in textwrap.wrap(ln, 130)]
    G0 = TOP + T_H + S_H * len(lines)
    H = 99000 - G0
    weights = weights or [1] * len(grid)
    cells, first, y = "", None, G0
    for ri, row in enumerate(grid):
        rh = int(H * weights[ri] / sum(weights))
        cws = (col_weights or {}).get(ri) or [1] * len(row)
        x = X0
        for ci, cell in enumerate(row):
            cw = int(W * cws[ci] / sum(cws))
            if ci:
                x += int(W * cws[ci - 1] / sum(cws))
            if isinstance(cell, tuple):                                   # block of text
                _, ttl, body = cell
                cells += text_zone(nid(), x, y, cw, C_T, ttl, 12, bold=True)
                ty = y + C_T + 600
                for para in body:
                    head = para.startswith("## ")
                    ty += P_GAP * (3 if head else 1)
                    for ln in textwrap.wrap(para[3:] if head else para, 66, subsequent_indent="" if head else "    "):
                        cells += text_zone(nid(), x + 300, ty, cw - 300, P_LH, ln, 11, bold=head, color="#333333", margin=0)
                        ty += P_LH
                assert ty <= y + rh, f"{name}: text block is {ty - y - rh} units too tall"
                continue
            _, key, _, _, _, opts = by_name[cell]
            color = opts.get("color")
            legend = bool(color) and opts.get("legend", True)
            sw = cw - LEG if legend else cw
            cells += text_zone(nid(), x, y, cw, C_T, cell, 12, bold=True)
            i = nid()
            first = first or i
            cells += f"\n          <zone h='{rh - C_T}' id='{i}' name={q(cell)} show-title='false' w='{sw}' x='{x}' y='{y + C_T}'>{ZS}</zone>"
            if legend:
                param = f"[federated.{key}].{instance(key, color)[0]}"
                cells += (f"\n          <zone h='{rh - C_T}' id='{nid()}' name={q(cell)} pane-specification-id='0' param={q(param)} "
                          f"type-v2='color' w='{LEG}' x='{x + sw}' y='{y + C_T}'>{ZS}</zone>")
        y += rh
    text = text_zone(nid(), X0, TOP, W, T_H, title, 18, bold=True)
    verdict = False
    for li, ln in enumerate(lines):
        verdict = ln.startswith("Verdict:") or (verdict and li > 0)       # a wrapped verdict line stays bold
        text += text_zone(nid(), X0, TOP + T_H + li * S_H, W, S_H, ln, 11, bold=verdict, color="#222222" if verdict else "#555555")
    outer_style = ZS.replace("value='4'", "value='8'")
    xml = f"""    <dashboard name={q(name)}>
      <style />
      <size maxheight='900' maxwidth='1500' minheight='900' minwidth='1500' />
      <zones>
        <zone h='100000' id='{nid()}' type-v2='layout-basic' w='100000' x='0' y='0'>{text}{cells}
          {outer_style}
        </zone>
      </zones>
      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_OID, name)).upper()}}}' />
    </dashboard>"""
    return xml, first


def windows_xml(sheet_names, dashboards, front=0):
    out = "  <windows source-height='30'>\n"
    for i, (n, grid, active) in enumerate(dashboards):
        maxed = " maximized='true'" if i == front else ""
        vps = "".join(f"<viewpoint name={q(s)}><zoom type='entire-view' /></viewpoint>" for row in grid for s in row if isinstance(s, str))
        # active id -1 = no zone selected, so the dashboard opens without a selection border and floating toolbar
        out += (f"    <window class='dashboard'{maxed} name={q(n)}>\n      <viewpoints>{vps}</viewpoints>\n      <active id='-1' />\n"
                f"      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_X500, n)).upper()}}}' />\n    </window>\n")
    for i, n in enumerate(sheet_names):
        maxed = " maximized='true'" if (i == 0 and not dashboards) else ""
        out += (f"    <window class='worksheet'{maxed} name={q(n)}>\n      <cards>\n"
                "        <edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>\n"
                "        <edge name='top'><strip size='2147483647'><card type='columns' /></strip>"
                "<strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge>\n"
                "      </cards>\n"
                f"      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_DNS, n)).upper()}}}' />\n    </window>\n")
    return out + "  </windows>\n"


MAIN4 = ["Cookies", "Crackers", "Crisps", "Muffins"]
ACT_BUD = ["Scenario", "Period"]              # two header rows: Actual | Budget above the years, so budget never reads as an actual


def waterfall(exhibit, header_width=None):
    """Horizontal waterfall drawn from the pre-calculated summary table: stacked bar = white Spacer + the step."""
    return dict(color="Key", text="Label Revenue", filters=[("Exhibit", [exhibit])], sort_by=("Label", "Sort Order", "ASC"),
                legend=False, header_width=header_width)


# name -> (datasource, rows, cols, mark, options). The name is also the chart title on the dashboard.
S = {
    # 1. The answer: budget risk
    "2021 budget is above every year on record":
        ("sales", ["Revenue"], ["Period"], "Bar", dict(color="Scenario", labels=True, legend=False)),
    "H2 budget: $8.9M above best":
        ("sales", ["Half", "Period"], ["Revenue"], "Bar", dict(color="Scenario", labels=True, legend=False, all_labels=True)),
    "Oct and Nov budget beat any past month":
        ("sales", ["Revenue"], ["Month Num"], "Line", dict(color="Period")),
    "Where the extra $21.3M comes from, by customer status":
        ("summary", ["Label"], ["Revenue"], "Bar", waterfall("Customer bridge", 200)),
    "15 customers carry $13.1M of step-up over 2020":
        ("customers", ["Customer"], ["Step-up vs 2020"], "Bar",
         dict(color="Customer Status", filters=[("Step-up Group", ["Top 15 step-ups"])], sort_by=("Customer", "Step-up vs 2020"), labels=True)),
    # 2. Volume and price trends (case question 1)
    "Why revenue moved: volume, price and mix":
        ("summary", ["Label"], ["Revenue"], "Bar", waterfall("PVM bridge")),
    "Pounds shipped by channel":
        ("sales", ["Pounds"], ACT_BUD, "Bar", dict(color="Channel", labels=True)),
    "Price per lb by brand type (2021 is budget)":
        ("sales", ["Price per lb"], ["Period"], "Line", dict(color="Brand Type", labels=True, legend=False)),
    "Pounds shipped by brand type":
        ("sales", ["Pounds"], ACT_BUD, "Bar", dict(color="Brand Type", labels=True)),
    "Customers buying each year":
        ("sales", ["Customers"], ["Period"], "Bar", dict(color="Scenario", labels=True, legend=False)),
    # 3. Revenue distribution (question 2)
    "Customers: the top 10% bring 54% of revenue":
        ("summary", ["Share of Revenue"], ["Label"], "Bar",
         dict(color="Key", filters=[("Exhibit", ["Customer tiers"])], sort_by=("Label", "Sort Order", "ASC"), labels=True, all_labels=True,
              legend=False)),
    "Items: the top 10% (8 items) bring 70%":
        ("summary", ["Share of Revenue"], ["Label"], "Bar",
         dict(color="Key", filters=[("Exhibit", ["Item tiers"])], sort_by=("Label", "Sort Order", "ASC"), labels=True, all_labels=True)),
    "Top 15 customers, 2020 revenue":
        ("sales", ["Customer"], ["Revenue"], "Bar",
         dict(color="Channel", filters=[("Period", ["2020"]), ("Top 15 Customer 2020", ["Top 15"])], sort_by=("Customer", "Revenue"), labels=True)),
    "Top 15 items, 2020 revenue":
        ("sales", ["Item Label"], ["Revenue"], "Bar",
         dict(color="Brand Type", filters=[("Period", ["2020"]), ("Top 15 Item 2020", ["Top 15"])], sort_by=("Item Label", "Revenue"), labels=True)),
    # 4. Price per pound (question 3)
    "Price per lb by item group, 2020":
        ("sales", ["Item Group", "Brand Type"], ["Price per lb"], "Bar",
         dict(color="Brand Type", filters=[("Period", ["2020"]), ("Item Group", MAIN4)], labels=True, legend=False)),
    "Cracker price per lb by brand":
        ("sales", ["Price per lb"], ["Period"], "Line",
         dict(color="Brand Type", filters=[("Item Group", ["Crackers"])], labels=True, legend=False)),
    "Cracker pounds by channel":
        ("sales", ["Pounds"], ["Channel", "Period"], "Bar",
         dict(color="Brand Type", filters=[("Item Group", ["Crackers"])], labels=True, legend=False)),
    "Top 10 cracker items, 2020 revenue":
        ("sales", ["Item Label"], ["Revenue"], "Bar",
         dict(color="Brand Type", filters=[("Period", ["2020"]), ("Top 10 Cracker 2020", ["Top 10"])], sort_by=("Item Label", "Revenue"),
              labels=True, legend=False)),
    "Price per lb, same 10 items":
        ("sales", ["Item Label"], ["Price per lb"], "Bar",
         dict(color="Brand Type", filters=[("Period", ["2020"]), ("Top 10 Cracker 2020", ["Top 10"])], sort_by=("Item Label", "Revenue"),
              labels=True)),
    # 5. Business A and B (question 4)
    "Revenue by business: A carries the growth":
        ("sales", ["Revenue"], ACT_BUD, "Bar", dict(color="Business", labels=True, legend=False)),
    "Price per lb: B is 3x A":
        ("sales", ["Price per lb"], ["Period"], "Line", dict(color="Business", labels=True, legend=False)),
    "2020 revenue: A is Food Service, B is Retail":
        ("sales", ["Business"], ["Revenue"], "Bar", dict(color="Channel", filters=[("Period", ["2020"])], labels=True)),
    "Customers of one business carry the budget growth":
        ("sales", ["Revenue"], ACT_BUD, "Bar", dict(color="Customer Overlap", labels=True)),
    "Top 15 overlap customers, 2020 revenue by business":
        ("sales", ["Customer"], ["Revenue"], "Bar",
         dict(color="Business", filters=[("Period", ["2020"]), ("Top 15 Overlap Customer 2020", ["Top 15"])], sort_by=("Customer", "Revenue"))),
    # 6. What the budget assumes (question 5)
    "Share of revenue: 2020's shift and the budget's reversal":
        ("summary", ["Share of Revenue"], ["Label"], "Line",
         dict(color="Key", filters=[("Exhibit", ["Mix shares"])], sort_by=("Label", "Sort Order", "ASC"), labels=True)),
    "Revenue by item group":
        ("sales", ["Revenue"], ACT_BUD, "Bar", dict(color="Item Group", labels=True)),
    "Top 10 items by budget increase over 2020":
        ("sales", ["Item Label"], ["Budget change vs 2020"], "Bar",
         dict(color="Brand Type", filters=[("Top 10 Item Budget Increase", ["Top 10"])], sort_by=("Item Label", "Budget change vs 2020"), labels=True)),
    "Biggest item changes in the budget: volume vs price":
        ("summary", ["Label"], ["Revenue"], "Bar",
         dict(color="Key", filters=[("Exhibit", ["Item price volume"])], sort_by=("Label", "Revenue"), labels=True)),
    # 7. Verdict
    "2021 revenue: the budget against what the history supports":
        ("summary", ["Label"], ["Revenue"], "Bar",
         dict(color="Key", filters=[("Exhibit", ["Scenarios"])], sort_by=("Label", "Sort Order", "ASC"), labels=True, legend=False,
              header_width=190)),
}
SHEETS = [(n,) + v for n, v in S.items()]
N = list(S)
QUESTIONS = ("TEXT", "Questions for management before relying on the budget", [
    "1. January to March 2021 look like actuals in the budget file. How is the year tracking so far?",
    "2. What signed orders or contracts back the 5 new customers ($5.5M, starting in April)?",
    "3. October and November are budgeted at about $9.2M each. The best month on record is $7.3M. Is there plant capacity for that?",
    "4. What is in the order book and backlog today for the second half?",
    "5. Cookie item 50040 goes from $1.5M to $7.4M. Who is buying it, and at what price?",
    "6. Which of the 57 lapsed customers ($3.9M in the budget) have placed an order?",
    "7. Why are 41 customers with $2.2M of 2020 sales left out of the budget?",
    "## How each stress test is built",
    "Without the 5 new customers: the budget less the $5.5M from customers with no sales history.",
    "Capped at best year: no customer above its best year of 2018 to 2020. This removes $12.7M.",
    "Recovery rate: Q4 2020 revenue was 78% of Q4 2019. 2019 revenue times 78% is $52.3M.",
])
# (tab name, headline, takeaway lines, grid of sheet names, relative row heights[, {row: relative column widths}])
# Pages follow the case: the answer first, then the case's questions 1 to 5, then the verdict.
# Takeaway lines over 130 characters wrap onto a second line and push the charts down.
DASHBOARDS = [
    ("1 Budget Risk", "1. The 2021 budget is not supported by the sales history",
     ["The $72.9M budget is 41% above 2020 and 8% above 2019, the best year. 61% of it lands in the second half; history is 53 to 54%.",
      "Verdict: unlikely as submitted. History supports about $52M to $60M unless orders back the second-half ramp and 5 new customers."],
     [N[0:3], N[3:5]], [40, 60], {0: [41, 27, 32]}),
    ("2 Volume and Price", "2. 2020 fell on volume, not price. The budget needs all of that volume back, and more",
     ["2020 revenue fell $15.7M: volume -$19.5M, price +$2.1M, mix +$1.6M. Pounds fell 29%; 47 fewer customers bought.",
      "Price per lb rose 7.9%: 4.5 points from price increases (4 to 5% on both brand types) and 3.4 points from mix.",
      "Private label's jump from $1.43 to $1.70/lb is mostly mix: its cheapest crackers, 78100 and 10142, lost almost 4M lbs."],
     [N[5:7], N[7:10]], [50, 50], {1: [36, 40, 24]}),
    ("3 Revenue Distribution", "3. Revenue is spread across customers but concentrated in a few items",
     ["The top 10% of customers bring 54% of revenue and the bottom half 7%, the same every year since 2018. No customer is above 8%.",
      "Items are far more concentrated: the top 10% (8 items) bring 70%, and branded cracker 15040 alone was 31% of 2020 revenue.",
      "The budget leans on bigger customers: 16 are budgeted above $1M, against 9 in 2020. Customer 900009 is budgeted up 151%."],
     [N[10:12], N[12:14]], [42, 58]),
    ("4 Price per Pound", "4. Crisps and muffins are $6/lb, crackers $1.81. The brand premium rests on one item",
     ["Crisps ($5.83) and muffins ($6.37) sell at about 3x crackers ($1.81) and cookies ($1.65) per lb. Together they are Business B.",
      "Branded crackers sold at $2.35/lb, private label at $1.39. Branded 15040 alone is 42% of cracker revenue, at $2.40/lb.",
      "Branded Food Service crackers fell from 11.6M to 6.7M lbs in 2020. The budget brings back 9.1M lbs, still below 2019."],
     [N[14:17], N[17:19]], [46, 54], {0: [34, 26, 40]}),
    ("5 Business A and B", "5. A sells volume, B sells price. The budget's growth is almost all Business A",
     ["A (crackers, cookies) sells at $1.79/lb, 62% to Food Service. B (crisps, muffins) sells at $6.01/lb, 91% to Retail.",
      "In 2020 A fell 26% and B only 7%. The budget grows A by $19.9M (+46%) and B by $1.3M (+16%), so the budget risk sits in A.",
      "61 customers buy from both, 22% of 2020 revenue. The budget keeps them 12% below 2019 while one-business customers go 14% above."],
     [N[19:22], N[22:24]], [44, 56], {0: [34, 27, 39], 1: [42, 58]}),
    ("6 What the Budget Assumes", "6. The budget assumes 2020's shifts reverse and cookies more than double",
     ["2020 moved revenue to Retail (39% to 47%) and Private Label (38% to 43%). The budget puts both back near 2019 levels.",
      "Cookies go from $5.1M to $12.5M, mostly item 50040 ($1.55M to $7.41M). Ten items carry $20.3M of the $21.3M increase."],
     [N[24:26], N[26:28]], [45, 55]),
    ("7 Verdict and Questions", "7. What the history supports, and what to ask management",
     ["Stress tests give $52M (2019 at the recent recovery rate) to $60M (no customer above its best year). The rest needs new business."],
     [[N[28], QUESTIONS]], [100]),
]
for _d in DASHBOARDS:
    for _ln in _d[2]:
        if len(_ln) > 130:
            print(f"note: {_d[0]} takeaway is {len(_ln)} characters and will wrap")


def build(tableau_dir, level=2, out_name="case_study.twb", front=0):
    global LEVEL
    LEVEL = level
    data_dir = os.path.join(tableau_dir, "data").replace("\\", "/")
    check_headers(data_dir)
    sheets = [sheet(n, k, r, c, m, **o) for n, k, r, c, m, o in SHEETS]
    built = [(d[0], d[3]) + dashboard(*d) for d in (DASHBOARDS if level >= 1 else [])]
    dashes = [(n, g, active) for n, g, _, active in built]
    dash_xml = ("  <dashboards>\n" + "\n".join(x for _, _, x, _ in built) + "\n  </dashboards>\n") if built else ""
    doc = ("<?xml version='1.0' encoding='utf-8' ?>\n"
           "<workbook source-build='2026.2.3 (20262.26.0912.1023)' source-platform='win' version='18.1' "
           "xmlns:user='http://www.tableausoftware.com/xml/user'>\n"
           "  <document-format-change-manifest>\n"
           "    <_.fcp.ObjectModelEncapsulateLegacy.true...ObjectModelEncapsulateLegacy />\n"
           "    <_.fcp.ObjectModelTableType.true...ObjectModelTableType />\n"
           "    <_.fcp.SchemaViewerObjectModel.true...SchemaViewerObjectModel />\n"
           "    <SheetIdentifierTracking />\n    <SortTagCleanup />\n    <WindowsPersistSimpleIdentifiers />\n"
           "  </document-format-change-manifest>\n"
           "  <preferences />\n"
           "  <datasources>\n" + "\n".join(ds_xml(k, data_dir) for k in SOURCES) + "\n  </datasources>\n"
           "  <worksheets>\n" + "\n".join(sheets) + "\n  </worksheets>\n"
           + dash_xml + windows_xml([s[0] for s in SHEETS], dashes, front) + "</workbook>\n")
    out = os.path.join(tableau_dir, out_name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    import xml.etree.ElementTree as ET
    ET.parse(out)                                                         # fails loudly if the file is not well-formed XML
    print("wrote", out, "level", level, "sheets", len(sheets), "dashboards", len(dashes))


if __name__ == "__main__":
    build(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2, sys.argv[3] if len(sys.argv) > 3 else "case_study.twb",
          int(sys.argv[4]) if len(sys.argv) > 4 else 0)
