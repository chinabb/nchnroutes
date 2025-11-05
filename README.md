# nchnroutes

This project is forked from https://github.com/dndx/nchnroutes. For more information, please see his blog posts 
(Chinese version only): https://idndx.com/use-routeros-ospf-and-raspberry-pi-to-create-split-routing-for-different-ip-ranges/

Similar to chnroutes, but instead generates routes that are not originating from Mainland China and generates 
result in BIRD static route format and Mikrotik firewall address list format.

Both IPv4 and IPv6 are supported.

As of Nov 2025, the size of generated table is roughly 13000-14000 entries for IPv4 (depends on the IP list used) 
and 17000-18000 for IPv6. On a Raspberry Pi 4 with BIRD, full loading and convergence over OSPF with RouterOS running 
on Mikrotik hEX takes around 5 seconds.

Requires Python 3, no additional dependencies.

```
usage: produce.py [-h] [--exclude [CIDR [CIDR ...]]] [--next INTERFACE OR IP]

Generate non-China routes for BIRD.

optional arguments:
  -h, --help            show this help message and exit
  --exclude [CIDR [CIDR ...]]
                        IPv4 ranges to exclude in CIDR format
  --next INTERFACE OR IP
                        next hop for where non-China IP address, this is
                        usually the tunnel interface
  --ipv4-list [{apnic,clang} [{apnic,clang} ...]]
                        IPv4 lists to use when subtracting China based IP,
                        multiple lists can be used at the same time (default:apnic clang)
  --ipv6-list [{apnic,clang} [{apnic,clang} ...]]
                        IPv6 lists to use when subtracting China based IP,
                        multiple lists can be used at the same time (default:apnic clang)
```

To specify China IPv4 list to use, use the --ipv4-list or/and --ipv6-list as the following:

* `python3 produce.py --ipv4-list clang` - only use list [from ispip.clang.cn](https://ispip.clang.cn/all_cn.txt)
* `python3 produce.py --ipv4-list apnic` - only use list [from APNIC](https://ftp.apnic.net/stats/apnic/delegated-apnic-latest)
* `python3 produce.py --ipv4-list apnic clang` - use both lists **(default)**
* `python3 produce.py --ipv6-list clang` - only use list [from ispip.clang.cn](https://ispip.clang.cn/all_cn_ipv6.txt)
* `python3 produce.py --ipv6-list apnic` - only use list [from APNIC](https://ftp.apnic.net/stats/apnic/delegated-apnic-latest)
* `python3 produce.py --ipv6-list apnic clang` - use both lists **(default)**


If you want to run this automatically, you can first edit `Makefile` and uncomment the BIRD reload code
at the end, then:

```
sudo crontab -e
```

and add `0 0 * * 0 make -C /path/to/nchnroutes` to the file.

This will re generate the table every Sunday at midnight and reload BIRD afterwards.

