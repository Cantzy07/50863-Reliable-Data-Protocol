#!/usr/bin/env python3
from monitor import Monitor
import sys
import threading
from queue import Queue
import queue

# Config File
import configparser

def listen_for_ack(send_monitor, max_packet_size, result_queue):
	global last_ack_received
	global eof
	
	while not last_ack_received or eof:
		receiver, ack_data = send_monitor.recv(max_packet_size)
		if ack_data:
			result_queue.put(ack_data)

if __name__ == '__main__':
	print("Sender starting up!")
	config_path = sys.argv[1]

	global last_ack_received
	last_ack_received = False

	global eof
	eof = False

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
	transmission_delay = max_packet_size / int(cfg.get('network', 'LINK_BANDWIDTH'))
	# twice the amount of time it takes for a round trip assuming ack and data have max transmission time
	max_time_to_wait = 2 * (propagation_delay * 2 + transmission_delay * 2)
	
	with open(file_to_send, "rb") as file:
		result_queue = Queue()
		threading.Thread(target=listen_for_ack, args=(send_monitor, max_packet_size, result_queue), daemon=True).start()
		while not last_ack_received or not eof:
			data = file.read(max_payload_size)
			# if end of file reached then send an end of file message to receiver and end NE
			if not data:
				end_of_file = "EOF"
				data = end_of_file.encode('utf-8')
				eof = True
			ack = ""
			while ack != "ACK":
				while True:
					send_monitor.send(receiver_id, data)
					try:
						ack_data = result_queue.get(timeout=max_time_to_wait)
						# if acknowledgement is sent then break out to end loop
						if ack_data:
							ack = ack_data.decode("utf-8")

							if (eof):
								last_ack_received = True
								
							break
					except queue.Empty:
						break
				
	send_monitor.send_end(receiver_id)
	print("program end")
