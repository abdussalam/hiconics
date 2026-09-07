"""Constants for the Hiconics integration."""

DOMAIN = "hiconics"

# Defaults
DEFAULT_SCAN_INTERVAL = 600  # 10 minutes
DEFAULT_APP_ID = "3124071798191830"
DEFAULT_PRODUCT = "0_1067_1"
DEFAULT_CODE_GROUP = "G1200"

# Configuration keys
CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_SN = "device_sn"
CONF_DEVICE_ID = "device_id"
CONF_PRODUCT = "product"
CONF_CODE_GROUP = "code_group"
CONF_SCAN_INTERVAL = "scan_interval"

# API Endpoints
URL_TOKEN = "https://globalapi.solarmanpv.com/account/v1.0/token"
URL_DEVICE_DATA = "https://globalapi.solarmanpv.com/device/v1.0/currentData"
URL_COMMAND_SEND = "https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send"
URL_ORDER_STATUS = "https://globaldc-pro.solarmanpv.com/order-s/order/action"
