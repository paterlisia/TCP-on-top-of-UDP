import sys

def recv_arg_parser(argv):
    if len(argv) < 6:
       print ("missing arguments.")
       print ("format: python Receiver.py <filename> <listening_port> <sender_IP> <sender_port> <log_filename>")
       print ("ex. python Receiver.py test/received.txt 8082 192.168.0.3 8080 log/logfile.txt")
       sys.exit(1)
    else:
       return {
               "filename" : argv[1],                                           \
               "recv_port": int(argv[2]),                                      \
               "send_ip"  : argv[3],                                           \
               "send_port": int(argv[4]),                                      \
               "log_name" : argv[5]                                            \
              }

def send_arg_parser(argv):
    if len(argv) < 7:
       print ("missing arguments.")
       print ("format: python Sender.py <filename> <remote_IP> <remote_port> <ack_port_num> <log_filename> <window_size>")
       print ("ex. python Sender.py test/test.txt 192.168.0.3 41192 8082 log/logfile.txt 1000")
       sys.exit(1)
    else:
       return {
               "filename"    : argv[1],                                         \
               "recv_ip"     : argv[2],                                         \
               "recv_port"   : int(argv[3]),                                    \
               "send_port"   : int(argv[4]),                                    \
               "log_name"    : argv[5],                                         \
               "window_size" : int(argv[6])                                     \
              }