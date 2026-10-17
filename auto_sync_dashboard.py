import os
import sys
import glob
import re
import datetime
import sqlite3
import subprocess
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

import credflow_portal as cp

def find_latest_download_file():
    downloads_dir = os.path.expanduser('~/Downloads')
    candidates = []
    for ext in ['*.csv', '*.xlsx', '*.xls']:
        candidates.extend(glob.glob(os.path.join(downloads_dir, ext)))
    if not candidates:
        return None
    # Sort by modification time, newest first
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]

def main():
    print("=" * 65)
    print("      🚀 CREDFLOW AUTOMATIC DASHBOARD UPDATER")
    print("=" * 65)

    input_file = None
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        input_file = sys.argv[1]
        print(f"📂 File Provided: {os.path.basename(input_file)}")
    else:
        latest = find_latest_download_file()
        if latest:
            print(f"🔍 Auto-detected Latest File from Downloads: {os.path.basename(latest)}")
            input_file = latest
        else:
            print("❌ No input file found in Downloads or drag-and-drop.")
            input("Press Enter to exit...")
            return

    # Load file
    print("⏳ Reading data file...")
    try:
        if input_file.lower().endswith(('.xlsx', '.xls')):
            df_raw = pd.read_excel(input_file)
        else:
            for enc in ['utf-8', 'latin1', 'cp1252', 'utf-8-sig']:
                try:
                    df_raw = pd.read_csv(input_file, encoding=enc)
                    break
                except Exception:
                    pass
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        input("Press Enter to exit...")
        return

    print(f"✅ Loaded {len(df_raw)} rows.")

    # Find columns
    sync_cols = [c for c in df_raw.columns if 'sync' in str(c).lower()]
    cp_cols = [c for c in df_raw.columns if 'cp' in str(c).lower() or 'point' in str(c).lower()]
    phone_cols = [c for c in df_raw.columns if 'phone' in str(c).lower() or 'mobile' in str(c).lower()]
    month_cols = [c for c in df_raw.columns if 'month' in str(c).lower()]
    name_cols = [c for c in df_raw.columns if 'name' in str(c).lower() or 'customer' in str(c).lower()]
    plan_cols = [c for c in df_raw.columns if 'plan' in str(c).lower()]
    email_cols = [c for c in df_raw.columns if 'email' in str(c).lower() or 'mail' in str(c).lower()]
    ver_cols = [c for c in df_raw.columns if 'version' in str(c).lower()]

    sync_col = sync_cols[0] if sync_cols else None
    cp_col = cp_cols[0] if cp_cols else None
    phone_col = phone_cols[0] if phone_cols else None
    month_col = month_cols[0] if month_cols else None
    name_col = name_cols[0] if name_cols else None
    plan_col = plan_cols[0] if plan_cols else None
    email_col = email_cols[0] if email_cols else None
    ver_col = ver_cols[0] if ver_cols else None

    if not phone_col or not sync_col:
        print("❌ Could not identify Phone Number or Sync status column.")
        input("Press Enter to exit...")
        return

    df_raw['clean_pts'] = pd.to_numeric(df_raw[cp_col].astype(str).str.replace(',', '').str.extract(r'(\d+)')[0], errors='coerce').fillna(0) if cp_col else 0
    df_raw['phone_clean'] = df_raw[phone_col].astype(str).str.replace(r'\.0$', '', regex=True).str.replace('+91', '').str.strip()

    # Process by cohort / month
    months = df_raw[month_col].dropna().unique() if month_col else ['Current Cohort']
    processed_dfs = []

    for m in months:
        sub = df_raw[df_raw[month_col] == m].copy() if month_col else df_raw.copy()
        m_lower = str(m).lower()

        # Batch naming
        if 'jul' in m_lower:
            batch_name = "july2609.csv"
            row_date = "15/07/2026"
        elif 'aug' in m_lower:
            batch_name = "aug2609.csv"
            row_date = "15/08/2026"
        elif 'sep' in m_lower:
            batch_name = "September.csv"
            row_date = "15/09/2026"
        else:
            batch_name = f"{m}.csv"
            row_date = datetime.datetime.now().strftime('%d/%m/%Y')

        # Exclude known Channel Partners
        sub['is_cp'] = sub['phone_clean'].isin(cp.CHANNEL_PARTNER_PHONES)
        cps = sub[sub['is_cp']].copy()
        cps['Usage check'] = 'Channel Partner 🤝'

        custs = sub[~sub['is_cp']].copy()
        custs_dedup = custs.drop_duplicates(subset=['phone_clean']).copy()

        # Deduplicate with unique suffix if needed
        is_within = custs_dedup[sync_col].astype(str).str.contains('within', case=False, na=False)
        custs_dedup['is_within'] = is_within

        # Classify health
        def classify_row(r):
            ph = str(r['phone_clean'])
            if ph in cp.CHANNEL_PARTNER_PHONES:
                return 'Channel Partner 🤝'
            within = r['is_within']
            pts = float(r['clean_pts'])
            if within:
                if pts > 200:
                    return 'Very Good Usage 🌟'
                else:
                    return 'Proper Usage 🟢'
            else:
                if pts > 200:
                    return 'Low Usage 🟡'
                else:
                    return 'No Usage 🔴'

        custs_dedup['Usage check'] = custs_dedup.apply(classify_row, axis=1)
        combined_cohort = pd.concat([custs_dedup, cps]).reset_index(drop=True)
        combined_cohort['Upload_Batch'] = batch_name
        combined_cohort['Upload_Date'] = row_date
        processed_dfs.append(combined_cohort)

    master_combined = pd.concat(processed_dfs).reset_index(drop=True)

    # Explode features for standard schema
    rows = []
    s_no = 1
    for idx, r in master_combined.iterrows():
        cx_name = str(r.get(name_col, '')).strip() if name_col else ''
        phone = str(r.get('phone_clean', '')).strip()
        plan_name = str(r.get(plan_col, 'Standard Plan')).strip() if plan_col else 'Standard Plan'
        email = str(r.get(email_col, '')).strip() if email_col else ''
        sync_raw = str(r.get(sync_col, 'Within 7 days Sync')).strip()
        c_val = float(r.get('clean_pts', 0))
        health = r.get('Usage check', 'Low Usage 🟡')
        batch_name = r.get('Upload_Batch', 'September.csv')
        r_date = r.get('Upload_Date', datetime.datetime.now().strftime('%d/%m/%Y'))

        features = cp.resolve_features_for_plan(plan_name)
        if not features:
            features = [plan_name]

        for feat in features:
            rows.append({
                'S.No': s_no,
                'Name': cx_name,
                'phone': phone,
                'lsq phone': np.nan,
                'gst number': np.nan,
                'email': email,
                'plan name': plan_name,
                'feature': feat,
                'Plan Stat Date': r_date,
                'Plan End Date': np.nan,
                'Usage check': health,
                'Last Sync in 7 days': sync_raw,
                'CP Usage in last 7 days': f"{int(c_val)} Credits" if c_val > 0 else "0 Credits",
                'Contact details fetched in last 7 days': np.nan,
                'App login done in last 7 days': "No",
                'raw_credits': c_val,
                'Upload_Batch': batch_name,
                'Upload_Date': r_date
            })
            s_no += 1

    master_df = pd.DataFrame(rows)

    # Save clean GZ file
    csv_out = os.path.join(SCRIPT_DIR, 'clean_master_data.csv.gz')
    master_df.to_csv(csv_out, compression='gzip', index=False)

    # Save to SQLite
    db_path = os.path.join(SCRIPT_DIR, 'credflow_history.db')
    conn = sqlite3.connect(db_path)
    master_df.to_sql('sales_plan_history', conn, if_exists='replace', index=False)

    now_str = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')
    new_ver = f"v{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('scoring_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (new_ver,))
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('last_uploaded_file', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (os.path.basename(input_file),))
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('last_upload_time', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (f"{now_str} (Live & Synced)",))
    conn.commit()
    conn.close()

    # Update version in credflow_portal.py
    portal_file = os.path.join(SCRIPT_DIR, 'credflow_portal.py')
    with open(portal_file, 'r', encoding='utf-8') as f:
        p_content = f.read()

    p_content = re.sub(r"TARGET_SCORING_VER\s*=\s*['\"][^'\"]+['\"]", f"TARGET_SCORING_VER = '{new_ver}'", p_content)
    with open(portal_file, 'w', encoding='utf-8') as f:
        f.write(p_content)

    print("\n" + "=" * 65)
    print("           📊 UPDATED METRICS SUMMARY")
    print("=" * 65)
    tr_all = master_combined[~master_combined['Usage check'].str.contains('Channel Partner')]
    print(f"👥 Total Trackable Customers: {len(tr_all)}")
    for k, v in tr_all['Usage check'].value_counts().items():
        pct = round(v / len(tr_all) * 100)
        print(f"  {k}: {v} ({pct}%)")

    # Git commit and push
    print("\n⏳ Pushing updates to Live Dashboard (GitHub)...")
    try:
        subprocess.run(['git', 'add', 'clean_master_data.csv.gz', 'credflow_history.db', 'credflow_portal.py'], check=True)
        subprocess.run(['git', 'commit', '-m', f"Auto-sync dashboard with {os.path.basename(input_file)} ({now_str})"], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        print("\n🎉 SUCCESS: Live Dashboard Updated & Synced to Cloud!")
    except Exception as e:
        print(f"\n⚠️ Git push notice: {e}")

    print("\n" + "=" * 65)
    input("Sab kuch complete ho gaya! Window band karne ke liye Enter dabayein...")

if __name__ == '__main__':
    main()
