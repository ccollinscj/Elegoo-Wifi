import socket
import requests
import json
import hashlib
import os
import uuid
import time
import websocket
import tkinter as tk
from tkinter import filedialog, messagebox

class PrinterUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("3D Printer File Uploader")
        self.file_path = None
        self.mainboard_ip = None
        self.mainboard_id = None
        self.uploaded_filename = None

        # Create GUI components
        self.create_widgets()

    def create_widgets(self):
        # Printer discovery button at the top
        self.discover_button = tk.Button(self.root, text="Discover Printer", command=self.discover_printer)
        self.discover_button.pack(pady=10)

        # File selection button
        self.file_button = tk.Button(self.root, text="Select File", command=self.select_file)
        self.file_button.pack(pady=10)

        # Label to show the selected file
        self.file_label = tk.Label(self.root, text="No file selected")
        self.file_label.pack(pady=10)

        # Upload button
        self.upload_button = tk.Button(self.root, text="Upload File", command=self.upload_file, state=tk.DISABLED)
        self.upload_button.pack(pady=10)

        # Print button
        self.print_button = tk.Button(self.root, text="Submit for Print", command=self.submit_for_print, state=tk.DISABLED)
        self.print_button.pack(pady=10)

        # Exit button at the bottom
        self.exit_button = tk.Button(self.root, text="Exit", command=self.root.quit)
        self.exit_button.pack(side=tk.BOTTOM, pady=10)

    def select_file(self):
        self.file_path = filedialog.askopenfilename()
        if self.file_path:
            self.file_label.config(text=f"Selected file: {os.path.basename(self.file_path)}")
            if self.mainboard_ip:
                self.upload_button.config(state=tk.NORMAL)

    def discover_printer(self):
        broadcast_message = "M99999"
        udp_ip = "255.255.255.255"
        udp_port = 3000

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(broadcast_message.encode(), (udp_ip, udp_port))

        sock.settimeout(5)
        try:
            data, addr = sock.recvfrom(1024)
            response = json.loads(data.decode())
            self.mainboard_ip = response['Data']['MainboardIP']
            self.mainboard_id = response['Data']['MainboardID']
            messagebox.showinfo("Printer Found", f"Printer found: IP={self.mainboard_ip}")
            if self.file_path:
                self.upload_button.config(state=tk.NORMAL)
        except socket.timeout:
            messagebox.showerror("Error", "No printer found.")
            self.mainboard_ip = None
            self.upload_button.config(state=tk.DISABLED)

    def upload_file(self):
        if not self.file_path or not self.mainboard_ip:
            messagebox.showerror("Error", "No file selected or printer not found.")
            return
        
        url = f"http://{self.mainboard_ip}:3030/uploadFile/upload"
        
        # Calculate MD5 hash of the file
        md5_hash = hashlib.md5()
        with open(self.file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        file_md5 = md5_hash.hexdigest()
        
        file_size = os.path.getsize(self.file_path)
        file_uuid = str(uuid.uuid4()).replace('-', '')  # Generate a unique UUID
        self.uploaded_filename = os.path.basename(self.file_path)  # Get the original filename
        
        with open(self.file_path, "rb") as file:
            files = {'File': (self.uploaded_filename, file, 'application/octet-stream')}
            headers = {
                'S-File-MD5': file_md5,
                'Check': '1',
                'Offset': '0',  # Always 0 since we're not chunking
                'Uuid': file_uuid,
                'TotalSize': str(file_size)
            }
            
            response = requests.post(url, headers=headers, files=files)
            result = response.json()
            
            if result.get('code') == "000000":
                messagebox.showinfo("Success", f"File '{self.uploaded_filename}' uploaded successfully.")
                self.print_button.config(state=tk.NORMAL)
                self.get_file_list()  # Retrieve file list after upload
            else:
                messagebox.showerror("Error", f"Failed to upload file '{self.uploaded_filename}', Error: {result.get('messages')}")
                self.print_button.config(state=tk.DISABLED)

    def get_file_list(self):
        if not self.mainboard_ip:
            messagebox.showerror("Error", "Printer not found.")
            return

        ws_url = f"ws://{self.mainboard_ip}:3030/websocket"
        ws = websocket.create_connection(ws_url)

        # Command to retrieve file list
        file_list_command = {
            "Id": str(uuid.uuid4()).replace('-', ''),
            "Data": {
                "Cmd": 258,  # Command to retrieve file list
                "Data": {
                    "Url": "/local/"  # Assuming the file is stored in the local storage
                },
                "RequestID": self.mainboard_id,
                "MainboardID": self.mainboard_id,
                "TimeStamp": int(time.time()),
                "From": 0  # Source identification (0 = Local PC Software)
            },
            "Topic": f"sdcp/request/{self.mainboard_id}"
        }

        ws.send(json.dumps(file_list_command))
        response = json.loads(ws.recv())
        ws.close()

        # Debug: Print the entire response for inspection
        print("File list response from printer:", response)

        # Extract the uploaded filename from the file list
        files = response.get('Data', {}).get('Data', {}).get('FileList', [])
        if files:
            # Assume the first file in the list is the one we uploaded
            self.uploaded_filename = files[0]['name']
            print(f"Updated filename on printer: {self.uploaded_filename}")
        else:
            messagebox.showerror("Error", "Uploaded file not found on printer.")
            self.uploaded_filename = None

    def submit_for_print(self):
        if not self.uploaded_filename or not self.mainboard_ip:
            messagebox.showerror("Error", "No file uploaded or printer not found.")
            return

        ws_url = f"ws://{self.mainboard_ip}:3030/websocket"
        ws = websocket.create_connection(ws_url)

        # Create the start print command
        start_print_command = {
            "Id": str(uuid.uuid4()).replace('-', ''),
            "Data": {
                "Cmd": 128,  # Start printing command
                "Data": {
                    "Filename": self.uploaded_filename,  # Use the filename as it is on the printer
                    "StartLayer": 0  # Start from the first layer
                },
                "RequestID": self.mainboard_id,
                "MainboardID": self.mainboard_id,
                "TimeStamp": int(time.time()),
                "From": 0  # Source identification (0 = Local PC Software)
            },
            "Topic": f"sdcp/request/{self.mainboard_id}"
        }

        ws.send(json.dumps(start_print_command))
        response = json.loads(ws.recv())
        ws.close()

        # Debug: Print the entire response for inspection
        print("Response from printer:", response)

        # Correctly access the 'Ack' key
        ack = response.get('Data', {}).get('Data', {}).get('Ack')
        
        # Interpret the Ack code
        if ack is not None:
            if ack == 0:
                messagebox.showinfo("Success", f"Printing started for '{self.uploaded_filename}'.")
            elif ack == 1:
                messagebox.showerror("Error", "Printer is busy. Try again later.")
            elif ack == 2:
                messagebox.showerror("Error", "File not found on the printer. Please verify the file upload.")
            elif ack == 3:
                messagebox.showerror("Error", "MD5 verification failed. The file may be corrupted.")
            elif ack == 4:
                messagebox.showerror("Error", "File read failed on the printer. Check the printer's storage.")
            elif ack == 5:
                messagebox.showerror("Error", "Resolution mismatch. The file resolution is not compatible with the printer.")
            elif ack == 6:
                messagebox.showerror("Error", "Unknown file format. The file type is not supported.")
            elif ack == 7:
                messagebox.showerror("Error", "Machine model mismatch. The file is not compatible with this printer.")
            else:
                messagebox.showerror("Error", f"Unknown error occurred. Ack code: {ack}")
        else:
            messagebox.showerror("Error", "Unexpected response from printer: 'Ack' not found.")

# Main function to run the application
def main():
    root = tk.Tk()
    app = PrinterUploaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
