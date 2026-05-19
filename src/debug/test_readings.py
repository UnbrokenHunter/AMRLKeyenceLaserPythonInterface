import serial
import time

PORT = "COM5"
BAUD_RATE = 115200

with serial.Serial(
    PORT,
    BAUD_RATE,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1,
) as ser:
    time.sleep(0.25)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    ser.write(b"PR\r")
    ser.flush()
    print("Program response:", ser.readline().decode(errors="replace").strip())

    ser.write(b"R0\r")
    ser.flush()
    print("Measurement mode response:", ser.readline().decode(errors="replace").strip())

    ser.write(b"MA,0\r")
    ser.flush()
    print("Measurement response:", ser.readline().decode(errors="replace").strip())