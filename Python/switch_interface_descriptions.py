__author__ = 'Ricardo da Paz'

import os
import os.path
import re
import json
import win32com.client
import sqlite3


# Try to import the faster cStringIO
# module if this is available for tswitch_sfp_report.pyhe platform
# default to the StringIO version, written in
# Python
# -----------------
# Utility Functions
# -----------------
# try:
#     from cStringIO import StringIO
# except NotImplementedError:
#     from StringIO import StringIO

from io import StringIO

def pretty_print(o):
    print (json.dumps(o, indent=4))


def try_to_i(s):
    try:
        return int(s)
    except:
        return s

def mergeTwoDicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    if all([x, y]):
        z = x.copy()
        z.update(y)
        return z
    elif x and not y:
        return x
    elif y and not x:
        return y
    else:
        return {}


def slices(input_text, *args):
    """
    Returns slices of text defined by the length of each
    fixed width field in the text.  Use list(slices(input, *args) to
    get a list when calling this function.
    :param input_text:
    :param args:
    :return a generator:
    """
    position = 0
    for length in args:
        yield input_text[position:position + length].strip()
        position += length


def clean_up_hostname(s):
    '''sw = ''
    if '.' in s:
        sw = s.split('.')[0]
    else:
        sw = s
    '''
    return s


def take2(theList, ref):
    returnVal = []
    if ref in theList:
        idx = theList.index(ref)
        if theList.index(ref) < len(theList) - 1:
            returnVal = [theList[idx], theList[idx+1]]
        else:
            returnVal = [theList[idx], None]
    else:
        pass
    return returnVal


def clean_up_ifce(s):
    regex = re.compile(r'(\w+)'         # i.e. Gig or Ten or Fas
                       r'\s'            # followed by a space
                       r'([\d\/+]+)',   # followed by digit and optical slash, possibly repeated
                       re.VERBOSE)
    m = regex.search(s)
    ifce_name = ''
    ifce_no = ''
    if m:
        ifce_name = m.group(1)[:2]
        ifce_no = m.group(2)
        return '{}{}'.format(ifce_name, ifce_no)
    else:
        return None


def column_name(column_number):
    dividend = column_number
    column_name = ''
    modulo = 0
    while dividend > 0:
        modulo = (dividend - 1) % 26
        column_name = str(chr(65 + modulo)) + column_name
        dividend = int((dividend - modulo) / 26)
    return column_name


def format_cells(sheet, row):
    sheet.Range("B13:L13").EntireColumn.AutoFit()
    sheet.Range("B13:L13").Style = "Accent3"
    sheet.Range("B2:L2").Style = "Heading 1"
    sheet.Range("B4:B11").Style = "Output"
    sheet.Range("C4:C11").Style = "Calculation"
    sheet.Range("B{}:L{}".format(row, row)).Style = "Output"
    sheet.Range("E13").EntireColumn.HorizontalAlignment = -4108 #xlCenter
    sheet.Range("F13").EntireColumn.HorizontalAlignment = -4108 #xlCenter
    sheet.Range("G13").EntireColumn.HorizontalAlignment = -4108 #xlCenter


# ----------------------------------
# ---        Core Functions     ----
# ----------------------------------


