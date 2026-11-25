"""Package the workbook and its CSVs into one portable .twbx (a zip Tableau opens directly).

Usage: python -I package_twbx.py <tableau_dir> <workbook.twb> <output.twbx>
Inside the package the CSVs sit under Data/data/ and the workbook points there, so it opens on any machine.
"""
import os, re, sys, zipfile

td, twb, out = sys.argv[1:4]
xml = open(os.path.join(td, twb), encoding="utf-8").read()
xml, n = re.subn(r"directory=(['\"]).*?\1", "directory='Data/data'", xml)      # absolute folder -> folder inside the package
csvs = sorted(f for f in os.listdir(os.path.join(td, "data")) if f.endswith(".csv"))
assert n == len(csvs), f"{n} data connections but {len(csvs)} CSV files"
with zipfile.ZipFile(os.path.join(td, out), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(twb, xml)
    for f in csvs:
        z.write(os.path.join(td, "data", f), f"Data/data/{f}")
print("wrote", os.path.join(td, out), "with", [twb] + csvs)
