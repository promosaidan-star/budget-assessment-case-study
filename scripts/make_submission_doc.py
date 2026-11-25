"""Build the case study write-up as a Word file. Usage: python -I make_submission_doc.py <out.docx>"""
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT = sys.argv[1]
NAVY = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x59, 0x59, 0x59)
FONT = "Calibri"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, m, Inches(1))


def style_font(style, size, bold=None, color=None, before=None, after=None):
    """Set one font on a style and strip the theme-font attributes that would override it."""
    style.font.name = FONT
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rf.attrib.pop(qn(a), None)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    pf = style.paragraph_format
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)


style_font(doc.styles["Normal"], 11, after=6)
style_font(doc.styles["List Bullet"], 11, after=3)
style_font(doc.styles["Heading 1"], 15, bold=True, color=NAVY, before=18, after=6)
style_font(doc.styles["Heading 2"], 12, bold=True, color=NAVY, before=12, after=4)
for h in ("Heading 1", "Heading 2"):
    doc.styles[h].paragraph_format.keep_with_next = True


def runs(p, text, size=None, color=None, italic=False, bold_all=False):
    """Add text to a paragraph; **double stars** mark bold spans."""
    for i, chunk in enumerate(re.split(r"\*\*", text)):
        if not chunk:
            continue
        r = p.add_run(chunk)
        r.bold = bold_all or (i % 2 == 1)
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if color is not None:
            r.font.color.rgb = color
    return p


def P(text, after=6, keep=False, **kw):
    p = runs(doc.add_paragraph(), text, **kw)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.keep_with_next = keep
    return p


def B(text):
    return runs(doc.add_paragraph(style="List Bullet"), text)


def N(items):
    """Numbered list written as text, so each list starts at 1."""
    for i, t in enumerate(items, 1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent, pf.first_line_indent, pf.space_after = Inches(0.3), Inches(-0.3), Pt(3)
        pf.tab_stops.add_tab_stop(Inches(0.3))
        runs(p, f"{i}.\t{t}")


def Q(text):
    P("Case question: " + text, italic=True, color=GREY, size=10, after=4, keep=True)


def DASH(text):
    P(text, italic=True, color=GREY, size=10, after=2)


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear")
    s.set(qn("w:color"), "auto")
    s.set(qn("w:fill"), fill)
    tcPr.append(s)


def TABLE(caption, rows, widths, numeric_from=None):
    """Caption, then a grid table with a shaded header row. numeric_from: first column index to right-align."""
    P(caption, bold_all=True, size=10, color=NAVY, after=3, keep=True)
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for j, w in enumerate(widths):
        t.columns[j].width = Inches(w)
    for i, row in enumerate(rows):
        tr_pr = t.rows[i]._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.width = Inches(widths[j])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            runs(p, val, size=10, bold_all=(i == 0))
            if numeric_from is not None and j >= numeric_from:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if i == 0:
                shade(c, "DCE6F1")
            if i < len(rows) - 1:
                p.paragraph_format.keep_with_next = True
    P("", after=2)


def rule():
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "8"), ("w:space", "1"), ("w:color", "1F4E79")):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    pPr.append(bdr)
    p.paragraph_format.space_after = Pt(10)


# ---------- footer with page number
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
runs(fp, "Aidan Walsh | Lender diligence case study | Page ", size=9, color=GREY)
fld = OxmlElement("w:fldSimple")
fld.set(qn("w:instr"), "PAGE")
r = OxmlElement("w:r")
rpr = OxmlElement("w:rPr")
sz = OxmlElement("w:sz")
sz.set(qn("w:val"), "18")
rpr.append(sz)
r.append(rpr)
t = OxmlElement("w:t")
t.text = "1"
r.append(t)
fld.append(r)
fp._p.append(fld)

# ---------- title block
P("2021 Budget Assessment", size=24, color=NAVY, bold_all=True, after=2)
P("Findings and reporting recommendations for the lender", size=13, color=GREY, after=2)
P("Lender diligence case study | Aidan Walsh | November 2026", size=10, color=GREY, after=0)
rule()
P("A lender asked whether this ~$70M snack and baked goods company can hit its 2021 budget, and how its sales and budget "
  "reporting could be automated. This document answers the case's five analytical questions and four architecture questions. "
  "The seven dashboard pages referenced below are in the attached PDF and Tableau workbook.")

