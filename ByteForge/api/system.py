import datetime
import os
import re
import shutil

from api.config import PLATFORM, FILES_ROOT
from api.utils import run


def _is_admin():
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def exec_command(cmd):
    BLOCKED = ["rm -rf /", "mkfs", "> /dev/", "dd if=", ":(){:|:&};:", "chmod 777 /", "chmod -R 777 /"]
    cmd_lower = cmd.lower().strip()
    for b in BLOCKED:
        if b in cmd_lower:
            return {"ok": False, "output": "⛔ Kommando blokeret af sikkerhedshensyn", "code": 1}
    out, err, code = run(cmd, timeout=15, shell=True)
    return {"ok": True, "output": out or err or "(ingen output)", "code": code}


def get_system():
    import time
    cpu, total, used, temp, uptime = 0, 0, 0, "?", "?"

    if PLATFORM == "Linux":
        cpu_out, _, _ = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
        if not cpu_out:
            cpu_out, _, _ = run("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
        try:
            cpu = round(float(cpu_out), 1)
        except Exception:
            cpu = 0
        try:
            with open("/proc/meminfo") as f:
                mem = {l.split(":")[0]: int(l.split(":")[1].strip().split()[0]) for l in f if ":" in l}
            total = mem.get("MemTotal", 0)
            used = total - mem.get("MemAvailable", 0)
        except Exception:
            pass
        try:
            temp_raw, _, _ = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
            temp = round(int(temp_raw) / 1000, 1)
        except Exception:
            t2, _, _ = run("sensors 2>/dev/null | grep 'Core 0' | awk '{print $3}' | tr -d '+°C'")
            temp = t2 or "?"
        try:
            uptime_s = int(open("/proc/uptime").read().split()[0].split(".")[0])
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass

    elif PLATFORM == "Darwin":
        cpu_out, _, _ = run("top -l 1 -s 0 | grep 'CPU usage' | awk '{print $3}' | tr -d '%'")
        try:
            cpu = round(float(cpu_out), 1)
        except Exception:
            cpu = 0
        try:
            mem_out, _, _ = run("sysctl hw.memsize")
            total = int(mem_out.split(":")[1].strip()) // 1024
            vm_out, _, _ = run("vm_stat")
            page_size = 4096
            pages_free = pages_inactive = 0
            for line in vm_out.splitlines():
                if "page size of" in line:
                    page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
                elif "Pages free" in line:
                    pages_free = int(line.split(":")[1].strip().rstrip("."))
                elif "Pages inactive" in line:
                    pages_inactive = int(line.split(":")[1].strip().rstrip("."))
            avail = (pages_free + pages_inactive) * page_size // 1024
            used = total - avail
        except Exception:
            pass
        temp_out, _, _ = run("osx-cpu-temp 2>/dev/null || echo '?'")
        temp = temp_out.replace("°C", "").strip() or "?"
        try:
            boot_out, _, _ = run("sysctl kern.boottime | awk '{print $5}' | tr -d ','")
            uptime_s = int(time.time()) - int(boot_out)
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass

    elif PLATFORM == "Windows":
        cpu_out, _, _ = run("wmic cpu get loadpercentage /value", shell=True)
        try:
            cpu = round(float(next(l for l in cpu_out.splitlines() if "=" in l).split("=")[1].strip()), 1)
        except Exception:
            cpu = 0
        try:
            mem_out, _, _ = run("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value", shell=True)
            vals = {l.split("=")[0].strip(): l.split("=")[1].strip() for l in mem_out.splitlines() if "=" in l and l.split("=")[1].strip()}
            total = int(vals.get("TotalVisibleMemorySize", 0))
            used = total - int(vals.get("FreePhysicalMemory", 0))
        except Exception:
            pass
        try:
            boot_out, _, _ = run("wmic os get lastbootuptime /value", shell=True)
            boot_str = next(l for l in boot_out.splitlines() if "=" in l).split("=")[1].strip()[:14]
            boot_dt = datetime.datetime.strptime(boot_str, "%Y%m%d%H%M%S")
            uptime_s = int((datetime.datetime.now() - boot_dt).total_seconds())
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass
        temp = "?"

    return {
        "cpu": cpu,
        "ram_used_mb": used // 1024,
        "ram_total_mb": total // 1024,
        "ram_pct": round(used / total * 100, 1) if total else 0,
        "temp": temp,
        "uptime": uptime,
    }


def get_disks():
    import shlex
    disks = []
    if PLATFORM == "Windows":
        out, _, _ = run("wmic logicaldisk get caption,size,freespace /format:csv", shell=True)
        seen = set()
        for line in out.splitlines()[2:]:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                caption, free_s, size_s = parts[1], parts[2], parts[3]
                if caption and size_s and caption not in seen:
                    seen.add(caption)
                    try:
                        total_g = int(size_s) // (1024 ** 3) or 1
                        free_g = int(free_s) // (1024 ** 3)
                        used_g = total_g - free_g
                        disks.append({"mount": caption, "total": str(total_g), "used": str(used_g),
                                      "free": str(free_g), "pct": str(round(used_g / total_g * 100))})
                    except Exception:
                        pass
        return disks
    def kib_to_gib(value):
        try:
            kib = int(value)
        except (TypeError, ValueError):
            return "0"
        gib = 1024 * 1024
        return str((kib + gib - 1) // gib)

    cmd = f"df -kP / {shlex.quote(str(FILES_ROOT))} 2>/dev/null || df -kP /"
    out, _, _ = run(cmd)
    seen = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[5] not in seen:
            seen.add(parts[5])
            disks.append({
                "mount": parts[5],
                "total": kib_to_gib(parts[1]),
                "used": kib_to_gib(parts[2]),
                "free": kib_to_gib(parts[3]),
                "pct": parts[4].replace("%", ""),
            })
    return disks


def get_raid():
    if PLATFORM != "Linux":
        return {"status": "inactive", "info": f"RAID administration ikke understøttet på {PLATFORM}"}
    md, _, _ = run("cat /proc/mdstat 2>/dev/null")
    if not md or "md" not in md:
        return {"status": "inactive", "info": "Ingen RAID konfigureret"}
    info = [line.strip() for line in md.splitlines() if line.strip()]
    state = "active" if "active" in md else "degraded" if "degraded" in md else "unknown"
    return {"status": state, "info": "\n".join(info[:6])}


def get_hardware():
    cpu_model = cpu_cores = gpu = ""
    if PLATFORM == "Linux":
        m, _, _ = run("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2")
        cpu_model = m.strip()
        c, _, _ = run("nproc --all 2>/dev/null || grep -c processor /proc/cpuinfo")
        cpu_cores = c.strip()
        g, _, _ = run("lspci 2>/dev/null | grep -iE 'vga|3d|display' | head -1 | sed 's/.*: //'")
        gpu = g.strip()
        if not gpu:
            g2, _, _ = run("nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1")
            gpu = g2.strip()
    elif PLATFORM == "Darwin":
        m, _, _ = run("sysctl machdep.cpu.brand_string 2>/dev/null | cut -d: -f2")
        cpu_model = m.strip()
        c, _, _ = run("sysctl hw.logicalcpu 2>/dev/null | cut -d: -f2")
        cpu_cores = c.strip()
        g, _, _ = run("system_profiler SPDisplaysDataType 2>/dev/null | grep 'Chipset Model' | head -1 | cut -d: -f2")
        gpu = g.strip()
    elif PLATFORM == "Windows":
        mo, _, _ = run("wmic cpu get name /value", shell=True)
        cpu_model = next((l.split("=", 1)[1].strip() for l in mo.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
        co, _, _ = run("wmic cpu get NumberOfLogicalProcessors /value", shell=True)
        cpu_cores = next((l.split("=", 1)[1].strip() for l in co.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
        go, _, _ = run("wmic path win32_VideoController get name /value", shell=True)
        gpu = next((l.split("=", 1)[1].strip() for l in go.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
    hostname, _, _ = run("hostname")
    mb = ""
    if PLATFORM == "Linux":
        mb_v, _, _ = run("cat /sys/class/dmi/id/board_vendor 2>/dev/null")
        mb_n, _, _ = run("cat /sys/class/dmi/id/board_name 2>/dev/null")
        mb = f"{mb_v.strip()} {mb_n.strip()}".strip()
    elif PLATFORM == "Darwin":
        mb_o, _, _ = run("system_profiler SPHardwareDataType 2>/dev/null | grep 'Model Name' | cut -d: -f2")
        mb = mb_o.strip()
    elif PLATFORM == "Windows":
        mb_o, _, _ = run("wmic baseboard get manufacturer,product /value", shell=True)
        parts = {l.split("=")[0].strip(): l.split("=")[1].strip() for l in mb_o.splitlines() if "=" in l and l.split("=")[1].strip()}
        mb = f"{parts.get('Manufacturer','')} {parts.get('Product','')}".strip()
    # Distro / OS name
    os_name = PLATFORM
    if PLATFORM == "Linux":
        pr, _, _ = run("grep '^PRETTY_NAME' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '\"'")
        if not pr:
            pr, _, _ = run("lsb_release -ds 2>/dev/null")
        os_name = pr.strip() or "Linux"
    elif PLATFORM == "Darwin":
        pn, _, _ = run("sw_vers -productName 2>/dev/null")
        pv, _, _ = run("sw_vers -productVersion 2>/dev/null")
        os_name = f"{pn.strip()} {pv.strip()}".strip() or "macOS"
    elif PLATFORM == "Windows":
        wo, _, _ = run("wmic os get caption /value", shell=True)
        os_name = next((l.split("=", 1)[1].strip() for l in wo.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "Windows")
    kernel = ""
    if PLATFORM == "Linux":
        kernel, _, _ = run("uname -r 2>/dev/null")
    return {
        "cpu_model": cpu_model or "Ukendt CPU",
        "cpu_cores": cpu_cores or "?",
        "gpu": gpu or "Ingen GPU fundet",
        "motherboard": mb or "?",
        "hostname": hostname.strip(),
        "platform": PLATFORM,
        "os_name": os_name,
        "kernel": kernel.strip(),
    }


def get_smart():
    if PLATFORM != "Linux":
        return {"available": False, "disks": []}
    smart_bin = shutil.which("smartctl")
    out, _, _ = run("lsblk -d -n -o NAME,SIZE,MODEL,ROTA 2>/dev/null", shell=True, timeout=5)
    disks = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if not parts:
            continue
        name = parts[0].strip()
        if name.startswith(("loop", "ram", "zram", "sr")):
            continue
        size = parts[1].strip() if len(parts) > 1 else "?"
        rotational = parts[2].strip() if len(parts) > 2 else "1"
        model = (parts[3].strip() if len(parts) > 3 else name.upper()) or name.upper()
        disk = {"name": name, "dev": f"/dev/{name}", "model": model, "size": size,
                "type": "HDD" if rotational == "1" else "SSD/NVMe",
                "health": "unknown", "temp": None, "power_on_hours": None,
                "reallocated": None, "smartctl": smart_bin is not None}
        if smart_bin:
            sout, _, _ = run([smart_bin, "-a", f"/dev/{name}"], shell=False, timeout=10)
            if "PASSED" in sout:
                disk["health"] = "passed"
            elif "FAILED" in sout:
                disk["health"] = "failed"
            m = re.search(r'Temperature[^:\n]*:\s*(\d+)\s*(?:Celsius)?', sout, re.IGNORECASE)
            if m:
                disk["temp"] = int(m.group(1))
            m = re.search(r'Power_On_Hours\s+(?:\S+\s+){5}(\d+)', sout)
            if not m:
                m = re.search(r'Power On Hours:\s+([\d,]+)', sout)
            if m:
                disk["power_on_hours"] = int(m.group(1).replace(",", ""))
            m = re.search(r'Reallocated_Sector_Ct\s+(?:\S+\s+){5}(\d+)', sout)
            if m:
                disk["reallocated"] = int(m.group(1))
            m = re.search(r'Available Spare:\s+(\d+)%', sout)
            if m:
                disk["available_spare"] = int(m.group(1))
            m = re.search(r'Percentage Used:\s+(\d+)%', sout)
            if m:
                disk["pct_used"] = int(m.group(1))
        disks.append(disk)
    return {"available": smart_bin is not None, "disks": disks}
