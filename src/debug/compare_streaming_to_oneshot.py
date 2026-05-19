from src.input.keyence_input_client import KeyenceInputClient

client = KeyenceInputClient(port="COM5", out_no=2, timeout=0.5)
client.open()

try:
    print("R0:", repr(client.send_command("R0")))

    for i in range(5):
        print("before stream MS:", repr(client.send_command("MS,3,2")))

    print("START STREAM:", repr(client.send_command("NS,3,01000000")))

    for i in range(10):
        raw = client.read_raw_bytes_until_cr()
        print("stream:", i, raw, raw.hex(" "))

    client.write_command_no_response("NT")

    for i in range(5):
        print("after stream MS:", repr(client.send_command("MS,3,2")))

finally:
    client.close()