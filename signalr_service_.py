import logging
import threading
import requests

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol


# SignalR kütüphanesinin gereksiz loglarını azalt
logging.getLogger("SignalRCoreClient").setLevel(logging.WARNING)


class SignalRService:

    def __init__(self, hub_url: str = "https://call.qring.net/callHub"):

        self.hub_url = hub_url
        self.connection = None

        self.device_id = (
            "49B7E50FBB53A79454424DA3B8053F8EEC2B0428B202B21C835B203C9716426F"
        )

        self._cached_ip = None
        self._client_ip = None

        # SignalR bağlantısının gerçekten hazır olduğunu main.py'ye bildirir
        self.connected_event = threading.Event()

        # CallRejected geldiğinde main.py'deki fonksiyonu çalıştıracağız
        self.rejection_callback = None


    # ============================================================
    # CALL REJECTED CALLBACK
    # ============================================================

    def set_rejection_callback(self, callback):
        """
        main.py içerisindeki CallRejected fonksiyonunu buraya bağlar.
        """
        self.rejection_callback = callback


    # ============================================================
    # PUBLIC IP
    # ============================================================

    def get_public_ip(self) -> str:
        """
        Raspberry Pi'nin dış IP adresini bulur.
        """

        if self._cached_ip:
            return self._cached_ip

        try:

            response = requests.get(
                "https://api.ipify.org?format=json",
                timeout=5
            )

            if response.ok:

                ip = response.json().get("ip")

                if ip:
                    self._cached_ip = ip
                    return ip

        except Exception as e:

            print(
                f"[SIGNALR] Public IP alınamadı: {e}"
            )

        # Public IP alınamazsa yedek değer
        return "81.214.248.9"


    # ============================================================
    # BAĞLANTI BAŞLAT
    # ============================================================

    def start_connection(
        self,
        token: str,
        client_ip: str = None,
        timeout: int = 12
    ) -> bool:

        """
        SignalR bağlantısını başlatır.

        Bağlantı gerçekten kurulursa True,
        zaman aşımı veya hata olursa False döndürür.
        """

        # Önce eski READY durumunu temizle
        self.connected_event.clear()

        # IP manuel verilmediyse otomatik bul
        if client_ip:
            self._client_ip = client_ip
        else:
            self._client_ip = self.get_public_ip()


        def _connect():

            try:

                print(
                    "[SIGNALR] Soket bağlantısı başlatılıyor..."
                )

                full_url = (
                    f"{self.hub_url}?access_token={token}"
                )

                # ------------------------------------------------
                # SIGNALR CONNECTION
                # ------------------------------------------------

                self.connection = (
                    HubConnectionBuilder()
                    .with_url(
                        full_url,
                        options={
                            "access_token_factory": lambda: token
                        }
                    )
                    .with_hub_protocol(
                        JsonHubProtocol()
                    )
                    .configure_logging(
                        logging.WARNING
                    )
                    .with_automatic_reconnect({
                        "type": "raw",
                        "keep_alive_interval": 10,
                        "reconnect_interval": 5,
                        "max_attempts": 5
                    })
                    .build()
                )


                # ------------------------------------------------
                # SERVER EVENTLERİ
                # ------------------------------------------------

                self.connection.on(
                    "CallRejected",
                    lambda data:
                        self.handle_rejection(
                            "CallRejected",
                            data
                        )
                )

                # Bazı sistemlerde küçük harfle gelebileceği için
                self.connection.on(
                    "callRejected",
                    lambda data:
                        self.handle_rejection(
                            "callRejected",
                            data
                        )
                )


                # ------------------------------------------------
                # CONNECTION CALLBACKLERİ
                # ------------------------------------------------

                self.connection.on_open(
                    self._on_open
                )

                self.connection.on_close(
                    self._on_close
                )

                self.connection.on_error(
                    self._on_error
                )


                # ------------------------------------------------
                # BAĞLANTIYI BAŞLAT
                # ------------------------------------------------

                self.connection.start()


            except Exception as e:

                print(
                    f"\n[SIGNALR HATA] "
                    f"Bağlantı başlatılamadı: {e}"
                )

                self.connected_event.clear()


        # SignalR ayrı thread'de çalışsın
        thread = threading.Thread(
            target=_connect,
            daemon=True
        )

        thread.start()


        # --------------------------------------------------------
        # BAĞLANTININ GERÇEKTEN HAZIR OLMASINI BEKLE
        # --------------------------------------------------------

        connected = self.connected_event.wait(
            timeout=timeout
        )


        if connected:

            print(
                "[SIGNALR] Bağlantı hazır."
            )

            return True


        print(
            "[SIGNALR HATA] "
            "Bağlantı zaman aşımına uğradı."
        )

        return False


    # ============================================================
    # CONNECTION OPEN
    # ============================================================

    def _on_open(self):
        """
        SignalR handshake tamamlandığında çalışır.
        """

        print(
            "\n[SIGNALR] Soket bağlantısı kuruldu!"
        )


        try:

            # Cihazı SignalR odasına kaydet
            self.register_guest_ip(
                self._client_ip
            )

            # main.py artık bağlantının hazır olduğunu anlayabilir
            self.connected_event.set()


        except Exception as e:

            print(
                f"[SIGNALR HATA] "
                f"Cihaz kaydı yapılamadı: {e}"
            )

            self.connected_event.clear()


    # ============================================================
    # CONNECTION CLOSE
    # ============================================================

    def _on_close(self):

        print(
            "[SIGNALR] Soket bağlantısı kapandı."
        )

        self.connected_event.clear()


    # ============================================================
    # CONNECTION ERROR
    # ============================================================

    def _on_error(self, error):

        print(
            f"[SIGNALR HATA] {error}"
        )

        self.connected_event.clear()


    # ============================================================
    # REGISTER GUEST IP
    # ============================================================

    def register_guest_ip(self, ip_address: str):
        """
        Cihazı SignalR tarafında ilgili odaya kaydeder.
        """

        if self.connection is None:

            raise RuntimeError(
                "SignalR bağlantısı oluşturulmamış."
            )


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

        print(
            "[SIGNALR] CallRejected dinleniyor...\n"
        )


    # ============================================================
    # CALL REJECTED
    # ============================================================

    def handle_rejection(
        self,
        target,
        data
    ):

        """
        Sunucudan CallRejected geldiğinde çalışır.
        """

        if (
            isinstance(data, list)
            and len(data) > 0
        ):

            device_id = data[0]

        else:

            device_id = data


        print("\n" + "=" * 55)
        print("ÇAĞRI REDDEDİLDİ!")
        print(f"TARGET    : {target}")
        print(f"DEVICE ID : {device_id}")
        print("=" * 55 + "\n")


        # main.py içerisindeki callback'i çalıştır
        if self.rejection_callback:

            try:

                self.rejection_callback()

            except Exception as e:

                print(
                    f"[SIGNALR HATA] "
                    f"Rejection callback hatası: {e}"
                )


    # ============================================================
    # BAĞLANTIYI KAPAT
    # ============================================================

    def stop_connection(self):

        # Önce READY bilgisini kaldır
        self.connected_event.clear()


        if self.connection is None:
            return


        try:

            self.connection.stop()

            print(
                "[SIGNALR] Soket kapatıldı."
            )


        except Exception as e:

            print(
                f"[SIGNALR] "
                f"Soket kapatılırken hata: {e}"
            )


        finally:

            self.connection = None