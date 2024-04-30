import tkinter as tk
from client import Client  # Thay `your_module` bằng tên module chứa class Client
import sys

class ClientControlApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Client UI")

        #Khởi tạo client
        self.client = Client()

        # Tạo một khung để chứa các thành phần của giao diện
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(padx=20, pady=20)

        # Tạo một Entry widget để nhập lệnh
        self.command_entry = tk.Entry(self.main_frame, width=50)
        self.command_entry.pack(side=tk.LEFT, padx=5)

        # Tạo một nút "Start" để bắt đầu client
        self.start_button = tk.Button(self.main_frame, text="Start", command=self.start_client)
        self.start_button.pack(side=tk.LEFT, padx=5)

        # Tạo một nút "Stop" để dừng client
        self.stop_button = tk.Button(self.main_frame, text="Stop", command=self.stop_client)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Tạo một nút "Send" để gửi lệnh từ Entry
        self.send_button = tk.Button(self.main_frame, text="Send", command=self.send_command)
        self.send_button.pack(side=tk.LEFT, padx=5)

        # Tạo một Text widget để hiển thị output từ client
        self.output_text = tk.Text(master, height=20, width=60)
        self.output_text.pack(pady=20)

        self.stdout_backup = sys.stdout
        sys.stdout = TextRedirector(self.output_text)

    def start_client(self):
        self.client.start()

    def stop_client(self):
        pass

    def send_command(self):
        command = self.command_entry.get()
        self.client.get_input(command)
        self.command_entry.delete(0, tk.END)  # Xóa nội dung trong Entry sau khi gửi lệnh

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
    app = ClientControlApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
