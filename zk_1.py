#!/usr/bin/env python3
import socket
import re
import requests
from datetime import datetime
import urllib3
import sys
import signal
import logging
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------ CONFIG ------------------
HOST = '0.0.0.0'
PORT = 5015
LARAVEL_URL = "https://pr.nitbd.com/iclock/cdata/"  # Change to your Laravel URL

verifyTypes = {'0':'Password/Other','1':'Fingerprint','2':'Card','3':'Password','15':'Face','25':'Palm'}
accessTypes = {'0':'Access Denied','1':'Access Granted'}

# ------------------ LOGGING ------------------
if not os.path.exists("logs"):
    os.mkdir("logs")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
attendance_logger = logging.getLogger('attendance')
access_logger = logging.getLogger('access')

att_handler = logging.FileHandler('logs/attendance.log')
att_handler.setLevel(logging.INFO)
attendance_logger.addHandler(att_handler)

acc_handler = logging.FileHandler('logs/access.log')
acc_handler.setLevel(logging.INFO)
access_logger.addHandler(acc_handler)

error_handler = logging.FileHandler('logs/error.log')
error_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(error_handler)

# ------------------ SERVER SETUP ------------------
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
print("G4 Pro ADMS Proxy - A&C + T&A Compatible")
print(f"Listening on port {PORT}, forwarding to: {LARAVEL_URL}")
print("--------------------------------------------------")

# ------------------ MAIN LOOP ------------------
while True:
    try:
        client, addr = server.accept()

        # ------------------ RAW DATA DEBUG ------------------
        print(f"[RAW DATA]: {data}")       # original bytes
        print(f"[RAW HEX] : {data.hex()}") # hex format
        # ----------------------------------------------------

        data = client.recv(131072)
        if not data:
            client.close()
            continue

        raw_str = data.decode(errors="ignore")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Incoming: {addr}")

        response_body = "OK"

        # ------------------ ATTENDANCE (T&A) ------------------
        if "table=rtlog" in raw_str.lower() or "table=attlog" in raw_str.lower():
            sn_match = re.search(r'SN=([A-Z0-9]+)', raw_str, re.I)
            pin_match = re.search(r'pin=(\d+)', raw_str, re.I)
            time_match = re.search(r'time=([\d-]+\s[\d:]+)', raw_str, re.I)
            vtype_match = re.search(r'verifytype=(\d+)', raw_str, re.I)

            postData = {
                'event_type': 'attendance',
                'device_sn': sn_match.group(1) if sn_match else 'Unknown',
                'user_id': pin_match.group(1) if pin_match else 'Unknown',
                'time': time_match.group(1) if time_match else 'Unknown',
                'type_code': vtype_match.group(1) if vtype_match else '0',
                'type_name': verifyTypes.get(vtype_match.group(1) if vtype_match else '0', 'Other')
            }

            print(f"  --> [Attendance] User: {postData['user_id']} | Type: {postData['type_name']}")
            attendance_logger.info(postData)

            try:
                requests.post(LARAVEL_URL, data=postData, headers={'User-Agent':'PostmanRuntime/7.40.0'}, timeout=5, verify=False)
                print("  --> [SUCCESS] Attendance Forwarded")
            except Exception as e:
                print(f"  --> [ERROR] Laravel API Fail: {e}")
                logging.error(f"Attendance API Error: {e} | Data: {postData}")

        # ------------------ ACCESS CONTROL (A&C) ------------------
        elif "table=aclog" in raw_str.lower():
            sn_match = re.search(r'SN=([A-Z0-9]+)', raw_str, re.I)
            card_match = re.search(r'pin=(\d+)', raw_str, re.I)
            time_match = re.search(r'time=([\d-]+\s[\d:]+)', raw_str, re.I)
            ac_match = re.search(r'status=(\d+)', raw_str, re.I)

            postData = {
                'event_type': 'access',
                'device_sn': sn_match.group(1) if sn_match else 'Unknown',
                'user_id': card_match.group(1) if card_match else 'Unknown',
                'time': time_match.group(1) if time_match else 'Unknown',
                'access_status_code': ac_match.group(1) if ac_match else '0',
                'access_status_name': accessTypes.get(ac_match.group(1) if ac_match else '0', 'Unknown')
            }

            print(f"  --> [Access] User: {postData['user_id']} | Status: {postData['access_status_name']}")
            access_logger.info(postData)

            try:
                requests.post(LARAVEL_URL, data=postData, headers={'User-Agent':'PostmanRuntime/7.40.0'}, timeout=5, verify=False)
                print("  --> [SUCCESS] Access Forwarded")
            except Exception as e:
                print(f"  --> [ERROR] Laravel API Fail: {e}")
                logging.error(f"Access API Error: {e} | Data: {postData}")

        # ------------------ HANDSHAKE / HEARTBEAT ------------------
        else:
            if "options=all" in raw_str.lower() or "/iclock/registry" in raw_str.lower():
                response_body = "RegistryCode=None\nServerVersion=3.1.1\nServerName=ADMS\nPushVersion=3.1.1\nErrorDelay=60\nDelay=30\nTransInterval=1\nTransFlag=1111111111\nRealtime=1\nEncrypt=0"
                print(f"  --> [HANDSHAKE] Sending RegistryCode and Config...")
            else:
                print(f"  --> [HEARTBEAT] Sending OK")

        # ------------------ SEND RESPONSE ------------------
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
        logging.error(f"System Error: {e}")
