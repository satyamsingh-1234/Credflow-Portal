# -*- coding: utf-8 -*-
"""
Desktop App Version Tracker & WhatsApp Upgrade Outreach Module
Tracking desktop application versions across July, August, and September cohorts.
Identifies updated versions (Green) vs legacy versions (Red/Upgrade Required).
Provides 1-click WhatsApp upgrade outreach via Interakt API and Desktop Auto-Sender.
"""

import os
import re
import json
import sqlite3
import datetime
import urllib.parse
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credflow_history.db")
EXTRACTED_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customer_version_detail_extracted.csv")

UPGRADE_TEMPLATE_TEXT = """Dear {customer_name},

Your CredFlow Desktop App needs to be upgraded to the latest version. Please download and install the latest version using the below link:

For Windows 10+: https://drive.google.com/file/d/13tXCQW5u_cOiB28WJZT2sOAh2HfCGcjQ/view?usp=sharing

For Windows 7–10: https://drive.google.com/file/d/1Yr3Z6m62-y8mZ8QFTQfOLJaY80n4KwxD/view?usp=drive_link

Installation guide: https://credflow.freshdesk.com/support/solutions/articles/82000912032-credflow-desktop-application-installation

Regards,
CredFlow Support"""


def ensure_desktop_version_table(conn):
    """Ensure desktop_version_details table exists and is populated."""
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS desktop_version_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            customer_name TEXT,
            company TEXT,
            phone TEXT,
            email TEXT,
            admin_user_id TEXT,
            desktop_app_version TEXT,
            software_type TEXT,
            environment TEXT,
            match_status TEXT,
            is_latest_version INTEGER,
            count_in_month INTEGER,
            count_overall INTEGER,
            plan TEXT,
            alternate_phone TEXT,
            source TEXT
        )
        """)
        conn.commit()

        # Check if table has data
        row_count = cur.execute("SELECT COUNT(*) FROM desktop_version_details").fetchone()[0]
        if row_count == 0 and os.path.exists(EXTRACTED_CSV):
            df = pd.read_csv(EXTRACTED_CSV)
            records = []
            for _, row in df.iterrows():
                p = str(row['Phone']).replace('.0', '').strip()
                if len(p) > 10:
                    p = p[-10:]
                ver = str(row['Desktop app version']).strip() if pd.notna(row['Desktop app version']) else 'Unknown'
                env = str(row['Environment']).strip() if pd.notna(row['Environment']) else 'Unknown'
                
                sw = 'Tally' if 'tally' in ver.lower() else ('Busy' if 'busy' in ver.lower() else 'Unknown')
                is_latest = 1 if (ver == '2.0.1_tally' or (ver == '1.8.6_tally' and env == 'Cloud') or ver == '3.6.12_busy') else 0
                
                records.append((
                    str(row['Month']) if pd.notna(row['Month']) else '',
                    str(row['Customer name']) if pd.notna(row['Customer name']) else '',
                    str(row['Company']) if pd.notna(row['Company']) else '',
                    p,
                    str(row['Email']) if pd.notna(row['Email']) else '',
                    str(row['Admin / User ID']).replace('.0', '') if pd.notna(row['Admin / User ID']) else '',
                    ver,
                    sw,
                    env,
                    str(row['Match status']) if pd.notna(row['Match status']) else '',
                    is_latest,
                    1 if row.get('Count in month') == True else 0,
                    1 if row.get('Count overall') == True else 0,
                    str(row.get('Plan (July source)', '')) if pd.notna(row.get('Plan (July source)', '')) else '',
                    str(row.get('Alternate phone (July)', '')).replace('.0', '') if pd.notna(row.get('Alternate phone (July)', '')) else '',
                    str(row.get('Source', '')) if pd.notna(row.get('Source', '')) else ''
                ))

            cur.executemany("""
            INSERT INTO desktop_version_details (
                month, customer_name, company, phone, email, admin_user_id,
                desktop_app_version, software_type, environment, match_status,
                is_latest_version, count_in_month, count_overall, plan,
                alternate_phone, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()
    except Exception as e:
        st.error(f"Error ensuring desktop_version_details table: {e}")


def send_interakt_desktop_upgrade(phone, name, template_name="credflow_desktop_app_upgrade"):
    """Dispatches WhatsApp Upgrade message via Interakt API."""
    import requests
    
    clean_p = str(phone).replace('.0', '').replace('+91', '').strip()
    wa_phone = re.sub(r'\D', '', clean_p)
    if len(wa_phone) > 10:
        wa_phone = wa_phone[-10:]
        
    if len(wa_phone) != 10:
        return False, f"Invalid phone length ({phone})"
        
    c_code = "+91"
    p_num = wa_phone
    cust_name = str(name).title() if name and pd.notna(name) and str(name).strip() != '' else "Customer"
    
    payload = {
        "countryCode": c_code,
        "phoneNumber": p_num,
        "type": "Template",
        "template": {
            "name": template_name,
            "languageCode": "en",
            "bodyValues": [cust_name]
        }
    }
    
    headers = {
        "Authorization": "Basic RHFqbG9icEFxYkRBOGdLdVVXaUtjRDBiaGxITHJwOElGQUZzUkVKMEFEMDo=",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post("https://api.interakt.ai/v1/public/message/", headers=headers, json=payload, timeout=12)
        if resp.status_code in [200, 201, 202]:
            return True, resp.text
        else:
            err_txt = resp.text
            if "wallet" in err_txt.lower() or "recharge" in err_txt.lower() or "balance" in err_txt.lower():
                return False, "WALLET_INSUFFICIENT_BALANCE"
            return False, f"HTTP {resp.status_code}: {err_txt}"
    except Exception as e:
        return False, str(e)


def log_upgrade_outreach(conn, phone, customer_name, email, status, error_msg=""):
    """Logs the upgrade message outreach to outreach_logs table."""
    try:
        cur = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        INSERT INTO outreach_logs (
            timestamp, channel, health_tier, customer_name, phone, email, subject, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now,
            "WhatsApp (Interakt)",
            "Desktop Upgrade",
            customer_name,
            phone,
            email or "",
            "Desktop App Upgrade to Latest Version",
            status,
            error_msg
        ))
        conn.commit()
    except Exception as e:
        print(f"Error logging upgrade outreach: {e}")


def render_desktop_version_tracker(conn):
    """Renders the Desktop App Version Tracker tab."""
    ensure_desktop_version_table(conn)
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 20px 24px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 24px;">
        <h2 style="color: #38BDF8; margin: 0 0 6px 0; font-size: 24px; font-weight: 700;">🔄 Desktop App Version Tracker & Upgrade Studio</h2>
        <p style="color: #94A3B8; margin: 0; font-size: 14px;">
            Tracking desktop software versions for <b>July, August, and September</b> customer cohorts from the official master Google Sheet.
            Easily identify customers on outdated Tally/Busy versions and send 1-click WhatsApp upgrade links via Interakt API.
        </p>
        <div style="display: flex; gap: 12px; margin-top: 14px; flex-wrap: wrap;">
            <span style="background: #064E3B; color: #6EE7B7; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid #059669;">
                🟢 Latest Tally: 2.0.1_tally (Local) / 1.8.6_tally (Cloud)
            </span>
            <span style="background: #064E3B; color: #6EE7B7; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid #059669;">
                🟢 Latest Busy: 3.6.12_busy
            </span>
            <span style="background: #7F1D1D; color: #FCA5A5; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid #DC2626;">
                🔴 Outdated / Old Versions: Requires Upgrade Message
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Load master desktop version data
    raw_df = pd.read_sql("SELECT * FROM desktop_version_details", conn)
    if raw_df.empty:
        st.warning("⚠️ No desktop version details found in database.")
        return

    # Top Filter Bar
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        month_options = ["All Months (Overall)"] + sorted([m for m in raw_df['month'].dropna().unique() if m])
        sel_month = st.selectbox("📅 Cohort Month", month_options, index=0, key="dsk_sel_month")
    
    with f_col2:
        sw_options = ["All Software", "Tally", "Busy", "Unknown"]
        sel_sw = st.selectbox("💻 Software Type", sw_options, index=0, key="dsk_sel_sw")
        
    with f_col3:
        env_options = ["All Environments", "Local", "Cloud", "Unknown"]
        sel_env = st.selectbox("☁️ Environment", env_options, index=0, key="dsk_sel_env")
        
    with f_col4:
        status_options = ["All Customers", "🔴 Needs Upgrade Only", "🟢 Latest Version Only", "⚪ Unknown / Broken Sync"]
        sel_status = st.selectbox("🏷️ Version Status", status_options, index=0, key="dsk_sel_status")

    # Search Bar
    search_query = st.text_input("🔍 Search by Customer Name, Company, Phone, or Version:", placeholder="e.g. Mangilia, 9443344881, 2.0.1_tally, etc.", key="dsk_search_query")

    # Apply Filters
    filtered_df = raw_df.copy()
    if sel_month != "All Months (Overall)":
        filtered_df = filtered_df[filtered_df['month'] == sel_month]
        
    if sel_sw != "All Software":
        filtered_df = filtered_df[filtered_df['software_type'] == sel_sw]
        
    if sel_env != "All Environments":
        filtered_df = filtered_df[filtered_df['environment'] == sel_env]
        
    if sel_status == "🔴 Needs Upgrade Only":
        filtered_df = filtered_df[(filtered_df['is_latest_version'] == 0) & (filtered_df['desktop_app_version'] != 'Unknown / Not found')]
    elif sel_status == "🟢 Latest Version Only":
        filtered_df = filtered_df[filtered_df['is_latest_version'] == 1]
    elif sel_status == "⚪ Unknown / Broken Sync":
        filtered_df = filtered_df[filtered_df['desktop_app_version'] == 'Unknown / Not found']

    if search_query.strip():
        q = search_query.strip().lower()
        mask = (
            filtered_df['customer_name'].astype(str).str.lower().str.contains(q) |
            filtered_df['company'].astype(str).str.lower().str.contains(q) |
            filtered_df['phone'].astype(str).str.contains(q) |
            filtered_df['desktop_app_version'].astype(str).str.lower().str.contains(q)
        )
        filtered_df = filtered_df[mask]

    # Metrics Summary
    total_cx = len(filtered_df)
    latest_cx = len(filtered_df[filtered_df['is_latest_version'] == 1])
    needs_upgrade_cx = len(filtered_df[(filtered_df['is_latest_version'] == 0) & (filtered_df['desktop_app_version'] != 'Unknown / Not found')])
    unknown_cx = len(filtered_df[filtered_df['desktop_app_version'] == 'Unknown / Not found'])

    pct_latest = (latest_cx / total_cx * 100) if total_cx > 0 else 0
    pct_upgrade = (needs_upgrade_cx / total_cx * 100) if total_cx > 0 else 0
    pct_unknown = (unknown_cx / total_cx * 100) if total_cx > 0 else 0

    st.markdown("### 📊 Version Health Overview")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("👥 Total Customers", f"{total_cx:,}")
    with m2:
        st.metric("🟢 Updated / Latest Version", f"{latest_cx:,}", f"{pct_latest:.1f}% of cohort")
    with m3:
        st.metric("🔴 Needs Upgrade", f"{needs_upgrade_cx:,}", f"{pct_upgrade:.1f}% require update", delta_color="inverse")
    with m4:
        st.metric("⚪ Unknown / Broken Sync", f"{unknown_cx:,}", f"{pct_unknown:.1f}% of cohort", delta_color="off")

    st.markdown("---")

    # Tabbed view: 1) Version Synopsis Breakdown, 2) Customer Detail List, 3) 1-Click WhatsApp Outreach
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "📋 Version Synopsis Breakdown",
        "👥 Customer Version Registry",
        "📢 Send WhatsApp Upgrade Messages"
    ])

    with sub_tab1:
        st.markdown("#### 📊 Version Distribution & Environment Breakdown")
        st.caption("Aggregated summary matching Google Sheet Synopsis (Local vs Cloud vs Unknown)")
        
        # Aggregation
        piv = filtered_df.groupby(['desktop_app_version', 'software_type']).agg(
            Total=('phone', 'count'),
            Local=('environment', lambda x: (x == 'Local').sum()),
            Cloud=('environment', lambda x: (x == 'Cloud').sum()),
            Unknown=('environment', lambda x: (x == 'Unknown').sum()),
            Is_Latest=('is_latest_version', 'max')
        ).reset_index().sort_values(by='Total', ascending=False)
        
        piv['Status'] = piv['Is_Latest'].apply(lambda x: '🟢 Updated / Latest' if x == 1 else '🔴 Old / Upgrade Needed')
        piv.loc[piv['desktop_app_version'] == 'Unknown / Not found', 'Status'] = '⚪ Unknown / Not Synced'
        
        disp_piv = piv[['desktop_app_version', 'software_type', 'Status', 'Local', 'Cloud', 'Unknown', 'Total']]
        disp_piv.columns = ['Desktop App Version', 'Software', 'Status', 'Local Users', 'Cloud Users', 'Unknown Env', 'Total Customers']
        st.dataframe(disp_piv, use_container_width=True, hide_index=True)

    with sub_tab2:
        st.markdown(f"#### 👥 Customer Records ({total_cx:,} Found)")
        
        # Format table for display
        display_df = filtered_df[['month', 'customer_name', 'company', 'phone', 'desktop_app_version', 'software_type', 'environment', 'is_latest_version']].copy()
        display_df['Upgrade Status'] = display_df['is_latest_version'].apply(lambda x: '🟢 Latest' if x == 1 else '🔴 Needs Upgrade')
        display_df.loc[display_df['desktop_app_version'] == 'Unknown / Not found', 'Upgrade Status'] = '⚪ Unknown'
        
        # Add clickable WhatsApp link
        def make_wa_link(row):
            p = str(row['phone']).strip()
            cname = str(row['customer_name']).title() if pd.notna(row['customer_name']) else "Customer"
            msg = UPGRADE_TEMPLATE_TEXT.format(customer_name=cname)
            encoded = urllib.parse.quote(msg)
            return f"https://wa.me/91{p}?text={encoded}"
            
        display_df['Direct WhatsApp'] = display_df.apply(make_wa_link, axis=1)
        
        clean_disp = display_df[['month', 'customer_name', 'company', 'phone', 'software_type', 'desktop_app_version', 'environment', 'Upgrade Status', 'Direct WhatsApp']]
        clean_disp.columns = ['Month', 'Customer Name', 'Company', 'Phone', 'Software', 'App Version', 'Environment', 'Status', '1-Click WA Link']
        
        st.dataframe(
            clean_disp,
            use_container_width=True,
            hide_index=True,
            column_config={
                "1-Click WA Link": st.column_config.LinkColumn("📲 Send WhatsApp", display_text="Chat / Send")
            }
        )
        
        # Download Filtered CSV
        csv_exp = clean_disp.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Filtered Customer List (CSV)",
            data=csv_exp,
            file_name=f"credflow_desktop_versions_{sel_month.replace(' ', '_')}.csv",
            mime="text/csv"
        )

    with sub_tab3:
        st.markdown("### 📢 WhatsApp Upgrade Dispatch Studio")
        st.info("Directly send the official Desktop App Upgrade notification to customers on older versions using Interakt WhatsApp API.")
        
        # Target audience
        upgrade_targets = filtered_df[filtered_df['is_latest_version'] == 0].copy()
        
        w_col1, w_col2 = st.columns([6, 4])
        with w_col1:
            st.markdown("#### 📝 Message Template Preview")
            sample_name = "Rajesh Sharma"
            st.code(UPGRADE_TEMPLATE_TEXT.format(customer_name=sample_name), language="text")
            
            st.caption("ℹ️ Variable `{{Customer}}` will be dynamically populated with the customer's real name.")
            
            # Interakt Template Name Setting
            tpl_input = st.text_input("Interakt WhatsApp Template Key Name", value="credflow_desktop_app_upgrade", key="interakt_tpl_key_input", help="The approved template identifier in your Interakt dashboard.")

        with w_col2:
            st.markdown("#### 🎯 Target Audience")
            st.write(f"• **Customers Needing Upgrade in current filter:** `{len(upgrade_targets):,}`")
            st.write(f"• **Current Month Cohort:** `{sel_month}`")
            st.write(f"• **Software Type:** `{sel_sw}`")
            
            st.markdown("#### 🧪 Test Single Number")
            test_phone = st.text_input("Enter 10-digit mobile number for test:", placeholder="9876543210", key="dsk_test_phone")
            test_name = st.text_input("Test customer name:", value="Test User", key="dsk_test_name")
            
            if st.button("🚀 Send Test WhatsApp via Interakt", use_container_width=True, key="btn_send_test_upgrade"):
                if not test_phone or len(test_phone.strip()) < 10:
                    st.error("Please enter a valid 10-digit phone number.")
                else:
                    with st.spinner("Dispatching via Interakt API..."):
                        success, res = send_interakt_desktop_upgrade(test_phone, test_name, tpl_input)
                        if success:
                            st.success(f"✅ Test WhatsApp sent successfully to {test_phone}!")
                            log_upgrade_outreach(conn, test_phone, test_name, "", "Success", "Test Dispatch")
                        else:
                            st.error(f"❌ Failed to send: {res}")
                            log_upgrade_outreach(conn, test_phone, test_name, "", "Failed", res)

        st.markdown("---")
        st.markdown("#### ⚡ Bulk Outreach Action")
        
        if len(upgrade_targets) == 0:
            st.success("🎉 All customers in this filter are already on the latest version! No upgrade messages required.")
        else:
            st.warning(f"⚠️ You have **{len(upgrade_targets):,}** customers needing an upgrade in the selected filter.")
            
            confirm_box = st.checkbox(f"I confirm that I want to send WhatsApp upgrade notifications to {len(upgrade_targets):,} customers", key="confirm_bulk_upgrade")
            
            b_c1, b_c2 = st.columns([1, 1])
            with b_c1:
                if st.button("🚀 Send Upgrade WhatsApp to Filtered Customers", type="primary", disabled=not confirm_box, use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success_count = 0
                    fail_count = 0
                    total = len(upgrade_targets)
                    
                    for idx, (_, r) in enumerate(upgrade_targets.iterrows()):
                        p = str(r['phone']).strip()
                        cname = str(r['customer_name']).strip()
                        email = str(r['email']).strip()
                        
                        ok, resp = send_interakt_desktop_upgrade(p, cname, tpl_input)
                        if ok:
                            success_count += 1
                            log_upgrade_outreach(conn, p, cname, email, "Success")
                        else:
                            fail_count += 1
                            log_upgrade_outreach(conn, p, cname, email, "Failed", str(resp))
                            
                        progress_bar.progress((idx + 1) / total)
                        status_text.text(f"Processed {idx + 1}/{total} | ✅ Success: {success_count} | ❌ Failed: {fail_count}")
                        
                    st.success(f"🎉 Dispatch completed! Total Sent: {success_count}, Failed: {fail_count}")
                    st.rerun()

            with b_c2:
                # Option for 100% Free Desktop Auto-Sender
                queue_items = []
                for _, r in upgrade_targets.iterrows():
                    p = str(r['phone']).strip()
                    cname = str(r['customer_name']).title() if pd.notna(r['customer_name']) else "Customer"
                    queue_items.append({
                        "phone": p,
                        "name": cname,
                        "message": UPGRADE_TEMPLATE_TEXT.format(customer_name=cname)
                    })
                json_queue = json.dumps(queue_items, indent=2).encode('utf-8')
                st.download_button(
                    "📥 Download Desktop Auto-Sender Queue (JSON)",
                    data=json_queue,
                    file_name="wa_desktop_upgrade_queue.json",
                    mime="application/json",
                    help="Use with whatsapp_desktop_sender.py for 100% free automated sending from your WhatsApp Web!",
                    use_container_width=True
                )
