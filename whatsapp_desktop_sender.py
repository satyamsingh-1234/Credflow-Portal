# -*- coding: utf-8 -*-
"""
CredFlow Desktop WhatsApp Web Auto-Sender
100% Free & Unlimited Automation for WhatsApp Web.
Zero third-party fees, zero per-message cost, zero contact limits.
"""

import os
import sys
import time
import json
import urllib.parse
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILE_DIR = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".credflow_whatsapp_profile")
DEFAULT_QUEUE_FILE = os.path.join(APP_DIR, "wa_desktop_queue.json")
DOWNLOADS_QUEUE_FILE = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Downloads", "wa_desktop_queue.json")


class WhatsAppAutoSenderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ CredFlow Desktop WhatsApp Auto-Sender")
        self.root.geometry("720x620")
        self.root.minsize(650, 550)
        self.root.configure(bg="#0F172A")

        self.queue_data = []
        self.is_running = False
        self.driver = None

        self._build_ui()
        self._auto_detect_queue()

    def _build_ui(self):
        # Header Frame
        header_frame = tk.Frame(self.root, bg="#1E293B", pady=14, padx=20)
        header_frame.pack(fill="x")

        lbl_title = tk.Label(
            header_frame,
            text="⚡ CredFlow Desktop WhatsApp Auto-Sender",
            font=("Segoe UI", 16, "bold"),
            fg="#38BDF8",
            bg="#1E293B"
        )
        lbl_title.pack(anchor="w")

        lbl_subtitle = tk.Label(
            header_frame,
            text="100% Free & Unlimited WhatsApp Outreach • Direct from your WhatsApp Web",
            font=("Segoe UI", 10),
            fg="#94A3B8",
            bg="#1E293B"
        )
        lbl_subtitle.pack(anchor="w", pady=(2, 0))

        # Main Container
        main_container = tk.Frame(self.root, bg="#0F172A", padx=20, pady=15)
        main_container.pack(fill="both", expand=True)

        # Queue Status Bar
        self.lbl_queue_status = tk.Label(
            main_container,
            text="📂 No Queue Loaded",
            font=("Segoe UI", 11, "bold"),
            fg="#FACC15",
            bg="#0F172A"
        )
        self.lbl_queue_status.pack(anchor="w", pady=(0, 8))

        # Action Buttons Frame
        btn_frame = tk.Frame(main_container, bg="#0F172A")
        btn_frame.pack(fill="x", pady=(0, 12))

        btn_load = tk.Button(
            btn_frame,
            text="📂 Load Queue File",
            command=self.load_queue_dialog,
            bg="#334155",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2"
        )
        btn_load.pack(side="left", padx=(0, 8))

        self.btn_start = tk.Button(
            btn_frame,
            text="🚀 Start Auto-Sending",
            command=self.start_dispatch_thread,
            bg="#10B981",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2"
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = tk.Button(
            btn_frame,
            text="⏹️ Stop",
            command=self.stop_dispatch,
            bg="#EF4444",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            state="disabled",
            cursor="hand2"
        )
        self.btn_stop.pack(side="left")

        # Delay Setting
        delay_frame = tk.Frame(btn_frame, bg="#0F172A")
        delay_frame.pack(side="right")
        tk.Label(delay_frame, text="Delay (sec):", fg="#94A3B8", bg="#0F172A", font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self.spin_delay = tk.Spinbox(delay_frame, from_=3, to=15, width=4, font=("Segoe UI", 10))
        self.spin_delay.delete(0, "end")
        self.spin_delay.insert(0, "4")
        self.spin_delay.pack(side="left")

        # Progress Bar
        self.prog_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_container, variable=self.prog_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 6))

        self.lbl_prog_text = tk.Label(
            main_container,
            text="Ready to send",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#0F172A"
        )
        self.lbl_prog_text.pack(anchor="w", pady=(0, 10))

        # Log Console Box
        tk.Label(main_container, text="📋 Live Activity Log:", font=("Segoe UI", 10, "bold"), fg="#E2E8F0", bg="#0F172A").pack(anchor="w", pady=(0, 4))
        self.txt_log = tk.Text(
            main_container,
            bg="#1E293B",
            fg="#F8FAFC",
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
            padx=10,
            pady=8
        )
        self.txt_log.pack(fill="both", expand=True)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {message}\n")
        self.txt_log.see("end")

    def _auto_detect_queue(self):
        target = None
        if os.path.exists(DOWNLOADS_QUEUE_FILE):
            target = DOWNLOADS_QUEUE_FILE
        elif os.path.exists(DEFAULT_QUEUE_FILE):
            target = DEFAULT_QUEUE_FILE

        if target:
            self._load_file(target)
        else:
            self.log("💡 Tip: In CredFlow Portal, click '📥 Export Desktop Auto-Sender Queue' to download queue.")

    def load_queue_dialog(self):
        f_path = filedialog.askopenfilename(
            title="Select CredFlow Queue File",
            filetypes=[("JSON Queue", "*.json"), ("All Files", "*.*")]
        )
        if f_path:
            self._load_file(f_path)

    def _load_file(self, f_path):
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                self.queue_data = data
                self.lbl_queue_status.config(
                    text=f"✅ Queue Loaded: {len(self.queue_data)} Customers Ready ({os.path.basename(f_path)})",
                    fg="#4ADE80"
                )
                self.log(f"Loaded {len(self.queue_data)} customers from {os.path.basename(f_path)}")
                self.lbl_prog_text.config(text=f"0 / {len(self.queue_data)} Sent (0%)")
            else:
                messagebox.showwarning("Empty Queue", "The selected file has no customers.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load queue file:\n{e}")

    def start_dispatch_thread(self):
        if not self.queue_data:
            messagebox.showwarning("No Queue", "Please load a queue file first (wa_desktop_queue.json).")
            return

        if self.is_running:
            return

        self.is_running = True
        self.btn_start.config(state="disabled", bg="#64748B")
        self.btn_stop.config(state="normal")

        t = threading.Thread(target=self._run_dispatch, daemon=True)
        t.start()

    def stop_dispatch(self):
        if self.is_running:
            self.is_running = False
            self.log("⏹️ Stopping auto-sender...")
            self.btn_stop.config(state="disabled")

    def _run_dispatch(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self.log("🚀 Initializing Chrome with persistent WhatsApp Web profile...")

        options = Options()
        options.add_argument(f"--user-data-dir={DEFAULT_PROFILE_DIR}")
        options.add_argument("--disable-notifications")
        options.add_argument("--start-maximized")

        try:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            self.log(f"❌ Failed to launch Chrome: {e}")
            self.root.after(0, self._dispatch_finished)
            return

        self.log("🌐 Opening WhatsApp Web (web.whatsapp.com)...")
        self.driver.get("https://web.whatsapp.com")

        self.log("⏳ Checking WhatsApp Web login. If QR Code is visible on screen, please scan it once from your phone.")
        login_ok = False
        for _ in range(120):
            if not self.is_running:
                break
            try:
                if self.driver.find_elements(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]') or \
                   self.driver.find_elements(By.XPATH, '//div[@id="pane-side"]') or \
                   self.driver.find_elements(By.XPATH, '//header'):
                    login_ok = True
                    break
            except Exception:
                pass
            time.sleep(1)

        if not login_ok:
            if self.is_running:
                self.log("❌ WhatsApp Web login timeout. Please scan QR and restart.")
            self.root.after(0, self._dispatch_finished)
            return

        self.log("🟢 WhatsApp Web Logged In! Starting automated queue dispatch...")

        total = len(self.queue_data)
        success_count = 0
        error_count = 0

        delay_seconds = 4
        try:
            delay_seconds = max(3, int(self.spin_delay.get()))
        except ValueError:
            delay_seconds = 4

        for idx, item in enumerate(self.queue_data):
            if not self.is_running:
                self.log("⏹️ Dispatch cancelled by user.")
                break

            name = item.get("name", "Customer")
            phone = str(item.get("phone", "")).strip()
            msg = item.get("message", "")

            clean_p = "".join(filter(str.isdigit, phone))
            if len(clean_p) > 10:
                clean_p = clean_p[-10:]

            if len(clean_p) != 10:
                self.log(f"⚠️ [{idx+1}/{total}] Skipping {name} - Invalid phone: {phone}")
                error_count += 1
                continue

            wa_num = "91" + clean_p
            encoded_msg = urllib.parse.quote(msg)
            chat_url = f"https://web.whatsapp.com/send?phone={wa_num}&text={encoded_msg}"

            self.log(f"➡️ [{idx+1}/{total}] Sending to {name} (+91 {clean_p})...")
            self.driver.get(chat_url)

            msg_sent = False
            for _ in range(25):
                if not self.is_running:
                    break
                try:
                    invalid_pop = self.driver.find_elements(By.XPATH, '//div[contains(text(), "phone number shared via url is invalid") or contains(text(), "not registered on WhatsApp")]')
                    if invalid_pop:
                        self.log(f"⚠️ [{idx+1}/{total}] {name} is NOT registered on WhatsApp.")
                        try:
                            ok_btn = self.driver.find_elements(By.XPATH, '//button//div[contains(text(), "OK")]')
                            if ok_btn:
                                ok_btn[0].click()
                        except Exception:
                            pass
                        break

                    input_boxes = self.driver.find_elements(By.XPATH, '//footer//div[@contenteditable="true"]')
                    if input_boxes:
                        box = input_boxes[0]
                        box.send_keys(Keys.ENTER)
                        msg_sent = True
                        break
                except Exception:
                    pass
                time.sleep(1)

            if msg_sent:
                success_count += 1
                self.log(f"✅ [{idx+1}/{total}] Sent successfully to {name} (+91 {clean_p})!")
            else:
                error_count += 1
                self.log(f"❌ [{idx+1}/{total}] Could not send to {name}")

            prog_percent = int(((idx + 1) / total) * 100)
            self.root.after(0, self._update_progress, prog_percent, idx + 1, total, success_count, error_count)

            if idx + 1 < total and self.is_running:
                self.log(f"⏳ Waiting {delay_seconds}s anti-spam interval...")
                time.sleep(delay_seconds)

        self.log(f"🏁 Finished dispatch! Total Sent: {success_count} ✅ | Errors: {error_count} ❌")
        self.root.after(0, self._dispatch_finished)

    def _update_progress(self, percent, curr, total, succ, err):
        self.prog_var.set(percent)
        self.lbl_prog_text.config(text=f"{curr} / {total} Processed ({percent}%) • Success: {succ} ✅ • Error: {err} ❌")

    def _dispatch_finished(self):
        self.is_running = False
        self.btn_start.config(state="normal", bg="#10B981")
        self.btn_stop.config(state="disabled")
        messagebox.showinfo("Dispatch Complete", "WhatsApp outreach finished!")


if __name__ == "__main__":
    root = tk.Tk()
    app = WhatsAppAutoSenderGUI(root)
    root.mainloop()
