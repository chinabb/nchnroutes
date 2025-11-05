#!/usr/bin/env python3
import argparse
import csv
from ipaddress import IPv4Network, IPv6Network
import math

parser = argparse.ArgumentParser(description='Generate non-China routes for BIRD and Mikrotik firewall address list script.')
parser.add_argument('--exclude', metavar='CIDR', type=str, nargs='*',
                    help='IPv4 ranges to exclude in CIDR format')
parser.add_argument('--next', default="wg0", metavar = "INTERFACE OR IP",
                    help='next hop for where non-China IP address, this is usually the tunnel interface')
parser.add_argument('--ipv4-list', choices=['apnic', 'clang'], default=['apnic', 'clang'], nargs='*',
                    help='IPv4 lists to use when subtracting China based IP, multiple lists can be used at the same time (default: apnic clang)')
parser.add_argument('--ipv6-list', choices=['apnic', 'clang'], default=['apnic', 'clang'], nargs='*',
                    help='IPv6 lists to use when subtracting China based IP, multiple lists can be used at the same time (default: apnic clang)')
args = parser.parse_args()

class Node:
    def __init__(self, cidr, parent=None):
        self.cidr = cidr
        self.child = []
        self.dead = False
        self.parent = parent

    def __repr__(self):
        return "<Node %s>" % self.cidr

def dump_tree(lst, ident=0):
    for n in lst:
        print("+" * ident + str(n))
        dump_tree(n.child, ident + 1)

# get_live_cidrs: Collect the CIDRs of non-dead leaf nodes for sorting.
def get_live_cidrs(lst):
    result = []
    for n in lst:
        if n.dead:
            continue
        if len(n.child) > 0:
            result.extend(get_live_cidrs(n.child))
        else:
            result.append(n.cidr)
    return result

# dump_bird: Generates BIRD route configurations, sorted by IP address.
def dump_bird(lst, f):
    cidrs = get_live_cidrs(lst)
    # Sort by network_address and prefixlen.
    for cidr in sorted(cidrs, key=lambda x: (x.network_address, x.prefixlen)):
        f.write('route %s via "%s";\n' % (cidr, args.next))

# dump_subnet: Generate subnet files, sorted by IP address.
def dump_subnet(lst, f):
    cidrs = get_live_cidrs(lst)
    # Sort by network_address and prefixlen.
    for cidr in sorted(cidrs, key=lambda x: (x.network_address, x.prefixlen)):
        f.write(f'{cidr}\n')

# dump_mikrotik: Generate a list of Mikrotik routing firewall address list, sorted by IP address.
def dump_mikrotik(lst, f, t):
    if t==6:
        f.write("/ipv6 firewall address-list\n")
        f.write("remove [/ipv6 firewall address-list find list=noCNv6]\n")
        n="noCNv6"
    else:
        f.write("/ip firewall address-list\n")
        f.write("remove [/ip firewall address-list find list=noCN]\n")
        n="noCN"    
    cidrs = get_live_cidrs(lst)
    # Sort by network_address and prefixlen.
    for cidr in sorted(cidrs, key=lambda x: (x.network_address, x.prefixlen)):
        f.write('add list=%s address=%s\n' % (n, cidr))

