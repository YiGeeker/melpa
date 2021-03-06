#!/usr/bin/env python


import argparse
from datetime import datetime
import gzip
import json
import os
import re
import sys
import time
import tempfile
import sqlite3
from operator import or_

LOGREGEX = r'^(?P<ip>[\d.]+) [ -]+ \[(?P<date>[\w/: +-]+)\] ' \
           r'"GET /+packages/+(?P<package>[^ ]+)-(?P<version>[0-9.]+).(?:el|tar) ' \
           r'HTTP/\d.\d" 200'


def json_handler(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    raise TypeError(
        'Object of type {0} with value {1} is not JSON serializable'.format(
            type(obj), repr(obj)))


def json_dump(data, jsonfile, indent=None):
    """
    jsonfiy `data`
    """
    return json.dump(data, jsonfile, default=json_handler, indent=indent, encoding='utf-8')


def datetime_parser(dct):
    for key, val in dct.items():
        if isinstance(val, list):
            dct[key] = set(val)
    return dct


def json_load(jsonfile):
    return json.load(jsonfile, object_hook=datetime_parser)


def parse_val(val):
    try:
        return datetime.strptime(val, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return val


def ip_to_number(ip):
    return reduce(or_, ((int(n) << (i*8)) for i, n in enumerate(
        reversed(ip.split('.')))), 0)


def parse_logfile(logfilename, curs):
    """
    """
    if logfilename.endswith("gz"):
        logfile = gzip.open(logfilename, 'r')
    else:
        logfile = open(logfilename, 'r')

    logre = re.compile(LOGREGEX)
    count = 0

    for line in logfile:
        match = logre.match(line)

        if match is None:
            continue

        # Convert ips to four character strings.
        ip = match.group('ip')
        pkg = match.group('package')

        curs.execute("INSERT OR IGNORE INTO pkg_ip VALUES (?, ?)", (pkg, ip))
        count += 1

    return count


def main():
    """main function"""

    parser = argparse.ArgumentParser(description='MELPA Log File Parser')
    parser.add_argument('--jsondir', help='JSON output directory (default: working directory)', default=".")
    parser.add_argument('--db', help='Database file (default: download_log.db)', default="download_log.db")
    parser.add_argument('logs', metavar="logs", type=unicode, nargs="+",
                        help="HTTP access log files to parse.")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    curs = conn.cursor()

    sys.stdout.write("ensuring database setup...\n")
    curs.execute(
        '''CREATE TABLE IF NOT EXISTS pkg_ip (package, ip, PRIMARY KEY (package, ip)) WITHOUT ROWID''')
    conn.commit()

    # parse each parameter
    for logfile in args.logs:
        sys.stdout.write("processing logfile {0}... ".format(logfile))
        sys.stdout.flush()

        count = parse_logfile(logfile, curs)
        sys.stdout.write("{0}\n".format(count))
        conn.commit()

    # calculate current package totals
    pkgcount = {p: c for p, c in curs.execute(
        "SELECT package, count(ip) FROM pkg_ip GROUP BY 1")}
    json_dump(pkgcount, open(args.jsondir + "/download_counts.json", 'w'), indent=1)

    return 0


if __name__ == '__main__':
    sys.exit(main())