# ---------- the answer
doc.add_heading("The answer", level=1)
P("**The $72.9M budget is unlikely as submitted. The sales history supports about $52M to $60M.**")
B("The budget is 41% above 2020 ($51.6M) and 8% above 2019 ($67.3M), the best year on record. Hitting it means winning back "
  "all the volume lost in 2020 and then growing on top of it.")
B("2020 was a volume problem, not a pricing problem. Pounds fell 29% and 47 fewer customers bought, while prices rose 4 to 5%.")
B("The budget's risk sits in a few places: 61% of the year lands in the second half, $5.5M comes from 5 customers with no "
  "sales history, and ten items carry $20.3M of the $21.3M increase over 2020.")
B("What would change the answer: signed orders and backlog for the second half, contracts with the new customers, and a plan "
  "behind cookie item 50040, which the budget takes from $1.5M to $7.4M.")
TABLE("2021 revenue under different assumptions", [
    ["Scenario", "2021 revenue", "How it is built"],
    ["Budget as submitted", "$72.9M", "The client's forecast"],
    ["Without the 5 new customers", "$67.4M", "The budget less the $5.5M from customers with no sales history"],
    ["Each customer capped at its best year", "$60.2M", "No customer above its best year of 2018 to 2020. Removes $12.7M"],
    ["2019 at the recent recovery rate", "$52.3M", "Q4 2020 revenue was 78% of Q4 2019, so 2019 revenue x 78%"],
], [2.3, 1.1, 3.1])
TABLE("Revenue, pounds and price by year", [
    ["", "2018", "2019", "2020", "2021 budget"],
    ["Revenue", "$66.1M", "$67.3M", "$51.6M", "$72.9M"],
    ["Pounds shipped", "34.8M", "36.1M", "25.6M", "37.9M"],
    ["Price per lb", "$1.90", "$1.87", "$2.01", "$1.92"],
    ["Customers buying", "319", "321", "274", "295"],
], [1.9, 1.1, 1.1, 1.1, 1.3], numeric_from=1)
DASH("Dashboards: page 1 (budget risk) and page 7 (verdict and questions).")

# ---------- analytical questions
doc.add_heading("Analytical questions", level=1)

doc.add_heading("1. Volume and price trends", level=2)
Q("How is the volume (lbs.) and pricing trending across customer, private/branded, channel, and item?")
P("**Revenue fell in 2020 because the company sold fewer pounds, not because prices fell.**")
B("**Price, volume and mix:** 2020 revenue fell $15.7M from 2019. Lost volume cost $19.5M. Higher prices added $2.1M and a "
  "richer mix added $1.6M.")
B("**Price:** the average price per lb rose 7.9%, from $1.87 to $2.01. 4.5 points of that were real price increases, about "
  "the same on both brand types (4.7% branded, 4.1% private label). The other 3.4 points were mix: the cheaper products lost "
  "the most volume.")
B("**Channel:** Food Service pounds fell 35% (21.1M to 13.7M). Retail fell 20% (15.0M to 11.9M).")
B("**Brand type:** branded pounds fell 32% and private label 26%. Private label's price per lb jumped from $1.43 to $1.70, "
  "mostly through mix: its two cheapest crackers, 78100 and 10142 (about $0.90 to $1.00 per lb), lost almost 4M lbs between "
  "them. Branded moved only from $2.30 to $2.35.")
B("**Item:** cracker pounds fell 31%. Crisps grew 15%, the only item group that grew.")
B("**Customer:** 321 customers bought in 2019 and 274 in 2020.")
B("**The budget reverses all of this.** From 2020 to the budget, volume is up $24.7M, price up $3.1M and mix down $6.5M. It needs 37.9M "
  "lbs, more than 2019's 36.1M. Mix turns negative because the growth is in crackers and cookies, which are cheap per pound, "
  "including the return of private label cracker 78100 (+$2.6M).")
DASH("Dashboard: page 2. The price, volume and mix method is in the appendix.")

doc.add_heading("2. Distribution of revenue", level=2)
Q("What is the distribution of revenue across all items/customers?")
P("**Revenue is spread across customers but concentrated in a few items.**")
B("**Customers:** the top 10% of customers bring about 54% of revenue and the bottom half about 7%. The pattern has held "
  "every year since 2018: about 28% of customers make 80% of revenue. No single customer can sink the year; the largest was "
  "8% of 2020 revenue.")
