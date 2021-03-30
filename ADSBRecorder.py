import yaml
import os
import subprocess
import re
import socket
import time
import threading
import PacketRingBuffer

CONFIGFILE = './config.yaml'
DUMP1090 = "/home/katsuwo/work/dump1090/dump1090"
DUMP1090HOST = "127.0.0.1"

class ADSBRecorder:

	def __init__(self):

		# kill all Dump1090 process
		self.kill_process("dump1090")

		self.config = self.read_configuration_file(CONFIGFILE)
		self.dump1090_process, self.raw_data_in_ports = self.startup_dump1090(self.config)
		self.read_and_exec(self.raw_data_in_ports)

	def read_configuration_file(self, file_name):
		with open(file_name, 'r') as yml:
			config = yaml.safe_load(yml)
		return config

	def startup_dump1090(self, config):
		processes = []
		out_ports = []
		print("Startup dump1090")
		for rc in config["Recievers"]:
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
			p = subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			processes.append(p)
			out_ports.append(dp1090["RawOutPort"])
			print(exec_cmd)
		print("Done.")
		return processes, out_ports

	def read_and_exec(self, ports):
		threads = []
		thread_num = 0
		ring_buffers = []
		for port in ports:
			rb = PacketRingBuffer.PacketRingBuffer(maxsize=100)
			t = threading.Thread(target=self.socket_worker, args=(thread_num, port, rb))
			t.start()
			threads.append(t)
			ring_buffers.append(rb)
			print(f"Thread {thread_num} start")
			thread_num += 1

		output_buffer = PacketRingBuffer.PacketRingBuffer(maxsize=100)
		while True:
			thread_num = 0
			for buffer in ring_buffers:
				if buffer.read_position is not buffer.write_position:
					num = buffer.read_position
					dat = buffer.get()
					if output_buffer.check_is_duplicate(dat) is False:
						output_buffer.append(dat)
						print(f"{thread_num}: {num} : {dat}")
				thread_num += 1


	def socket_worker(self, worker_number, port, buffer):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		time.sleep(1)
		print(f"Connect to {port}")
		sock.connect((DUMP1090HOST, port))

		while True:
			dat = sock.recv(1024)
			packet = dat.split()
			for p in packet:
				buffer.append(p)

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


if __name__ == '__main__':
	ADSBRecorder()
