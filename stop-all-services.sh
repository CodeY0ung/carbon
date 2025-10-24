#!/bin/bash

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  CASPIAN - Stopping All Services${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Stop port forwarding processes
echo -e "${YELLOW}Stopping port forwarding processes...${NC}"
if pgrep -f "kubectl.*port-forward" > /dev/null; then
    pkill -f "kubectl.*port-forward" 2>/dev/null || true
    print_status "Port forwarding processes stopped"
else
    print_warning "No port forwarding processes found"
fi

# Delete all Kind clusters
echo ""
echo -e "${YELLOW}Deleting Kind clusters...${NC}"

CLUSTERS=$(kind get clusters 2>/dev/null || echo "")

if [ -z "$CLUSTERS" ]; then
    print_warning "No Kind clusters found"
else
    for cluster in $CLUSTERS; do
        echo -n "  Deleting cluster: $cluster... "
        if kind delete cluster --name "$cluster" 2>/dev/null; then
            echo -e "${GREEN}done${NC}"
        else
            echo -e "${RED}failed${NC}"
        fi
    done
    print_status "All Kind clusters deleted"
fi

# Clean up Docker resources
echo ""
echo -e "${YELLOW}Cleaning up Docker resources...${NC}"

# Stop any running carbon-hub containers
if docker ps -a | grep -q "carbon-hub"; then
    echo -n "  Stopping carbon-hub containers... "
    docker stop $(docker ps -a | grep "carbon-hub" | awk '{print $1}') 2>/dev/null || true
    docker rm $(docker ps -a | grep "carbon-hub" | awk '{print $1}') 2>/dev/null || true
    echo -e "${GREEN}done${NC}"
fi

# Remove unused Docker images (optional - commented out by default)
# Uncomment the following lines if you want to remove Docker images as well
# echo -n "  Removing unused Docker images... "
# docker image prune -f > /dev/null 2>&1
# echo -e "${GREEN}done${NC}"

print_status "Docker resources cleaned up"

# Clean up temporary files
echo ""
echo -e "${YELLOW}Cleaning up temporary files...${NC}"

TEMP_FILES=(
    "dashboard-complete.json"
    "dashboard-updated.json"
    "current-dashboard.json"
    "dashboard-for-configmap.json"
)

for file in "${TEMP_FILES[@]}"; do
    if [ -f "$file" ]; then
        rm -f "$file"
        echo "  Removed: $file"
    fi
done

print_status "Temporary files cleaned up"

# Check for any remaining processes
echo ""
echo -e "${YELLOW}Checking for remaining processes...${NC}"

# Check for kubectl processes
if pgrep -f "kubectl" > /dev/null; then
    print_warning "Some kubectl processes are still running"
    pgrep -f "kubectl" | while read pid; do
        echo "    PID: $pid - $(ps -p $pid -o comm=)"
    done
else
    print_status "No kubectl processes running"
fi

# Check for docker processes related to kind
if docker ps | grep -q "kindest/node"; then
    print_warning "Some Kind-related Docker containers are still running"
    docker ps --filter "ancestor=kindest/node" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"
else
    print_status "No Kind-related containers running"
fi

# Summary
echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}  Cleanup Complete!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "All CASPIAN services have been stopped."
echo ""
echo "To restart the system, run:"
echo -e "  ${YELLOW}bash start-complete-system.sh${NC}"
echo ""
echo "Or on Windows:"
echo -e "  ${YELLOW}start-system.bat${NC}"
echo ""
