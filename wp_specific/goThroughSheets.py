# coding: utf-8
import re
import os
import sqlparse
import win32com.client
import pprint
import json


def pretty_printer(o):
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(o)


class MyExcel:

    def __init__(self, filePath):
        self.filePath = filePath
        self.xlApp = win32com.client.gencache.EnsureDispatch('Excel.Application')
        self.xlApp.Visible = True
        self.workBook = self.xlApp.Workbooks.Open(self.filePath)
        self.issues = {}
        self.goThroughSheets()
        self.writeToJson()

    def goThroughSheets(self):
        for idx in range(1, self.workBook.Worksheets.Count+1):
            sht = self.workBook.Worksheets(idx)
            print sht.Name
            eof = sht.Range('A65536').End(-4162).Row
            for row in range(4, eof+1):
                _id = int(sht.Range('A{}'.format(row)).Value2) if sht.Range('A{}'.format(row)).Value2 else None
                if _id:
                    concern = sht.Range('B{}'.format(row)).Value2 if sht.Range('B{}'.format(row)).Value2 else ''
                    outcome = sht.Range('C{}'.format(row)).Value2 if sht.Range('C{}'.format(row)).Value2 else ''
                    resolution = sht.Range('D{}'.format(row)).Value2 if sht.Range('D{}'.format(row)).Value2 else ''
                    if sht.Name not in self.issues:
                        self.issues[sht.Name] = {}
                    if _id not in self.issues[sht.Name]:
                        self.issues[sht.Name][_id] = dict(concern=concern, outcome=outcome, resolution=resolution)

    def writeToJson(self):
        import json
        try:
            folderPath = os.path.dirname(self.filePath)
            print folderPath
            with open(os.path.join(folderPath, r'network_issues.json'), 'w') as f:
                json.dump(self.issues, f, indent=4)
        except:
            print "Error writing file"


if __name__ == '__main__':
    ROOTDIR = r'C:\Users\Ricardo\projects\wp-fy17\Python'
    filePath = os.path.join(ROOTDIR, 'Final_Rec_Table.xlsx')
    xl = MyExcel(filePath)
    pretty_printer(xl.issues)