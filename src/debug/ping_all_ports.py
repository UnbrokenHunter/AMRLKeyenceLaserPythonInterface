from serial.tools import list_ports
import serial
import time


BAUD_RATES = [
    115200,  # manual says this is the initial/default value
    9600,
    19200,
    38400,
    57600,
]

PING_COMMANDS = [
    b"PR\r",      # Read program number: expected response like b"PR,0\r"
    b"R0\r",      # Go to measurement mode: expected response b"R0\r"
    b"MA,0\r",    # Read all measurement values OUT1-OUT8
]


def read_response(ser: serial.Serial, wait_seconds: float = 0.25) -> bytes:
    time.sleep(wait_seconds)

    chunks = []

    while ser.in_waiting:
        chunks.append(ser.read(ser.in_waiting))
        time.sleep(0.05)

    return b"".join(chunks)


def try_keyence_ping(port_name: str, baud_rate: int) -> bool:
    print(f"\nTrying {port_name} at {baud_rate} baud...")

    try:
        with serial.Serial(
            port=port_name,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=0.5,
        ) as ser:
            time.sleep(0.25)

            ser.reset_input_buffer()
            ser.reset_output_buffer()

            for command in PING_COMMANDS:
                print(f"  Sending: {command!r}")

                ser.write(command)
                ser.flush()

                response = read_response(ser)

                if response:
                    text = response.decode("ascii", errors="replace").strip()

                    print("  RESPONSE FOUND")
                    print(f"  Raw:  {response!r}")
                    print(f"  Text: {text}")

                    if text.startswith("PR"):
                        print("  Looks like KEYENCE CL-3000 response to PR.")
                    elif text.startswith("R0"):
                        print("  Looks like KEYENCE CL-3000 response to R0.")
                    elif text.startswith("MA"):
                        print("  Looks like KEYENCE CL-3000 measurement response.")

                    return True

            print("  No response.")
            return False

    except serial.SerialException as error:
        print(f"  Could not open {port_name}: {error}")
        return False


def scan_ports():
    ports = list(list_ports.comports())

    if not ports:
        print("No serial ports found.")
        return

    print("Available ports:")
    for port in ports:
        print(f"{port.device} | {port.description} | {port.hwid}")

    matches = []

    for port in ports:
        for baud_rate in BAUD_RATES:
            if try_keyence_ping(port.device, baud_rate):
                matches.append((port.device, baud_rate))
                break

    print("\nScan complete.")

    if matches:
        print("Possible CL-3000 port(s):")
        for port_name, baud_rate in matches:
            print(f"  {port_name} at {baud_rate} baud")
    else:
        print("No CL-3000 response found.")


if __name__ == "__main__":
    scan_ports()