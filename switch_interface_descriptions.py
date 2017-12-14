__author__ = 'Ricardo da Paz'

import os
import sys
import re
import json
import sqlite3

from io import StringIO

def pretty_print(o):
    print (json.dumps(o, indent=4))


def try_to_i(s):
    try:
        return int(s)
    except:
        return s

def slices(input_text, *args):
    """
    Returns slices of text defined by the length of each
    fixed width field in the text.  Use list(slices(input, *args) to
    get a list when calling this function.
    """
    position = 0
    for length in args:
        yield input_text[position:position + length].strip()
        position += length

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


# ----------------------------------
# ---        Core Functions     ----
# ----------------------------------


class ShowCommandAnalyser:

    def __init__(self, inputText):
        self.inputText = inputText
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

    def analyse(self):
        self.cdpNeighboursString = self.commandText('show cdp nei')
        self.cdpNeighbours()

        self.interfaceDescriptions()
        self.interfaceStatusString = self.commandText('show int status')

        self.interfaceStatus()

        self.macAddressString = self.commandText('show mac add')
        self.macAddresses()
        
        self.macToIPsString = self.commandText('show ip arp')
        self.macToIPs()

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

        for entry in data:
            remote_switch, local_ifce, holdtime, capability, remote_sw_type, remote_ifce = '', '', '', '', '', ''

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
            if m: 
                remote_switch = m.group(1).strip()
                local_ifce = clean_up_ifce(m.group(2).strip())
                holdtime = m.group(3).strip()
                capability = m.group(4).strip()
                remote_sw_type = m.group(5).strip()
                remote_ifce = clean_up_ifce(m.group(6).strip())
                sql = """
                    INSERT INTO cdp_neighbors (hostname, remote_switch, local_ifce,
                    holdtime, capability, remote_sw_type, remote_ifce)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ary = [self.hostName, remote_switch, local_ifce, holdtime, capability, remote_sw_type, remote_ifce]
                cur.execute(sql, ary)
                conn.commit()

    def macAddresses(self):
        """
        ================================================
        implements handling of the show mac-addr command
        ================================================
        """
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
                ifce = m.group(4)
                oui_vendor = ''
                if mac_address[:6] in oui_mac_addresses:
                    oui_vendor = oui_mac_addresses[mac_address[:6]]
                oui_vendor = oui_vendor.upper()

                if re.search(r'^(Gi|Te|Et|Fa)', ifce, re.IGNORECASE):
                    ary = [self.hostName, ifce, vlan, mac_address, oui_vendor]
                    sql = """
                        INSERT OR IGNORE INTO mac_addresses (hostname, ifce, vlan, mac_address, oui_vendor)
                        VALUES (?, ?, ?, ?, ?) 
                        """
                    cur.execute(sql, ary)
                    conn.commit()

    def interfaceDescriptions(self):

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

    def interfaceStatus(self):
        """
        ==================================================
        implements handling of the show int status command
        ==================================================
        """

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

    def macToIPs(self):
        """
        ===============================================
        implements handling of the show ip arp command
        ===============================================
        """
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


if __name__ == '__main__':

    current_path = os.path.dirname(sys.argv[0])
    os.chdir(current_path)
    ROOT = r'.' 
    rootdir = os.path.join(ROOT, 'show_commands')

    global oui_mac_addresses
    with open(os.path.join(ROOT, 'mac_addresses.json'), 'r') as infile:
        oui_mac_addresses = json.load(infile)

    global conn
    conn = sqlite3.connect(os.path.join(ROOT, 'pynetcco.sqlite3'))
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
                    analyser = ShowCommandAnalyser(run_text)
                    analyser.analyse()

    conn.close()