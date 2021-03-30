class PacketRingBuffer:
	def __init__(self, maxsize=100):
		self.buffer = []
		self.write_position = 0
		self.read_position = 0
		self.max_buffer_size = maxsize

	def append(self, dat):
		if len(self.buffer) < self.max_buffer_size:
			self.buffer.append(dat)
		else:
			self.buffer[self.write_position] = dat

		self.write_position += 1
		if self.write_position == self.max_buffer_size:
			self.write_position = 0

	def get(self):
		ret = self.buffer[self.read_position]
		self.read_position += 1
		if self.read_position == self.max_buffer_size:
			self.read_position = 0
		return ret

	def check_is_duplicate(self, dat):
		for b in self.buffer:
			if b == dat:
				return True
		return False
