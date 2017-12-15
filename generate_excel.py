import win32com.client
import sqlite3
import pprint
import sys
import os


def pretty_print(o):
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(o)


class Excel:
    def __init__(self):
        self.xlApp = win32com.client.gencache.EnsureDispatch('Excel.Application')
        self.xlApp.Visible = True
        self.wk = self.xlApp.Workbooks.Add()
        self.firstSheet = True
        self.lastEntry = ''
        self.hostnames = []

    def column_name(self, iVal):
        retVal = None
        if iVal <= 26:
            retVal = chr(64+iVal)
        else:
            m = int(iVal/26)
            n = iVal - m*26
            if n==0:
                m = m-1
                n = 26
            retVal = f'{value_colName(m)}{value_colName(n)}' 
        return retVal

    def generate_sheets(self, hostname, data):
        
        headings = [
                    'Switch', 
                    'Ifce',
                    'Description',
                    'Status',
                    'VLAN',
                    'Duplex',
                    'Speed',
                    'Type',
                    'MAC',
                    'OUI Vendor',
                    'IP Address',
                    'Alt Desc (CDP Neighbors)'
                    ]

        columnNames = [self.column_name(x+1) for x in range(len(headings))]

        if self.firstSheet:    
                self.sh = self.wk.Worksheets.Add()
        else:
            self.sh = self.wk.Worksheets.Add(After=self.wk.Worksheets(self.lastEntry))

        self.sh.Name = hostname
        self.hostnames.append(hostname)
        self.sh.Activate
        for col, val in enumerate(headings):
            self.sh.Range('{}{}'.format(self.column_name(col + 1), 1)).Value2 = val
            self.sh.Range('{}{}'.format(self.column_name(col + 1), 1)).Style = 'Accent3'
        
        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).Value2 = data
        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).Style = 'Output'
        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).EntireColumn.AutoFit()

        if self.firstSheet:
            self.firstSheet = False

        self.lastEntry = hostname

    def generate_summary_sheet(self):
        self.sh = self.wk.Worksheets.Add(After=self.wk.Worksheets(self.lastEntry))
        self.sh.Name = 'Summary'
        
        headings = [
            'Switch', 
            ]

        columnNames = [self.column_name(x+1) for x in range(len(headings))]

        for col, val in enumerate(headings):
            self.sh.Range('{}{}'.format(self.column_name(col + 1), 1)).Value2 = val
            self.sh.Range('{}{}'.format(self.column_name(col + 1), 1)).Style = 'Accent3'

        data = [[x] for x in self.hostnames]

        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).Value2 = data
        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).Style = 'Output'
        self.sh.Range('A2:{}{}'.format(columnNames[-1], len(data))).EntireColumn.AutoFit()


def main():

    xl = Excel()
    current_path = os.path.dirname(sys.argv[0])
    os.chdir(current_path)
    ROOT = r'.' 
    conn = sqlite3.connect(os.path.join(ROOT, 'pynetcco.sqlite3'))
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT hostname FROM ifce_descriptions
        """
    hosts = []
    cur.execute(sql)
    for row in cur.fetchall():
        hostname = row[0]
        hosts.append(hostname)

    for host in hosts:
        arr = []
        sql = """
        SELECT DISTINCT
            v_ifce_status_mac.hostname as hostname,
            v_ifce_status_mac.ifce as ifce,
            v_ifce_status_mac.description as description,
            v_ifce_status_mac.status as status,
            v_ifce_status_mac.duplex as duplex,
            v_ifce_status_mac.vlan as vlan,
            v_ifce_status_mac.speed as speed,
            v_ifce_status_mac.type as type,
            v_ifce_status_mac.mac as mac,
            v_ifce_status_mac.oui_vendor as oui_vendor,
            macs_to_ips.ip_addr as ip_addr,
            cdp_neighbors.remote_switch as remote_switch,
            cdp_neighbors.remote_ifce as remote_ifce,
            cdp_neighbors.remote_sw_type as remote_sw_type
            FROM
            v_ifce_status_mac
            LEFT OUTER JOIN macs_to_ips ON
            v_ifce_status_mac.mac = macs_to_ips.mac_addr
            LEFT OUTER JOIN cdp_neighbors ON
            v_ifce_status_mac.hostname = cdp_neighbors.hostname AND
                v_ifce_status_mac.ifce = cdp_neighbors.local_ifce
            WHERE v_ifce_status_mac.hostname = ?
        """
        cur.execute(sql, (host,))
        for row in cur.fetchall():
            hostname, ifce, description, status, duplex, vlan, \
                speed, _type, mac, oui_vendor, ip_addr, remote_switch, remote_ifce, remote_sw_type = row

            hostname = hostname.upper()
            remote_switch = remote_switch if remote_switch else ''
            remote_ifce = remote_ifce if remote_ifce else ''
            remote_sw_type = remote_sw_type if remote_sw_type else ''
            alt_desc = ''
            if remote_switch and '.' in remote_switch:
                remote_switch = remote_switch.split('.')[0].upper()
            if all([remote_switch, remote_ifce, remote_sw_type]):
                alt_desc = f"{remote_switch} {remote_ifce} ({remote_sw_type})"
            arr.append([hostname, ifce, description, status, vlan, duplex, speed, _type, mac, oui_vendor, ip_addr, alt_desc])

        xl.generate_sheets(hostname, arr)

    xl.generate_summary_sheet()
    cur.close()
    conn.close()

    pretty_print(arr)

main()