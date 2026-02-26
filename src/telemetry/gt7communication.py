# src/telemetry/gt7communication.py
import os
import socket
import struct
import time
from dataclasses import dataclass
from datetime import timedelta
from threading import Thread
from typing import Optional, Dict, Any

from Crypto.Cipher import Salsa20


@dataclass
class GTData:
    # Core telemetry fields parsed below need bytes through offset 0x92
    # inclusive.
    MIN_PACKET_SIZE = 0x93
    CAR_ID_OFFSET = 0x124
    CAR_ID_SIZE = 4

    package_id: int = 0
    best_lap_ms: int = 0
    last_lap_ms: int = 0
    current_lap: int = 0
    total_laps: int = 0

    car_speed_kmh: float = 0.0
    rpm: float = 0.0
    throttle_pct: float = 0.0
    brake_pct: float = 0.0

    # NEW (documented by protocol layout)
    current_gear: int = 0
    suggested_gear: int = 0

    fuel_capacity: float = 0.0
    current_fuel: float = 0.0

    is_paused: bool = False
    in_race: bool = False

    time_on_track: timedelta = timedelta(seconds=0)

    # NEW (documented by protocol layout)
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0

    car_id: Optional[int] = None

    @staticmethod
    def from_packet(ddata: bytes) -> "GTData":
        if not ddata or len(ddata) < GTData.MIN_PACKET_SIZE:
            return GTData()

        # Position/physics (0x04..0x34 range in docs)
        # PositionX/Y/Z are float32 at the start of that block.
        position_x = struct.unpack("<f", ddata[0x04:0x08])[0]
        position_y = struct.unpack("<f", ddata[0x08:0x0C])[0]
        position_z = struct.unpack("<f", ddata[0x0C:0x10])[0]

        # Packet metadata / timing
        package_id = struct.unpack("<I", ddata[0x70:0x74])[0]
        best_lap = struct.unpack("<i", ddata[0x78:0x7C])[0]
        last_lap = struct.unpack("<i", ddata[0x7C:0x80])[0]
        current_lap = struct.unpack("<h", ddata[0x74:0x76])[0]
        total_laps = struct.unpack("<h", ddata[0x76:0x78])[0]

        time_on_track = timedelta(
            seconds=round(struct.unpack("<i", ddata[0x80:0x84])[0] / 1000)
        )

        # Engine / fuel / speed
        fuel_capacity = struct.unpack("<f", ddata[0x48:0x4C])[0]
        current_fuel = struct.unpack("<f", ddata[0x44:0x48])[0]
        car_speed = (
            3.6 * struct.unpack("<f", ddata[0x4C:0x50])[0]
        )  # m/s -> km/h

        rpm = struct.unpack("<f", ddata[0x3C:0x40])[0]

        # Controls (0x90..0x92 range in docs)
        # Gear byte packs current+suggested: low nibble = current, high nibble
        # = suggested
        gear_byte = struct.unpack("<B", ddata[0x90:0x91])[0]
        current_gear = gear_byte & 0b00001111
        suggested_gear = (gear_byte >> 4) & 0b00001111

        throttle = struct.unpack("<B", ddata[0x91:0x92])[0] / 2.55
        brake = struct.unpack("<B", ddata[0x92:0x93])[0] / 2.55

        # Flags (docs mention flags at 0x8E; keeping your existing
        # interpretation)
        flags = struct.unpack("<B", ddata[0x8E:0x8F])[0]
        is_paused = bool(flags & 0b00000010)
        in_race = bool(flags & 0b00000001)

        # car_id is optional; some packet variants are shorter.
        car_id = None
        if len(ddata) >= (GTData.CAR_ID_OFFSET + GTData.CAR_ID_SIZE):
            car_id = struct.unpack(
                "<i",
                ddata[
                    GTData.CAR_ID_OFFSET:GTData.CAR_ID_OFFSET
                    + GTData.CAR_ID_SIZE
                ],
            )[0]

        return GTData(
            package_id=package_id,
            best_lap_ms=best_lap,
            last_lap_ms=last_lap,
            current_lap=current_lap,
            total_laps=total_laps,
            car_speed_kmh=car_speed,
            rpm=rpm,
            throttle_pct=throttle,
            brake_pct=brake,
            current_gear=current_gear,
            suggested_gear=suggested_gear,
            fuel_capacity=fuel_capacity,
            current_fuel=current_fuel,
            is_paused=is_paused,
            in_race=in_race,
            time_on_track=time_on_track,
            position_x=position_x,
            position_y=position_y,
            position_z=position_z,
            car_id=car_id,
        )


