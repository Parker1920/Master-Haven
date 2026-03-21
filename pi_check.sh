#!/bin/bash
# Pi Resource Check — Run: bash pi_check.sh

echo "============================================"
echo "  PI RESOURCE CHECK"
echo "  $(hostname) — $(date)"
echo "============================================"
echo

# CPU
echo "── CPU ──"
echo "  Model:  $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
echo "  Cores:  $(nproc)"
freq=$(vcgencmd measure_clock arm 2>/dev/null | cut -d= -f2)
if [ -n "$freq" ]; then
    echo "  Freq:   $((freq / 1000000)) MHz"
fi
temp=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
if [ -n "$temp" ]; then
    echo "  Temp:   $temp"
fi
echo

# RAM
echo "── MEMORY ──"
free -h | awk '
/^Mem:/ { printf "  Total:     %s\n  Used:      %s\n  Free:      %s\n  Available: %s\n", $2, $3, $4, $7 }
/^Swap:/ { printf "  Swap:      %s / %s\n", $3, $2 }
'
echo

# Load
echo "── LOAD ──"
uptime_str=$(uptime)
echo "  $uptime_str"
echo

# Disk
echo "── DISK ──"
df -h / | awk 'NR==2 { printf "  Total: %s  Used: %s (%s)  Free: %s\n", $2, $3, $5, $4 }'
echo

# Top processes by memory
echo "── TOP 10 PROCESSES (by RAM) ──"
ps aux --sort=-%mem | head -11 | awk 'NR==1 { printf "  %-8s %5s %5s  %s\n", "USER", "%MEM", "%CPU", "COMMAND" } NR>1 { printf "  %-8s %5s %5s  %s\n", $1, $4, $3, $11 }'
echo

# Docker (if running)
if command -v docker &>/dev/null; then
    echo "── DOCKER ──"
    docker stats --no-stream --format "  {{.Name}}: {{.MemUsage}} ({{.MemPerc}} RAM, {{.CPUPerc}} CPU)" 2>/dev/null || echo "  Docker not running"
    echo
fi

# Can it run the trade engine?
echo "── TRADE ENGINE FEASIBILITY ──"
avail_mb=$(free -m | awk '/^Mem:/ { print $7 }')
cores=$(nproc)
if [ "$avail_mb" -ge 2048 ]; then
    echo "  RAM:    OK ($avail_mb MB available, need ~2 GB)"
elif [ "$avail_mb" -ge 1024 ]; then
    echo "  RAM:    TIGHT ($avail_mb MB available, want 2 GB)"
else
    echo "  RAM:    LOW ($avail_mb MB available, need 1+ GB)"
fi
if [ "$cores" -ge 4 ]; then
    echo "  CPU:    OK ($cores cores)"
else
    echo "  CPU:    LIMITED ($cores cores)"
fi
python3 --version 2>/dev/null && echo "  Python: $(python3 --version)" || echo "  Python: NOT INSTALLED"
echo
echo "============================================"
