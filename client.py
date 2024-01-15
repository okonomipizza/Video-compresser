import json
import sys
import socket
import os


operations = ["compression", "resolution", "aspect", "sound", "convert"]

#ユーザが選択したメッソドによって最適なjsonデータを作製する
def generate_json_data_for_operation(operation, filename):

    compress_json = {
        "operation": "compression",
        "filename": filename,
    }
    resolution_json = {
        "operation": "resolution",
        "filename": filename,
        "order": "1"
    }
    aspect_json = {
        "operation": "aspect",
        "filename": filename,
        "width": 1280,
        "hight": 720
    }
    sound_json = {
        "operation": "sound",
        "filename": filename,
    }
    convert_json = {
        "operation": "convert",
        "filename": filename,
        "extension": ".mp4",
        "start": "",
        "duration": "",
    }

    json_map = {
        "compression" : compress_json,
        "resolution" : resolution_json,
        "aspect" : aspect_json,
        "sound" : sound_json,
        "convert" : convert_json
    }


    return json_map[operation]


class Socket:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = '0.0.0.0'
        self.server_port = 9001
    
    def connect(self):
        try:
            self.socket.connect((self.server_address, self.server_port))
            print(f'successfully connected{self.server_address} {self.server_port}')
        except socket.error as err:
            print(err)
            sys.exit(1)
    
    def multiple_media_protocol_header(self, json_size, media_type_size, payload_size):
        return json_size.to_bytes(16, "big") + media_type_size.to_bytes(1, "big") + payload_size.to_bytes(47, "big")
    
   

    
    def run(self):
        #ユーザから必要な情報を受け取る
        operation = get_operation()
        filepath, filename, media_type = get_filepath()
        print(f"operation: {operation}")
        print(f"filepath: {filepath}")
        print(f"filename: {filename}")
        print(f"media type: {media_type}")
        #ユーザが実行したい操作に応じて適切なjsonデータを作製
        operation_dict = generate_json_data_for_operation(operation, filename)
        #追加で引数が必要なときはさらにユーザから入力を受ける
        if operation == "resolution":
            operation_dict["order"] = get_resolution()
        elif operation == "aspect":
            width, height = get_aspect()
            operation_dict["width"] = width
            operation_dict["height"] = height
        elif operation == "convert":
            operation_dict["extension"] = get_convert_filetype()
            start, duration = get_time()
            operation_dict["start"] = start
            operation_dict["duration"] = duration
        

        try:
            #サーバへのリクエストを送信
            with open(filepath, 'rb') as f:
                #ファイルサイズを調べる
                f.seek(0, os.SEEK_END)
                filesize = f.tell()
                f.seek(0, 0)
                #ファイルサイズが大きすぎる場合はエラー
                if filesize > pow(2, 47):
                    raise Exception('File must be below 4GB.')

                #jsonのfilenameを更新
                operation_dict["filename"] = filename
                arg_dict_json = json.dumps(operation_dict)

                print(f"filesize: {filesize}")
                
                print('sending data...')
                #headerの作製と送信
                header = self.multiple_media_protocol_header(len(arg_dict_json.encode('utf-8')), len(media_type.encode('utf-8')), filesize)
                self.socket.send(header)

                #操作を記述したjsonファイルファイルを送信
                self.socket.send(arg_dict_json.encode('utf-8'))
                #メディアタイプを送信
                self.socket.send(media_type.encode('utf-8'))
                #動画ファイルを送信
                stream_rate = 1400 #パケットの最大サイズ
                data = f.read(stream_rate)
                while data:
                    print("Senging...")
                    self.socket.send(data)
                    data = f.read(stream_rate)
                
                print('sending has finished')
            

            #サーバからのレスポンスを受信
            header = self.socket.recv(64)
            #headerからデータを読み取る
            json_size = int.from_bytes(header[:16], "big")
            media_type_size = int.from_bytes(header[16:17], "big")
            file_size = int.from_bytes(header[17:64], "big")
            print(f"file_size: {file_size}")

            stream_rate = 1400 #パケットの最大サイズ

            response_json = self.socket.recv(json_size).decode('utf-8')
            response_dict = json.loads(response_json)
            media_type = self.socket.recv(media_type_size).decode('utf-8')

            filename = response_dict["filename"]

            print(f"filename: {filename}")
            print(f"media type: {media_type}")

            if file_size == 0:
                raise Exception('No data to read from server.')

            #サーバから受信したファイルを一時保管ディレクトリに書き出す
            dpath = "response"
            with open(os.path.join(dpath, filename + media_type), 'wb+') as f:
                while file_size > 0:
                    data = self.socket.recv(file_size if file_size <= stream_rate else stream_rate)
                    f.write(data)
                    print(f'received {len(data)} bytes')
                    file_size -= len(data)
                    print(file_size)

            
            print('Finished downloading the file from server')
        
        finally:
            print('closing socket')
            self.socket.close()

def get_operation():
    operation = ""
    while True:
        operation = input('Type in operation: ')
        if operation in operations:
            break
        else:
            print('invalid operation')
    return operation

def split_filename_media_type(filename):
    parts = filename.rsplit('.', 1)
    if len(parts) > 1:
        #拡張子が存在する場合
        name = parts[0]
        media_type = parts[1]
        return name, media_type
    else:
        #拡張子が存在しない場合
        return filename, None

def get_filepath():
    filepath = ""
    filename = ""
    media_type = ""
    while True:
        filepath = input('Type in filepath: ')
        filename, media_type = split_filename_media_type(filepath)
        if os.path.exists(filepath) and media_type == "mp4":
            return filepath, filename, media_type
        else:
            print('file does not exist or file type is not .mp4')

def get_resolution():
    userinput = 0
    while True:
        userinput = input('Choose resolution: HD -> 1,  FullHD -> 2')
        if userinput == "1":
            break
        elif userinput == "2":
            break
    return userinput

def get_aspect():
    width = 0
    height = 0
    while True:
        try:
            width = int(input('Type in width: '))
            height = int(input('Type in height: '))
            break
        except ValueError:
            print('Type in integer')
    
    return width, height

def get_convert_filetype():
    extension = ""
    while True:
        value = input('Choose video type: GIF -> 1, WEBM -> 2')
        if value == "1":
            extension = ".gif"
            break
        elif value == "2":
            extension = ".webm"
            break
    return extension

def get_time():
    start = input('Type in start time (00:00:00): ')
    duration = input('Type in duration (ex: 10 (s)): ')
    return start, duration



# print(f"you chose {request_operation}")

def main():
    socket = Socket()
    socket.connect()
    socket.run()

    


if __name__ == "__main__":
    main()

