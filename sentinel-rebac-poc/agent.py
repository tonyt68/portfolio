import redis, smtplib, json, os
from email.mime.text import MIMEText

# Connect to the "Brain"
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def get_claude_verdict(threat, remediation):
    print(f"\n🤖 [SENTINEL AI] Investigating {threat} event...")
    
    # Logic if the brain has been wiped
    if remediation == "GOVERNANCE_MISSING":
        return "🚨 ALERT: No governance rules found in Redis! System may be under lockdown or unauthorized modification."
    
    # Standard Reasoning
    if threat == "CryptoMining" and remediation == "QUARANTINE":
        return "CRITICAL: Behavioral analysis matches known miner signatures. Governance rule 'QUARANTINE' is VALIDATED."
    
    return "CAUTION: Pattern unclear. Suggesting MANUAL_REVIEW."

def handle_finding(finding_json):
    finding = json.loads(finding_json)
    threat = finding['detail']['type']
    
    # 1. Fetch static skill from the Redis Brain
    # If the key is gone, we explicitly flag it
    raw_remediation = r.get(threat)
    remediation = raw_remediation if raw_remediation else "GOVERNANCE_MISSING"
    
    # 2. Add the Agentic Reasoning layer
    ai_verdict = get_claude_verdict(threat, remediation)
    print(f"🧠 [AI VERDICT]: {ai_verdict}\n")
    
    # 3. Trigger Alert with the combined context
    status_icon = "🔴" if remediation == "GOVERNANCE_MISSING" else "🟢"
    full_action = f"{status_icon} Action: {remediation} | AI Logic: {ai_verdict}"
    send_audit_email(threat, full_action, remediation)
    
    return f"Execution State: {remediation}"

def send_audit_email(threat, action_details, state):
    msg = MIMEText(f"Governance Status Report\n\nThreat: {threat}\nDetails: {action_details}")
    
    # Dynamic Subject based on system health
    if state == "GOVERNANCE_MISSING":
        msg['Subject'] = '🔴 CRITICAL: Sentinel Governance Brain Wiped'
    else:
        msg['Subject'] = '🟢 Sentinel: Threat Validated & Logged'
        
    msg['From'] = 'sentinel@idp.local'
    msg['To'] = 'security-audit@idp.local'
    
    port = int(os.getenv('SENTINEL_SMTP_PORT', 1025))
    try:
        with smtplib.SMTP("127.0.0.1", port, timeout=5) as server:
            server.sendmail('sentinel@idp.local', ['security-audit@idp.local'], msg.as_string())
            print(f"✅ Audit Logged to MailHog (Port {port})")
    except Exception as e:
        print(f"❌ Mail Error: {e}")

# The Mock Trigger
print(handle_finding('{"detail": {"type": "CryptoMining"}}'))