B("**Items:** the top 10% of items (8 items) brought about 70% of 2020 revenue and the top 10 items 75%. Branded cracker "
  "15040 alone was 31%. That one item is the biggest concentration risk in the business.")
B("**The budget leans on bigger customers:** 16 are budgeted above $1M, against 9 in 2020. Customer 900009 is budgeted up 151%.")
B("**Segments:** 2020 moved revenue toward Retail and private label. The budget moves it back (table below).")
TABLE("Share of revenue by segment", [
    ["Segment", "2018", "2019", "2020", "2021 budget"],
    ["Business A (crackers, cookies)", "83%", "87%", "84%", "87%"],
    ["Food Service", "59%", "61%", "53%", "60%"],
    ["Branded", "63%", "62%", "57%", "62%"],
    ["Crackers", "76%", "78%", "74%", "70%"],
    ["Cookies", "7%", "8%", "10%", "17%"],
], [2.5, 0.9, 0.9, 0.9, 1.3], numeric_from=1)
DASH("Dashboard: page 3.")

doc.add_heading("3. Price per pound by item group and brand type", level=2)
Q("How different is the pricing per pound by item group and private/brand?")
P("**Crisps and muffins sell at about three times the price per pound of crackers and cookies. The brand premium on crackers "
  "rests mostly on one item.**")
TABLE("2020 price per lb", [
    ["Item group", "Branded", "Private label", "All", "Share of 2020 revenue"],
    ["Crackers", "$2.35", "$1.39", "$1.81", "74%"],
    ["Cookies", "$1.64", "$1.76", "$1.65", "10%"],
    ["Crisps", "$7.63", "$5.72", "$5.83", "10%"],
    ["Muffins", "$6.44", "$5.83", "$6.37", "6%"],
    ["All items", "$2.35", "$1.70", "$2.01", "100%"],
], [1.6, 1.0, 1.2, 0.9, 1.8], numeric_from=1)
B("Crisps and muffins together make up Business B, which is why B averages about $6 per lb against $1.79 for Business A.")
B("Branded sold at $2.35 per lb and private label at $1.70 in 2020. In 2019 it was $2.30 against $1.43, a 60% premium. The "
  "gap narrowed to 38% mostly through mix, not price (see question 1).")
B("Crackers carry the brand premium: branded $2.35 against private label $1.39, a 69% premium. Branded 15040 alone is 42% of "
  "cracker revenue, at $2.40 per lb. Cookies are the opposite: branded $1.64 sells below private label $1.76.")
B("Retail branded is the highest-priced segment at $2.72 per lb, and steady every year.")
B("The budget lowers the average price to $1.92 per lb (from $2.01) because its growth is in products that are cheap per pound.")
DASH("Dashboard: page 4.")

doc.add_heading("4. Customers that buy from both Business A and Business B", level=2)
Q("What are the customers that overlap with one another between Business A and Business B, and how much revenue does that make up?")
P("**61 of the 395 customers with sales history buy from both businesses. They were $11.48M (22%) of 2020 revenue and "
  "$13.25M (18%) of the budget, up 15%.**")
B("The overlap customers are mostly Retail: 47 Retail and 14 Food Service.")
B("The two businesses work differently. A (crackers, cookies) sells volume: $1.79 per lb, 62% to Food Service. B (crisps, "
  "muffins) sells price: $6.01 per lb, 91% to Retail.")
B("In 2020, A fell 26% and B only 7%. The budget grows A by $19.9M (+46%) and B by $1.3M (+16%). Almost all of the budget's "
  "growth, and its risk, sits in Business A.")
B("The budget keeps the overlap customers 12% below 2019, while customers of one business are budgeted 14% above 2019. The "
  "growth is planned with the customers who buy from only one business.")
DASH("Dashboard: page 5.")

doc.add_heading("5. Other insights and risks", level=2)
Q("What other insights or trends do you see?")
B("**Timing:** 61% of the budget ($44.7M) lands in the second half; history is 53 to 54%. That is $8.9M above the best second "
  "half on record. October and November are budgeted at about $9.2M each, and the best month on record is $7.3M.")
B("**New and returning customers:** $5.5M comes from 5 customers with no sales history, starting in April. $3.9M comes from "
  "57 customers who bought nothing in 2020. 15 customers carry $13.1M of the increase over 2020.")
