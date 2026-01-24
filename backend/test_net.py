
import socket
import sys

def test_socket(host, port):
    print(f"Testing connection to {host}:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((host, port))
        print("Success!")
        s.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_socket('127.0.0.1', 5432)
    test_socket('localhost', 5432)
