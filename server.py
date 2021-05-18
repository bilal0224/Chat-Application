'''
Server receives start join and end and sends back their acks and also receives also the message chunks in whole
'''
import sys
import getopt
import socket
import util
import os
from threading import Thread
import queue
import random

addr_dic = {}
seq_num_dic = {}

class Server:
	def __init__(self, dest, port, window):
		self.server_addr = dest
		self.server_port = port
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.settimeout(None)
		self.sock.bind((self.server_addr, self.server_port))
		self.window = window
		self.q = queue.Queue(0)
		self.seq_no = random.randrange(1, 10000, 1)
  
#################################################################################################################
	
	def thread(self, message_decode, addr):
		mssg, seq_num, message, _ = util.parse_packet(message_decode)
		msg_type = message.split(" ", 1)
		if mssg == "ack":
			self.q.put(mssg)
			
		if mssg == "data":
			if msg_type[0] == "join":
				username = message.rsplit(" ", 1)
				username = username[1]
				if username not in addr_dic.keys() and len(addr_dic) <= util.MAX_NUM_CLIENTS:
					addr_dic[f"{username}"] = addr
					print(f"join: {username}")

				elif len(addr_dic) > util.MAX_NUM_CLIENTS:
					packet = util.make_packet("start", self.seq_no, "")
					self.sock.sendto(packet.encode(), addr)
					self.seq_no = self.seq_no + 1

					send_msg = "disconnected: server full"
					send_msg = util.make_message("err_server_full", 2, send_msg)
					packet = util.make_packet("data", self.seq_no, send_msg)
					self.sock.sendto(packet.encode(), addr)
					self.seq_no = self.seq_no + 1

					packet = util.make_packet("end", self.seq_no, "")
					self.sock.sendto(packet.encode(),addr)
					self.seq_no = self.seq_no + 1
					
				elif username in addr_dic.keys():
					packet = util.make_packet("start", self.seq_no, "")
					self.sock.sendto(packet.encode(), addr)
					self.seq_no = self.seq_no + 1

					send_msg = "disconnected: username unavailable"
					send_msg = util.make_message("err_username_unavailable", 2, send_msg)
					packet = util.make_packet("data", self.seq_no, send_msg)
					self.sock.sendto(packet.encode(), addr)  
					self.seq_no = self.seq_no + 1

					packet = util.make_packet("end", self.seq_no, "")
					self.sock.sendto(packet.encode(), addr)
					self.seq_no = self.seq_no + 1 
     
			elif msg_type[0] == "disconnect":
				message = message.rsplit(" ", 1)
				sender_username = message[1]
				del addr_dic[sender_username]
				print(f"disconnected: {sender_username}")

			elif msg_type[0] == "request_users_list":
				username = message.rsplit(" ", 1)
				username = username[1]
				for k, val in addr_dic.items():
					if str(val) == str(addr):
						username = k
						break
				print(f"request_users_list: {username}")
				li = ""
				c = 0
				for k, val in addr_dic.items():
					c = c + 1
					li = li + " " + k
				li = str(c) + li

				packet = util.make_packet("start", self.seq_no, "")
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1    

				message = util.make_message(msg_type[0], 3, li)
				packet = util.make_packet("data", self.seq_no, message)
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1

				packet = util.make_packet("end", self.seq_no, "")
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1

			else:
				packet = util.make_packet("start", self.seq_no, "")
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1

				message = util.make_message("err_unknown_message",2 ,message)
				packet = util.make_packet("data", self.seq_no, message)
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1

				packet = util.make_packet("end", self.seq_no, "")
				self.sock.sendto(packet.encode(),addr)
				self.seq_no = self.seq_no + 1

				sender_username = ""
				for k,val in addr_dic.items():
					if str(val) == str(addr):
						sender_username = k
						break
				del addr_dic[sender_username]
				print(f"disconnected: {sender_username} sent unknown command")
		
		packet = util.make_packet("ack", int(seq_num) + 1, "")
		self.sock.sendto(packet.encode(),addr)
 
 ###########################################################################################################
	#start thread
	def start(self):
		ch = True
		msg_type_checker = 0
		while True:
			msg, addr = self.sock.recvfrom(100000)
			message_decode = msg.decode()
			mssg, seq_num, message, _ = util.parse_packet(message_decode)
			msg_list = message.split(" ",1)
							
			if msg_list[0] in ['request_users_list', 'join', 'disconnect'] or (mssg in ["start", "ack"]) or (mssg == "end" and ch):
				T = Thread(target=self.thread(message_decode, addr))
				T.daemon = True
				T.start()

			else:
				# else it waits for all message chunks and send it to the dictionary
				ch = False
				if mssg == "data":
					if message.split(" ", 1)[0] == "send_message":
						msg_type_checker = 1
					elif message.split(" ", 1)[0] == "send_file":
						msg_type_checker = 2
					seq_num_dic[seq_num] = message
					packet = util.make_packet("ack", int(seq_num) + 1, "")
					self.sock.sendto(packet.encode(),addr)
     
				if mssg == 'end' and ch == False:
					ch = True
					sorted(seq_num_dic.keys())
					message = ""
					for key in sorted(seq_num_dic.keys()):
						message = message + seq_num_dic[key]
					if msg_type_checker == 1:
						packet = util.make_packet("ack", self.seq_no, "")
						self.sock.sendto(packet.encode(), addr)
						T = Thread(target=self.message_handler(message, addr))
						T.daemon = True
						T.start()
						msg_type_checker = 0
					elif msg_type_checker == 2:
						packet = util.make_packet("ack", self.seq_no, "")
						self.sock.sendto(packet.encode(), addr)
						T = Thread(target=self.file_handler(message, addr))
						T.daemon = True
						T.start()
						msg_type_checker = 0

  ##########################################################################################################
	def file_handler(self, message, addr):
		username = message.rsplit(" ",1)
		username = username[1]
		for k,val in addr_dic.items():
			if str(val) == str(addr):
				sender_username = k
				break
		print(f"file: {sender_username}")
		actual_msg = message.split(" ",2) 
		actual_msg = actual_msg[2] # number of clients + client names + filename and file content
		number_of_clients = actual_msg.split(" ",1) 
		number_of_clients_int = int(float(number_of_clients[0])) #number of clients in integer
		client_file_content = number_of_clients[1]
		split_client_file_content = client_file_content.split(" ",number_of_clients_int) #client names separated with file content separated
		file_content = split_client_file_content[number_of_clients_int] # only file content
		file_content =  number_of_clients[0] + " " + sender_username + " " + file_content

		message = util.make_message("forward_file", 4, file_content)
		for name in split_client_file_content[0:number_of_clients_int]:
			check = 0
			for k,val in addr_dic.items():
				if name == k:
					packet = util.make_packet("start", self.seq_no, "")
					self.sock.sendto(packet.encode(),val)
					exp_seq_no = self.seq_no
					if len(message) <= util.CHUNK_SIZE:
						packet = util.make_packet("data", self.seq_no, message)
						self.sock.sendto(packet.encode(),val)
					else:
						message_list = util.split_string(message)
						for i in range(len(message_list)):
							self.data_sender(exp_seq_no, message_list[i],val)
							exp_seq_no = exp_seq_no + 1
					packet = util.make_packet("end", self.seq_no, "")
					self.sock.sendto(packet.encode(),val)
					check = 1
					break
				else:
					check = 0
					
			if check == 0:
				print(f"file: {sender_username} to non-existent user {name}")
			else:
				continue
		seq_num_dic.clear()
		self.seq_no = exp_seq_no + 1
  
  #######################################################################################################
  
	def message_handler(self, message, addr):
		username = message.rsplit(" ",1)
		username = username[1]
		for k,val in addr_dic.items():
			if str(val) == str(addr):
				sender_username = k
				break
		print(f"msg: {sender_username}")
		actual_msg = message.split(" ",2)
		actual_msg = actual_msg[2]
		number_of_clients = actual_msg.split(" ",1)
		number_of_clients_int = int(float(number_of_clients[0]))
		client_msg = number_of_clients[1]
		split_client_msg = client_msg.split(" ",number_of_clients_int)
		msg = split_client_msg[number_of_clients_int]
		msg = number_of_clients[0] + " " + sender_username + " " + msg

		message = util.make_message("forward_message", 4, msg)
		for name in split_client_msg[0:number_of_clients_int]:
			check = 0
			for k,val in addr_dic.items():
				if name == k:
					packet = util.make_packet("start", self.seq_no, "")
					self.sock.sendto(packet.encode(),val)
					exp_seq_no = self.seq_no
					if len(message) <= util.CHUNK_SIZE:
						packet = util.make_packet("data", self.seq_no, message)
						self.sock.sendto(packet.encode(),val)
					else:
						message_list = util.split_string(message)
						for i in range(len(message_list)):
							self.data_sender(exp_seq_no, message_list[i],val)
							exp_seq_no = exp_seq_no + 1
					packet = util.make_packet("end", self.seq_no, "")
					self.sock.sendto(packet.encode(),val)
					check = 1
					break
				else:
					check = 0
     
			if check == 0:
				print(f"msg: {sender_username} to non-existent user {name}")
			else:
				continue
		seq_num_dic.clear()
		self.seq_no = exp_seq_no + 1
  
  #################################################################################################
  #func for sending packets of message chunks in diff threads and waiting for their acks in their own threads
	def data_sender(self, seqno, message_chunk, addr):
		packet = util.make_packet("data", seqno, message_chunk)
		self.sock.sendto(packet.encode(),addr)

  
# Do not change this part of code

if __name__ == "__main__":
	def helper():
		'''
		This function is just for the sake of our module completion
		'''
		print("Server")
		print("-p PORT | --port=PORT The server port, defaults to 15000")
		print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
		print("-w WINDOW | --window=WINDOW The window size, default is 3")
		print("-h | --help Print this help")

	try:
		OPTS, ARGS = getopt.getopt(sys.argv[1:],
									"p:a:w", ["port=", "address=","window="])
	except getopt.GetoptError:
		helper()
		exit()

	PORT = 15000
	DEST = "localhost"
	WINDOW = 3

	for o, a in OPTS:
		if o in ("-p", "--port="):
			PORT = int(a)
		elif o in ("-a", "--address="):
			DEST = a
		elif o in ("-w", "--window="):
			WINDOW = a

	SERVER = Server(DEST, PORT,WINDOW)
	try:
		T = Thread(target=SERVER.start())
		T.daemon = True
		T.start()
	except (KeyboardInterrupt, SystemExit):
		exit()
