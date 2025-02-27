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
			print("Data\n", data)
			result_queue.put(data)

def get_packet_info(data):
	global eof

	if data == b'EOF':
		eof = True
		return (-1, data)
	else:
		packet_num, message = data.split(b" ", 1)
		return (int(packet_num.decode()), message)

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
	link_bandwidth = int(cfg.get('network', 'LINK_BANDWIDTH'))
	transmission_delay = max_packet_size / link_bandwidth
	window_size = min(50, (link_bandwidth * propagation_delay) // max_packet_size)
	# the amount of time it takes for a round trip for all packets assuming ack and data have max transmission time
	max_time_to_wait = 2 * (propagation_delay * 2 + transmission_delay * 2)

	with open(write_location, "wb", buffering=0) as file:
		packet_dict = {}
		packets_received = set()
		counter = 1
		file_transfer_started = False
		result_queue = Queue()
		# Receive data from sender and write to file
		threading.Thread(target=listen_for_data, args=(recv_monitor, max_packet_size, result_queue), daemon=True).start()
		while True:
			try:
				data = result_queue.get(timeout=max_time_to_wait)
				file_transfer_started = True
				packet_num, message = get_packet_info(data)
				print(packet_num)
				print(message)
				print("counter: ", counter)

				if counter == packet_num:
					print("writing to file")
					file.write(message)
					file.flush()
					counter += 1
				else:
					if (packet_num != -1 and packet_num not in packets_received):
						packet_dict[packet_num] = message
				
				packets_received.add(packet_num)

				while counter in packet_dict:
					print("writing to file")
					file.write(packet_dict[counter])
					file.flush()
					packet_dict.pop(counter)
					counter += 1

				if (packet_num != -1):
					# Send an ack for the packet received
					ack = "ACK " + str(packet_num)
					encoded_ack = ack.encode('utf-8')
					recv_monitor.send(sender_id, encoded_ack)
					print("ack sent for", packet_num)
				
			except queue.Empty:
				if (file_transfer_started and eof):
					if packet_dict:
						while counter in packet_dict:
							print("writing to file")
							file.write(packet_dict[counter])
							file.flush()
							packet_dict.pop(counter)
							counter += 1
					else:
						timeout_reached = True
						print("timeout")
						break
				else:
					continue
	print("end program")
	recv_monitor.recv_end(write_location, sender_id)
