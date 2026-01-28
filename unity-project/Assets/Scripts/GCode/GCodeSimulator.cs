using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;

namespace CNCDigitalTwin.GCode
{
    /// <summary>
    /// G-Code Simulator and Verifier
    /// Parses, simulates, and validates CNC programs before execution
    /// Supports ISO 6983 (G-code) and Fanuc/Haas/Siemens dialects
    /// </summary>
    public class GCodeSimulator : MonoBehaviour
    {
        public static GCodeSimulator Instance { get; private set; }

        [Header("Machine Configuration")]
        [SerializeField] private MachineType machineType = MachineType.Mill_3Axis;
        [SerializeField] private ControllerDialect dialect = ControllerDialect.Fanuc;
        [SerializeField] private Vector3 workEnvelopeMin = new Vector3(-500, -500, -200);
        [SerializeField] private Vector3 workEnvelopeMax = new Vector3(500, 500, 200);
        [SerializeField] private float maxSpindleSpeed = 24000f; // RPM
        [SerializeField] private float maxFeedRate = 15000f; // mm/min

        [Header("Simulation Settings")]
        [SerializeField] private float simulationSpeed = 1f;
        [SerializeField] private bool enableCollisionDetection = true;
        [SerializeField] private bool enableToolpathRendering = true;
        [SerializeField] private float toolpathLineWidth = 0.5f;

        // Events
        public event Action<GCodeProgram> OnProgramLoaded;
        public event Action<GCodeBlock, SimulationState> OnBlockExecuting;
        public event Action<GCodeBlock> OnBlockCompleted;
        public event Action<SimulationState> OnSimulationStateChanged;
        public event Action<List<GCodeError>> OnVerificationComplete;
        public event Action<CollisionEvent> OnCollisionDetected;

        // Program state
        private GCodeProgram currentProgram;
        private SimulationState simulationState = new SimulationState();
        private MachineState machineState = new MachineState();
        private List<GCodeError> verificationErrors = new List<GCodeError>();

        // Toolpath visualization
        private List<ToolpathSegment> toolpath = new List<ToolpathSegment>();
        private LineRenderer toolpathRenderer;

        // Modal groups
        private Dictionary<int, string> modalGroupState = new Dictionary<int, string>();

        // Statistics
        private SimulationStats stats = new SimulationStats();

        #region Data Structures

        public enum MachineType
        {
            Mill_3Axis,
            Mill_4Axis,
            Mill_5Axis,
            Lathe_2Axis,
            Lathe_CY,
            Lathe_Turret,
            Router_3Axis,
            WireEDM,
            Laser,
            Waterjet,
            Plasma
        }

        public enum ControllerDialect
        {
            Fanuc,
            Haas,
            Siemens,
            Mazak,
            Okuma,
            Heidenhain,
            LinuxCNC,
            Mach3,
            Grbl
        }

        public enum MotionMode
        {
            G0_Rapid,
            G1_Linear,
            G2_CW_Arc,
            G3_CCW_Arc,
            G5_NURBS,
            G33_Threading
        }

        public enum PlaneSelect
        {
            G17_XY,
            G18_XZ,
            G19_YZ
        }

        public enum DistanceMode
        {
            G90_Absolute,
            G91_Incremental
        }

        public enum FeedMode
        {
            G94_UnitsPerMinute,
            G95_UnitsPerRev
        }

        public enum UnitMode
        {
            G20_Inch,
            G21_Metric
        }

        public enum WorkOffset
        {
            G54, G55, G56, G57, G58, G59
        }

        public enum ErrorSeverity
        {
            Warning,
            Error,
            Critical
        }

        public class GCodeProgram
        {
            public string ProgramNumber { get; set; }
            public string Name { get; set; }
            public List<GCodeBlock> Blocks { get; set; } = new List<GCodeBlock>();
            public Dictionary<string, object> Variables { get; set; } = new Dictionary<string, object>();
            public List<Subprogram> Subprograms { get; set; } = new List<Subprogram>();
            public string RawCode { get; set; }
            public DateTime ParsedTime { get; set; }
        }

        public class GCodeBlock
        {
            public int LineNumber { get; set; }
            public int? NNumber { get; set; }
            public List<GCodeWord> Words { get; set; } = new List<GCodeWord>();
            public string Comment { get; set; }
            public string RawLine { get; set; }
            public bool IsComment { get; set; }
            public float EstimatedTime { get; set; } // seconds
            public float DistanceMoved { get; set; } // mm
        }

