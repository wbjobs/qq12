import asyncio
import json
import socket
import platform
from datetime import datetime
from typing import Dict, Optional, Callable, List
from database import SessionLocal, ColorGroup, GroupMember, HeartbeatLog

DISCOVER_PORT = 45678
HEARTBEAT_PORT = 45679
NOTIFY_PORT = 45680
BUFFER_SIZE = 1024
MEMBER_TIMEOUT = 30

OnGroupUpdateCallback = Optional[Callable[[str], None]]


def _get_all_interface_ips() -> List[str]:
    ips = set()
    try:
        if platform.system() == "Windows":
            hostname = socket.gethostname()
            addrinfo = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
            for info in addrinfo:
                ip = info[4][0]
                if not ip.startswith("127."):
                    ips.add(ip)
        else:
            import netifaces
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr["addr"]
                        if not ip.startswith("127."):
                            ips.add(ip)
    except Exception:
        pass
    if not ips:
        ips.add("0.0.0.0")
    return list(ips)


class UDPService:
    def __init__(self):
        self._discover_socks: List[socket.socket] = []
        self._heartbeat_socks: List[socket.socket] = []
        self._notify_sock: Optional[socket.socket] = None
        self._tasks: list = []
        self._on_group_update: OnGroupUpdateCallback = None
        self._server_host: str = "0.0.0.0"
        self._all_ips: List[str] = []

    def set_group_update_callback(self, callback: OnGroupUpdateCallback):
        self._on_group_update = callback

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _create_bound_socket(self, port: int, ip: str = "") -> Optional[socket.socket]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass
            sock.bind((ip, port))
            sock.setblocking(False)
            return sock
        except Exception as e:
            print(f"[UDP] Failed to bind {ip}:{port}: {e}")
            try:
                sock.close()
            except Exception:
                pass
            return None

    async def start(self):
        self._server_host = self._get_local_ip()
        self._all_ips = _get_all_interface_ips()

        print(f"[UDP] Found network interfaces: {self._all_ips}")

        for ip in self._all_ips:
            sock = self._create_bound_socket(DISCOVER_PORT, ip)
            if sock:
                self._discover_socks.append(sock)
                print(f"[UDP] Discover bound to {ip}:{DISCOVER_PORT}")

        if not self._discover_socks:
            sock = self._create_bound_socket(DISCOVER_PORT, "")
            if sock:
                self._discover_socks.append(sock)
                print(f"[UDP] Discover bound to 0.0.0.0:{DISCOVER_PORT} (fallback)")

        for ip in self._all_ips:
            sock = self._create_bound_socket(HEARTBEAT_PORT, ip)
            if sock:
                self._heartbeat_socks.append(sock)
                print(f"[UDP] Heartbeat bound to {ip}:{HEARTBEAT_PORT}")

        if not self._heartbeat_socks:
            sock = self._create_bound_socket(HEARTBEAT_PORT, "")
            if sock:
                self._heartbeat_socks.append(sock)
                print(f"[UDP] Heartbeat bound to 0.0.0.0:{HEARTBEAT_PORT} (fallback)")

        self._notify_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._notify_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self._tasks.append(asyncio.create_task(self._handle_discover()))
        self._tasks.append(asyncio.create_task(self._handle_heartbeat()))
        self._tasks.append(asyncio.create_task(self._cleanup_timeout_members()))

        print(f"[UDP] Service started. Primary Server IP: {self._server_host}")
        print(f"[UDP] Discover sockets: {len(self._discover_socks)}, Heartbeat sockets: {len(self._heartbeat_socks)}")

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        for sock in self._discover_socks:
            try:
                sock.close()
            except Exception:
                pass
        for sock in self._heartbeat_socks:
            try:
                sock.close()
            except Exception:
                pass
        if self._notify_sock:
            try:
                self._notify_sock.close()
            except Exception:
                pass

    async def _recv_from_any_sock(self, socks: List[socket.socket]) -> Optional[tuple]:
        loop = asyncio.get_event_loop()
        tasks = []
        for sock in socks:
            tasks.append(loop.sock_recvfrom(sock, BUFFER_SIZE))
        if not tasks:
            await asyncio.sleep(0.1)
            return None
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            try:
                return task.result()
            except Exception:
                continue
        return None

    async def _handle_discover(self):
        loop = asyncio.get_event_loop()
        while True:
            try:
                result = await self._recv_from_any_sock(self._discover_socks)
                if not result:
                    continue
                data, addr = result
                message = data.decode("utf-8").strip()
                if message == "DISCOVER":
                    response = json.dumps({
                        "type": "SERVER_INFO",
                        "server_ip": self._server_host,
                        "heartbeat_port": HEARTBEAT_PORT,
                        "notify_port": NOTIFY_PORT
                    })
                    for sock in self._discover_socks:
                        try:
                            await loop.sock_sendto(sock, response.encode("utf-8"), addr)
                            break
                        except Exception:
                            continue
                    print(f"[UDP] Discover response sent to {addr}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[UDP] Discover error: {e}")

    async def _handle_heartbeat(self):
        while True:
            try:
                result = await self._recv_from_any_sock(self._heartbeat_socks)
                if not result:
                    continue
                data, addr = result
                message = data.decode("utf-8").strip()
                if message.startswith("REPORT:"):
                    parts = message.split(":")
                    if len(parts) >= 4:
                        group_id = parts[1]
                        member_id = parts[2]
                        try:
                            color_temp = float(parts[3])
                            self._process_heartbeat(group_id, member_id, color_temp, addr)
                        except ValueError:
                            print(f"[UDP] Invalid color temp from {addr}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[UDP] Heartbeat error: {e}")

    def _process_heartbeat(self, group_id: str, member_id: str, color_temp: float, addr: tuple):
        db = SessionLocal()
        try:
            group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
            if not group:
                group = ColorGroup(group_id=group_id, name=group_id)
                db.add(group)
                db.commit()
                db.refresh(group)

            member = db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.member_id == member_id
            ).first()

            if member:
                member.current_color_temp = color_temp
                member.client_ip = addr[0]
                member.client_port = addr[1]
                member.last_heartbeat = datetime.utcnow()
            else:
                member = GroupMember(
                    group_id=group_id,
                    member_id=member_id,
                    current_color_temp=color_temp,
                    client_ip=addr[0],
                    client_port=addr[1]
                )
                db.add(member)

            log = HeartbeatLog(
                group_id=group_id,
                member_id=member_id,
                color_temp=color_temp
            )
            db.add(log)
            db.commit()

            print(f"[UDP] Heartbeat: group={group_id}, member={member_id}, temp={color_temp}K, addr={addr}")

            if self._on_group_update:
                self._on_group_update(group_id)
        except Exception as e:
            print(f"[UDP] Process heartbeat error: {e}")
            db.rollback()
        finally:
            db.close()

    async def _cleanup_timeout_members(self):
        while True:
            try:
                await asyncio.sleep(10)
                db = SessionLocal()
                try:
                    now = datetime.utcnow()
                    timeout_members = []
                    groups = db.query(ColorGroup).all()
                    for group in groups:
                        for member in group.members:
                            if (now - member.last_heartbeat).total_seconds() > MEMBER_TIMEOUT:
                                timeout_members.append(member)

                    for member in timeout_members:
                        print(f"[UDP] Timeout member removed: {member.group_id}/{member.member_id}")
                        db.delete(member)
                    if timeout_members:
                        db.commit()
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[UDP] Cleanup error: {e}")

    def notify_target_temp(self, group_id: str, target_temp: float):
        db = SessionLocal()
        try:
            group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
            if not group:
                return

            message = f"SET_TEMP:{group_id}:{target_temp}"
            for member in group.members:
                if member.client_ip and member.client_port:
                    try:
                        self._notify_sock.sendto(
                            message.encode("utf-8"),
                            (member.client_ip, NOTIFY_PORT)
                        )
                        print(f"[UDP] Notify {member.client_ip}:{NOTIFY_PORT} -> {message}")
                    except Exception as e:
                        print(f"[UDP] Notify error to {member.client_ip}:{e}")
        finally:
            db.close()
