#
# Pre-upload script: put the board into download mode before flashing.
#
# This board runs the ESP32-S3's native USB (ARDUINO_USB_MODE=0), which has no
# auto-reset circuit: DTR and RTS are plain CDC line-state bits here, not lines
# wired to EN/IO0 through a USB-UART bridge. esptool's --before default_reset
# therefore cannot reboot the board, and flashing otherwise means holding BOOT
# and tapping RESET by hand.
#
# The Arduino core implements the "1200bps touch" in software instead: opening
# the CDC port at 1200 baud and dropping DTR makes it restart into the ROM
# downloader. That re-enumerates the device under a different port name, so the
# new port is discovered here and handed to esptool as UPLOAD_PORT.
#
import glob
import time

Import("env")

BOOTLOADER_DESC_HINTS = ("USB JTAG/serial debug unit",)


def _ports():
    return set(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))


def before_upload(source, target, env):
    configured = env.subst("$UPLOAD_PORT")

    before = _ports()
    if not before:
        print("enter_bootloader: no serial ports found, leaving upload as-is")
        return

    # Prefer the port the user asked for; otherwise touch every candidate, since
    # the running firmware could be on any of them.
    targets = [configured] if configured in before else sorted(before)

    for port in targets:
        try:
            import serial

            handle = serial.Serial(port, 1200)
            handle.setDTR(False)
            time.sleep(0.3)
            handle.close()
            print("enter_bootloader: 1200bps touch sent to %s" % port)
        except Exception as exc:  # noqa: BLE001 - best effort, never block upload
            print("enter_bootloader: touch failed on %s (%s)" % (port, exc))

    # The downloader enumerates as a new device; wait for it to settle.
    deadline = time.time() + 10
    while time.time() < deadline:
        time.sleep(0.5)
        now = _ports()
        appeared = now - before
        if appeared:
            port = sorted(appeared)[0]
            print("enter_bootloader: download mode on %s" % port)
            env.Replace(UPLOAD_PORT=port)
            return
        # Same name came back, or it never left: nothing more to resolve.
        if now == before and time.time() > deadline - 7:
            break

    print("enter_bootloader: no new port appeared; using %s"
          % (env.subst("$UPLOAD_PORT") or "auto-detect"))


env.AddPreAction("upload", before_upload)
