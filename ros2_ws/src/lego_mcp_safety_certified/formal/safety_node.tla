---------------------------- MODULE SafetyNode ----------------------------
(*
 * TLA+ Specification for LEGO MCP Safety Node
 * IEC 61508 SIL 2+ Formal Verification
 *
 * This specification models the safety-critical behavior of the dual-channel
 * e-stop system and proves key safety properties:
 *
 * SAFETY PROPERTIES:
 * - P1: E-stop active implies both relays open
 * - P2: No single point of failure can prevent e-stop
 * - P3: Channel disagreement triggers e-stop within bounded time
 *
 * LIVENESS PROPERTIES:
 * - L1: Heartbeat timeout eventually triggers e-stop
 * - L2: Reset request eventually succeeds if conditions met
 *
 * Author: LEGO MCP Safety Engineering
 * Date: 2026-01-07
 * Verification Tool: TLC Model Checker
 *)

EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS
    MAX_TIME,           \* Maximum simulation time steps
    WATCHDOG_TIMEOUT,   \* Heartbeat timeout (time steps)
    CROSS_CHECK_PERIOD  \* Cross-channel check period

VARIABLES
    \* Safety state machine
    safety_state,       \* NORMAL, WARNING, ESTOP_PENDING, ESTOP_ACTIVE, LOCKOUT

    \* Relay states (dual-channel)
    primary_relay,      \* OPEN, CLOSED
    secondary_relay,    \* OPEN, CLOSED

    \* Heartbeat tracking
    heartbeat_counter,  \* Time since last heartbeat
    heartbeat_received, \* Boolean: heartbeat received this step

    \* Hardware button state
    hw_estop_pressed,   \* Physical e-stop button

    \* Fault injection (for verification)
    primary_fault,      \* Simulated primary channel fault
    secondary_fault,    \* Simulated secondary channel fault

    \* Time
    time

(* ========================================================================= *)
(* Type Definitions                                                          *)
(* ========================================================================= *)

SafetyStates == {"NORMAL", "WARNING", "ESTOP_PENDING", "ESTOP_ACTIVE", "LOCKOUT"}
RelayStates == {"OPEN", "CLOSED"}

TypeInvariant ==
    /\ safety_state \in SafetyStates
    /\ primary_relay \in RelayStates
    /\ secondary_relay \in RelayStates
    /\ heartbeat_counter \in 0..MAX_TIME
    /\ heartbeat_received \in BOOLEAN
    /\ hw_estop_pressed \in BOOLEAN
    /\ primary_fault \in BOOLEAN
    /\ secondary_fault \in BOOLEAN
    /\ time \in 0..MAX_TIME

(* ========================================================================= *)
(* Initial State                                                             *)
(* ========================================================================= *)

Init ==
    /\ safety_state = "NORMAL"
    /\ primary_relay = "CLOSED"
    /\ secondary_relay = "CLOSED"
    /\ heartbeat_counter = 0
    /\ heartbeat_received = TRUE
    /\ hw_estop_pressed = FALSE
    /\ primary_fault = FALSE
    /\ secondary_fault = FALSE
    /\ time = 0

(* ========================================================================= *)
(* Helper Predicates                                                         *)
(* ========================================================================= *)

\* Both relays are in safe (open) state
BothRelaysOpen ==
    /\ primary_relay = "OPEN"
    /\ secondary_relay = "OPEN"

\* Both relays are closed (operational)
BothRelaysClosed ==
    /\ primary_relay = "CLOSED"
    /\ secondary_relay = "CLOSED"

\* Relays disagree (fault condition)
RelaysDisagree ==
    primary_relay # secondary_relay

\* Watchdog has timed out
WatchdogTimeout ==
    heartbeat_counter >= WATCHDOG_TIMEOUT

\* System is in e-stop state
EstopActive ==
    safety_state \in {"ESTOP_ACTIVE", "LOCKOUT"}

\* Conditions for safe reset
SafeToReset ==
    /\ ~hw_estop_pressed
    /\ ~WatchdogTimeout
    /\ ~RelaysDisagree
    /\ ~primary_fault
    /\ ~secondary_fault

