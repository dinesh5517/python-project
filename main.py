from machine import Pin, PWM
import time
import network
import logging
from arduino_iot_cloud import ArduinoCloudClient
import gc

# Import credentials from secrets.py
from secrets import WIFI_SSID, WIFI_PASSWORD, DEVICE_ID, CLOUD_PASSWORD

# GPIO setup
LED1_PIN = 4  # Simple ON/OFF LED
led1 = Pin(LED1_PIN, Pin.OUT)

LED2_PIN = 5  # Brightness control LED
led2_pwm = PWM(Pin(LED2_PIN), freq=1000)
led2_pwm.duty(0)

# RGB LED pins
RED_PIN = 25
GREEN_PIN = 32
BLUE_PIN = 18
red_pwm = PWM(Pin(RED_PIN), freq=1000)
green_pwm = PWM(Pin(GREEN_PIN), freq=1000)
blue_pwm = PWM(Pin(BLUE_PIN), freq=1000)
red_pwm.duty(0)
green_pwm.duty(0)
blue_pwm.duty(0)

# Configure logging
logging.basicConfig(
    datefmt="%H:%M:%S",
    format="%(asctime)s.%(msecs)03d %(message)s",
    level=logging.INFO,
)

# Current state variables
led1_state = False
led2_brightness = 20  # Default to 20% brightness
led2_switch = False
led3_hue = 240  # Default to blue
led3_saturation = 100
led3_brightness = 100
led3_switch = False

