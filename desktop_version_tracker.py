# -*- coding: utf-8 -*-
"""
Desktop App Version Tracker & WhatsApp Upgrade Outreach Module
With Customer Usage Health Integration (Proper / Low / No Usage),
Ultra-fast caching, and crash-proof execution.
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


@st.cache_data(show_spinner=False)
def load_cached_desktop_data_with_usage():
    """Loads desktop version data and joins customer usage health (Proper/Low/No Usage)."""
    if not os.path.exists(EXTRACTED_CSV):
        return pd.DataFrame()
        
    df = pd.read_csv(EXTRACTED_CSV)
    
    # Clean phone numbers (standard 10 digits)
    df['phone_clean'] = df['Phone'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df['phone_clean'] = df['phone_clean'].apply(lambda x: x[-10:] if len(x) > 10 else x)
    
    # Software type
    def get_sw(ver):
        v = str(ver).lower()
        if 'tally' in v: return 'Tally'
        if 'busy' in v: return 'Busy'
        return 'Unknown'
        
    df['software_type'] = df['Desktop app version'].apply(get_sw)
    
    # Latest vs old flag
    def get_is_latest(row):
        v = str(row['Desktop app version']).strip()
        e = str(row['Environment']).strip()
        if v == '2.0.1_tally': return 1
        if v == '1.8.6_tally' and e == 'Cloud': return 1
        if v == '3.6.12_busy': return 1
        return 0
        
    df['is_latest_version'] = df.apply(get_is_latest, axis=1)
    df['customer_name_clean'] = df['Customer name'].fillna('').astype(str).str.strip()
    df['company_clean'] = df['Company'].fillna('').astype(str).str.strip()
    df['email_clean'] = df['Email'].fillna('').astype(str).str.strip()
    df['version_clean'] = df['Desktop app version'].fillna('Unknown / Not found').astype(str).str.strip()
    df['env_clean'] = df['Environment'].fillna('Unknown').astype(str).str.strip()
    df['month_clean'] = df['Month'].fillna('').astype(str).str.strip()
    
    # Fetch Usage Check mapping from database if available
    usage_map = {}
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            u_df = pd.read_sql('SELECT phone, [Usage check] as usage_val FROM sales_plan_history', conn)
            conn.close()
            for _, r in u_df.iterrows():
                p = str(r['phone']).replace('.0', '').strip()
                if len(p) > 10: p = p[-10:]
                if p and p not in usage_map and pd.notna(r['usage_val']):
                    usage_map[p] = str(r['usage_val']).strip()
        except Exception:
            pass
            
    def map_health(row):
        p = row['phone_clean']
        h = usage_map.get(p, '')
        if not h or h == 'nan':
            # Fallback check
            ver = row['version_clean']
            if 'Unknown' in ver:
                return '⚪ Not Started / Sync Pending'
            return '⚪ Not Tracked in Master'
        if 'Very Good' in h:
            return '🌟 Very Good Usage'
        elif 'Proper' in h:
            return '🟢 Proper Usage'
        elif 'Low' in h:
            return '🟡 Low Usage'
        elif 'No Usage' in h:
            return '🔴 No Usage'
        elif 'Not Started' in h or 'Blank' in h:
            return '⚪ Not Started / Blank Setup'
        elif 'Partner' in h:
            return '🤝 Channel Partner'
        return h

    df['usage_health'] = df.apply(map_health, axis=1)
    return df


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


def log_upgrade_outreach(conn, phone, customer_name, email, status, error_msg=""):
    """Logs the upgrade message outreach to outreach_logs table."""
    try:
        cur = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS outreach_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, channel TEXT, health_tier TEXT,
            customer_name TEXT, phone TEXT, email TEXT,
            subject TEXT, status TEXT, error_message TEXT
        )
        """)
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
        pass