        public class GCodeWord
        {
            public char Letter { get; set; }
            public float Value { get; set; }
            public string Expression { get; set; } // For parametric programming
            public bool IsExpression => !string.IsNullOrEmpty(Expression);
        }

        public class Subprogram
        {
            public int Number { get; set; }
            public string Name { get; set; }
            public List<GCodeBlock> Blocks { get; set; } = new List<GCodeBlock>();
        }

        public class MachineState
        {
            // Position
            public Vector3 Position { get; set; } = Vector3.zero;
            public Vector3 MachinePosition { get; set; } = Vector3.zero;
            public float AAxis { get; set; }
            public float BAxis { get; set; }
            public float CAxis { get; set; }

            // Spindle
            public float SpindleSpeed { get; set; }
            public bool SpindleOn { get; set; }
            public bool SpindleCW { get; set; }

            // Feed
            public float FeedRate { get; set; }
            public FeedMode FeedMode { get; set; } = FeedMode.G94_UnitsPerMinute;

            // Modal states
            public MotionMode MotionMode { get; set; } = MotionMode.G0_Rapid;
            public PlaneSelect Plane { get; set; } = PlaneSelect.G17_XY;
            public DistanceMode DistanceMode { get; set; } = DistanceMode.G90_Absolute;
            public UnitMode Units { get; set; } = UnitMode.G21_Metric;
            public WorkOffset WorkOffset { get; set; } = WorkOffset.G54;

            // Tool
            public int CurrentTool { get; set; }
            public float ToolLengthOffset { get; set; }
            public float ToolRadiusOffset { get; set; }
            public int ToolLengthCompNumber { get; set; }
            public int CutterCompNumber { get; set; }
            public bool CutterCompLeft { get; set; }
            public bool CutterCompRight { get; set; }

            // Coolant
            public bool CoolantFlood { get; set; }
            public bool CoolantMist { get; set; }
            public bool CoolantThrough { get; set; }

            // Canned cycles
            public bool InCannedCycle { get; set; }
            public int CannedCycleType { get; set; }
            public float CannedCycleR { get; set; }
            public float CannedCycleZ { get; set; }
            public float CannedCycleQ { get; set; }
            public float CannedCycleP { get; set; }
        }

        public class SimulationState
        {
            public bool IsRunning { get; set; }
            public bool IsPaused { get; set; }
            public int CurrentBlockIndex { get; set; }
            public float ElapsedTime { get; set; }
            public float TotalEstimatedTime { get; set; }
            public float TotalDistance { get; set; }
            public float ProgressPercent { get; set; }
            public Vector3 CurrentPosition { get; set; }
            public float CurrentFeedRate { get; set; }
            public float CurrentSpindleSpeed { get; set; }
        }

        public class ToolpathSegment
        {
            public Vector3 StartPoint { get; set; }
            public Vector3 EndPoint { get; set; }
            public MotionMode MotionType { get; set; }
            public float FeedRate { get; set; }
            public int ToolNumber { get; set; }
            public Color Color { get; set; }
            public bool IsCuttingMove { get; set; }
        }

        public class GCodeError
        {
            public int LineNumber { get; set; }
            public string Code { get; set; }
            public string Message { get; set; }
            public ErrorSeverity Severity { get; set; }
            public string Suggestion { get; set; }
        }

        public class CollisionEvent
        {
            public Vector3 Position { get; set; }
            public string ObjectA { get; set; }
            public string ObjectB { get; set; }
            public int BlockNumber { get; set; }
            public string GCodeLine { get; set; }
        }

        public class ToolDefinition
        {
            public int ToolNumber { get; set; }
            public string Description { get; set; }
            public float Diameter { get; set; }
            public float Length { get; set; }
            public float CornerRadius { get; set; }
            public int NumberOfFlutes { get; set; }
            public float MaxSpindleSpeed { get; set; }
            public float MaxFeedPerTooth { get; set; }
        }

        public class SimulationStats
        {
            public int TotalBlocks { get; set; }
            public int ExecutedBlocks { get; set; }
            public float TotalCuttingTime { get; set; }
            public float TotalRapidTime { get; set; }
            public float TotalCuttingDistance { get; set; }
            public float TotalRapidDistance { get; set; }
            public int ToolChanges { get; set; }
            public float MaterialRemoved { get; set; }
            public Dictionary<int, float> ToolUsage { get; set; } = new Dictionary<int, float>();
        }

