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
        if args.arg1 is None:
            print("no specified database file.")
            exit(-1)

        if not os.path.exists(args.arg1):
            print(f"file:{args.dbfile} is not exists.")
            exit(-1)

        self.dbfile = args.arg1
        if args.start is not None:
            self.start = int(args.start)
        if args.duration is not None:
            self.duration = int(args.duration)

        self.loop = args.loop

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((DUMP1090HOST, OUTPORT))
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.listen(3)
                client_socket, address = sock.accept()
                self.read_exec(client_socket)
                self.read_exec(3)
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

        while True:
            start_time = time.time()
            start_id, end_id = self.get_start_and_end_frame(c, self.start, self.duration)
            if end_id == -1:
                end_id = total_rows

            while start_id < end_id:
                select_start = start_id
                select_end = end_id if select_start + 1000 else select_start + 1000

                sql = f"SELECT * FROM data WHERE id BETWEEN {select_start} AND {select_end}"
                c.execute(sql)
                rows = c.fetchall()
                for row in rows:
                    elapsed = (time.time() - start_time) + self.start
                    while elapsed < row[1]:
                        elapsed = (time.time() - start_time) + self.start
                    dat = row[2].replace("b'", "")
                    dat = dat.replace("\\n", "")
                    dat = dat.replace("'", "")
                    sock.send(dat.encode())
                    print(f"{row[0]} : {row[1]}")
                    start_id += 1
            if not self.loop:
                break
        conn.close()

    def get_start_and_end_frame(self, cursor, start_time, duration):
        start_id = 0
        end_id = -1

        # search start frame
        if start_time is not -1:
            sql = f"SELECT * FROM data WHERE time >= {start_time}"
            cursor.execute(sql)
            row = cursor.fetchone()
            if row is not None:
                start_id = row[0]

        if duration is not -1:
            end_time = start_time + duration
            sql = f"SELECT * FROM data WHERE time >= {start_time + duration}"
            cursor.execute(sql)
            row = cursor.fetchone()
            if row is not None:
                end_id = row[0]
        return start_id, end_id

    def parse_argument(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('arg1', help='read filename')
        parser.add_argument('-s', '--start')
        parser.add_argument('-d', '--duration')
        parser.add_argument('-l', '--loop',action='store_true')

        args = parser.parse_args()
        return args

if __name__ == '__main__':
    ADSBPlayer()

