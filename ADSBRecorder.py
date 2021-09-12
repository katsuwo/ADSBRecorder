import yaml
import signal
import subprocess
import re
import socket
import time
import threading
import PacketRingBuffer
import sqlite3
import datetime
import select

CONFIGFILE = './config.yaml'
DUMP1090 = "/home/katsuwo/work/dump1090/dump1090"
RTLAIS = "rtl_ais"
DUMP1090HOST = "127.0.0.1"
OUTPORT = 30002
OUTPUTDIR = "./database/"

class ADSBRecorder:

	def __init__(self):
		signal.signal(signal.SIGINT, self.signal_handler)

		# kill all Dump1090 process
		self.kill_process("dump1090")
		self.start_time = time.time()
		self.connection, self.cursor = self.make_db()
		self.row_counter = 0
		self.client_socket = None
		self.output_buffer = PacketRingBuffer.PacketRingBuffer(maxsize=100)
		self.config = self.read_configuration_file(CONFIGFILE)
		self.dump1090_process, self.raw_data_in_ports = self.startup_dump1090(self.config)
		self.rtlais_process, self.raw_data_in_ports = self.startup_rtlais(self.config, self.raw_data_in_ports)
		self.read_and_exec(self.raw_data_in_ports, self.connection, self.cursor)

	def read_configuration_file(self, file_name):
		with open(file_name, 'r') as yml:
			config = yaml.safe_load(yml)
		return config

	def startup_dump1090(self, config):
		processes = []
		out_ports = []
		print("Startup dump1090")
		for rc in config["Recievers"]["ADSB"]:
			dp1090 = rc["Dump1090"]
			device_index = str(dp1090["DeviceIndex"])
			gain = str(dp1090["Gain"])
			opt = dp1090["OtherOption"]
			raw_out_port = str(dp1090["RawOutPort"])
			dummy_port1 = str(dp1090["dummyPort1"])
			dummy_port2 = str(dp1090["dummyPort2"])
			dummy_port3 = str(dp1090["dummyPort3"])
			dummy_port4 = str(dp1090["dummyPort4"])

			exec_cmd = f"{DUMP1090} --device {device_index} --gain {gain}  --net-ro-port {raw_out_port} --net-bo-port {dummy_port1} --net-sbs-port {dummy_port2} --net-ri-port {dummy_port3}"
			exec_cmd = f"{exec_cmd} --net-bi-port {dummy_port4} {opt}"
			p = subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
			processes.append(p)
			out_ports.append(dp1090["RawOutPort"])
			print(exec_cmd)
		print("Done.")
		return processes, out_ports

	def startup_rtlais(self, config, out_ports):
		processes = []
		print("Startup rtl_ais")
		for rc in config["Recievers"]["AIS"]:
			rtlais = rc["RtlAIS"]
			device_index = str(rtlais["DeviceIndex"])
			opt = rtlais["OtherOption"]
			raw_out_port = str(rtlais["RawOutPort"])
			gain = str(rtlais["Gain"])
			exec_cmd = f"{RTLAIS} -d {device_index} -g {gain} -P {raw_out_port} {opt}"
			p = subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
			processes.append(p)
			out_ports.append(rtlais["RawOutPort"])
			print(exec_cmd)
		return processes, out_ports

	def read_and_exec(self, ports, connection, cursor):
		server_thread = self.start_server()

		descriptors = []
		for port in ports:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

			time.sleep(1)
			print(f"Connect to {port}")
			sock.connect((DUMP1090HOST, port))
			descriptors.append(sock)

		while True:
			r ,_ ,_ = select.select(descriptors, [], [])
			for sc in r:
				dat = sc.recv(4096)
				if self.output_buffer.check_is_duplicate(dat) is False:
					self.output_buffer.append(dat)
					elapsed_time = time.time() - self.start_time
					print(f"time{elapsed_time} : {dat}")
					self.write_db(connection=connection, cursor=cursor, elapsed=elapsed_time, body=dat)
				else:
					print("SKIP")

	# create dbfile and tables
	def make_db(self):
		conn = sqlite3.connect(f"{OUTPUTDIR}{self.get_datetime_string()}.db")
		c = conn.cursor()
		c.execute('CREATE TABLE IF NOT EXISTS data(id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, body STRING)')
		conn.commit()
		return conn, c

	# write data to sqlite
	def write_db(self, connection, cursor, elapsed, body):
		sql = f'INSERT INTO data(time, body) VALUES({elapsed}, "{body}")'
		cursor.execute(sql)
		if self.row_counter == 100:
			connection.commit()
			self.row_counter = 0
			print("commit.")
		else:
			self.row_counter += 1

	def get_datetime_string(self):
		now = datetime.datetime.now()
		return now.strftime("%Y%m%d_%H%M%S")

	# kill process
	def kill_process(self, process_string):
		cmdline = f"ps aux | grep {process_string}"
		print(f"kill {process_string} process.")
		old_procs = []
		subp = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

		while True:
			line = subp.stdout.readline().decode('utf-8')
			if process_string in line and "/bin/sh -c ps aux" not in line and "grep" not in line:
				print(line)
				p = re.sub(r'^[a-zA-Z0-9]+\s+', '', line).split(" ")[0]
				old_procs.append(p)
			if not line and subp.poll() is not None:
				break

		if len(old_procs) == 0:
			print("not found.")
		for p in old_procs:
			ret = subprocess.run(["kill", '-9', p])
			if ret == 0:
				print(f"PID:{p} was killed.")
			else:
				print(f"Failed kill PID:{p}")
		print("-------------------------")

	def start_server(self):
		t = threading.Thread(target=self.server)
		t.start()
		return t

	def server(self):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
			try:
				sock.bind((DUMP1090HOST, OUTPORT))
				sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				sock.listen(3)
			except Exception:
				print("Exception raised. exit.")
				exit(-1)

			while True:
				self.client_socket, address = sock.accept()
				print(f"Connect {address}")
				with self.client_socket:
					while True:
						if self.output_buffer.write_position is not self.output_buffer.read_position:
							dat = self.output_buffer.get()
							self.client_socket.send(dat)
						else:
							time.sleep(0.1)

	def signal_handler(self, signo, _):
		self.connection.commit()
		self.connection.close()
		exit(0)

if __name__ == '__main__':
	ADSBRecorder()
