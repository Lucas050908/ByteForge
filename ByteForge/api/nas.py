import os
import shutil
import subprocess
from pathlib import Path

from api.config import PLATFORM, SHARED_ROOT
from api.utils import run


def _linux_pkg_manager():
    for pm, bin_ in [("apt","apt-get"),("dnf","dnf"),("yum","yum"),
                     ("pacman","pacman"),("zypper","zypper"),("apk","apk")]:
        if shutil.which(bin_):
            return pm
    return None


def get_nas():
    if PLATFORM == "Windows":
        return {"status": "inactive", "shares": [], "path": str(SHARED_ROOT)}
    if PLATFORM == "Darwin":
        exports, _, _ = run("cat /etc/exports 2>/dev/null")
        active, _, _ = run("nfsd status 2>/dev/null | head -1")
        shares = [l.strip() for l in exports.splitlines() if l.strip() and not l.startswith("#")]
        return {"status": "active" if "running" in active.lower() else "inactive", "shares": shares, "path": str(SHARED_ROOT)}
    exports, _, _ = run("cat /etc/exports 2>/dev/null")
    active, _, _ = run("systemctl is-active nfs-server 2>/dev/null || systemctl is-active nfs-kernel-server 2>/dev/null")
    shares = [line.strip() for line in exports.splitlines() if line.strip() and not line.startswith("#")]
    return {"status": active.strip(), "shares": shares, "path": str(SHARED_ROOT)}


def nas_setup(path, subnet, readonly, smb_user="", smb_pass=""):
    if PLATFORM != "Linux":
        return {"ok": False, "steps": ["NFS setup kun understøttet på Linux"]}
    steps = []
    # 1. Install nfs-utils if exportfs is missing
    if not shutil.which("exportfs"):
        steps.append("▶ Installerer NFS server pakke...")
        pm = _linux_pkg_manager()
        pkg = {"apt":"nfs-kernel-server","dnf":"nfs-utils","yum":"nfs-utils",
               "pacman":"nfs-utils","zypper":"nfs-utils","apk":"nfs-utils"}.get(pm)
        if not pkg:
            steps.append("✗ Ukendt pakkemanager — installer nfs-utils manuelt")
            return {"ok": False, "steps": steps}
        _, err, code = run([{"apt":"apt-get","dnf":"dnf","yum":"yum",
                              "pacman":"pacman","zypper":"zypper","apk":"apk"}[pm],
                            "install", "-y", pkg], shell=False, timeout=180)
        if code != 0:
            steps.append(f"✗ Installation fejlede: {err[:200]}")
            return {"ok": False, "steps": steps}
        steps.append(f"✓ NFS server installeret")
    else:
        steps.append("✓ NFS server allerede installeret")
    # 2. Create directory
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o777)
        steps.append(f"✓ Mappe klar: {path}")
    except Exception as e:
        steps.append(f"✗ Kunne ikke oprette mappe: {e}")
        return {"ok": False, "steps": steps}
    # 3. Write /etc/exports (skip if already present)
    opts = "ro,sync,no_subtree_check" if readonly else "rw,sync,no_subtree_check,no_root_squash"
    entry = f"{path} {subnet}({opts})"
    exports_path = Path("/etc/exports")
    existing = exports_path.read_text() if exports_path.exists() else ""
    if path in existing and subnet in existing:
        steps.append("✓ Export allerede i /etc/exports")
    else:
        try:
            with open(str(exports_path), "a") as f:
                f.write(f"\n{entry}\n")
            steps.append(f"✓ Tilføjet til /etc/exports")
        except Exception as e:
            steps.append(f"✗ Kunne ikke skrive /etc/exports: {e}")
            return {"ok": False, "steps": steps}
    # 4. Enable + start NFS service
    started = False
    for svc in ("nfs-server", "nfs-kernel-server"):
        _, _, code = run(f"systemctl enable --now {svc} 2>/dev/null", shell=True, timeout=20)
        if code == 0:
            steps.append(f"✓ NFS service startet ({svc})")
            started = True
            break
    if not started:
        steps.append("✗ Kunne ikke starte NFS service")
        return {"ok": False, "steps": steps}
    # 5. Reload exports
    _, err, code = run("exportfs -ra 2>/dev/null", shell=True, timeout=10)
    steps.append("✓ Exports genindlæst" if code == 0 else f"! exportfs: {err[:100]}")
    # 6. Firewall
    if shutil.which("firewall-cmd"):
        for svc in ("nfs", "mountd", "rpc-bind"):
            run(f"firewall-cmd --permanent --add-service={svc} 2>/dev/null", shell=True)
        run("firewall-cmd --reload 2>/dev/null", shell=True)
        steps.append("✓ Firewall åbnet for NFS (firewalld)")
    elif shutil.which("ufw"):
        run("ufw allow 2049/tcp 2>/dev/null", shell=True)
        run("ufw allow 111/tcp 2>/dev/null", shell=True)
        steps.append("✓ Firewall åbnet for NFS (ufw)")
    # Samba setup
    if smb_user and smb_pass:
        smb_steps, _ = nas_setup_samba(path, smb_user, smb_pass)
        steps.extend(smb_steps)
    return {"ok": True, "steps": steps}


