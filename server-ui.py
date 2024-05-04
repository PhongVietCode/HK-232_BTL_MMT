import tkinter as tk
from tkinter import *
import re
from threading import Thread, Lock
import time
import sys
from server import Server
import json

class Server_UI(tk.Tk):
    def __init__(self):
        # create root window
        super().__init__()
        
        self.title("Server File Sharing Application")
        self.minsize(500,550)
        self.server = None
        self.server = Server()
        self.server.start()
        self.current_frame = self.main_frame()
        self.current_frame.pack()

    def main_frame(self):
        frame = tk.Frame()
        
        # =========
        label = tk.Label(frame, text="File Sharing Application (Server)", font=("Sans Serif", 20, "bold"))
        # =========
        label.grid(row=0,column = 0,columnspan=2, sticky="ns")
        
        terminal_frame = self.terminal_frame(frame)
        terminal_frame.grid(row=1, column=0, sticky='w')
        
        info_frame = tk.Frame(frame)
        info_frame.grid(row=1, column=1)
        client_container = self.client_container(info_frame)
        file_container = self.file_container(info_frame)
        
        client_container.grid(row=0, column=0)
        file_container.grid(row=1, column=0)

        return frame
    def terminal_frame(self, p_frame):
        frame = tk.Frame(p_frame)
        terminal_text = tk.Text(frame, bg='black', padx=10, pady=10, width=40, height=40)
        terminal_text.tag_configure("color", foreground="white")
        terminal_text.config(state = tk.DISABLED)
        terminal_text.grid(row=0, column=0)
        t = Thread(target=self.print_output, args=(terminal_text, 1))
        t.start()
        return frame

    def print_output(self, frame, number):
        if not self.server:
            return
        while self.server.is_printing:
            output = self.server.get_output()
            if output:
                frame.config(state = tk.NORMAL)
                frame.insert(tk.END, output, "color")
                frame.insert(tk.END, '\n', "color")
                
                frame.see(tk.END)
                frame.config(state = tk.DISABLED)
    def client_container(self, p_frame):
        frame = tk.Frame(p_frame)
        text_frame = tk.Text(frame,width=30, height=20)
        text_frame.pack()
        t = Thread(target=self.update_client, args=(text_frame, 1))
        t.start()
        return frame
    def update_client(self, frame, number):
        old_data = self.server.file_data['clients']
        formatted_data = json.dumps(old_data, indent = 4)
        frame.insert(tk.END, formatted_data)
        while True:
            if not self.server.is_printing: 
                break
            new_data = self.server.file_data['clients']
            if new_data != old_data:
                frame.config(state=NORMAL)
                frame.delete('1.0', tk.END)
                old_data = new_data
                formatted_data = json.dumps(new_data, indent = 4)
                frame.insert(tk.END, formatted_data)
                frame.config(state=DISABLED)
                
            
    def file_container(self, p_frame):
        frame = tk.Frame(p_frame)
        text_frame = tk.Text(frame,width=30, height=20)
        text_frame.pack()
        t = Thread(target=self.update_file, args=(text_frame,1))
        t.start()
        return frame
    def update_file(self, frame, number):
        old_data = self.server.file_data['files']
        formatted_data = json.dumps(old_data, indent = 4)
        frame.insert(tk.END, formatted_data)
        while True:
            if not self.server.is_printing: 
                break
            new_data = self.server.file_data['files']
            if new_data != old_data:
                frame.config(state=NORMAL)
                frame.delete('1.0', tk.END)
                old_data = new_data
                formatted_data = json.dumps(new_data, indent = 4)
                frame.insert(tk.END, formatted_data)
                frame.config(state=DISABLED)
    def close(self):
        if self.server:
            self.server.close()
        self.destroy()
def main():
    app = Server_UI()
    app.protocol("WM_DELETE_WINDOW", app.close)
    app.mainloop()

if __name__ == "__main__":
    main()