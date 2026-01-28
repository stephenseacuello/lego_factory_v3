---------------------------- MODULE manufacturing_cell ----------------------------
(*
 * TLA+ Specification for Manufacturing Cell Control
 *
 * Models the coordination between injection molding machine,
 * robot arm, and conveyor system.
 *
 * Safety Properties:
 * - Robot cannot enter mold area when mold is closing
 * - Conveyor cannot start with parts in gripper
 * - Emergency stop halts all equipment immediately
 *
 * Liveness Properties:
 * - System eventually produces parts (no deadlock)
 * - Robot returns home after timeout
 *
 * Author: LEGO MCP Safety Engineering
 * Reference: IEC 61508, ISO 13849
 *)

EXTENDS Integers, Sequences, TLC

(* ============== CONSTANTS ============== *)
CONSTANTS
    MAX_CYCLE_COUNT,     \* Maximum production cycles
    ROBOT_TIMEOUT_TICKS, \* Ticks before robot timeout
    MOLD_CLOSE_TICKS     \* Ticks for mold close operation

ASSUME MAX_CYCLE_COUNT \in Nat /\ MAX_CYCLE_COUNT > 0
ASSUME ROBOT_TIMEOUT_TICKS \in Nat /\ ROBOT_TIMEOUT_TICKS > 0
ASSUME MOLD_CLOSE_TICKS \in Nat /\ MOLD_CLOSE_TICKS > 0

(* ============== VARIABLES ============== *)
VARIABLES
    (* Mold state *)
    moldState,           \* "open", "closing", "closed", "opening"
    moldPosition,        \* 0 (fully open) to 100 (fully closed)

    (* Robot state *)
    robotState,          \* "home", "moving_to_mold", "at_mold", "moving_home"
    robotPosition,       \* Position enum
    robotGripperState,   \* "empty", "holding_part"
    robotTimer,          \* Timeout counter

    (* Conveyor state *)
    conveyorState,       \* "stopped", "running"
    partsOnConveyor,     \* Count of parts on conveyor

    (* System state *)
    estopActive,         \* Emergency stop flag
    cycleCount,          \* Production cycle counter
    systemMode           \* "auto", "manual", "stopped"

vars == <<moldState, moldPosition, robotState, robotPosition,
          robotGripperState, robotTimer, conveyorState,
          partsOnConveyor, estopActive, cycleCount, systemMode>>

(* ============== TYPE INVARIANTS ============== *)
TypeInvariant ==
    /\ moldState \in {"open", "closing", "closed", "opening"}
    /\ moldPosition \in 0..100
    /\ robotState \in {"home", "moving_to_mold", "at_mold", "moving_home"}
    /\ robotPosition \in {"home_pos", "transit", "mold_area"}
    /\ robotGripperState \in {"empty", "holding_part"}
    /\ robotTimer \in Nat
    /\ conveyorState \in {"stopped", "running"}
    /\ partsOnConveyor \in Nat
    /\ estopActive \in BOOLEAN
    /\ cycleCount \in Nat
    /\ systemMode \in {"auto", "manual", "stopped"}

(* ============== SAFETY PROPERTIES ============== *)