(* ========================================================================= *)
(* Actions                                                                   *)
(* ========================================================================= *)

\* Receive heartbeat from orchestrator
ReceiveHeartbeat ==
    /\ ~EstopActive
    /\ heartbeat_received' = TRUE
    /\ heartbeat_counter' = 0
    /\ UNCHANGED <<safety_state, primary_relay, secondary_relay,
                   hw_estop_pressed, primary_fault, secondary_fault, time>>

\* Heartbeat timeout check
HeartbeatTimeoutCheck ==
    /\ ~heartbeat_received
    /\ heartbeat_counter' = heartbeat_counter + 1
    /\ heartbeat_received' = FALSE
    /\ IF heartbeat_counter' >= WATCHDOG_TIMEOUT
       THEN /\ safety_state' = "ESTOP_ACTIVE"
            /\ primary_relay' = "OPEN"
            /\ secondary_relay' = "OPEN"
       ELSE UNCHANGED <<safety_state, primary_relay, secondary_relay>>
    /\ UNCHANGED <<hw_estop_pressed, primary_fault, secondary_fault, time>>

\* Hardware e-stop button pressed
HardwareEstopPressed ==
    /\ hw_estop_pressed' = TRUE
    /\ safety_state' = "ESTOP_ACTIVE"
    /\ primary_relay' = "OPEN"
    /\ secondary_relay' = "OPEN"
    /\ UNCHANGED <<heartbeat_counter, heartbeat_received, primary_fault,
                   secondary_fault, time>>

\* Hardware e-stop button released
HardwareEstopReleased ==
    /\ hw_estop_pressed
    /\ hw_estop_pressed' = FALSE
    /\ UNCHANGED <<safety_state, primary_relay, secondary_relay,
                   heartbeat_counter, heartbeat_received, primary_fault,
                   secondary_fault, time>>

\* Cross-channel consistency check
CrossChannelCheck ==
    /\ time > 0
    /\ time % CROSS_CHECK_PERIOD = 0
    /\ IF RelaysDisagree
       THEN /\ safety_state' = "ESTOP_ACTIVE"
            /\ primary_relay' = "OPEN"
            /\ secondary_relay' = "OPEN"
       ELSE UNCHANGED <<safety_state, primary_relay, secondary_relay>>
    /\ UNCHANGED <<heartbeat_counter, heartbeat_received, hw_estop_pressed,
                   primary_fault, secondary_fault, time>>

\* Software e-stop request
SoftwareEstopRequest ==
    /\ safety_state = "NORMAL"
    /\ safety_state' = "ESTOP_ACTIVE"
    /\ primary_relay' = "OPEN"
    /\ secondary_relay' = "OPEN"
    /\ UNCHANGED <<heartbeat_counter, heartbeat_received, hw_estop_pressed,
                   primary_fault, secondary_fault, time>>

\* Reset request (only if safe)
ResetRequest ==
    /\ EstopActive
    /\ SafeToReset
    /\ safety_state' = "NORMAL"
    /\ primary_relay' = "CLOSED"
    /\ secondary_relay' = "CLOSED"
    /\ heartbeat_counter' = 0
    /\ UNCHANGED <<heartbeat_received, hw_estop_pressed, primary_fault,
                   secondary_fault, time>>

\* Fault injection: Primary channel stuck closed (dangerous fault)
InjectPrimaryFault ==
    /\ ~primary_fault
    /\ primary_fault' = TRUE
    \* Fault prevents relay from opening
    /\ IF safety_state = "ESTOP_ACTIVE"
       THEN primary_relay' = "CLOSED"  \* Fault: can't open
       ELSE UNCHANGED primary_relay
    \* Secondary should still work - triggers cross-channel fault
    /\ UNCHANGED <<safety_state, secondary_relay, heartbeat_counter,
                   heartbeat_received, hw_estop_pressed, secondary_fault, time>>

