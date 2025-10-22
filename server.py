import sys
import socket
import threading
import os
import argparse
import mimetypes
from datetime import datetime, timezone

SERVER_NAME = "NikkiGorskiServer/1.0"


def http_date():
    return datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')


class HTTPWorker(threading.Thread):
    def __init__(self, clientsocket, address, docroot):
        super().__init__()
        self.clientsocket = clientsocket
        self.address = address
        self.docroot = docroot

    def run(self):
        try:
            request = self._recv_request()
            if not request:
                self.clientsocket.close()
                return
            method, path, version = self._parse_request_line(request)
            if method != 'GET':
                self._send_response(405, b'Method Not Allowed', 'text/plain')
                return
            fullpath = os.path.normpath(os.path.join(self.docroot, path.lstrip('/')))
            if not fullpath.startswith(os.path.abspath(self.docroot)):
                self._send_response(404, b'Not Found', 'text/plain')
                return
            if os.path.isdir(fullpath):
                index = os.path.join(fullpath, 'index.html')
                if os.path.exists(index):
                    fullpath = index
                else:
                    self._send_response(404, b'Not Found', 'text/plain')
                    return
            if not os.path.exists(fullpath):
                self._send_response(404, b'Not Found', 'text/plain')
                return
            with open(fullpath, 'rb') as f:
                body = f.read()
            ctype, _ = mimetypes.guess_type(fullpath)
            if ctype is None:
                ctype = 'application/octet-stream'
            self._send_response(200, body, ctype)
        except Exception as e:
            try:
                self._send_response(500, b'Internal Server Error', 'text/plain')
            except Exception:
                pass
        finally:
            try:
                self.clientsocket.close()
            except Exception:
                pass

    def _recv_request(self):
        data = b''
        self.clientsocket.settimeout(2.0)
        try:
            while b'\r\n\r\n' not in data:
                chunk = self.clientsocket.recv(1024)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        except Exception:
            return None
        return data.decode('iso-8859-1') if data else ''

    def _parse_request_line(self, request_text):
        lines = request_text.split('\r\n')
        if len(lines) == 0 or lines[0] == '':
            raise ValueError('Empty request')
        parts = lines[0].split()
        if len(parts) < 3:
            raise ValueError('Invalid request line format')
        return parts[0], parts[1], parts[2]

    def _send_response(self, status_code, body, content_type):
        reason = {200: 'OK', 404: 'Not Found', 500: 'Internal Server Error', 405: 'Method Not Allowed'}.get(status_code, 'OK')
        if isinstance(body, str):
            body = body.encode('utf-8')
        header_lines = []
        header_lines.append(f'HTTP/1.1 {status_code} {reason}')
        header_lines.append(f'Date: {http_date()}')
        header_lines.append(f'Server: {SERVER_NAME}')
        header_lines.append(f'Content-Type: {content_type}')
        header_lines.append(f'Content-Length: {len(body)}')
        header_lines.append('\r\n')
        header = '\r\n'.join(header_lines).encode('utf-8')
        self.clientsocket.sendall(header + body)


def run_server(port, docroot):
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(('0.0.0.0', port))
    serversocket.listen(5)
    print(f'Listening on port {port}, serving {docroot}')
    try:
        while True:
            clientsocket, address = serversocket.accept()
            worker = HTTPWorker(clientsocket, address, docroot)
            worker.daemon = True
            worker.start()
    finally:
        serversocket.close()


def main():
    parser = argparse.ArgumentParser(description='Simple HTTP server')
    parser.add_argument('--port', type=int, default=1029, help='TCP port to listen on')
    parser.add_argument('--docroot', type=str, default='www', help='Document root directory')
    args = parser.parse_args()
    docroot = os.path.abspath(args.docroot)
    if not os.path.exists(docroot):
        print(f'Document root {docroot} does not exist')
        sys.exit(1)
    run_server(args.port, docroot)


if __name__ == '__main__':
    main()
