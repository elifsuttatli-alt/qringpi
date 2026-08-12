import logging
import threading
import time
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol

# Arka plan log kalabalığını gizliyoruz
logging.getLogger("SignalRCoreClient").setLevel(logging.WARNING)


class SignalRService:
    def __init__(self, hub_url: str = "https://call.qring.net/callHub"):
        self.hub_url = hub_url
        self.connection = None
        self.device_id = "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"

    def start_connection(self, token: str):
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

                # Odaya kayıt olup dinlemeyi aktifleştiriyoruz
                self.register_guest_ip()

            except Exception as e:
                print(f"\n[SIGNALR HATA] Soket bağlanırken hata: {e}")

        t = threading.Thread(target=_connect, daemon=True)
        t.start()

    def register_guest_ip(self):
        """Sunucuya cihaz kaydını gönderir."""
        try:
            payload = [
                self.device_id,
                "81.214.248.9",
                self.device_id
            ]
            self.connection.send("RegisterGuestIP", payload)
            print("[SIGNALR] Cihaz odaya kaydedildi. Sadece CallRejected dinleniyor...\n")
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