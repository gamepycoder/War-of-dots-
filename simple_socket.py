import socket

HEADER = 64
FORMAT = "utf-8"


class Client:
    """
    A simple socket client.
    """

    def __init__(self, servip: str, port: int) -> None:
        """Initializes the client with addr details.

        Args:
            servip (str): server ip address
            port (int): port
        """
        self.servip = servip
        self.port = port

    def connect(self) -> None:
        """Attempts to establish a connection."""
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        addr = (self.servip, self.port)
        self.client.connect(addr)

    def send(self, msg: bytes) -> None:
        """Sends bytes to the server with a fixed-width header.

        Args:
            msg (bytes): The bytes to send
        """
        msg_length = len(msg)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b" " * (HEADER - len(send_length))
        self.client.sendall(send_length)
        self.client.sendall(msg)

    def rcv(self) -> bytes:
        """
        Receives bytes based on the header length.
        """
        msg_length = int(self.client.recv(HEADER).decode(FORMAT))
        total_received = 0
        chunks = []

        while total_received < msg_length:
            data = self.client.recv(msg_length - total_received)
            if not data:
                break
            total_received += len(data)
            chunks.append(data)

        return b"".join(chunks)

    def close(self) -> None:
        """Closes the socket"""
        self.client.close()


class Server:
    """
    A simple socket server
    """

    def __init__(self, ip: str, port: int) -> None:
        """Defines the server addr.

        Args:
            ip (str): server ip address
            port (int): port
        """
        self.ip = ip
        self.port = port
        self.conns = []

    def start(self) -> None:
        """Starts the server."""
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (self.ip, self.port)
        self.server.bind(addr)

    def lsn(self, conns: int = 0) -> None:
        """Starts listening for connections.

        Args:
            conns (int, optional): How many connections to listen for, Defaults to 0 (inf).
        """
        if conns > 0:
            self.server.listen(conns)
        else:
            self.server.listen()

    def accept(self) -> tuple:
        """Accepts a connection. Returns a socket and an address."""
        conn, addr = self.server.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.conns.append(conn)
        return conn, addr

    def send(self, conns: list, msg: bytes) -> None:
        """Sends a byte message to chosen connections.

        Args:
            conns (list): connections to send to
            msg (bytes): message in bytes
        """
        msg_length = len(msg)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b" " * (HEADER - len(send_length))
        for conn in conns:
            conn.sendall(send_length)
            conn.sendall(msg)

    def rcv(self, conn: socket.socket) -> bytes:
        """Receives bytes from a specific connection.

        Args:
            conn (socket.socket): connection to rcv from.

        Returns:
            bytes: the received message.
        """
        raw_header = conn.recv(HEADER).decode(FORMAT)
        if not raw_header.strip():
            return b""

        msg_length = int(raw_header)
        total_received = 0
        chunks = []

        while total_received < msg_length:
            data: bytes = conn.recv(msg_length - total_received)
            if not data:
                break
            total_received += len(data)
            chunks.append(data)

        return b"".join(chunks)

    def close(self, conn: socket.socket) -> None:
        """Closes a specific connection and removes it from the list of connections.

        Args:
            conn (socket.socket): connection to remove.
        """
        conn.close()
        if conn in self.conns:
            self.conns.remove(conn)