def salsa20_dec(dat: bytes) -> bytes:
    key = b"Simulator Interface Packet GT7 ver 0.0"
    oiv = dat[0x40:0x44]
    iv1 = int.from_bytes(oiv, byteorder="little")
    iv2 = iv1 ^ 0xDEADBEAF
    iv = bytearray()
    iv.extend(iv2.to_bytes(4, "little"))
    iv.extend(iv1.to_bytes(4, "little"))
    cipher = Salsa20.new(key[0:32], bytes(iv))
    ddata = cipher.decrypt(dat)
    magic = int.from_bytes(ddata[0:4], byteorder="little")
    if magic != 0x47375330:
        return b""
    return ddata


class GT7Communication(Thread):
    SEND_PORT = 33739
    RECV_PORT = 33740
    DISCOVERY_SENTINEL = "AUTO"

    def __init__(self, playstation_ip: Optional[str] = None):
        super().__init__(daemon=True)
        self._shall_run = True
        self._shall_restart = False

        self.playstation_ip = (
            playstation_ip
            or os.getenv("GT7_PLAYSTATION_IP", "").strip()
            or self.DISCOVERY_SENTINEL
        )
        self._discovered_ip: Optional[str] = None

        self._last_rx_time = 0.0
        self._telemetry_seq = 0
        self._last_gtdata: GTData = GTData()
        self._last_error: Optional[str] = None
        self._bound_recv_port: Optional[int] = None
        self._rx_datagrams = 0
        self._rx_valid_packets = 0
        self._tx_heartbeats = 0
        self._last_sender_ip: Optional[str] = None
        try:
            hb = float(os.getenv("GT7_HEARTBEAT_INTERVAL_S", "1.00"))
        except Exception:
            hb = 1.00
        self._hb_interval_s = max(0.05, min(1.0, hb))
        self._socket_timeout_s = 0.25
        self._no_data_warn_after_s = 3.0

    def stop(self) -> None:
        self._shall_run = False

    def restart(self) -> None:
        self._shall_restart = True

    def set_playstation_ip(self, ip: str) -> None:
        normalized = (ip or "").strip()
        self.playstation_ip = normalized or self.DISCOVERY_SENTINEL
        if self.playstation_ip == self.DISCOVERY_SENTINEL:
            self._discovered_ip = None

    def is_connected(self) -> bool:
        return (
            self._last_rx_time > 0
            and (time.time() - self._last_rx_time) <= 1.0
        )

    def _set_error(self, message: str) -> None:
        msg = (message or "").strip()
        if not msg:
            return
        if msg != self._last_error:
            self._last_error = msg
            print(f"[gt7comm] {msg}")

    def _clear_error(self) -> None:
        self._last_error = None

    def _make_socket(self, *, broadcast: bool = False) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if broadcast:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except OSError:
                pass
        if os.name == "nt":
            # Windows can raise WSAECONNRESET on UDP recvfrom
            # after ICMP errors.
            # Disable that behavior so transient network errors don't break the
            # loop.
            try:
                # type: ignore[attr-defined]
                s.ioctl(socket.SIO_UDP_CONNRESET, False)
            except Exception:
                pass
        return s

    def _report_no_data(self, ip: Optional[str]) -> None:
        target = (ip or "").strip()
        if target:
            self._set_error(
                (
                    f"No telemetry packets from {target}. Verify PS5 IP, "
                    "GT7 on-track state, and Windows firewall UDP "
                    f"{self.RECV_PORT}."
                )
            )
        else:
            self._set_error(
                (
                    "No telemetry packets received. Set PS5 IP manually or "
                    "verify network/firewall UDP "
                    f"{self.RECV_PORT}."
                )
            )

    def _on_sample(self, _gt: GTData) -> None:
        # Reserved for future: push into a higher-rate session buffer, etc.
        return

    def snapshot(self) -> Dict[str, Any]:
        d = self._last_gtdata
        if d is None:
            return {}

        return {
            "connected": self.is_connected(),
            "ip": self._discovered_ip
            or (
                None
                if self.playstation_ip == self.DISCOVERY_SENTINEL
                else self.playstation_ip
            ),
            "telemetry_seq": self._telemetry_seq,
            "rx_age_s": None
            if self._last_rx_time == 0
            else (time.time() - self._last_rx_time),
            "package_id": d.package_id,
            "connection_error": self._last_error,
            "bound_recv_port": self._bound_recv_port,
            "rx_datagrams": self._rx_datagrams,
            "rx_valid_packets": self._rx_valid_packets,
            "tx_heartbeats": self._tx_heartbeats,
            "last_sender_ip": self._last_sender_ip,
            "lap": d.current_lap,
            "total_laps": d.total_laps,
            "in_race": d.in_race,
            "paused": d.is_paused,
            "time_on_track_s": int(d.time_on_track.total_seconds()),
            "speed_kmh": d.car_speed_kmh,
            "rpm": d.rpm,
            "gear": d.current_gear,
            "suggested_gear": d.suggested_gear,
            "throttle": d.throttle_pct,
            "brake": d.brake_pct,
            "fuel": d.current_fuel,
            "fuel_capacity": d.fuel_capacity,
            "best_lap_ms": d.best_lap_ms,
            "last_lap_ms": d.last_lap_ms,
            "position_x": d.position_x,
            "position_y": d.position_y,
            "position_z": d.position_z,
            "car_id": d.car_id,
        }

    def _send_hb(self, s: socket.socket, ip: str) -> None:
        try:
            s.sendto(b"A", (ip, self.SEND_PORT))
            self._tx_heartbeats += 1
        except OSError:
            pass

    def _discover_playstation_ip(
        self, timeout_sec: float = 3.0
    ) -> Optional[str]:
        s = self._make_socket(broadcast=True)
        try:
            s.bind(("0.0.0.0", self.RECV_PORT))
            self._bound_recv_port = int(s.getsockname()[1])
            s.settimeout(0.25)

            end = time.time() + timeout_sec
            while (
                time.time() < end
                and self._shall_run
                and not self._shall_restart
            ):
                self._send_hb(s, "255.255.255.255")
                try:
                    data, addr = s.recvfrom(4096)
                except socket.timeout:
                    continue
                self._rx_datagrams += 1
                self._last_sender_ip = addr[0]
                ddata = salsa20_dec(data)
                if ddata:
                    self._rx_valid_packets += 1
                    return addr[0]
            self._report_no_data(None)
        except OSError as e:
            self._set_error(
                f"Discovery socket error on UDP {self.RECV_PORT}: {e}"
            )
        finally:
            try:
                s.close()
            except Exception:
                pass
            self._bound_recv_port = None
        return None

    def run(self) -> None:
        while self._shall_run:
            s = None
            try:
                self._shall_restart = False

                ip = self.playstation_ip
                if ip in (None, "", self.DISCOVERY_SENTINEL):
                    ip = self._discover_playstation_ip()
                    if not ip:
                        time.sleep(0.5)
                        continue
                    self._discovered_ip = ip
                else:
                    self._discovered_ip = ip

                s = self._make_socket()
                s.bind(("0.0.0.0", self.RECV_PORT))
                self._bound_recv_port = int(s.getsockname()[1])
                s.settimeout(self._socket_timeout_s)

                self._send_hb(s, ip)
                last_hb_time = time.monotonic()
                last_rx_any_time = time.monotonic()

                last_seen_package_id: Optional[int] = None

                while self._shall_run and not self._shall_restart:
                    now_mono = time.monotonic()
                    if (now_mono - last_hb_time) >= self._hb_interval_s:
                        self._send_hb(s, ip)
                        last_hb_time = now_mono

                    try:
                        data, addr = s.recvfrom(4096)
                        last_rx_any_time = time.monotonic()
                        self._rx_datagrams += 1
                        self._last_sender_ip = addr[0]
                        ddata = salsa20_dec(data)
                        if not ddata:
                            continue
                        if len(ddata) < GTData.MIN_PACKET_SIZE:
                            continue

                        pkg_id = struct.unpack("<I", ddata[0x70:0x74])[0]
                        if (
                            last_seen_package_id is not None
                            and pkg_id == last_seen_package_id
                        ):
                            self._last_rx_time = time.time()
                            self._clear_error()
                            continue
                        last_seen_package_id = pkg_id

                        gt = GTData.from_packet(ddata)
                        self._last_gtdata = gt
                        self._last_rx_time = time.time()
                        self._rx_valid_packets += 1
                        self._clear_error()

                        # now safe (no AttributeError)
                        self._on_sample(gt)

                        self._telemetry_seq += 1

                    except socket.timeout:
                        now_mono = time.monotonic()
                        if (now_mono - last_hb_time) >= self._hb_interval_s:
                            self._send_hb(s, ip)
                            last_hb_time = now_mono
                        if (
                            now_mono - last_rx_any_time
                        ) >= self._no_data_warn_after_s:
                            self._report_no_data(ip)
                    except struct.error:
                        # Ignore malformed packets and keep listening.
                        continue
                    except OSError:
                        break

            except Exception as e:
                self._set_error(f"Connection loop error: {e}")
                time.sleep(0.5)
            finally:
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass
                self._bound_recv_port = None
                if not self._shall_restart:
                    time.sleep(0.1)
