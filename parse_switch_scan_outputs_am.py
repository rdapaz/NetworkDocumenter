import win32com.client
import re
import os
import sys
import pprint


def pretty_print(o):
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(o)


def excel_column_name(iVal):
    retVal = None
    if iVal <= 26:
        retVal = chr(64+iVal)
    else:
        m = int(iVal/26)
        n = iVal - m*26
        if n==0:
            m = m-1
            n = 26
        retVal = f'{excel_column_name(m)}{excel_column_name(n)}' 
    return retVal


def fix_sh_name(sh_name):
    ret_val = sh_name.replace(' ','').replace('(','_').replace(')','')
    return ret_val

current_path = os.path.dirname(sys.argv[0])
os.chdir(current_path)
ROOT = r'../../Desktop'
os.chdir(ROOT)
xlApp = win32com.client.gencache.EnsureDispatch('Excel.Application')
xlApp.Visible = True
print(os.path.join(ROOT, 'FY17 - Switch Scan Outputs.xlsx'))
wk = xlApp.Workbooks.Open(os.path.join('.', 'FY17 - Switch Scan Outputs.xlsx'))

data_cols = []
for sh in wk.Worksheets:
    if sh.Name =='Addressing and Tracking':
        pass
    else:
        for col in range(1, 80):
            if sh.Range(f'{excel_column_name(col)}2').Value == 'term len 0':
                data_cols.append(dict(wk_sheet=sh.Name, data_column=excel_column_name(col), sw_name_column =excel_column_name(col+1)))


os.chdir('./temp')

for entry in data_cols:
    data = []
    sh = wk.Worksheets(entry['wk_sheet'])
    site_name = fix_sh_name(sh.Name)
    eof = sh.Range(f"{entry['data_column']}32767").End(-4162).Row
    for row in range(2, eof+1):
        val = sh.Range(f"{entry['data_column']}{row}").Value if sh.Range(f"{entry['data_column']}{row}").Value else ''
        data.append(val)
    pretty_print(data)
    txt = "\n".join(data)
    hostname = sh.Range(f"{entry['sw_name_column']}1").Value
    f_name = f'{site_name} - {hostname}.txt'
    with open(f_name, 'w') as fout:
        fout.write(txt)