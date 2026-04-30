#!/usr/bin/env python3
import gi, subprocess, threading, urllib.request, os, tempfile, time
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

def run(cmd):
    try: return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except: return ""

def get_metadata():
    status = run(["playerctl", "status"])
    if status not in ("Playing", "Paused"): return None
    return {"status": status, "title": run(["playerctl", "metadata", "title"]),
            "artist": run(["playerctl", "metadata", "artist"]),
            "album": run(["playerctl", "metadata", "album"]),
            "art_url": run(["playerctl", "metadata", "mpris:artUrl"])}

def fetch_art(url):
    if not url: return None
    try:
        if url.startswith("file://"): return GdkPixbuf.Pixbuf.new_from_file_at_scale(url[7:], 140, 140, True)
        tmp = tempfile.mktemp(suffix=".jpg")
        urllib.request.urlretrieve(url, tmp)
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(tmp, 140, 140, True)
        os.unlink(tmp); return pb
    except: return None

win = Gtk.Window(title="Now Playing")
win.set_default_size(420, 150)
win.set_decorated(False)
win.connect("destroy", Gtk.main_quit)
css = Gtk.CssProvider()
css.load_from_data(b"window{background-color:rgba(10,10,10,0.88);border-radius:18px;border:1px solid rgba(255,255,255,0.08);} .song{font-size:17px;font-weight:bold;color:#fff;} .artist{font-size:13px;color:rgba(255,255,255,0.65);} .album{font-size:11px;color:rgba(255,255,255,0.35);} button{background:rgba(255,255,255,0.10);border-radius:50%;min-width:40px;min-height:40px;color:white;border:none;} button:hover{background:rgba(255,255,255,0.22);} .play{min-width:48px;min-height:48px;background:rgba(255,255,255,0.18);} .off{font-size:14px;color:rgba(255,255,255,0.35);}")
Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
stack = Gtk.Stack(); stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE); win.set_child(stack)
row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
row.set_margin_top(16); row.set_margin_bottom(16); row.set_margin_start(16); row.set_margin_end(16)
img = Gtk.Image(); img.set_pixel_size(140); img.set_from_icon_name("audio-x-generic")
fr = Gtk.Frame(); fr.set_child(img); fr.set_size_request(140,140); row.append(fr)
right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); right.set_valign(Gtk.Align.CENTER); right.set_hexpand(True)
tl = Gtk.Label(label=""); tl.add_css_class("song"); tl.set_xalign(0); tl.set_ellipsize(3); right.append(tl)
al = Gtk.Label(label=""); al.add_css_class("artist"); al.set_xalign(0); al.set_ellipsize(3); right.append(al)
bl = Gtk.Label(label=""); bl.add_css_class("album"); bl.set_xalign(0); bl.set_ellipsize(3); right.append(bl)
ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); ctrl.set_margin_top(12)
pbtn = None
for ic, cmd in [("media-skip-backward",["playerctl","previous"]),("media-playback-start",["playerctl","play-pause"]),("media-skip-forward",["playerctl","next"])]:
    btn = Gtk.Button(); btn.set_icon_name(ic)
    if ic == "media-playback-start": btn.add_css_class("play"); pbtn = btn
    btn.connect("clicked", lambda _,c=cmd: subprocess.Popen(c))
    ctrl.append(btn)
right.append(ctrl); row.append(right); stack.add_named(row, "on")
off_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); off_box.set_valign(Gtk.Align.CENTER); off_box.set_halign(Gtk.Align.CENTER); off_box.set_size_request(420,150)
off_lbl = Gtk.Label(label="No music playing"); off_lbl.add_css_class("off"); off_box.append(off_lbl)
stack.add_named(off_box, "off")
last_url = [None]
def update():
    m = get_metadata()
    if not m: stack.set_visible_child_name("off")
    else:
        tl.set_text(m["title"] or "Unknown"); al.set_text(m["artist"] or ""); bl.set_text(m["album"] or "")
        pbtn.set_icon_name("media-playback-pause" if m["status"]=="Playing" else "media-playback-start")
        if m["art_url"] != last_url[0]:
            last_url[0] = m["art_url"]
            def load():
                pb = fetch_art(m["art_url"])
                GLib.idle_add(img.set_from_pixbuf if pb else img.set_from_icon_name, pb if pb else "audio-x-generic")
            threading.Thread(target=load, daemon=True).start()
        stack.set_visible_child_name("on")
    return True
def pin():
    time.sleep(1.5)
    subprocess.run(["wmctrl","-r","Now Playing","-b","add,below"], capture_output=True)
    subprocess.run(["wmctrl","-r","Now Playing","-b","add,skip_taskbar,skip_pager"], capture_output=True)
threading.Thread(target=pin, daemon=True).start()
GLib.timeout_add(1500, update); update(); win.present(); Gtk.main()
