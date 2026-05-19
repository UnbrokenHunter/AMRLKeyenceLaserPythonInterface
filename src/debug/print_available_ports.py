from serial.tools import list_ports


def print_available_ports() -> None:
    ports = list(list_ports.comports())

    if not ports:
        print("No serial ports found.")
        return

    print(f"Found {len(ports)} serial port(s):")

    for i, port in enumerate(ports, start=1):
        print()
        print(f"[{i}] {port.device}")
        print(f"    Description:  {port.description}")
        print(f"    Manufacturer: {port.manufacturer}")
        print(f"    Product:      {port.product}")
        print(f"    Serial #:     {port.serial_number}")
        print(f"    VID/PID:      {port.vid}:{port.pid}")
        print(f"    HWID:         {port.hwid}")


if __name__ == "__main__":
    print_available_ports()