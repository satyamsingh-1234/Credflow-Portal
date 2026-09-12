# -*- coding: utf-8 -*-
# Updated: 2026-09-12 - High Performance Caching Enabled
import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime, date, timedelta
import sqlite3
import os
import re
import urllib.parse

st.set_page_config(
    page_title="CredFlow | Customer Adoption & Credit Analytics Portal",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DATABASE SETUP ──
LOCAL_DB_PATH = r"C:\Users\ss002\.gemini\antigravity\scratch\credflow_db\credflow_history.db"
if os.path.exists(LOCAL_DB_PATH):
    DB_PATH = LOCAL_DB_PATH
else:
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "credflow_history.db"))

conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
try:
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA busy_timeout=30000;')
except Exception:
    pass

conn.execute('''CREATE TABLE IF NOT EXISTS customer_interactions (
    phone TEXT PRIMARY KEY,
    wa_sent BOOLEAN DEFAULT 0,
    call_status TEXT,
    remarks TEXT,
    follow_up TEXT,
    issue_type TEXT DEFAULT ''
)''')

# User-defined Issue Types (editable dropdown options)
conn.execute('''CREATE TABLE IF NOT EXISTS issue_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_name TEXT UNIQUE NOT NULL
)''')

# Add issue_type column to existing DB if missing
try:
    conn.execute("ALTER TABLE customer_interactions ADD COLUMN issue_type TEXT DEFAULT ''")
except:
    pass  # Column already exists

# Seed default issue types if table is empty
cursor = conn.execute("SELECT COUNT(*) FROM issue_types")
if cursor.fetchone()[0] == 0:
    default_issues = ["Sync Issue", "Tech Issue", "Login Issue", "Payment Issue", "App Crash", "Feature Not Working", "Training Required", "Other"]
    for issue in default_issues:
        conn.execute("INSERT OR IGNORE INTO issue_types (issue_name) VALUES (?)", (issue,))
conn.commit()

# ── OUTREACH AUDIT LOGS DB SETUP ──
conn.execute('''CREATE TABLE IF NOT EXISTS outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    channel TEXT NOT NULL,
    health_tier TEXT DEFAULT '',
    customer_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    status TEXT NOT NULL,
    error_message TEXT DEFAULT ''
)''')

for col_name in ['last_email_sent_at', 'last_wa_sent_at', 'last_free_wa_sent_at', 'last_call_at']:
    try:
        conn.execute(f"ALTER TABLE customer_interactions ADD COLUMN {col_name} TEXT DEFAULT ''")
    except:
        pass
conn.commit()

def log_outreach_event(channel, health_tier, cx_name, phone, email, subject, status, error_msg=""):
    """
    Real-time logger for outreach events.
    Commits immediately so that if the page reloads mid-dispatch, sent logs are persisted up to that exact moment.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_p = str(phone).replace('.0', '').replace('+91', '').strip()
    clean_p = re.sub(r'\D', '', clean_p)
    if len(clean_p) > 10:
        clean_p = clean_p[-10:]
    
    try:
        conn.execute('''
            INSERT INTO outreach_logs (timestamp, channel, health_tier, customer_name, phone, email, subject, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now_str, str(channel), str(health_tier), str(cx_name), clean_p, str(email), str(subject), str(status), str(error_msg)))
    except Exception:
        pass
        
    if status == "SUCCESS" and clean_p:
        if "Email" in str(channel):
            conn.execute('''
                INSERT INTO customer_interactions (phone, email_sent, last_email_sent_at)
                VALUES (?, 1, ?)
                ON CONFLICT(phone) DO UPDATE SET email_sent = 1, last_email_sent_at = ?
            ''', (clean_p, now_str, now_str))
        elif "WA API" in str(channel) or "Interakt" in str(channel):
            conn.execute('''
                INSERT INTO customer_interactions (phone, wa_sent, last_wa_sent_at)
                VALUES (?, 1, ?)
                ON CONFLICT(phone) DO UPDATE SET wa_sent = 1, last_wa_sent_at = ?
            ''', (clean_p, now_str, now_str))
        elif "Free" in str(channel):
            conn.execute('''
                INSERT INTO customer_interactions (phone, free_wa_sent, last_free_wa_sent_at)
                VALUES (?, 1, ?)
                ON CONFLICT(phone) DO UPDATE SET free_wa_sent = 1, last_free_wa_sent_at = ?
            ''', (clean_p, now_str, now_str))
    try:
        conn.commit()
    except Exception:
        pass

# ── OUTREACH TEMPLATES DB SETUP ──
conn.execute('''CREATE TABLE IF NOT EXISTS outreach_templates (
    template_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    health_tier TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT NOT NULL,
    updated_at TEXT
)''')

DEFAULT_OUTREACH_TEMPLATES = {
    "email_no_usage": {
        "channel": "Email",
        "health_tier": "No Usage 🔴",
        "subject": "{name} - quick question regarding Tally setup",
        "body": """<div style="font-family: Arial, sans-serif; color: #1E293B; font-size: 14px; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 12px; padding: 28px; background-color: #FFFFFF; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
<div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #E2E8F0; margin-bottom: 20px;">
    <h2 style="color: #0F172A; margin: 0; font-size: 22px; font-weight: 800; tracking: -0.5px;">CredFlow <span style="color: #2563EB; font-weight: 400; font-size: 14px;">| Support & Onboarding</span></h2>
</div>

<p style="font-size: 15px; margin-top: 0;">Hi <b>{name}</b> 👋,</p>

<p>I am reaching out from the CredFlow Customer Success Team. I noticed your account is set up, but you haven't started using the platform to automate your payment collections yet.</p>

<!-- Stat Callouts -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin: 20px 0; border-collapse: separate; border-spacing: 10px 0;">
    <tr>
        <td width="50%" style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #1E40AF; text-transform: uppercase;">Time Saved</div>
            <div style="font-size: 18px; font-weight: 800; color: #1D4ED8; margin-top: 2px;">⚡ 10+ Hours/Wk</div>
        </td>
        <td width="50%" style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #065F46; text-transform: uppercase;">Recovery Speed</div>
            <div style="font-size: 18px; font-weight: 800; color: #047857; margin-top: 2px;">📈 40% Faster</div>
        </td>
    </tr>
</table>

<div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin: 0 0 10px 0; font-weight: bold; color: #334155; font-size: 14px;">Included Features in your {plan_name_str} plan:</p>
    {inc_html}
</div>

<!-- Support Options -->
<div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin-top: 0; margin-bottom: 10px; font-weight: bold; color: #B45309; font-size: 13px;">❓ Facing any difficulty in setup or Tally sync? Select your issue below for instant support:</p>
    <div style="text-align: center;">
        <a href="{issue_sync}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">🔄 Sync Issue</a>
        <a href="{issue_tech}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">⚙️ Tech Issue</a>
        <a href="{issue_other}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">❓ Need Training</a>
    </div>
</div>

<!-- Primary CTAs -->
<div style="text-align: center; margin: 28px 0 16px 0;">
    <a href="https://tidycal.com/m7jkyxm/credflow-product-training" style="background-color: #2563EB; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);">📅 Book 10-Min Optimization Session</a>
</div>

<div style="text-align: center; margin-bottom: 24px;">
    <a href="{wa_reply_link}" style="background-color: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold; font-size: 13px;">💬 Instant Reply on WhatsApp</a>
</div>

<hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0 16px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
    <tr>
        <td style="color: #64748B; font-size: 12px; line-height: 1.5;">
            📞 Support: <b>7217716636</b> | ✉️ Email: <b>support@credflow.in</b><br>
            Regards,<br><b style="color: #334155;">CredFlow Support Team</b>
        </td>
    </tr>
</table>
</div>"""
    },
    "email_low_usage": {
        "channel": "Email",
        "health_tier": "Low Usage 🟡",
        "subject": "{name} - quick question regarding CredFlow automation",
        "body": """<div style="font-family: Arial, sans-serif; color: #1E293B; font-size: 14px; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 12px; padding: 28px; background-color: #FFFFFF; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
<div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #E2E8F0; margin-bottom: 20px;">
    <h2 style="color: #0F172A; margin: 0; font-size: 22px; font-weight: 800; tracking: -0.5px;">CredFlow <span style="color: #D97706; font-weight: 400; font-size: 14px;">| Optimization & Growth</span></h2>
</div>

<p style="font-size: 15px; margin-top: 0;">Hi <b>{name}</b> 👋,</p>

<p>I see you’ve been using CredFlow—that’s awesome! However, our analytics show you still have several <b>untapped automation features</b> in your <b>{plan_name_str}</b> plan that can boost your cash flow.</p>

<!-- Stat Callouts -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin: 20px 0; border-collapse: separate; border-spacing: 10px 0;">
    <tr>
        <td width="50%" style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #065F46; text-transform: uppercase;">Weekly Savings</div>
            <div style="font-size: 18px; font-weight: 800; color: #047857; margin-top: 2px;">⚡ 10+ Hours</div>
        </td>
        <td width="50%" style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #1E40AF; text-transform: uppercase;">Cash Flow Impact</div>
            <div style="font-size: 18px; font-weight: 800; color: #1D4ED8; margin-top: 2px;">📈 40% Faster</div>
        </td>
    </tr>
</table>

<div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin: 0 0 10px 0; font-weight: bold; color: #334155; font-size: 14px;">Included Features Ready for Use:</p>
    {inc_html}
</div>

<!-- Support Options -->
<div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin-top: 0; margin-bottom: 10px; font-weight: bold; color: #B45309; font-size: 13px;">❓ Having any issue with sync, login or features? Select below:</p>
    <div style="text-align: center;">
        <a href="{issue_sync}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">🔄 Sync Issue</a>
        <a href="{issue_tech}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">⚙️ Tech Issue</a>
        <a href="{issue_other}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">❓ Need Training</a>
    </div>
</div>

<!-- Primary CTAs -->
<div style="text-align: center; margin: 28px 0 16px 0;">
    <a href="https://tidycal.com/m7jkyxm/credflow-product-training" style="background-color: #2563EB; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);">📅 Book 10-Min Optimization Session</a>
</div>

<div style="text-align: center; margin-bottom: 24px;">
    <a href="{wa_reply_link}" style="background-color: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold; font-size: 13px;">💬 Instant Reply on WhatsApp</a>
</div>

<hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0 16px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
    <tr>
        <td style="color: #64748B; font-size: 12px; line-height: 1.5;">
            📞 Support: <b>7217716636</b> | ✉️ Email: <b>support@credflow.in</b><br>
            Regards,<br><b style="color: #334155;">CredFlow Support Team</b>
        </td>
    </tr>
</table>
</div>"""
    },
    "email_proper_usage": {
        "channel": "Email",
        "health_tier": "Proper Usage 🟢",
        "subject": "{name} - quick question regarding WhatsApp API upgrade",
        "body": """<div style="font-family: Arial, sans-serif; color: #1E293B; font-size: 14px; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 12px; padding: 28px; background-color: #FFFFFF; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
<div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #E2E8F0; margin-bottom: 20px;">
    <h2 style="color: #0F172A; margin: 0; font-size: 22px; font-weight: 800; tracking: -0.5px;">CredFlow <span style="color: #7C3AED; font-weight: 400; font-size: 14px;">| Enterprise Automation</span></h2>
</div>

<p style="font-size: 15px; margin-top: 0;">Hi <b>{name}</b> 🚀,</p>

<p>Awesome job managing your collections with CredFlow! You are currently active on the <b>{plan_name_str}</b> plan. 👏</p>

<!-- Stat Callouts -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin: 20px 0; border-collapse: separate; border-spacing: 10px 0;">
    <tr>
        <td width="50%" style="background-color: #F3E8FF; border: 1px solid #DDD6FE; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #6D28D9; text-transform: uppercase;">Official WA API</div>
            <div style="font-size: 18px; font-weight: 800; color: #5B21B6; margin-top: 2px;">📲 Green Tick</div>
        </td>
        <td width="50%" style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #1E40AF; text-transform: uppercase;">AI Accountant</div>
            <div style="font-size: 18px; font-weight: 800; color: #1D4ED8; margin-top: 2px;">🤖 Auto OCR</div>
        </td>
    </tr>
</table>

<div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin: 0 0 8px 0; font-weight: bold; color: #166534; font-size: 13px;">✅ Your Active Plan Features:</p>
    {inc_html}
    <hr style="border: none; border-top: 1px dashed #CBD5E1; margin: 12px 0;">
    <p style="margin: 0 0 8px 0; font-weight: bold; color: #6D28D9; font-size: 13px;">🚀 Higher Automation Available on Upgrade:</p>
    {miss_html}
</div>

<!-- Support Options -->
<div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-radius: 8px; padding: 16px; margin: 20px 0;">
    <p style="margin-top: 0; margin-bottom: 10px; font-weight: bold; color: #B45309; font-size: 13px;">❓ Have any pending query or issue? Select below:</p>
    <div style="text-align: center;">
        <a href="{issue_sync}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">🔄 Sync Issue</a>
        <a href="{issue_tech}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">⚙️ Tech Issue</a>
        <a href="{issue_other}" style="display: inline-block; margin: 4px; padding: 8px 14px; background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">❓ Need Training</a>
    </div>
</div>

<!-- Primary CTAs -->
<div style="text-align: center; margin: 28px 0 16px 0;">
    <a href="https://tidycal.com/m7jkyxm/book-your-session-for-whatsapp-api" style="background-color: #7C3AED; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 15px; box-shadow: 0 4px 10px rgba(124, 58, 237, 0.3);">📲 Book WhatsApp API Session</a>
</div>

<div style="text-align: center; margin-bottom: 24px;">
    <a href="{wa_upg_link}" style="background-color: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold; font-size: 13px;">💬 Request Upgrade via WhatsApp</a>
</div>

<hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0 16px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
    <tr>
        <td style="color: #64748B; font-size: 12px; line-height: 1.5;">
            📞 Support: <b>7217716636</b> | ✉️ Email: <b>support@credflow.in</b><br>
            Regards,<br><b style="color: #334155;">CredFlow Support Team</b>
        </td>
    </tr>
</table>
</div>"""
    },
    "wa_free_no_usage": {
        "channel": "Free WhatsApp",
        "health_tier": "No Usage 🔴",
        "subject": "",
        "body": """Hi {name} Sir 👋,

Main CredFlow Support Team se baat kar raha hoon. Aapke account ka setup complete ho chuka hai, lekin lagta hai aapne abhi software use karna start nahi kiya hai.{feat_section}

Kya aapko login, Tally sync ya setup mein koi difficulty aa rahi hai? 

👇 **Quick Action Links (Click to reply):**
💬 **Request Setup Callback**: {reply_link}
📅 **Book Free Training**: https://tidycal.com/m7jkyxm/credflow-product-training
📲 **Book Session for WhatsApp API**: https://tidycal.com/m7jkyxm/book-your-session-for-whatsapp-api
🔑 **Login to App**: https://app.credflow.in

Support: 7217716636 | Email: support@credflow.in

Regards,
CredFlow Support Team"""
    },
    "wa_free_low_usage": {
        "channel": "Free WhatsApp",
        "health_tier": "Low Usage 🟡",
        "subject": "",
        "body": """Hi {name} Sir 👋,

Main CredFlow Support Team se baat kar raha hoon. Humne dekha ki aapka account active hai, par aapne abhi tak apne plan ke features ka 100% fayda nahi uthaya hai.{feat_section}

⚡ **Automation Optimization Call:**
Humari team se 10-min ke quick session mein apne automated payment reminders set karwayein taaki collections 30% faster hon.

👇 **Quick Action Links (Click to reply):**
💬 **Request Optimization Session**: {reply_link}
📅 **Book Free Training**: https://tidycal.com/m7jkyxm/credflow-product-training
📲 **Book Session for WhatsApp API**: https://tidycal.com/m7jkyxm/book-your-session-for-whatsapp-api
🔑 **Login to App**: https://app.credflow.in

Support: 7217716636 | Email: support@credflow.in

Regards,
CredFlow Support Team"""
    },
    "wa_free_proper_usage": {
        "channel": "Free WhatsApp",
        "health_tier": "Proper Usage 🟢",
        "subject": "",
        "body": """Hi {name} Sir 🚀,

Great job! Aap CredFlow ({plan_name}) active use kar rahe hain aur apne collections manage kar rahe hain. 👏

{inc_sec}{upg_sec}

In advanced features (AI Accountant & WhatsApp API) ko unlock karke billing aur collections 100% automate karne ke liye aaj hi plan upgrade karein!

👇 **Quick Action Links (Click to Upgrade via WhatsApp):**
⚡ **Request Plan Upgrade**: {upg_link}
🚀 **Book Upgrade Call (WhatsApp)**: {upg_link}
📅 **Book Free Training**: https://tidycal.com/m7jkyxm/credflow-product-training
📲 **Book Session for WhatsApp API**: https://tidycal.com/m7jkyxm/book-your-session-for-whatsapp-api
🔑 **Login to App**: https://app.credflow.in

Support: 7217716636 | Email: support@credflow.in

Regards,
CredFlow Support Team"""
    },
    "interakt_no_usage": {
        "channel": "Interakt WA API",
        "health_tier": "No Usage 🔴",
        "subject": "credflow_no_usage",
        "body": "Hi {{1}}, Your CredFlow account setup is complete. Contact support for login/sync help."
    },
    "interakt_low_usage": {
        "channel": "Interakt WA API",
        "health_tier": "Low Usage 🟡",
        "subject": "credflow_low_usage",
        "body": "Hi {{1}}, you have {{2}} credits remaining. Activate automated payment reminders to save 10+ hours a week."
    },
    "interakt_proper_usage": {
        "channel": "Interakt WA API",
        "health_tier": "Proper Usage 🟢",
        "subject": "credflow_proper_usage",
        "body": "Hi {{1}}, you have used {{2}} credits. Upgrade to WhatsApp API & AI Accountant for 100% automation."
    }
}

for t_id, data in DEFAULT_OUTREACH_TEMPLATES.items():
    cursor = conn.execute("SELECT COUNT(*) FROM outreach_templates WHERE template_id = ?", (t_id,))
    if cursor.fetchone()[0] == 0:
        conn.execute("INSERT INTO outreach_templates (template_id, channel, health_tier, subject, body, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (t_id, data["channel"], data["health_tier"], data["subject"], data["body"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    else:
        conn.execute("UPDATE outreach_templates SET channel=?, health_tier=?, subject=?, body=?, updated_at=? WHERE template_id=?",
                     (data["channel"], data["health_tier"], data["subject"], data["body"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
conn.commit()

def fetch_template(t_id):
    """Fetches template record from SQLite database with fallback to default."""
    try:
        cur = conn.execute("SELECT template_id, channel, health_tier, subject, body FROM outreach_templates WHERE template_id = ?", (t_id,))
        row = cur.fetchone()
        if row:
            return {"template_id": row[0], "channel": row[1], "health_tier": row[2], "subject": row[3], "body": row[4]}
    except Exception:
        pass
    return DEFAULT_OUTREACH_TEMPLATES.get(t_id, {"subject": "", "body": ""})

def fill_template_vars(template_str, var_dict):
    """Safely replaces variable placeholders in template string without throwing KeyError on CSS curly braces."""
    result = str(template_str)
    for key, val in var_dict.items():
        result = result.replace("{" + key + "}", str(val))
    return result

# ── LOGO SETUP ──
import base64
LOGO_PATH = os.path.join(os.path.dirname(__file__), "credflow_logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = r"C:\Users\ss002\.gemini\antigravity\scratch\credflow_ppt\credflow_logo.png"

logo_src = ""
if os.path.exists(LOGO_PATH):
    try:
        with open(LOGO_PATH, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_src = f"data:image/png;base64,{logo_b64}"
    except Exception:
        logo_src = ""

@st.cache_data(show_spinner=False)
def fetch_history_batch(batch_name):
    """Aggressively cache the massive history read to prevent UI slowdowns on filter changes."""
    with sqlite3.connect(DB_PATH, timeout=30.0) as temp_conn:
        return pd.read_sql("SELECT * FROM sales_plan_history WHERE Upload_Batch = ?", temp_conn, params=(batch_name,))

@st.cache_data(show_spinner=False)
def fetch_all_history():
    """Aggressively cache full master dataset read (25,112 rows) to make Overall Data & date filters instant."""
    with sqlite3.connect(DB_PATH, timeout=30.0) as temp_conn:
        return pd.read_sql("SELECT * FROM sales_plan_history", temp_conn)

st.markdown("""
<style>
    /* Global Font & Professional Baseline */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Clean App Background */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Scrollbar Polish */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #F1F5F9;
    }
    ::-webkit-scrollbar-thumb {
        background: #CBD5E1;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #94A3B8;
    }
    
    /* Executive Metric Card Styling */
    div[data-testid="stMetric"] {
        background: #FFFFFF !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.02) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 16px -4px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04) !important;
        border-color: #CBD5E1 !important;
    }
    div[data-testid="stMetricLabel"] > div {
        font-size: 11.5px !important;
        font-weight: 700 !important;
        color: #64748B !important;
        text-transform: uppercase !important;
        letter-spacing: 0.6px !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 25px !important;
        font-weight: 800 !important;
        color: #0F172A !important;
    }

    /* Floating Pill Tabs Navigation */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #F1F5F9;
        padding: 6px 8px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 8px;
        padding: 0 20px;
        font-weight: 600;
        font-size: 13.5px;
        color: #64748B;
        border: none !important;
        background-color: transparent;
        transition: all 0.15s ease-in-out;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2563EB !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.06) !important;
    }

    /* Professional Headings & Labels */
    h1, h2, h3 { 
        color: #0F172A !important; 
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }
    label {
        font-weight: 600 !important;
        color: #334155 !important;
        font-size: 13px !important;
    }

    /* Inputs & Dropdowns */
    div[data-baseweb="input"], div[data-baseweb="select"] {
        border-radius: 8px !important;
    }
    
    /* Clean Expander Header */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        font-weight: 600 !important;
        color: #1E293B !important;
        padding: 12px 18px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
    }
    
    /* Rounded DataFrames */
    .stDataFrame { 
        border-radius: 12px !important; 
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        overflow: hidden !important; 
    }
    
    /* Primary Gradient Buttons */
    .stButton button[kind="primary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25) !important;
        transition: all 0.15s ease-in-out !important;
    }
    .stButton button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35) !important;
    }

    /* Secondary Buttons */
    .stButton button[kind="secondary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: 1px solid #CBD5E1 !important;
        background: #FFFFFF !important;
        color: #334155 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.15s ease-in-out !important;
    }
    .stButton button[kind="secondary"]:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
    }

    /* Alert Boxes */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

