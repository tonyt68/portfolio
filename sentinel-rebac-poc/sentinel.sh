#!/bin/bash
REDIS_PORT=6379

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

show_menu() {
    clear
    echo "=================================================="
    echo "     🛡️  SENTINEL AI: ReBAC GOVERNANCE POC"
    echo "=================================================="
    echo "  ALLOWED FLOW:  1 → 2"
    echo "  DENIED FLOW:   1 → 3 → 2 → 4 → 2"
    echo ""
    echo "  Auth Chain:"
    echo "  sentinel-agent → tony → platform-team → CryptoMining"
    echo "=================================================="
    echo "  1) 🚀 START & SEED     (Infra + ReBAC Graph)"
    echo "  2) 🤖 RUN SENTINEL     (AI checks auth chain)"
    echo "  3) 🔒 REVOKE ACCESS    (Break Tony's membership)"
    echo "  4) 🔓 RESTORE ACCESS   (Restore Tony's membership)"
    echo "  5) 🔍 VERIFY GRAPH     (Show relationships)"
    echo "  6) 📊 STATUS CHECK     (Pods & Links)"
    echo "  7) 🛑 STOP & RESET     (Cleanup & Sleep)"
    echo "  8) 🚪 EXIT"
    echo "=================================================="
    printf "Choose an option: "
}

start_and_seed() {
    echo "🚀 Starting Minikube..."
    minikube status | grep -q "Running" || minikube start --driver=docker --memory=4096 --cpus=4
    kubectl apply -f infra.yaml
    echo "⏳ Waiting for pods..."
    kubectl wait --for=condition=Ready pods --all --timeout=60s
    pkill -f "port-forward"
    kubectl port-forward svc/redis-service 6379:6379 > /dev/null 2>&1 &
    kubectl port-forward svc/mail-service 1025:1025 8025:8025 > /dev/null 2>&1 &
    echo -n "🌀 Stabilizing Tunnels..."
    sleep 12 &
    spinner $!

    echo "📦 Installing Python dependencies..."
    source venv/bin/activate
    pip install "anthropic[mcp]" -q
    deactivate

    echo ""
    echo "🔐 Seeding ReBAC Relationship Graph..."
    echo "   sentinel-agent --delegate_of--> tony"
    kubectl exec -it deployment/redis -- redis-cli sadd rebac:sentinel-agent:delegate_of tony > /dev/null
    echo "   tony           --member_of-->   platform-team"
    kubectl exec -it deployment/redis -- redis-cli sadd rebac:tony:member_of platform-team > /dev/null
    echo "   platform-team  --can_remediate--> CryptoMining"
    kubectl exec -it deployment/redis -- redis-cli sadd rebac:platform-team:can_remediate CryptoMining > /dev/null
    kubectl exec -it deployment/redis -- redis-cli sadd rebac:platform-team:can_remediate Ransomware > /dev/null
    echo ""
    echo "✅ ReBAC Graph Loaded. Authorization chain is INTACT."
    read -p "Press enter..."
}

run_sentinel() {
    echo "🤖 Running Sentinel AI..."
    if [ -d "venv" ]; then
        source venv/bin/activate
        SENTINEL_SMTP_PORT=1025 python3 client.py
        deactivate
    else
        SENTINEL_SMTP_PORT=1025 python3 client.py
    fi
    [ "$1" != "auto" ] && read -p "Press enter..."
}

revoke_access() {
    echo "🔒 Revoking Tony's platform-team membership..."
    kubectl exec -it deployment/redis -- redis-cli srem rebac:tony:member_of platform-team > /dev/null
    echo ""
    echo "⚠️  Tony's membership REVOKED."
    echo "   Authorization chain BROKEN:"
    echo "   sentinel-agent → tony → ??? → CryptoMining"
    echo ""
    echo "   Run Sentinel (option 2) to see REBAC_DENIED in action."
    read -p "Press enter..."
}

restore_access() {
    echo "🔓 Restoring Tony's platform-team membership..."
    kubectl exec -it deployment/redis -- redis-cli sadd rebac:tony:member_of platform-team > /dev/null
    echo ""
    echo "✅ Tony's membership RESTORED."
    echo "   Authorization chain INTACT:"
    echo "   sentinel-agent → tony → platform-team → CryptoMining"
    echo ""
    echo "   Run Sentinel (option 2) to confirm REBAC_ALLOWED."
    read -p "Press enter..."
}

verify_graph() {
    clear
    echo "=================================================="
    echo "      🔍 ReBAC Relationship Graph"
    echo "=================================================="
    echo ""

    parse_set() {
        kubectl exec deployment/redis -- redis-cli smembers "$1" 2>/dev/null \
            | tr -d '\r' \
            | awk -F'"' 'NF>1{print $2} NF==1 && $0!=""{print $0}' \
            | paste -sd, - \
            | sed 's/,/, /g'
    }

    DELEGATE=$(parse_set "rebac:sentinel-agent:delegate_of")
    MEMBER=$(parse_set "rebac:tony:member_of")
    REMEDIATE=$(parse_set "rebac:platform-team:can_remediate")

    echo "  sentinel-agent --delegate_of-->   [ ${DELEGATE:-EMPTY} ]"
    echo "  tony           --member_of-->     [ ${MEMBER:-EMPTY} ]"
    echo "  platform-team  --can_remediate--> [ ${REMEDIATE:-EMPTY} ]"
    echo ""

    if [ -n "$DELEGATE" ] && [ -n "$MEMBER" ] && [ -n "$REMEDIATE" ]; then
        echo "  🟢 Chain: sentinel-agent → tony → platform-team → CryptoMining  [INTACT]"
    else
        printf "  \e[5;31m🔴 Chain BROKEN — authorization will be DENIED\e[0m\n"
    fi
    echo ""
    read -p "Press enter..."
}

check_status() {
    echo "--- POD INVENTORY ---"
    kubectl get pods --show-labels
    echo ""
    URL="http://127.0.0.1:8025"
    printf "📬 Audit Dashboard: \e]8;;$URL\e\\$URL\e]8;;\e\\ (Cmd+Click)\n"
    echo ""
    lsof -i :$REDIS_PORT -stcp:LISTEN >/dev/null && echo "✅ ReBAC Store (Redis): Online" || echo "❌ ReBAC Store: Offline"
    read -p "Press enter..."
}

stop_env() {
    echo -n "🛑 💤 Cleaning up..."
    (
        pkill -f "kubectl port-forward"
        pkill -f "minikube service mail-service"
        minikube stop > /dev/null 2>&1
    ) &
    spinner $!
    echo "✅ System Sleeping."
}

while true; do
    show_menu
    read opt
    case $opt in
        1) start_and_seed ;;
        2) run_sentinel ;;
        3) revoke_access ;;
        4) restore_access ;;
        5) verify_graph ;;
        6) check_status ;;
        7) stop_env ;;
        8)
            printf "🚪 Shutdown before exit? (y/n): "
            read confirm
            [[ "$confirm" == [yY] ]] && stop_env
            exit 0 ;;
    esac
done
