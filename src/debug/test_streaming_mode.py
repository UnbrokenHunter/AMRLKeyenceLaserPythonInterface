from src.input.keyence_input_client import KeyenceInputClient

client = KeyenceInputClient(port="COM5", out_no=2, timeout=0.5)
client.open()

try:
    print("Trying to stop old stream...")
    try:
        client.write_command_no_response("NT")
    except Exception as e:
        print("NT write failed:", e)

    for _ in range(10):
        line = client.read_raw_line()
        if line:
            print("drain:", repr(line))

    print("R0:", repr(client.send_command("R0")))
    print("MS:", repr(client.send_command("MS,3,2")))

    print("START STREAM:", repr(client.send_command("NS,3,01000000")))

    for i in range(20):
        raw = client.read_raw_bytes_until_cr()
        print(i, raw, raw.hex(" "))

    print("STOP STREAM")
    client.write_command_no_response("NT")

finally:
    client.close()