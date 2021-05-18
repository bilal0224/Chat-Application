'''
This module defines the behaviour of a client in your Chat Application
'''
import sys
import getopt
import socket
import random
from threading import Thread
import os
import queue
import util
import time

'''
My code is able to send all the messages to server and made chunks for large message and files and send it to the server
'''

class Client:
    '''
    This is the main Client Class. 
    '''
    def __init__(self, username, dest, port, window_size):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None)
        self.sock.bind(('', random.randint(10000, 40000)))
        self.name = username
        self.window = window_size
        self.q = queue.Queue(0)
        self.seq_num = random.randrange(1, 10000, 1)
        self.addr_tuple = (self.server_addr, self.server_port)

    def start(self):
        self.join_message_sender()
        
        while True:
            user_input = ""
            user_input = input()
            msg_type = user_input.split(" ", 1)
            # sending start again and then waiting for start ack
            packet = util.make_packet("start", self.seq_num, "")
            self.sock.sendto(packet.encode(), self.addr_tuple)
            while True:
                self.q.get()
                break
            
            if util.validate_user_input(user_input):
                if user_input == "list":
                    msg_type = util.input_to_std_msg_type(user_input)
                    msg_format = util.msg_type_to_msg_format(msg_type)
                    message = util.make_message(msg_type, msg_format, "")
                    # getting msg format and msg type and sending data to server
                    packet = util.make_packet("data", self.seq_num, message)
                    self.sock.sendto(str.encode(packet), self.addr_tuple)
                    
                elif user_input == "quit":
                    msg_type = util.input_to_std_msg_type(user_input)
                    msg_format = util.msg_type_to_msg_format(msg_type)
                    message = util.make_message(msg_type, msg_format, self.name)
                    packet = util.make_packet("data", self.seq_num, message)
                    self.sock.sendto(packet.encode(), self.addr_tuple)
                    print("quitting")
                    # sending ack messages instantaneiusly
                    # and waiting for acknowledgment
                    packet = util.make_packet("end", self.seq_num, "")
                    self.sock.sendto(packet.encode(), self.addr_tuple)
                    while True:
                        self.q.get()
                        break
                    sys.exit()
                    
                elif msg_type[0] == "msg":
                    users_msg = msg_type[1]
                    msg_type = util.input_to_std_msg_type(msg_type[0])
                    msg_format = util.msg_type_to_msg_format(msg_type)
                    message = util.make_message(msg_type, msg_format, users_msg)
                    exp_seq_num = self.seq_num
                    # when message size is less than chunck size
                    # send whole message in one go
                    if len(message) <= util.CHUNK_SIZE:
                        packet = util.make_packet("data", self.seq_num, message)
                        self.sock.sendto(packet.encode(), self.addr_tuple)
                    # when message size is greater than chunck size
                    # send whole message in chuncks
                    else: 
                        message_list = util.split_string(message)
                        for i in range(len(message_list)):
                            thre = Thread(target=self.thread(exp_seq_num, message_list[i]))
                            thre.daemon = True
                            thre.start()
                        
                elif msg_type[0] == "file":
                    file_content = user_input.rsplit(" ", 1)
                    file_name = file_content[1]
                    file_read = open(file_name, "r")
                    file_read = file_read.read()  # reading file contents
                    msg = file_content[0] + " " + file_name + " " + file_read
                    msg = msg.split(" ", 1)
                    msg = msg[1]  # number of clients + clients names + file content
                    
                    # getting message type and format and sending message to server 
                    msg_type = util.input_to_std_msg_type(msg_type[0])
                    msg_format = util.msg_type_to_msg_format(msg_type)
                    message = util.make_message(msg_type, msg_format, msg)
                    exp_seq_num = self.seq_num
                    # same as above explanation
                    if len(message) <= util.CHUNK_SIZE:
                        packet = util.make_packet("data", self.seq_num, message)
                        self.sock.sendto(packet.encode(), self.addr_tuple)
                    else:
                        message_list = util.split_string(message)
                        for i in range(len(message_list)):
                            thre = Thread(target=self.thread(exp_seq_num, message_list[i]))
                            thre.daemon = True
                            thre.start()
                            exp_seq_num = exp_seq_num + 1
            else:
                print("incorrect userinput format")
            # sending ack message
            packet = util.make_packet("end", self.seq_num, "")
            self.sock.sendto(packet.encode(), self.addr_tuple)
            while True:
                self.q.get()
                break

    ################################################################################################        
    def receive_handler(self):
        while True:
            msg, addr = self.sock.recvfrom(100000)
            msg = msg.decode("utf-8")
            msg_type, exp_seq_num, message, _ = util.parse_packet(msg)
            exp_seq_num = int(exp_seq_num)
            msg = message.split(" ", 2)
            # receiving start or end message from server and sending
            # it acknowledge message
            if msg_type == "start" or msg_type == "end":
                packet = util.make_packet("ack", exp_seq_num+1, "")
                self.sock.sendto(packet.encode(), self.addr_tuple)
            # waiting for ack message and putting it in queue
            elif msg_type == "ack":
                self.q.put(msg_type)
            
            elif msg[0] == "err_server_full" and msg_type == "data":
                packet = util.make_packet("ack", exp_seq_num + 1, "")
                self.sock.sendto(packet.encode(), self.addr_tuple)
                print("disconnect: server full")
                sys.exit()
            
            elif msg[0] == "err_username_unavailable" and msg_type == "data":
                packet = util.make_packet("ack", exp_seq_num, "")
                self.sock.sendto(packet.encode(), self.addr_tuple)
                print("disconnect: username unavailable")
                sys.exit()

            elif msg[0] == "request_users_list" and msg_type == "data":
                msg = msg[2].split(" ", 1)
                names = msg[1].split(" ")
                names.sort()
                li = ""
                check = 1
                for n in names:
                    if check == 1:
                        li = n
                        check = check + 1 # to avoid space for first time
                    else:
                        li = li + " " + n
                li = "list: " + li
                packet = util.make_packet("ack", exp_seq_num + 1, "")
                self.sock.sendto(packet.encode(), self.addr_tuple)
                print(li)

            elif msg[0] == "forward_message":
                dic = {}
                dic[exp_seq_num] = message
                while msg_type != "end":
                    msg, addr = self.sock.recvfrom(100000)
                    msg = msg.decode("utf-8")
                    msg_type, new_exp_seq_num, msg_chunk, _ = util.parse_packet(msg)
                    new_exp_seq_num = int(new_exp_seq_num)
                    packet = util.make_packet("ack", exp_seq_num+1, "")
                    self.sock.sendto(packet.encode(), self.addr_tuple)
                    
                    if new_exp_seq_num not in dic.keys():
                        dic[new_exp_seq_num] = msg_chunk
                concat_msg = ""
                for key in sorted(dic.keys()):
                    concat_msg = concat_msg + dic[key]         

                msg = concat_msg.split(" ", 2)
                msg = msg[2].split(" ", 2)
                sender_username = msg[1]
                msg_rcv = msg[2]
                s = "msg: " + sender_username + ": " + msg_rcv
                print(s)
            
            elif msg[0] == "forward_file":
                dic = {}
                dic[exp_seq_num] = message
                while msg_type != "end":
                    msg, addr = self.sock.recvfrom(100000)
                    msg = msg.decode("utf-8")
                    msg_type, new_exp_seq_num, msg_chunck, _ = util.parse_packet(msg)
                    
                    new_exp_seq_num = int(new_exp_seq_num)
                    packet = util.make_packet("ack", exp_seq_num+1, "")
                    self.sock.sendto(packet.encode(), self.addr_tuple)
                    
                    if new_exp_seq_num not in dic.keys():
                        dic[new_exp_seq_num] = msg_chunck
                concat_msg = ""
                for key in sorted(dic.keys()):
                    concat_msg = concat_msg + dic[key]
                    
                msg = concat_msg.split(" ", 5)
                filename = msg[4]
                filename = self.name + "_" + filename  # modified name with client username as prefix
                file_content = msg[5]
                file_write = open(filename, "w")
                file_write.write(file_content)
                file_write.close()
                s = "file: " + msg[3] + ": " + msg[4]
                print(s)
                
            elif msg[0] == "err_unknown_message":
                print("disconnected: server received an unknown command")
                packet = util.make_packet("ack", exp_seq_num+1, "")
                self.sock.sendto(packet.encode(), self.addr_tuple)
                sys.exit()

		#########################################################################################

	# func for sending packets of message chunks in diff threads and waiting for their acks in their own threads
    def thread(self, seq_no, msg_chunck):
        packet = util.make_packet("data", seq_no, msg_chunck)
        self.sock.sendto(packet.encode(), self.addr_tuple)
        while True:
            self.q.get()
            break
        
        #########################################################################################

    def join_message_sender(self):
        message = ""
        packet = util.make_packet("start", self.seq_num, message)
        self.sock.sendto(packet.encode(), self.addr_tuple)
        # waiting for ack message
        while True:
            self.q.get()  # wait until ack message shows up in queue (in receive handler)
            break
        # sending join data message
        message = util.make_message("join", 1, self.name)
        packet = util.make_packet("data", self.seq_num, message)
        self.sock.sendto(packet.encode(),self.addr_tuple)
        while True:
            self.q.get()
            break
        # sending end for join message
        packet = util.make_packet("end", self.seq_num, "")
        self.sock.sendto(packet.encode(),self.addr_tuple)
        while True:
            self.q.get()
            break

# Do not change this part of code
if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our Client module completion
        '''
        print("Client")
        print("-u username | --user=username The username of Client")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW_SIZE | --window=WINDOW_SIZE The window_size, defaults to 3")
        print("-h | --help Print this help")
    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "u:p:a:w", ["user=", "port=", "address=","window="])
    except getopt.error:
        helper()
        exit(1)

    PORT = 15000
    DEST = "localhost"
    USER_NAME = None
    WINDOW_SIZE = 3
    for o, a in OPTS:
        if o in ("-u", "--user="):
            USER_NAME = a
        elif o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW_SIZE = a

    if USER_NAME is None:
        print("Missing Username.")
        helper()
        exit(1)

    S = Client(USER_NAME, DEST, PORT, WINDOW_SIZE)
    try:
        # Start receiving Messages
        T = Thread(target=S.receive_handler)
        T.daemon = True
        T.start()
        # Start Client
        S.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