        #endregion

        #region Initialization

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeModalGroups();
        }

        private void Start()
        {
            InitializeToolpathRenderer();
            Debug.Log("[GCodeSimulator] Initialized for " + machineType + " with " + dialect + " dialect");
        }

        private void InitializeModalGroups()
        {
            // ISO 6983 modal groups
            modalGroupState[1] = "G0";   // Motion
            modalGroupState[2] = "G17";  // Plane select
            modalGroupState[3] = "G90";  // Distance mode
            modalGroupState[5] = "G94";  // Feed mode
            modalGroupState[6] = "G21";  // Units
            modalGroupState[7] = "G40";  // Cutter comp
            modalGroupState[8] = "G43";  // Tool length comp
            modalGroupState[10] = "G98"; // Return mode
            modalGroupState[12] = "G54"; // Work offset
        }

        private void InitializeToolpathRenderer()
        {
            if (enableToolpathRendering)
            {
                var go = new GameObject("ToolpathRenderer");
                go.transform.SetParent(transform);
                toolpathRenderer = go.AddComponent<LineRenderer>();
                toolpathRenderer.material = new Material(Shader.Find("Sprites/Default"));
                toolpathRenderer.startWidth = toolpathLineWidth;
                toolpathRenderer.endWidth = toolpathLineWidth;
                toolpathRenderer.positionCount = 0;
            }
        }

        #endregion

        #region Parsing

        public GCodeProgram ParseProgram(string gcode)
        {
            currentProgram = new GCodeProgram
            {
                RawCode = gcode,
                ParsedTime = DateTime.Now
            };

            verificationErrors.Clear();
            toolpath.Clear();

            string[] lines = gcode.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i].Trim();
                if (string.IsNullOrEmpty(line)) continue;