class ShowCommandAnalyser:

    def __init__(self, inputText, ifceDesData, ifceStatusData, cdpData, macToIpData, macAddrData):
        self.inputText = inputText
        self.ifceDesData = ifceDesData
        self.ifceStatusData = ifceStatusData
        self.cdpData = cdpData
        self.macToIPData = macToIpData
        self.macAddrData = macAddrData
        self.COMMANDS = [
            'show cdp nei',
            'show int status',
            'show ip arp',
            'show mac add',
            'show int | inc (rops|otoc)',
            'show run',
            'show ver',
            'show ip route',
            'show inv',
        ]
        self.cdpNeighboursString = self.commandText('show cdp nei')
        self.macAddressString = self.commandText('show mac add')
        self.interfaceStatusString = self.commandText('show int status')
        self.macToIPsString = self.commandText('show ip arp') if self.commandText('show ip arp') else ''

        self.cdpData = mergeTwoDicts(self.cdpData, self.cdpNeighbours)
        self.macAddrData = mergeTwoDicts(self.macAddrData, self.macAddresses)
        self.macToIPData = mergeTwoDicts(self.macToIPData, self.macToIPs)
        self.ifceStatusData = mergeTwoDicts(self.ifceStatusData, self.interfaceStatus)
        self.ifceDesData = mergeTwoDicts(self.ifceDesData, self.interfaceDescriptions)

    def commandText(self, command_name):
        begin, end = take2(self.COMMANDS, command_name)
        # end = end if end else r'\Z'
        marker_regexes = "(?<={})(.*)(?={})".format(begin, end)
        m = re.search(r"{0:s}".format(marker_regexes), self.inputText,
                      re.DOTALL | re.IGNORECASE)
        cmd_text = None
        if m:
            cmd_text = m.group(1)
        return cmd_text

    @property
    def hostName(self):
        hostname = ''
        for line in self.inputText.split('\n'):
            if re.search(r'hostname\s+(.*)', line, re.IGNORECASE):
                hostname = line.split(' ')[1]
                break
        return hostname

    @property
    def cdpNeighbours(self):
        """
        ===============================================
        implements handling of the show cdp nei command
        ===============================================
        NS1602#show cdp nei
        Capability Codes: R - Router, T - Trans Bridge, B - Source Route Bridge
                          S - Switch, H - Host, I - IGMP, r - Repeater, P - Phone,
                          D - Remote, C - CVTA, M - Two-port Mac Relay
    
        Device ID        Local Intrfce     Holdtme    Capability  Platform  Port ID
        OPDC-CORE1.bene.irnnew.bhpbilliton.net.a
                         Gig 1/1/1         175             R S I  WS-C3850- Gig 1/0/5
    
        Total cdp entries displayed : 1
        NS1602
        """
        # conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')     
        cur = conn.cursor()
        sql = """
        CREATE TABLE IF NOT EXISTS cdp_neighbors (
            id integer PRIMARY KEY,
            hostname text,
            remote_switch text,
            local_ifce text,
            holdtime text,
            capability text,
            remote_sw_type text,
            remote_ifce text
        );
        """
        cur.execute(sql)

        results = {}
        failures = []

        regex = re.compile(r'(?<=Port ID)(.*)(?={0:s})'.format(self.hostName), (re.DOTALL | re.IGNORECASE))
        m = regex.search(self.cdpNeighboursString)
        snippet = ''
        if m:
            snippet = m.group(1)

        out = StringIO()

        for line in snippet.splitlines():
            if re.search(r'^$', line) or \
                    re.search(r'Total cdp entries', line, re.IGNORECASE):
                continue
            else:
                print (line, file=out)

        input_text = out.getvalue()

        split_at = re.compile(r'(?<=\d)\n', (re.MULTILINE | re.DOTALL))
        data = re.split(split_at, input_text)
        data = [x for x in data if len(x) > 0]

        new_data = []

        for entry in data:
            remote_switch, local_ifce, holdtime, capability, remote_sw_type, remote_ifce = '', '', '', '', '', ''

            # Below regex tested on http://regexr.com/
            # regex = re.compile(r'(.*)\s+((?:Gig|Ten|Fas|Eth)\s+(?:.*))\s+(\d+)\s+((?:[RSIC]\s?)+)+\s+(.*)\s+((?:Gig|Ten|Fas|Eth)\s(?:.*))')
            regex = re.compile(r'(.*)\s+'
                               r'('
                                    r'(?:Gig|Ten|Fas|Eth)\s+'
                                    r'(?:.*)'
                               r')\s+'
                               r'(\d+)\s+'
                               r'('
                                    r'(?:[RSTIC]\s?)+'
                               r')+\s+'
                               r'(.*)\s+'
                               r'('
                                    r'(?:Gig|Ten|Fas|Eth)\s'
                                    r'(?:.*)'
                               r')',
                               re.VERBOSE)

            m = regex.search(entry)
            if m: # match is found
                remote_switch = clean_up_hostname(m.group(1).strip())
                local_ifce = clean_up_ifce(m.group(2).strip())
                holdtime = m.group(3).strip()
                capability = m.group(4).strip()
                remote_sw_type = m.group(5).strip()
                remote_ifce = clean_up_ifce(m.group(6).strip())

                print(self.hostName, remote_switch, local_ifce, holdtime, capability, remote_sw_type, remote_ifce, sep='|')
                new_data.append([remote_switch,
                                 local_ifce,
                                 holdtime,
                                 capability,
                                 remote_sw_type,
                                 remote_ifce])
            else: # no match found for this entry, record failure for future inspection
                if self.hostName not in failures:
                    failures.append(self.hostName)

        # new_data = sorted(new_data, key=lambda x: (x[0], map(try_to_i, x[1].split('/'))))


        for remote_switch, local_ifce, _, _, remote_sw_type, remote_ifce in new_data:

            if self.hostName not in results:
                results[self.hostName] = {}

            if local_ifce not in results[self.hostName]:
                results[self.hostName][local_ifce] = {}

            results[self.hostName][local_ifce]['remote_switch'] = remote_switch
            results[self.hostName][local_ifce]['remote_ifce'] = remote_ifce
            results[self.hostName][local_ifce]['remote_sw_type'] = remote_sw_type
            
            sql = """
                INSERT INTO cdp_neighbors (hostname, remote_switch, local_ifce,
                holdtime, capability, remote_sw_type, remote_ifce)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            ary = [self.hostName, remote_switch, local_ifce, holdtime, capability, remote_sw_type, remote_ifce]
            cur.execute(sql, ary)
            conn.commit()
            
            
        # conn.close()
        return results

    @property
    def macAddresses(self):
        """
        ================================================
        implements handling of the show mac-addr command
        ================================================
        """
        results = {}
        failures = []

        regex = re.compile(r'(?<=Ports)(.*)(?={0:s})'.format(self.hostName), (re.DOTALL | re.IGNORECASE))
        m = regex.search(self.macAddressString)
        snippet = ''
        if m:
            snippet = m.group(1)

        out = StringIO()

        for line in snippet.splitlines():
            if re.search(r'^$', line) or \
                    re.search(r'^\-+', line) or \
                    re.search(r'Total Mac', line, re.IGNORECASE):
                continue
            else:
                print(line, file=out)
        input_text = out.getvalue()

        # conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')
        cur = conn.cursor()
        sql = """
            CREATE TABLE IF NOT EXISTS mac_addresses (
            id integer PRIMARY KEY,
            hostname text,
            ifce text,
            vlan text,
            mac_address text,
            oui_vendor text,
            UNIQUE(mac_address, oui_vendor)
            )
            """

        cur.execute(sql)
        conn.commit()
        
        for line in input_text.splitlines():

            regex = re.compile(r'(?:^[\s*R]+)?'
                               r'((?:All|\d+))'
                               r'\s+'
                               r'((?:[0-9a-f]{4}\.?){3})'
                               r'\s+'
                               r'(static|dynamic)'
                               r'\s+'
                               r'(?:Yes|No)?'
                               r'(?:\s+)?'
                               r'(?:[0-9\-]+)?'
                               r'(?:\s+)'
                               r'(.*)', (re.IGNORECASE | re.VERBOSE))

            m = regex.search(line)

            if m:
                vlan = m.group(1).strip()
                mac_address = m.group(2).strip()
                mac_address = "".join(mac_address.split('.'))
                _ = m.group(3)
                ifce = m.group(4)
                oui_vendor = ''
                if mac_address[:6] in oui_mac_addresses:
                    oui_vendor = oui_mac_addresses[mac_address[:6]]
                oui_vendor = oui_vendor.upper()

                if re.search(r'^(Gi|Te|Et|Fa)', ifce, re.IGNORECASE):
                    if self.hostName not in results:
                        results[self.hostName] = {}

                    if ifce not in results[self.hostName] and self.hostName not in ifce:
                        results[self.hostName][ifce] = []

                    results[self.hostName][ifce].append(mac_address)
                    results[self.hostName][ifce] = list(set(results[self.hostName][ifce]))


                    ary = [self.hostName, ifce, vlan, mac_address, oui_vendor]
                    sql = """
                        INSERT OR IGNORE INTO mac_addresses (hostname, ifce, vlan, mac_address, oui_vendor)
                        VALUES (?, ?, ?, ?, ?) 
                        """
                    cur.execute(sql, ary)
                    conn.commit()

            else:
                if self.hostName not in failures:
                    failures.append('{}: {}'.format(self.hostName, line))

        # conn.close()
        return results

    @property
    def interfaceDescriptions(self):

        results = {}

        output = StringIO()
        inside_block = False

        for line in self.inputText.splitlines():
            if (re.search('interface', line, re.IGNORECASE) and
                    not re.search('vlan', line, re.IGNORECASE)) \
                    or inside_block:
                inside_block = True
            if inside_block and re.search(r'interface Vlan', line, re.IGNORECASE):
                inside_block = False
            if inside_block:
                print(line, file=output)

        ifce_config_lines = output.getvalue()

        snippets = re.split(r'\n!\n', ifce_config_lines)
        snippets = [x for x in snippets if len(x) > 0]

        ifce = ''
        description = ''

        # conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')
        cur = conn.cursor()
        sql = """
            CREATE TABLE IF NOT EXISTS ifce_descriptions (
            id integer PRIMARY KEY,
            hostname text,
            ifce text,
            description text
            )
            """
        cur.execute(sql)
        conn.commit()

        for entry in snippets:
            m = re.search(r'interface (?P<name>.*)', entry)
            if m:
                ifce = m.group('name').replace('TenGigabitEthernet', 'Te'). \
                    replace('GigabitEthernet', 'Gi'). \
                    replace('FastEthernet', 'Fa')
            m = re.search(r'description (?P<desc>.*)', entry)
            if m:
                description = m.group('desc')
            else:
                m = re.search(r'shutdown', entry)
                if m:
                    description = 'ADMINISTRATIVELY DISABLED'
                else:
                    description = ''

            if self.hostName not in results:
                results[self.hostName] = {}

            if ifce and ifce not in results[self.hostName]:
                results[self.hostName][ifce] = description


            m1 = re.search(r'^$', ifce)
            m2 = re.search(r'loopback', ifce, re.IGNORECASE)
            m3 = re.search(r'default', ifce, re.IGNORECASE)
            m4 = re.search(r'port\-channel', ifce, re.IGNORECASE)

            if ifce and len(ifce) > 0 and not m1 and not m2 and not m3 and not m4:
                sql = """
                    INSERT INTO ifce_descriptions (hostname, ifce, description)
                    VALUES (?, ?, ?)
                    """
                ary = [self.hostName, ifce, description]

                cur.execute(sql, ary)
                conn.commit()


        # conn.close()
        return results

    @property
    def interfaceStatus(self):
        """
        ==================================================
        implements handling of the show int status command
        ==================================================
        """
        results = {}
        failures = []

        regex = re.compile(r'(?<=Type)(.*)(?={0:s})'.format(self.hostName), (re.DOTALL | re.IGNORECASE))
        m = regex.search(self.interfaceStatusString)
        snippet = ''

        if m:
            snippet = m.group(1)
            out = StringIO()

            for line in snippet.splitlines():
                if re.search(r'^$', line) or \
                                self.hostName in line:
                    continue
                else:
                    print(line, file=out)

            snippet = out.getvalue()

            regex = re.compile(r'((?:Gi|Fa|Te|Po)(?:[0-9\/]+))\s+'
                               r'(.*)\s+'
                               r'(connected|notconnect|disabled)\s+'
                               r'(\d+|routed|trunk)\s+'
                               r'(a-full|a-half|full|half|auto)\s+'
                               r'((?:a-)?1?(?:0+|auto))\s+'
                               r'(.*)', (re.IGNORECASE | re.VERBOSE))

            # conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')
            cur = conn.cursor()
            sql = """
                CREATE TABLE IF NOT EXISTS ifce_status (
                id integer PRIMARY KEY,
                hostname text,
                ifce text,
                description text,
                status text,
                vlan text,
                duplex text,
                speed text,
                type text
                )
                """

            cur.execute(sql)
            conn.commit()

            for line in snippet.splitlines():
                m = regex.search(line)
                if m:

                    ifce = m.group(1).strip()
                    ifce_name = m.group(2).strip()
                    status = m.group(3).strip()
                    vlan = m.group(4).strip()
                    duplex = m.group(5).strip()
                    speed = m.group(6).strip()
                    type = m.group(7).strip()

                    headers = ['ifce_name', 'status', 'vlan', 'duplex', 'speed', 'type']


                    m1 = re.search(r'^$', ifce)
                    m2 = re.search(r'loopback', ifce, re.IGNORECASE)
                    m3 = re.search(r'default', ifce, re.IGNORECASE)
                    if ifce and len(ifce) > 0 and not m1 and not m2 and not m3:
                        ary = [self.hostName, ifce, ifce_name, status, vlan, duplex, speed, type]
                        sql = """
                            INSERT INTO ifce_status (hostname, ifce, description, status, vlan, duplex, speed, type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """
                        cur.execute(sql, ary)
                        conn.commit()

                    if self.hostName not in results:
                        results[self.hostName] = {}

                    if ifce and ifce not in results[self.hostName]:
                        results[self.hostName][ifce] = dict(zip(headers,
                                                         [ifce_name,
                                                          status,
                                                          vlan,
                                                          duplex,
                                                          speed,
                                                          type]))
                else:
                    if self.hostName not in failures:
                        failures.append(self.hostName)

        # conn.close()
        return results

    @property
    def macToIPs(self):
        """
        ===============================================
        implements handling of the show ip arp command
        ===============================================
        """
        results = {}
        regex = re.compile(r'(?<=Interface)(.*)(?={0:s})'.format(self.hostName), (re.DOTALL | re.IGNORECASE))
        m = regex.search(self.macToIPsString)

        # conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')
        cur = conn.cursor()
        sql = """
            CREATE TABLE IF NOT EXISTS macs_to_ips (
            id integer PRIMARY KEY,
            mac_addr,
            ip_addr
            )
            """
        cur.execute(sql)
        conn.commit()

        snippet = ''
        if m:
            snippet = m.group(1)

            for line in snippet.splitlines():
                if len(line.split()) == 6:

                    _, ip_addr, _, mac_addr, _, _ = line.split()
                    mac_addr = "".join(mac_addr.split('.'))

                    sql = """
                    INSERT INTO macs_to_ips (mac_addr, ip_addr)
                    VALUES (?, ?)
                    """
                    ary = [mac_addr, ip_addr]
                    cur.execute(sql, ary)
                    conn.commit()

                    if mac_addr not in results:
                        results[mac_addr] = ip_addr
        # conn.close()
        return results

    def updateValues(self):
        return (self.cdpData, self.ifceDesData,
                self.ifceStatusData, self.macAddrData,
                self.macToIPData)

    def __repr__(self):
        from pprint import pformat
        return pformat(vars(self), indent=4, width=1)

class Reporter:

    def __init__(self, ifceDesData, ifceStatusData, cdpData, macToIpData, macAddrData, ouiMACData):
        self.ifceDesData = ifceDesData
        self.ifceStatusData = ifceStatusData
        self.cdpData = cdpData
        self.macToIPData = macToIpData
        self.macAddrData = macAddrData
        self.ouiMACData = ouiMACData
        pretty_print(self.cdpData)
        pretty_print(self.ifceStatusData)
        pretty_print(self.macAddrData)

        self.generateInterfaceDescriptions()

    def generateInterfaceDescriptions(self):
        ary = []
        for switch, rest in self.ifceStatusData.items():
            print (switch)
            for ifce, properties in rest.items():
                mac = ''
                oui = ''
                ip_addr = ''
                desc = ''
                config_desc = ''
                # Check to see how many mac_addresses in the interface
                mac_ary = []

                def isGEDevice(mac_addr):
                    oui_prefix = mac_addr[:6].lower()
                    return oui_prefix in self.ouiMACData and \
                        self.ouiMACData[oui_prefix] in [
                            'GE Fanuc Automation Manufacturing, Inc.',
                            'GENERAL ELECTRIC CORPORATION'
                        ]

                if switch in self.ifceDesData and ifce in self.ifceDesData[switch]:
                    config_desc = self.ifceDesData[switch][ifce]
                    config_desc.replace('=', '~')

                if switch in self.macAddrData and ifce in self.macAddrData[switch]:
                    mac_ary = self.macAddrData[switch][ifce]
                    if len(mac_ary) == 1:
                        mac = mac_ary[0].lower()
                        oui = oui_mac_addresses[mac[:6]] if mac[:6] in oui_mac_addresses else 'OUI Not Found'
                        if mac in self.macToIPData:
                            ip_addr = self.macToIPData[mac]
                    elif len(mac_ary) > 1:
                        print(switch, ifce, sep="|")
                        print(switch in self.cdpData and ifce in self.cdpData[switch])
                        if switch in self.cdpData and ifce in self.cdpData[switch]:
                            desc = 'Connects to {} ({}), port {}'.format(self.cdpData[switch][ifce]['remote_switch'],
                                                                         self.cdpData[switch][ifce]['remote_sw_type'],
                                                                         self.cdpData[switch][ifce]['remote_ifce'])
                        elif any([isGEDevice(x) for x in mac_ary]):
                            desc = 'GE Device behind media converter'
                        else:
                            desc = 'More than 1 MAC on interface'

                config_desc = re.sub(r'[=]+', '', config_desc)
                config_desc = re.sub(r'^\s+', '', config_desc)
                ary.append([switch,
                            ifce,
                            config_desc.upper(),
                            properties['status'],
                            properties['vlan'],
                            properties['duplex'],
                            properties['speed'],
                            properties['type'],
                            mac,
                            oui,
                            ip_addr,
                            desc.upper(),
                            ])

        # ary = sorted(ary, key=lambda x: (x[0], map(try_to_i, x[1].split('/'))))
        ary = sorted(ary, key=lambda x: (x[0], [try_to_i(a) for a in x[1].split('/')]))

        for entry in ary:
            print ("|".join(entry))

        headings = ['ifce',
                    'desc_cfg',
                    'status',
                    'vlan',
                    'duplex',
                    'speed',
                    'type',
                    'mac',
                    'oui',
                    'ip_address',
                    'desc_alt']

        xl = win32com.client.gencache.EnsureDispatch("Excel.Application")
        xl.Visible = True
        xl.DisplayAlerts = False
        wk = xl.Workbooks.Add()
        last_entry = ''

        for entry in ary:
            if entry[0] != last_entry:
                row = 13
                # Add sheet at start or after last sheet if not first one
                # if we have found a row with a new switch from the
                # last one
                if len(last_entry) < 1:
                    sh = wk.Worksheets.Add()
                else:
                    sh = wk.Worksheets.Add(After=wk.Worksheets(last_entry))

                # Define sheet name
                sh.Name = entry[0]
                sh.Activate
                xl.ActiveWindow.DisplayGridlines = False

                rge = sh.Columns("O:O")
                rge = sh.Range(rge, rge.End(-4161))
                rge.EntireColumn.Hidden = True

                # Write headings
                for col, val in enumerate(headings):
                    sh.Range('{}{}'.format(column_name(col + 2), row)).Value2 = val.upper()

                # Write other values
                # Lots of change here
                # sh.Range('B2').Value2 = 'Switch Name:'
                # sh.Range('B4').Value2 = 'Serial No(s).:'
                # sh.Range('B5').Value2 = 'IP Address:'
                # sh.Range('B6').Value2 = 'Switch 1 Type:'
                # sh.Range('B7').Value2 = 'Switch 2 Type:'
                # sh.Range('B8').Value2 = 'Switch 3 Type:'
                # sh.Range('B9').Value2 = 'Switch IOS:'
                # sh.Range('B10').Value2 = 'Switch License:'
                # sh.Range('B11').Value2 = 'Drawing No(s).:'

                # sh.Range('C2').Value2 = entry[0]
                # sh.Range('C4').Value2 = ''
                # sh.Range('C5').FormulaR1C1 = '=vlookup(RC[-1], ip_addresses, 1, 0)'
                # sh.Range('C6').FormulaR1C1 = '=vlookup(RC[-1], switch_details, 4, 0)'
                # sh.Range('C7').Value2 = 'Not Applicable'
                # sh.Range('C8').Value2 = 'Not Applicable'
                # sh.Range('C9').Value2 = '=vlookup(RC[-1], switch_details, 5, 0)'
                # sh.Range('C10').Value2 = '=vlookup(RC[-1], switch_details, 6, 0)'
                # sh.Range('C11').Value2 = ''

            # Write data
            row += 1
            sh.Range('{}{}:{}{}'.format('B', row, 'L', row)).Value2 = entry[1:]
            format_cells(sh, row)
            last_entry = entry[0]

if __name__ == '__main__':

    cdpData = {}
    macAddData = {}
    macToIPData = {}
    ifceDesData = {}
    ifceStatusData = {}

    ###################################################################################
    # ROOT = r'C:\Users\Ricardo'  # TODO: modify this to suit in target machine

    ROOT = r'C:\Users\rdapaz\Documents\projects\wp-fy17\Python'  # TODO: modify this to suit in target machine
    ##################################################################################
    rootdir = os.path.join(ROOT, 'ShowCommands')

    global oui_mac_addresses
    with open(r'C:\Users\rdapaz\Documents\projects\wp-fy17\Python\mac_addresses.json', 'r') as infile:
        oui_mac_addresses = json.load(infile)


    # with open(os.path.join(rootdir, r'oui_mac_addresses.json'), 'r') as infile:
    #     oui_mac_addresses = json.load(infile)
    global conn
    conn = sqlite3.connect(r'C:\Users\rdapaz\Desktop\pynetcco.sqlite3')
    cur = conn.cursor()

    sql_ary = [
    'DROP TABLE IF EXISTS cdp_neighbors',
    'DROP TABLE IF EXISTS ifce_descriptions',
    'DROP TABLE IF EXISTS ifce_status',
    'DROP TABLE IF EXISTS mac_addresses',
    'DROP TABLE IF EXISTS macs_to_ip',
    ]
    for sql in sql_ary:
        cur.execute(sql)
        conn.commit()

    for subdir, dirs, files in os.walk(rootdir):
        for my_file in files:
            if re.search(r'(txt|log)$', my_file, re.IGNORECASE):
                with open(os.path.join(subdir, my_file), 'r') as f:
                    run_text = f.read()
                    analyser = ShowCommandAnalyser(inputText=run_text, cdpData=cdpData, ifceDesData=ifceDesData,
                                                   ifceStatusData=ifceStatusData, macAddrData=macAddData,
                                                   macToIpData=macToIPData)

                    cdpData, ifceDesData, ifceStatusData, macAddData, macToIPData = analyser.updateValues()

    # report = Reporter(cdpData=cdpData, ifceDesData=ifceDesData,
    #                   ifceStatusData=ifceStatusData, ouiMACData=oui_mac_addresses,
    #                   macAddrData=macAddData, macToIpData=macToIPData)
    conn.close()