BASE_URL = "https://call.qring.net"

apiPaths = {
    "auth": {
        "login": "/api/Authentication/Login",
        "refreshToken": "/api/Authentication/RefreshToken"
    },
    "taxi": {
        "call": "/api/Message/InsertMessage"
    },
    "call": {
        "start": "/api/Call/CallStart"
    },
    "switch": {
        "setStatus": "/api/Switch/SetSwitchStatus"
    }
}