B("**Missing customers:** 41 customers with $2.2M of 2020 sales are not in the budget.")
B("**Items:** ten items carry $20.3M of the $21.3M increase over 2020. Cookies go from $5.1M to $12.5M, mostly item 50040 "
  "($1.55M to $7.41M).")
B("**Mix reversal:** 2020 moved revenue toward Retail (39% to 47%) and private label (38% to 43%). The budget puts both back "
  "near 2019 levels, which assumes Food Service and branded demand fully return.")
B("**Budget file:** January to March 2021 budget values look like actuals rather than plan. This is my inference and should "
  "be confirmed with management.")
B("**Data quality:** the three files did not join cleanly (see the appendix). Those fixes should be made permanent before "
  "reporting is automated.")
DASH("Dashboards: pages 1 and 6.")

doc.add_heading("Questions for management before relying on the budget", level=1)
N(["January to March 2021 look like actuals in the budget file. How is the year tracking so far?",
   "What signed orders or contracts back the 5 new customers ($5.5M, starting in April)?",
   "October and November are budgeted at about $9.2M each, and the best month on record is $7.3M. Is there plant capacity for that?",
   "What is in the order book and backlog today for the second half?",
   "Cookie item 50040 goes from $1.5M to $7.4M. Who is buying it, and at what price?",
   "Which of the 57 lapsed customers ($3.9M in the budget) have placed an order?",
   "Why are 41 customers with $2.2M of 2020 sales left out of the budget?"])

# ---------- architecture
doc.add_heading("Reporting architecture", level=1)
P("Today every report starts with three manual extracts and an Excel file on one person's desktop. The recommendation is one "
  "scheduled pipeline that lands, cleans and models the data, then feeds one set of reports. At today's volume that is a "
  "small cloud SQL database and a BI tool, not a big data platform. If volume grows, the model stays the same and only the "
  "engine underneath it changes.")

doc.add_heading("1. Automating historical sales and budget reporting", level=2)
Q("Given that the board wants to continue analyzing historical sales and budgets, how would you go about automating this type of reporting?")
P("One pipeline pulls all three sources on a schedule, applies the cleaning rules as code, loads a star schema and refreshes "
  "the reports. Nobody exports a file or pastes into Excel.")
TABLE("How each source gets in", [
    ["Source", "Today", "Automated"],
    ["Historical sales", "Custom app on an on-premises SQL Server, extracted by hand",
     "Nightly incremental pull through a secure gateway, by order date or change tracking"],
    ["Budget", "Third-party SaaS budgeting app, exported by hand",
     "Scheduled API pull. Every pull is stored with a version stamp so reforecasts can be compared"],
    ["Case weights", "Excel file on an operations manager's desktop",
     "Short term: a locked template in a shared location with validation. Then a governed item table with a named owner"],
], [1.3, 2.3, 2.9])
N(["**Land the raw data unchanged.** Keep every extract as received, so any number can be traced back and reloaded.",
   "**Clean and conform in code.** The fixes from this exercise become rules: strip zero padding from item codes, map channel "
   "and brand labels to one list, unpivot the budget from 12 month columns to rows, fill weights from the item table.",
   "**Load a star schema.** Two fact tables (sales, budget) share three dimensions (item, customer, date). That shared shape "
   "makes budget versus actual a simple comparison.",
   "**Define each measure once.** Revenue, pounds and price per lb are defined in one semantic layer, not rebuilt in each report.",
   "**Test on every run.** Row counts and revenue totals tie to the source. Unmatched item codes, missing weights and budget "
   "rows with no customer stop the load and alert an owner.",
   "**Refresh the reports.** A monthly management and lender pack, plus budget versus actual by customer, item and channel."])
P("The prototype behind this analysis follows the same steps: Python cleans and models the three files, and the Tableau "
  "workbook reads the result.")

doc.add_heading("2. Tools and architecture if data volume stays about the same", level=2)
Q("Which tools / what data architecture would you recommend for this client, given that the data volume will not significantly increase over time? Why?")
P("Keep it small: a managed cloud SQL database as the warehouse, a light scheduler to move the data, SQL for the "
  "transformations, and Power BI on top. The sample holds 17,132 sales rows for three years, so a full reload takes seconds.")
