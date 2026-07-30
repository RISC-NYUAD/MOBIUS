
import serial

try:
    # Change ttyUSB0 to your actual port if it's different
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    print("Listening to raw port. Press Ctrl+C to stop...")
    
    while True:
        raw_data = ser.readline()
        if raw_data:
            print(raw_data)
            
except Exception as e:
    print(f"Port Error: {e}")
