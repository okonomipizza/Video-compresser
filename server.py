from audioop import mul
from concurrent.futures import thread
import socket
import os
import subprocess
import json
import time


#通使用プロトコル
def multiple_media_protocol_header(json_size, media_type_size, payload_size):
        return json_size.to_bytes(16, "big") + media_type_size.to_bytes(1, "big") + payload_size.to_bytes(47, "big")

#ffmpegの処理を行うための関数
def get_ffmpeg_func(methodname):

    def compress_video(input_filename, output_filename):
        media_type = ".mp4"


        input_file = input_filename + media_type
        output_file = os.path.join('temp', output_filename + media_type)
        try:
            cmd = ['ffmpeg', '-i', input_file, '-c:v', 'libx264', '-crf', '40', '-c:a', 'aac', '-b:a', '128k', output_file]
            subprocess.run(cmd, check=True)
            print('video has compressed')
        except subprocess.CalledProcessError as err:
            print("Convert Error occured ", err)
            
        return media_type
    
    def change_resolution(input_filename, output_filename, resolution):
        media_type = ".mp4"
        input_file = input_filename + media_type
        output_file = os.path.join('temp', output_filename + media_type)
        #resolution 1->720, 2->1080
        
        width = 1280
        height = 720
        if resolution == "2":
            width = 1920
            height = 1080
        try:
            scale = str(width) + "x" + str(height)
            cmd = ['ffmpeg', '-i', input_file, '-s', scale, output_file]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as err:
            print("Convert Error occured ", err)
        return media_type
    
    def change_aspect_ratio(input_filename, output_filename, width, height):
        media_type = ".mp4"
        input_file = input_filename + media_type
        output_file = os.path.join('temp', output_filename + media_type)
        aspect_ratio = "scale=" + str(width) + ":" + str(height)

        try:
            cmd = ['ffmpeg', '-i', input_file, '-vf', aspect_ratio, output_file]
            subprocess.run(cmd, check=True)
            print('video has compressed')
        except subprocess.CalledProcessError as err:
            print("Convert Error occured ", err)
        
        return media_type

    def extract_sound(input_filename, output_filename):
        input_media_type = ".mp4"
        output_media_type = ".mp3"
        input_file = input_filename + input_media_type
        output_file = os.path.join('temp', output_filename + output_media_type)
        try:
            cmd = ['ffmpeg', '-i', input_file, '-vn', output_file]
            subprocess.run(cmd, check=True)
            print('sound has extracted')
        except subprocess.CalledProcessError as err:
            print("Convert Error occured ", err)

        return output_media_type

    def convert(input_filename, output_filename, extension, start, duration):
        input_media_type = ".mp4"
        
        input_file = input_filename + input_media_type
        output_file = os.path.join('temp', output_filename + extension)
        cmd = []
        try:
            if extension == ".gif":
                cmd = ['ffmpeg', '-i', input_file, '-ss', start, '-t', duration, '-vf', 'fps=24', output_file]
            elif extension == ".webm":
                cmd = ['ffmpeg', '-i', input_file, '-ss', start, '-t', duration, '-c:v', 'libvpx', '-crf', '10', '-b:v', '1M', '-c:a', 'libvorbis', output_file]

            subprocess.run(cmd, check=True)
            print('sound has extracted')
        except subprocess.CalledProcessError as err:
            print("Convert Error occured ", err)

        return extension
        
    
    func_map = {
        "compression" : compress_video,
        "resolution" : change_resolution,
        "aspect" : change_aspect_ratio,
        "sound" : extract_sound,
        "convert" : convert
    }

    return func_map[methodname]


def main():
    #クライアントから受信したファイルを格納するためのディレクトリを作製
    dpath = 'temp'
    if not os.path.exists(dpath):
        os.makedirs(dpath)
    
    #ソケットを作製
    SERVER_ADDRESS = '0.0.0.0'
    SERVER_PORT = 9001

    print(f'Starting up on {SERVER_ADDRESS} {SERVER_PORT}')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((SERVER_ADDRESS, SERVER_PORT))
    sock.listen(1)
    global data_processing_status
    while True:
        connection, client_address = sock.accept()
        try:
            print(f'connection from {client_address}')

            header = connection.recv(64)

            #headerから情報を読み取る
            json_size = int.from_bytes(header[:16], "big")
            media_type_size = int.from_bytes(header[16:17], "big")
            file_size = int.from_bytes(header[17:64], "big")
            
            #bodyからデータを読み取る
            operation_json = connection.recv(json_size).decode('utf-8')
            operation_dict = json.loads(operation_json)
            operation = operation_dict["operation"]
            filename = operation_dict["filename"]
            media_type = connection.recv(media_type_size).decode('utf-8')

            print(f"operation: {operation}")
            print(f"filename: {filename}")
            print(f"media type: {media_type}")
            print(f"file_size: {file_size}")


            if file_size == 0:
                raise Exception('No data to read from client.')

            stream_rate = 1400 #パケットの最大サイズ

            #ユーザから受信したファイルを一時保管ディレクトリに書き出す
            filepath = filename + "." + media_type
            with open(os.path.join(dpath, filepath), 'wb+') as f:
                while file_size > 0:
                    data = connection.recv(file_size if file_size <= stream_rate else stream_rate)
                    f.write(data)
                    print(f'received {len(data)} bytes')
                    file_size -= len(data)

                print('Finished downloading the file from client')
            
            #operationに応じてファイルを操作
            func = get_ffmpeg_func(operation)
            output_filename = "processed-" + filename
            
            media_type = ""
            if operation == "compression":
                media_type = func(filename, output_filename)
            elif operation == "resolution":
                print(f'order: {operation_dict["order"]}')
                media_type = func(filename, output_filename, operation_dict["order"])
            elif operation == "aspect":
                media_type = func(filename, output_filename, operation_dict["width"], operation_dict["height"])
            elif operation == "sound":
                media_type = func(filename, output_filename)
            elif operation == "convert":
                media_type = func(filename, output_filename, operation_dict["extension"], operation_dict["start"], operation_dict["duration"])


            output_file = output_filename + media_type
            print(f"output_filepath: {output_file}")


            #tempに生成されたoutputファイルをユーザに送信
            with open(os.path.join(dpath, output_file), 'rb') as f:
                #ファイルサイズを調べる
                f.seek(0, os.SEEK_END)
                filesize = f.tell()
                f.seek(0, 0)
                print(f"filesize: {filesize}")

                #response用のjsonを作製
                response_data = {
                    "filename": output_filename,
                    "media_type": media_type,
                }

                response_json = json.dumps(response_data)
                header = multiple_media_protocol_header(len(response_json.encode('utf-8')), len(media_type.encode('utf-8')), filesize)

                print('sending data...')
                #responseを送信
                connection.sendall(header)
                connection.sendall(response_json.encode('utf-8'))
                connection.sendall(media_type.encode('utf-8'))

                #動画ファイルを送信
                stream_rate = 1400 #パケットの最大サイズ
                data = f.read(stream_rate)
                while data:
                    print("Senging...")
                    connection.sendall(data)
                    data = f.read(stream_rate)
                
                print('sending has finished')


            #tempディレクトリを空にする
            os.remove(os.path.join(dpath, filepath))
            os.remove(os.path.join(dpath, output_file))

            

        except Exception as e:
            print('Error: ' + str(e))

        finally:
            print("Closing current connection")
            connection.close()  


if __name__ == "__main__":
    main()
