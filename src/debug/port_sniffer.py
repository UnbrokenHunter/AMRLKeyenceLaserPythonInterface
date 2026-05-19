import serial

PORT = "COM3"
BAUD_RATE = 9600

with serial.Serial(PORT, BAUD_RATE, timeout=1) as ser:
    print(f"Listening on {PORT}...")

    while True:
        data = ser.readline()

        if data:
            print(data)
            print(data.decode("utf-8", errors="replace").strip())