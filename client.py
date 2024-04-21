import socket
import const
import random
import platform
from threading import Thread, Lock
import os # method to interact with files
import shutil # library to moving/control file 
import hashlib
from message import Message, Type, Header
import json
import ftplib
import sys
from queue import Queue
from collections import Counter
import time

IP = socket.gethostbyname(socket.gethostname())
HOST = socket.gethostname()
ADDR = (IP,const.SERVER_PORT)
FORMAT = 'utf-8'

class Client:
    def __init__(self):
        self.client_id  = random.randint(1,1000)
        self.client_port = 65000 + random.randint(1,500)
        self.p2s_socket = None
        self.p2p_socket = None
        self.is_listening = True
        self.is_loging_in =  False
        
        self.request_block_queue = Queue(maxsize=200)
        self.download_mutex = Lock()
        
    def start(self):
        self.p2p_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.p2p_socket.bind((IP,self.client_port))
        
        listen_thread = Thread(target=self.listen, args=())
        listen_thread.start()
        
        self.get_user_input()
        
    def init_server_socket(self):
        self.p2s_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.p2s_socket.connect(ADDR)
            return 1
        except:
            return 0
    def get_user_input(self):
        while True:
            inp = input()
            # info = None
            cmd = inp.split(" ")[0]
            
            if cmd.lower() == "upload":
                if not self.is_loging_in:
                    print("You have to login first")
                    continue
                try:
                    info = inp.split(" ")[1]
                    message = self.preprocess_upload_file(info)
                    print(f"msg: {message.get_full_message()}")
                    self.send_msg(message)
                except:
                    print("Not enough information")
            elif cmd.lower() == "login": # check
                if not self.is_loging_in:
                    self.is_loging_in = True
                    message = Message(Header.LOG_IN,Type.REQUEST, {"ID": self.client_id, "IP": IP, "PORT": self.client_port})
                    self.send_msg(message)
            elif cmd.lower() == "logout":
                if self.is_loging_in: 
                    self.is_loging_in = False
                    message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": self.client_id})
                    self.send_msg(message)
            elif cmd.lower() == "download":
                try:
                    info = inp.split(" ")[1]
                    message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": info})
                    res = self.send_msg(message)
                    self.download(info,res)
                except Exception as e:
                    print(f"Error download command: {e}")
            elif cmd.lower() == "discover":
                try:
                    message = Message(Header.DISCOVER,Type.REQUEST, {})
                    res = self.send_msg(message)
                    print(res)
                except:
                    print("Something went wrong !")             
            elif cmd.lower() == 'close':
                print("Closing...")
                if self.is_loging_in: 
                    self.is_loging_in = False
                    message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": self.client_id})
                    self.send_msg(message)
                self.is_listening = False
                sys.exit()
                break
            elif cmd.lower() == 'help':
                print(":))) guess it !")
            else:
                print("Wrong command! Press 'help' to see the support command")
    
    def listen(self):
        self.p2p_socket.listen()
        threads_array = []
        while True:
            if not self.is_listening:
                break
            conn, addr = self.p2p_socket.accept()
            peer_thread = Thread(target=self.handle_request, args=(conn, addr))
            threads_array.append(peer_thread)
            peer_thread.start()
        for thread in threads_array:
            thread.stop()
            thread.join()
        print("Stop listen")

    def handle_request(self, peer_socket, address):
        """
            process connect and disconnect from client
        """
        try:
            peer_socket.settimeout(5)
            message = peer_socket.recv(const.PACKET_SIZE).decode()
            if not message: 
                print(f"{address} : Disconnected")
                peer_socket.close()
            else:
                self.request_message_process(peer_socket,message)
        except Exception as e:
            print(f"ERROR with {address}: {e}") 

    def request_message_process(self,peer_socket, message):
        message = Message(None,None,None, message)
        msg_header = message.get_header()
        msg_info = message.get_info()
        print(f"Client request: {msg_header}")
        if msg_header == Header.PING:
            if self.reply_ping():
                msg = Message(Header.PING, Type.RESPONSE, {"status": 200})
            else:
                msg = Message(Header.PING, Type.RESPONSE, {"status": 404})
        elif msg_header == Header.DOWNLOAD:
            response = self.reply_download(msg_info)
            if response:
                msg = Message(Header.DOWNLOAD, Type.RESPONSE, {"status": 200, "data": response})
            else:
                msg = Message(Header.DOWNLOAD, Type.RESPONSE, {"status": 404})
        peer_socket.send(json.dumps(msg.get_full_message()).encode())
        
    def send_msg(self, message):
        res = self.init_server_socket()
        if res:
            encoded_msg = json.dumps(message.get_full_message()).encode()
            self.p2s_socket.sendall(encoded_msg)
            response = self.p2s_socket.recv(const.PACKET_SIZE).decode()
            self.p2s_socket.close()
            response = Message(None,None,None, response)
            return response.get_info()
        else:
            return "CONNECT_SERVER_ERROR"
    def download(self,file_name, response):
        peers_list = response.get("peers_list")
        pieces_count = response.get("pieces_count")
        piece_index = 0
        peers_array = []
        download_threads_array = []
        # try to connect to all peer
        print("Checking peers living...")
        for peer in peers_list:
            IP = peer.get("IP")
            PORT = peer.get("PORT")
            download_thread = Thread(target=self.check_peer_living, args=(peers_array,IP, PORT))
            download_threads_array.append(download_thread)
            download_thread.start()
        for thread in download_threads_array:
            thread.join()
        print("Check living done all peer")
        download_threads_array = []
        divider = pieces_count/len(peers_array)
        peer_index = 0
        for i in range(pieces_count): # use request block queue
            if i > divider:
                peer_index = peer_index + 1
                divider = divider * 2
            self.request_block_queue.put({"peer_index": peer_index, "file_name": file_name, "chunk_index": i})
        print("Star download...")
        try:
            d_thread = Thread(target=self.request_downloads, args=(peers_array, 1))
            start_time = time.time()
            d_thread.start()
            d_thread.join()
            end_time = time.time()
            print(f"Download done in: {end_time - start_time}")
        except:
            print("Error in request download ")
    def check_peer_living(self,peers_array, ip, port):
        sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sck.connect((ip,port))
            message = Message(Header.PING, Type.REQUEST, {})
            sck.sendall(json.dumps(message.get_full_message()).encode())
            resp = sck.recv(const.PACKET_SIZE).decode()
            sck.close()
            resp = Message(None,None,None, resp)
            peers_array.append({"IP":ip, "PORT": port})            
        except Exception as e:
            print(f"{e}")
            
    def request_downloads(self, peers_array, number):
        threads_container = []
        try:
            while not self.request_block_queue.empty():
                self.download_mutex.acquire()
                request = self.request_block_queue.get()
                self.download_mutex.release() 
                request_thread = Thread(target=self.handle_download_request, args=(request,peers_array))
                threads_container.append(request_thread)
                request_thread.start()
            for thread in threads_container:
                thread.join()
        except Exception as e:
            print(f"Error in request_downloads : {e}")
        
    def handle_download_request(self, request, peers_array):
        index = request.get("peer_index")
        chunk_index = request.get("chunk_index")
        file_name = request.get("file_name")
        peer = peers_array[index]

        sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sck.connect((peer.get("IP"),peer.get("PORT")))
            message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": file_name, "chunk_index": chunk_index})
            sck.sendall(json.dumps(message.get_full_message()).encode())
            response = sck.recv(const.PACKET_SIZE).decode()
            sck.close()
            response = Message(None,None,None, response)
            request_thread = Thread(target=self.handle_download_response, args=(response.get_info(), request, len(peers_array))).start()
        except Exception as e:
            print(f"Error in handle_download_request: {e}")
            
    def handle_download_response(self, response, request, size):
        file_name = request.get("file_name")
        chunk_index = request.get("chunk_index")
        peer_index = request.get("peer_index")
        
        status = response.get("status")
        if status == 200:
            data = response.get("data")
            
            local_repo_path = os.getcwd()
            OS = platform.system()
            if OS == "Windows":
                local_repo_path = f"download_files\\"
            else:
                local_repo_path = f"download_files/"
            if not os.path.exists(local_repo_path): # if not have the folder
                os.mkdir(local_repo_path)
            try:
                download_folder = self.create_folder(local_repo_path + file_name.split(".")[0] + "_chunks")
                chunk_filename = f"{file_name.split('.')[0]}_chunk#{chunk_index}.txt"
                
                with open(download_folder + chunk_filename, "w") as fp:
                    fp.write(data)
            except Exception as e: 
                print(f"Error in handle_download_response: {e}")
        else:
            request.update({"peer_index": (peer_index + 1) % size} )
            self.download_mutex.acquire()
            self.request_block_queue.put(request)
            self.download_mutex.release()
            
    def reply_ping(self):
        return True
    def reply_download(self, info):
        file_name = info.get("file_name")
        chunk_index = info.get("chunk_index")
        
        local_repo_path = self.get_local_repository_path()
        try:
            chunk_folder = self.create_folder(local_repo_path + file_name.split(".")[0] + "_chunks")
            chunk_filename = f"{file_name.split('.')[0]}_chunk#{chunk_index}.txt"
            
            with open(chunk_folder + chunk_filename, "r") as fp:
                data = fp.read()
                return data
        except:
            return None
        
        
    # def login(self, message):
    #     res = self.init_server_socket()
    #     if res:
    #         self.send_msg(self.p2s_socket,message)
    #         response = self.p2s_socket.recv(const.PACKET_SIZE).decode()
    #         self.p2s_socket.close()
    #         response = Message(None,None,None, response)
    #         return response.get_info()
    #     else 
    #         return "CONNECT_SERVER_ERROR"
    # def logout(self, message):
    #     res = self.init_server_socket()
    #     if res:
    #         self.send_msg(self.p2s_socket,message)
    #         response = self.p2s_socket.recv(const.PACKET_SIZE).decode()
    #         self.p2s_socket.close()
    #         response = Message(None,None,None, response)
    #         return response.get_info()
    #     else 
    #         return "CONNECT_SERVER_ERROR"
    
    def get_local_repository_path(self):
        local_repo_path = os.getcwd()
        OS = platform.system()
        if OS == "Windows":
            local_repo_path = f"local_repository\\"
        else:
            local_repo_path = f"local_repository/"
        if not os.path.exists(local_repo_path): # if not have the folder
            os.mkdir(local_repo_path)
        return local_repo_path
    def create_folder(self,folder_name):
        local_repo_path = os.getcwd()
        OS = platform.system()
        if OS == "Windows":
            local_repo_path = f"{folder_name}\\"
        else:
            local_repo_path = f"{folder_name}/"
        if not os.path.exists(local_repo_path): # if not have the folder
            os.mkdir(local_repo_path)
        return local_repo_path
    def hash_file(self, file_name):
        local_repo_path = self.get_local_repository_path()
        try:
            with open(local_repo_path + file_name, "rb") as bigfile:
                file_content = bigfile.read()
                sha256 = hashlib.sha256()
                sha256.update(file_content)
                hash_result = sha256.hexdigest()
                return hash_result
        except:
            print("Hash file has error")  
    def split_file(self,file_name, chunk_size):
        local_repo_path = self.get_local_repository_path()
        smallfile = None
        pieces_count = 0
        pieces_size = []
        sizes = {}
        try:
            with open(local_repo_path + file_name, "rb") as bigfile:
                chunk_folder = self.create_folder(local_repo_path + file_name.split(".")[0] + "_chunks")
                file_size = os.path.getsize(local_repo_path + file_name)
                print(f"file_size: {file_size}")
                while True:
                    chunk = bigfile.read(chunk_size)
                    if not chunk:
                        break
                    small_filename = f"{file_name.split('.')[0]}_chunk#{pieces_count}.txt"
                    with open(chunk_folder + small_filename, "wb") as smallfile:
                        smallfile.write(chunk)
                    pieces_count = pieces_count + 1
                    pieces_size.append(os.path.getsize(chunk_folder + small_filename))
            counter = Counter(pieces_size)
            for size in counter.keys():
                sizes[size] = counter[size]
            return {"pieces_count": pieces_count, "sizes": sizes}
        except Exception as e:
            print(f"Split file has error: {e}")
    def preprocess_upload_file(self,file_name):
        try:
            hash_result = self.hash_file(file_name)
            split_info = self.split_file(file_name, 12)
            message = Message(Header.UPLOAD, Type.REQUEST, {"ID": self.client_id,"file_name": file_name, "hash_string": hash_result, "pieces_count": split_info["pieces_count"], "pieces_length": split_info["sizes"]})
            return message
        except:
            print("Pre-process file failed")
        return 1
        
    def listen_server_thread(self):
        past
    def listern_peer_thread(self):
        past
    def handle_peer_request(self):
        past
    def handle_peer_response(self):
        past
        
        