def map_value(value, in_min, in_max, out_min, out_max):
    return (value - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB (0-1023) with accurate color reproduction"""
    h = max(0, min(360, h))
    s = max(0, min(100, s)) / 100.0
    v = max(0, min(100, v)) / 100.0
    
    if s == 0:
        r = g = b = v
    else:
        h /= 60.0
        i = int(h)
        f = h - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        
        if i == 0: r, g, b = v, t, p
        elif i == 1: r, g, b = q, v, p
        elif i == 2: r, g, b = p, v, t
        elif i == 3: r, g, b = p, q, v
        elif i == 4: r, g, b = t, p, v
        else: r, g, b = v, p, q
    
    r = int(r * 1023)
    g = int(g * 1023)
    b = int(b * 1023)
    
    # Uncomment if your RGB LED is common anode
    r, g, b = 1023 - r, 1023 - g, 1023 - b
    
    return (r, g, b)

def update_rgb_led():
    """Update RGB LED based on current HSV values"""
    if led3_switch:
        r, g, b = hsv_to_rgb(led3_hue, led3_saturation, led3_brightness)
        red_pwm.duty(r)
        green_pwm.duty(g)
        blue_pwm.duty(b)
        logging.info(f"Set RGB: H={led3_hue} S={led3_saturation}% B={led3_brightness}% => R={r} G={g} B={b}")
    else:
        red_pwm.duty(0)
        green_pwm.duty(0)
        blue_pwm.duty(0)
        logging.info("RGB LED turned OFF")

def sync_initial_values(client):
    """Sync initial values with cloud variables."""
    try:
        client.update("led1", led1_state)
        client.update("led2:bri", led2_brightness)
        client.update("led2:swi", led2_switch)
        client.update("led3:hue", led3_hue)
        client.update("led3:sat", led3_saturation)
        client.update("led3:bri", led3_brightness)
        client.update("led3:swi", led3_switch)
        logging.info("Initial values synced with cloud")
    except Exception as e:
        logging.error(f"Error syncing initial values: {e}")

# Cloud callbacks
def on_led1_changed(client, value):
    global led1_state
    led1_state = value
    led1.value(not value)  # Changed from 'not value' to 'value'
    logging.info(f"LED1 {'ON' if value else 'OFF'}")

def on_led2_brightness_changed(client, value):
    global led2_brightness
    led2_brightness = max(0, min(100, int(value)))  # Convert to int
    if led2_switch:
        led2_pwm.duty(map_value(led2_brightness, 0, 100, 0, 1023))
    logging.info(f"LED2 brightness {led2_brightness}%")

def on_led2_switch_changed(client, value):
    global led2_switch
    led2_switch = bool(value)  # Ensure boolean
    if value:
        led2_pwm.duty(map_value(led2_brightness, 0, 100, 0, 1023))
    else:
        led2_pwm.duty(0)
    logging.info(f"LED2 {'ON' if value else 'OFF'}")

def on_led3_hue_changed(client, value):
    global led3_hue
    led3_hue = max(0, min(360, value))
    update_rgb_led()

def on_led3_saturation_changed(client, value):
    global led3_saturation
    led3_saturation = max(0, min(100, value))
    update_rgb_led()

def on_led3_brightness_changed(client, value):
    global led3_brightness
    led3_brightness = max(0, min(100, value))
    update_rgb_led()

def on_led3_switch_changed(client, value):
    global led3_switch
    led3_switch = value
    update_rgb_led()

def wifi_connect():
    """Connect to Wi-Fi with retries."""
    if not WIFI_SSID or not WIFI_PASSWORD:
        raise Exception("Network not configured in secrets.py")
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        logging.info(f"Connecting to WiFi {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        for _ in range(30):
            if wlan.isconnected():
                break
            time.sleep(1)
        
        if not wlan.isconnected():
            raise Exception("Wi-Fi connection failed")
    
    logging.info(f"Connected to Wi-Fi: {wlan.ifconfig()}")

# Initialize all devices to OFF state
led1.value(False)  # OFF state
led2_pwm.duty(0)
red_pwm.duty(0)
green_pwm.duty(0)
blue_pwm.duty(0)
logging.info("Initialized: All LEDs OFF")

# Connect to Wi-Fi
try:
    wifi_connect()
except Exception as e:
    logging.error(f"Wi-Fi failed: {e}")
    raise

# Connect to Arduino IoT Cloud
def setup_cloud_client():
    client = ArduinoCloudClient(device_id=DEVICE_ID, username=DEVICE_ID, password=CLOUD_PASSWORD)
    
    # Register cloud variables
    client.register("led1", value=None, on_write=on_led1_changed)
    client.register("led2:bri", value=None, on_write=on_led2_brightness_changed)
    client.register("led2:swi", value=None, on_write=on_led2_switch_changed)
    client.register("led3:hue", value=None, on_write=on_led3_hue_changed)
    client.register("led3:sat", value=None, on_write=on_led3_saturation_changed)
    client.register("led3:bri", value=None, on_write=on_led3_brightness_changed)
    client.register("led3:swi", value=None, on_write=on_led3_switch_changed)
    
    return client

max_cloud_attempts = 5
client = None

for attempt in range(max_cloud_attempts):
    try:
        logging.info(f"Cloud connection attempt {attempt + 1}/{max_cloud_attempts}")
        client = setup_cloud_client()
        client.start()
        
        # Wait for connection to stabilize
        time.sleep(3)
        sync_initial_values(client)
        logging.info("Successfully connected to Arduino IoT Cloud")
        break
    except Exception as e:
        logging.error(f"Cloud connection failed (attempt {attempt + 1}): {e}")
        if attempt + 1 == max_cloud_attempts:
            logging.error("Max connection attempts reached, continuing without cloud")
            client = None  # Continue without cloud connection
            break
        time.sleep(5)
        gc.collect()

# Main loop
while True:
    try:
        if client:
            # Check connection status periodically
            if not client.is_connected():
                logging.warning("Reconnecting to cloud...")
                try:
                    client.reconnect()
                    time.sleep(3)
                    sync_initial_values(client)
                except Exception as e:
                    logging.error(f"Reconnection failed: {e}")
        
        time.sleep(1)
    except Exception as e:
        logging.error(f"Main loop error: {e}")
        time.sleep(5)