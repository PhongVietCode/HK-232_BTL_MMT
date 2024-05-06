import tkinter as tk
from tkinter import *
from tkinter import ttk
import re
import sys
from threading import Thread, Lock
from client import Client
from queue import Queue
import os
import time
import math
import const


class Client_UI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.client = Client()
        self.client.start()
        self.title("Client File Sharing Application")
        self.minsize(750,550)
        
        self.current_frame = None
        self.terminal_text = None
        self.download_window = None
        # self.local_repo_frame = None
        # self.download_repo_frame = None
        # self.client_response_frame = None
        self.thread_list = []
        self.downloading_files = []
        self.user_inp = tk.StringVar()
        self.thread_print_output = None
        self.current_frame = self.main_frame()
        self.current_frame.pack()
    def main_frame(self):
        
        frame = tk.Frame()
        
        # =========
        label = tk.Label(frame, text=f"File Sharing Application (Client {self.client.client_id})", font=("Sans Serif", 20, "bold"))
        # =========
        left_frame = tk.Frame(frame)
        
        terminal = self.terminal(left_frame)
        statistic_frame = self.statistic(left_frame)
        
        terminal.grid(row=0,column = 0,sticky="w")
        statistic_frame.grid(row=1, column=0,columnspan=2,sticky=tk.EW, padx=10, pady=5)
        # =========
        folder = self.folder(frame)
    
        left_frame.grid(row=1,column=0,sticky="w")    
        label.grid(row=0,column = 0, columnspan=2, sticky='ns')
        folder.grid(row=1,column = 1, sticky="ns")
        
        return frame
    def statistic(self, parent_frame):
        statistic_frame = tk.LabelFrame(parent_frame,text="Download files", font=('Sans serif', 14, 'bold'))
        download_list_frame = tk.Frame(statistic_frame)
        cv = tk.Canvas(download_list_frame, width=400,height=100)
        cv.grid(row=0, column= 0, sticky=tk.E)
        download_list_frame.grid(row=0, column=0)
        
        throughput_statistic_frame = tk.Frame(statistic_frame)
        
        # l1 = tk.Label(throughput_statistic_frame, text="Upload speed: ",font=('Sans Serif', 12, 'bold'))
        # upload_speed = tk.Label(throughput_statistic_frame, text="123Kb/s", font=('Sans Serif', 14, 'normal'))
        l2 = tk.Label(throughput_statistic_frame, text="Download speed: ",font=('Sans Serif', 12, 'bold'))
        download_speed = tk.Label(throughput_statistic_frame, text="10Kb/s", font=('Sans Serif', 14, 'normal'))
        download_speed_thread = Thread(target=self.ds_thread, args=(download_speed,1))
        download_speed_thread.start()

        # l1.grid(row=0, column=0,sticky="w")
        # upload_speed.grid(row=1, column=0, sticky="w")
        l2.grid(row=2, column=0,sticky="w")
        download_speed.grid(row=3, column=0,sticky="w")
        
        throughput_statistic_frame.grid(row=0, column=1, sticky='ne')
        
        self.download_window = cv
        thrd = Thread(target=self.check_dowloading_files, args=())
        thrd.start()
        return statistic_frame
    def ds_thread(self, container, number):

        if self.client.download_speed == 0:
            old_speed = 0
        else:
            old_speed = const.CHUNK_SIZE/self.client.download_speed
        old_speed = math.floor(old_speed)
        container.config(text = f'{old_speed}b/s')
        while self.client.is_printing:
            if self.client.download_speed == 0:
                current_speed = 0
            else:
                current_speed = const.CHUNK_SIZE/self.client.download_speed
            if old_speed != current_speed:
                old_speed = current_speed
                container.config(text = f'{math.floor(current_speed)}b/s')
    def check_dowloading_files(self):
        while self.client.is_printing:
            keys = list(self.client.slot_download_list.keys())
            for file_name in keys:
                if file_name not in self.downloading_files:
                    self.downloading_files.append(file_name)
                    thrd = Thread(target=self.download_file_item, args=(file_name,1))
                    thrd.start()
    
    def download_file_item(self,file_name, number):
        file_info = self.client.slot_download_list.get(file_name)
        if not file_info: return
        total_chunks = file_info.get('pieces_count')
        downloaded_chunks = file_info.get('downloaded_chunks')
        
        item_frame = tk.Frame(self.download_window)                
        label = tk.Label(item_frame, text=file_name, font=('Sans Serif', 12, 'bold'))
        
        pb = ttk.Progressbar(item_frame,orient='horizontal', mode='determinate', length=200)
        pct = tk.Label(item_frame, text=f"--%", font=('Sans Serif', 12, 'bold'))
        
        label.grid(row=0, column=0)
        pb.grid(row=0, column=1, padx=10, pady=20)
        pct.grid(row=0, column=2)
        
        item_frame.pack(expand=True, fill=tk.X, padx=10, side=tk.BOTTOM)
        track_thread = Thread(target=self.track_file_percentage, args=(item_frame, pb, pct, file_info))    
        track_thread.start()
        self.thread_list.append(track_thread)
    def track_file_percentage(self,item_frame, pb,pct, file_info):
        chunks = file_info['downloaded_chunks']
        max_chunks = file_info['pieces_count']
        while chunks <= max_chunks - 1:
            chunks = file_info['downloaded_chunks']
            pct_num = math.floor(chunks*100/max_chunks)
            pb['value'] = pct_num
            pct.config(text=f'{pct_num}%')
        self.downloading_files.remove(file_info['file_name'])
        item_frame.destroy()
            
    def folder_info(self, folder_name, text_frame):
        files = os.listdir(folder_name)
        oldFiles = None
        while self.client.is_listening:
            files = os.listdir(folder_name)
            if oldFiles != files:
                text_frame.config(state = tk.NORMAL)
                text_frame.delete('1.0', tk.END)
                oldFiles = files
                for f in files:
                    text_frame.insert(tk.END, f ,"color")
                    text_frame.insert(tk.END, '\n' ,"color")
                    # text_frame.see(tk.END)
                    time.sleep(0.2)
                text_frame.config(state = tk.DISABLED)
        
    def folder(self, parent_frame):
        folder_frame = tk.Frame(parent_frame)
        
        label1, local_repo_frame = self.square_container(folder_frame, "Local Repo")
        # label2, download_repo_frame = self.square_container(folder_frame, "Downloaded Repo")
        label3, reply_frame = self.square_container(folder_frame, "Response Client")
        reply_frame.insert(tk.END, "Client is listening...", 'output_color')
        reply_frame.config(bg='black')
        replyThread = Thread(target=self.client_reply, args=(reply_frame,1))
        self.thread_list.append(replyThread)
        replyThread.start()
        
        localRep = Thread(target=self.folder_info, args=(self.client.local_file_folder, local_repo_frame))
        self.thread_list.append(localRep)
        localRep.start()
        # downloadRep = Thread(target=self.folder_info, args=(self.client.create_folder("download_files"), download_repo_frame))
        # self.thread_list.append(downloadRep)
        # downloadRep.start()
        
        label1.grid(row=0, column=0, sticky="w")
        local_repo_frame.grid(column=0, row=1, sticky="w")
        # label2.grid(column=0, row=2, sticky="w")
        # download_repo_frame.grid(column=0, row=3, sticky="w")
        label3.grid(column=0, row=2, sticky="w")
        reply_frame.grid(column=0, row=4, sticky="w")
        
        return folder_frame
    def client_reply(self, frame, number):
        if not self.client:
            return
        while self.client.is_printing:
            output = self.client.print_client_output()
            if output:
                frame.config(state = NORMAL)
                frame.insert(tk.END, output, "output_color")
                frame.insert(tk.END, '\n', "output_color")
                
                frame.see(tk.END)
                frame.config(state=DISABLED)
    def square_container(self, frame, label):
        title = tk.Label(frame, text=label, font=("Sans Serif", 14, "bold"))
        frame = tk.Text(frame,width=30, height=10, bd=2)
        frame.tag_configure("color",foreground="black")
        frame.tag_configure("output_color",foreground="white")
        return title, frame
    def terminal(self, parent_frame):
        terminal_frame = tk.Frame(parent_frame)
        
        self.terminal_text = tk.Text(terminal_frame,bg='black', padx=10, pady=10)
        self.terminal_text.tag_configure("output_color",foreground="white")
        self.terminal_text.tag_configure("input_color",foreground="yellow")
        self.terminal_text.insert(tk.END, "Terminal [Version 1.0.0]\nCopyright (C) quocphong. All right reserved.\n", "output_color")
        self.terminal_text.config(state = tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(terminal_frame, orient='vertical', command=self.terminal_text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        
        self.terminal_text['yscrollcommand'] = scrollbar.set
        
        self.thread_print_output = Thread(target=self.show_output, args=())
        self.thread_list.append(self.thread_print_output)
        self.thread_print_output.start()
        
        input_field = tk.Entry(terminal_frame,  textvariable=self.user_inp, font=('Sans Serif', 12 , 'normal'), bg='black', fg='white', width=72)
        input_field.bind('<Return>', lambda event: self.execute_command(input_field))
        self.terminal_text.grid(row=0, column=0)
        input_field.grid(row = 1, column = 0, sticky="w")
        
        return terminal_frame
    
    def execute_command(self, input_field):
        command = input_field.get()
        if not self.client:
            return
        if command == 'clear':
            self.terminal_text.config(state = tk.NORMAL)
            self.terminal_text.delete('1.0', tk.END)
            self.terminal_text.insert(tk.END, "Terminal [Version 1.0.0]\nCopyright (C) quocphong. All right reserved.\n", "output_color")
            self.terminal_text.config(state = tk.DISABLED)
        elif len(command) != 0:
            self.client.get_input(command)
            self.insert_command(f">> {command}", "input_color")
        input_field.delete(0, tk.END)

    def show_output(self):
        if not self.client:
            return
        while self.client.is_printing:
            output = self.client.print_output()
            if output:
                self.insert_command(output, "output_color")
    def insert_command(self, content, color):
        self.terminal_text.config(state = tk.NORMAL)
        self.terminal_text.insert(tk.END, content,color)
        self.terminal_text.insert(tk.END, '\n',color)
        self.terminal_text.see(tk.END)
        self.terminal_text.config(state = tk.DISABLED)
    
    def navigate(self, frame):
        self.current_frame.pack_forget()
        self.curent_frame = frame() 
        self.current_frame.pack()
    def close(self):
        if self.client:
            self.client.close()
        # for thread in self.thread_list:
        #     if thread:
        #         thread.join()
        self.destroy()
        
def main():
    app = Client_UI()
    app.protocol("WM_DELETE_WINDOW", app.close)
    app.mainloop()

if __name__ == "__main__":
    main()