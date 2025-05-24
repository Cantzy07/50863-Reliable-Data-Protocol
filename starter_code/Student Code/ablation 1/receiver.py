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
			result_queue.put(data)

def get_packet_info(data):
	global eof

	if data == b'EOF':
		eof = True
		print("eof received")
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
	window_size = min(50, (link_bandwidth * propagation_delay * 2) // max_packet_size)
	# the amount of time it takes for a round trip for all packets assuming ack and data have max transmission time
	max_time_to_wait = window_size // 6 * (propagation_delay * 2 + transmission_delay * 2)

	with open(write_location, "wb", buffering=0) as file:
		packet_dict = {}
		packets_received = set()
		packets_written = set()
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

				# if EOF already received and packet already received and written just ack it
				if (packet_num in packets_written and eof):
					# Remove selective ack only ack if in order
					# Send an ack for the packet received
					ack = "FINISHED"
					encoded_ack = ack.encode('utf-8')
					recv_monitor.send(sender_id, encoded_ack)
				
				else:

					if counter == packet_num:
						file.write(message)
						file.flush()
						packets_written.add(counter)

						# Remove selective ack only ack if in order
						# Send an ack for the packet received
						ack = "ACK " + str(counter)
						encoded_ack = ack.encode('utf-8')
						recv_monitor.send(sender_id, encoded_ack)

						counter += 1
					else:
						if (packet_num != -1 and packet_num not in packets_received):
							packet_dict[packet_num] = message
					
					packets_received.add(packet_num)

					while counter in packet_dict:
						file.write(packet_dict[counter])
						file.flush()
						packets_written.add(counter)
						packet_dict.pop(counter)

						# Remove selective ack only ack if in order
						# Send an ack for the packet received
						ack = "ACK " + str(counter)
						encoded_ack = ack.encode('utf-8')
						recv_monitor.send(sender_id, encoded_ack)

						counter += 1
				
			except queue.Empty:
				if (file_transfer_started and eof):
					while counter in packet_dict:
						written = True
						file.write(packet_dict[counter])
						file.flush()
						packets_written.add(counter)
						packet_dict.pop(counter)

						# Remove selective ack only ack if in order
						# Send an ack for the packet received
						ack = "ACK " + str(counter)
						encoded_ack = ack.encode('utf-8')
						recv_monitor.send(sender_id, encoded_ack)

						counter += 1
					else:
						timeout_reached = True
						break
				else:
					continue
	print("end program")
	recv_monitor.recv_end(write_location, sender_id)