                var block = ParseBlock(line, i + 1);
                if (block != null)
                {
                    currentProgram.Blocks.Add(block);
                }
            }

            // Extract program number if present
            var firstBlock = currentProgram.Blocks.FirstOrDefault();
            if (firstBlock != null)
            {
                var oWord = firstBlock.Words.FirstOrDefault(w => w.Letter == 'O');
                if (oWord != null)
                {
                    currentProgram.ProgramNumber = "O" + ((int)oWord.Value).ToString("D4");
                }
            }

            stats.TotalBlocks = currentProgram.Blocks.Count;
            Debug.Log($"[GCodeSimulator] Parsed {currentProgram.Blocks.Count} blocks");

            OnProgramLoaded?.Invoke(currentProgram);
            return currentProgram;
        }

        private GCodeBlock ParseBlock(string line, int lineNumber)
        {
            var block = new GCodeBlock
            {
                LineNumber = lineNumber,
                RawLine = line
            };

            // Check for pure comment
            if (line.StartsWith("(") || line.StartsWith(";"))
            {
                block.IsComment = true;
                block.Comment = line.TrimStart('(', ';').TrimEnd(')');
                return block;
            }

            // Extract inline comment
            int commentStart = line.IndexOf('(');
            if (commentStart >= 0)
            {
                int commentEnd = line.IndexOf(')', commentStart);
                if (commentEnd > commentStart)
                {
                    block.Comment = line.Substring(commentStart + 1, commentEnd - commentStart - 1);
                    line = line.Substring(0, commentStart) + line.Substring(commentEnd + 1);
                }
            }

            // Also handle semicolon comments
            int semicolonPos = line.IndexOf(';');
            if (semicolonPos >= 0)
            {
                if (string.IsNullOrEmpty(block.Comment))
                    block.Comment = line.Substring(semicolonPos + 1).Trim();
                line = line.Substring(0, semicolonPos);
            }

            // Parse words using regex
            line = line.Replace(" ", "").ToUpper();
            var wordPattern = new Regex(@"([A-Z])(-?\d*\.?\d+|\[.+?\]|#\d+)");
            var matches = wordPattern.Matches(line);

            foreach (Match match in matches)
            {
                char letter = match.Groups[1].Value[0];
                string valueStr = match.Groups[2].Value;

                var word = new GCodeWord { Letter = letter };

                // Check for expression or variable
                if (valueStr.StartsWith("[") || valueStr.StartsWith("#"))
                {
                    word.Expression = valueStr;
                    word.Value = 0; // Will be evaluated at runtime
                }
                else
                {
                    if (float.TryParse(valueStr, out float value))
                        word.Value = value;
                }

                if (letter == 'N')
                    block.NNumber = (int)word.Value;

                block.Words.Add(word);
            }

            return block;
        }

        #endregion

        #region Verification

        public List<GCodeError> VerifyProgram(GCodeProgram program = null)
        {
            program = program ?? currentProgram;
            if (program == null)
            {
                Debug.LogError("[GCodeSimulator] No program to verify");
                return new List<GCodeError>();
            }

            verificationErrors.Clear();

            // Reset machine state for verification
            var verifyState = new MachineState();

            foreach (var block in program.Blocks)
            {
                if (block.IsComment) continue;

                VerifyBlock(block, verifyState);
            }

            // Calculate totals
            CalculateProgramStats(program);

            OnVerificationComplete?.Invoke(verificationErrors);
            Debug.Log($"[GCodeSimulator] Verification complete: {verificationErrors.Count(e => e.Severity == ErrorSeverity.Error)} errors, " +
                      $"{verificationErrors.Count(e => e.Severity == ErrorSeverity.Warning)} warnings");

            return verificationErrors;
        }

        private void VerifyBlock(GCodeBlock block, MachineState state)
        {
            Vector3 targetPos = state.Position;
            bool hasMotion = false;

            foreach (var word in block.Words)
            {
                switch (word.Letter)
                {
                    case 'G':
                        VerifyGCode(block, word, state);
                        break;

                    case 'M':
                        VerifyMCode(block, word, state);
                        break;

                    case 'X':
                        targetPos.x = state.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : state.Position.x + word.Value;
                        hasMotion = true;
                        break;

                    case 'Y':
                        targetPos.y = state.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : state.Position.y + word.Value;
                        hasMotion = true;
                        break;

                    case 'Z':
                        targetPos.z = state.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : state.Position.z + word.Value;
                        hasMotion = true;
                        break;

                    case 'F':
                        if (word.Value <= 0)
                            AddError(block, "E002", "Feed rate must be positive", ErrorSeverity.Error);
                        else if (word.Value > maxFeedRate)
                            AddError(block, "W001", $"Feed rate {word.Value} exceeds max {maxFeedRate}", ErrorSeverity.Warning);
                        state.FeedRate = word.Value;
                        break;

                    case 'S':
                        if (word.Value < 0)
                            AddError(block, "E003", "Spindle speed must be positive", ErrorSeverity.Error);
                        else if (word.Value > maxSpindleSpeed)
                            AddError(block, "W002", $"Spindle speed {word.Value} exceeds max {maxSpindleSpeed}", ErrorSeverity.Warning);
                        state.SpindleSpeed = word.Value;
                        break;

                    case 'T':
                        state.CurrentTool = (int)word.Value;
                        break;
                }
            }

            // Check motion
            if (hasMotion)
            {
                // Check travel limits
                if (!IsWithinEnvelope(targetPos))
                {
                    AddError(block, "E010", $"Position {targetPos} exceeds work envelope", ErrorSeverity.Error);
                }

                // Check for feed rate on cutting moves
                if (state.MotionMode != MotionMode.G0_Rapid && state.FeedRate <= 0)
                {
                    AddError(block, "E011", "Feed rate not specified for cutting move", ErrorSeverity.Error);
                }

                // Calculate distance and time
                float distance = Vector3.Distance(state.Position, targetPos);
                block.DistanceMoved = distance;

                if (state.MotionMode == MotionMode.G0_Rapid)
                    block.EstimatedTime = distance / maxFeedRate * 60f;
                else
                    block.EstimatedTime = distance / Mathf.Max(state.FeedRate, 1f) * 60f;

                // Add to toolpath
                toolpath.Add(new ToolpathSegment
                {
                    StartPoint = state.Position,
                    EndPoint = targetPos,
                    MotionType = state.MotionMode,
                    FeedRate = state.FeedRate,
                    ToolNumber = state.CurrentTool,
                    IsCuttingMove = state.MotionMode != MotionMode.G0_Rapid,
                    Color = state.MotionMode == MotionMode.G0_Rapid ? Color.yellow : Color.blue
                });

                state.Position = targetPos;
            }
        }

        private void VerifyGCode(GCodeBlock block, GCodeWord word, MachineState state)
        {
            int code = (int)word.Value;
            int decimal_part = (int)((word.Value - code) * 10);

            switch (code)
            {
                case 0:
                    state.MotionMode = MotionMode.G0_Rapid;
                    break;
                case 1:
                    state.MotionMode = MotionMode.G1_Linear;
                    break;
                case 2:
                    state.MotionMode = MotionMode.G2_CW_Arc;
                    break;
                case 3:
                    state.MotionMode = MotionMode.G3_CCW_Arc;
                    break;
                case 4:
                    // Dwell - requires P word
                    if (!block.Words.Any(w => w.Letter == 'P'))
                        AddError(block, "W003", "G4 dwell requires P parameter", ErrorSeverity.Warning);
                    break;
                case 17:
                    state.Plane = PlaneSelect.G17_XY;
                    break;
                case 18:
                    state.Plane = PlaneSelect.G18_XZ;
                    break;
                case 19:
                    state.Plane = PlaneSelect.G19_YZ;
                    break;
                case 20:
                    state.Units = UnitMode.G20_Inch;
                    break;
                case 21:
                    state.Units = UnitMode.G21_Metric;
                    break;
                case 28:
                    // Home - valid
                    break;
                case 40:
                    state.CutterCompLeft = false;
                    state.CutterCompRight = false;
                    break;
                case 41:
                    state.CutterCompLeft = true;
                    break;
                case 42:
                    state.CutterCompRight = true;
                    break;
                case 43:
                    // Tool length comp - requires H word
                    var hWord = block.Words.FirstOrDefault(w => w.Letter == 'H');
                    if (hWord != null)
                        state.ToolLengthCompNumber = (int)hWord.Value;
                    break;
                case 49:
                    state.ToolLengthCompNumber = 0;
                    break;
                case 54:
                case 55:
                case 56:
                case 57:
                case 58:
                case 59:
                    state.WorkOffset = (WorkOffset)Enum.Parse(typeof(WorkOffset), $"G{code}");
                    break;
                case 80:
                    state.InCannedCycle = false;
                    break;
                case 81:
                case 82:
                case 83:
                case 84:
                case 85:
                case 86:
                case 87:
                case 88:
                case 89:
                    state.InCannedCycle = true;
                    state.CannedCycleType = code;
                    VerifyCannedCycle(block, code, state);
                    break;
                case 90:
                    if (decimal_part == 1)
                        state.DistanceMode = DistanceMode.G91_Incremental; // G90.1 arc incremental
                    else
                        state.DistanceMode = DistanceMode.G90_Absolute;
                    break;
                case 91:
                    state.DistanceMode = DistanceMode.G91_Incremental;
                    break;
                case 94:
                    state.FeedMode = FeedMode.G94_UnitsPerMinute;
                    break;
                case 95:
                    state.FeedMode = FeedMode.G95_UnitsPerRev;
                    break;
                case 98:
                case 99:
                    // Canned cycle return mode - valid
                    break;
                default:
                    if (!IsValidGCode(code, decimal_part))
                        AddError(block, "W004", $"Unrecognized G-code G{word.Value}", ErrorSeverity.Warning);
                    break;
            }
        }

        private void VerifyMCode(GCodeBlock block, GCodeWord word, MachineState state)
        {
            int code = (int)word.Value;

            switch (code)
            {
                case 0:
                    // Program stop
                    break;
                case 1:
                    // Optional stop
                    break;
                case 2:
                case 30:
                    // Program end
                    break;
                case 3:
                    state.SpindleOn = true;
                    state.SpindleCW = true;
                    if (state.SpindleSpeed <= 0)
                        AddError(block, "W005", "M3 spindle start without speed specified", ErrorSeverity.Warning);
                    break;
                case 4:
                    state.SpindleOn = true;
                    state.SpindleCW = false;
                    if (state.SpindleSpeed <= 0)
                        AddError(block, "W005", "M4 spindle start without speed specified", ErrorSeverity.Warning);
                    break;
                case 5:
                    state.SpindleOn = false;
                    break;
                case 6:
                    // Tool change
                    stats.ToolChanges++;
                    break;
                case 7:
                    state.CoolantMist = true;
                    break;
                case 8:
                    state.CoolantFlood = true;
                    break;
                case 9:
                    state.CoolantFlood = false;
                    state.CoolantMist = false;
                    state.CoolantThrough = false;
                    break;
                case 19:
                    // Spindle orient
                    break;
                case 98:
                case 99:
                    // Subprogram call/return
                    break;
                default:
                    if (!IsValidMCode(code))
                        AddError(block, "W006", $"Unrecognized M-code M{code}", ErrorSeverity.Warning);
                    break;
            }
        }

        private void VerifyCannedCycle(GCodeBlock block, int cycleCode, MachineState state)
        {
            // Check for required parameters
            bool hasZ = block.Words.Any(w => w.Letter == 'Z');
            bool hasR = block.Words.Any(w => w.Letter == 'R');

            if (!hasZ)
                AddError(block, "E020", $"G{cycleCode} requires Z depth", ErrorSeverity.Error);
            if (!hasR)
                AddError(block, "E021", $"G{cycleCode} requires R retract plane", ErrorSeverity.Error);

            // Peck drilling needs Q
            if (cycleCode == 83 && !block.Words.Any(w => w.Letter == 'Q'))
                AddError(block, "W020", "G83 peck drill without Q peck depth", ErrorSeverity.Warning);

            // Tapping needs spindle speed
            if (cycleCode == 84 && state.SpindleSpeed <= 0)
                AddError(block, "E022", "G84 tapping requires spindle speed", ErrorSeverity.Error);
        }

        private bool IsValidGCode(int code, int decimal_part)
        {
            // Common valid G-codes (dialect-specific codes handled elsewhere)
            int[] validCodes = { 0, 1, 2, 3, 4, 5, 10, 17, 18, 19, 20, 21, 28, 30, 40, 41, 42, 43, 44, 49,
                                 52, 53, 54, 55, 56, 57, 58, 59, 61, 64, 65, 68, 69, 73, 74, 76,
                                 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99 };
            return validCodes.Contains(code);
        }

        private bool IsValidMCode(int code)
        {
            int[] validCodes = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 19, 30, 48, 49, 98, 99 };
            return validCodes.Contains(code);
        }

        private bool IsWithinEnvelope(Vector3 pos)
        {
            return pos.x >= workEnvelopeMin.x && pos.x <= workEnvelopeMax.x &&
                   pos.y >= workEnvelopeMin.y && pos.y <= workEnvelopeMax.y &&
                   pos.z >= workEnvelopeMin.z && pos.z <= workEnvelopeMax.z;
        }

        private void AddError(GCodeBlock block, string code, string message, ErrorSeverity severity)
        {
            verificationErrors.Add(new GCodeError
            {
                LineNumber = block.LineNumber,
                Code = code,
                Message = message,
                Severity = severity
            });
        }

        private void CalculateProgramStats(GCodeProgram program)
        {
            stats.TotalCuttingTime = 0;
            stats.TotalRapidTime = 0;
            stats.TotalCuttingDistance = 0;
            stats.TotalRapidDistance = 0;

            foreach (var segment in toolpath)
            {
                float dist = Vector3.Distance(segment.StartPoint, segment.EndPoint);
                if (segment.IsCuttingMove)
                {
                    stats.TotalCuttingDistance += dist;
                    stats.TotalCuttingTime += dist / Mathf.Max(segment.FeedRate, 1f) * 60f;
                }
                else
                {
                    stats.TotalRapidDistance += dist;
                    stats.TotalRapidTime += dist / maxFeedRate * 60f;
                }

                // Track tool usage
                if (!stats.ToolUsage.ContainsKey(segment.ToolNumber))
                    stats.ToolUsage[segment.ToolNumber] = 0;
                if (segment.IsCuttingMove)
                    stats.ToolUsage[segment.ToolNumber] += dist;
            }

            simulationState.TotalEstimatedTime = stats.TotalCuttingTime + stats.TotalRapidTime;
            simulationState.TotalDistance = stats.TotalCuttingDistance + stats.TotalRapidDistance;
        }

        #endregion

        #region Simulation

        public void StartSimulation()
        {
            if (currentProgram == null || currentProgram.Blocks.Count == 0)
            {
                Debug.LogError("[GCodeSimulator] No program loaded");
                return;
            }

            simulationState.IsRunning = true;
            simulationState.IsPaused = false;
            simulationState.CurrentBlockIndex = 0;
            simulationState.ElapsedTime = 0;

            // Reset machine state
            machineState = new MachineState();

            StartCoroutine(RunSimulation());
            Debug.Log("[GCodeSimulator] Simulation started");
        }

        public void PauseSimulation()
        {
            simulationState.IsPaused = true;
            Debug.Log("[GCodeSimulator] Simulation paused");
        }

        public void ResumeSimulation()
        {
            simulationState.IsPaused = false;
            Debug.Log("[GCodeSimulator] Simulation resumed");
        }

        public void StopSimulation()
        {
            simulationState.IsRunning = false;
            simulationState.IsPaused = false;
            StopAllCoroutines();
            Debug.Log("[GCodeSimulator] Simulation stopped");
        }

        private IEnumerator RunSimulation()
        {
            while (simulationState.IsRunning && simulationState.CurrentBlockIndex < currentProgram.Blocks.Count)
            {
                if (simulationState.IsPaused)
                {
                    yield return new WaitForSeconds(0.1f);
                    continue;
                }

                var block = currentProgram.Blocks[simulationState.CurrentBlockIndex];
                if (!block.IsComment)
                {
                    OnBlockExecuting?.Invoke(block, simulationState);

                    // Execute block
                    yield return StartCoroutine(ExecuteBlock(block));

                    OnBlockCompleted?.Invoke(block);
                }

                simulationState.CurrentBlockIndex++;
                simulationState.ProgressPercent = (float)simulationState.CurrentBlockIndex / currentProgram.Blocks.Count * 100f;
                stats.ExecutedBlocks++;

                OnSimulationStateChanged?.Invoke(simulationState);
            }

            simulationState.IsRunning = false;
            Debug.Log("[GCodeSimulator] Simulation complete");
        }

        private IEnumerator ExecuteBlock(GCodeBlock block)
        {
            Vector3 targetPos = machineState.Position;
            bool hasMotion = false;

            // Process words
            foreach (var word in block.Words)
            {
                switch (word.Letter)
                {
                    case 'G':
                        ProcessGCodeForSim(word);
                        break;
                    case 'M':
                        ProcessMCodeForSim(word);
                        break;
                    case 'X':
                        targetPos.x = machineState.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : machineState.Position.x + word.Value;
                        hasMotion = true;
                        break;
                    case 'Y':
                        targetPos.y = machineState.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : machineState.Position.y + word.Value;
                        hasMotion = true;
                        break;
                    case 'Z':
                        targetPos.z = machineState.DistanceMode == DistanceMode.G90_Absolute ?
                            word.Value : machineState.Position.z + word.Value;
                        hasMotion = true;
                        break;
                    case 'F':
                        machineState.FeedRate = word.Value;
                        break;
                    case 'S':
                        machineState.SpindleSpeed = word.Value;
                        break;
                }
            }

            // Execute motion
            if (hasMotion)
            {
                float moveTime = block.EstimatedTime / simulationSpeed;
                float elapsed = 0;
                Vector3 startPos = machineState.Position;

                // Check collision before moving
                if (enableCollisionDetection)
                {
                    CheckCollision(startPos, targetPos, block);
                }

                while (elapsed < moveTime)
                {
                    if (simulationState.IsPaused)
                    {
                        yield return null;
                        continue;
                    }

                    elapsed += Time.deltaTime;
                    float t = Mathf.Clamp01(elapsed / moveTime);

                    machineState.Position = Vector3.Lerp(startPos, targetPos, t);
                    simulationState.CurrentPosition = machineState.Position;
                    simulationState.ElapsedTime += Time.deltaTime * simulationSpeed;

                    yield return null;
                }

                machineState.Position = targetPos;
            }

            simulationState.CurrentFeedRate = machineState.FeedRate;
            simulationState.CurrentSpindleSpeed = machineState.SpindleSpeed;
        }

        private void ProcessGCodeForSim(GCodeWord word)
        {
            int code = (int)word.Value;
            switch (code)
            {
                case 0: machineState.MotionMode = MotionMode.G0_Rapid; break;
                case 1: machineState.MotionMode = MotionMode.G1_Linear; break;
                case 2: machineState.MotionMode = MotionMode.G2_CW_Arc; break;
                case 3: machineState.MotionMode = MotionMode.G3_CCW_Arc; break;
                case 17: machineState.Plane = PlaneSelect.G17_XY; break;
                case 18: machineState.Plane = PlaneSelect.G18_XZ; break;
                case 19: machineState.Plane = PlaneSelect.G19_YZ; break;
                case 90: machineState.DistanceMode = DistanceMode.G90_Absolute; break;
                case 91: machineState.DistanceMode = DistanceMode.G91_Incremental; break;
            }
        }

        private void ProcessMCodeForSim(GCodeWord word)
        {
            int code = (int)word.Value;
            switch (code)
            {
                case 3: machineState.SpindleOn = true; machineState.SpindleCW = true; break;
                case 4: machineState.SpindleOn = true; machineState.SpindleCW = false; break;
                case 5: machineState.SpindleOn = false; break;
                case 8: machineState.CoolantFlood = true; break;
                case 9: machineState.CoolantFlood = false; machineState.CoolantMist = false; break;
            }
        }

        private void CheckCollision(Vector3 start, Vector3 end, GCodeBlock block)
        {
            // Raycast for collision detection
            Vector3 direction = end - start;
            float distance = direction.magnitude;

            if (Physics.Raycast(start, direction.normalized, out RaycastHit hit, distance))
            {
                var collision = new CollisionEvent
                {
                    Position = hit.point,
                    ObjectA = "Tool",
                    ObjectB = hit.collider.gameObject.name,
                    BlockNumber = block.LineNumber,
                    GCodeLine = block.RawLine
                };

                OnCollisionDetected?.Invoke(collision);
                Debug.LogWarning($"[GCodeSimulator] COLLISION at line {block.LineNumber}: Tool -> {hit.collider.gameObject.name}");
            }
        }

        #endregion

        #region Toolpath Visualization

        public void RenderToolpath()
        {
            if (!enableToolpathRendering || toolpathRenderer == null || toolpath.Count == 0)
                return;

            var points = new List<Vector3>();
            foreach (var segment in toolpath)
            {
                if (points.Count == 0 || points.Last() != segment.StartPoint)
                    points.Add(segment.StartPoint);
                points.Add(segment.EndPoint);
            }

            toolpathRenderer.positionCount = points.Count;
            toolpathRenderer.SetPositions(points.ToArray());

            // Color gradient based on feed rate
            var gradient = new Gradient();
            var colorKeys = new GradientColorKey[]
            {
                new GradientColorKey(Color.yellow, 0f),
                new GradientColorKey(Color.blue, 0.5f),
                new GradientColorKey(Color.red, 1f)
            };
            gradient.colorKeys = colorKeys;
            toolpathRenderer.colorGradient = gradient;
        }

        public void ClearToolpath()
        {
            toolpath.Clear();
            if (toolpathRenderer != null)
                toolpathRenderer.positionCount = 0;
        }

        #endregion

        #region Public API

        public GCodeProgram GetCurrentProgram() => currentProgram;
        public SimulationState GetSimulationState() => simulationState;
        public MachineState GetMachineState() => machineState;
        public List<GCodeError> GetErrors() => verificationErrors;
        public List<ToolpathSegment> GetToolpath() => toolpath;
        public SimulationStats GetStats() => stats;

        public void SetMachineEnvelope(Vector3 min, Vector3 max)
        {
            workEnvelopeMin = min;
            workEnvelopeMax = max;
        }

        public void SetSimulationSpeed(float speed)
        {
            simulationSpeed = Mathf.Max(0.1f, speed);
        }

        public GCodeBlock GetBlockAtLine(int lineNumber)
        {
            return currentProgram?.Blocks.FirstOrDefault(b => b.LineNumber == lineNumber);
        }

        public string GenerateReport()
        {
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("=== G-Code Verification Report ===");
            sb.AppendLine($"Program: {currentProgram?.ProgramNumber ?? "N/A"}");
            sb.AppendLine($"Total Blocks: {stats.TotalBlocks}");
            sb.AppendLine($"Total Distance: {stats.TotalCuttingDistance + stats.TotalRapidDistance:F2} mm");
            sb.AppendLine($"Cutting Distance: {stats.TotalCuttingDistance:F2} mm");
            sb.AppendLine($"Rapid Distance: {stats.TotalRapidDistance:F2} mm");
            sb.AppendLine($"Estimated Time: {(stats.TotalCuttingTime + stats.TotalRapidTime) / 60f:F2} min");
            sb.AppendLine($"Tool Changes: {stats.ToolChanges}");
            sb.AppendLine();
            sb.AppendLine("--- Errors ---");
            foreach (var err in verificationErrors.Where(e => e.Severity == ErrorSeverity.Error))
            {
                sb.AppendLine($"Line {err.LineNumber}: [{err.Code}] {err.Message}");
            }
            sb.AppendLine();
            sb.AppendLine("--- Warnings ---");
            foreach (var warn in verificationErrors.Where(e => e.Severity == ErrorSeverity.Warning))
            {
                sb.AppendLine($"Line {warn.LineNumber}: [{warn.Code}] {warn.Message}");
            }

            return sb.ToString();
        }

        #endregion
    }
}
