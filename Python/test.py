# -*- coding: UTF-8 -*-
import pprint
import json


def pretty_printer(o):
	try:
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(o)
	except:
		pass


with open(r'C:\Users\rdapaz\Documents\wp-fy17\Python\mac_addresses.txt', 'r', encoding='UTF-8') as infile:
    mac_addresses = infile.readlines()


mac_addresses = [x.split('\t') for x in mac_addresses if len(x) > 0]

le_macs = {}
for entry in mac_addresses:
	mac = entry[0][:8].lower()
	mac = "".join(mac.split(':'))
	if len(entry) == 2:
		le_macs[mac] = entry[1].strip()
	elif len(entry) == 3:
		le_macs[mac] = entry[2].strip()

with open(r'C:\Users\rdapaz\Documents\wp-fy17\Python\mac_addresses.json', 'w') as outfile:
	json.dump(le_macs, outfile, indent=True)