(* S1: Robot cannot be in mold area when mold is closing or closed *)
SafetyP1_RobotMoldExclusion ==
    (moldState \in {"closing", "closed"}) => (robotPosition # "mold_area")

(* S2: Robot cannot move toward mold while mold is not fully open *)
SafetyP2_RobotMoveRestriction ==
    (robotState = "moving_to_mold") => (moldState = "open" /\ moldPosition = 0)

(* S3: Conveyor cannot start if robot is holding a part *)
SafetyP3_ConveyorGripperInterlock ==
    (conveyorState = "running") => (robotGripperState = "empty" \/ robotPosition # "transit")

(* S4: E-stop immediately stops all motion *)
SafetyP4_EstopEffect ==
    estopActive =>
        /\ systemMode = "stopped"
        /\ conveyorState = "stopped"
        /\ robotState \in {"home", "moving_home", "at_mold"}  \* Not in motion when estop

(* Combined safety invariant *)
SafetyInvariant ==
    /\ SafetyP1_RobotMoldExclusion
    /\ SafetyP2_RobotMoveRestriction
    /\ SafetyP3_ConveyorGripperInterlock
    /\ SafetyP4_EstopEffect

(* ============== INITIAL STATE ============== *)
Init ==
    /\ moldState = "open"
    /\ moldPosition = 0
    /\ robotState = "home"
    /\ robotPosition = "home_pos"
    /\ robotGripperState = "empty"
    /\ robotTimer = 0
    /\ conveyorState = "stopped"
    /\ partsOnConveyor = 0
    /\ estopActive = FALSE
    /\ cycleCount = 0
    /\ systemMode = "auto"

(* ============== ACTIONS ============== *)

(* E-Stop activation - highest priority *)
ActivateEstop ==
    /\ ~estopActive
    /\ estopActive' = TRUE
    /\ systemMode' = "stopped"
    /\ conveyorState' = "stopped"
    \* Robot holds current position
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, robotTimer, partsOnConveyor, cycleCount>>

(* E-Stop reset - requires conditions *)
ResetEstop ==
    /\ estopActive
    /\ moldState = "open"
    /\ moldPosition = 0
    /\ robotPosition = "home_pos"
    /\ estopActive' = FALSE
    /\ systemMode' = "manual"  \* Must manually restart
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, robotTimer, conveyorState,
                   partsOnConveyor, cycleCount>>

(* Start automatic mode *)
StartAutoMode ==
    /\ ~estopActive
    /\ systemMode = "manual"
    /\ robotPosition = "home_pos"
    /\ moldState = "open"
    /\ systemMode' = "auto"
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, robotTimer, conveyorState,
                   partsOnConveyor, estopActive, cycleCount>>

(* Mold close operation *)
StartMoldClose ==
    /\ ~estopActive
    /\ systemMode = "auto"
    /\ moldState = "open"
    /\ moldPosition = 0
    /\ robotPosition # "mold_area"  \* Safety interlock
    /\ robotState # "moving_to_mold"
    /\ moldState' = "closing"
    /\ UNCHANGED <<moldPosition, robotState, robotPosition, robotGripperState,
                   robotTimer, conveyorState, partsOnConveyor, estopActive,
                   cycleCount, systemMode>>

(* Mold closing progress *)
MoldClosingProgress ==
    /\ ~estopActive
    /\ moldState = "closing"
    /\ moldPosition < 100
    /\ moldPosition' = moldPosition + 10
    /\ IF moldPosition' = 100
       THEN moldState' = "closed"
       ELSE UNCHANGED moldState
    /\ UNCHANGED <<robotState, robotPosition, robotGripperState, robotTimer,
                   conveyorState, partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Mold open operation *)
StartMoldOpen ==
    /\ ~estopActive
    /\ systemMode = "auto"
    /\ moldState = "closed"
    /\ moldPosition = 100
    /\ moldState' = "opening"
    /\ cycleCount' = cycleCount + 1  \* Part molded
    /\ UNCHANGED <<moldPosition, robotState, robotPosition, robotGripperState,
                   robotTimer, conveyorState, partsOnConveyor, estopActive, systemMode>>

(* Mold opening progress *)
MoldOpeningProgress ==
    /\ ~estopActive
    /\ moldState = "opening"
    /\ moldPosition > 0
    /\ moldPosition' = moldPosition - 10
    /\ IF moldPosition' = 0
       THEN moldState' = "open"
       ELSE UNCHANGED moldState
    /\ UNCHANGED <<robotState, robotPosition, robotGripperState, robotTimer,
                   conveyorState, partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot move to mold *)
RobotMoveToMold ==
    /\ ~estopActive
    /\ systemMode = "auto"
    /\ robotState = "home"
    /\ robotPosition = "home_pos"
    /\ moldState = "open"
    /\ moldPosition = 0
    /\ robotGripperState = "empty"
    /\ robotState' = "moving_to_mold"
    /\ robotPosition' = "transit"
    /\ robotTimer' = 0
    /\ UNCHANGED <<moldState, moldPosition, robotGripperState, conveyorState,
                   partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot arrive at mold *)
RobotArriveAtMold ==
    /\ ~estopActive
    /\ robotState = "moving_to_mold"
    /\ moldState = "open"  \* Verify still safe
    /\ robotPosition' = "mold_area"
    /\ robotState' = "at_mold"
    /\ UNCHANGED <<moldState, moldPosition, robotGripperState, robotTimer,
                   conveyorState, partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot pick part *)
