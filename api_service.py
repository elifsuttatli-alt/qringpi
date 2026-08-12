import requests
from api_map import BASE_URL, apiPaths


class APIService:
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = BASE_URL

    def login(self, username: str, password: str) -> str:
        url = f"{self.base_url}{apiPaths['auth']['login']}"
        payload = {"username": username, "password": password}

        response = self.session.post(url, json=payload)
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

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def start_call(self, device_unique_id: str, guest_name: str = "Sistem Test", client_ip: str = "82.222.168.210",
                   current_x: int = 0, current_y: int = 0, block_id: int = 0, apartment_id: int = 0, apartment_no: str = "undefined"):
        """Çağrı başlatır."""
        url = "https://call.qring.net/api/Call/CallStart"
        params = {
            "deviceUniqueId": device_unique_id,
            "guestName": guest_name,
            "clientIp": client_ip,
            "currentX": current_x,
            "currentY": current_y,
            "blockId": block_id,
            "apartmentId": apartment_id,
            "apartmentNo": apartment_no
        }

        response = self.session.get(url, params=params)
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

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()