import logging
import threading
import time
import psutil

logger = logging.getLogger(__name__)

class KairosEngine:
    """
    KAIROS: Event-Driven Proactive Intelligence.
    Laptop-optimized: Monitors lightweight OS events (battery, CPU spikes) 
    instead of constant screen captures.
    """
    def __init__(self, tts_callback, hud_callback):
        self.tts_callback = tts_callback
        self.hud_callback = hud_callback
        self.running = False
        self.last_battery_warning = 0
        self.last_cpu_warning = 0

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("KAIROS proactive engine started.")

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        while self.running:
            try:
                self._check_battery()
                self._check_cpu()
            except Exception as e:
                logger.error(f"KAIROS loop error: {e}")
            
            # Sleep for 60 seconds to save battery (Laptop-optimized)
            time.sleep(60)

    def _check_battery(self):
        if not hasattr(psutil, "sensors_battery"):
            return
        battery = psutil.sensors_battery()
        if not battery:
            return

        # If battery drops below 20% and not plugged in, warn user (once per hour)
        if battery.percent < 20 and not battery.power_plugged:
            now = time.time()
            if now - self.last_battery_warning > 3600:
                msg = f"Sir, your laptop battery is running low at {battery.percent} percent. I recommend plugging it in."
                self._notify(msg)
                self.last_battery_warning = now

    def _check_cpu(self):
        cpu = psutil.cpu_percent(interval=1)
        if cpu > 90:
            now = time.time()
            # Warn once every 10 minutes if CPU is slammed
            if now - self.last_cpu_warning > 600:
                msg = "Sir, system CPU usage has spiked above 90 percent."
                self._notify(msg)
                self.last_cpu_warning = now

    def _notify(self, message: str):
        logger.info(f"KAIROS PROACTIVE: {message}")
        try:
            self.tts_callback(message)
            if self.hud_callback:
                self.hud_callback({
                    "type": "kairos_alert",
                    "message": message
                })
        except Exception as e:
            logger.error(f"KAIROS notification failed: {e}")
