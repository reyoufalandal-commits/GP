from scapy.all import sniff, IP, TCP, UDP
from pathlib import Path
import time
import random

LOG_FILE = Path(r"C:\Users\خالد\Desktop\HawkEye_ZDA-main\data\lab\sim_conn.log")

HEADER = "#fields\tts\tuid\tproto\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\tid.orig_h\tid.resp_p\n"

target_rows = random.randint(15, 30)
written_rows = 0

def get_proto_port(pkt):
    if pkt.haslayer(TCP):
        return "tcp", pkt[TCP].dport
    if pkt.haslayer(UDP):
        return "udp", pkt[UDP].dport
    return "ip", 0

def process_packet(pkt):
    global written_rows

    if written_rows >= target_rows:
        return True

    if not pkt.haslayer(IP):
        return False

    proto, port = get_proto_port(pkt)
    ip = pkt[IP]

    ts = time.time()
    uid = f"Live{written_rows:05d}"
    duration = round(random.uniform(0.1, 2.5), 3)
    orig_bytes = len(pkt)
    resp_bytes = random.randint(80, 1500)
    orig_pkts = random.randint(1, 8)
    resp_pkts = random.randint(1, 8)

    row = (
        f"{ts:.6f}\t{uid}\t{proto}\t{duration}\t"
        f"{orig_bytes}\t{resp_bytes}\t{orig_pkts}\t{resp_pkts}\t"
        f"{ip.src}\t{port}\n"
    )

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(row)

    written_rows += 1
    print(f"{written_rows}/{target_rows} -> {ip.src}:{port}")

    return written_rows >= target_rows

def main():
    LOG_FILE.write_text(HEADER, encoding="utf-8")
    print(f"Capturing REAL network traffic: target {target_rows} rows")
    print("Open Google/YouTube now...")

    sniff(prn=process_packet, store=False, stop_filter=process_packet)

    print(f"Done. Wrote {written_rows} rows to sim_conn.log")

if __name__ == "__main__":
    main()