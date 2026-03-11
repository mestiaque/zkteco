#!/usr/bin/env python3
import socket
import re
import requests
from datetime import datetime
import urllib3
import sys
import signal

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = '0.0.0.0'
PORT = 5015
LARAVEL_URL = "https://pr.nitbd.com/iclock/cdata/"

verifyTypes = {'0':'Password/Other','1':'Fingerprint','2':'Card','3':'Password','15':'Face','25':'Palm'}

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(10)

def signal_handler(sig, frame):
    print("\n[!] Server Stopped Safely.")
    server.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("--------------------------------------------------")
print("G4 Pro ADMS Proxy Fix - 2026 LIVE")
print(f"Forwarding to: {LARAVEL_URL}")
print("--------------------------------------------------")

while True:
    try:
        client, addr = server.accept()
        data = client.recv(131072)
        if not data:
            client.close()
            continue

        raw_str = data.decode(errors="ignore")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] Incoming: {addr}")
        # print(f"  --> [Raw Data Received]:\n{raw_str}")
        # ১. এটেনডেন্স ডাটা হ্যান্ডলিং
        if "table=rtlog" in raw_str.lower() or "table=attlog" in raw_str.lower():
            print(f"  --> [FIND] Attendance Data! Processing...")
            sn_match = re.search(r'SN=([A-Z0-9]+)', raw_str, re.I)
            pin_match = re.search(r'pin=(\d+)', raw_str, re.I)
            time_match = re.search(r'time=([\d-]+\s[\d:]+)', raw_str, re.I)
            vtype_match = re.search(r'verifytype=(\d+)', raw_str, re.I)

            postData = {
                'device_sn': sn_match.group(1) if sn_match else 'Unknown',
                'user_id': pin_match.group(1) if pin_match else 'Unknown',
                'time': time_match.group(1) if time_match else 'Unknown',
                'type_code': vtype_match.group(1) if vtype_match else '0',
                'type_name': verifyTypes.get(vtype_match.group(1) if vtype_match else '0', 'Other')
            }

            print(f"  --> [Data] User: {postData['user_id']} | Type: {postData['type_name']}")
            
            try:
                requests.post(LARAVEL_URL, data=postData, headers={'User-Agent': 'PostmanRuntime/7.40.0'}, timeout=5, verify=False)
                print(f"  --> [SUCCESS] Forwarded to Laravel")
            except Exception as e:
                print(f"  --> [ERROR] API Fail: {e}")
            
            response_body = "OK"

        # ২. রেজিস্ট্রেশন এবং কনফিগারেশন লুপ ব্রেকার (G4 Pro স্পেসিফিক)
        elif "options=all" in raw_str or "/iclock/registry" in raw_str:
            print(f"  --> [HANDSHAKE] Sending RegistryCode and Config...")
            # G4 Pro-কে এই প্যারামিটারগুলো দিলে সে লুপ থেকে বের হয়ে আসবে
            response_body = "RegistryCode=None\nServerVersion=3.1.1\nServerName=ADMS\nPushVersion=3.1.1\nErrorDelay=60\nDelay=30\nTransInterval=1\nTransFlag=1111111111\nRealtime=1\nEncrypt=0"
        
        else:
            print(f"  --> [HEARTBEAT] Sending OK")
            response_body = "OK"

        # ৩. প্রফেশনাল HTTP রেসপন্স
        http_res = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain;charset=UTF-8\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "Connection: close\r\n\r\n"
            f"{response_body}"
        )

        client.sendall(http_res.encode())
        client.close()
        print(f"  --> [CLOSE] Response Sent.\n")

    except Exception as e:
        print(f"  --> [SYSTEM ERROR] {e}")