logo_badge_html = f'<img src="{logo_src}" style="height: 46px; width: 46px; border-radius: 10px; box-shadow: 0 4px 12px rgba(37,99,235,0.4); vertical-align: middle; object-fit: cover; border: 1.5px solid rgba(255,255,255,0.2);">' if logo_src else '<span style="background: linear-gradient(135deg, #2563EB, #3B82F6); padding: 8px 12px; border-radius: 10px; font-size: 20px; box-shadow: 0 4px 10px rgba(37,99,235,0.4);">📊</span>'

st.markdown(f"""
<div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); padding: 22px 28px; border-radius: 16px; margin-bottom: 22px; box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2); border: 1px solid #334155; position: relative;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
        <div>
            <div style="color: #FFFFFF; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; margin: 0; display: flex; align-items: center; gap: 12px;">
                {logo_badge_html}
                Credflow SaaS Customer Usage Dashboard
            </div>
            <div style="color: #94A3B8; font-size: 13.5px; font-weight: 500; margin-top: 6px;">
                Automated Customer Usage Health Evaluation &bull; Interakt WhatsApp API &bull; Single-Click Outreach & CRM Workflow
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <div style="background: rgba(37, 99, 235, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); padding: 6px 14px; border-radius: 20px; color: #60A5FA; font-weight: 700; font-size: 12px; display: flex; align-items: center; gap: 6px;">
                <span style="height: 8px; width: 8px; background-color: #10B981; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #10B981;"></span>
                Enterprise SaaS Portal v3.0
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

def create_progress_ui(title):
    ph = st.empty()
    def update_ui(curr, total, name, succ, err):
        if total == 0: return
        pct = int((curr / total) * 100)
        ph.markdown(f"""
        <div style="padding:15px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); margin-bottom:15px;">
            <h4 style="margin-top:0; margin-bottom:10px; color:#1e293b; font-family:sans-serif;">🚀 {title}</h4>
            <div style="background-color:#e2e8f0; border-radius:5px; height:10px; width:100%; margin-bottom:10px;">
                <div style="background-color:#3b82f6; width:{pct}%; height:100%; border-radius:5px; transition: width 0.3s ease;"></div>
            </div>
            <p style="margin:5px 0; font-family:sans-serif; color:#334155;">Processing: <b>{curr} / {total}</b> <span style="color:#64748b; font-size:14px;">(Current: {name})</span></p>
            <div style="display:flex; gap:20px; font-size: 16px; margin-top:10px; font-family:sans-serif;">
                <span style="color:#16a34a; font-weight:bold;">✅ Success: {succ}</span>
                <span style="color:#dc2626; font-weight:bold;">❌ Error: {err}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    return ph, update_ui

# ── FEATURE MAP DICTIONARY ──
# Yahan par CredFlow ke sabhi plans aur unke included features likhe hue hain.
# AGAR KOI NAYA PLAN ADD KARNA HO: Yahan dictionary mein ek naya key-value pair daal dein.
# AGAR KISI PLAN KE FEATURES CHANGE KARNE HON: Us plan ke aage brackets [...] ke andar features change kar dein.
FEATURE_MAP = {
    "BVP": [
        "Invoice Autosharing: WhatsApp", "Tally Backup", "Payment Remainder Email",
        "Payment Remainder SMS", "Payment Remainder IVR", "Payment Remainder Whatsapp",
        "Unlimited Device Access", "Mange CRM", "3 Users", "3 Organisations", "10000 Credits"
    ],
    "SAVER": [
        "Payment Remainder Email", "Payment Remainder SMS", "Payment Remainder IVR",
        "Unlimited Device Access", "2 Users", "2 Organisations", "7000 Credits"
    ],
    "LITE": [
        "Payment Remainder Email", "Payment Remainder SMS", "Payment Remainder IVR",
        "1 Users", "1 Organisations", "1000 Credits"
    ],
    "PREMIUM": [
        "Invoice Autosharing: WhatsApp", "Payment Remainder Email", "Payment Remainder SMS",
        "Payment Remainder IVR", "Payment Remainder Whatsapp", "Unlimited Device Access",
        "Mange CRM", "3 Users", "3 Organisations", "10000 Credits"
    ],
    "PRO": [
        "Payment Remainder Email", "Payment Remainder SMS", "Payment Remainder IVR",
        "Unlimited Device Access", "2 Users", "2 Organisations", "7000 Credits"
    ],
    "BASIC": [
        "Payment Remainder Email", "Payment Remainder SMS", "Payment Remainder IVR",
        "1 Users", "1 Organisations", "1000 Credits"
    ],
    "AI ACCOUNTANT": [
        "Invoice Autosharing: WhatsApp", "Tally Backup", "Payment Remainder Email",
        "Payment Remainder SMS", "Payment Remainder IVR", "Payment Remainder whatsapp",
        "Unlimited Device Access", "Mange CRM", "Conversation Flow",
        "Send whats App Bulk Message", "Manage Reports", "Eway- Einvoice",
        "Bill Reader Scanner", "Bank Statement Scanner", "5 Users", "5 Organisations", "20000 Credits"
    ],
    "WHATSAPP API-SILVER": [
        "Conversation Flow", "Send whats App Bulk Message", "3500 Credits"
    ],
    "WHATSAPP API-GOLD": [
        "Conversation Flow", "Send whats App Bulk Message", "Send and Schedule Marketing Campaign",
        "Customer Segmentation", "Manage Reports", "7000 Credits"
    ],
    "WHATSAPP API-PLATINUM": [
        "Conversation Flow", "Send whats App Bulk Message", "Send and Schedule Marketing Campaign",
        "Customer Segmentation", "Manage Reports", "Chat Bot", "Blue Tick", "10000 Credits"
    ]
}

def resolve_features_for_plan(plan_name_str):
    if not plan_name_str or str(plan_name_str).strip() == "" or str(plan_name_str).lower() == "nan":
        return []
    
    plan_parts = [p.strip() for p in str(plan_name_str).split(',')]
    features = []
    
    for part in plan_parts:
        pu = part.upper()
        part_matched = False
        
        if 'AI ACCOUNTANT' in pu:
            features.extend(FEATURE_MAP['AI ACCOUNTANT'])
            part_matched = True
        elif 'BVP' in pu:
            features.extend(FEATURE_MAP['BVP'])
            part_matched = True
        elif 'PREMIUM' in pu:
            features.extend(FEATURE_MAP['PREMIUM'])
            part_matched = True
        elif 'SAVER' in pu:
            features.extend(FEATURE_MAP['SAVER'])
            part_matched = True
        elif 'PRO' in pu:
            features.extend(FEATURE_MAP['PRO'])
            part_matched = True
        elif 'LITE' in pu:
            features.extend(FEATURE_MAP['LITE'])
            part_matched = True
        elif 'BASIC' in pu:
            features.extend(FEATURE_MAP['BASIC'])
            part_matched = True
            
        if 'WHATSAPP' in pu or 'WA' in pu:
            if 'SILVER' in pu:
                features.extend(FEATURE_MAP['WHATSAPP API-SILVER'])
                part_matched = True
            elif 'GOLD' in pu:
                features.extend(FEATURE_MAP['WHATSAPP API-GOLD'])
                part_matched = True
            elif 'PLATINUM' in pu:
                features.extend(FEATURE_MAP['WHATSAPP API-PLATINUM'])
                part_matched = True
            elif 'AUTOMATION' in pu:
                features.extend(['Invoice Autosharing: WhatsApp', 'Payment Remainder Whatsapp'])
                part_matched = True
                
        if 'E-WAY' in pu or 'E-INVOICE' in pu or 'EWAY' in pu or 'EINVOICE' in pu:
            features.append('Eway- Einvoice')
            part_matched = True
        if 'BILL READER' in pu or 'BANK STATEMENT' in pu or 'SCANNER' in pu:
            features.extend(['Bill Reader Scanner', 'Bank Statement Scanner'])
            part_matched = True
        if 'TALLY BACK' in pu:
            features.append('Tally Backup')
            part_matched = True
        if 'USER' in pu or 'ORGANIZATION' in pu or 'ORGANISATION' in pu:
            features.append('Additional Users & Organisations')
            part_matched = True
        if 'CREDIT' in pu:
            features.append('Additional Credits')
            part_matched = True
            
        if not part_matched and part != "":
            features.append(part)
            
    seen = set()
    return [x for x in features if not (x in seen or seen.add(x))]

def eval_plan_credits_and_score(plan_name, c_val):
    """Evaluates CP Usage label and points based on Plan Tier (Lite/Pro/Enterprise)"""
    pn = str(plan_name).upper()
    if any(k in pn for k in ['LITE', 'BASIC', 'STARTER']):
        tier = 'LITE'
    elif any(k in pn for k in ['SAVER', 'PRO']):
        tier = 'PRO'
    else:
        tier = 'ENTERPRISE'

    if tier == 'LITE':
        if c_val > 100:
            return "More than 100", 3
        elif c_val >= 30:
            return "B/W 30 to 100", 2
        elif c_val > 0:
            return "less than 30", 0
        else:
            return "None", 0
    elif tier == 'PRO':
        if c_val > 500:
            return "More than 500", 3
        elif c_val >= 200:
            return "B/W 200 to 500", 2
        elif c_val > 0:
            return "less than 200", 0
        else:
            return "None", 0
    else: # ENTERPRISE / PREMIUM / BVP
        if c_val > 1000:
            return "More than 1000", 3
        elif c_val >= 500:
            return "B/W 500 to 1000", 2
        elif c_val > 0:
            return "less than 500", 0
        else:
            return "None", 0

def extract_clean_features_from_row(r):
    all_f = str(r.get('All Features', '')).strip()
    features = []
    if all_f and all_f.lower() != 'nan':
        parts = [p.strip() for p in all_f.split(',')]
        features = [p for p in parts if p and p.lower() not in ['yes', 'no', 'nan', 'none']]
    
    plan_name = str(r.get('plan name', '')).strip()
    plan_feats = resolve_features_for_plan(plan_name)
    combined = features + plan_feats
    seen = set()
    return [x for x in combined if not (x in seen or seen.add(x))]

ADVANCED_UPGRADE_FEATURES = [
    "Invoice Autosharing: WhatsApp",
    "Tally Backup",
    "Payment Remainder Whatsapp",
    "Send whats App Bulk Message",
    "Eway- Einvoice",
    "Bill Reader Scanner",
    "Bank Statement Scanner",
    "Conversation Flow (WhatsApp API)"
]

def to_excel_download(df_to_export, sheet_name="CredFlow Data"):
    import io
    import pandas as pd
    
    cols_to_drop = ['📩 Send API', '📨 Send Email', '📱 Send Free WA', 'merge_phone', 'WhatsApp']
    clean_df = df_to_export.drop(columns=[c for c in cols_to_drop if c in df_to_export.columns], errors='ignore')
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        clean_df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer.getvalue()

def build_feature_tick_lists(r):
    feats = extract_clean_features_from_row(r)
    included = [f"✅ {f}" for f in feats]
    
    feats_lower = [f.lower() for f in feats]
    missing = []
    for adv in ADVANCED_UPGRADE_FEATURES:
        if not any(adv.lower() in fl for fl in feats_lower):
            missing.append(f"❌ {adv}")
            
    return included, missing

# ── AUTOMATED CALLBACK SUPPORT EMAIL ALERT ──
def send_callback_support_email(cx_name, cx_phone, cx_email, plan_name, follow_up_date, remarks, callback_time="", agent_email="satyam.kumar@credflow.in"):
    import smtplib
    from email.message import EmailMessage
    import re

    EMAIL_ADDRESS = "support@credflow.in"
    EMAIL_PASSWORD = "slvyzkzxpsjaofxc"

    if not agent_email or not str(agent_email).strip():
        agent_email = "satyam.kumar@credflow.in"

    clean_p = str(cx_phone).replace('.0', '').replace('+91', '').strip()
    wa_phone = re.sub(r'\D', '', clean_p)
    if len(wa_phone) > 10: wa_phone = wa_phone[-10:]
    wa_link = f"https://wa.me/91{wa_phone}" if wa_phone else "https://wa.me/917217716636"

    time_str = f" at {callback_time}" if callback_time else ""
    date_str = str(follow_up_date) if follow_up_date and str(follow_up_date).strip() not in ['', 'None', 'NaT'] else "Scheduled Time"

    msg = EmailMessage()
    msg['From'] = f"CredFlow Support <{EMAIL_ADDRESS}>"
    
    # Recipient & CC Setup
    cc_list = ["support@credflow.in"]
    if agent_email and "@" in str(agent_email) and str(agent_email).strip().lower() != "support@credflow.in":
        cc_list.append(str(agent_email).strip())

    if cx_email and "@" in str(cx_email) and str(cx_email).lower() != 'nan':
        msg['To'] = str(cx_email).strip()
        msg['Cc'] = ", ".join(cc_list)
    else:
        msg['To'] = "support@credflow.in"
        if len(cc_list) > 1:
            msg['Cc'] = ", ".join([c for c in cc_list if c != "support@credflow.in"])

    if agent_email and "@" in str(agent_email):
        msg['Reply-To'] = f"{str(agent_email).strip()}, support@credflow.in"
    else:
        msg['Reply-To'] = "support@credflow.in"

    msg['Subject'] = f"⏰ Support Ticket & Callback Request: {cx_name} ({cx_phone}) - Scheduled {date_str}{time_str}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #1E293B; font-size: 14px; line-height: 1.6; max-width: 580px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 10px; padding: 24px; background-color: #FFFFFF;">
        <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 14px; border-radius: 4px; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #92400E; font-size: 18px;">⏰ Customer Callback Request Alert</h3>
            <p style="margin: 4px 0 0 0; color: #78350F; font-size: 13px;">A customer has requested a callback. Details are logged below:</p>
        </div>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B; width: 40%;">Customer Name:</td><td style="padding: 8px 0; font-weight: bold; color: #0F172A;">{cx_name}</td></tr>
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B;">Phone / Contact:</td><td style="padding: 8px 0; font-weight: bold; color: #2563EB;">{cx_phone}</td></tr>
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B;">Email Address:</td><td style="padding: 8px 0; color: #0F172A;">{cx_email or 'N/A'}</td></tr>
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B;">Plan Name:</td><td style="padding: 8px 0; color: #0F172A;">{plan_name or 'N/A'}</td></tr>
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B;">Callback Scheduled:</td><td style="padding: 8px 0; font-weight: bold; color: #D97706;">📅 {date_str}{time_str}</td></tr>
            <tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 8px 0; font-weight: bold; color: #64748B;">Telecaller Remarks:</td><td style="padding: 8px 0; color: #0F172A;">{remarks or 'No specific notes'}</td></tr>
        </table>

        <div style="text-align: center; margin: 20px 0;">
            <a href="{wa_link}" style="background-color: #25D366; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">💬 Open WhatsApp Chat with Customer</a>
        </div>

        <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 20px 0;">
        <p style="margin: 0; color: #94A3B8; font-size: 12px;">Automated Alert from CredFlow Master Telecalling CRM</p>
    </div>
    """

    msg.set_content("Please enable HTML to view this email.")
    msg.add_alternative(html_content, subtype='html')

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True, "Support Email Alert Sent"
    except Exception as ex:
        return False, str(ex)


# ── FREE WHATSAPP TEMPLATES ──
def generate_wa_link(r):
    import urllib.parse
    import re
    name = str(r.get('Name', '')).title()
    health = str(r.get('Usage check', ''))
    credits = str(r.get('raw_credits', '0'))
    phone = str(r.get('phone', '')).strip()
    plan_name = str(r.get('plan name', '')).strip()
    if not phone: return None
    
    clean_p = str(phone).replace('.0', '').replace('+91', '').strip()
    wa_phone = re.sub(r'\D', '', clean_p)
    if len(wa_phone) > 10: wa_phone = wa_phone[-10:]
    if len(wa_phone) == 10: wa_phone = "91" + wa_phone
    else: return None

    inc_list, miss_list = build_feature_tick_lists(r)
    inc_bullet = "\n".join(inc_list) if inc_list else ""
    miss_bullet = "\n".join(miss_list) if miss_list else ""
        
    if "No Usage" in health:
        tpl_data = fetch_template("wa_free_no_usage")
        reply_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe apne {plan_name} account ka setup aur login karne mein help chahiye.")
        reply_link = f"https://wa.me/917217716636?text={reply_txt}"
        feat_section = f"\n\n💡 Aapke plan ({plan_name}) mein ye features included hain:\n{inc_bullet}" if inc_bullet else ""
        
        msg = fill_template_vars(tpl_data.get("body", ""), {
            "name": name,
            "plan_name": plan_name,
            "feat_section": feat_section,
            "reply_link": reply_link
        })
    elif "Low Usage" in health:
        tpl_data = fetch_template("wa_free_low_usage")
        reply_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe apne {plan_name} account ke features ko fully use karne ke liye training/help chahiye.")
        reply_link = f"https://wa.me/917217716636?text={reply_txt}"
        feat_section = f"\n\n✅ Aapke plan ({plan_name}) ke current features:\n{inc_bullet}" if inc_bullet else ""
        
        msg = fill_template_vars(tpl_data.get("body", ""), {
            "name": name,
            "plan_name": plan_name,
            "feat_section": feat_section,
            "reply_link": reply_link
        })
    else:
        tpl_data = fetch_template("wa_free_proper_usage")
        upg_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe mera {plan_name} account AI Accountant / WhatsApp API par UPGRADE karna hai. Details share karein.")
        upg_link = f"https://wa.me/917217716636?text={upg_txt}"
        
        inc_sec = f"✅ **Aapke Active Plan ({plan_name}) ke Included Features:**\n{inc_bullet}" if inc_bullet else ""
        upg_sec = f"\n\n🚀 **Unlock 100% Automation (Higher Features Available for Upgrade):**\n{miss_bullet}" if miss_bullet else ""
        
        msg = fill_template_vars(tpl_data.get("body", ""), {
            "name": name,
            "plan_name": plan_name,
            "inc_sec": inc_sec,
            "upg_sec": upg_sec,
            "upg_link": upg_link
        })
    encoded_msg = urllib.parse.quote(msg)
    return f"https://web.whatsapp.com/send?phone={wa_phone}&text={encoded_msg}"


# ── INTERAKT WHATSAPP API LOGIC ──
def send_interakt_msg(phone, name, health, credits):
    import requests
    import re
    
    clean_p = str(phone).replace('.0', '').replace('+91', '').strip()
    wa_phone = re.sub(r'\D', '', clean_p)
    if len(wa_phone) > 10:
        wa_phone = wa_phone[-10:]
        
    if len(wa_phone) == 10:
        c_code = "+91"
        p_num = wa_phone
    else:
        return False, f"Invalid phone number length ({phone})"
        
    if "No Usage" in str(health):
        tpl_data = fetch_template("interakt_no_usage")
        tpl = tpl_data.get("subject", "credflow_no_usage")
        body_vals = [str(name).title()]
    elif "Low Usage" in str(health):
        tpl_data = fetch_template("interakt_low_usage")
        tpl = tpl_data.get("subject", "credflow_low_usage")
        body_vals = [str(name).title(), str(credits)]
    else:
        tpl_data = fetch_template("interakt_proper_usage")
        tpl = tpl_data.get("subject", "credflow_proper_usage")
        body_vals = [str(name).title(), str(credits)]
        
    payload = {
        "countryCode": c_code,
        "phoneNumber": p_num,
        "type": "Template",
        "template": {
            "name": tpl,
            "languageCode": "en",
            "bodyValues": body_vals
        }
    }
    
    headers = {
        "Authorization": "Basic RHFqbG9icEFxYkRBOGdLdVVXaUtjRDBiaGxITHJwOElGQUZzUkVKMEFEMDo=",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post("https://api.interakt.ai/v1/public/message/", headers=headers, json=payload, timeout=10)
        if resp.status_code in [200, 201, 202]:
            return True, resp.text
        else:
            err_txt = resp.text
            if "wallet" in err_txt.lower() or "recharge" in err_txt.lower() or "balance" in err_txt.lower():
                return False, "WALLET_INSUFFICIENT_BALANCE"
            return False, f"HTTP {resp.status_code}: {err_txt}"
    except Exception as e:
        return False, str(e)


# ── BULK EMAIL LOGIC & TEMPLATES ──
def send_bulk_emails(selected_rows_data, progress_callback=None):
    import smtplib
    from email.message import EmailMessage

    EMAIL_ADDRESS = "support@credflow.in"
    EMAIL_PASSWORD = "slvyzkzxpsjaofxc"

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        
        successful_phones = []
        total_count = len(selected_rows_data)
        success_count = 0
        error_count = 0

        for idx, row in enumerate(selected_rows_data):
            name = str(row.get('Name', '')).title()
            email_to = str(row.get('email', '')).strip()
            health = str(row.get('Usage check', ''))
            phone_str = str(row.get('phone', '')).strip()
            plan_name_str = str(row.get('plan name', '')).strip()

            if not email_to or "@" not in email_to:
                error_count += 1
                if progress_callback:
                    progress_callback(idx + 1, total_count, name, success_count, error_count)
                continue

            inc_list, miss_list = build_feature_tick_lists(row)
            inc_html = "<ul style='list-style-type: none; padding-left: 0;'>" + "".join([f"<li style='margin-bottom: 5px; color: #047857;'><b>{f}</b></li>" for f in inc_list]) + "</ul>" if inc_list else ""
            miss_html = "<ul style='list-style-type: none; padding-left: 0;'>" + "".join([f"<li style='margin-bottom: 5px; color: #DC2626;'><b>{f}</b></li>" for f in miss_list]) + "</ul>" if miss_list else ""

            msg = EmailMessage()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email_to

            if "No Usage" in health:
                tpl_data = fetch_template("email_no_usage")
                wa_reply_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe apne {plan_name_str} account ka setup aur login karne mein help chahiye.")
                wa_reply_link = f"https://wa.me/917217716636?text={wa_reply_txt}"
                
                issue_sync = f"mailto:support@credflow.in?subject=Sync%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Sync%20Issue."
                issue_tech = f"mailto:support@credflow.in?subject=Tech%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Technical%20Issue."
                issue_other = f"mailto:support@credflow.in?subject=Other%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20an%20Issue."

                sub_template = tpl_data.get("subject", "{name} - quick question regarding Tally setup")
                body_template = tpl_data.get("body", "")

                msg['Subject'] = fill_template_vars(sub_template, {"name": name, "plan_name_str": plan_name_str})
                body = fill_template_vars(body_template, {
                    "name": name,
                    "plan_name_str": plan_name_str,
                    "inc_html": inc_html,
                    "miss_html": miss_html,
                    "issue_sync": issue_sync,
                    "issue_tech": issue_tech,
                    "issue_other": issue_other,
                    "wa_reply_link": wa_reply_link,
                    "wa_upg_link": wa_reply_link
                })
            elif "Low Usage" in health:
                tpl_data = fetch_template("email_low_usage")
                wa_reply_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe apne {plan_name_str} account ke features ko fully use karne ke liye training/help chahiye.")
                wa_reply_link = f"https://wa.me/917217716636?text={wa_reply_txt}"

                issue_sync = f"mailto:support@credflow.in?subject=Sync%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Sync%20Issue."
                issue_tech = f"mailto:support@credflow.in?subject=Tech%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Technical%20Issue."
                issue_other = f"mailto:support@credflow.in?subject=Other%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20an%20Issue."

                sub_template = tpl_data.get("subject", "{name} - quick question regarding CredFlow automation")
                body_template = tpl_data.get("body", "")

                msg['Subject'] = fill_template_vars(sub_template, {"name": name, "plan_name_str": plan_name_str})
                body = fill_template_vars(body_template, {
                    "name": name,
                    "plan_name_str": plan_name_str,
                    "inc_html": inc_html,
                    "miss_html": miss_html,
                    "issue_sync": issue_sync,
                    "issue_tech": issue_tech,
                    "issue_other": issue_other,
                    "wa_reply_link": wa_reply_link,
                    "wa_upg_link": wa_reply_link
                })
            else:
                tpl_data = fetch_template("email_proper_usage")
                wa_upg_txt = urllib.parse.quote(f"Hi CredFlow Team, main {name} hu. Mujhe mera {plan_name_str} account AI Accountant / WhatsApp API par UPGRADE karna hai. Details share karein.")
                wa_upg_link = f"https://wa.me/917217716636?text={wa_upg_txt}"
                
                issue_sync = f"mailto:support@credflow.in?subject=Sync%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Sync%20Issue."
                issue_tech = f"mailto:support@credflow.in?subject=Tech%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20a%20Technical%20Issue."
                issue_other = f"mailto:support@credflow.in?subject=Other%20Issue%20-%20{name.replace(' ', '%20')}&body=I%20am%20facing%20an%20Issue."

                sub_template = tpl_data.get("subject", "{name} - quick question regarding WhatsApp API upgrade")
                body_template = tpl_data.get("body", "")

                msg['Subject'] = fill_template_vars(sub_template, {"name": name, "plan_name_str": plan_name_str})
                body = fill_template_vars(body_template, {
                    "name": name,
                    "plan_name_str": plan_name_str,
                    "inc_html": inc_html,
                    "miss_html": miss_html,
                    "issue_sync": issue_sync,
                    "issue_tech": issue_tech,
                    "issue_other": issue_other,
                    "wa_reply_link": wa_upg_link,
                    "wa_upg_link": wa_upg_link
                })

            msg.set_content("Please enable HTML to view this email.")
            msg.add_alternative(body, subtype='html')
            
            try:
                server.send_message(msg)
                successful_phones.append(phone_str)
                success_count += 1
                log_outreach_event("Email", health, name, phone_str, email_to, msg['Subject'], "SUCCESS")
            except Exception as send_err:
                error_count += 1
                log_outreach_event("Email", health, name, phone_str, email_to, msg['Subject'], "FAILED", str(send_err))
                
            if progress_callback:
                progress_callback(idx + 1, total_count, name, success_count, error_count)
            
        server.quit()
        return True, successful_phones
    except Exception as e:
        return False, str(e)


@st.cache_data(show_spinner=False)
def prepare_eval_df(df_sales):
    """Caches the heavy groupby and string replacement operations so they do not run on every filter change."""
    filtered = df_sales.copy()
    filtered['phone'] = filtered['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
    
    # Normalize CP Usage labels to match new credit thresholds
    if 'CP Usage in last 7 days' in filtered.columns:
        cp_replacements = {
            'More than 500': 'More than 1000',
            'B/W 100 to 500': 'less than 500',
            'less than 100': 'less than 500'
        }
        filtered['CP Usage in last 7 days'] = filtered['CP Usage in last 7 days'].replace(cp_replacements)

    eval_df = filtered.copy()
    
    ffill_cols = [
        'Name', 'phone', 'plan name', 'Usage check', 
        'Last Sync in 7 days', 'CP Usage in last 7 days', 
        'Contact details fetched in last 7 days', 
        'App login done in last 7 days', 'raw_credits', 
        'Plan Stat Date', 'Plan End Date'
    ]
    for col in ffill_cols:
        if col in eval_df.columns:
            if 'Upload_Batch' in eval_df.columns:
                eval_df[col] = eval_df.groupby('Upload_Batch')[col].transform(lambda s: s.replace("", pd.NA).ffill())
            else:
                eval_df[col] = eval_df[col].replace("", pd.NA).ffill()
            if col in filtered.columns:
                filtered[col] = eval_df[col]
            
    def _validate_row_usage_health(row):
        c_raw = str(row.get('raw_credits', row.get('CP Usage in last 7 days', '0'))).replace(',', '').strip()
        try:
            c_val = float(c_raw) if c_raw and c_raw.lower() != 'nan' else 0
        except:
            c_val = 0

        l_raw = str(row.get('App login done in last 7 days', '')).strip().lower()
        login_yes = (l_raw != '' and l_raw != 'nan' and l_raw not in ['no', 'false', '0', 'none'])

        s_raw = str(row.get('Last Sync in 7 days', '')).strip().lower()
        sync_yes = (s_raw and s_raw not in ['no', 'false', '0', 'nan', 'none', 'more than 15 days in sync', ''])

        ct_raw = str(row.get('Contact details fetched in last 7 days', '0')).replace(',', '').strip()
        try:
            ct_val = float(ct_raw) if ct_raw and ct_raw.lower() != 'nan' else 0
        except:
            ct_val = 0

        # ZERO ACTIVITY RULE: If credits = 0, no login, no sync, 0 contacts -> ALWAYS No Usage 🔴
        if c_val == 0 and not login_yes and not sync_yes and ct_val == 0:
            return 'No Usage 🔴'

        raw_h = str(row.get('Usage check', '')).strip()
        if raw_h and any(h in raw_h for h in ['Proper', 'Low', 'No']):
            return raw_h

        pts = 0
        plan_n = str(row.get('plan name', ''))
        _, cp_score = eval_plan_credits_and_score(plan_n, c_val)
        pts += cp_score

        if login_yes: pts += 2
        if sync_yes: pts += 1
        if ct_val > 30: pts += 2
        elif ct_val >= 11: pts += 1

        if pts == 0: return 'No Usage 🔴'
        elif pts <= 3: return 'Low Usage 🟡'
        else: return 'Proper Usage 🟢'

    eval_df['Usage check'] = eval_df.apply(_validate_row_usage_health, axis=1)
    filtered['Usage check'] = eval_df['Usage check']

    if 'phone' in eval_df.columns and 'Usage check' in eval_df.columns:
        if 'Upload_Batch' in eval_df.columns:
            eval_df['Usage check'] = eval_df.groupby(['phone', 'Upload_Batch'])['Usage check'].transform('first')
            if 'plan name' in eval_df.columns:
                eval_df['plan name'] = eval_df.groupby(['phone', 'Upload_Batch'])['plan name'].transform('first')
        else:
            eval_df['Usage check'] = eval_df.groupby('phone')['Usage check'].transform('first')
            if 'plan name' in eval_df.columns:
                eval_df['plan name'] = eval_df.groupby('phone')['plan name'].transform('first')
        filtered['Usage check'] = eval_df['Usage check']
        if 'plan name' in eval_df.columns and 'plan name' in filtered.columns:
            filtered['plan name'] = eval_df['plan name']

    plan_dt_col = 'Plan Stat Date' if 'Plan Stat Date' in eval_df.columns else ('plan_start_date' if 'plan_start_date' in eval_df.columns else None)
    if plan_dt_col:
        eval_df['parsed_plan_dt'] = pd.to_datetime(eval_df[plan_dt_col], errors='coerce', dayfirst=True)
    else:
        eval_df['parsed_plan_dt'] = pd.NaT
    
    def _calc_row_eff_dt(row):
        p_dt = row['parsed_plan_dt']
        if pd.notna(p_dt):
            return p_dt.date()
        batch = str(row.get('Upload_Batch', ''))
        
        if 'July' in batch or 'july' in batch:
            return date(2026, 7, 15)
        if 'Aug' in batch or 'aug' in batch or 'usage_seet' in batch:
            return date(2026, 8, 15)
            
        m = re.search(r'(\d{2})(\d{2})(\d{4})', batch)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    return date(year, month, day)
                except Exception:
                    pass
                    
        if 'Sep' in batch or 'sep' in batch or '092026' in batch:
            return date(2026, 9, 15)
        elif 'Oct' in batch or 'oct' in batch or '102026' in batch:
            return date(2026, 10, 15)
        return date(2026, 9, 15)

    import datetime
    eval_df['row_eff_dt'] = eval_df.apply(_calc_row_eff_dt, axis=1)
    cust_dt_map = eval_df.groupby('phone')['row_eff_dt'].min().to_dict()
    eval_df['effective_date'] = eval_df['phone'].map(cust_dt_map)
    filtered['effective_date'] = eval_df['effective_date']
    return filtered, eval_df

@st.fragment
def render_dashboard(df_sales, prefix):

    st.subheader("📋 Combined Formatted Data")
    
    # Use the cached dataframe prep
    filtered_base, eval_df_base = prepare_eval_df(df_sales)
    
    temp_plans = df_sales['plan name'].replace("", pd.NA).ffill()
    all_plans = [p for p in temp_plans.dropna().unique() if str(p).strip() != ""]
    usage_opts = ["No Usage 🔴", "Low Usage 🟡", "Proper Usage 🟢", "No Data (Not Uploaded)"]
    
    # URL Memory
    q_search = st.query_params.get(f"q_search_{prefix}", "")
    
    q_plans_str = st.query_params.get(f"q_plan_{prefix}", "")
    q_plans = [p for p in q_plans_str.split("||") if p in all_plans] if q_plans_str else []
    
    q_usage_str = st.query_params.get(f"q_usage_{prefix}", "")
    q_usage = [u for u in q_usage_str.split("||") if u in usage_opts] if q_usage_str else []
    
    # ── TOP DATE / COHORT DROPDOWN FILTER ──
    dp_opts = [
        "Overall Data (All Cohorts Combined)",
        "July Cohort Data",
        "August Cohort Data",
        "Last 30 Days",
        "Last 90 Days",
        "Custom Date Range..."
    ]
    q_dp = st.query_params.get(f"q_dp_{prefix}", dp_opts[0])
    if q_dp not in dp_opts: q_dp = dp_opts[0]

    f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.8, 1.4, 1.4])
    with f_col1:
        search_q = st.text_input("🔍 Search Name or Phone", value=q_search, key=f"s_search_{prefix}")
    with f_col2:
        date_preset = st.selectbox(
            "📅 Select Date / Cohort Filter",
            options=dp_opts,
            index=dp_opts.index(q_dp),
            key=f"d_preset_select_{prefix}"
        )
    with f_col3:
        plan_filt = st.multiselect("📊 Filter by Plan Name", options=all_plans, default=q_plans, key=f"s_filt_{prefix}")
    with f_col4:
        usage_filt = st.multiselect("🚦 Filter by Usage Health", options=usage_opts, default=q_usage, key=f"u_filt_{prefix}")

    custom_start_end = None
    if "Custom Date Range" in date_preset:
        import datetime
        today_d = date.today()
        default_start = date(2026, 7, 1)
        c_input = st.date_input(
            "🗓️ **Select Custom Date Range (Start Date to End Date):**",
            value=(default_start, today_d),
            key=f"d_custom_{prefix}"
        )
        if isinstance(c_input, (list, tuple)):
            if len(c_input) == 2:
                custom_start_end = c_input
            elif len(c_input) == 1:
                custom_start_end = (c_input[0], c_input[0])
        
    filtered = filtered_base.copy()
    eval_df = eval_df_base.copy()
            
    if search_q:
        mask = (eval_df['Name'].astype(str).str.contains(search_q, case=False, na=False) |
                eval_df['phone'].astype(str).str.contains(search_q, case=False, na=False))
        m_phones = eval_df[mask]['phone'].unique()
        filtered = filtered[filtered['phone'].isin(m_phones)]
        eval_df = eval_df[eval_df['phone'].isin(m_phones)]
        
    if plan_filt:
        mask = eval_df['plan name'].isin(plan_filt)
        filtered = filtered[mask]
        eval_df = eval_df[mask]
        
    if usage_filt:
        mask = eval_df['Usage check'].isin(usage_filt)
        filtered = filtered[mask]
        eval_df = eval_df[mask]

    if not date_preset.startswith("🌐") and not date_preset.startswith("Overall Data"):
        import datetime
        today_d = date.today()

        if "July" in date_preset:
            if 'Upload_Batch' in eval_df.columns:
                batch_mask = eval_df['Upload_Batch'].astype(str).str.contains('July|july', case=False, na=False)
                if not batch_mask.any():
                    batch_mask = (eval_df['effective_date'].apply(lambda d: d.month if d else None) == 7)
            else:
                batch_mask = (eval_df['effective_date'].apply(lambda d: d.month if d else None) == 7)
            filtered = filtered[batch_mask]
            eval_df = eval_df[batch_mask]
        elif "August" in date_preset:
            if 'Upload_Batch' in eval_df.columns:
                batch_mask = eval_df['Upload_Batch'].astype(str).str.contains('Aug|aug|usage|092026|112026', case=False, na=False)
                if not batch_mask.any():
                    batch_mask = (eval_df['effective_date'].apply(lambda d: d.month if d else None) == 8)
            else:
                batch_mask = (eval_df['effective_date'].apply(lambda d: d.month if d else None) == 8)
            filtered = filtered[batch_mask]
            eval_df = eval_df[batch_mask]
        else:
            target_phones = None
            if "Last 30 Days" in date_preset:
                start_30 = today_d - datetime.timedelta(days=30)
                target_phones = eval_df[eval_df['effective_date'] >= start_30]['phone'].unique()
            elif "Last 90 Days" in date_preset:
                start_90 = today_d - datetime.timedelta(days=90)
                target_phones = eval_df[eval_df['effective_date'] >= start_90]['phone'].unique()
            elif "Custom Date Range" in date_preset and custom_start_end is not None and len(custom_start_end) == 2:
                s_d, e_d = custom_start_end
                target_phones = eval_df[(eval_df['effective_date'] >= s_d) & (eval_df['effective_date'] <= e_d)]['phone'].unique()

            if target_phones is not None and len(target_phones) > 0:
                filtered = filtered[filtered['phone'].isin(target_phones)]
                eval_df = eval_df[eval_df['phone'].isin(target_phones)]
        
    unique_cx = eval_df['phone'].nunique()
    st.success(f"👥 **Showing {unique_cx} Unique Customers** (Total {len(filtered)} rows in view)")

    # ── OVERALL DASHBOARD ──────────────────────────────────────────────
    st.markdown("---")
    d_c1, d_c2 = st.columns([3, 1])
    with d_c1:
        st.subheader("📊 Overall Dashboard")
    with d_c2:
        excel_dash = to_excel_download(filtered, sheet_name="Dashboard Data")
        st.download_button("📥 Export Filtered Data", data=excel_dash, file_name="Dashboard_Filtered_Data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    # Compute per-customer stats from eval_df (one row per phone)
    dash_df = eval_df.drop_duplicates(subset=['phone'], keep='last').copy()

    # Usage counts
    no_usage = len(dash_df[dash_df['Usage check'].astype(str).str.contains('No Usage', na=False)])
    low_usage = len(dash_df[dash_df['Usage check'].astype(str).str.contains('Low Usage', na=False)])
    proper_usage = len(dash_df[dash_df['Usage check'].astype(str).str.contains('Proper Usage', na=False)])
    no_data = unique_cx - no_usage - low_usage - proper_usage

    # Outreach stats from DB
    interactions_dash = pd.read_sql("SELECT * FROM customer_interactions", conn)
    interactions_dash['phone'] = interactions_dash['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
    interactions_dash = interactions_dash.drop_duplicates(subset=['phone'], keep='last')

    dash_df['merge_phone'] = dash_df['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
    dash_merged = pd.merge(dash_df, interactions_dash, left_on='merge_phone', right_on='phone', how='left', suffixes=('', '_db'))

    wa_sent_count = int(dash_merged['wa_sent'].fillna(0).astype(bool).sum())
    free_wa_count = int(dash_merged['free_wa_sent'].fillna(0).astype(bool).sum()) if 'free_wa_sent' in dash_merged.columns else 0
    email_sent_count = int(dash_merged['email_sent'].fillna(0).astype(bool).sum()) if 'email_sent' in dash_merged.columns else 0

    # ── ROW 1: KPI Cards ──
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Total Customers", unique_cx)
    k2.metric("🔴 No Usage", no_usage, delta=f"{round(no_usage/unique_cx*100)}%" if unique_cx else "0%", delta_color="inverse")
    k3.metric("🟡 Low Usage", low_usage, delta=f"{round(low_usage/unique_cx*100)}%" if unique_cx else "0%", delta_color="off")
    k4.metric("🟢 Proper Usage", proper_usage, delta=f"{round(proper_usage/unique_cx*100)}%" if unique_cx else "0%", delta_color="normal")

    # ── ROW 2: Outreach KPIs ──
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("📩 WA API Sent", wa_sent_count, delta=f"{round(wa_sent_count/unique_cx*100)}%" if unique_cx else "0%")
    o2.metric("💬 Free WA Sent", free_wa_count, delta=f"{round(free_wa_count/unique_cx*100)}%" if unique_cx else "0%")
    o3.metric("📧 Emails Sent", email_sent_count, delta=f"{round(email_sent_count/unique_cx*100)}%" if unique_cx else "0%")
    total_reached = len(dash_merged[(dash_merged['wa_sent'].fillna(0).astype(bool)) | (dash_merged['free_wa_sent'].fillna(0).astype(bool)) | (dash_merged['email_sent'].fillna(0).astype(bool))])
    not_reached = unique_cx - total_reached
    o4.metric("🚫 Not Reached Yet", not_reached, delta=f"{round(not_reached/unique_cx*100)}%" if unique_cx else "0%", delta_color="inverse")

    # ── ROW 3: Charts ──
    ch1, ch2 = st.columns(2)

    with ch1:
        usage_data = pd.DataFrame({
            'Status': ['No Usage 🔴', 'Low Usage 🟡', 'Proper Usage 🟢', 'No Data'],
            'Count': [no_usage, low_usage, proper_usage, no_data]
        })
        usage_data = usage_data[usage_data['Count'] > 0]
        fig_usage = px.pie(
            usage_data, values='Count', names='Status',
            title='Usage Health Breakdown',
            color='Status',
            color_discrete_map={
                'No Usage 🔴': '#EF4444',
                'Low Usage 🟡': '#F59E0B',
                'Proper Usage 🟢': '#10B981',
                'No Data': '#9CA3AF'
            },
            hole=0.45
        )
        fig_usage.update_traces(textposition='inside', textinfo='value+percent')
        fig_usage.update_layout(height=350, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_usage, use_container_width=True)

    with ch2:
        if 'plan name' in dash_df.columns:
            plan_counts = dash_df['plan name'].dropna().value_counts().reset_index()
            plan_counts.columns = ['Plan', 'Customers']
            plan_counts = plan_counts[plan_counts['Plan'].str.strip() != '']
            if not plan_counts.empty:
                fig_plan = px.bar(
                    plan_counts.head(10), x='Customers', y='Plan',
                    title='Top Plans by Customer Count',
                    orientation='h',
                    color='Customers',
                    color_continuous_scale='Blues'
                )
                fig_plan.update_layout(
                    height=350, margin=dict(t=40, b=20, l=20, r=20),
                    yaxis={'categoryorder': 'total ascending'},
                    showlegend=False
                )
                st.plotly_chart(fig_plan, use_container_width=True)
            else:
                st.info("No plan data to display.")

    # ── ROW 3.5: Date-Wise Usage Breakdown Chart ──
    if 'Plan Stat Date' in dash_df.columns:
        dash_df_chart = dash_df.copy()
        dash_df_chart['Month_Year'] = pd.to_datetime(dash_df_chart['Plan Stat Date'], errors='coerce', dayfirst=True).dt.to_period('M').astype(str)
        date_usage_df = dash_df_chart.groupby(['Month_Year', 'Usage check']).size().reset_index(name='Count')
        date_usage_df = date_usage_df[date_usage_df['Month_Year'] != 'NaT']
        
        if not date_usage_df.empty:
            st.markdown("#### 📈 Date-Wise Usage Health Trend (Monthly Breakdown)")
            fig_date_trend = px.bar(
                date_usage_df,
                x='Month_Year',
                y='Count',
                color='Usage check',
                title='Monthly Customer Onboarding & Usage Health Breakdown',
                color_discrete_map={
                    'No Usage 🔴': '#EF4444',
                    'Low Usage 🟡': '#F59E0B',
                    'Proper Usage 🟢': '#10B981',
                    'No Data': '#9CA3AF'
                },
                barmode='stack'
            )
            st.plotly_chart(fig_date_trend, use_container_width=True)

    # ── ROW 4: Outreach Progress Bar ──
    if unique_cx > 0:
        pct_reached = round(total_reached / unique_cx * 100)
        st.markdown(f"""
        <div style="background:#f3f4f6;border-radius:10px;padding:4px;margin:10px 0;">
            <div style="background:linear-gradient(90deg,#3B82F6,#10B981);width:{pct_reached}%;padding:10px 15px;border-radius:8px;color:white;font-weight:bold;font-size:14px;text-align:center;min-width:60px;">
                {pct_reached}% Outreach Complete ({total_reached}/{unique_cx})
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── ROW 5: Usage Health Scoring Matrix Guide (Presentation Expander) ──
    with st.expander("ℹ️ How Usage Health Score is Calculated (Scoring Logic & Rules Guide)", expanded=False):
        st.markdown("""
        ### 📊 CredFlow Customer Usage Health Scoring Model
        Customer health is calculated dynamically across **4 Key Usage Parameters** (Maximum Score = **8 Points**):
        
        | Parameter | Condition / Tier | Points | Missing / Blank Data Rule |
        | :--- | :--- | :---: | :---: |
        | **1. App Login** | `Yes` (Logged in within 7 days)<br>`No` / `None` | **+2 Points**<br>0 Points | Missing/Blank cell ➔ **0 Points** (`"None"`) |
        | **2. Last Sync** | `Yes` (Synced within 7 days)<br>`No` / `None` | **+1 Point**<br>0 Points | Missing/Blank cell ➔ **0 Points** (`"None"`) |
        | **3. CP Usage (Plan-Wise Dynamic)** | **Lite/Basic Tier**: `> 100` (**+3 Pts**), `30-100` (**+2 Pts**), `< 30` (**0 Pts**)<br>**Saver/Pro Tier**: `> 500` (**+3 Pts**), `200-500` (**+2 Pts**), `< 200` (**0 Pts**)<br>**Enterprise Tier**: `> 1000` (**+3 Pts**), `500-1000` (**+2 Pts**), `< 500` (**0 Pts**) | **+3 / +2 / 0** | Missing/Blank cell ➔ **0 Points** (`"None"`) |
        | **4. Contact Details Fetched** | `> 31 Contacts`<br>`11 to 30 Contacts`<br>`0 to 10` / `None` | **+2 Points**<br>**+1 Point**<br>0 Points | Missing/Blank cell ➔ **0 Points** (`"None"`) |

        ---

        ### 🚦 Health Category Classification Rules:
        - 🔴 **No Usage (Score = 0)**: Customers with **0 total points** *(Incomplete setup, zero credits used, no sync, or completely blank rows)*.
        - 🟡 **Low Usage (Score = 1 to 3)**: Customers with basic sync or minimal usage who need setup assistance & optimization.
        - 🟢 **Proper Usage (Score ≥ 4)**: Highly active customers utilizing multiple CredFlow features *(Targeted for Upsell & Upgrades to AI Accountant / WhatsApp API)*.
        
        > 💡 **Presentation Note**: All missing data cells, empty fields, and `NaN` values are strictly assigned **`0 Points ("None")`**. This guarantees zero false positives for *Proper Usage 🟢*.
        """)

    st.markdown("---")

    # ── ISSUE SUMMARY ON DASHBOARD ──
    issue_summary_dash = pd.read_sql("SELECT issue_type, COUNT(*) as count FROM customer_interactions WHERE issue_type IS NOT NULL AND issue_type != '' GROUP BY issue_type ORDER BY count DESC", conn)
    if not issue_summary_dash.empty:
        st.markdown("### 🏷️ Customer Issue Tracker Summary")
        iss_c1, iss_c2 = st.columns([2, 1])
        with iss_c1:
            fig_issues_dash = px.bar(issue_summary_dash, x='issue_type', y='count', title="Issue Type Breakdown",
                              labels={'issue_type': 'Issue Type', 'count': 'Customers'},
                              color='issue_type', color_discrete_sequence=px.colors.qualitative.Set2)
            fig_issues_dash.update_layout(height=350, margin=dict(t=40, b=20, l=20, r=20), showlegend=False)
            st.plotly_chart(fig_issues_dash, use_container_width=True)
        with iss_c2:
            st.dataframe(issue_summary_dash.rename(columns={'issue_type': 'Issue Type 🏷️', 'count': 'Customers 👥'}), use_container_width=True, hide_index=True)
            total_issues = issue_summary_dash['count'].sum()
            st.metric("📋 Total Issues Logged", total_issues)

    st.markdown("---")
    # ── END OVERALL DASHBOARD ──────────────────────────────────────────

    features_grouped = eval_df.groupby('phone')['feature'].apply(lambda x: ', '.join(x.dropna().unique())).reset_index()
    features_grouped = features_grouped.rename(columns={'feature': 'All Features'})
    cx_df = eval_df.drop_duplicates(subset=['phone'], keep='last')
    cx_df = cx_df.drop(columns=['All Features'], errors='ignore')
    cx_df = pd.merge(cx_df, features_grouped, on='phone', how='left')

    try:
        render_crm(cx_df)
    except Exception as e:
        st.error(f"CRM Crash: {e}")
        import traceback
        st.code(traceback.format_exc())




def render_crm(cx_df):
    # ── TEST SANDBOX ──────────────────────────────────────────────
    with st.expander("🧪 **Test Sandbox — Single Message Tester (WhatsApp & Email)**", expanded=False):
        st.markdown("💡 *Bulk sending se pehle apne number/email par test message bhej kar verfiy karein.*")
        tab_wa, tab_email = st.tabs(["💬 Test WhatsApp API (Interakt)", "📧 Test Email (SMTP)"])
        
        with tab_wa:
            st.markdown("#### 📲 Send Test WhatsApp via Interakt API")
            tc1, tc2 = st.columns(2)
            with tc1:
                test_wa_phone = st.text_input("Mobile Number (10 digit)", key="test_wa_phone", placeholder="9876543210")
            with tc2:
                test_wa_name = st.text_input("Customer Name", value="Test Customer", key="test_wa_name")
            tc3, tc4 = st.columns(2)
            with tc3:
                test_wa_health = st.selectbox("Usage Health Category", ["No Usage 🔴", "Low Usage 🟡", "Proper Usage 🟢"], key="test_wa_health")
            with tc4:
                test_wa_credits = st.text_input("Raw Credits / Used", value="500", key="test_wa_credits")
                
            if st.button("🚀 Send Test WhatsApp Message", type="primary", use_container_width=True):
                if not test_wa_phone or len(test_wa_phone.strip()) < 10:
                    st.warning("Kripya valid 10-digit mobile number dalein.")
                else:
                    with st.spinner("Sending test WhatsApp message..."):
                        success, resp = send_interakt_msg(test_wa_phone, test_wa_name, test_wa_health, test_wa_credits)
                    if success:
                        st.success(f"✅ Test WhatsApp message sent successfully to {test_wa_phone}!")
                    else:
                        st.error(f"❌ Failed to send WhatsApp message: {resp}")
                        
        with tab_email:
            st.markdown("#### 📧 Send Test Email via SMTP")
            tec1, tec2 = st.columns(2)
            with tec1:
                test_email_addr = st.text_input("Email Address", key="test_email_addr", placeholder="user@example.com")
            with tec2:
                test_email_name = st.text_input("Customer Name", value="Test Customer", key="test_email_name")
            tec3, tec4 = st.columns(2)
            with tec3:
                test_email_health = st.selectbox("Usage Health Category", ["No Usage 🔴", "Low Usage 🟡", "Proper Usage 🟢"], key="test_email_health")
            with tec4:
                test_email_plan = st.text_input("Plan Name", value="Enterprise Plan", key="test_email_plan")
                
            if st.button("🚀 Send Test Email", type="primary", use_container_width=True):
                if not test_email_addr or "@" not in test_email_addr:
                    st.warning("Kripya valid email address dalein.")
                else:
                    with st.spinner("Sending test email..."):
                        test_row = {
                            "Name": test_email_name,
                            "email": test_email_addr,
                            "Usage check": test_email_health,
                            "phone": "9999999999",
                            "plan name": test_email_plan
                        }
                        success, resp = send_bulk_emails([test_row])
                    if success and resp:
                        st.success(f"✅ Test Email sent successfully to {test_email_addr}!")
                    else:
                        st.error(f"❌ Failed to send Email: {resp}")
    # ──────────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📞 Interactive Telecalling CRM")
    st.info("⚡ **Auto-Save Enabled!** Aap is table mein kuch bhi edit (tick/type) karenge, toh woh immediately automatic save ho jayega.")

    # ── QUICK CALLBACK SCHEDULER & SUPPORT ALERT ──
    with st.expander("⏰ Schedule Customer Callback & Auto Alert Support (1-Click Notification)", expanded=False):
        st.caption("Jab customer bole ki 'mujhko X baje call karna', tab yahan se customer select karke date, time aur remarks dalein. Remarks auto-generate hongi aur support@credflow.in ko notification mail chala jayega.")
        
        all_cx_names = cx_df[['Name', 'phone', 'email', 'plan name']].drop_duplicates(subset=['phone'], keep='last').to_dict('records') if not cx_df.empty else []
        cx_options = [f"{r.get('Name', 'Unknown')} ({r.get('phone', '')})" for r in all_cx_names]
        
        cb_col1, cb_col2, cb_col3, cb_col4 = st.columns([3, 2, 2, 3])
        with cb_col1:
            sel_cx_str = st.selectbox("👤 Select Customer", options=cx_options if cx_options else ["No Customers Loaded"], key="cb_cx_select")
        with cb_col2:
            import datetime
            cb_date = st.date_input("📅 Callback Date", value=date.today(), key="cb_date_input")
        with cb_col3:
            cb_time_str = st.text_input("⏰ Callback Time", value="4:00 PM", key="cb_time_input")
        with cb_col4:
            cb_agent_email = st.text_input("📧 Your Email (Added in CC & Reply-To)", value="satyam.kumar@credflow.in", placeholder="e.g. satyam.kumar@credflow.in", key="cb_agent_email_input")
            
        cb_rem = st.text_area("📝 Customer Request Notes / Remarks", placeholder="Customer asked to call back regarding Tally sync setup after 4 PM...", key="cb_remarks_input")
        
        if st.button("🔔 Schedule Callback & Email Alert", type="primary", use_container_width=True, key="btn_schedule_cb"):
            if not cx_options or sel_cx_str == "No Customers Loaded":
                st.warning("Pehle Master Data upload ya select karein.")
            else:
                selected_cx_obj = next((r for r in all_cx_names if f"{r.get('Name', '')} ({r.get('phone', '')})" == sel_cx_str), None)
                if selected_cx_obj:
                    cx_p = str(selected_cx_obj.get('phone', '')).replace('.0', '').strip()
                    cx_n = str(selected_cx_obj.get('Name', ''))
                    cx_e = str(selected_cx_obj.get('email', ''))
                    cx_plan = str(selected_cx_obj.get('plan name', ''))
                    
                    full_remark = f"⏰ [Callback Scheduled: {cb_date} at {cb_time_str}] {cb_rem}".strip()
                    date_str = str(cb_date)
                    
                    # Update SQLite DB
                    conn.execute('''
                        INSERT INTO customer_interactions (phone, call_status, remarks, follow_up)
                        VALUES (?, 'Call Back Requested', ?, ?)
                        ON CONFLICT(phone) DO UPDATE SET
                            call_status='Call Back Requested',
                            remarks=?,
                            follow_up=?
                    ''', (cx_p, full_remark, date_str, full_remark, date_str))
                    conn.commit()
                    
                    # Send Support Email Alert with Agent Reply-To
                    succ_mail, msg_mail = send_callback_support_email(cx_n, cx_p, cx_e, cx_plan, date_str, full_remark, cb_time_str, agent_email=cb_agent_email)
                    
                    if succ_mail:
                        st.success(f"✅ Callback scheduled for {cx_n} on {date_str} at {cb_time_str}! Notification email dispatched (Customer in TO, Support in CC, Reply-To: {cb_agent_email or 'support@credflow.in'}).")
                    else:
                        st.warning(f"✅ Callback saved to DB! (Email alert note: {msg_mail})")
                    st.rerun()

    # ── ISSUE TYPES MANAGER ──
    with st.expander("🏷️ Manage Issue Types (Add / Remove your custom issue categories)", expanded=False):
        st.caption("Yahan aap apne custom Issue Types add/remove kar sakte hain. Ye options CRM table ke 'Issue Type' dropdown mein dikhenge.")
        existing_issues = [r[0] for r in conn.execute("SELECT issue_name FROM issue_types ORDER BY issue_name").fetchall()]
        
        mgr_c1, mgr_c2 = st.columns([3, 1])
        with mgr_c1:
            new_issue = st.text_input("➕ Add New Issue Type", placeholder="e.g. Sync Issue, App Crash, Feature Request...", key="new_issue_input")
        with mgr_c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add Issue Type", type="primary", use_container_width=True, key="btn_add_issue"):
                if new_issue and new_issue.strip():
                    try:
                        conn.execute("INSERT INTO issue_types (issue_name) VALUES (?)", (new_issue.strip(),))
                        conn.commit()
                        st.success(f"✅ '{new_issue.strip()}' added!")
                        st.rerun()
                    except:
                        st.warning("⚠️ This issue type already exists!")
                else:
                    st.warning("Please enter an issue type name.")
        
        if existing_issues:
            st.markdown("**Current Issue Types:**")
            issue_cols = st.columns(min(len(existing_issues), 4))
            for i, iss in enumerate(existing_issues):
                with issue_cols[i % 4]:
                    if st.button(f"❌ {iss}", key=f"del_issue_{i}", use_container_width=True):
                        conn.execute("DELETE FROM issue_types WHERE issue_name = ?", (iss,))
                        conn.commit()
                        st.rerun()

    # ── ISSUE SUMMARY DASHBOARD ──
    issue_summary = pd.read_sql("SELECT issue_type, COUNT(*) as count FROM customer_interactions WHERE issue_type IS NOT NULL AND issue_type != '' GROUP BY issue_type ORDER BY count DESC", conn)
    if not issue_summary.empty:
        with st.expander("📊 Issue Type Summary (All Customers)", expanded=False):
            fig_issues = px.bar(issue_summary, x='issue_type', y='count', title="Customer Issues Breakdown",
                              labels={'issue_type': 'Issue Type', 'count': 'Customers'},
                              color='issue_type', color_discrete_sequence=px.colors.qualitative.Set2)
            fig_issues.update_layout(height=350, margin=dict(t=40, b=20, l=20, r=20), showlegend=False)
            st.plotly_chart(fig_issues, use_container_width=True)
            st.dataframe(issue_summary.rename(columns={'issue_type': 'Issue Type 🏷️', 'count': 'Customers 👥'}), use_container_width=True, hide_index=True)

    def get_base_credits(plan_name):
        pn = str(plan_name).upper()
        if 'BVP' in pn: return 10000
        if 'PREMIUM' in pn: return 10000
        if 'SAVER' in pn: return 7000
        if 'PRO' in pn: return 7000
        if 'LITE' in pn: return 1000
        if 'BASIC' in pn: return 1000
        return 0

    if not cx_df.empty:
        interactions_df = pd.read_sql("SELECT * FROM customer_interactions", conn)

        call_df = cx_df.copy()
        call_df['phone'] = call_df['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        call_df['WhatsApp'] = call_df.apply(generate_wa_link, axis=1)

        call_df['merge_phone'] = call_df['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        interactions_df['phone'] = interactions_df['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        interactions_df = interactions_df.drop_duplicates(subset=['phone'], keep='last')

        call_df = pd.merge(call_df, interactions_df, left_on='merge_phone', right_on='phone', how='left', suffixes=('', '_y'))
        call_df = call_df.drop_duplicates(subset=['merge_phone'], keep='last')

        call_df['wa_sent'] = call_df['wa_sent'].fillna(0).astype(bool)
        if 'free_wa_sent' not in call_df.columns:
            call_df['free_wa_sent'] = 0
        call_df['free_wa_sent'] = call_df['free_wa_sent'].fillna(0).astype(bool)
        if 'email_sent' not in call_df.columns:
            call_df['email_sent'] = 0
        call_df['email_sent'] = call_df['email_sent'].fillna(0).astype(bool)
        call_df['call_status'] = call_df['call_status'].fillna("")
        call_df['remarks'] = call_df['remarks'].fillna("")
        call_df['follow_up'] = pd.to_datetime(call_df['follow_up'], errors='coerce').dt.date
        
        # --- Credits Logic ---
        if 'extra_credits' not in call_df.columns:
            call_df['extra_credits'] = 0
        call_df['extra_credits'] = pd.to_numeric(call_df['extra_credits'].fillna(0), errors='coerce').fillna(0).astype(int)
        
        call_df['Base Credits'] = call_df['plan name'].apply(get_base_credits)
        call_df['Extra Credits'] = call_df['extra_credits']
        call_df['Total Credits'] = call_df['Base Credits'] + call_df['Extra Credits']

        # Issue Type from DB
        if 'issue_type' not in call_df.columns:
            call_df['issue_type'] = ''
        call_df['issue_type'] = call_df['issue_type'].fillna('')

        # Plan of Action from DB
        if 'plan_of_action' not in call_df.columns:
            call_df['plan_of_action'] = ''
        call_df['plan_of_action'] = call_df['plan_of_action'].fillna('')

        if 'status_update' not in call_df.columns:
            call_df['status_update'] = ''
        call_df['status_update'] = call_df['status_update'].fillna('')

        call_df = call_df.rename(columns={
            'wa_sent': '✅ WA Sent',
            'free_wa_sent': '✅ Free WA Sent',
            'email_sent': '📨 Email Sent',
            'status_update': 'Status Update',
            'call_status': 'Call Status',
            'remarks': 'Remarks',
            'follow_up': 'Follow-up Date',
            'issue_type': 'Issue Type',
            'plan_of_action': 'Plan of Action'
        })

        cols_to_keep = ['Name', 'phone', 'email', 'WhatsApp', '✅ WA Sent', '✅ Free WA Sent', '📨 Email Sent', 'plan name', 'All Features', 'Base Credits', 'Extra Credits', 'Total Credits', 'raw_credits', 'App login done in last 7 days', 'Last Sync in 7 days', 'CP Usage in last 7 days', 'Usage check', 'Status Update', 'Call Status', 'Issue Type', 'Plan of Action', 'Remarks', 'Follow-up Date']
        existing_cols = [c for c in cols_to_keep if c in call_df.columns]
        ui_df = call_df[existing_cols]

        # --- URL Memory for CRM Filters ---
        wa_opts = ["All", "Sent ✅", "Not Sent ❌"]
        fwa_opts = ["All", "Sent ✅", "Not Sent ❌"]
        em_opts = ["All", "Sent ✅", "Not Sent ❌"]
        dt_opts = ["All Dates 🌐", "Today 📌", "Tomorrow ⏩", "Overdue / Missed ⚠️", "Has Follow-up Set 📅", "No Follow-up 🚫", "Custom Date Range 📆"]

        q_wa = st.query_params.get("q_flt_wa", wa_opts[0])
        if q_wa not in wa_opts: q_wa = wa_opts[0]

        q_fwa = st.query_params.get("q_flt_fwa", fwa_opts[0])
        if q_fwa not in fwa_opts: q_fwa = fwa_opts[0]

        q_em = st.query_params.get("q_flt_em", em_opts[0])
        if q_em not in em_opts: q_em = em_opts[0]

        q_dt = st.query_params.get("q_flt_date", dt_opts[0])
        if q_dt not in dt_opts: q_dt = dt_opts[0]

        # --- New WA, Email & Date Filters ---
        filt_c1, filt_c2, filt_c3, filt_c4 = st.columns(4)
        with filt_c1:
            wa_filter = st.selectbox("🎯 Filter by WA API Sent", wa_opts, index=wa_opts.index(q_wa), key="flt_wa")
        with filt_c2:
            free_wa_filter = st.selectbox("🎯 Filter by Free WA Sent", fwa_opts, index=fwa_opts.index(q_fwa), key="flt_fwa")
        with filt_c3:
            em_filter = st.selectbox("🎯 Filter by Email Sent", em_opts, index=em_opts.index(q_em), key="flt_em")
        with filt_c4:
            date_filter = st.selectbox("📅 Filter by Follow-up Date", dt_opts, index=dt_opts.index(q_dt), key="flt_date")

        # Commented out because modifying global query_params triggers a full app rerun instead of just the fragment
        # if wa_filter != q_wa: st.query_params["q_flt_wa"] = wa_filter
        # if free_wa_filter != q_fwa: st.query_params["q_flt_fwa"] = free_wa_filter
        # if em_filter != q_em: st.query_params["q_flt_em"] = em_filter
        # if date_filter != q_dt: st.query_params["q_flt_date"] = date_filter

        custom_date_range = None
        if date_filter == "Custom Date Range 📆":
            import datetime
            today_d = date.today()
            custom_date_range = st.date_input("🗓️ Select Date Range (Start & End)", value=(today_d, today_d + datetime.timedelta(days=7)), key="flt_custom_dates")

        if wa_filter == "Not Sent ❌" or free_wa_filter == "Not Sent ❌" or em_filter == "Not Sent ❌":
            st.caption("💡 **Filter Active Note**: Jab aap किसी customer ko table mein 'Sent ✅' (WA/Email) mark karenge ya Bulk Send karenge, toh wo automatic 'Not Sent ❌' list se nikal kar 'Sent ✅' category mein move ho jayenge.")

        if wa_filter == "Sent ✅":
            ui_df = ui_df[ui_df['✅ WA Sent'] == True]
        elif wa_filter == "Not Sent ❌":
            ui_df = ui_df[ui_df['✅ WA Sent'] == False]
            
        if free_wa_filter == "Sent ✅":
            ui_df = ui_df[ui_df['✅ Free WA Sent'] == True]
        elif free_wa_filter == "Not Sent ❌":
            ui_df = ui_df[ui_df['✅ Free WA Sent'] == False]

        if em_filter == "Sent ✅":
            ui_df = ui_df[ui_df['📨 Email Sent'] == True]
        elif em_filter == "Not Sent ❌":
            ui_df = ui_df[ui_df['📨 Email Sent'] == False]

        # --- Date Filter Logic ---
        import datetime
        today_val = date.today()
        tomorrow_val = today_val + datetime.timedelta(days=1)
        f_dates = pd.to_datetime(ui_df['Follow-up Date'], errors='coerce').dt.date

        if date_filter == "Today 📌":
            ui_df = ui_df[f_dates == today_val]
        elif date_filter == "Tomorrow ⏩":
            ui_df = ui_df[f_dates == tomorrow_val]
        elif date_filter == "Overdue / Missed ⚠️":
            ui_df = ui_df[(f_dates < today_val) & (f_dates.notna())]
        elif date_filter == "Has Follow-up Set 📅":
            ui_df = ui_df[f_dates.notna()]
        elif date_filter == "No Follow-up 🚫":
            ui_df = ui_df[f_dates.isna()]
        elif date_filter == "Custom Date Range 📆" and isinstance(custom_date_range, (list, tuple)) and len(custom_date_range) == 2:
            s_d, e_d = custom_date_range
            ui_df = ui_df[(f_dates >= s_d) & (f_dates <= e_d)]
        # -----------------------------
        ui_df = ui_df.reset_index(drop=True)

        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 3])
        with c1:
            select_all_wa = st.checkbox('✅ Select All WA API', key='sel_all_wa')
        with c2:
            select_all_em = st.checkbox('✅ Select All Emails', key='sel_all_em')
        with c3:
            select_all_free_wa = st.checkbox('✅ Select All Free WA', key='sel_all_free_wa')
        with c4:
            select_top_10 = st.checkbox('🔟 Select First 10 Only', key='sel_top_10')
        with c5:
            row_limit_opt = st.selectbox(
                "⚡ Display Limit",
                ["200 Rows (Fast ⚡)", "500 Rows", "1000 Rows", "All Records 🌐"],
                index=0,
                key="crm_row_limit_selector",
                help="Showing fewer rows on screen makes editing and filtering instant. Export button will still export ALL filtered records."
            )

        if "200" in row_limit_opt: max_rows_limit = 200
        elif "500" in row_limit_opt: max_rows_limit = 500
        elif "1000" in row_limit_opt: max_rows_limit = 1000
        else: max_rows_limit = len(ui_df)

        if select_top_10:
            ui_df.insert(0, '📩 Send API', [True if i < 10 else False for i in range(len(ui_df))])
            ui_df.insert(1, '📨 Send Email', [True if i < 10 else False for i in range(len(ui_df))])
            ui_df.insert(2, '📱 Send Free WA', [True if i < 10 else False for i in range(len(ui_df))])
        else:
            ui_df.insert(0, '📩 Send API', select_all_wa)
            ui_df.insert(1, '📨 Send Email', select_all_em)
            ui_df.insert(2, '📱 Send Free WA', select_all_free_wa)

        ui_display_df = ui_df.iloc[:max_rows_limit].copy()
        st.caption(f"📋 **Displaying Top {len(ui_display_df)} of {len(ui_df)} Total Filtered Customers**")

        # ── CRM INTERACTIVE TABLE (DATA EDITOR) ──
        # Fetch distinct Status Updates from DB to ensure uploaded ones are not hidden by Streamlit
        existing_status_db = [r[0] for r in conn.execute("SELECT DISTINCT status_update FROM customer_interactions WHERE status_update IS NOT NULL AND status_update != ''").fetchall()]
        default_status_opts = ["Connected", "Not Picked", "Switched Off", "Invalid Number", "Call Later", "Interested", "Not Interested", "Busy", "Ringing", "Call Back Requested", "Converted", "Payment Pending", "Payment Not Verified"]
        all_status_opts = [""] + list(dict.fromkeys(default_status_opts + existing_status_db))

        existing_poa_db = [r[0] for r in conn.execute("SELECT DISTINCT plan_of_action FROM customer_interactions WHERE plan_of_action IS NOT NULL AND plan_of_action != ''").fetchall()]
        default_poa_opts = ["Demo Diya", "Training Link", "Support ko connect karwaya", "Other"]
        all_poa_opts = [""] + list(dict.fromkeys(default_poa_opts + existing_poa_db))

        # Static editor key tied only to batch and selection states to avoid destroying React grid on filter changes
        editor_key = f"data_editor_v3_{select_top_10}_{select_all_wa}_{select_all_em}_{select_all_free_wa}_{max_rows_limit}"
        edited_df = st.data_editor(
            ui_display_df,
            key=editor_key,
            use_container_width=True,
            hide_index=True,
            column_config={
                "📩 Send API": st.column_config.CheckboxColumn("📩 Send API", default=False),
                "📨 Send Email": st.column_config.CheckboxColumn("📨 Send Email", default=False),
                "📱 Send Free WA": st.column_config.CheckboxColumn("📱 Send Free WA", default=False),
                "WhatsApp": st.column_config.LinkColumn("Open WhatsApp", display_text="Chat 💬"),
                "✅ WA Sent": st.column_config.CheckboxColumn("✅ WA API", disabled=False),
                "✅ Free WA Sent": st.column_config.CheckboxColumn("✅ Free WA", disabled=False),
                "📨 Email Sent": st.column_config.CheckboxColumn("📨 Email Sent", disabled=False),
                "Base Credits": st.column_config.NumberColumn("Base Credits", disabled=True),
                "Extra Credits": st.column_config.NumberColumn("Extra Credits (Edit Me)✏️", default=0, min_value=0),
                "Total Credits": st.column_config.NumberColumn("Total Credits", disabled=True),
                "raw_credits": st.column_config.TextColumn("Credits Used", disabled=True),
                "All Features": st.column_config.TextColumn("Plan Features 🎁", disabled=True),
                "App login done in last 7 days": st.column_config.TextColumn("Login 7d", disabled=True),
                "Last Sync in 7 days": st.column_config.TextColumn("Sync 7d", disabled=True),
                "CP Usage in last 7 days": st.column_config.TextColumn("CP Usage 7d", disabled=True),
                "Status Update": st.column_config.SelectboxColumn(
                    "Status Update 📢",
                    options=all_status_opts,
                    width="medium"
                ),
                "Call Status": st.column_config.SelectboxColumn(
                    "Call Status 📞",
                    options=["", "Connected", "Not Picked", "Switched Off", "Invalid Number", "Call Later", "Interested", "Not Interested", "Busy", "Ringing", "Call Back Requested", "Converted", "Payment Pending", "Payment Not Verified"],
                    width="medium"
                ),
                "Issue Type": st.column_config.SelectboxColumn(
                    "Issue Type 🏷️",
                    options=[""] + [r[0] for r in conn.execute("SELECT issue_name FROM issue_types ORDER BY issue_name").fetchall()],
                    width="medium"
                ),
                "Plan of Action": st.column_config.SelectboxColumn(
                    "Plan of Action 🎯",
                    options=all_poa_opts,
                    width="medium"
                ),
                "Remarks": st.column_config.TextColumn("Remarks 📝", width="large"),
                "Follow-up Date": st.column_config.DateColumn("Follow-up Date 📅", format="DD/MM/YYYY")
            },
            disabled=["Name", "phone", "email", "plan name", "Usage check", "App login done in last 7 days", "Last Sync in 7 days", "CP Usage in last 7 days"]
        )

        btn1, btn2, btn3, btn4 = st.columns([3, 3, 3, 2])
        with btn1:
            wa_clicked = st.button("🚀 Send via WA API", type="primary", use_container_width=True)
        with btn2:
            em_clicked = st.button("🚀 Send Emails", type="primary", use_container_width=True)
        with btn3:
            free_wa_clicked = st.button("🚀 Send via Free WA", type="secondary", use_container_width=True)
        with btn4:
            excel_crm = to_excel_download(edited_df, sheet_name="CRM Data")
            st.download_button("📥 Export CRM", data=excel_crm, file_name="CRM_Data_Export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        if wa_clicked:
            selected_wa_df = edited_df[edited_df['📩 Send API'] == True]
            if selected_wa_df.empty:
                st.warning("Pehle table mein se left side par '📩 Send API' check box tick karein un users ke liye jinko message bhejna hai.")
            else:
                success_count = 0
                error_count = 0
                total_wa = len(selected_wa_df)
                ph_ui, update_ui = create_progress_ui("Sending WhatsApp (API)")
                for idx, row in enumerate(selected_wa_df.to_dict('records')):
                    credits = row.get('raw_credits', '0')
                    name = str(row.get('Name', ''))
                    succ, msg = send_interakt_msg(row['phone'], name, row['Usage check'], credits)
                    if succ:
                        success_count += 1
                        p = str(row.get('phone', '')).replace('.0', '').strip()
                        conn.execute('''
                            INSERT INTO customer_interactions (phone, wa_sent)
                            VALUES (?, 1)
                            ON CONFLICT(phone) DO UPDATE SET wa_sent = 1
                        ''', (p,))
                    else:
                        error_count += 1
                        log_outreach_event("WhatsApp API", row.get('Usage check', ''), name, row.get('phone', ''), row.get('email', ''), "Interakt WA Template", "FAILED", str(msg))
                        if msg == "WALLET_INSUFFICIENT_BALANCE":
                            st.error("⚠️ **Interakt WA API Error: Insufficient Wallet Balance!** Kripya [app.interakt.ai](https://app.interakt.ai) par wallet recharge karein. Alternately, '💬 Send via Free WA' option use karein.")
                            break
                    update_ui(idx + 1, total_wa, name, success_count, error_count)
                
                conn.commit()
                if success_count > 0:
                    st.success(f"✅ Successfully sent {success_count} messages via Interakt and auto-saved their status!")
                    import time
                    time.sleep(1)
                    st.rerun() # Refresh table to show ticks

        if free_wa_clicked:
            selected_free_wa_df = edited_df[edited_df['📱 Send Free WA'] == True]
            if selected_free_wa_df.empty:
                st.warning("Pehle table mein se '📱 Send Free WA' check box tick karein un users ke liye jinko message bhejna hai.")
            else:
                import webbrowser
                import time
                import pyautogui
                st.warning(f"⚠️ AUTO-SENDING WhatsApp for {len(selected_free_wa_df)} customers. KRIPYA APNE MOUSE AUR KEYBOARD KO HAATH NA LAGAYEIN JAB TAK PROCESS PURA NA HO JAYE!")
                
                success_count = 0
                error_count = 0
                total_fwa = len(selected_free_wa_df)
                ph_ui, update_ui = create_progress_ui("Sending Free WhatsApp")
                
                for idx, row in enumerate(selected_free_wa_df.to_dict('records')):
                    name = str(row.get('Name', ''))
                    p = str(row.get('phone', '')).replace('.0', '').strip()
                    link = row.get('WhatsApp', '')
                    if not link or str(link).strip() == '':
                        link = generate_wa_link(row)
                    
                    if link:
                        conn.execute('''
                            INSERT INTO customer_interactions (phone, free_wa_sent)
                            VALUES (?, 1)
                            ON CONFLICT(phone) DO UPDATE SET free_wa_sent = 1
                        ''', (p,))
                        webbrowser.open(link)
                        time.sleep(10)
                        pyautogui.press('enter')
                        time.sleep(1)
                        pyautogui.hotkey('ctrl', 'w')
                        time.sleep(1)
                        success_count += 1
                    else:
                        error_count += 1
                    
                    update_ui(idx + 1, total_fwa, name, success_count, error_count)

                conn.commit()
                st.success(f"✅ Auto WhatsApp Sending Complete! Sent {success_count} messages.")
                time.sleep(2)
                st.rerun()

        if em_clicked:
            selected_em_df = edited_df[edited_df['📨 Send Email'] == True]
            if selected_em_df.empty:
                st.warning("Pehle table mein se '📨 Send Email' check box tick karein un users ke liye jinko email bhejna hai.")
            else:
                selected_rows_data = selected_em_df.to_dict('records')
                total_mails = len(selected_rows_data)
                ph_ui, update_ui = create_progress_ui("Sending Emails")
                
                with st.spinner("Sending Emails..."):
                    succ, result = send_bulk_emails(selected_rows_data, progress_callback=update_ui)
                    if succ:
                        successful_phones = result
                        for p in successful_phones:
                            conn.execute('''
                                INSERT INTO customer_interactions (phone, email_sent)
                                VALUES (?, 1)
                                ON CONFLICT(phone) DO UPDATE SET email_sent = 1
                            ''', (p,))
                        conn.commit()
                        st.success(f"✅ Successfully sent {len(successful_phones)} Emails and auto-saved their status!")
                        if len(successful_phones) < len(selected_rows_data):
                            st.warning(f"⚠️ Skipped {len(selected_rows_data) - len(successful_phones)} customers because their email address was invalid or missing.")
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Failed to send emails: {result}")

        # ── AUTO-SAVE LOGIC (SQLite Database) ──
        # Compare edited_df with ui_display_df (matching shape)
        diff_wa = ui_display_df['✅ WA Sent'].fillna(False).astype(bool) != edited_df['✅ WA Sent'].fillna(False).astype(bool)
        diff_fwa = ui_display_df['✅ Free WA Sent'].fillna(False).astype(bool) != edited_df['✅ Free WA Sent'].fillna(False).astype(bool)
        diff_em = ui_display_df['📨 Email Sent'].fillna(False).astype(bool) != edited_df['📨 Email Sent'].fillna(False).astype(bool)
        diff_status = ui_display_df['Call Status'].fillna('').astype(str).str.strip() != edited_df['Call Status'].fillna('').astype(str).str.strip()
        diff_status_upd = ui_display_df['Status Update'].fillna('').astype(str).str.strip() != edited_df['Status Update'].fillna('').astype(str).str.strip() if 'Status Update' in ui_display_df.columns and 'Status Update' in edited_df.columns else pd.Series(False, index=ui_display_df.index)
        diff_issue = ui_display_df['Issue Type'].fillna('').astype(str).str.strip() != edited_df['Issue Type'].fillna('').astype(str).str.strip() if 'Issue Type' in ui_display_df.columns and 'Issue Type' in edited_df.columns else pd.Series(False, index=ui_display_df.index)
        diff_poa = ui_display_df['Plan of Action'].fillna('').astype(str).str.strip() != edited_df['Plan of Action'].fillna('').astype(str).str.strip() if 'Plan of Action' in ui_display_df.columns and 'Plan of Action' in edited_df.columns else pd.Series(False, index=ui_display_df.index)
        diff_remarks = ui_display_df['Remarks'].fillna('').astype(str).str.strip() != edited_df['Remarks'].fillna('').astype(str).str.strip()
        diff_credits = pd.to_numeric(ui_display_df['Extra Credits'].fillna(0), errors='coerce').fillna(0).astype(int) != pd.to_numeric(edited_df['Extra Credits'].fillna(0), errors='coerce').fillna(0).astype(int)

        f_ui = pd.to_datetime(ui_display_df['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        f_ed = pd.to_datetime(edited_df['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        diff_follow = f_ui != f_ed

        diff = diff_wa | diff_fwa | diff_em | diff_status | diff_status_upd | diff_issue | diff_poa | diff_remarks | diff_credits | diff_follow

        if diff.any():
            changed_rows = edited_df[diff]
            for idx, row in changed_rows.iterrows():
                p = str(row.get('phone', '')).replace('.0', '').strip()
                if not p: continue
                w = 1 if row['✅ WA Sent'] else 0
                fw = 1 if row['✅ Free WA Sent'] else 0
                c = str(row.get('Call Status', ''))
                su = str(row.get('Status Update', ''))
                it = str(row.get('Issue Type', ''))
                poa = str(row.get('Plan of Action', ''))
                r = str(row['Remarks'])
                f_val = row['Follow-up Date']
                f = str(f_val) if pd.notna(f_val) and str(f_val).strip() not in ['NaT', 'None', 'nan', ''] else ""
                e = 1 if row['📨 Email Sent'] else 0
                ec = int(row['Extra Credits']) if str(row['Extra Credits']).strip() not in ['', 'nan', 'None'] else 0

                # ── AUTO REMARK & EMAIL ALERT ON CALLBACK REQUEST ──
                if (c in ["Call Back Requested", "Call Later"] or su in ["Call Back Requested", "Call Later"]):
                    if "⏰" not in r:
                        r = f"⏰ [Callback Requested: {f or 'Set Date'}] {r}".strip()
                    # Trigger automated email alert to support@credflow.in if status just changed
                    if (diff_status.loc[idx] if idx in diff_status.index else False) or (diff_status_upd.loc[idx] if idx in diff_status_upd.index else False):
                        cx_name = str(row.get('Name', 'Customer'))
                        cx_email = str(row.get('email', ''))
                        plan_name = str(row.get('plan name', ''))
                        succ_mail, _ = send_callback_support_email(cx_name, p, cx_email, plan_name, f, r)
                        if succ_mail:
                            st.toast(f"📧 Callback Alert sent to support@credflow.in for {cx_name}!", icon="⏰")

                now_call_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if c else ""

                conn.execute('''
                    INSERT INTO customer_interactions (phone, wa_sent, free_wa_sent, email_sent, call_status, status_update, issue_type, plan_of_action, remarks, follow_up, extra_credits, last_call_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(phone) DO UPDATE SET
                        wa_sent=excluded.wa_sent,
                        free_wa_sent=excluded.free_wa_sent,
                        email_sent=excluded.email_sent,
                        call_status=excluded.call_status,
                        status_update=excluded.status_update,
                        issue_type=excluded.issue_type,
                        plan_of_action=excluded.plan_of_action,
                        remarks=excluded.remarks,
                        follow_up=excluded.follow_up,
                        extra_credits=excluded.extra_credits,
                        last_call_at=CASE WHEN excluded.call_status != '' THEN excluded.last_call_at ELSE customer_interactions.last_call_at END
                ''', (p, w, fw, e, c, su, it, poa, r, f, ec, now_call_at))
            conn.commit()
def render_telecalling_analytics(conn):
    st.markdown("### 📞 Telecalling Analytics & Performance (Sept 2 - Today)")
    st.info("💡 **Date-Wise Telecalling Performance Tracker**: Real-time monitoring of calls made, connected status, callbacks requested, and unreachable attempts logged starting from **September 2nd, 2026** onwards.")
    
    today_d = datetime.now().date()
    sept2_d = date(2026, 9, 2)
    today_str = today_d.strftime("%Y-%m-%d")
    
    col_date, col_space = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input(
            "🗓️ Select Specific Date to Inspect / Edit Calls",
            value=today_d,
            min_value=sept2_d,
            max_value=today_d,
            key="tele_date_picker"
        )
    
    sel_date_str = selected_date.strftime("%Y-%m-%d")
    sel_date_dmy = selected_date.strftime("%d/%m/%Y")
    
    # Query customer interactions
    interactions_df = pd.read_sql("""
        SELECT * FROM customer_interactions 
        WHERE (call_status IS NOT NULL AND call_status != '')
           OR (remarks IS NOT NULL AND remarks != '')
           OR (follow_up IS NOT NULL AND follow_up != '')
    """, conn)
    
    if not interactions_df.empty:
        # Extract robust call date for grouping
        def _parse_call_date(row):
            l_at = str(row.get('last_call_at', '')).strip()
            if len(l_at) >= 10:
                p_dt = pd.to_datetime(l_at[:10], errors='coerce')
                if pd.notna(p_dt): return p_dt.date()
            f_up = str(row.get('follow_up', '')).strip()
            if f_up and f_up.lower() not in ['none', 'nat', 'nan', '']:
                p_dt = pd.to_datetime(f_up, errors='coerce', dayfirst=True)
                if pd.notna(p_dt): return p_dt.date()
            return today_d

        interactions_df['parsed_call_date'] = interactions_df.apply(_parse_call_date, axis=1)
        
        # ── 1. SELECTED DATE METRICS ──
        date_calls_df = interactions_df[
            (interactions_df['parsed_call_date'] == selected_date) |
            (interactions_df['last_call_at'].fillna('').astype(str).str.startswith(sel_date_str)) |
            (interactions_df['follow_up'].fillna('').astype(str).str.contains(sel_date_str)) |
            (interactions_df['follow_up'].fillna('').astype(str).str.contains(sel_date_dmy))
        ]
        
        if date_calls_df.empty and selected_date == today_d:
            date_calls_df = interactions_df
            
        total_calls = len(date_calls_df)
        total_all_calls = len(interactions_df)
        
        connected_statuses = ["Connected", "Interested", "Converted", "Payment Pending"]
        callback_statuses = ["Call Later", "Call Back Requested", "Busy", "Ringing"]
        unreachable_statuses = ["Not Picked", "Switched Off", "Invalid Number", "Not Interested"]

        calls_connected = len(date_calls_df[date_calls_df['call_status'].isin(connected_statuses)])
        calls_callback = len(date_calls_df[date_calls_df['call_status'].isin(callback_statuses)])
        calls_unreachable = len(date_calls_df[date_calls_df['call_status'].isin(unreachable_statuses)])

        # KPI Metrics Cards for Selected Date
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"📞 Calls Logged ({selected_date.strftime('%d %b %Y')})", f"{total_calls}", help="Calls logged on selected date")
        k2.metric("🟢 Connected / Interested", f"{calls_connected}", delta=f"{round(calls_connected/total_calls*100)}%" if total_calls else "0%")
        k3.metric("🟡 Callback / Busy", f"{calls_callback}", delta=f"{round(calls_callback/total_calls*100)}%" if total_calls else "0%")
        k4.metric("🔴 Not Picked / Unreachable", f"{calls_unreachable}", delta=f"{round(calls_unreachable/total_calls*100)}%" if total_calls else "0%", delta_color="inverse")
        
        st.markdown("---")
        
        # ── 3. DETAILED LOG FOR SELECTED DATE ──
        st.markdown(f"#### 📋 Detailed Call Log for {selected_date.strftime('%d %b %Y')}")
        if not date_calls_df.empty:
            show_cols = [c for c in ['phone', 'call_status', 'status_update', 'issue_type', 'plan_of_action', 'remarks', 'follow_up', 'last_call_at'] if c in date_calls_df.columns]
            st.dataframe(date_calls_df[show_cols], use_container_width=True)
            
            excel_tele = to_excel_download(date_calls_df[show_cols], sheet_name="Telecalling_Log")
            st.download_button("📥 Export Selected Date Call Log (Excel)", data=excel_tele, file_name=f"Telecalling_Log_{sel_date_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        else:
            st.info(f"ℹ️ No calls logged on {sel_date_str} yet. Select another date or update call status in main dashboard.")
    else:
        st.info("ℹ️ No telecalling interactions recorded yet. As agents update call statuses, metrics will appear here.")


def render_batch_comparison(conn):
    st.markdown("### ⚔️ Compare 2 Batches / Datasets (Batch vs Batch Analytics)")
    st.info("💡 **Dataset Comparison Tool**: Select any 2 Upload Batches (e.g. Sept 1 vs Sept 3) to compare Customer Usage Health, KPI changes, and track customer upgrades/degradations over time.")
    
    batches_df = pd.read_sql("SELECT DISTINCT Upload_Batch, COUNT(*) as cnt FROM sales_plan_history GROUP BY Upload_Batch ORDER BY Upload_Batch DESC", conn)
    batch_list = batches_df['Upload_Batch'].tolist()
    
    if len(batch_list) < 2:
        st.warning("⚠️ Comparison requires at least 2 upload batches in history. Please upload another batch or select another dataset.")
        return
        
    b_col1, b_col2 = st.columns(2)
    q_b_old = st.query_params.get("q_batch_old", "")
    q_b_new = st.query_params.get("q_batch_new", "")
    
    idx_old = batch_list.index(q_b_old) if q_b_old in batch_list else min(1, len(batch_list)-1)
    idx_new = batch_list.index(q_b_new) if q_b_new in batch_list else 0

    with b_col1:
        batch_old = st.selectbox("📌 Select Baseline Batch (Batch A / Older)", batch_list, index=idx_old, key="cmp_batch_old")
    with b_col2:
        batch_new = st.selectbox("🎯 Select Comparison Batch (Batch B / Newer)", batch_list, index=idx_new, key="cmp_batch_new")
        
    # if batch_old != q_b_old: st.query_params["q_batch_old"] = batch_old
    # if batch_new != q_b_new: st.query_params["q_batch_new"] = batch_new
        
    if batch_old == batch_new:
        st.warning("⚠️ Please select two DIFFERENT upload batches to compare.")
        return

    # Fetch data using cached function
    df_old = fetch_history_batch(batch_old)
    df_new = fetch_history_batch(batch_new)

    df_old['phone'] = df_old['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df_new['phone'] = df_new['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()

    for c in ['Name', 'phone', 'plan name', 'Usage check', 'Last Sync in 7 days', 'CP Usage in last 7 days', 'Contact details fetched in last 7 days', 'App login done in last 7 days', 'raw_credits']:
        if c in df_old.columns: df_old[c] = df_old[c].replace('', pd.NA).ffill()
        if c in df_new.columns: df_new[c] = df_new[c].replace('', pd.NA).ffill()

    df_old['Usage check'] = df_old.groupby('phone')['Usage check'].transform('first')
    df_new['Usage check'] = df_new.groupby('phone')['Usage check'].transform('first')

    cx_old = df_old.drop_duplicates(subset=['phone'], keep='first').copy()
    cx_new = df_new.drop_duplicates(subset=['phone'], keep='first').copy()

    total_old = len(cx_old)
    total_new = len(cx_new)

    no_old = len(cx_old[cx_old['Usage check'].astype(str).str.contains('No Usage', na=False)])
    no_new = len(cx_new[cx_new['Usage check'].astype(str).str.contains('No Usage', na=False)])

    low_old = len(cx_old[cx_old['Usage check'].astype(str).str.contains('Low Usage', na=False)])
    low_new = len(cx_new[cx_new['Usage check'].astype(str).str.contains('Low Usage', na=False)])

    prop_old = len(cx_old[cx_old['Usage check'].astype(str).str.contains('Proper Usage', na=False)])
    prop_new = len(cx_new[cx_new['Usage check'].astype(str).str.contains('Proper Usage', na=False)])

    # Metrics delta cards
    st.markdown("#### 📊 Side-by-Side KPI Comparison")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("👥 Total Customers", f"A: {total_old} | B: {total_new}", delta=f"{total_new - total_old} ({round((total_new - total_old)/total_old*100) if total_old else 0}%)")
    mc2.metric("🔴 No Usage", f"A: {no_old} | B: {no_new}", delta=f"{no_new - no_old}", delta_color="inverse")
    mc3.metric("🟡 Low Usage", f"A: {low_old} | B: {low_new}", delta=f"{low_new - low_old}", delta_color="off")
    mc4.metric("🟢 Proper Usage", f"A: {prop_old} | B: {prop_new}", delta=f"{prop_new - prop_old}", delta_color="normal")

    # Side-by-Side Bar Chart
    comp_chart_df = pd.DataFrame({
        'Status': ['No Usage 🔴', 'Low Usage 🟡', 'Proper Usage 🟢'] * 2,
        'Batch': ['Batch A (Older)'] * 3 + ['Batch B (Newer)'] * 3,
        'Customers': [no_old, low_old, prop_old, no_new, low_new, prop_new]
    })
    
    fig_comp = px.bar(
        comp_chart_df, x='Status', y='Customers', color='Batch', barmode='group',
        title=f'Batch Comparison Breakdown',
        color_discrete_sequence=['#64748B', '#3B82F6']
    )
    fig_comp.update_layout(height=380, margin=dict(t=40, b=20, l=20, r=20))
    st.plotly_chart(fig_comp, use_container_width=True)

    # Customer Migration Matrix
    cx_new_clean = cx_new.drop(columns=['Name', 'email', 'plan name'], errors='ignore')
    merged = pd.merge(cx_old[['phone', 'Name', 'email', 'plan name', 'Usage check']],
                      cx_new_clean,
                      on='phone', suffixes=(' (Batch A)', ' (Batch B)'))

    # Merge with customer_interactions for Call Status, Issue Type, Remarks, Follow-up Date
    interactions_comp = pd.read_sql("SELECT * FROM customer_interactions", conn)
    if not interactions_comp.empty:
        interactions_comp['phone'] = interactions_comp['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        interactions_comp = interactions_comp.drop_duplicates(subset=['phone'], keep='last')
        merged['merge_phone'] = merged['phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        int_cols = ['phone', 'call_status', 'issue_type', 'remarks', 'follow_up']
        int_cols = [c for c in int_cols if c in interactions_comp.columns]
        merged = pd.merge(merged, interactions_comp[int_cols], left_on='merge_phone', right_on='phone', how='left', suffixes=('', '_db'))
        merged = merged.drop(columns=['phone_db'], errors='ignore')
    else:
        merged['call_status'] = ""
        merged['issue_type'] = ""
        merged['remarks'] = ""
        merged['follow_up'] = ""

    merged['call_status'] = merged['call_status'].fillna("")
    if 'issue_type' not in merged.columns:
        merged['issue_type'] = ""
    merged['issue_type'] = merged['issue_type'].fillna("")
    merged['remarks'] = merged['remarks'].fillna("")
    merged['follow_up'] = pd.to_datetime(merged['follow_up'], errors='coerce').dt.date

    merged = merged.rename(columns={
        'call_status': 'Call Status',
        'issue_type': 'Issue Type',
        'remarks': 'Remarks',
        'follow_up': 'Follow-up Date'
    })

    def _get_health_rank(h_str):
        s = str(h_str)
        if 'Proper' in s: return 3
        if 'Low' in s: return 2
        if 'No' in s: return 1
        return 0

    merged['rank_a'] = merged['Usage check (Batch A)'].apply(_get_health_rank)
    merged['rank_b'] = merged['Usage check (Batch B)'].apply(_get_health_rank)

    upgraded = merged[merged['rank_b'] > merged['rank_a']].copy()
    degraded = merged[merged['rank_b'] < merged['rank_a']].copy()

    st.markdown("#### 🔄 Customer Migration & Movement Analysis")
    st.info("💡 **Interactive Call Notes**: Aap is list mein kisi bhi customer ka **Call Status**, **Remarks / Notes**, aur **Follow-up Date** direct edit karke auto-save kar sakte hain.")

    m_col1, m_col2 = st.columns(2)
    m_col1.success(f"🎉 **{len(upgraded)} Customers Upgraded (Usage Improved 🟢)**")
    m_col2.error(f"⚠️ **{len(degraded)} Customers Degraded (Usage Dropped 🔴)**")

    if not upgraded.empty:
        with st.expander("🟢 View Upgraded Customers List (Editable Notes & Call Status)", expanded=False):
            upg_cols = ['Name', 'phone', 'email', 'plan name', 'Usage check (Batch A)', 'Usage check (Batch B)', 'Call Status', 'Issue Type', 'Remarks', 'Follow-up Date']
            upg_df_export = upgraded.reset_index(drop=True)
            
            # Select All Checkboxes
            u_c1, u_c2, u_c3 = st.columns(3)
            with u_c1: sel_api_u = st.checkbox('✅ Select All WA API', key='u_wa_api')
            with u_c2: sel_em_u = st.checkbox('📧 Select All Email', key='u_em')
            with u_c3: sel_fwa_u = st.checkbox('💬 Select All Free WA', key='u_fwa')

            upg_df_export.insert(0, '✅ Send API', sel_api_u)
            upg_df_export.insert(1, '📧 Send Email', sel_em_u)
            upg_df_export.insert(2, '💬 Send Free WA', sel_fwa_u)
            
            # Helper: rename for generate_wa_link
            temp_upg = upg_df_export.rename(columns={'Usage check (Batch B)': 'Usage check'})
            upg_df_export.insert(3, 'WhatsApp', [generate_wa_link(row) for _, row in temp_upg.iterrows()])
            
            upg_bytes = to_excel_download(upg_df_export[[c for c in upg_cols if c in upg_df_export.columns]], sheet_name="Upgraded Customers")
            st.download_button(
                label=f"🟢 Download Upgraded Customers Excel ({len(upg_df_export)})",
                data=upg_bytes,
                file_name=f"CredFlow_Upgraded_Customers_{batch_old}_vs_{batch_new}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_dl_upgraded"
            )
            
            upg_edited = st.data_editor(
                upg_df_export,
                key=f"ed_upg_{batch_old}_{batch_new}",
                use_container_width=True,
                hide_index=True,
                column_order=['✅ Send API', '📧 Send Email', '💬 Send Free WA', 'WhatsApp'] + upg_cols,
                column_config={
                    "✅ Send API": st.column_config.CheckboxColumn("✅ Send API", default=False),
                    "📧 Send Email": st.column_config.CheckboxColumn("📧 Send Email", default=False),
                    "💬 Send Free WA": st.column_config.CheckboxColumn("💬 Send Free WA", default=False),
                    "WhatsApp": st.column_config.LinkColumn("Open WhatsApp", display_text="Chat 💬"),
                    "Call Status": st.column_config.SelectboxColumn(
                        "Call Status 📞",
                        options=["", "Connected", "Not Picked", "Switched Off", "Invalid Number", "Call Later", "Interested", "Not Interested", "Busy", "Ringing", "Call Back Requested", "Converted", "Payment Pending", "Payment Not Verified"],
                        width="medium"
                    ),
                    "Issue Type": st.column_config.SelectboxColumn(
                        "Issue Type 🏷️",
                        options=[""] + [r[0] for r in conn.execute("SELECT issue_name FROM issue_types ORDER BY issue_name").fetchall()],
                        width="medium"
                    ),
                    "Remarks": st.column_config.TextColumn("Remarks / Notes 📝", width="large"),
                    "Follow-up Date": st.column_config.DateColumn("Follow-up Date 📅", format="DD/MM/YYYY")
                },
                disabled=["Name", "phone", "email", "plan name", "Usage check (Batch A)", "Usage check (Batch B)", "WhatsApp"]
            )

            # ── BULK ACTIONS (UPGRADED) ──
            upg_b1, upg_b2, upg_b3 = st.columns(3)
            with upg_b1: btn_wa_u = st.button("📱 Send via WA API", type="primary", use_container_width=True, key="btn_wa_u")
            with upg_b2: btn_em_u = st.button("📧 Send via Email", type="primary", use_container_width=True, key="btn_em_u")
            with upg_b3: btn_fw_u = st.button("💬 Send via Free WA", type="secondary", use_container_width=True, key="btn_fw_u")

            if btn_wa_u:
                selected_wa_u = upg_edited[upg_edited['✅ Send API'] == True]
                if selected_wa_u.empty:
                    st.warning("Pehle table mein se '✅ Send API' check box tick karein.")
                else:
                    success_count = 0
                    error_count = 0
                    total_wa = len(selected_wa_u)
                    ph_ui, update_ui = create_progress_ui("Sending WhatsApp (API)")
                    
                    for idx, row in enumerate(selected_wa_u.to_dict('records')):
                        credits = row.get('raw_credits', '0')
                        name = str(row.get('Name', ''))
                        phone_val = str(row.get('phone', '')).strip()
                        email_val = str(row.get('email', '')).strip()
                        tier_val = str(row.get('Usage check (Batch B)', ''))
                        succ, msg = send_interakt_msg(phone_val, name, tier_val, credits)
                        if succ:
                            success_count += 1
                            p = phone_val.replace('.0', '').strip()
                            log_outreach_event("WhatsApp API", tier_val, name, p, email_val, "Interakt WA Template", "SUCCESS")
                        else:
                            error_count += 1
                            log_outreach_event("WhatsApp API", tier_val, name, phone_val, email_val, "Interakt WA Template", "FAILED", str(msg))
                            if msg == "WALLET_INSUFFICIENT_BALANCE":
                                st.error("⚠️ **Interakt WA API Error: Insufficient Wallet Balance!** Kripya [app.interakt.ai](https://app.interakt.ai) par wallet recharge karein. Alternately, '💬 Send via Free WA' option use karein.")
                                break
                        update_ui(idx + 1, total_wa, name, success_count, error_count)
                        
                    conn.commit()
                    if success_count > 0:
                        st.success(f"✅ WA API Sent to {success_count} customers!")
                        import time
                        time.sleep(1)
                        st.rerun()

            if btn_em_u:
                selected_em_u = upg_edited[upg_edited['📧 Send Email'] == True].copy()
                if selected_em_u.empty:
                    st.warning("Pehle table mein se '📧 Send Email' check box tick karein.")
                else:
                    selected_em_u['Usage check'] = selected_em_u['Usage check (Batch B)']
                    selected_rows_data = selected_em_u.to_dict('records')
                    total_mails = len(selected_rows_data)
                    ph_ui, update_ui = create_progress_ui("Sending Emails")
                    
                    with st.spinner("Sending Emails..."):
                        succ, result = send_bulk_emails(selected_rows_data, progress_callback=update_ui)
                        if succ:
                            successful_phones = result
                            for p in successful_phones:
                                conn.execute('INSERT INTO customer_interactions (phone, email_sent) VALUES (?, 1) ON CONFLICT(phone) DO UPDATE SET email_sent = 1', (p,))
                            conn.commit()
                            st.success(f"✅ Emails sent to: {len(successful_phones)} customers!")
                            import time
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")

            if btn_fw_u:
                import webbrowser, time, pyautogui
                selected_fwa_u = upg_edited[upg_edited['💬 Send Free WA'] == True]
                if selected_fwa_u.empty:
                    st.warning("Pehle table mein se '💬 Send Free WA' check box tick karein.")
                else:
                    st.warning(f"⚠️ AUTO-SENDING WhatsApp for {len(selected_fwa_u)} customers. KRIPYA APNE MOUSE AUR KEYBOARD KO HAATH NA LAGAYEIN!")
                    success_count = 0
                    error_count = 0
                    total_fwa = len(selected_fwa_u)
                    ph_ui, update_ui = create_progress_ui("Sending Free WhatsApp")
                    
                    for idx, row in enumerate(selected_fwa_u.to_dict('records')):
                        name = str(row.get('Name', ''))
                        p = str(row.get('phone', '')).replace('.0', '').strip()
                        link = row.get('WhatsApp', '')
                        if not link or str(link).strip() == '':
                            row['Usage check'] = row.get('Usage check (Batch B)', '')
                            link = generate_wa_link(row)
                            
                        if link:
                            if p:
                                log_outreach_event("Free WhatsApp", row.get('Usage check (Batch B)', ''), name, p, row.get('email', ''), 'Free WA Web Link', 'SUCCESS')
                            webbrowser.open(link)
                            time.sleep(10)
                            pyautogui.press('enter')
                            time.sleep(1)
                            pyautogui.hotkey('ctrl', 'w')
                            time.sleep(1)
                            success_count += 1
                        else:
                            error_count += 1
                            
                        update_ui(idx + 1, total_fwa, name, success_count, error_count)
                        
                    conn.commit()
                    st.success(f"✅ Auto WhatsApp Sending Complete! Sent {success_count} messages.")
                    time.sleep(2)
                    st.rerun()

            # Auto-save edits for Upgraded list
            diff_status = upg_df_export['Call Status'].fillna('').astype(str).str.strip() != upg_edited['Call Status'].fillna('').astype(str).str.strip()
            diff_issue = upg_df_export['Issue Type'].fillna('').astype(str).str.strip() != upg_edited['Issue Type'].fillna('').astype(str).str.strip() if 'Issue Type' in upg_df_export.columns and 'Issue Type' in upg_edited.columns else pd.Series(False, index=upg_df_export.index)
            diff_remarks = upg_df_export['Remarks'].fillna('').astype(str).str.strip() != upg_edited['Remarks'].fillna('').astype(str).str.strip()
            f_ui = pd.to_datetime(upg_df_export['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            f_ed = pd.to_datetime(upg_edited['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            diff_follow = f_ui != f_ed

            diff = diff_status | diff_issue | diff_remarks | diff_follow
            if diff.any():
                for _, row in upg_edited[diff].iterrows():
                    p = str(row.get('phone', '')).replace('.0', '').strip()
                    if not p: continue
                    c = str(row['Call Status'])
                    it = str(row.get('Issue Type', ''))
                    r = str(row['Remarks'])
                    f_val = row['Follow-up Date']
                    f = str(f_val) if pd.notna(f_val) and str(f_val).strip() not in ['NaT', 'None', 'nan', ''] else ""
                    
                    conn.execute('''
                        INSERT INTO customer_interactions (phone, call_status, issue_type, remarks, follow_up)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(phone) DO UPDATE SET
                            call_status=excluded.call_status,
                            issue_type=excluded.issue_type,
                            remarks=excluded.remarks,
                            follow_up=excluded.follow_up
                    ''', (p, c, it, r, f))
                conn.commit()
                st.toast("✅ Auto-saved!", icon="💾")

    if not degraded.empty:
        with st.expander("🔴 View Degraded Customers List (Editable Notes & Call Status)", expanded=False):
            deg_cols = ['Name', 'phone', 'email', 'plan name', 'Usage check (Batch A)', 'Usage check (Batch B)', 'Call Status', 'Issue Type', 'Remarks', 'Follow-up Date']
            deg_df_export = degraded.reset_index(drop=True)
            
            # Select All Checkboxes
            d_c1, d_c2, d_c3 = st.columns(3)
            with d_c1: sel_api_d = st.checkbox('✅ Select All WA API', key='d_wa_api')
            with d_c2: sel_em_d = st.checkbox('📧 Select All Email', key='d_em')
            with d_c3: sel_fwa_d = st.checkbox('💬 Select All Free WA', key='d_fwa')

            deg_df_export.insert(0, '✅ Send API', sel_api_d)
            deg_df_export.insert(1, '📧 Send Email', sel_em_d)
            deg_df_export.insert(2, '💬 Send Free WA', sel_fwa_d)
            
            # Helper: rename for generate_wa_link
            temp_deg = deg_df_export.rename(columns={'Usage check (Batch B)': 'Usage check'})
            deg_df_export.insert(3, 'WhatsApp', [generate_wa_link(row) for _, row in temp_deg.iterrows()])
            
            deg_bytes = to_excel_download(deg_df_export[[c for c in deg_cols if c in deg_df_export.columns]], sheet_name="Degraded Customers")
            st.download_button(
                label=f"🔴 Download Degraded Customers Excel ({len(deg_df_export)})",
                data=deg_bytes,
                file_name=f"CredFlow_Degraded_Customers_{batch_old}_vs_{batch_new}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_dl_degraded"
            )
            
            deg_edited = st.data_editor(
                deg_df_export,
                key=f"ed_deg_{batch_old}_{batch_new}",
                use_container_width=True,
                hide_index=True,
                column_order=['✅ Send API', '📧 Send Email', '💬 Send Free WA', 'WhatsApp'] + deg_cols,
                column_config={
                    "✅ Send API": st.column_config.CheckboxColumn("✅ Send API", default=False),
                    "📧 Send Email": st.column_config.CheckboxColumn("📧 Send Email", default=False),
                    "💬 Send Free WA": st.column_config.CheckboxColumn("💬 Send Free WA", default=False),
                    "WhatsApp": st.column_config.LinkColumn("Open WhatsApp", display_text="Chat 💬"),
                    "Call Status": st.column_config.SelectboxColumn(
                        "Call Status 📞",
                        options=["", "Connected", "Not Picked", "Switched Off", "Invalid Number", "Call Later", "Interested", "Not Interested", "Busy", "Ringing", "Call Back Requested", "Converted", "Payment Pending", "Payment Not Verified"],
                        width="medium"
                    ),
                    "Issue Type": st.column_config.SelectboxColumn(
                        "Issue Type 🏷️",
                        options=[""] + [r[0] for r in conn.execute("SELECT issue_name FROM issue_types ORDER BY issue_name").fetchall()],
                        width="medium"
                    ),
                    "Remarks": st.column_config.TextColumn("Remarks / Notes 📝", width="large"),
                    "Follow-up Date": st.column_config.DateColumn("Follow-up Date 📅", format="DD/MM/YYYY")
                },
                disabled=["Name", "phone", "email", "plan name", "Usage check (Batch A)", "Usage check (Batch B)", "WhatsApp"]
            )

            # ── BULK ACTIONS (DEGRADED) ──
            deg_b1, deg_b2, deg_b3 = st.columns(3)
            with deg_b1: btn_wa_d = st.button("📱 Send via WA API", type="primary", use_container_width=True, key="btn_wa_d")
            with deg_b2: btn_em_d = st.button("📧 Send via Email", type="primary", use_container_width=True, key="btn_em_d")
            with deg_b3: btn_fw_d = st.button("💬 Send via Free WA", type="secondary", use_container_width=True, key="btn_fw_d")

            if btn_wa_d:
                selected_wa_d = deg_edited[deg_edited['✅ Send API'] == True]
                if selected_wa_d.empty:
                    st.warning("Pehle table mein se '✅ Send API' check box tick karein.")
                else:
                    success_count = 0
                    error_count = 0
                    total_wa = len(selected_wa_d)
                    ph_ui, update_ui = create_progress_ui("Sending WhatsApp (API)")
                    
                    for idx, row in enumerate(selected_wa_d.to_dict('records')):
                        credits = row.get('raw_credits', '0')
                        name = str(row.get('Name', ''))
                        phone_val = str(row.get('phone', '')).strip()
                        email_val = str(row.get('email', '')).strip()
                        tier_val = str(row.get('Usage check (Batch B)', ''))
                        succ, msg = send_interakt_msg(phone_val, name, tier_val, credits)
                        if succ:
                            success_count += 1
                            p = phone_val.replace('.0', '').strip()
                            log_outreach_event("WhatsApp API", tier_val, name, p, email_val, "Interakt WA Template", "SUCCESS")
                        else:
                            error_count += 1
                            log_outreach_event("WhatsApp API", tier_val, name, phone_val, email_val, "Interakt WA Template", "FAILED", str(msg))
                            if msg == "WALLET_INSUFFICIENT_BALANCE":
                                st.error("⚠️ **Interakt WA API Error: Insufficient Wallet Balance!** Kripya [app.interakt.ai](https://app.interakt.ai) par wallet recharge karein. Alternately, '💬 Send via Free WA' option use karein.")
                                break
                        update_ui(idx + 1, total_wa, name, success_count, error_count)
                        
                    conn.commit()
                    if success_count > 0:
                        st.success(f"✅ WA API Sent to {success_count} customers!")
                        import time
                        time.sleep(1)
                        st.rerun()

            if btn_em_d:
                selected_em_d = deg_edited[deg_edited['📧 Send Email'] == True].copy()
                if selected_em_d.empty:
                    st.warning("Pehle table mein se '📧 Send Email' check box tick karein.")
                else:
                    selected_em_d['Usage check'] = selected_em_d['Usage check (Batch B)']
                    selected_rows_data = selected_em_d.to_dict('records')
                    total_mails = len(selected_rows_data)
                    ph_ui, update_ui = create_progress_ui("Sending Emails")
                    
                    with st.spinner("Sending Emails..."):
                        succ, result = send_bulk_emails(selected_rows_data, progress_callback=update_ui)
                        if succ:
                            successful_phones = result
                            for p in successful_phones:
                                conn.execute('INSERT INTO customer_interactions (phone, email_sent) VALUES (?, 1) ON CONFLICT(phone) DO UPDATE SET email_sent = 1', (p,))
                            conn.commit()
                            st.success(f"✅ Emails sent to: {len(successful_phones)} customers!")
                            import time
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Failed: {result}")

            if btn_fw_d:
                import webbrowser, time, pyautogui
                selected_fwa_d = deg_edited[deg_edited['💬 Send Free WA'] == True]
                if selected_fwa_d.empty:
                    st.warning("Pehle table mein se '💬 Send Free WA' check box tick karein.")
                else:
                    st.warning(f"⚠️ AUTO-SENDING WhatsApp for {len(selected_fwa_d)} customers. KRIPYA APNE MOUSE AUR KEYBOARD KO HAATH NA LAGAYEIN!")
                    success_count = 0
                    error_count = 0
                    total_fwa = len(selected_fwa_d)
                    ph_ui, update_ui = create_progress_ui("Sending Free WhatsApp")
                    
                    for idx, row in enumerate(selected_fwa_d.to_dict('records')):
                        name = str(row.get('Name', ''))
                        p = str(row.get('phone', '')).replace('.0', '').strip()
                        link = row.get('WhatsApp', '')
                        if not link or str(link).strip() == '':
                            row['Usage check'] = row.get('Usage check (Batch B)', '')
                            link = generate_wa_link(row)
                            
                        if link:
                            if p:
                                log_outreach_event("Free WhatsApp", row.get('Usage check (Batch B)', ''), name, p, row.get('email', ''), 'Free WA Web Link', 'SUCCESS')
                            webbrowser.open(link)
                            time.sleep(10)
                            pyautogui.press('enter')
                            time.sleep(1)
                            pyautogui.hotkey('ctrl', 'w')
                            time.sleep(1)
                            success_count += 1
                        else:
                            error_count += 1
                            
                        update_ui(idx + 1, total_fwa, name, success_count, error_count)
                        
                    conn.commit()
                    st.success(f"✅ Auto WhatsApp Sending Complete! Sent {success_count} messages.")
                    time.sleep(2)
                    st.rerun()

            # Auto-save edits for Degraded list
            diff_status = deg_df_export['Call Status'].fillna('').astype(str).str.strip() != deg_edited['Call Status'].fillna('').astype(str).str.strip()
            diff_issue = deg_df_export['Issue Type'].fillna('').astype(str).str.strip() != deg_edited['Issue Type'].fillna('').astype(str).str.strip() if 'Issue Type' in deg_df_export.columns and 'Issue Type' in deg_edited.columns else pd.Series(False, index=deg_df_export.index)
            diff_remarks = deg_df_export['Remarks'].fillna('').astype(str).str.strip() != deg_edited['Remarks'].fillna('').astype(str).str.strip()
            f_ui = pd.to_datetime(deg_df_export['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            f_ed = pd.to_datetime(deg_edited['Follow-up Date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            diff_follow = f_ui != f_ed

            diff = diff_status | diff_issue | diff_remarks | diff_follow
            if diff.any():
                for _, row in deg_edited[diff].iterrows():
                    p = str(row.get('phone', '')).replace('.0', '').strip()
                    if not p: continue
                    c = str(row['Call Status'])
                    it = str(row.get('Issue Type', ''))
                    r = str(row['Remarks'])
                    f_val = row['Follow-up Date']
                    f = str(f_val) if pd.notna(f_val) and str(f_val).strip() not in ['NaT', 'None', 'nan', ''] else ""
                    
                    conn.execute('''
                        INSERT INTO customer_interactions (phone, call_status, issue_type, remarks, follow_up)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(phone) DO UPDATE SET
                            call_status=excluded.call_status,
                            issue_type=excluded.issue_type,
                            remarks=excluded.remarks,
                            follow_up=excluded.follow_up
                    ''', (p, c, it, r, f))
                conn.commit()
                st.toast("✅ Auto-saved!", icon="💾")


def render_outreach_history(conn):
    import pandas as pd
    from datetime import datetime, date, timedelta

    st.markdown("""
    <div style="background: #FFFFFF; padding: 18px 22px; border-radius: 12px; border: 1px solid #E2E8F0; border-top: 4px solid #2563EB; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
            <div>
                <h3 style="margin: 0; color: #0F172A; font-size: 20px; font-weight: 700;">📜 Outreach & Dispatch Audit History</h3>
                <p style="color: #64748B; font-size: 13px; margin-top: 4px; margin-bottom: 0;">
                    Real-time logged history of all Email (SMTP), WhatsApp API (Interakt), and Free WhatsApp dispatches. Tracks every single sent message with timestamp even if the page refreshes!
                </p>
            </div>
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; padding: 4px 12px; border-radius: 20px; color: #1D4ED8; font-weight: 600; font-size: 12px;">
                ⚡ Real-time Audit Logger Active
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Auto-backfill legacy customer_interactions dispatches into outreach_logs if outreach_logs is empty
    log_cnt = conn.execute("SELECT COUNT(*) FROM outreach_logs").fetchone()[0]
    if log_cnt == 0:
        try:
            cur = conn.execute('''
                SELECT ci.phone, sph.Name, sph.email, ci.email_sent, ci.wa_sent, ci.free_wa_sent
                FROM customer_interactions ci
                LEFT JOIN sales_plan_history sph ON sph.phone LIKE '%' || ci.phone || '%'
                WHERE ci.email_sent = 1 OR ci.wa_sent = 1 OR ci.free_wa_sent = 1
                GROUP BY ci.phone
            ''')
            legacy_rows = cur.fetchall()
            today_str = datetime.now().strftime("%Y-%m-%d 10:00:00")
            for p, n, em, e_sent, w_sent, fw_sent in legacy_rows:
                c_name = n if n else "Customer"
                c_email = em if em else ""
                if e_sent:
                    conn.execute('''INSERT INTO outreach_logs (timestamp, channel, health_tier, customer_name, phone, email, subject, status)
                                   VALUES (?, 'Email', 'Batch Dispatch', ?, ?, ?, 'Outreach Email', 'SUCCESS')''',
                                 (today_str, c_name, p, c_email))
                if w_sent:
                    conn.execute('''INSERT INTO outreach_logs (timestamp, channel, health_tier, customer_name, phone, email, subject, status)
                                   VALUES (?, 'WhatsApp API', 'Batch Dispatch', ?, ?, ?, 'Interakt WA', 'SUCCESS')''',
                                 (today_str, c_name, p, c_email))
                if fw_sent:
                    conn.execute('''INSERT INTO outreach_logs (timestamp, channel, health_tier, customer_name, phone, email, subject, status)
                                   VALUES (?, 'Free WhatsApp', 'Batch Dispatch', ?, ?, ?, 'Free WA Web', 'SUCCESS')''',
                                 (today_str, c_name, p, c_email))
            conn.commit()
        except Exception:
            pass

    # Today's Date Metrics
    emails_today = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE channel = 'Email' AND status = 'SUCCESS' AND date(timestamp) = date('now', 'localtime')").fetchone()[0]
    wa_today = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE channel LIKE '%WA API%' AND status = 'SUCCESS' AND date(timestamp) = date('now', 'localtime')").fetchone()[0]
    fwa_today = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE channel LIKE '%Free WA%' AND status = 'SUCCESS' AND date(timestamp) = date('now', 'localtime')").fetchone()[0]
    failed_today = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE status = 'FAILED' AND date(timestamp) = date('now', 'localtime')").fetchone()[0]
    total_emails = conn.execute("SELECT COUNT(*) FROM outreach_logs WHERE channel = 'Email' AND status = 'SUCCESS'").fetchone()[0]

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("📧 Emails Today", f"{emails_today}", help="Successfully sent emails today")
    with m2:
        st.metric("📱 WA API Today", f"{wa_today}", help="WhatsApp API messages sent today")
    with m3:
        st.metric("💬 Free WA Today", f"{fwa_today}", help="Free WA web messages sent today")
    with m4:
        st.metric("❌ Failed Today", f"{failed_today}", help="Failed dispatches today")
    with m5:
        st.metric("📦 Total Emails (All-Time)", f"{total_emails}", help="Total emails sent across all uploads")

    st.markdown("---")

    # Filters
    f1, f2, f3, f4 = st.columns([2, 2, 2, 3])
    with f1:
        dt_filter = st.selectbox("📅 Date Filter", ["Today", "Yesterday", "Last 7 Days", "All Time"], index=0, key="hist_dt_flt")
    with f2:
        ch_filter = st.selectbox("📡 Dispatch Channel", ["All Channels", "Email", "WhatsApp API", "Free WhatsApp"], index=0, key="hist_ch_flt")
    with f3:
        st_filter = st.selectbox("🎯 Status", ["All Statuses", "SUCCESS", "FAILED"], index=0, key="hist_st_flt")
    with f4:
        search_q = st.text_input("🔍 Search Customer (Name / Phone / Email)", value="", key="hist_search_input")

    where_clauses = []
    params = []

    if dt_filter == "Today":
        where_clauses.append("date(timestamp) = date('now', 'localtime')")
    elif dt_filter == "Yesterday":
        where_clauses.append("date(timestamp) = date('now', 'localtime', '-1 day')")
    elif dt_filter == "Last 7 Days":
        where_clauses.append("date(timestamp) >= date('now', 'localtime', '-7 days')")

    if ch_filter != "All Channels":
        where_clauses.append("channel LIKE ?")
        params.append(f"%{ch_filter}%")

    if st_filter != "All Statuses":
        where_clauses.append("status = ?")
        params.append(st_filter)

    if search_q.strip():
        q_like = f"%{search_q.strip()}%"
        where_clauses.append("(customer_name LIKE ? OR phone LIKE ? OR email LIKE ?)")
        params.extend([q_like, q_like, q_like])

    sql_str = "SELECT timestamp as 'Timestamp 🕒', channel as 'Channel 📡', customer_name as 'Customer Name 👤', phone as 'Phone 📞', email as 'Email ✉️', health_tier as 'Health Tier 🎯', subject as 'Subject / Template 📝', status as 'Status ⚡', error_message as 'Notes / Error ℹ️' FROM outreach_logs"
    if where_clauses:
        sql_str += " WHERE " + " AND ".join(where_clauses)
    sql_str += " ORDER BY id DESC"

    df_hist = pd.read_sql(sql_str, conn, params=params)

    st.markdown(f"#### 📋 Sent Messages & Dispatch Audit Table ({len(df_hist)} records)")

    if not df_hist.empty:
        st.dataframe(
            df_hist,
            use_container_width=True,
            height=450
        )

        dl_bytes = to_excel_download(df_hist, sheet_name="Outreach History Log")
        st.download_button(
            label=f"📥 Download Outreach History Log Excel ({len(df_hist)} rows)",
            data=dl_bytes,
            file_name=f"CredFlow_Outreach_Audit_History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_dl_outreach_audit_hist"
        )
    else:
        st.info("No outreach logs found matching the selected filters.")


def render_template_manager(conn):
    import streamlit.components.v1 as components
    from datetime import datetime, date, timedelta

    st.markdown("""
    <div style="background: #FFFFFF; padding: 18px 22px; border-radius: 12px; border: 1px solid #E2E8F0; border-top: 4px solid #10B981; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
            <div>
                <h3 style="margin: 0; color: #0F172A; font-size: 20px; font-weight: 700;">📝 Outreach Message Templates Manager</h3>
                <p style="color: #64748B; font-size: 13px; margin-top: 4px; margin-bottom: 0;">
                    View & customize templates used for Email (SMTP), Free WhatsApp Web, and Interakt WA API dispatches. All outgoing messages use these live saved templates!
                </p>
            </div>
            <div style="background: #ECFDF5; border: 1px solid #A7F3D0; padding: 4px 12px; border-radius: 20px; color: #047857; font-weight: 600; font-size: 12px;">
                🟢 Active Template Sync Enabled
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    sub_tab_email, sub_tab_wa, sub_tab_interakt = st.tabs([
        "📧 Email Templates (SMTP)",
        "💬 Free WhatsApp Web Templates",
        "📲 Interakt WA API Templates"
    ])

    sample_name = "Rajesh Sharma"
    sample_plan = "Lite Plan"
    sample_inc_html = "<ul style='list-style-type: none; padding-left: 0;'><li style='margin-bottom: 5px; color: #047857;'><b>✅ Payment Remainder Email</b></li><li style='margin-bottom: 5px; color: #047857;'><b>✅ 1 Users</b></li></ul>"
    sample_miss_html = "<ul style='list-style-type: none; padding-left: 0;'><li style='margin-bottom: 5px; color: #DC2626;'><b>❌ WhatsApp API</b></li><li style='margin-bottom: 5px; color: #DC2626;'><b>❌ AI Accountant</b></li></ul>"
    sample_reply_link = "https://wa.me/917217716636?text=Hi%20CredFlow%20Team"
    sample_issue_link = "mailto:support@credflow.in?subject=Issue"

    with sub_tab_email:
        st.markdown("#### 📧 Email Templates (SMTP Bulk Dispatch)")
        st.info("💡 **Available Dynamic Variables**: `{name}`, `{plan_name_str}`, `{inc_html}`, `{miss_html}`, `{wa_reply_link}`, `{wa_upg_link}`, `{issue_sync}`, `{issue_tech}`, `{issue_other}`")
        
        email_tiers = [
            ("email_no_usage", "🔴 No Usage Tier Email Template"),
            ("email_low_usage", "🟡 Low Usage Tier Email Template"),
            ("email_proper_usage", "🟢 Proper Usage Tier Email Template")
        ]

        for t_id, label in email_tiers:
            tpl = fetch_template(t_id)
            with st.expander(f"📌 {label}", expanded=(t_id == "email_no_usage")):
                new_sub = st.text_input(f"Subject Line ({t_id})", value=tpl.get("subject", ""), key=f"sub_{t_id}")
                new_body = st.text_area(f"Email HTML Body ({t_id})", value=tpl.get("body", ""), height=280, key=f"body_{t_id}")
                
                col_save, col_reset, col_space = st.columns([2, 2, 6])
                with col_save:
                    if st.button(f"💾 Save Template", key=f"save_{t_id}", type="primary"):
                        conn.execute("UPDATE outreach_templates SET subject = ?, body = ?, updated_at = ? WHERE template_id = ?",
                                     (new_sub, new_body, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"✅ Saved {label}!", icon="💾")
                        st.rerun()
                with col_reset:
                    if st.button(f"🔄 Reset Default", key=f"reset_{t_id}"):
                        def_tpl = DEFAULT_OUTREACH_TEMPLATES[t_id]
                        conn.execute("UPDATE outreach_templates SET subject = ?, body = ?, updated_at = ? WHERE template_id = ?",
                                     (def_tpl["subject"], def_tpl["body"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"🔄 Reset {label} to default!", icon="🔄")
                        st.rerun()

                st.markdown("##### 👁️ Live Rendered Email Preview")
                try:
                    rendered_body = fill_template_vars(new_body, {
                        "name": sample_name,
                        "plan_name_str": sample_plan,
                        "inc_html": sample_inc_html,
                        "miss_html": sample_miss_html,
                        "wa_reply_link": sample_reply_link,
                        "wa_upg_link": sample_reply_link,
                        "issue_sync": sample_issue_link,
                        "issue_tech": sample_issue_link,
                        "issue_other": sample_issue_link
                    })
                    components.html(rendered_body, height=420, scrolling=True)
                except Exception as ex:
                    st.error(f"Error rendering preview: {ex}")

    with sub_tab_wa:
        st.markdown("#### 💬 Free WhatsApp Web Templates")
        st.info("💡 **Available Dynamic Variables**: `{name}`, `{plan_name}`, `{feat_section}`, `{inc_sec}`, `{upg_sec}`, `{reply_link}`, `{upg_link}`")

        wa_tiers = [
            ("wa_free_no_usage", "🔴 No Usage Tier WhatsApp Template"),
            ("wa_free_low_usage", "🟡 Low Usage Tier WhatsApp Template"),
            ("wa_free_proper_usage", "🟢 Proper Usage Tier WhatsApp Template")
        ]

        for t_id, label in wa_tiers:
            tpl = fetch_template(t_id)
            with st.expander(f"📌 {label}", expanded=(t_id == "wa_free_no_usage")):
                new_body = st.text_area(f"WhatsApp Message Body ({t_id})", value=tpl.get("body", ""), height=220, key=f"body_{t_id}")
                
                col_save, col_reset, col_space = st.columns([2, 2, 6])
                with col_save:
                    if st.button(f"💾 Save Template", key=f"save_{t_id}", type="primary"):
                        conn.execute("UPDATE outreach_templates SET body = ?, updated_at = ? WHERE template_id = ?",
                                     (new_body, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"✅ Saved {label}!", icon="💾")
                        st.rerun()
                with col_reset:
                    if st.button(f"🔄 Reset Default", key=f"reset_{t_id}"):
                        def_tpl = DEFAULT_OUTREACH_TEMPLATES[t_id]
                        conn.execute("UPDATE outreach_templates SET body = ?, updated_at = ? WHERE template_id = ?",
                                     (def_tpl["body"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"🔄 Reset {label} to default!", icon="🔄")
                        st.rerun()

                st.markdown("##### 👁️ Live Rendered Message Preview")
                try:
                    feat_sec_sample = f"\n\n💡 Aapke plan ({sample_plan}) mein ye features included hain:\n✅ Payment Remainder Email\n✅ 1 Users"
                    inc_sec_sample = f"✅ **Aapke Active Plan ({sample_plan}) ke Included Features:**\n✅ Payment Remainder Email"
                    upg_sec_sample = f"\n\n🚀 **Unlock 100% Automation:**\n❌ WhatsApp API"
                    
                    rendered_wa = fill_template_vars(new_body, {
                        "name": sample_name,
                        "plan_name": sample_plan,
                        "feat_section": feat_sec_sample,
                        "inc_sec": inc_sec_sample,
                        "upg_sec": upg_sec_sample,
                        "reply_link": sample_reply_link,
                        "upg_link": sample_reply_link
                    })
                    st.code(rendered_wa, language="markdown")
                except Exception as ex:
                    st.error(f"Error rendering preview: {ex}")

    with sub_tab_interakt:
        st.markdown("#### 📲 Interakt WA API Templates")
        st.warning("⚠️ **Note**: Interakt API templates are registered and approved on your Interakt Dashboard. Update the exact approved template name below for each health tier.")

        interakt_tiers = [
            ("interakt_no_usage", "🔴 No Usage Tier Interakt Template", "credflow_no_usage", "{{1}} = Name"),
            ("interakt_low_usage", "🟡 Low Usage Tier Interakt Template", "credflow_low_usage", "{{1}} = Name, {{2}} = Credits"),
            ("interakt_proper_usage", "🟢 Proper Usage Tier Interakt Template", "credflow_proper_usage", "{{1}} = Name, {{2}} = Credits")
        ]

        for t_id, label, default_name, vars_info in interakt_tiers:
            tpl = fetch_template(t_id)
            with st.expander(f"📌 {label}", expanded=False):
                st.caption(f"Parameters expected by Interakt for this tier: **{vars_info}**")
                new_name = st.text_input(f"Approved Template Name on Interakt Dashboard ({t_id})", value=tpl.get("subject", default_name), key=f"name_{t_id}")
                new_desc = st.text_area(f"Template Overview / Description ({t_id})", value=tpl.get("body", ""), height=100, key=f"body_{t_id}")

                col_save, col_reset, col_space = st.columns([2, 2, 6])
                with col_save:
                    if st.button(f"💾 Save Config", key=f"save_{t_id}", type="primary"):
                        conn.execute("UPDATE outreach_templates SET subject = ?, body = ?, updated_at = ? WHERE template_id = ?",
                                     (new_name, new_desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"✅ Updated Interakt settings for {label}!", icon="💾")
                        st.rerun()
                with col_reset:
                    if st.button(f"🔄 Reset Default", key=f"reset_{t_id}"):
                        def_tpl = DEFAULT_OUTREACH_TEMPLATES[t_id]
                        conn.execute("UPDATE outreach_templates SET subject = ?, body = ?, updated_at = ? WHERE template_id = ?",
                                     (def_tpl["subject"], def_tpl["body"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_id))
                        conn.commit()
                        st.toast(f"🔄 Reset {label} to default!", icon="🔄")
                        st.rerun()


# ── LOGO & HEADER SETUP ──
logo_path = os.path.join(os.path.dirname(__file__), "credflow_logo.png")
if not os.path.exists(logo_path):
    logo_path = r"C:\Users\ss002\.gemini\antigravity\scratch\credflow_ppt\credflow_logo.png"

if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)


# ── SIDEBAR ACCESS CONTROL (ADMIN VS VIEW-ONLY) ──
if 'admin_unlocked' not in st.session_state:
    st.session_state['admin_unlocked'] = False

st.sidebar.markdown("## 🔒 Access & Role Control")
role_mode = st.sidebar.radio(
    "Select Access Mode",
    ["👁️ View-Only Mode", "🔑 Admin Access"],
    index=1 if st.session_state['admin_unlocked'] else 0,
    help="View-Only Mode lets everyone inspect data & dashboards safely. Admin Access unlocks data upload & deletion."
)

if role_mode == "🔑 Admin Access":
    if not st.session_state['admin_unlocked']:
        pass_input = st.sidebar.text_input("Enter Admin Password", type="password", key="admin_pwd_input")
        if st.sidebar.button("🔓 Unlock Admin Mode", type="primary", use_container_width=True):
            if pass_input == "credflow2026":
                st.session_state['admin_unlocked'] = True
                st.sidebar.success("✅ Admin Mode Unlocked!")
                st.rerun()
            else:
                st.sidebar.error("❌ Incorrect Admin Password!")
    else:
        st.sidebar.success("🟢 Admin Mode Active")
        if st.sidebar.button("🔒 Lock Admin Access", use_container_width=True):
            st.session_state['admin_unlocked'] = False
            st.rerun()
else:
    st.session_state['admin_unlocked'] = False
    st.sidebar.info("👁️ View-Only Mode Active. File uploads & batch deletions are locked.")

is_admin = st.session_state.get('admin_unlocked', False)


tab_dash, tab_tele, tab_comp, tab_hist, tab_tpl, tab_upload = st.tabs([
    "📊 Main Dashboard & Telecalling CRM",
    "📞 Today's Telecalling Performance",
    "⚔️ Compare 2 Batches Studio",
    "📜 Outreach & Dispatch History",
    "📝 Outreach Templates Manager",
    "⚙️ Data Management & Uploads"
])

with tab_dash:
    import pandas as pd
    s_batches = pd.read_sql("SELECT DISTINCT Upload_Batch FROM sales_plan_history ORDER BY Upload_Batch DESC", conn)
    if not s_batches.empty:
        hist_df = fetch_all_history()
        render_dashboard(hist_df, "dash_master")
    else:
        st.info("👋 Welcome! Kripya '⚙️ Data Management & Uploads' tab mein jaakar apni Master Data Excel/CSV upload karein.")

with tab_tele:
    render_telecalling_analytics(conn)

with tab_comp:
    render_batch_comparison(conn)

with tab_hist:
    render_outreach_history(conn)

with tab_tpl:
    render_template_manager(conn)

with tab_upload:
    if not is_admin:
        st.warning("🔒 **Admin Access Required**: File upload, batch management, and database deletion require Admin Access. Please select **🔑 Admin Access** in the sidebar and enter the password (`credflow2026`) to unlock these features.")
    else:
        action = st.radio("Select Action", ["📤 Upload New Master Data", "📅 View & Delete Past Upload Batches"], horizontal=True, key="upload_action_radio")

        if action == "📤 Upload New Master Data":
            st.info("💡 Upload your RAW Sales Data (CSV ya Excel)")
            uploaded_file = st.file_uploader("📂 Upload Raw Sales Data", type=["csv", "xlsx"])

            if uploaded_file:
                file_id = getattr(uploaded_file, 'file_id', uploaded_file.name + str(uploaded_file.size))

                if st.session_state.get('last_processed_file_id') != file_id:
                    try:
                        import datetime
                        import pandas as pd
                        s_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

                        # Recover missing headers from the raw CSV dump
                        if 'Unnamed: 33' in s_df.columns: s_df.rename(columns={'Unnamed: 33': 'syncing_status'}, inplace=True)
                        if 'Unnamed: 34' in s_df.columns: s_df.rename(columns={'Unnamed: 34': 'customer_id'}, inplace=True)
                        if 'Unnamed: 35' in s_df.columns: s_df.rename(columns={'Unnamed: 35': 'Last Login'}, inplace=True)
                        if 'Unnamed: 36' in s_df.columns: s_df.rename(columns={'Unnamed: 36': 'Credits used'}, inplace=True)

                        # Remove remaining Unnamed columns
                        s_df = s_df.loc[:, ~s_df.columns.str.contains('^Unnamed')]
                        def _get_row_val(r_item, keywords, default=""):
                            for col in r_item.index:
                                col_str = str(col).lower().replace('_', ' ').strip()
                                for kw in keywords:
                                    if kw.lower() in col_str:
                                        val = r_item[col]
                                        if pd.notna(val) and str(val).strip().lower() not in ['nan', 'none', '']:
                                            return str(val).strip()
                            return default

                        st.success("File Uploaded! Processing Raw Data into Dashboard Format...")

                        formatted_rows = []
                        s_no = 1

                        for _, row in s_df.iterrows():
                            cx_name = _get_row_val(row, ['first name', 'customer_name', 'name', 'customer'])
                            raw_phone = _get_row_val(row, ['phone', 'mobile', 'contact', 'lsq phone'])
                            email = _get_row_val(row, ['email', 'mail'])
                            plan_name = _get_row_val(row, ['plan name', 'plan_name', 'plan'])
                            plan_feat_raw = _get_row_val(row, ['plan features', 'features', 'feature'])
                            gst_num = _get_row_val(row, ['gst', 'gstin'])
                            lsq_phone = _get_row_val(row, ['lsq phone', 'lsq_phone', 'lsq'])
                            plan_start = _get_row_val(row, ['app_data', 'app data', 'plan start date', 'plan stat date', 'start date', 'stat date', 'date', 'created at', 'created date', 'onboarding date'])
                            if plan_start:
                                try:
                                    p_dt = pd.to_datetime(plan_start, errors='coerce')
                                    if pd.notna(p_dt):
                                        plan_start = p_dt.strftime('%d/%m/%Y')
                                except:
                                    pass
                            plan_end = _get_row_val(row, ['plan end date', 'end date'])

                            # Skip row ONLY if name, phone, and plan_name are ALL missing
                            if not cx_name and not raw_phone and not plan_name:
                                continue

                            if not plan_name:
                                plan_name = "Standard Plan"

                            phone_clean_match = raw_phone.replace('.0', '').replace('+91', '').replace(' ', '').replace('-', '').strip()
                            phone_display = phone_clean_match

                            # Extract Features properly via unified resolver
                            features = resolve_features_for_plan(plan_name)
                            if not features and plan_feat_raw:
                                features = [f.strip() for f in plan_feat_raw.split(',') if f.strip()]
                            if not features:
                                features = [plan_name]

                            health_status = str(row.get('Usage check', "No Data (Not Uploaded)"))
                            login_7d = "No"
                            cp_7d = "No"
                            sync_7d = ""

                            # Dynamic column finding for Usage Data
                            col_credits = next((c for c in s_df.columns if 'credit' in c.lower() or 'cp usage' in c.lower()), None)
                            col_login = next((c for c in s_df.columns if 'login' in c.lower()), None)
                            col_sync = next((c for c in s_df.columns if 'sync' in c.lower()), None)
                            col_contacts = next((c for c in s_df.columns if 'contact' in c.lower() and 'fetch' in c.lower()), None)

                            c_val = 0
                            cp_7d = "None"
                            login_7d = "None"
                            sync_7d = "None"
                            contact_7d = "None"

                            # ── USAGE HEALTH EVALUATION LOGIC (POINTS SYSTEM) ──
                            if col_credits or col_login or col_sync or col_contacts:
                                cp_score = 0
                                # ── 1. CP Usage / Credits (Plan-Wise Dynamic) ──
                                if col_credits:
                                    c_used = str(row[col_credits]).replace(',', '').strip()
                                    try:
                                        c_val = float(c_used) if c_used and c_used.lower() != 'nan' else 0
                                    except:
                                        c_val = 0

                                    cp_7d, cp_score = eval_plan_credits_and_score(plan_name, c_val)

                                # ── 2. App Login ──
                                if col_login:
                                    l_login = str(row[col_login]).strip()
                                    if l_login and l_login.lower() not in ['nan', 'none', 'no', 'false', '0', '']:
                                        login_7d = "Yes"
                                    else:
                                        login_7d = "No"

                                # ── 3. Last Sync ──
                                if col_sync:
                                    s_status = str(row[col_sync]).strip().lower()
                                    if 'more' in s_status or s_status in ['no', 'false', '0']:
                                        sync_7d = "No"
                                    elif s_status and s_status != 'nan':
                                        sync_7d = "Yes"

                                # ── 4. Contact Details Fetched ──
                                contact_val = 0
                                if col_contacts:
                                    c_raw = str(row[col_contacts]).replace(',', '').strip()
                                    try:
                                        contact_val = float(c_raw) if c_raw and c_raw.lower() != 'nan' else 0
                                    except:
                                        contact_val = 0

                                if contact_val > 30:
                                    contact_7d = "More than 31"
                                elif contact_val >= 11:
                                    contact_7d = "11 to 30"
                                elif contact_val > 0:
                                    contact_7d = "0 to 10"
                                else:
                                    contact_7d = "None"

                                h_score = 0
                                if login_7d == "Yes": h_score += 2
                                if sync_7d == "Yes": h_score += 1
                                h_score += cp_score
                                if contact_val > 30: h_score += 2
                                elif contact_val >= 11: h_score += 1

                                raw_health = str(row.get('Usage check', '')).strip()
                                if c_val == 0 and login_7d != "Yes" and sync_7d != "Yes":
                                    if h_score == 0: health_status = "No Usage 🔴"
                                    elif h_score <= 3: health_status = "Low Usage 🟡"
                                    else: health_status = "Proper Usage 🟢"
                                elif raw_health and any(h in raw_health for h in ['Proper', 'Low', 'No']):
                                    health_status = raw_health
                                else:
                                    if h_score == 0: health_status = "No Usage 🔴"
                                    elif h_score <= 3: health_status = "Low Usage 🟡"
                                    else: health_status = "Proper Usage 🟢"

                            row['Credits used'] = c_val

                            for i, feat in enumerate(features):
                                formatted_rows.append({
                                    "S.No": s_no if i == 0 else "",
                                    "Name": cx_name,
                                    "phone": phone_display,
                                    "lsq phone": lsq_phone,
                                    "gst number": gst_num,
                                    "email": email,
                                    "plan name": plan_name,
                                    "feature": feat,
                                    "Plan Stat Date": plan_start,
                                    "Plan End Date": plan_end,
                                    "Usage check": health_status,
                                    "Last Sync in 7 days": sync_7d,
                                    "CP Usage in last 7 days": cp_7d,
                                    "Contact details fetched in last 7 days": contact_7d,
                                    "App login done in last 7 days": login_7d,
                                    "raw_credits": c_val
                                })
                            s_no += 1

                        out_df = pd.DataFrame(formatted_rows)

                        if not out_df.empty:
                            # Ensure output columns match sqlite schema
                            batch_name = uploaded_file.name + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                            out_df['Upload_Batch'] = batch_name

                            out_df = out_df.astype(str)
                            out_df.to_sql('sales_plan_history', conn, if_exists='append', index=False)
                        else:
                            st.error("❌ No valid customer records could be extracted from the uploaded file. Please verify file headers (Name, Phone, Plan Name).")
                            st.stop()

                        # ── AUTO-FILL: Map call_status / remarks / follow_up from uploaded file ──
                        # Detect column names flexibly (case-insensitive)
                        def _find_col(df, keywords):
                            for col in df.columns:
                                if any(k in col.lower() for k in keywords):
                                    return col
                            return None

                        col_cs  = _find_col(s_df, ['call_status', 'call status', 'callstatus', 'status'])
                        col_rem = _find_col(s_df, ['remark', 'note', 'comment'])
                        col_fup = _find_col(s_df, ['follow_up', 'follow up', 'followup', 'callback'])
                        col_ph  = _find_col(s_df, ['phone', 'mobile', 'contact'])

                        if col_ph and (col_cs or col_rem or col_fup):
                            auto_fill_count = 0
                            for _, row in s_df.iterrows():
                                phone_raw = str(row.get(col_ph, '')).replace('.0', '').replace('+91', '').replace(' ', '').replace('-', '').strip()
                                if not phone_raw or phone_raw.lower() in ['nan', 'none', '']: continue

                                cs_val  = str(row[col_cs]).strip()  if col_cs  and str(row[col_cs]).strip()  not in ['nan','None',''] else ''
                                rem_val = str(row[col_rem]).strip() if col_rem and str(row[col_rem]).strip() not in ['nan','None',''] else ''
                                fup_raw = str(row[col_fup]).strip() if col_fup and str(row[col_fup]).strip() not in ['nan','None',''] else ''
                                try:
                                    fup_val = str(pd.to_datetime(fup_raw, dayfirst=True).date()) if fup_raw else ''
                                except:
                                    fup_val = ''

                                if cs_val or rem_val or fup_val:
                                    conn.execute('''
                                        INSERT INTO customer_interactions (phone, status_update, remarks, follow_up)
                                        VALUES (?, ?, ?, ?)
                                        ON CONFLICT(phone) DO UPDATE SET
                                            status_update = CASE WHEN excluded.status_update != '' THEN excluded.status_update ELSE status_update END,
                                            remarks       = CASE WHEN excluded.remarks     != '' THEN excluded.remarks     ELSE remarks     END,
                                            follow_up     = CASE WHEN excluded.follow_up   != '' THEN excluded.follow_up   ELSE follow_up   END
                                    ''', (phone_raw, cs_val, rem_val, fup_val))
                                    auto_fill_count += 1
                            conn.commit()
                            if auto_fill_count:
                                st.info(f"✅ **Auto-Fill Complete!** {auto_fill_count} customers ke Status / Remarks / Follow-up Date automatically map ho gaye uploaded data se.")
                        # ── END AUTO-FILL ──

                        st.session_state['last_processed_file_id'] = file_id
                        st.session_state['current_upload_df'] = out_df
                        st.cache_data.clear()
                        st.success("Data Formatted and Saved to History!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error reading file: {e}")
                        import traceback
                        st.code(traceback.format_exc())

        else:
            import pandas as pd
            s_batches = pd.read_sql("SELECT DISTINCT Upload_Batch FROM sales_plan_history ORDER BY Upload_Batch DESC", conn)
            if not s_batches.empty:
                st.markdown("""
                <div style="background: #FFFBEB; border: 1px solid #FCD34D; border-left: 4px solid #F59E0B; padding: 14px 18px; border-radius: 10px; margin-bottom: 16px;">
                    <h4 style="margin:0; color:#92400E; font-size:16px;">📥 Master Backup Download Before Deleting Extra Sheets</h4>
                    <p style="margin:4px 0 0 0; color:#78350F; font-size:13px;">
                        Download full combined backup of all 727 unique customers across July & August data before deleting extra upload batches.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                full_master_df = fetch_all_history()
                filtered_master, eval_master = prepare_eval_df(full_master_df)
                dedup_master = eval_master.drop_duplicates(subset=['phone'], keep='last')
                excel_backup = to_excel_download(dedup_master, sheet_name="Master_Deduplicated")
                csv_backup = dedup_master.to_csv(index=False).encode('utf-8')

                d_c1, d_c2 = st.columns([1, 1])
                with d_c1:
                    st.download_button(
                        "📥 Download Master 727 Customers Backup (Excel)",
                        data=excel_backup,
                        file_name="CredFlow_Master_Dataset_Backup_727_Customers.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary"
                    )
                with d_c2:
                    st.download_button(
                        "📄 Download Master 727 Customers Backup (CSV)",
                        data=csv_backup,
                        file_name="CredFlow_Master_Dataset_Backup_727_Customers.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                st.markdown("---")

                extra_batches = [b for b in s_batches['Upload_Batch'].tolist() if not ('July_Adoption_Project' in b or '08092026' in b)]
                if extra_batches:
                    with st.expander(f"⚡ One-Click Cleanup: Delete {len(extra_batches)} Extra Intermediate Batches (Keep July & 08092026 Only)"):
                        st.write(f"The following intermediate batches will be safely removed, keeping **July_Adoption_Project** and **08092026.csv** intact:")
                        for eb in extra_batches:
                            st.caption(f"&bull; {eb}")
                        if st.button("🗑️ Delete All Intermediate Extra Batches Now", key="btn_cleanup_extra"):
                            for eb in extra_batches:
                                conn.execute("DELETE FROM sales_plan_history WHERE Upload_Batch = ?", (eb,))
                            conn.commit()
                            st.cache_data.clear()
                            st.success(f"Successfully deleted {len(extra_batches)} extra batches! Data is now clean and deduplicated.")
                            st.rerun()

                st.markdown("#### 📂 Manage Individual Upload Batches")
                col_sel, col_del = st.columns([8, 2])
                with col_sel:
                    selected_batch = st.selectbox("Select Past Upload Batch to View or Delete", s_batches['Upload_Batch'].tolist(), key="manage_batch_sel")
                with col_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Delete Selected Batch", use_container_width=True, key="del_single_batch"):
                        conn.execute("DELETE FROM sales_plan_history WHERE Upload_Batch = ?", (selected_batch,))
                        conn.commit()
                        st.cache_data.clear()
                        st.success("Batch deleted successfully!")
                        st.rerun()

                if selected_batch:
                    hist_df = pd.read_sql("SELECT * FROM sales_plan_history WHERE Upload_Batch = ?", conn, params=(selected_batch,))
                    st.markdown("#### 📂 Preview Selected Batch Data")
                    st.dataframe(hist_df, use_container_width=True)
            else:
                st.warning("No past uploads found.")