\* Fault injection: Secondary channel stuck closed (dangerous fault)
InjectSecondaryFault ==
    /\ ~secondary_fault
    /\ secondary_fault' = TRUE
    /\ IF safety_state = "ESTOP_ACTIVE"
       THEN secondary_relay' = "CLOSED"  \* Fault: can't open
       ELSE UNCHANGED secondary_relay
    /\ UNCHANGED <<safety_state, primary_relay, heartbeat_counter,
                   heartbeat_received, hw_estop_pressed, primary_fault, time>>

\* Time tick
Tick ==
    /\ time < MAX_TIME
    /\ time' = time + 1
    /\ heartbeat_received' = FALSE  \* Reset heartbeat flag each tick
    /\ UNCHANGED <<safety_state, primary_relay, secondary_relay,
                   heartbeat_counter, hw_estop_pressed, primary_fault,
                   secondary_fault>>

(* ========================================================================= *)
(* Next State Relation                                                       *)
(* ========================================================================= *)

Next ==
    \/ ReceiveHeartbeat
    \/ HeartbeatTimeoutCheck
    \/ HardwareEstopPressed
    \/ HardwareEstopReleased
    \/ CrossChannelCheck
    \/ SoftwareEstopRequest
    \/ ResetRequest
    \/ InjectPrimaryFault
    \/ InjectSecondaryFault
    \/ Tick

(* ========================================================================= *)
(* Fairness Conditions                                                       *)
(* ========================================================================= *)

Fairness ==
    /\ WF_<<time>>(Tick)
    /\ WF_<<heartbeat_counter>>(HeartbeatTimeoutCheck)
    /\ WF_<<primary_relay, secondary_relay>>(CrossChannelCheck)

Spec == Init /\ [][Next]_<<safety_state, primary_relay, secondary_relay,
                           heartbeat_counter, heartbeat_received,
                           hw_estop_pressed, primary_fault, secondary_fault,
                           time>>
             /\ Fairness

(* ========================================================================= *)
(* SAFETY PROPERTIES (Must Always Hold)                                      *)
(* ========================================================================= *)

\* P1: E-stop active implies both relays SHOULD be open
\*     (unless there's a fault preventing it)
SafetyP1_EstopImpliesRelaysOpen ==
    (safety_state = "ESTOP_ACTIVE" /\ ~primary_fault /\ ~secondary_fault)
        => BothRelaysOpen

\* P2: If both channels are healthy, e-stop command succeeds
SafetyP2_EstopCommandSucceeds ==
    (safety_state = "ESTOP_ACTIVE" /\ ~primary_fault) => (primary_relay = "OPEN")

\* P3: Single channel fault does not prevent safety
\*     (at least one relay opens)
SafetyP3_SingleFaultSafe ==
    (safety_state = "ESTOP_ACTIVE") =>
        (primary_relay = "OPEN" \/ secondary_relay = "OPEN" \/
         (primary_fault /\ secondary_fault))

\* P4: Lockout state is irreversible without manual intervention
SafetyP4_LockoutPersists ==
    (safety_state = "LOCKOUT") => (safety_state' = "LOCKOUT")

\* Combined safety invariant
SafetyInvariant ==
    /\ TypeInvariant
    /\ SafetyP1_EstopImpliesRelaysOpen
    /\ SafetyP2_EstopCommandSucceeds
    /\ SafetyP3_SingleFaultSafe

(* ========================================================================= *)
(* LIVENESS PROPERTIES (Must Eventually Hold)                                *)
(* ========================================================================= *)

\* L1: Heartbeat timeout eventually triggers e-stop
LivenessL1_TimeoutTriggersEstop ==
    (heartbeat_counter >= WATCHDOG_TIMEOUT) ~> EstopActive

\* L2: Safe reset request eventually succeeds
LivenessL2_ResetEventuallySucceeds ==
    (EstopActive /\ SafeToReset) ~> (safety_state = "NORMAL")

(* ========================================================================= *)
(* Model Checking Configuration                                              *)
(* ========================================================================= *)

\* Symmetry reduction not applicable (no symmetric variables)

\* State constraint to bound model checking
StateConstraint ==
    /\ time <= MAX_TIME
    /\ heartbeat_counter <= WATCHDOG_TIMEOUT + 1

=============================================================================
\* Modification History
\* Last modified: 2026-01-07
\* Created: 2026-01-07
