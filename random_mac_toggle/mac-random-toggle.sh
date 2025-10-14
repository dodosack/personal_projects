#!/usr/bin/env bash
# mac-random-toggle.sh (verbessert, finale Version)
# CLI: up | down | status | test
#  - erkennt automatisch aktive WLAN-Verbindungen (auch bei VPN)
#  - zeigt aktuelle MAC-Adresse (Hardware und aktiv)
#  - farbige Ausgaben mit Statusmeldungen

set -euo pipefail
IFS=$'\n\t'

SCRIPT_NAME=$(basename "$0")
DRY_RUN=0
CONN=""
IFACE=""
ACTION=""

if [[ -t 1 ]]; then
  RED=$(printf '\033[31m'); GREEN=$(printf '\033[32m'); YELLOW=$(printf '\033[33m'); BLUE=$(printf '\033[34m'); BOLD=$(printf '\033[1m'); RESET=$(printf '\033[0m')
else
  RED=; GREEN=; YELLOW=; BLUE=; BOLD=; RESET=
fi

usage(){
  cat <<EOF
Usage: $SCRIPT_NAME <up|down|status|test> [options]

Commands:
  up        Aktiviert MAC-Randomisierung und reconnectet
  down      Deaktiviert Randomisierung (echte MAC)
  status    Zeigt MAC-Zustand, Modus und aktive Adresse
  test      Testlauf (dry-run)

Options:
  -c, --conn <name>   Connection-Name (z. B. "Cafe-WLAN")
  -i, --iface <if>    Interface (z. B. wlan0)
  -n, --dry-run       Nur anzeigen, nichts ausführen
  -h, --help          Diese Hilfe
EOF
}

[[ $# -lt 1 ]] && { usage; exit 2; }
ACTION=$1; shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--conn) CONN="$2"; shift 2;;
    -i|--iface) IFACE="$2"; shift 2;;
    -n|--dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 2;;
  esac
 done

run_cmd(){ if [[ $DRY_RUN -eq 1 ]]; then echo -e "${YELLOW}[DRY-RUN]${RESET} $*"; else echo -e "${BLUE}RUN:${RESET} $*"; eval "$@"; fi; }

check_requirements(){ command -v nmcli >/dev/null 2>&1 || { echo -e "${RED}nmcli not found${RESET}"; exit 1; } }

get_target_connections(){
  if [[ -n "$CONN" ]]; then
    echo "$CONN"
    return
  fi
  if [[ -n "$IFACE" ]]; then
    nmcli -t -f NAME,DEVICE,TYPE connection show --active | awk -F: -v iface="$IFACE" '$3=="wifi" && $2==iface {print $1}'
    return
  fi
  CURRENT_SSID=$(nmcli -t -f active,ssid dev wifi | awk -F: '$1=="yes"{print $2; exit}')
  [[ -n "$CURRENT_SSID" ]] && echo "$CURRENT_SSID"
}

get_property(){ nmcli connection show "$1" 2>/dev/null | awk -F: '/wifi.cloned-mac-address/{gsub(/^ +| +$/,"",$2); print $2}' || true; }
get_iface(){ nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v conn="$1" '$1==conn{print $2}'; }
get_current_mac(){ local iface="$1"; cat /sys/class/net/$iface/address 2>/dev/null || echo "unknown"; }
get_hw_mac(){ local iface="$1"; nmcli -f GENERAL.HWADDR device show "$iface" 2>/dev/null | awk '{print $2}'; }

set_property(){ local conn="$1" prop="$2" val="$3"; echo -e "Setting ${BOLD}${prop}=${val}${RESET} for ${GREEN}${conn}${RESET}"; run_cmd nmcli connection modify "$conn" "$prop" "$val"; }
reconnect_conn(){ local conn="$1"; echo -e "Reconnecting ${GREEN}${conn}${RESET}..."; run_cmd nmcli connection down "$conn" || true; run_cmd nmcli connection up "$conn"; }

action_up(){ local conns=$(get_target_connections); [[ -z "$conns" ]] && { echo -e "${RED}No Wi-Fi connection found${RESET}"; exit 1; }
  for c in $conns; do
    local iface=$(get_iface "$c"); echo "--- ${BOLD}$c${RESET} (${iface}) ---"
    local before=$(get_property "$c")
    echo "Before: cloned-mac = ${before:-(unset)}"
    set_property "$c" wifi.cloned-mac-address random
    reconnect_conn "$c"
    local after=$(get_property "$c")
    local cur_mac=$(get_current_mac "$iface")
    local hw_mac=$(get_hw_mac "$iface")
    echo -e "After: cloned-mac = ${after:-(unset)}"
    echo -e "Current MAC: ${GREEN}$cur_mac${RESET} | HW MAC: ${YELLOW}$hw_mac${RESET}\n"
  done
}

action_down(){ local conns=$(get_target_connections); [[ -z "$conns" ]] && { echo -e "${RED}No Wi-Fi connection found${RESET}"; exit 1; }
  for c in $conns; do
    local iface=$(get_iface "$c"); echo "--- ${BOLD}$c${RESET} (${iface}) ---"
    local before=$(get_property "$c")
    echo "Before: cloned-mac = ${before:-(unset)}"
    set_property "$c" wifi.cloned-mac-address preserve
    reconnect_conn "$c"
    local after=$(get_property "$c")
    local cur_mac=$(get_current_mac "$iface")
    local hw_mac=$(get_hw_mac "$iface")
    echo -e "After: cloned-mac = ${after:-(unset)}"
    echo -e "Current MAC: ${GREEN}$cur_mac${RESET} | HW MAC: ${YELLOW}$hw_mac${RESET}\n"
  done
}

action_status(){ local conns=$(get_target_connections); [[ -z "$conns" ]] && { echo -e "${YELLOW}No Wi-Fi connection found${RESET}"; exit 0; }
  for c in $conns; do
    local iface=$(get_iface "$c"); local val=$(get_property "$c"); local cur_mac=$(get_current_mac "$iface"); local hw_mac=$(get_hw_mac "$iface")
    echo -e "--- ${BOLD}$c${RESET} (${iface}) ---"
    echo -e "wifi.cloned-mac-address = ${val:-(unset)}"
    echo -e "Current MAC: ${GREEN}$cur_mac${RESET} | HW MAC: ${YELLOW}$hw_mac${RESET}\n"
  done
}

action_test(){ DRY_RUN=1; check_requirements; echo -e "${BOLD}Self-test (dry-run).${RESET}"; action_status; }

case "$ACTION" in
  up) check_requirements; action_up;;
  down) check_requirements; action_down;;
  status) check_requirements; action_status;;
  test) action_test;;
  *) usage; exit 2;;
esac