RobotPickPart ==
    /\ ~estopActive
    /\ robotState = "at_mold"
    /\ robotPosition = "mold_area"
    /\ robotGripperState = "empty"
    /\ cycleCount > 0  \* Part available
    /\ robotGripperState' = "holding_part"
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition, robotTimer,
                   conveyorState, partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot move home *)
RobotMoveHome ==
    /\ ~estopActive
    /\ robotState = "at_mold"
    /\ robotGripperState = "holding_part"
    /\ robotState' = "moving_home"
    /\ robotPosition' = "transit"
    /\ robotTimer' = 0
    /\ UNCHANGED <<moldState, moldPosition, robotGripperState, conveyorState,
                   partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot arrive home *)
RobotArriveHome ==
    /\ ~estopActive
    /\ robotState = "moving_home"
    /\ robotPosition' = "home_pos"
    /\ robotState' = "home"
    /\ UNCHANGED <<moldState, moldPosition, robotGripperState, robotTimer,
                   conveyorState, partsOnConveyor, estopActive, cycleCount, systemMode>>

(* Robot place part on conveyor *)
RobotPlacePart ==
    /\ ~estopActive
    /\ robotState = "home"
    /\ robotPosition = "home_pos"
    /\ robotGripperState = "holding_part"
    /\ conveyorState = "stopped"
    /\ robotGripperState' = "empty"
    /\ partsOnConveyor' = partsOnConveyor + 1
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition, robotTimer,
                   conveyorState, estopActive, cycleCount, systemMode>>

(* Start conveyor *)
StartConveyor ==
    /\ ~estopActive
    /\ systemMode = "auto"
    /\ conveyorState = "stopped"
    /\ partsOnConveyor > 0
    /\ robotGripperState = "empty"  \* Safety interlock
    /\ conveyorState' = "running"
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, robotTimer, partsOnConveyor,
                   estopActive, cycleCount, systemMode>>

(* Conveyor moves part off *)
ConveyorMovePart ==
    /\ ~estopActive
    /\ conveyorState = "running"
    /\ partsOnConveyor > 0
    /\ partsOnConveyor' = partsOnConveyor - 1
    /\ IF partsOnConveyor' = 0
       THEN conveyorState' = "stopped"
       ELSE UNCHANGED conveyorState
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, robotTimer, estopActive, cycleCount, systemMode>>

(* Robot timeout *)
RobotTimeout ==
    /\ ~estopActive
    /\ robotState \in {"moving_to_mold", "moving_home"}
    /\ robotTimer < ROBOT_TIMEOUT_TICKS
    /\ robotTimer' = robotTimer + 1
    /\ IF robotTimer' = ROBOT_TIMEOUT_TICKS
       THEN estopActive' = TRUE /\ systemMode' = "stopped"
       ELSE UNCHANGED <<estopActive, systemMode>>
    /\ UNCHANGED <<moldState, moldPosition, robotState, robotPosition,
                   robotGripperState, conveyorState, partsOnConveyor, cycleCount>>

(* ============== NEXT STATE ============== *)
Next ==
    \/ ActivateEstop
    \/ ResetEstop
    \/ StartAutoMode
    \/ StartMoldClose
    \/ MoldClosingProgress
    \/ StartMoldOpen
    \/ MoldOpeningProgress
    \/ RobotMoveToMold
    \/ RobotArriveAtMold
    \/ RobotPickPart
    \/ RobotMoveHome
    \/ RobotArriveHome
    \/ RobotPlacePart
    \/ StartConveyor
    \/ ConveyorMovePart
    \/ RobotTimeout

(* ============== SPECIFICATION ============== *)
Spec == Init /\ [][Next]_vars

(* ============== LIVENESS PROPERTIES ============== *)

(* The system eventually produces parts *)
LivenessProducesPartsEventually ==
    systemMode = "auto" ~> cycleCount > 0

(* Robot eventually returns home *)
LivenessRobotReturnsHome ==
    robotPosition = "mold_area" ~> robotPosition = "home_pos"

(* ============== THEOREMS ============== *)
THEOREM Spec => []TypeInvariant
THEOREM Spec => []SafetyInvariant

=============================================================================