def nas_setup_samba(path, smb_user, smb_pass):
    steps = []
    pm = _linux_pkg_manager()
    # Install samba
    if not shutil.which("smbd"):
        steps.append("▶ Installerer Samba...")
        pkg = {"apt":"samba","dnf":"samba","yum":"samba",
               "pacman":"samba","zypper":"samba","apk":"samba"}.get(pm)
        if not pkg:
            steps.append("✗ Ukendt pakkemanager"); return steps, False
        _, err, code = run([{"apt":"apt-get","dnf":"dnf","yum":"yum",
                              "pacman":"pacman","zypper":"zypper","apk":"apk"}[pm],
                            "install", "-y", pkg], shell=False, timeout=180)
        if code != 0:
            steps.append(f"✗ Samba installation fejlede: {err[:200]}"); return steps, False
        steps.append("✓ Samba installeret")
    else:
        steps.append("✓ Samba allerede installeret")
    # Add share to smb.conf
    conf_path = Path("/etc/samba/smb.conf")
    share_name = Path(path).name
    existing = conf_path.read_text() if conf_path.exists() else ""
    if f"[{share_name}]" not in existing:
        share_block = f"\n[{share_name}]\n   path = {path}\n   browsable = yes\n   writable = yes\n   valid users = {smb_user}\n   create mask = 0664\n   directory mask = 0775\n"
        with open(str(conf_path), "a") as f:
            f.write(share_block)
        steps.append(f"✓ Share '{share_name}' tilføjet til smb.conf")
    else:
        steps.append(f"✓ Share '{share_name}' allerede i smb.conf")
    # Set samba password
    proc = subprocess.Popen(["smbpasswd", "-a", "-s", smb_user],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate(input=f"{smb_pass}\n{smb_pass}\n")
    if proc.returncode == 0:
        steps.append(f"✓ Samba adgangskode sat for {smb_user}")
    else:
        steps.append(f"! smbpasswd: {out.strip()[:100]}")
    # Enable + start smb
    _, _, code = run("systemctl enable --now smb 2>/dev/null || systemctl enable --now smbd 2>/dev/null",
                     shell=True, timeout=15)
    steps.append("✓ Samba service startet" if code == 0 else "✗ Kunne ikke starte Samba service")
    # Firewall
    if shutil.which("firewall-cmd"):
        run("firewall-cmd --permanent --add-service=samba 2>/dev/null", shell=True)
        run("firewall-cmd --reload 2>/dev/null", shell=True)
        steps.append("✓ Firewall åbnet for Samba")
    elif shutil.which("ufw"):
        run("ufw allow samba 2>/dev/null", shell=True)
        steps.append("✓ UFW åbnet for Samba")
    return steps, code == 0


def nas_remove_share(path):
    if PLATFORM != "Linux":
        return {"ok": False, "msg": "Ikke understøttet"}
    exports_path = Path("/etc/exports")
    if not exports_path.exists():
        return {"ok": False, "msg": "/etc/exports ikke fundet"}
    lines = [l for l in exports_path.read_text().splitlines() if not l.strip().startswith(path)]
    exports_path.write_text("\n".join(lines) + "\n")
    run("exportfs -ra 2>/dev/null", shell=True, timeout=10)
    return {"ok": True, "msg": f"Share fjernet: {path}"}


def nas_service_action(action):
    if PLATFORM == "Darwin":
        _, _, code = run(f"nfsd {action} 2>/dev/null", timeout=15, shell=True)
        return {"ok": code == 0, "msg": f"NFS {action} gennemført" if code == 0 else "NFS fejlede"}
    if PLATFORM == "Windows":
        return {"ok": False, "msg": "NFS administration ikke understøttet på Windows"}
    for svc in ("nfs-server", "nfs-kernel-server"):
        _, _, code = run(f"systemctl {action} {svc} 2>/dev/null", timeout=15, shell=True)
        if code == 0:
            return {"ok": True, "msg": f"NFS {action} gennemført"}
    return {"ok": False, "msg": "NFS service ikke fundet"}
