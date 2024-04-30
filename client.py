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

IP = socket.gethostbyname(socket.gethostname())
HOST = socket.gethostname()
ADDR = (IP,const.SERVER_PORT)
FORMAT = 'utf-8'
CHUNK_SIZE = 12
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
        
        self.slot_download_list = [None] * 5
        self.slot_download_mutex = Lock()
        
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
        #self.get_input()
        
    def init_server_socket(self):
        self.p2s_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.p2s_socket.connect(ADDR)
            return 1
        except:
            return 0
    def push_output(self, cnt):
        self.ouput_mutex.acquire()
        self.output_queue.put(cnt)
        self.ouput_mutex.release()
    def get_input(self, inp):
        #while self.is_printing:
            # self.push_output('>> \t')
            #inp = input()
            # info = None
            cmd = inp.split(" ")[0]
            
            if cmd.lower() == "upload":
                if not self.is_loging_in:
                    self.push_output("You have to login first")
                    #continue
                try:
                    info = inp.split(" ")[1]
                    if info.split(".")[1] != "txt":
                        self.push_output("Sorry! Current version just supoprts file type '.txt'!")
                        #continue
                    message = self.preprocess_upload_file(info)
                    self.push_output(f"msg: {message.get_full_message()}")
                    self.send_msg(message)
                except:
                    self.push_output("Not enough information")
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
                    if info.split(".")[1] != 'txt':
                        self.push_output("Sorry! Current version just supoprts file type '.txt'!")
                        #continue
                    message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": info})
                    res = self.send_msg(message)
                    self.download(info,res)
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
                #break
            elif cmd.lower() == 'help':
                self.push_output("U need some help!??")
            else:
                self.push_output("Wrong command? Try another !")
    def print_output(self):
        while self.is_printing:
            # time.sleep(0.5)
            self.ouput_mutex.acquire()
            if not self.output_queue.empty():
                output = self.output_queue.get()
                print(output)
            self.ouput_mutex.release()
    def listen(self):
        self.p2p_socket.listen()
        while self.is_listening:
            conn, addr = self.p2p_socket.accept()
            peer_thread = Thread(target=self.handle_request, args=(conn, addr))
            self.thread_list.append(peer_thread)
            peer_thread.start()

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
        self.push_output(f"Client request: {msg_header}")
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
            self.push_output("CONNECT_SERVER_ERROR")
    def download(self, file_name, response):
        peers_list = response.get("peers_list")
        pieces_count = response.get("pieces_count")
        hash_string = response.get("hash_string")
        if not peers_list:
            self.push_output("No peer contain your file! Use 'discover' command to know which file is available")
            return
        has_empty_slot = False
        download_slot_index = 0
        self.slot_download_mutex.acquire()
        for download_slot in self.slot_download_list:
            if download_slot == None:
                has_empty_slot = True
                break      
            download_slot_index = download_slot_index + 1
        self.slot_download_list[download_slot_index] = {"file_name": file_name,"hash_string": hash_string, "pieces_count": pieces_count, "downloaded_chunks": 0 }
        self.slot_download_mutex.release()
        if not has_empty_slot:
            self.push_output("Download queue is full now !")
            return
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
        if len(living_peers) == 0:
            self.push_output("No peers is online")
            self.slot_download_mutex.acquire()
            self.slot_download_list[download_slot_index] = None
            self.slot_download_mutex.release()
            return
        divider = math.floor(pieces_count/len(living_peers))
        start_piece_index = 0
        end_piece_index = divider
        if end_piece_index == pieces_count:
            end_piece_index = pieces_count - 1
        peer_index = 0
        # ======= Request download chunks ========
        start_time = time.time()
        for peer in living_peers:
            self.push_output(f"{end_piece_index}")
            thr = Thread(target=self.request_peer_download, args=(peer, start_piece_index, end_piece_index, file_name, pieces_count, peer_index, download_slot_index ))
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
            self.download_mutex.acquire()
            request = self.request_block_queue.get()
            self.download_mutex.release() 
            request_thread = Thread(target=self.request_peer_download, args=(living_peers[request.get("peer_index")], request.get("chunk_index"), request.get("chunk_index"), request.get("file_name"), pieces_count, request.get("peer_index"), download_slot_index))
            thread_array.append(request_thread)
            request_thread.start()
        for thread in thread_array:
            thread.join()
        end_time = time.time()
        self.push_output(f"Download done: {end_time - start_time}")
        
        # ===== Check the correction of the combined file
        self.combine_file(file_name, download_slot_index)
        

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
            self.push_output(f"{e}")
            
            
    def request_peer_download(self, peer, start_index, end_index, file_name, pieces_count, peer_index, download_slot_index):
        thread_array = []
        while start_index <= end_index: # use request block queue
            sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            try:
                sck.connect((peer.get("IP"),peer.get("PORT")))
                message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": file_name, "chunk_index": start_index})
                sck.sendall(json.dumps(message.get_full_message()).encode())
                
                response = sck.recv(const.PACKET_SIZE).decode()
                sck.close()
                response = Message(None,None,None, response)
                request_thread = Thread(target=self.response_peer_download, args=(response.get_info(), pieces_count, peer_index, start_index, file_name, download_slot_index))
                thread_array.append(request_thread)
                request_thread.start()
                start_index = start_index + 1
            except Exception as e:
                self.push_output(f"Error in request_peer_download: {e}")
        for thread in thread_array:
            thread.join()
    def response_peer_download(self, response, pieces_count, peer_index, chunk_index, file_name, download_slot_index):
        status = response.get("status")          
        if status == 200: # download successfully
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
                self.slot_download_mutex.acquire()
                downloaded_chunks = self.slot_download_list[download_slot_index]['downloaded_chunks']
                self.slot_download_list[download_slot_index].update({"downloaded_chunks": (downloaded_chunks + 1)})
                self.slot_download_mutex.release()  
                downloaded_chunks = self.slot_download_list[download_slot_index]['downloaded_chunks']
                total_piece = self.slot_download_list[download_slot_index]["pieces_count"]
                self.push_output(f"Download {downloaded_chunks}/{total_piece}")
            except Exception as e: 
                self.push_output(f"Error in response_peer_download: {e}")
        else: # download failed
            self.download_mutex.acquire()
            self.request_block_queue.put({"peer_index": peer_index + 1, "file_name": file_name, "chunk_index": chunk_index})
            self.download_mutex.release()
    

    # def request_downloads(self, peers_array, pieces_count):
    #     threads_container = []
    #     try:
    #         while not self.request_block_queue.empty():
    #             self.download_mutex.acquire()
    #             request = self.request_block_queue.get()
    #             request_thread = Thread(target=self.handle_download_request, args=(request,peers_array))
    #             threads_container.append(request_thread)
    #             request_thread.start()
    #             self.download_mutex.release() 
    #         for thread in threads_container:
    #             thread.join()
    #         request_thread.join()
    #     except Exception as e:
    #         self.push_output(f"Error in request_downloads : {e}")
        
    # def handle_download_request(self, request, peers_array):
    #     index = request.get("peer_index")
    #     chunk_index = request.get("chunk_index")
    #     file_name = request.get("file_name")
    #     peer = peers_array[index]

    #     sck = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    #     try:
    #         sck.connect((peer.get("IP"),peer.get("PORT")))
    #         message = Message(Header.DOWNLOAD, Type.REQUEST, {"file_name": file_name, "chunk_index": chunk_index})
    #         sck.sendall(json.dumps(message.get_full_message()).encode())
            
    #         response = sck.recv(const.PACKET_SIZE).decode()
    #         sck.close()
    #         response = Message(None,None,None, response)
    #         request_thread = Thread(target=self.handle_download_response, args=(response.get_info(), request, len(peers_array)))
    #         request_thread.start()
    #         request_thread.join()
    #     except Exception as e:
    #         self.push_output(f"Error in handle_download_request: {e}")
            
    # def handle_download_response(self, response, request, peers_count):
    #     file_name = request.get("file_name")
    #     chunk_index = request.get("chunk_index")
    #     peer_index = request.get("peer_index")
    #     status = response.get("status")
    #     pieces_count = request.get("pieces_count")
    #     if status == 200:
    #         data = response.get("data")
            
    #         local_repo_path = os.getcwd()
    #         OS = platform.system()
    #         if OS == "Windows":
    #             local_repo_path = f"download_files\\"
    #         else:
    #             local_repo_path = f"download_files/"
    #         if not os.path.exists(local_repo_path): # if not have the folder
    #             os.mkdir(local_repo_path)
    #         try:
    #             download_folder = self.create_folder(local_repo_path + file_name.split(".")[0] + "_chunks")
    #             chunk_filename = f"{file_name.split('.')[0]}_chunk#{chunk_index}.txt"
                
    #             with open(download_folder + chunk_filename, "w") as fp:
    #                 fp.write(data)
    #             self.push_output(f"Download done {chunk_index}/{pieces_count}")
    #         except Exception as e: 
    #             self.push_output(f"Error in handle_download_response: {e}")
    #     else:
    #         request.update({"peer_index": (peer_index + 1) % peers_count} )
    #         self.download_mutex.acquire()
    #         self.request_block_queue.put(request)
    #         self.download_mutex.release()
            
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
    def split_file(self, file_name, chunk_size):
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
    def combine_file(self, file_name, download_slot_index):
        local_repo_path = os.getcwd()
        OS = platform.system()
        slot_download = self.slot_download_list[download_slot_index]
        hash_string = slot_download.get("hash_string")
        pieces_count = slot_download.get("pieces_count")
        if OS == "Windows":
            local_repo_path = f"download_files\\"
        else:
            local_repo_path = f"download_files/"  
        try:
            path = local_repo_path + file_name.split(".")[0] + "_chunks"
            with open(local_repo_path + file_name, "wb") as fo:
                for i in range(pieces_count):
                    chunk_filename = f"/{file_name.split('.')[0]}_chunk#{i}.txt"
                    with open(path + chunk_filename, "rb") as fi:
                        data = fi.read()
                    fo.write(data)
            with open(local_repo_path + file_name, "rb") as bigfile:
                file_content = bigfile.read()
                sha256 = hashlib.sha256()
                sha256.update(file_content)
                hash_result = sha256.hexdigest()
            if hash_string == hash_result:
                self.push_output("Combined file successful.")
            else:
                self.push_output("Combined file is having some error !")
        except Exception as e:
            self.push_output(f"Error in combine file: {e}")
    def preprocess_upload_file(self,file_name):
        try:
            hash_result = self.hash_file(file_name)
            split_info = self.split_file(file_name, CHUNK_SIZE)
            message = Message(Header.UPLOAD, Type.REQUEST, {"ID": self.client_id,"file_name": file_name, "hash_string": hash_result, "pieces_count": split_info["pieces_count"], "pieces_length": split_info["sizes"]})
            return message
        except:
            self.push_output("Pre-process file failed")
        return 1
        
    def close(self):
        if self.is_loging_in: 
            self.is_loging_in = False
            message = Message(Header.LOG_OUT, Type.REQUEST, {"ID": self.client_id})
            self.send_msg(message)
        self.is_listening = False
        self.is_printing = False
        self.p2p_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.p2p_socket.close()
        os._exit(1)

def main():
    client = Client()
    client.start()
    
if __name__ == "__main__":
    main()