TABLE("Recommended stack", [
    ["Layer", "Recommendation", "Why"],
    ["Ingestion and scheduling", "Azure Data Factory or Fabric Data Factory",
     "A gateway to the on-premises SQL Server and a REST connector for the budget API. Three small pipelines"],
    ["Storage", "Azure SQL Database, smallest practical tier",
     "The client already runs SQL Server, so the skills and the SQL dialect carry over"],
    ["Transformation", "SQL views or dbt Core, in version control",
     "Cleaning rules are readable, reviewed and tested, not hidden in a workbook"],
    ["Semantic model and reports", "Power BI, import mode, scheduled refresh",
     "The whole dataset fits in memory. Measures are defined once and reused"],
    ["Data quality", "Tests in the pipeline, with email or Teams alerts",
     "Catches a bad code or a missing weight before a report goes out"],
], [1.4, 1.9, 3.2])
B("**The data is tiny.** A Spark cluster, a lakehouse or streaming would add cost and moving parts with no benefit at this size.")
B("**It fits the people.** A finance or IT analyst who knows SQL can run and change it. No specialist data engineer is needed day to day.")
B("**Running cost is low.** Every piece is pay-as-you-go at its smallest tier. Exact pricing should be confirmed against the "
  "client's Microsoft agreement.")
B("**It can grow.** The star schema and the measure definitions carry over unchanged if the engine is replaced later.")
P("A cheaper option is Power BI dataflows alone, with no database. I would not start there, because the business logic then "
  "lives inside the BI tool, where it is harder to test, reuse and audit.")

doc.add_heading("3. Tools and architecture if shipped orders reach billions of rows a month", level=2)
Q("Which tools / what data architecture would you recommend for this client, given that the data volume would dramatically increase in the future (billions of rows per month for shipped orders)? Why?")
P("Move to a cloud lakehouse or a scale-out cloud warehouse, load changes continuously, and serve reports from "
  "pre-aggregated tables. A single SQL database and a nightly full reload stop working at this size: loads run past their "
  "window, and a query that scans raw order lines no longer returns in time for a dashboard. The star schema and the "
  "measures stay the same.")
TABLE("What changes at scale", [
    ["Layer", "What changes", "Why"],
    ["Ingestion", "Change data capture or event streaming from the order system",
     "Only new and changed rows move. A nightly full extract of billions of rows would not finish"],
    ["Storage", "Columnar files (Parquet or Delta) on cloud object storage, partitioned by ship date",
     "Cheap at scale, and a query reads only the months and columns it needs"],
    ["Compute", "A distributed engine: Microsoft Fabric or Azure Databricks to stay on Microsoft, or Snowflake or BigQuery",
     "Storage and compute scale separately. Compute can be sized up for a load, then paused"],
    ["Transformation", "Incremental only: each run processes new partitions",
     "Rebuilding history every night is too slow and too expensive"],
    ["Serving", "Aggregate tables at the grain reports use (day, customer, item), with drill-down on demand",
     "Dashboards read millions of rows, not billions, and stay fast"],
    ["Operations", "Orchestration, monitoring, data quality checks and cost alerts",
     "At this size a failed load or a runaway query costs real money"],
], [1.1, 2.7, 2.7])
B("**Cost becomes a design choice.** Partitioning, auto-pause and moving old data to cheaper storage decide the monthly bill.")
B("**The source system is the first constraint.** An on-premises custom app writing billions of rows a month would need its "
  "own re-architecture, ahead of the reporting.")
B("**The team changes.** This needs dedicated data engineering, in-house or as a managed service.")
P("I would choose the vendor on three things: the skills the team already has, existing vendor contracts, and whether the "
  "workload is mostly SQL reporting or also data science. I would run a proof of concept on one month of real data before committing.")

doc.add_heading("4. Other recommendations", level=2)
Q("Any other recommendations for the client in terms of automating their reporting?")
P("Fix the master data first. Most of the manual work in this case came from codes and labels that did not match, not from "
  "a missing tool. Each step below fixes a problem found in this data or watches a risk in the budget.")
B("**One item master and one customer master.** Each item has one code, one weight, one item group and one brand type; each "
  "customer has a parent and its ship-to locations. Why: budget item codes are zero-padded (00642 against 642), channel and "
  "brand labels differ between files, and some items have no weight or a zero weight. Automating on top of that repeats the "
  "same errors every month, just faster.")
