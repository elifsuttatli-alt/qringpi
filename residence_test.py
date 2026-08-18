from interceptor import create_api_session
from api_service import APIService


USERNAME = "samsung.canli@fsitip.com"
PASSWORD = "Aa123456."


session = create_api_session()
api = APIService(session=session)


print("Login yapiliyor...")

token = api.login(
    USERNAME,
    PASSWORD
)

print("Login basarili.")
print()


# ============================================================
# BLOKLARI GETIR
# ============================================================

print("BLOKLAR:")

blocks = api.get_block_list()

for block in blocks:
    print(
        block["blockName"],
        "-> blockId:",
        block["id"]
    )


# ============================================================
# A BLOK DAIRELERINI GETIR
# ============================================================

print()
print("A BLOK DAIRELERI:")

apartments = api.get_apartment_list(12)

for apartment in apartments:
    print(
        apartment["apartmentName"],
        "-> apartmentId:",
        apartment["id"]
    )