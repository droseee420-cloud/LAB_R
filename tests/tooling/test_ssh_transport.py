"""Real loopback SSH handshakes with a disposable server; no external host."""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paramiko
import pytest
from scripts.deploy.client import DeployError, connect, fingerprint, run

pytestmark = pytest.mark.ssh


@pytest.fixture
def ssh_server(tmp_path):
    host_key = paramiko.RSAKey.generate(2048)
    user_key = paramiko.RSAKey.generate(2048)
    key_file = tmp_path / "synthetic key.pem"
    user_key.write_private_key_file(str(key_file))
    stop = threading.Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.1)
    transports = []

    class Server(paramiko.ServerInterface):
        def __init__(self):
            self.command = None
            self.command_ready = threading.Event()

        def get_allowed_auths(self, username):
            return "password,publickey"

        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL if username == "synthetic" and password == "test-password" else paramiko.AUTH_FAILED

        def check_auth_publickey(self, username, key):
            return paramiko.AUTH_SUCCESSFUL if username == "synthetic" and key == user_key else paramiko.AUTH_FAILED

        def check_channel_request(self, kind, chanid):
            return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

        def check_channel_exec_request(self, channel, command):
            self.command = command
            self.command_ready.set()
            return True

    def handle(sock):
        transport = paramiko.Transport(sock)
        transports.append(transport)
        transport.add_server_key(host_key)
        server = Server()
        try:
            transport.start_server(server=server)
            channel = transport.accept(5)
            if channel and server.command_ready.wait(5):
                if server.command == b"false":
                    channel.send_stderr(b"synthetic-private-error")
                    channel.send_exit_status(1)
                else:
                    channel.send(b"LAB_STAGE protocol-verified\n")
                    channel.send_exit_status(0)
                channel.close()
                # Let the client consume exit-status and close its transport first.
                deadline = time.monotonic() + 10
                while transport.is_active() and time.monotonic() < deadline and not stop.wait(0.01):
                    pass
        except (EOFError, paramiko.SSHException, OSError):
            pass
        finally:
            transport.close()

    executor = ThreadPoolExecutor(max_workers=4)
    def accept():
        while not stop.is_set():
            try:
                sock, _ = listener.accept()
                executor.submit(handle, sock)
            except socket.timeout:
                continue
            except OSError:
                break
    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield {"host": "127.0.0.1", "port": listener.getsockname()[1], "username": "synthetic", "password": "test-password",
           "host_fingerprint": fingerprint(host_key)}, key_file
    stop.set()
    listener.close()
    for transport in transports:
        transport.close()
    thread.join(timeout=2)
    executor.shutdown(wait=True)


def test_password_auth_and_command_exit(ssh_server, capsys):
    config, _ = ssh_server
    client = connect(config)
    try:
        run(client, ["true"])
    finally:
        client.close()
    assert "protocol-verified" in capsys.readouterr().out
    client = connect(config)
    try:
        with pytest.raises(DeployError):
            run(client, ["false"])
    finally:
        client.close()
    assert "synthetic-private-error" not in capsys.readouterr().out


def test_wrong_password_key_and_host_are_rejected(ssh_server, tmp_path):
    config, _ = ssh_server
    with pytest.raises(paramiko.AuthenticationException):
        connect(config | {"password": "wrong"})
    wrong_key = Path(tmp_path) / "wrong.pem"
    paramiko.RSAKey.generate(2048).write_private_key_file(str(wrong_key))
    with pytest.raises(paramiko.AuthenticationException):
        connect(config | {"password": "", "key_filename": str(wrong_key)})
    with pytest.raises(DeployError):
        connect(config | {"host_fingerprint": "SHA256:untrusted"})


def test_key_authentication(ssh_server):
    config, key_file = ssh_server
    client = connect(config | {"password": "", "key_filename": str(key_file)})
    try:
        assert run(client, ["true"], capture=True) == "LAB_STAGE protocol-verified"
    finally:
        client.close()