RESERVED = [
    IPv4Network('0.0.0.0/8'), #RFC1700,Current (local, "this") network
    IPv4Network('10.0.0.0/8'), #RFC1918,Private network A
    IPv4Network('100.64.0.0/10'), #RFC6598,carrier-grade NAT
    IPv4Network('127.0.0.0/8'), #RFC990,loopback addresses
    IPv4Network('169.254.0.0/16'), #RFC3927,Dynamic link-local addresses
    IPv4Network('172.16.0.0/12'), #RFC1918,Private network B
    IPv4Network('192.0.0.0/24'), #RFC5736,IETF Protocol Assignments, DS-Lite
    IPv4Network('192.0.2.0/24'), #RFC5737,Assigned as TEST-NET-1
    IPv4Network('192.88.99.0/24'), #RFC3068,6to4 relay
    IPv4Network('192.168.0.0/16'), #RFC1918,Private network C
    IPv4Network('198.18.0.0/15'), #RFC2544,benchmark testing of inter-network
    IPv4Network('198.51.100.0/24'), #RFC5737,Assigned as TEST-NET-2
    IPv4Network('203.0.113.0/24'), #RFC5737,Assigned as TEST-NET-3
    IPv4Network('224.0.0.0/4'), #RFC1112,In use for multicast(Class D)
    IPv4Network('233.252.0.0/24'), #RFC5771,Assigned as MCAST-TEST-NET
    IPv4Network('240.0.0.0/4'), #RFC6890,Reserved for future use(Class E)
    IPv4Network('255.255.255.255/32'), #RFC6890,limited broadcast destination address
]
RESERVED_V6 = [
    IPv6Network('2001::/32'), #RFC6890,Teredo tunneling
    IPv6Network('2001:10::/28'), #RFC4843,ORCHID
    IPv6Network('2001:20::/28'), #RFC7374,ORCHIDv2
    IPv6Network('2001:db8::/32'), #RFC3849,used in documentation and example
    IPv6Network('2002::/16'), #RFC3056,6to4 addressing scheme
]
if args.exclude:
    for e in args.exclude:
        if ":" in e:
            RESERVED_V6.append(IPv6Network(e))

        else:
            RESERVED.append(IPv4Network(e))

IPV6_UNICAST = IPv6Network('2000::/3')

def subtract_cidr(sub_from, sub_by):
    for cidr_to_sub in sub_by:
        for n in sub_from:
            if n.cidr == cidr_to_sub:
                n.dead = True
                break

            if n.cidr.supernet_of(cidr_to_sub):
                if len(n.child) > 0:
                    subtract_cidr(n.child, sub_by)

                else:
                    n.child = [Node(b, n) for b in n.cidr.address_exclude(cidr_to_sub)]

                break

root = []
root_v6 = [Node(IPV6_UNICAST)]

with open("ipv4-address-space.csv", newline='') as f:
    f.readline() # skip the title

    reader = csv.reader(f, quoting=csv.QUOTE_MINIMAL)
    for cidr in reader:
        if cidr[5] == "ALLOCATED" or cidr[5] == "LEGACY":
            block = cidr[0]
            cidr = "%s.0.0.0%s" % (block[:3].lstrip("0"), block[-2:], )
            root.append(Node(IPv4Network(cidr)))

with open("delegated-apnic-latest") as f:
    for line in f:
        if 'apnic' in args.ipv4_list and "apnic|CN|ipv4|" in line:
            line = line.split("|")
            a = "%s/%d" % (line[3], 32 - math.log(int(line[4]), 2), )
            a = IPv4Network(a)
            subtract_cidr(root, (a,))

        elif "apnic|CN|ipv6|" in line:
            line = line.split("|")
            a = "%s/%s" % (line[3], line[4])
            a = IPv6Network(a)
            subtract_cidr(root_v6, (a,))

if 'clang' in args.ipv4_list:
    with open("all_cn.txt") as f:
        for line in f:
            line = line.strip('\n')
            a = IPv4Network(line)
            subtract_cidr(root, (a,))

if 'clang' in args.ipv6_list:
    with open("all_cn_ipv6.txt") as f:
        for line in f:
            line = line.strip('\n')
            a = IPv6Network(line)
            subtract_cidr(root_v6, (a,))

# get rid of reserved IPv4 addresses
subtract_cidr(root, RESERVED)
# get rid of reserved IPv6 addresses
subtract_cidr(root_v6, RESERVED_V6)

with open("routes4.conf", "w") as f, open("subnet4.txt", "w") as g, open("noCN.rsc", "w") as h:
    dump_bird(root, f)
    dump_subnet(root, g)
    dump_mikrotik(root, h, 4)

with open("routes6.conf", "w") as f, open("subnet6.txt", "w") as g, open("noCNv6.rsc", "w") as h:
    dump_bird(root_v6, f)
    dump_subnet(root_v6, g)
    dump_mikrotik(root_v6, h, 6)

