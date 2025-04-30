import network
import socket
from machine import Pin, PWM
import time
import _thread

# Wi-Fi Credentials (Replace with your Wi-Fi details)
SSID = "kusuma"
PASSWORD ="12345678"

# Connect ESP32 to Wi-Fi
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, PASSWORD)

while not wifi.isconnected():
    pass

print("Connected to Wi-Fi:", wifi.ifconfig())

# Setup PWM for RGB Bulb
red_led = PWM(Pin(25), freq=1000, duty=0)     # Red LED (GPIO 25)
green_led = PWM(Pin(32), freq=1000, duty=0)   # Green LED (GPIO 32)
blue_led = PWM(Pin(18), freq=1000, duty=0)    # Blue LED (GPIO 33)

# Setup PWM for LED Brightness
led_pwm = PWM(Pin(5), freq=1600, duty=0)      # LED Brightness (GPIO 5)

# Setup Relay for Light ON/OFF (GPIO 4)
relay = Pin(4, Pin.OUT)
relay.value(1)  # Start OFF - 1 is OFF, 0 is ON

# Function to control RGB Bulb color
def set_color(red, green, blue):
    red_led.duty(1023-int((red / 100) * 1023))      # Convert 0–100% to PWM
    green_led.duty(1023-int((green / 100) * 1023))
    blue_led.duty(1023-int((blue / 100) * 1023))

# Function to set LED Brightness
def set_brightness(level):
    duty_cycle = int((level / 100) * 1023)
    led_pwm.duty(duty_cycle)

# Function to turn light ON/OFF
def control_relay(state):
    relay.value(1 - state)  # Invert the logic: 1 is OFF, 0 is ON

# Function to handle light timer
def light_timer(minutes):
    print(f"Light will turn OFF in {minutes} minutes")
    # Turn the light ON when timer starts
    control_relay(1)  # 1 means ON
    
    # Wait for the specified time
    time.sleep(minutes * 60)
    
    # Turn the light OFF after timer completes
    control_relay(0)  # 0 means OFF
    print("Light Turned OFF after timer")

# HTML Web Page
html = """<!DOCTYPE html>
<html>
<head>
    <title>Home Automation</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background-color: #f4f4f4; }
        .container { max-width: 400px; margin: 20px auto; background: white; padding: 20px; box-shadow: 0px 0px 10px #aaa; border-radius: 10px; }
        h1 { color: #333; }
        .slider { width: 100%; }
        .btn { padding: 10px 20px; margin: 10px; border: none; background: #007bff; color: white; font-size: 18px; border-radius: 5px; cursor: pointer; }
        .btn:active { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RGB Bulb Control</h1>
        <label>Red:</label>
        <input type="range" min="0" max="100" value="0" class="slider" id="redSlider" oninput="updateColor()"><br><br>
        <label>Green:</label>
        <input type="range" min="0" max="100" value="0" class="slider" id="greenSlider" oninput="updateColor()"><br><br>
        <label>Blue:</label>
        <input type="range" min="0" max="100" value="0" class="slider" id="blueSlider" oninput="updateColor()"><br><br>
        <p>Red: <span id="redValue">0</span>%, Green: <span id="greenValue">0</span>%, Blue: <span id="blueValue">0</span>%</p>
    </div>

    <div class="container">
        <h1>LED Brightness</h1>
        <input type="range" min="0" max="100" value="50" class="slider" id="brightnessSlider" oninput="updateBrightness(this.value)">
        <p>Brightness: <span id="brightnessValue">50</span>%</p>
    </div>

    <div class="container">
        <h1>Light Control</h1>
        <button class="btn" onclick="window.location.href='/on'">Turn ON Light</button>
        <button class="btn" onclick="window.location.href='/off'">Turn OFF Light</button>
        <br><br>
        <form action="/set_timer" method="get">
            <label>Set Timer (minutes): </label>
            <input type="number" name="minutes" min="1">
            <button class="btn" type="submit">Set Timer</button>
        </form>
    </div>

    <script>
        function updateColor() {
            let red = document.getElementById('redSlider').value;
            let green = document.getElementById('greenSlider').value;
            let blue = document.getElementById('blueSlider').value;
            document.getElementById('redValue').innerText = red;
            document.getElementById('greenValue').innerText = green;
            document.getElementById('blueValue').innerText = blue;
            fetch('/color?red=' + red + '&green=' + green + '&blue=' + blue);
        }
        
        function updateBrightness(value) {
            document.getElementById('brightnessValue').innerText = value;
            fetch('/brightness?value=' + value);
        }
    </script>
</body>
</html>
"""

# Web Server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 80))
server.listen(5)

while True:
    conn, addr = server.accept()
    request = conn.recv(1024).decode()
    print("Request:", request)

    response = html  # Default response is the webpage

    if "/color?red=" in request and "&green=" in request and "&blue=" in request:
        try:
            red = int(request.split("/color?red=")[1].split("&")[0])
            green = int(request.split("&green=")[1].split("&")[0])
            blue = int(request.split("&blue=")[1].split(" ")[0])
            set_color(red, green, blue)
            response = f"RGB Color Set - R:{red}% G:{green}% B:{blue}%"
        except:
            response = "Invalid RGB values"

    elif "/brightness?value=" in request:
        try:
            value = int(request.split("/brightness?value=")[1].split(" ")[0])
            set_brightness(value)
            response = f"Brightness Set to {value}%"
        except:
            response = "Invalid brightness value"

    elif "/on" in request:
        control_relay(1)  # 1 means ON
        response = "Light Turned ON"

    elif "/off" in request:
        control_relay(0)  # 0 means OFF
        response = "Light Turned OFF"

    elif "/set_timer?minutes=" in request:
        try:
            minutes = int(request.split("/set_timer?minutes=")[1].split(" ")[0])
            _thread.start_new_thread(light_timer, (minutes,))
            response = f"Timer Set for {minutes} minutes. Light is ON and will turn OFF after timer."
        except:
            response = "Invalid timer value"

    conn.send("HTTP/1.1 200 OK\nContent-Type: text/html\n\n" + response)
    conn.close()