# # CONNECTION 
# def peer_to_server_thread(): # this is for server listen
#     while True:
#         data = client_socket.recv(const.PACKET_SIZE).decode(FORMAT)
#         if not data: break

#         print(f"Server: {data}")
# def handle_peer(conn, addr): # request from connected peer
#     while True:
#         try:
#             data = conn.recv(const.PACKET_SIZE).decode(FORMAT)
#             if not data:
#                 break
#             print(f"Receive from {addr}: {data}")
#         except ConnectionResetError:
#             break 
#     print(f"Disconnected from {addr}")
#     conn.close()
   
# def peer_to_peer_thread(): # this socket for listen connecting from other peers
#     upload_socket = socket.socket() # socket for client
#     upload_socket.bind((IP, int(private_port)))
#     upload_socket.listen()
#     print(f"Listening for client on {private_port}")
#     local_repo_path = get_local_repository_path()
#     while True:
#         con, addr = upload_socket.accept()
#         print(f"Client {addr}: connected")
#         with open(local_repo_path + "file1.txt", "rb") as bigfile:
#             file_content = bigfile.read()
#             con.send(file_content) 
#         # con.send("ESF".encode(FORMAT))
#         start_new_thread(handle_peer, (con, addr))
        
# def handle_peer_response(socket, port):
#     local_repo_path = get_local_repository_path()
#     while True:
#         data = socket.recv(const.PACKET_SIZE).decode("utf-8")
#         if not data: break
#         print(data)
#         with open(local_repo_path + f"rcv_{private_port}.txt", "w") as rcvfile:
#             rcvfile.write(data)
#     socket.close()

