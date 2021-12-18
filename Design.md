# **System Design**
**A description of the overall program design**
## **Client**

- TCP connection
    - Connection over UDP <br/>
            The client appication process first starts the connection using socket:<br />
        ```python
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_socket.bind((dest_ip, dest_port))
        ```
    - Send data
        - package data<br/>
        The data to be sent can be formed as `MSS` and `header`. 
            1. `MSS` specifies the maximum amount of application-layer data in the segment, in this project, I set it as `576`.
            2. `header` includes `sorc_port`, `dest_port`, `seq_num`, `ack_num`, `fin_flag`, `window`, `header_len` and `checksum`.  The `seq_num` and `ack_num` is used for  implementing the reliable data transfer, window is for flow control, and `header_len` specifies the length of the TCP header in 32-bits words. `fin_flag` is used to judge if the file has been fully received. 
            3. In this project, I implemented a `PacketGenerator` class to help generate the packet with data and header.
        - window size<br />
        Window size specifies the maximum data that can be sent without being ACKed. To implement this, I ultilized `Multiple-threading`. So I desiged a independent thread as `tcp_send_pkts`, which will keep sending packets whose `seq_num` is within the window size. That is, the `seq_num` is in the range of $(base\_num, \ base\_num+window)$.
        - Buffer<br />
            1. Since the client keeps sending packets within the window_size, there are packets that are sent but not yet been ACKed, I use a `buf` which is implemented by python list to store the sequence number of a packet that has been sent but not be ACKed.
            2. When the client send a packet, then append its `seq_num` to the `buf`.
            3. When the client receive a packet, pop all the element whose `seq_num` lower than the `ack_num` in the `buf`. Because in TCP client, it is the accumulative ACK.
            4. When retransmission happens, send the packet whose `seq_num` is the first element in the `buf` since it is the oldest packet that has not been ACKed.
    - Receive packets<br/>
        I desiged a independent thread as `tcp_recv_acks`, which will keep listen on the `src_port` to receive packets from the server.
        - Fast retransmision<br/>
        If TCP client receives 3 additional ACKs for the same data, resend unACKed segment with the smallest `seq_num`, and this is stored in `buf`, we do not wait for timeout this time.
    - Timer<br/>
        1. To handle on scenario of the loss of packets, I implemented a timer to judge timeout event. And this is done by create a independent thread called `timer_thread` to listen timeout event, and a timer variable to record `send_time`.<br/>
        *note that the timer mentioned below is not the thread!*
        2. Start timer when the first packet is sent or when there is no timer on.
        3. Stop timer when received the `ack_num` for the smallest `seq_num` not be ACKed.
        4. Restart the timer if received the not right `ack_num` since this suggests an ack loss.
    - Time out interval calculation<br/>
        - sample rtt<br/>
            1. Use a tuple to record the sampled `seq_num` and the time be sent.
            2. Once receiving the ACK, if it ACKs the sampled packet, then we can update `time_out_interval` by the EWMA plus "safety margin"; if it is larger than the `seq_num`, then we should discard this sample as packet loss might cause invalid estimation of rtt.
        - timer thread<br/>
            The `timer_thread` mentioned above will adopt this value to listen timeout event. If it detects the timeout event, it will retransmit the packet with the smallest unACKed packet.
- Thread safety<br/>
    To ensure the sycronalization and thread safety, I imported thread lock which will release the lock until all the options have been done in that memory.
## **Server**
- receive packet<br/>
    I implemented `PacketExtractor` class to extract value from packet.
- Send duplicate ACKs scenarios <br/>
    - Checksum not correct
    - Received `seq_num` is not expected.
- Buffer
    - This buffer is used to store the `seq_num` which is not equal to the `expected_seq` the server receives from the client.
    - When the `seq_num` it received is not expected, then pushes it into the buffer with its data.
    - When the `expected_seq` is in our buffer:<br/>
        1. Remove it from the buffer.
        2. Update current `expected_seq`.
        3. Write corresponding data.<br/>
        *note that this should be implemented in a `while` loop*






            
            
    
