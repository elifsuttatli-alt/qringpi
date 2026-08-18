import requests
from api_map import BASE_URL, apiPaths


class APIService:
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = BASE_URL
        self._cached_ip = None

    def get_public_ip(self) -> str:
        """Cihazın dış ağ IP adresini otomatik tespit eder (CallRejected engellemek için)."""
        if self._cached_ip:
            return self._cached_ip
        try:
            res = requests.get("https://api.ipify.org?format=json", timeout=5)
            if res.ok:
                self._cached_ip = res.json().get("ip")
                return self._cached_ip
        except Exception:
            pass
        return "82.222.168.210"  # Yedek varsayılan IP

    def login(self, username: str, password: str) -> str:
        url = f"{self.base_url}{apiPaths['auth']['login']}"
        payload = {"username": username, "password": password}

        response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()

        token = response.json().get("token")

        self.session.headers["Authorization"] = f"Bearer {token}"
        if hasattr(self.session, 'interceptor'):
            self.session.interceptor.api_key = token

        return token

    def call_taxi(self, device_unique_id: str, guest_name: str = "ESP32", message: str = "1"):
        url = f"{self.base_url}{apiPaths['taxi']['call']}"
        payload = {
            "deviceUniqueId": device_unique_id,
            "guestName": guest_name,
            "message": message
        }

        response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def start_call(self, device_unique_id: str, guest_name: str = "Sistem Test", client_ip: str = None,
                   current_x: int = 0, current_y: int = 0, block_id: int = 0, apartment_id: int = 0, apartment_no: str = "undefined"):
        """Çağrı başlatır."""
        url = "https://call.qring.net/api/Call/CallStart"

        # Eğer IP manuel verilmediyse otomatik tespit edilen dış IP kullanılır
        ip_to_use = client_ip if client_ip else self.get_public_ip()

        params = {
            "deviceUniqueId": device_unique_id,
            "guestName": guest_name,
            "clientIp": ip_to_use,
            "currentX": current_x,
            "currentY": current_y,
            "blockId": block_id,
            "apartmentId": apartment_id,
            "apartmentNo": apartment_no
        }

        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def set_switch_status(self, switch_id: str, device_unique_id: str, outlet: int = 0, request_type: int = 0):
        url = f"{self.base_url}{apiPaths['switch']['setStatus']}"
        payload = {
            "switchId": str(switch_id),
            "outlet": outlet,
            "deviceUniqueId": device_unique_id,
            "requestType": request_type
        }

        response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_block_list(self, device_id: int = 102025):
        url = f"{self.base_url}/api/Residence/GetBlockList"

        params = {
            "deviceId": device_id
        }

        response = self.session.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        return response.json()

    def get_apartment_list(self, block_id: int):
        url = f"{self.base_url}/api/Residence/GetCallableBlockApartmentList"

        params = {
            "blockId": block_id
        }

        response = self.session.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        return response.json()