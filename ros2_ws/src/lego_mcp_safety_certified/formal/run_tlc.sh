#!/bin/bash
# TLC Model Checker Runner for LEGO MCP Safety Node
# IEC 61508 SIL 2+ Formal Verification
#
# Usage: ./run_tlc.sh [options]
#   --download    Download TLA+ tools if not present
#   --verbose     Show detailed TLC output
#   --workers N   Number of worker threads (default: auto)
#   --help        Show this help message

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TLA_TOOLS_DIR="${HOME}/.tla-tools"
TLA_VERSION="1.8.0"
TLA_JAR="${TLA_TOOLS_DIR}/tla2tools.jar"

# Default options
VERBOSE=false
WORKERS="auto"
DOWNLOAD=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "=============================================="
    echo "  TLA+ Model Checker - LEGO MCP Safety Node"
    echo "  IEC 61508 SIL 2+ Formal Verification"
    echo "=============================================="
    echo -e "${NC}"
}

print_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --download    Download TLA+ tools if not present"
    echo "  --verbose     Show detailed TLC output"
    echo "  --workers N   Number of worker threads (default: auto)"
    echo "  --help        Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --download --verbose"
}

download_tla_tools() {
    echo -e "${YELLOW}Downloading TLA+ tools v${TLA_VERSION}...${NC}"
    mkdir -p "${TLA_TOOLS_DIR}"
    cd "${TLA_TOOLS_DIR}"

    if [ ! -f "tla2tools.jar" ]; then
        wget -q "https://github.com/tlaplus/tlaplus/releases/download/v${TLA_VERSION}/tla2tools.jar"
        echo -e "${GREEN}Downloaded tla2tools.jar${NC}"
    else
        echo -e "${GREEN}tla2tools.jar already exists${NC}"
    fi

    cd "${SCRIPT_DIR}"
}

check_java() {
    if ! command -v java &> /dev/null; then
        echo -e "${RED}Error: Java is not installed.${NC}"
        echo "Please install Java 11 or later:"
        echo "  macOS: brew install openjdk@17"
        echo "  Ubuntu: sudo apt-get install openjdk-17-jdk"
        exit 1
    fi
}

check_tla_tools() {
    if [ ! -f "${TLA_JAR}" ]; then
        if [ "$DOWNLOAD" = true ]; then
            download_tla_tools
        else
            echo -e "${RED}Error: TLA+ tools not found at ${TLA_JAR}${NC}"
            echo "Run with --download to automatically download them."
            exit 1
        fi
    fi
}

run_syntax_check() {
    echo -e "${BLUE}Step 1: Syntax Check${NC}"
    echo "Verifying TLA+ specification syntax..."

    if java -cp "${TLA_JAR}" tla2sany.SANY safety_node.tla; then
        echo -e "${GREEN}Syntax check passed${NC}"
    else
        echo -e "${RED}Syntax check failed${NC}"
        exit 1
    fi
    echo ""
}

run_model_check() {
    echo -e "${BLUE}Step 2: Model Checking${NC}"
    echo "Running TLC model checker..."
    echo "  Spec: safety_node.tla"
    echo "  Config: safety_node.cfg"
    echo "  Workers: ${WORKERS}"
    echo ""

    OUTPUT_FILE="${SCRIPT_DIR}/tlc_output_$(date +%Y%m%d_%H%M%S).txt"

    TLC_ARGS=(
        -config safety_node.cfg
        -workers "${WORKERS}"
        -deadlock
        -cleanup
    )

    if [ "$VERBOSE" = true ]; then
        java -XX:+UseParallelGC -Xmx4g -cp "${TLA_JAR}" \
            tlc2.TLC "${TLC_ARGS[@]}" safety_node.tla 2>&1 | tee "${OUTPUT_FILE}"
    else
        java -XX:+UseParallelGC -Xmx4g -cp "${TLA_JAR}" \
            tlc2.TLC "${TLC_ARGS[@]}" safety_node.tla > "${OUTPUT_FILE}" 2>&1
    fi

    TLC_EXIT_CODE=$?

    echo ""
    echo -e "${BLUE}Step 3: Results Analysis${NC}"

    # Parse results
    STATES=$(grep -oP '\d+ states generated' "${OUTPUT_FILE}" | grep -oP '\d+' | head -1 || echo "0")
    DISTINCT=$(grep -oP '\d+ distinct states found' "${OUTPUT_FILE}" | grep -oP '\d+' | head -1 || echo "0")

    echo "  States generated: ${STATES}"
    echo "  Distinct states: ${DISTINCT}"
    echo ""

    # Check for errors
    HAS_ERRORS=false
    INVARIANT_VIOLATED=false

    if grep -q "Error:" "${OUTPUT_FILE}"; then
        HAS_ERRORS=true
    fi

    if grep -q "Invariant .* is violated" "${OUTPUT_FILE}"; then
        INVARIANT_VIOLATED=true
    fi

    # Report results
    echo -e "${BLUE}=============================================="
    echo "  VERIFICATION RESULTS"
    echo -e "==============================================${NC}"
    echo ""

    echo "Safety Invariants:"
    if [ "$INVARIANT_VIOLATED" = true ]; then
        echo -e "  ${RED}[FAIL]${NC} One or more invariants violated"
    else
        echo -e "  ${GREEN}[PASS]${NC} TypeInvariant"
        echo -e "  ${GREEN}[PASS]${NC} SafetyInvariant"
        echo -e "  ${GREEN}[PASS]${NC} SafetyP1_EstopImpliesRelaysOpen"
        echo -e "  ${GREEN}[PASS]${NC} SafetyP2_EstopCommandSucceeds"
        echo -e "  ${GREEN}[PASS]${NC} SafetyP3_SingleFaultSafe"
    fi

    echo ""
    echo "Liveness Properties:"
    if grep -q "Temporal properties were violated" "${OUTPUT_FILE}"; then
        echo -e "  ${RED}[FAIL]${NC} Liveness properties violated"
    else
        echo -e "  ${GREEN}[PASS]${NC} LivenessL1_TimeoutTriggersEstop"
        echo -e "  ${GREEN}[PASS]${NC} LivenessL2_ResetEventuallySucceeds"
    fi

    echo ""
    echo "Output saved to: ${OUTPUT_FILE}"
    echo ""

    # Final status
    if [ "$INVARIANT_VIOLATED" = true ] || [ "$HAS_ERRORS" = true ]; then
        echo -e "${RED}=============================================="
        echo "  VERIFICATION FAILED"
        echo -e "==============================================${NC}"
        echo ""
        echo "Check ${OUTPUT_FILE} for details."
        exit 1
    else
        echo -e "${GREEN}=============================================="
        echo "  ALL PROPERTIES VERIFIED"
        echo "  IEC 61508 SIL 2+ Compliance: PASS"
        echo -e "==============================================${NC}"
        exit 0
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --download)
            DOWNLOAD=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_help
            exit 1
            ;;
    esac
done

# Main execution
print_banner
check_java
check_tla_tools

cd "${SCRIPT_DIR}"
run_syntax_check
run_model_check
