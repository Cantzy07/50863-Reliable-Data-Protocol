#!/usr/bin/env python3
from monitor import Monitor
import sys
import threading
import queue
from queue import Queue

# Config File
import configparser

def listen_for_data(recv_monitor, max_packet_size, result_queue):
	global timeout_reached
	global eof 

	while not timeout_reached or not eof:
		receiver, data = recv_monitor.recv(max_packet_size)
		if data:
			print(data)
			result_queue.put(data)

if __name__ == '__main__':
	print("Receiver starting up!")
	config_path = sys.argv[1]

	global timeout_reached
	timeout_reached = False

	global eof
	eof = False

	# Initialize sender monitor
	recv_monitor = Monitor(config_path, 'receiver')
	
	# Parse config file
	cfg = configparser.RawConfigParser(allow_no_value=True)
	cfg.read(config_path)
	sender_id = int(cfg.get('sender', 'id'))
	write_location = cfg.get('receiver', 'write_location')
	max_packet_size = int(cfg.get('network', 'MAX_PACKET_SIZE'))
	propagation_delay = float(cfg.get('network', 'PROP_DELAY'))
	transmission_delay = max_packet_size / int(cfg.get('network', 'LINK_BANDWIDTH'))
	# twice the amount of time it takes for a round trip assuming ack and data have max transmission time
	max_time_to_wait = 2 * (propagation_delay * 2 + transmission_delay * 2)

	with open(write_location, "wb") as file:
		# variable so that the same packet isn't written to the file twice
		old_data = ""
		result_queue = Queue()
		# Receive data from sender and write to file
		threading.Thread(target=listen_for_data, args=(recv_monitor, max_packet_size, result_queue), daemon=True).start()
		while True:
			try:
				decoded_data = result_queue.get(timeout=max_time_to_wait)

				if decoded_data == b'EOF':
					eof = True
				elif old_data != decoded_data:
					print(decoded_data)
					file.write(decoded_data)
					file.flush()
					old_data = decoded_data

				# Send an ack for the packet received
				ack = "ACK"
				encoded_ack = ack.encode('utf-8')
				recv_monitor.send(sender_id, encoded_ack)
			except queue.Empty:
				if (eof):
					timeout_reached = True
					print("timeout")
					break
				else:
					print("queue empty")
					continue

	print("end program")
	recv_monitor.recv_end(write_location, sender_id)
			