import sys

def recv_arg_parser(argv):
    if len(argv) < 6:
      print ("Error: please use this format: python Receiver.py <filename> <listening_port> <sender_IP> <sender_port> <log_filename>")
      sys.exit(1)
    else:
      return {"filename" : argv[1], "recv_port": int(argv[2]), "send_ip"  : argv[3], "send_port": int(argv[4]), "log_name" : argv[5] }

def send_arg_parser(argv):
    if len(argv) < 7:
      print ("Error: please use this format: python Sender.py <filename> <remote_IP> <remote_port> <ack_port_num> <log_filename> <window_size>")
      sys.exit(1)
    else:
      return {"filename": argv[1], "recv_ip": argv[2], "recv_port": int(argv[3]), "send_port": int(argv[4]), "log_name" : argv[5], "window_size" : int(argv[6]) }