def render_desktop_version_tracker(conn):
    """Renders the Desktop App Version Tracker tab with Usage Health integration."""
    try:
        raw_df = load_cached_desktop_data_with_usage()
        if raw_df.empty:
            st.warning("⚠️ Desktop version data file not found.")
            return

        st.markdown("""
        <div style="background: #FFFFFF; padding: 20px 24px; border-radius: 12px; border: 1.5px solid #E2E8F0; border-left: 6px solid #0284C7; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="background: #E0F2FE; border: 1px solid #BAE6FD; padding: 6px 10px; border-radius: 8px; font-size: 20px;">🔄</span>
                <span style="font-size: 22px; font-weight: 800; color: #0F172A;">Desktop App Version Tracker &amp; Upgrade Studio</span>
            </div>
            <p style="margin: 0 0 14px 0; font-size: 14px; color: #334155; line-height: 1.5;">
                Tracking desktop software versions with <b style="color: #0369A1;">Live Customer Usage Health (Proper 🟢 / Low 🟡 / No Usage 🔴)</b> across July, August, and September cohorts.
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <span style="background: #ECFDF5; color: #065F46; padding: 6px 12px; border-radius: 6px; font-size: 12.5px; font-weight: 700; border: 1px solid #A7F3D0; display: inline-flex; align-items: center; gap: 4px;">
                    🟢 Latest Tally: 2.0.1_tally (Local) / 1.8.6_tally (Cloud)
                </span>
                <span style="background: #ECFDF5; color: #065F46; padding: 6px 12px; border-radius: 6px; font-size: 12.5px; font-weight: 700; border: 1px solid #A7F3D0; display: inline-flex; align-items: center; gap: 4px;">
                    🟢 Latest Busy: 3.6.12_busy
                </span>
                <span style="background: #FEF2F2; color: #991B1B; padding: 6px 12px; border-radius: 6px; font-size: 12.5px; font-weight: 700; border: 1px solid #FECACA; display: inline-flex; align-items: center; gap: 4px;">
                    🔴 Outdated Versions: Requires Upgrade Message
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Top Filter Bar (5 Columns)
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
        with f_col1:
            month_options = ["All Months (Overall)"] + sorted([m for m in raw_df['month_clean'].unique() if m])
            sel_month = st.selectbox("📅 Cohort Month", month_options, index=0, key="dsk_sel_month")
        
        with f_col2:
            sw_options = ["All Software", "Tally", "Busy", "Unknown"]
            sel_sw = st.selectbox("💻 Software Type", sw_options, index=0, key="dsk_sel_sw")
            
        with f_col3:
            env_options = ["All Environments", "Local", "Cloud", "Unknown"]
            sel_env = st.selectbox("☁️ Environment", env_options, index=0, key="dsk_sel_env")
            
        with f_col4:
            status_options = ["All Versions", "🔴 Needs Upgrade Only", "🟢 Latest Version Only", "⚪ Unknown / Broken Sync"]
            sel_status = st.selectbox("🏷️ Version Status", status_options, index=0, key="dsk_sel_status")

        with f_col5:
            health_options = [
                "All Usage Types",
                "🟢 Proper Usage",
                "🌟 Very Good Usage",
                "🟡 Low Usage",
                "🔴 No Usage",
                "⚪ Not Started / Sync Pending"
            ]
            sel_health = st.selectbox("🚦 Usage Health", health_options, index=0, key="dsk_sel_health")

        # Search Bar
        search_query = st.text_input("🔍 Search by Customer Name, Company, Phone, or Version:", placeholder="e.g. Mangilia, 9443344881, 2.0.1_tally, etc.", key="dsk_search_query")

        # Apply Filters
        filtered_df = raw_df.copy()
        if sel_month != "All Months (Overall)":
            filtered_df = filtered_df[filtered_df['month_clean'] == sel_month]
            
        if sel_sw != "All Software":
            filtered_df = filtered_df[filtered_df['software_type'] == sel_sw]
            
        if sel_env != "All Environments":
            filtered_df = filtered_df[filtered_df['env_clean'] == sel_env]
            
        if sel_status == "🔴 Needs Upgrade Only":
            filtered_df = filtered_df[(filtered_df['is_latest_version'] == 0) & (filtered_df['version_clean'] != 'Unknown / Not found')]
        elif sel_status == "🟢 Latest Version Only":
            filtered_df = filtered_df[filtered_df['is_latest_version'] == 1]
        elif sel_status == "⚪ Unknown / Broken Sync":
            filtered_df = filtered_df[filtered_df['version_clean'] == 'Unknown / Not found']

        if sel_health != "All Usage Types":
            filtered_df = filtered_df[filtered_df['usage_health'].str.contains(sel_health.split()[1], na=False)]

        if search_query.strip():
            q = search_query.strip().lower()
            mask = (
                filtered_df['customer_name_clean'].str.lower().str.contains(q) |
                filtered_df['company_clean'].str.lower().str.contains(q) |
                filtered_df['phone_clean'].str.contains(q) |
                filtered_df['version_clean'].str.lower().str.contains(q)
            )
            filtered_df = filtered_df[mask]

        # Metrics Summary
        total_cx = len(filtered_df)
        latest_cx = len(filtered_df[filtered_df['is_latest_version'] == 1])
        needs_upgrade_cx = len(filtered_df[(filtered_df['is_latest_version'] == 0) & (filtered_df['version_clean'] != 'Unknown / Not found')])
        
        # Usage breakdown
        proper_cnt = len(filtered_df[filtered_df['usage_health'].str.contains('Proper|Very Good', na=False)])
        low_cnt = len(filtered_df[filtered_df['usage_health'].str.contains('Low', na=False)])
        no_cnt = len(filtered_df[filtered_df['usage_health'].str.contains('No Usage', na=False)])

        st.markdown("### 📊 Version & Usage Health Overview")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("👥 Total Customers", f"{total_cx:,}")
        with m2:
            st.metric("🟢 Latest Versions", f"{latest_cx:,}", f"{(latest_cx/total_cx*100 if total_cx else 0):.1f}%")
        with m3:
            st.metric("🔴 Needs Upgrade", f"{needs_upgrade_cx:,}", f"{(needs_upgrade_cx/total_cx*100 if total_cx else 0):.1f}%", delta_color="inverse")
        with m4:
            st.metric("🟢 Proper Usage CX", f"{proper_cnt:,}")
        with m5:
            st.metric("🟡 Low / 🔴 No Usage", f"{low_cnt + no_cnt:,}", f"{low_cnt} Low | {no_cnt} No")

        st.markdown("---")

        # Tabbed view: 1) Version Synopsis Breakdown, 2) Customer Detail List, 3) 1-Click WhatsApp Outreach
        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "📋 Version Synopsis Breakdown",
            "👥 Customer Version Registry",
            "📢 Send WhatsApp Upgrade Messages"
        ])

        with sub_tab1:
            st.markdown("#### 📊 Version Distribution & Usage Health Breakdown")
            st.caption("Aggregated summary showing Environment (Local vs Cloud) and Customer Usage Health (Proper vs Low vs No Usage)")
            
            piv = filtered_df.groupby(['version_clean', 'software_type']).agg(
                Total=('phone_clean', 'count'),
                Local=('env_clean', lambda x: (x == 'Local').sum()),
                Cloud=('env_clean', lambda x: (x == 'Cloud').sum()),
                Proper_Usage=('usage_health', lambda x: x.str.contains('Proper|Very Good', na=False).sum()),
                Low_Usage=('usage_health', lambda x: x.str.contains('Low', na=False).sum()),
                No_Usage=('usage_health', lambda x: x.str.contains('No Usage', na=False).sum()),
                Is_Latest=('is_latest_version', 'max')
            ).reset_index().sort_values(by='Total', ascending=False)
            
            piv['Status'] = piv['Is_Latest'].apply(lambda x: '🟢 Latest' if x == 1 else '🔴 Needs Upgrade')
            piv.loc[piv['version_clean'] == 'Unknown / Not found', 'Status'] = '⚪ Not Synced'
            
            disp_piv = piv[['version_clean', 'software_type', 'Status', 'Local', 'Cloud', 'Proper_Usage', 'Low_Usage', 'No_Usage', 'Total']]
            disp_piv.columns = ['Desktop Version', 'Software', 'Version Status', 'Local', 'Cloud', 'Proper 🟢', 'Low 🟡', 'No Usage 🔴', 'Total Customers']
            st.dataframe(disp_piv, use_container_width=True, hide_index=True)

        with sub_tab2:
            st.markdown(f"#### 👥 Customer Records ({total_cx:,} Found)")
            
            display_df = filtered_df[['month_clean', 'customer_name_clean', 'company_clean', 'phone_clean', 'version_clean', 'software_type', 'env_clean', 'usage_health', 'is_latest_version']].copy()
            display_df['Version Status'] = display_df['is_latest_version'].apply(lambda x: '🟢 Latest' if x == 1 else '🔴 Needs Upgrade')
            display_df.loc[display_df['version_clean'] == 'Unknown / Not found', 'Version Status'] = '⚪ Unknown'
            
            # Direct WhatsApp link
            display_df['Direct WhatsApp'] = display_df['phone_clean'].apply(lambda p: f"https://wa.me/91{p}" if p and p != 'nan' else "")
            
            clean_disp = display_df[['month_clean', 'customer_name_clean', 'company_clean', 'phone_clean', 'software_type', 'version_clean', 'env_clean', 'usage_health', 'Version Status', 'Direct WhatsApp']]
            clean_disp.columns = ['Month', 'Customer Name', 'Company', 'Phone', 'Software', 'Desktop Version', 'Environment', 'Usage Health 🚦', 'Status', '1-Click WA']
            
            st.dataframe(
                clean_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "1-Click WA": st.column_config.LinkColumn("📲 WhatsApp", display_text="Chat")
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
            
            upgrade_targets = filtered_df[filtered_df['is_latest_version'] == 0].copy()
            
            w_col1, w_col2 = st.columns([6, 4])
            with w_col1:
                st.markdown("#### 📝 Message Template Preview")
                sample_name = "Rajesh Sharma"
                st.code(UPGRADE_TEMPLATE_TEXT.format(customer_name=sample_name), language="text")
                
                st.caption("ℹ️ Variable `{{Customer}}` will be dynamically populated with the customer's real name.")
                
                tpl_input = st.text_input("Interakt WhatsApp Template Key Name", value="credflow_desktop_app_upgrade", key="interakt_tpl_key_input", help="The approved template identifier in your Interakt dashboard.")

            with w_col2:
                st.markdown("#### 🎯 Target Audience")
                st.write(f"• **Customers Needing Upgrade in current filter:** `{len(upgrade_targets):,}`")
                st.write(f"• **Current Month Cohort:** `{sel_month}`")
                st.write(f"• **Software Type:** `{sel_sw}`")
                st.write(f"• **Usage Health Filter:** `{sel_health}`")
                
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
                            p = str(r['phone_clean']).strip()
                            cname = str(r['customer_name_clean']).strip()
                            email = str(r['email_clean']).strip()
                            
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
                    queue_items = []
                    for _, r in upgrade_targets.iterrows():
                        p = str(r['phone_clean']).strip()
                        cname = str(r['customer_name_clean']).title() if r['customer_name_clean'] else "Customer"
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
    except Exception as e:
        st.error(f"Error loading Desktop Version Tracker: {e}")
