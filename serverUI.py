import tkinter as tk
from threading import Thread
from server import Server  # Đảm bảo rằng bạn có class Server trong module server
import sys

class ServerControlApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Server Control App")

        # Khởi tạo đối tượng Server
        self.server = Server(8003)

        # Frame chứa các thành phần giao diện
        self.control_frame = tk.Frame(self.master, padx=20, pady=20)
        self.control_frame.pack()

        # Button bắt đầu server
        self.start_button = tk.Button(self.control_frame, text="Start Server", command=self.start_server)
        self.start_button.grid(row=0, column=0, padx=10, pady=10)

        # Button dừng server
        self.stop_button = tk.Button(self.control_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=10, pady=10)

        # Text widget để hiển thị thông tin từ server
        self.text_output = tk.Text(self.master, height=15, width=50)
        self.text_output.pack(padx=20, pady=20)

        # Redirect stdout để hiển thị output từ server vào text widget
        self.stdout_backup = sys.stdout
        sys.stdout = TextRedirector(self.text_output)

    def start_server(self):
        self.server.start()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.text_output.insert(tk.END, "Server started.\n")

    def stop_server(self):
        self.server.close()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.text_output.insert(tk.END, "Server stopped.\n")

class TextRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, s):
        self.text_widget.insert(tk.END, s)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

def main():
    root = tk.Tk()
    app = ServerControlApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
