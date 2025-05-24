#!/usr/bin/env python3
from monitor import Monitor
import sys
import threading
from queue import Queue
import queue
import time

# Config File
import configparser

def read_file_into_queue(file, send_monitor, receiver_id, max_payload_size, packet_queue):
	global eof

	count = 1
	while not eof:
		while not packet_queue.full():
			data = file.read(max_payload_size - sys.getsizeof(str(count).encode('utf-8')))
			# if end of file reached then send an end of file message to receiver and end NE
			if not data:
				end_of_file = "EOF"
				data = end_of_file.encode('utf-8')
				send_monitor.send(receiver_id, data)
				eof = True
				break
			else: # if not end of file then attach the packet number in front of data and send
				data = str(count).encode('utf-8') + (" ").encode('utf-8') + data
				packet_queue.put((count, data))
				count += 1

# formatting for ACK is "ACK #"
def listen_for_ack(lock, send_monitor, max_packet_size, ack_buffer):
	global eof
	global all_queues_empty
	global force_quit

	while not all_queues_empty or not eof:
		receiver, ack_data = send_monitor.recv(max_packet_size)
		ack_data = ack_data.decode('utf-8')
		if "FINISHED" in ack_data:
			force_quit = True
			break
		ack_num = int(ack_data.split()[1])
		if "ACK" in ack_data:
			for i in range(len(ack_buffer)):
				if ack_buffer[i] is not None and ack_buffer[i][0] == ack_num:
					with lock:
						ack_buffer[i] = None
						break	

		
# tuple (packetNum, data, time)
def send_packets(lock, send_monitor, receiver_id, packet_queue, ack_buffer, ack_queue, max_time_to_wait):
	global eof
	global all_queues_empty
	while not packet_queue.empty() or not eof:
		try:
			buffer_index = ack_queue.get(timeout=max_time_to_wait)
			if (ack_buffer[buffer_index] is None):
				packet_num, data_to_send = packet_queue.get()
				send_monitor.send(receiver_id, data_to_send)
				with lock:
					ack_buffer[buffer_index] = (packet_num, data_to_send, time.time())

		except queue.Empty:
			continue

if __name__ == '__main__':
	print("Sender starting up!")
	config_path = sys.argv[1]

	MAX_HEADER_OVERHEAD = 30

	# Initialize sender monitor
	send_monitor = Monitor(config_path, 'sender')
	
	# Parse config file
	cfg = configparser.RawConfigParser(allow_no_value=True)
	cfg.read(config_path)
	receiver_id = int(cfg.get('receiver', 'id'))
	file_to_send = cfg.get('nodes', 'file_to_send')
	max_packet_size = int(cfg.get('network', 'MAX_PACKET_SIZE'))
	max_payload_size = max_packet_size - MAX_HEADER_OVERHEAD
	propagation_delay = float(cfg.get('network', 'PROP_DELAY'))
	link_bandwidth = int(cfg.get('network', 'LINK_BANDWIDTH'))
	transmission_delay = max_packet_size / link_bandwidth
	# window size, should be 19 for config1.ini
	window_size = int(min(50, (link_bandwidth * propagation_delay * 2) // max_packet_size))
	# the amount of time it takes for a round trip for all packets sent assuming ack and data have max transmission time
	max_time_to_wait = window_size // 6 * (propagation_delay * 2 + transmission_delay * 2)

	with open(file_to_send, "rb") as file:
		global eof
		eof = False

		global all_queues_empty
		all_queues_empty = False

		global force_quit
		force_quit = False

		packet_queue = Queue(maxsize=window_size)
		# tuple (packet data, time sent) holds the oldest packets (window_size amount)
		ack_buffer = [None for i in range(window_size)]
		# holds index in buffer for empty slots to put packet in after sending
		ack_queue = Queue()

		lock = threading.Lock()

		# continuously read file into the packet_queue
		threading.Thread(target=read_file_into_queue, args=(file, send_monitor, receiver_id, max_payload_size, packet_queue), daemon=True).start()
		# Sends packets continually
		threading.Thread(target=send_packets, args=(lock, send_monitor, receiver_id, packet_queue, ack_buffer, ack_queue, max_time_to_wait), daemon=True).start()
		# Listens for acknowledgements continually
		threading.Thread(target=listen_for_ack, args=(lock, send_monitor, max_packet_size, ack_buffer), daemon=True).start()

		# keep the loop until both packet and ack queues are empty ie. all packets sent and acknowledged
		while not all_queues_empty or not eof:
			if force_quit:
				break
			# fill any empty buffer slots with packets from ack_queue and check if one is timed out
			for i in range(window_size):
				# if packet has been acknowledged then take it out of the buffer
				with lock:
					# fill the resent packet's slot with a new packet from the queue
					if ack_buffer[i] is None:
						if not packet_queue.empty():
							ack_queue.put(i)
					else:
						# if packet has reached timeout time then assume it is dropped and resend
						if time.time() - ack_buffer[i][2] >= max_time_to_wait:
							send_monitor.send(receiver_id, ack_buffer[i][1])
							# reset time since sent
							ack_buffer[i] = (ack_buffer[i][0], ack_buffer[i][1], time.time())

			all_queues_empty = packet_queue.empty() and all(x is None for x in ack_buffer)

	print("program end")		
	send_monitor.send_end(receiver_id)
