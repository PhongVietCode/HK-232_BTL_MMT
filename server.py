import socket
import const  
import sys
import threading
import json
import os
from threading import Thread, Lock
from _thread import *
from queue import Queue
from message import Message, Type, Header

IP = socket.gethostbyname(socket.gethostname())
ADDR = (IP,const.SERVER_PORT)
FORMAT = 'utf-8'

event_flag = threading.Event()

db = {
    "clients": [],
    "files":[]
}
class Server(object):
    def __init__(self):
        # server port to listen for peer
        self.server_socket = None
        self.listen_thread = None
        self.output_queue = Queue(maxsize=100)
        self.output_queue_mutex = Lock()
        self.access_file_mutex = Lock()
        self.is_listening = True
        self.is_printing = True
        self.file_data = db
        with open("./store/db.json", "w") as fp:
            json.dump(db, fp)
            
    def push_output(self, op):
        self.output_queue_mutex.acquire()
        self.output_queue.put(op)
        self.output_queue_mutex.release()
    def get_output(self):
        output = None
        self.output_queue_mutex.acquire()
        if not self.output_queue.empty():
            output = self.output_queue.get()
        self.output_queue_mutex.release()
        return output
    def start(self):
        """
            create server port to listen 
            start a threate to listen for connection from peer
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(ADDR)
        self.listen_thread = Thread(target=self.listen, args=())
        self.listen_thread.start()

    def close(self):
        """
            close server socket listening for client
        """
        self.is_listening = False
        self.is_printing = False
        if self.server_socket:
            self.server_socket.close()
        self.listen_thread.join()
        os._exit(1)
            
    def listen(self):
        """
            start listen for client
            create new thread to handle for new comer
        """
        self.server_socket.listen()
        self.push_output(f"Server listening on {IP}:{const.SERVER_PORT}")
        while self.is_listening:
            try:
                conn, addr = self.server_socket.accept()            
                client_thread = Thread(target=self.handle_request, args=(conn, addr))
                client_thread.start() 
            except:
                break
    def handle_request(self, client_socket, address):
        """
            process connect and disconnect from client
        """
        try:
            client_socket.settimeout(10)
            message = client_socket.recv(const.PACKET_SIZE).decode()
            if not message: 
                client_socket.close()
            else:
                self.push_output(f"{address} request:")
                self.request_message_process(client_socket, message)
        except Exception as e:
            print(f"ERROR with {address}: {e}")
            
                
    def request_message_process(self,client_socket, message):
        """
            process the request message from client and call correspond function
        """
        try:
            message = Message(None, None, None, message)
            msg_header = message.get_header()
            msg_info = message.get_info()
            self.push_output(f"{msg_header}")
            self.push_output("--------------")
            if msg_header == Header.LOG_IN:
                if self.login(msg_info):
                    msg = Message(Header.LOG_IN, Type.RESPONSE, {"status": 200, "msg": "Login successfull"})
                else:
                    msg = Message(Header.LOG_IN, Type.RESPONSE, {"status": 505, "failure_msg": "Have some error in saving client information !"})
            elif msg_header == Header.UPLOAD:
                if self.upload(msg_info):
                    msg = Message(Header.UPLOAD, Type.RESPONSE, {"status":200})
                else:
                    msg = Message(Header.UPLOAD, Type.RESPONSE, {"status": 404, "failure_msg": "Cannot uploaded to database"})
            elif msg_header == Header.DISCOVER:
                files = self.discover()
                if len(files) != 0:
                    msg = Message(Header.DISCOVER, Type.RESPONSE, {"status": 200,"files": files})
                else:
                    msg = Message(Header.DISCOVER, Type.RESPONSE, {"status": 404, "failure_msg": "File in database is empty"})
            elif msg_header == Header.DOWNLOAD:
                peers_list, pieces_count, hash_string = self.download(msg_info)
                if len(peers_list) != 0:
                    msg = Message(Header.DOWNLOAD, Type.RESPONSE, {"status": 200,"peers_list": peers_list, "pieces_count": pieces_count, "hash_string": hash_string})
                else:
                    msg = Message(Header.DOWNLOAD, Type.RESPONSE, {"status": 404, "failure_msg": "No one have the file you need"})
            elif msg_header == Header.LOG_OUT:
                self.logout(msg_info)
                msg = Message(Header.LOG_OUT, Type.RESPONSE, {"status": 200})
            client_socket.send(json.dumps(msg.get_full_message()).encode())
        except Exception as e:
            self.push_output(f"Have some error sending response: {e}")
            
    def login(self, info):
        res = True
        try:
            with open("./store/db.json", "r+") as fp:
                data = json.load(fp)
                if not info in data["clients"]:
                    data["clients"].append(info)
                    fp.seek(0)
                    json.dump(data, fp, indent=4)
            self.file_data = data
        except:
            print(f"Have some error accessing db")
            res = False
        return res
    def logout(self, info):
        res = True
        data= None
        target_id = info.get("ID")
        with self.access_file_mutex:
            try:
                with open("./store/db.json", "r") as fp:
                    data = json.load(fp)
                if "clients" in data:
                    for client in data["clients"]:
                        if client.get("ID") == target_id:
                            data["clients"].remove(client)
                            break  # Exit the loop once the item is found    
                if "files" in data:
                    while True:
                        have_file = False
                        files = data['files']
                        for file in files:
                            IDs = file.get("ID")
                            for id in IDs:
                                if id == target_id:
                                    IDs.remove(id)
                                    have_file = True
                            if len(IDs) == 0:
                                data["files"].remove(file)
                        if not have_file:
                            break
                self.file_data = data
                with open("./store/db.json", "w") as fp:
                    json.dump(data, fp, indent=4)
            except NameError as e:
                print(f"Have some error accessing db: {e}")
                res = False
        return res
        
    def upload(self, info):
        res = True
        duplicated = False
        with self.access_file_mutex:
            try:
                with open("./store/db.json", "r") as fp:
                    data = json.load(fp)
                if "files" in data:
                    for file in data["files"]:
                        if file.get("hash_string") == info['hash_string']:
                            file.get("ID").append(info["ID"])
                            duplicated = True
                            break  # Exit the loop once the item is found   
                    if not duplicated:
                        id = info["ID"]
                        info.update({"ID": [id]})
                        data["files"].append(info) 
                self.file_data = data    
                with open("./store/db.json", "w") as fp:
                    json.dump(data, fp, indent=4) 
            except:
                self.push_output(f"Have some error accessing db")
                res = False
        return res
    def discover(self):
        files = []
        with self.access_file_mutex:
            with open("./store/db.json", "r") as fp:
                    data = json.load(fp)
            if "files" in data:
                for file in data["files"]:
                    files.append(file.get("file_name"))
        return files
    def download(self,info):
        peers_list = []
        IDs = None
        file_name = info.get("file_name")
        pieces_count = None
        hash_string = None
        found  = False
        data = self.file_data
        if "files" in data:
            for file in data["files"]:
                if file.get("file_name") == file_name:
                    found = True
                    IDs = file.get("ID")
                    pieces_count = file.get("pieces_count")
                    hash_string = file.get("hash_string")
                    break
        if found:
            if "clients" in data:
                for id in IDs: # need reformat clients in database
                    for client in data["clients"]:
                        if client.get("ID") == id:
                            peers_list.append(client)
            return peers_list, pieces_count, hash_string
        else:
            return [], 0, ""
