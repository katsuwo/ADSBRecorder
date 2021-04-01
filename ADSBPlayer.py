import yaml
import signal
import subprocess
import os
import socket
import time
import threading
import PacketRingBuffer
import sqlite3
import datetime
import select
import argparse

CONFIGFILE = './config.yaml'
DUMP1090 = "/home/katsuwo/work/dump1090/dump1090"
DUMP1090HOST = "127.0.0.1"
OUTPORT = 30002

class ADSBPlayer:
    def __init__(self):
        args = self.parse_argument()
        self.start = -1
        self.duration = -1
        if args.dbfile is None:
            print("no specified database file.")
            exit(-1)

        if not os.path.exists(args.dbfile):
            print(f"file:{args.dbfile} is not exists.")
            exit(-1)

        self.dbfile = args.dbfile
        if args.start is not None:
            self.start = args.start
        if args.duration is not None:
            self.duration = args.duration

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((DUMP1090HOST, OUTPORT))
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.listen(3)
                client_socket, address = sock.accept()
                self.read_exec(client_socket)
            except Exception as e :
                print(e)
                exit(-1)


    def read_exec(self, sock):
        conn = sqlite3.connect(self.dbfile)
        print(f"open {self.dbfile}")
        c = conn.cursor()
        c.execute("SELECT COUNt(*) from data")
        total_rows = c.fetchall()[0][0]
        print(f"obtain {total_rows} records.")
        start_time = time.time()

        read_count = 0
        while read_count < total_rows:
            sql = f"SELECT * FROM data WHERE id BETWEEN {read_count} AND {read_count + 1000}"
            c.execute(sql)
            rows = c.fetchall()
            for row in rows:
                elapsed = time.time() - start_time
                while elapsed < row[1]:
                    elapsed = time.time() - start_time
                dat = row[2].replace("b'", "")
                dat = dat.replace("\\n", "")
                dat = dat.replace("'", "")
                sock.send(dat.encode())
                print(dat)
                read_count += 1


    def parse_argument(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('dbfile', help='read filenam')
        parser.add_argument('-s', '--start')
        parser.add_argument('-d', '--duration')
        args = parser.parse_args()
        return args

if __name__ == '__main__':
    ADSBPlayer()

