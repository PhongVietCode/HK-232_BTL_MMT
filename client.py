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
import math
import shutil
from array import array

IP = socket.gethostbyname(socket.gethostname())
SERVER_IP = const.SERVER_IP
HOST = socket.gethostname()
ADDR = (IP,const.SERVER_PORT)
FORMAT = 'utf-8'
CHUNK_SIZE = const.CHUNK_SIZE
class Client:
    def __init__(self):
        self.client_id  = random.randint(1,1000)
        self.client_port = 65000 + random.randint(1,500)
        self.p2s_socket = None
        self.p2p_socket = None
        self.is_listening = True
        self.is_printing = True
        self.is_loging_in =  False
        
        self.thread_list = []
        self.request_block_queue = Queue(maxsize=200)
        self.download_mutex = Lock()
        
        self.output_queue = Queue(maxsize=500)
        self.ouput_mutex = Lock()
        
        self.client_req_output = Queue(maxsize=500)
        self.req_output_mutex = Lock()
        self.upload_speed = 0
        self.download_speed = 0
        self.local_file_folder = self.create_folder(f'local_repository_{self.client_id}')
        
        self.slot_download_list = {}
         
    def start(self):
        self.push_output("Staring...")
        self.p2p_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.p2p_socket.bind((IP,self.client_port))
        
        listen_thread = Thread(target=self.listen, args=())
        print_thread = Thread(target=self.print_output, args=())
        
        self.thread_list.append(print_thread)
        self.thread_list.append(listen_thread)
        self.push_output("You can input now")
        
        print_thread.start()
        listen_thread.start()

        # main thread
        # self.get_input()
        
    def init_server_socket(self):
        self.p2s_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.p2s_socket.connect((SERVER_IP,const.SERVER_PORT))
            return 1
        except:
            return 0
    def push_output(self, cnt):
        self.ouput_mutex.acquire()
        self.output_queue.put(cnt)
        self.ouput_mutex.release()
    def client_push_output(self, cnt):
        self.req_output_mutex.acquire()
        self.client_req_output.put(cnt)
        self.req_output_mutex.release()
    def get_input(self, command):
        # while self.is_printing:
            # self.push_output('>> \t')
        # inp = input()
        # info = None
        inp = command
        cmd = inp.split(" ")[0]
        
        if cmd.lower() == "upload":
            if not self.is_loging_in:
                self.push_output("You have to login first")
                return
            try:
                upload_files = inp.split(" ")[1:]
                for f in upload_files:
                    t = Thread(target=self.upload, args=(f,1))
                    t.start()
            except:
                self.push_output("Not enough information")
        elif cmd.lower() == "login": #check 
            if not self.is_loging_in:
                t = Thread(target=self.login, args=())
                t.start()
            else: 
                self.push_output("You have already logged in!")
        elif cmd.lower() == "logout":
            if self.is_loging_in: 
                self.is_loging_in = False
                t = Thread(target=self.logout, args=())
                t.start()
                message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": self.client_id})
                self.send_msg(message)
            self.push_output("Logout done !")   
        elif cmd.lower() == "download":
            if not self.is_loging_in:
                self.push_output("You have to login first")
                return
            try:
                download_files = inp.split(" ")[1:]
                for f in download_files:
                    t = Thread(target=self.download_many_files, args=(f,1))
                    t.start()
            except Exception as e:
                self.push_output(f"Error in download: {e}")
        elif cmd.lower() == "discover":
            try:
                message = Message(Header.DISCOVER,Type.REQUEST, {})
                res = self.send_msg(message)
                self.push_output(res)
            except:
                self.push_output("Error in discover")
        elif cmd.lower() == 'close':
            self.push_output("Closing...")
            time.sleep(0.5)
            self.close()
            return
        elif cmd.lower() == 'help':
            self.push_output("U need some help!??")
        elif cmd.lower() == 'copy':
            copy_files = inp.split(" ")[1:]
            for f in copy_files:
                Thread(target=self.copyfile, args=(f, 1)).start()
        else:
            self.push_output("Wrong command? Try another !")
    def login(self):
        self.push_output("Logging in...")
        message = Message(Header.LOG_IN,Type.REQUEST, {"ID": self.client_id, "IP": IP, "PORT": self.client_port})
        response = self.send_msg(message)
        if response:
            if response['status'] == 200:
                self.push_output(f'{response["msg"]}')
                self.is_loging_in = True
            else:
                self.push_output(f'{response["failure_msg"]}')
        else:
            self.push_output("Cannot connect to server")
    def copyfile(self, file_name, number):
        self.push_output(f"Copying {file_name}") 
        local_path = self.get_local_repository_path()
        try:
            shutil.copy2(local_path + file_name, self.local_file_folder)
            self.push_output(f"Done copy file {file_name}")
        except:
            self.push_output("File doesn't exist")
    def print_output(self):
        # while self.is_printing:
            # time.sleep(0.5)
        output = None
        self.ouput_mutex.acquire()
        if not self.output_queue.empty():
            output = self.output_queue.get()
            # print(output) 
        self.ouput_mutex.release()
        return output
    def print_client_output(self):
        # while self.is_printing:
            # time.sleep(0.5)
        output = None
        self.req_output_mutex.acquire()
        if not self.client_req_output.empty():
            output = self.client_req_output.get()
            # print(output) 
        self.req_output_mutex.release()
        return output
    def listen(self):
        self.p2p_socket.listen()
        while self.is_listening:
            try:
                conn, addr = self.p2p_socket.accept()
                peer_thread = Thread(target=self.handle_request, args=(conn, addr))
                self.thread_list.append(peer_thread)
                peer_thread.start()
            except OSError:
                break

    def handle_request(self, peer_socket, address):
        """
            process connect and disconnect from client
        """
        try:
            peer_socket.settimeout(5)
            message = peer_socket.recv(const.PACKET_SIZE).decode()
            self.request_message_process(peer_socket,message)
        except Exception as e:
            self.push_output(f"ERROR with handle request {address}: {e}") 

    def request_message_process(self,peer_socket, message):
        message = Message(None,None,None, message)
        msg_header = message.get_header()
        msg_info = message.get_info()
        self.client_push_output(f"Client request: {msg_header}")
        if msg_header == Header.PING:
            if self.reply_ping():
                msg = Message(Header.PING, Type.RESPONSE, {"status": 200})
            else:
                msg = Message(Header.PING, Type.RESPONSE, {"status": 404})
            peer_socket.send(json.dumps(msg.get_full_message()).encode())  
        elif msg_header == Header.DOWNLOAD:
            response = self.reply_download(msg_info)
            peer_socket.sendall(response)
            
        
    def send_msg(self, message):
        res = self.init_server_socket()
        if res:
            encoded_msg = json.dumps(message.get_full_message()).encode()
            self.p2s_socket.sendall(encoded_msg)
            self.p2s_socket.settimeout(3)
            response = self.p2s_socket.recv(const.PACKET_SIZE).decode()
            self.p2s_socket.close()
            response = Message(None,None,None, response)
            return response.get_info()
        else:
            self.push_output("CONNECT_SERVER_ERROR")    
    def upload(self, file_name, number):
        info = file_name
        # if info.split(".")[1] != "txt":
        #     self.push_output("Sorry! Current version just supoprts file type '.txt'!")
        #     return
        chunks_folder = info.split('.')[0] + '_chunks'
        files = os.listdir(self.local_file_folder)
        if chunks_folder in files:
            self.push_output("You have uploaded file information to server")
            return
        self.push_output("Uploading...")
        thrd  = Thread(target=self.preprocess_upload_file, args=(info, 1))
        self.thread_list.append(thrd)
        thrd.start()
    def download_many_files(self, file_name, number):
        info = file_name
        # if info.split(".")[1] != 'txt':
        #     self.push_output("Sorry! Current version just supoprts file type '.txt'!")
        #     return
        files = os.listdir(self.local_file_folder)
        if info in files:
            self.push_output("File have been loaded in your folder")
            return
        message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": info})
        res = self.send_msg(message)
        thr = Thread(target= self.download, args=(info,res))
        self.thread_list.append(thr)
        thr.start()
    def download(self, file_name, response):
        if file_name in self.slot_download_list:
            self.push_output("The file is downloading!")
            return
        peers_list = response.get("peers_list")
        pieces_count = response.get("pieces_count")
        hash_string = response.get("hash_string")
        pieces_length = response.get("pieces_length")
        if not peers_list:
            self.push_output("No peer contain your file! Use 'discover' command to know which file is available")
            return
        
        # self.push_output(self.slot_download_list[file_name])
        # piece_index = 0
        living_peers = []
        thread_array = []
        
        # ===== Check living peer ======
        self.push_output("Checking peers living...")
        for peer in peers_list:
            IP = peer.get("IP")
            PORT = peer.get("PORT")
            download_thread = Thread(target=self.check_peer_living, args=(living_peers,IP, PORT))
            thread_array.append(download_thread)
            download_thread.start()
        for thread in thread_array:
            thread.join()
        thread_array = []
        self.push_output("Check living all peer done")
        # ===== Check living peer done ========
        slot_download_mutex = Lock()
        slot_download_queue_mutex = Lock()
        
        if len(living_peers) == 0:
            self.push_output("No peers is online")
            return
        self.slot_download_list[file_name] = {"file_name": file_name,"hash_string": hash_string, "pieces_count": pieces_count, "downloaded_chunks": 0 }
        divider = math.floor(pieces_count/len(living_peers))
        start_piece_index = 0
        end_piece_index = divider
        if end_piece_index == pieces_count:
            end_piece_index = pieces_count - 1
        peer_index = 0
        
        # ======= Request download chunks ========
        start_time = time.time()
        for peer in living_peers:
            thr = Thread(target=self.request_peer_download, args=(peer, start_piece_index, end_piece_index, file_name, pieces_count, peer_index,slot_download_mutex,slot_download_queue_mutex, pieces_length, len(living_peers)))
            thread_array.append(thr)
            thr.start()
            peer_index = peer_index + 1
            start_piece_index = end_piece_index + 1
            if (peer_index < len(living_peers) - 1): # not last peer
                end_piece_index = end_piece_index + divider
            else:
                end_piece_index = pieces_count - 1
        for thread in thread_array:
            thread.join()
        # ======== Handle error chunks =======
        thread_array = []
        while not self.request_block_queue.empty():
            slot_download_queue_mutex.acquire()
            request = self.request_block_queue.get()
            slot_download_queue_mutex.release() 
            request_thread = Thread(target=self.request_peer_download, args=(living_peers[request.get("peer_index")], request.get("chunk_index"), request.get("chunk_index"), request.get("file_name"), pieces_count, request.get("peer_index"),slot_download_mutex,slot_download_queue_mutex,pieces_length, len(living_peers)))
            thread_array.append(request_thread)
            request_thread.start()
        for thread in thread_array:
            thread.join()
        end_time = time.time()
        del self.slot_download_list[file_name]
        self.push_output(f"Download {file_name} done: {end_time - start_time}")
        # ===== Check the correction of the combined file
        self.push_output(f"Checking {file_name} file error...")
        if self.combine_file(file_name, hash_string, pieces_count):
            message = Message(Header.UPLOAD, Type.REQUEST, {"ID": self.client_id,"file_name": file_name, "hash_string": hash_string, "pieces_count": pieces_count})
            self.push_output(f"File {file_name} upload done: {message.get_info()}")
            self.send_msg(message)
        else:
            os.remove(self.local_file_folder + file_name)
            shutil.rmtree(self.local_file_folder + file_name.split(".")[0] + "_chunks")
    def check_peer_living(self,living_peers, ip, port):
        sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sck.connect((ip,port))
            message = Message(Header.PING, Type.REQUEST, {})
            sck.sendall(json.dumps(message.get_full_message()).encode())
            resp = sck.recv(const.PACKET_SIZE).decode()
            sck.close()
            resp = Message(None,None,None, resp)
            living_peers.append({"IP":ip, "PORT": port})        
            self.push_output("Connected successfull")   
        except Exception as e:
            pass
            
            
    def request_peer_download(self, peer, start_index, end_index, file_name, pieces_count, peer_index,slot_download_mutex,slot_download_queue_mutex, pieces_length, peers_count):
        thread_array = []
        while start_index <= end_index: # use request block queue
            sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            try:
                sck.connect((peer.get("IP"),peer.get("PORT")))
                message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": file_name, "chunk_index": start_index})
                start_time = time.time()
                sck.sendall(json.dumps(message.get_full_message()).encode())
                
                response = sck.recv(const.PACKET_SIZE)
                end_time = time.time()
                self.download_speed = end_time - start_time
                sck.close()
                # response = Message(None,None,None, response)
                request_thread = Thread(target=self.response_peer_download, args=(response, pieces_count, peer_index, start_index, file_name,slot_download_mutex,slot_download_queue_mutex, pieces_length, peers_count))
                thread_array.append(request_thread)
                request_thread.start()
                start_index = start_index + 1
            except Exception as e:
                self.push_output(f"Error in request_peer_download: {e}")
        for thread in thread_array:
            thread.join()
    def response_peer_download(self, response, pieces_count, peer_index, chunk_index, file_name,slot_download_mutex,slot_download_queue_mutex, pieces_length, peers_count):
        # status = response.get("status")     
        check_valid = True
        file_sizes = []
        for s in pieces_length.keys():
            file_sizes.append(int(s))
        if not response:
            check_valid = False
        else:
            try:
                chunk_folder = self.create_folder(self.local_file_folder + file_name.split(".")[0] + "_chunks")
                chunk_filename = f"{file_name.split('.')[0]}_chunk#{chunk_index}.{file_name.split('.')[1]}"
                with open(chunk_folder + chunk_filename, "wb") as fp:
                    fp.write(response)
                file_size = os.path.getsize(chunk_folder + chunk_filename)
                # self.push_output(f"Downloaded file size: {file_size}")
                if chunk_index != pieces_count:
                    if file_size < file_sizes[0]:
                        check_valid = False
                else:
                    if file_size < file_sizes[1]:
                        check_valid= False
                slot_download_mutex.acquire()
                downloaded_chunks = self.slot_download_list[file_name]['downloaded_chunks']
                self.slot_download_list[file_name].update({"downloaded_chunks": (downloaded_chunks + 1)})
                slot_download_mutex.release() 
            except Exception as e: 
                pass
        if not check_valid: # download failed
            slot_download_queue_mutex.acquire()
            self.request_block_queue.put({"peer_index": (peer_index + 1) % peers_count, "file_name": file_name, "chunk_index": chunk_index})
            slot_download_queue_mutex.release()
    def reply_ping(self):
        return True
    def reply_download(self, info):
        file_name = info.get("file_name")
        chunk_index = info.get("chunk_index")
        try:
            chunk_folder = self.create_folder(self.local_file_folder + file_name.split(".")[0] + "_chunks")
            chunk_filename = f"{file_name.split('.')[0]}_chunk#{chunk_index}.{file_name.split('.')[1]}"
            
            with open(chunk_folder + chunk_filename, "rb") as fp:
                data = fp.read()
            return data
        except:
            return None
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
        try:
            with open(self.local_file_folder + file_name, "rb") as bigfile:
                file_content = bigfile.read()
            sha256 = hashlib.sha256()
            sha256.update(file_content)
            hash_result = sha256.hexdigest()
            return hash_result
        except:
            self.push_output("Hash file has error/File doesn't exist")  
    def split_file(self, file_name, chunk_size):
        smallfile = None
        pieces_count = 0
        pieces_size = []
        sizes = {}
        try:
            with open(self.local_file_folder + file_name, "rb") as bigfile:
                chunk_folder = self.create_folder(self.local_file_folder + file_name.split(".")[0] + "_chunks")
                file_size = os.path.getsize(self.local_file_folder + file_name)
                self.push_output(f'{file_size}')
                while True:
                    chunk = bigfile.read(chunk_size)
                    if not chunk:
                        break
                    small_filename = f"{file_name.split('.')[0]}_chunk#{pieces_count}.{file_name.split('.')[1]}"
                    with open(chunk_folder + small_filename, "wb") as smallfile:
                        smallfile.write(chunk)
                    pieces_count = pieces_count + 1
                    pieces_size.append(os.path.getsize(chunk_folder + small_filename))
            counter = Counter(pieces_size)
            for size in counter.keys():
                sizes[size] = counter[size]
            return {"pieces_count": pieces_count, "sizes": sizes}
        except Exception as e:
            self.push_output(f"Split file has error: {e}")
    def combine_file(self, file_name, hash_string, pieces_count):
        try:
            chunk_folder = self.create_folder(self.local_file_folder + file_name.split(".")[0] + "_chunks")
            with open(self.local_file_folder + file_name, "wb") as fo:
                for i in range(pieces_count):
                    chunk_filename = f"/{file_name.split('.')[0]}_chunk#{i}.{file_name.split('.')[1]}"
                    with open(chunk_folder + chunk_filename, "rb") as fi:
                        data = fi.read()
                    fo.write(data)
            with open(self.local_file_folder + file_name, "rb") as bigfile:
                file_content = bigfile.read()
                sha256 = hashlib.sha256()
                sha256.update(file_content)
                hash_result = sha256.hexdigest()
            if hash_string == hash_result:
                self.push_output("Combined file successful.")
                return 1
            else:
                self.push_output("Combined file is having some error !")
                return 0
        except Exception as e:
            self.push_output(f"Error in combine file: {e}")
            return 0
    def preprocess_upload_file(self,file_name, number):
        try:
            hash_result = self.hash_file(file_name)
            split_info = self.split_file(file_name, CHUNK_SIZE)
            message = Message(Header.UPLOAD, Type.REQUEST, {"ID": self.client_id,"file_name": file_name, "hash_string": hash_result, "pieces_count": split_info["pieces_count"], "pieces_length": split_info["sizes"]})
            self.push_output(f"File upload done: {message.get_info()}")
            self.send_msg(message)
        except:
            self.push_output("Pre-process file failed")
    def logout(self):
        files = os.listdir(self.local_file_folder)
        for f in files:
            if len(f.split('_')) > 1:
                shutil.rmtree(f)
    def close(self):
        if self.is_loging_in: 
            self.is_loging_in = False
            message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": self.client_id})
            self.send_msg(message)
        self.is_listening = False
        self.is_printing = False
        self.p2p_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.p2p_socket.close()
        shutil.rmtree(self.local_file_folder)
        # for thread in self.thread_list:
        #     if thread:
        #         thread.join()
        os._exit(1)

# client = Client()
# client.start()

