import logging
import threading
import requests

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol


logging.getLogger("SignalRCoreClient").setLevel(logging.WARNING)


class SignalRService:

    def __init__(self, hub_url: str = "https://call.qring.net/callHub"):
        self.hub_url = hub_url
        self.connection = None

        self.device_id = (
            "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
        )

        self._cached_ip = None

        # Main.py SignalR gerçekten hazır mı diye bunu bekleyecek
        self.connected_event = threading.Event()

        # CallRejected geldiğinde main.py'ye haber vermek için
        self.rejection_callback = None

        self._client_ip = None


    def set_rejection_callback(self, callback):
        self.rejection_callback = callback


    def get_public_ip(self) -> str:
        if self._cached_ip:
            return self._cached_ip

        try:
            res = requests.get(
                "https://api.ipify.org?format=json",
                timeout=5
            )

            if res.ok:
                self._cached_ip = res.json().get("ip")
                return self._cached_ip

        except Exception:
            pass

        return "81.214.248.9"


    def start_connection(
        self,
        token: str,
        client_ip: str = None,
        timeout: int = 10
    ) -> bool:

        self.connected_event.clear()

        self._client_ip = (
            client_ip if client_ip
            else self.get_public_ip()
        )

        def _connect():

            try:
                full_url = (
                    f"{self.hub_url}?access_token={token}"
                )

                self.connection = (
                    HubConnectionBuilder()
                    .with_url(
                        full_url,
                        options={
                            "access_token_factory": lambda: token
                        }
                    )
                    .with_hub_protocol(JsonHubProtocol())
                    .configure_logging(logging.WARNING)
                    .with_automatic_reconnect({
                        "type": "raw",
                        "keep_alive_interval": 10,
                        "reconnect_interval": 5,
                        "max_attempts": 5
                    })
                    .build()
                )

                # CallRejected eventleri
                self.connection.on(
                    "CallRejected",
                    lambda data:
                        self.handle_rejection(
                            "CallRejected",
                            data
                        )
                )

                self.connection.on(
                    "callRejected",
                    lambda data:
                        self.handle_rejection(
                            "callRejected",
                            data
                        )
                )

                # SignalR gerçekten hazır olduğunda çalışır
                self.connection.on_open(
                    self._on_open
                )

                self.connection.on_close(
                    self._on_close
                )

                self.connection.start()

            except Exception as e:

                print(
                    f"\n[SIGNALR HATA] "
                    f"Bağlantı kurulamadı: {e}"
                )

                self.connected_event.clear()


        thread = threading.Thread(
            target=_connect,
            daemon=True
        )

        thread.start()

        # Main.py burada bağlantının gerçekten açılmasını bekler
        connected = self.connected_event.wait(
            timeout=timeout
        )

        if not connected:
            print(
                "[SIGNALR HATA] "
                "Bağlantı zaman aşımına uğradı."
            )

        return connected


    def _on_open(self):

        print("\n[SIGNALR] Soket bağlantısı kuruldu!")

        try:
            self.register_guest_ip(
                self._client_ip
            )

            # RegisterGuestIP gönderildikten sonra
            # sistemi hazır kabul ediyoruz
            self.connected_event.set()

        except Exception as e:

            print(
                f"[SIGNALR HATA] "
                f"Cihaz kaydı başarısız: {e}"
            )

            self.connected_event.clear()


    def _on_close(self):

        print("[SIGNALR] Bağlantı kapandı.")

        self.connected_event.clear()


    def register_guest_ip(self, ip_address: str):

        payload = [
            self.device_id,
            ip_address,
            self.device_id
        ]

        self.connection.send(
            "RegisterGuestIP",
            payload
        )

        print(
            f"[SIGNALR] Cihaz odaya kaydoldu "
            f"({ip_address})."
        )


    def handle_rejection(self, target, data):

        device_id = (
            data[0]
            if isinstance(data, list)
            and len(data) > 0
            else data
        )

        print("\n" + "=" * 55)
        print("ÇAĞRI REDDEDİLDİ!")
        print(f"TARGET    : {target}")
        print(f"DEVICE ID : {device_id}")
        print("=" * 55 + "\n")

        # main.py'ye haber ver
        if self.rejection_callback:
            self.rejection_callback()


    def stop_connection(self):

        self.connected_event.clear()

        if self.connection:

            try:
                self.connection.stop()

            except Exception:
                pass

            self.connection = None

            print("[SIGNALR] Soket kapatıldı.")