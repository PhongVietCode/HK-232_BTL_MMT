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
    def __init__(self, server_port):
        # server port to listen for peer
        self.server_socket = None
        
        self.output_queue = Queue(maxsize=100)
        
        # if not os.path.exists("./store/db.json") or os.path.getsize("./store/db.json") == 0:
        with open("./store/db.json", "w") as fp:
            json.dump(db, fp)
            
    def start(self):
        """
            create server port to listen 
            start a threate to listen for connection from peer
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(ADDR)
        listen_thread = Thread(target=self.listen, args=())
        listen_thread.start()

    def close(self):
        """
            close server socket listening for client
        """
        if self.server_socket:
            self.server_socket.close()
            
    def listen(self):
        """
            start listen for client
            create new thread to handle for new comer
        """
        self.server_socket.listen()
        print(f"Server listening on port {const.SERVER_PORT}")
        while True:
            conn, addr = self.server_socket.accept()            
            client_thread = Thread(target=self.handle_request, args=(conn, addr))
            client_thread.start()   
        
    def handle_request(self, client_socket, address):
        """
            process connect and disconnect from client
        """
        try:
            client_socket.settimeout(10)
            message = client_socket.recv(const.PACKET_SIZE).decode()
            if not message: 
                print(f"{address} : Disconnected")
                client_socket.close()
            else:
                print(f"{address[0]} request")
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
            if msg_header == Header.LOG_IN:
                if self.login(msg_info):
                    msg = Message(Header.LOG_IN, Type.RESPONSE, {"status": 200})
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
                    msg = Message(Header.DISCOVER, Type.RESPONSE, {"status": 200,"peers_list": peers_list, "pieces_count": pieces_count, "hash_string": hash_string})
                else:
                    msg = Message(Header.DISCOVER, Type.RESPONSE, {"status": 404, "failure_msg": "No one have the file you need"})
            elif msg_header == Header.LOG_OUT:
                if self.logout(msg_info):
                    msg = Message(Header.LOG_IN, Type.RESPONSE, {"status": 200})
                else:
                    msg = Message(Header.LOG_IN, Type.RESPONSE, {"status": 505, "failure_msg": "Have some error in saving client information !"})
            client_socket.send(json.dumps(msg.get_full_message()).encode())
        except Exception as e:
            print(f"Have some error sending response: {e}")
            
    def login(self, info):
        res = True
        try:
            with open("./store/db.json", "r+") as fp:
                data = json.load(fp)
                if not info in data["clients"]:
                    data["clients"].append(info)
                    fp.seek(0)
                    json.dump(data, fp, indent=4)
        except:
            print(f"Have some error accessing db")
            res = False
        return res
                
    def logout(self, info):
        res = True
        target_id = info.get("ID")
        data= None
        try:
            with open("./store/db.json", "r") as fp:
                data = json.load(fp)
            if "clients" in data:
                for client in data["clients"]:
                    if client.get("ID") == target_id:
                        data["clients"].remove(client)
                        break  # Exit the loop once the item is found    
            if "files" in data:
                for file in data["files"]:
                    IDs = file.get("ID")
                    for id in IDs:
                        if id == target_id:
                            IDs.remove(id)
                    if len(IDs) == 0:
                        data["files"].remove(file)
                        break
            with open("./store/db.json", "w") as fp:
                json.dump(data, fp, indent=4) 
        except NameError as e:
            print(f"Have some error accessing db: {e}")
            res = False
        return res
        
    def upload(self, info):
        res = True
        duplicated = False
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
            with open("./store/db.json", "w") as fp:
                json.dump(data, fp, indent=4) 
        except:
            print(f"Have some error accessing db")
            res = False
        return res
    def discover(self):
        files = []
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
        with open("./store/db.json", "r") as fp:
                data = json.load(fp)
        if "files" in data:
            for file in data["files"]:
                if file.get("file_name") == file_name:
                    found = True
                    IDs = file.get("ID")
                    pieces_count = file.get("pieces_count")
                    hash_string = file.get("hash_string")
        if found:
            if "clients" in data:
                for id in IDs: # need reformat clients in database
                    for client in data["clients"]:
                        if client.get("ID") == id:
                            peers_list.append(client)
            return peers_list, pieces_count, hash_string
        else:
            return [], 0, ""
# __main__
def main():
    server = Server(8003)
    server.start()

if __name__ == "__main__":
    main()