B("**Rules at budget entry.** Every budget row names a customer and an item that exist in the masters. Why: 3 budget rows "
  "($106K) name no customer, so nobody can be held to them or tracked against them.")
B("**Version the budget.** Keep every budget and reforecast with its date. Why: January to March 2021 look like actuals, so "
  "the file has likely been changed once already. Without versions the lender cannot see how much the plan moved or how "
  "accurate past plans were.")
B("**Monthly price, volume and mix variance** against budget and prior year. Why: it tells the CFO in one line whether a miss "
  "is lost volume, discounting or selling cheaper products. It explained 2020 at once: volume down $19.5M, price up $2.1M, mix up $1.6M.")
B("**Exception alerts.** Flag customers behind budget pace and new-customer revenue that has not appeared. Why: the budget's "
  "risk sits in a few places, including $5.5M from 5 new customers and a second half $8.9M above any on record. An alert when "
  "those orders are not showing up gives months of warning instead of a surprise at year end.")
B("**A named owner for each data set.** Why: the case weights live in one operations manager's desktop Excel file. If that "
  "file is wrong or that person leaves, pounds and price per lb are wrong in every report.")
B("**Row-level security for the lender view.** Why: the lender sees the agreed view, not every customer's pricing, and both "
  "views come from one model, so the numbers always match.")
B("**Add the data the extracts lack:** open orders and backlog, cost and margin, and plant capacity. Why: a budget that needs "
  "a record second half cannot be judged on shipped sales alone.")
P("**Suggested rollout**", after=3, keep=True)
N(["**Days 1 to 30.** Agree the item, customer and channel lists. Move the case weight file to a controlled location. Stand "
   "up the database and load history.",
   "**Days 31 to 60.** Automate the sales and budget pulls. Put the cleaning rules and quality tests in code. Release the "
   "budget versus actual report.",
   "**Days 61 to 90.** Add the monthly variance pack, exception alerts and lender view. Hand over with documentation and a "
   "named owner for each data set."])
P("Master data comes first so the first automated report is right, and budget versus actual is live by month 2, early enough "
  "to act on 2021.")

# ---------- appendix
doc.add_heading("Appendix: method and data preparation", level=1)
P("**Tools.** Python (pandas) cleans, joins and models the three files and calculates the price, volume and mix bridges. "
  "Tableau presents the results in seven dashboard pages. I chose it because it is the BI tool I work in most, and I just "
  "finished a course on business visualization in Tableau. The model underneath is "
  "a set of plain tables, so it loads into Power BI unchanged, and Power BI is what I recommend for the client's ongoing "
  "reporting (architecture question 2).")
P("**Model.** A star schema: sales and budget fact tables that share item, customer and date dimensions. Revenue, pounds and "
  "price per lb (revenue divided by pounds) are each defined once.")
P("**Price, volume and mix.** Volume is the change in pounds, valued at the earlier period's average price per lb. Price is "
  "each item's change in price per lb, on items sold in both periods, valued at the new pounds. Mix is the remainder: the "
  "shift between items, plus new and dropped items.")
P("**Data issues found and fixed:**", after=3, keep=True)
B("**Codes.** Item and customer codes arrived as numbers, decimals and zero-padded text (00642 in the budget, 642 in sales). "
  "All were converted to one text key before joining.")
B("**Budget layout.** The budget has 12 month columns for cases and 12 for revenue. It was unpivoted to one row per customer, "
  "item and month so it lines up with sales.")
B("**Labels.** \"Retail Private Label\" (in sales only) was mapped into Retail, 12 Distributor rows ($61K) into Food Service, "
  "and \"Private Label\" and \"PL\" to one value.")
B("**Weights.** Pounds are cases times weight per case. The sales extract carries a 2-decimal weight and the operations file "
  "a 1-decimal one, so the sales weight was used first. Item 97519 has a zero weight on 295 sales rows ($206K), filled from "
  "the weight file. Item 97554 has no usable weight anywhere, so its few rows count in revenue but not in pounds.")
B("**Budget rows with no customer.** 3 rows ($106K) were kept and labelled UNASSIGNED, so the budget total still ties to the file.")

cp = doc.core_properties
cp.author = cp.last_modified_by = "Aidan Walsh"
cp.title = "2021 Budget Assessment"
cp.subject = "Lender diligence case study"
cp.comments = ""
cp.keywords = ""
doc.save(OUT)
print("saved", OUT)
