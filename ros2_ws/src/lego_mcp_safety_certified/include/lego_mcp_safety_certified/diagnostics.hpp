/**
 * @file diagnostics.hpp
 * @brief Safety Diagnostics and Self-Test Framework
 *
 * IEC 61508 SIL 2+ Diagnostic Coverage Implementation
 *
 * Provides:
 * - Continuous runtime diagnostics
 * - Power-on self-test (POST)
 * - Periodic proof tests
 * - Diagnostic coverage calculation
 * - Failure mode reporting
 *
 * DIAGNOSTIC COVERAGE TARGETS (per IEC 61508-2):
 * - SIL 2: DC >= 90% for Type A, >= 99% for Type B
 * - SIL 2+ (enhanced): DC >= 99% for all components
 */

#ifndef LEGO_MCP_SAFETY_CERTIFIED__DIAGNOSTICS_HPP_
#define LEGO_MCP_SAFETY_CERTIFIED__DIAGNOSTICS_HPP_

#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace lego_mcp
{

/**
 * @brief Diagnostic test result
 */
enum class DiagResult : std::uint8_t
{
    PASS = 0U,
    FAIL = 1U,
    DEGRADED = 2U,
    NOT_RUN = 3U,
    TIMEOUT = 4U
};

/**
 * @brief Failure mode category (per IEC 61508)
 */
enum class FailureMode : std::uint8_t
{
    SAFE = 0U,        ///< Failure leads to safe state
    DANGEROUS = 1U,   ///< Failure could compromise safety
    NO_EFFECT = 2U    ///< Failure has no safety impact
};

/**
 * @brief Individual diagnostic test definition
 */
struct DiagTest
{
    std::string id;
    std::string name;
    std::string description;
    FailureMode failure_mode;
    std::chrono::milliseconds expected_duration;
    bool is_critical;
};

/**
 * @brief Diagnostic test result record
 */
struct DiagTestResult
{
    std::string test_id;
    DiagResult result;
    std::string message;
    std::chrono::steady_clock::time_point timestamp;
    std::chrono::microseconds duration;
    std::uint32_t sequence;
};

/**
 * @brief Diagnostic coverage summary
 */
struct DiagCoverage
{
    /// Total detectable dangerous failures
    std::uint32_t dangerous_detected{0U};

    /// Total dangerous failures (detected + undetected)
    std::uint32_t dangerous_total{0U};

    /// Total safe failures detected
    std::uint32_t safe_detected{0U};

    /// Diagnostic coverage (DC) percentage
    float dc_percentage{0.0F};

    /// Safe failure fraction (SFF) percentage
    float sff_percentage{0.0F};

    /// Last calculation timestamp
    std::chrono::steady_clock::time_point calculated_at;
};

/**
 * @brief System health status
 */
struct HealthStatus
{
    bool overall_healthy{false};
    DiagCoverage coverage;
    std::uint32_t tests_passed{0U};
    std::uint32_t tests_failed{0U};
    std::uint32_t tests_degraded{0U};
    std::vector<DiagTestResult> failed_tests;
    std::chrono::steady_clock::time_point last_full_check;
};

/**
 * @brief Diagnostics Manager
 *
 * Manages all safety-related diagnostics including:
 * - Power-on self-test (POST)
 * - Continuous runtime monitoring
 * - Periodic proof tests
 * - Diagnostic coverage calculation
 *
 * TIMING CONSTRAINTS:
 * - POST: < 5 seconds total
 * - Runtime checks: < 1ms each
 * - Full diagnostic cycle: < 100ms
 */
class DiagnosticsManager
{
public:
    /// Callback type for diagnostic completion
    using DiagCompleteCallback = std::function<void(const HealthStatus&)>;

    /// Test function type
    using TestFunction = std::function<DiagResult(std::string&)>;

    /**
     * @brief Default constructor
     */
    DiagnosticsManager();

    /**
     * @brief Register a diagnostic test
     *
     * @param test Test definition
     * @param test_fn Test function to execute
     */
    void register_test(const DiagTest& test, TestFunction test_fn);

    /**
     * @brief Run power-on self-test
     *
     * Executes all registered tests marked as POST.
     * Must pass before system can enter NORMAL state.
     *
     * @return HealthStatus with all test results
     */
    [[nodiscard]] HealthStatus run_post();

    /**
     * @brief Run single diagnostic test
     *
     * @param test_id Test identifier
     * @return Test result
     */
    [[nodiscard]] DiagTestResult run_test(const std::string& test_id);

    /**
     * @brief Run all diagnostic tests
     *
     * @return HealthStatus with all test results
     */
    [[nodiscard]] HealthStatus run_all_tests();

    /**
     * @brief Run critical tests only
     *
     * Fast subset of tests for runtime monitoring.
     *
     * @return HealthStatus with critical test results
     */
    [[nodiscard]] HealthStatus run_critical_tests();

    /**
     * @brief Calculate diagnostic coverage
     *
     * Computes DC and SFF based on failure mode analysis.
     *
     * @return DiagCoverage with calculated values
     */
    [[nodiscard]] DiagCoverage calculate_coverage() const;

    /**
     * @brief Get current health status
     *
     * Returns cached status from last test run.
     */
    [[nodiscard]] const HealthStatus& current_status() const noexcept
    {
        return current_status_;
    }

    /**
     * @brief Check if system is healthy
     */
    [[nodiscard]] bool is_healthy() const noexcept
    {
        return current_status_.overall_healthy;
    }

    /**
     * @brief Get test history
     *
     * @param test_id Test identifier (empty = all tests)
     * @param max_results Maximum results to return
     * @return Vector of test results
     */
    [[nodiscard]] std::vector<DiagTestResult> get_history(
        const std::string& test_id = "",
        std::size_t max_results = 100) const;

    /**
     * @brief Clear test history
     */
    void clear_history();

    /**
     * @brief Set diagnostic completion callback
     */
    void set_callback(DiagCompleteCallback callback)
    {
        callback_ = std::move(callback);
    }

    /**
     * @brief Get registered test count
     */
    [[nodiscard]] std::size_t test_count() const noexcept
    {
        return tests_.size();
    }

    // =========================================================================
    // Built-in diagnostic tests
    // =========================================================================

    /**
     * @brief CPU self-test
     *
     * Verifies basic CPU operations, arithmetic, and logic.
     */
    [[nodiscard]] static DiagResult test_cpu(std::string& message);

    /**
     * @brief Memory self-test
     *
     * Pattern test on allocated memory regions.
     */
    [[nodiscard]] static DiagResult test_memory(std::string& message);

    /**
     * @brief Stack canary test
     *
     * Verifies stack protection is active.
     */
    [[nodiscard]] static DiagResult test_stack_canary(std::string& message);

    /**
     * @brief Timing self-test
     *
     * Verifies system clock and timer accuracy.
     */
    [[nodiscard]] static DiagResult test_timing(std::string& message);

    /**
     * @brief GPIO self-test
     *
     * Tests GPIO read/write operations (simulation mode if no hardware).
     */
    [[nodiscard]] static DiagResult test_gpio(std::string& message);

    /**
     * @brief Watchdog self-test
     *
     * Verifies watchdog timer responds correctly.
     */
    [[nodiscard]] static DiagResult test_watchdog(std::string& message);

private:
    /**
     * @brief Internal test record
     */
    struct RegisteredTest
    {
        DiagTest definition;
        TestFunction function;
    };

    /// Registered tests
    std::vector<RegisteredTest> tests_;

    /// Test history (circular buffer)
    std::vector<DiagTestResult> history_;
    std::size_t max_history_{1000U};

    /// Current health status
    HealthStatus current_status_;

    /// Sequence counter
    std::uint32_t sequence_{0U};

    /// Completion callback
    DiagCompleteCallback callback_;
};

}  // namespace lego_mcp

#endif  // LEGO_MCP_SAFETY_CERTIFIED__DIAGNOSTICS_HPP_
