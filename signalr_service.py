import logging
import threading
import time
import requests
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol

# Arka plan log kalabalığını gizliyoruz
logging.getLogger("SignalRCoreClient").setLevel(logging.WARNING)


class SignalRService:
    def __init__(self, hub_url: str = "https://call.qring.net/callHub"):
        self.hub_url = hub_url
        self.connection = None
        self.device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
        self._cached_ip = None

    def get_public_ip(self) -> str:
        """Cihazın dış ağ IP adresini otomatik tespit eder."""
        if self._cached_ip:
            return self._cached_ip
        try:
            res = requests.get("https://api.ipify.org?format=json", timeout=5)
            if res.ok:
                self._cached_ip = res.json().get("ip")
                return self._cached_ip
        except Exception:
            pass
        return "81.214.248.9"  # Yedek varsayılan IP

    def start_connection(self, token: str, client_ip: str = None):
        def _connect():
            try:
                full_url = f"{self.hub_url}?access_token={token}"
                self.connection = HubConnectionBuilder() \
                    .with_url(full_url, options={"access_token_factory": lambda: token}) \
                    .with_hub_protocol(JsonHubProtocol()) \
                    .configure_logging(logging.WARNING) \
                    .with_automatic_reconnect({
                        "type": "raw",
                        "keep_alive_interval": 10,
                        "reconnect_interval": 5,
                        "max_attempts": 5
                    }) \
                    .build()

                # SADECE 'CallRejected' / 'callRejected' EVENTLERİNİ BAĞLIYORUZ
                self.connection.on("CallRejected", lambda data: self.handle_rejection("CallRejected", data))
                self.connection.on("callRejected", lambda data: self.handle_rejection("callRejected", data))

                self.connection.start()
                print("\n[SIGNALR] Soket bağlantısı kuruldu!")
                time.sleep(1)

                # Odaya kayıt olup dinlemeyi aktifleştiriyoruz (IP parametresiyle)
                ip_to_use = client_ip if client_ip else self.get_public_ip()
                self.register_guest_ip(ip_to_use)

            except Exception as e:
                print(f"\n[SIGNALR HATA] Soket bağlanırken hata: {e}")

        t = threading.Thread(target=_connect, daemon=True)
        t.start()

    def register_guest_ip(self, ip_address: str):
        """Sunucuya cihaz kaydını dinamik IP ile gönderir."""
        try:
            payload = [
                self.device_id,
                ip_address,  # Dinamik dış ağ IP'si kullanılıyor
                self.device_id
            ]
            self.connection.send("RegisterGuestIP", payload)
            print(f"[SIGNALR] Cihaz odaya kaydoldu ({ip_address}). Sadece CallRejected dinleniyor...\n")
        except Exception as e:
            print(f"[SIGNALR HATA] RegisterGuestIP gönderilemedi: {e}")

    def handle_rejection(self, target, data):
        """Sadece CallRejected sinyali geldiğinde çalışır."""
        device_id = data[0] if isinstance(data, list) and len(data) > 0 else data

        print("\n" + "=" * 55)
        print(f" ❌ ÇAĞRI REDDEDİLDİ!")
        print(f" 🎯 TARGET   : {target}")
        print(f" 📱 DEVICE ID : {device_id}")
        print("=" * 55 + "\n")

    def stop_connection(self):
        if self.connection:
            try:
                self.connection.stop()
                print("[SIGNALR] Soket kapatıldı.")
            except Exception:
                pass