# def connect_to_peer(port):
#     try:
#         download_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
#         download_socket.connect((IP, int(port)))
#         start_new_thread(handle_peer_response, (download_socket, port))
#     except: 
#         print("Cannot connect to client")


# def publish_to_local_repo(source_file_folder, dest_file_name):
#     file_path = get_local_repository_path() + dest_file_name
#     shutil.copyfile(source_file_folder,file_path)
#     print(f"Successfully copied files in folder {source_file_folder} to local repository {dest_file_name}")
# FILE CONTROL
  


# ## METAINFO FILE
# def create_metainfo_file():
#     local_repo_path = get_local_repository_path()
#     # get all files from repo
#     # os.listdir: list of entries name in the directory
#     for file_name in os.listdir(local_repo_path):
#         past
   

## MAGNET TEXT




# def create_magnet_text(file_name):
#     # magnet_text = 
#     past


# def download_file(conn, addr, file_name):
#     past

# def get_user_input():
#     while True:
#         print()
#         inp = input()
#         cmd, new_port = inp.split(" ")
#         if cmd.lower() == "discover":
#             client_socket.send(cmd.encode(FORMAT))
#         elif cmd.lower() == "connect":
#             connect_to_peer(new_port)
#         elif cmd.lower() == "public":
#             # create_metainfo_file()
#             split_file("file1.txt", 12)
#         elif cmd.lower() == "request":
#             create_magnet_text("file1.txt")
#         elif cmd.lower() == "logout":
#             message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": client_id})
#             encoded_msg = json.dumps(message.get_full_message()).encode()
#             client_socket.send(encoded_msg)



# client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # socket for server
# client_socket.connect(ADDR)

# message = Message(Header.REGISTER,Type.REQUEST, {"ID": client_id, "IP": IP, "PORT": private_port})
# encoded_msg = json.dumps(message.get_full_message()).encode()
# client_socket.send(encoded_msg)

# cli = threading.Thread(target=get_user_input, args=())
# cli.start()

# start_new_thread(peer_to_server_thread,())
# peer_to_peer_thread()

client = Client()
client.start()

