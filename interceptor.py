import requests
from requests.adapters import HTTPAdapter
from api_map import BASE_URL, apiPaths


class APIInterceptor(HTTPAdapter):

    def __init__(self, api_key: str = None, *args, **kwargs):
        self.api_key = api_key
        self._is_refreshing = False  # Sonsuz döngü engelleme bayrağı
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if self.api_key:
            request.headers['Authorization'] = f"Bearer {self.api_key}"
        request.headers['User-Agent'] = "MyCustomClient/1.0"

        print(f"[INTERCEPTOR - OUT] -> {request.method} {request.url}")

        response = super().send(request, **kwargs)

        print(f"[INTERCEPTOR - IN]  <- Status: {response.status_code}")

        # 401 Unauthorized alındıysa ve şu an bir yenileme yapılmıyorsa
        if response.status_code == 401 and self.api_key and not self._is_refreshing:
            print("[INTERCEPTOR] Token süresi dolmuş (401). Yenileniyor...")
            self._is_refreshing = True

            try:
                refresh_url = f"{BASE_URL}{apiPaths['auth']['refreshToken']}"
                refresh_payload = {"token": self.api_key}

                # Interceptor'a takılmaması için doğrudan requests.post kullanıyoruz
                refresh_response = requests.post(refresh_url, json=refresh_payload, timeout=10)

                if refresh_response.ok:
                    new_token = refresh_response.json().get("token")
                    print("[INTERCEPTOR] Token başarıyla yenilendi! İstek tekrarlanıyor...")

                    self.api_key = new_token
                    request.headers['Authorization'] = f"Bearer {new_token}"
                    return super().send(request, **kwargs)
                else:
                    print("\n[UYARI] Refresh token süresi de dolmuş! Oturum sonlandırılıyor...")
                    raise requests.exceptions.HTTPError("REFRESH_TOKEN_EXPIRED")
            finally:
                self._is_refreshing = False

        return response


def create_api_session(api_key: str = None) -> requests.Session:
    session = requests.Session()
    interceptor = APIInterceptor(api_key=api_key)
    session.mount("http://", interceptor)
    session.mount("https://", interceptor)
    session.interceptor = interceptor
    return session