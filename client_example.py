import socket
import json
import time
import threading
import random
import sys

DISCOVER_PORT = 45678
HEARTBEAT_PORT = 45679
NOTIFY_PORT = 45680
BUFFER_SIZE = 1024
HEARTBEAT_INTERVAL = 5


class ColorTempClient:
    def __init__(self, group_id: str, member_id: str, initial_temp: float = 6500.0):
        self.group_id = group_id
        self.member_id = member_id
        self.current_temp = initial_temp
        self.target_temp = None
        self.server_ip = None
        self.server_heartbeat_port = None
        self.server_notify_port = None
        self._running = False
        self._notify_sock = None

    def discover_server(self, timeout: float = 3.0) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)

        try:
            sock.sendto("DISCOVER".encode("utf-8"), ("255.255.255.255", DISCOVER_PORT))
            print(f"[Client] Broadcasting DISCOVER on port {DISCOVER_PORT}")

            data, addr = sock.recvfrom(BUFFER_SIZE)
            response = json.loads(data.decode("utf-8"))
            self.server_ip = response["server_ip"]
            self.server_heartbeat_port = response["heartbeat_port"]
            self.server_notify_port = response["notify_port"]
            print(f"[Client] Discovered server at {self.server_ip}:{self.server_heartbeat_port}")
            return True
        except socket.timeout:
            print("[Client] Server discovery timed out")
            return False
        except Exception as e:
            print(f"[Client] Discovery error: {e}")
            return False
        finally:
            sock.close()

    def _listen_notifications(self):
        self._notify_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._notify_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._notify_sock.bind(("", NOTIFY_PORT))
        self._notify_sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = self._notify_sock.recvfrom(BUFFER_SIZE)
                message = data.decode("utf-8").strip()
                if message.startswith("SET_TEMP:"):
                    parts = message.split(":")
                    if len(parts) >= 3:
                        msg_group_id = parts[1]
                        if msg_group_id == self.group_id:
                            try:
                                self.target_temp = float(parts[2])
                                self._apply_target_temp()
                            except ValueError:
                                pass
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"[Client] Notification error: {e}")

        if self._notify_sock:
            self._notify_sock.close()

    def _apply_target_temp(self):
        if self.target_temp is None:
            return
        print(f"[Client] Adjusting color temp from {self.current_temp:.0f}K to {self.target_temp:.0f}K")
        step = 100 if self.target_temp > self.current_temp else -100
        while abs(self.current_temp - self.target_temp) > abs(step):
            self.current_temp += step
            time.sleep(0.1)
        self.current_temp = self.target_temp
        print(f"[Client] Color temp adjusted to {self.current_temp:.0f}K")

    def _send_heartbeat(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            message = f"REPORT:{self.group_id}:{self.member_id}:{self.current_temp:.0f}"
            sock.sendto(
                message.encode("utf-8"),
                (self.server_ip, self.server_heartbeat_port)
            )
            print(f"[Client] Heartbeat: {self.current_temp:.0f}K")
        except Exception as e:
            print(f"[Client] Heartbeat error: {e}")
        finally:
            sock.close()

    def _simulate_temp_variation(self):
        variation = random.uniform(-50, 50)
        self.current_temp += variation
        self.current_temp = max(2000, min(9000, self.current_temp))

    def run(self):
        if not self.discover_server():
            return

        self._running = True
        notify_thread = threading.Thread(target=self._listen_notifications, daemon=True)
        notify_thread.start()

        print(f"[Client] Started. Group={self.group_id}, Member={self.member_id}")

        try:
            while True:
                if self.target_temp is None:
                    self._simulate_temp_variation()
                self._send_heartbeat()
                time.sleep(HEARTBEAT_INTERVAL)
        except KeyboardInterrupt:
            print("\n[Client] Stopping...")
        finally:
            self._running = False


def main():
    group_id = sys.argv[1] if len(sys.argv) > 1 else "group-livingroom"
    member_id = sys.argv[2] if len(sys.argv) > 2 else f"display-{socket.gethostname()}"
    initial_temp = float(sys.argv[3]) if len(sys.argv) > 3 else 6500.0

    client = ColorTempClient(group_id, member_id, initial_temp)
    client.run()


if __name__ == "__main__":
    main()
