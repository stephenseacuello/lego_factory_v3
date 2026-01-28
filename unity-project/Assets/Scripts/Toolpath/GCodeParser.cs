using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace CNCScada.Toolpath
{
    /// <summary>
    /// G-code parser for CNC toolpath visualization.
    /// Supports G0, G1, G2, G3, and common modal codes.
    /// </summary>
    public class GCodeParser
    {
        // Current machine state
        private Vector3 currentPosition = Vector3.zero;
        private float currentFeedRate = 1000f;
        private float currentSpindleSpeed = 0f;
        private bool absoluteMode = true;
        private bool metricUnits = true;
        private int currentPlane = 17; // G17 = XY plane

        // Parsed data
        private List<ToolpathSegment> segments = new List<ToolpathSegment>();
        private List<GCodeCommand> commands = new List<GCodeCommand>();

        // Events
        public event Action<ToolpathSegment> OnSegmentParsed;
        public event Action<float> OnProgressUpdated;

        /// <summary>
        /// Parse G-code string and return toolpath segments
        /// </summary>
        public List<ToolpathSegment> Parse(string gcode)
        {
            segments.Clear();
            commands.Clear();
            currentPosition = Vector3.zero;

            string[] lines = gcode.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
            int totalLines = lines.Length;

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i].Trim();

                // Skip empty lines and comments
                if (string.IsNullOrWhiteSpace(line) || line.StartsWith(";") || line.StartsWith("("))
                    continue;

                // Remove inline comments
                int commentIndex = line.IndexOf(';');
                if (commentIndex >= 0)
                    line = line.Substring(0, commentIndex).Trim();

                commentIndex = line.IndexOf('(');
                if (commentIndex >= 0)
                    line = line.Substring(0, commentIndex).Trim();

                if (string.IsNullOrWhiteSpace(line))
                    continue;

                ParseLine(line, i + 1);

                // Report progress
                OnProgressUpdated?.Invoke((float)(i + 1) / totalLines);
            }

            return segments;
        }

        /// <summary>
        /// Parse G-code from file
        /// </summary>
        public List<ToolpathSegment> ParseFile(string filePath)
        {
            try
            {
                string content = System.IO.File.ReadAllText(filePath);
                return Parse(content);
            }
            catch (Exception e)
            {
                Debug.LogError($"[GCodeParser] Error reading file: {e.Message}");
                return new List<ToolpathSegment>();
            }
        }

        private void ParseLine(string line, int lineNumber)
        {
            var command = new GCodeCommand
            {
                lineNumber = lineNumber,
                rawLine = line
            };

            // Parse all words in the line
            var words = ExtractWords(line);

            // Process G codes first (modal commands)
            foreach (var word in words)
            {
                if (word.letter == 'G')
                {
                    ProcessGCode(word.value, command);
                }
            }

            // Process coordinates
            foreach (var word in words)
            {
                switch (word.letter)
                {
                    case 'X': command.x = ConvertUnits(word.value); break;
                    case 'Y': command.y = ConvertUnits(word.value); break;
                    case 'Z': command.z = ConvertUnits(word.value); break;
                    case 'I': command.i = ConvertUnits(word.value); break;
                    case 'J': command.j = ConvertUnits(word.value); break;
                    case 'K': command.k = ConvertUnits(word.value); break;
                    case 'R': command.r = ConvertUnits(word.value); break;
                    case 'F': command.f = word.value; currentFeedRate = word.value; break;
                    case 'S': command.s = word.value; currentSpindleSpeed = word.value; break;
                }
            }

            // Process M codes
            foreach (var word in words)
            {
                if (word.letter == 'M')
                {
                    ProcessMCode((int)word.value, command);
                }
            }

            // Generate toolpath segment if this is a motion command
            if (command.motionType != MotionType.None)
            {
                CreateSegment(command);
            }

            commands.Add(command);
        }

        private List<(char letter, float value)> ExtractWords(string line)
        {
            var words = new List<(char, float)>();
            var matches = Regex.Matches(line.ToUpper(), @"([A-Z])(-?\d+\.?\d*)");

            foreach (Match match in matches)
            {
                char letter = match.Groups[1].Value[0];
                if (float.TryParse(match.Groups[2].Value, out float value))
                {
                    words.Add((letter, value));
                }
            }

            return words;
        }

        private void ProcessGCode(float code, GCodeCommand command)
        {
            int gCode = (int)code;

            switch (gCode)
            {
                case 0:  // Rapid move
                    command.motionType = MotionType.Rapid;
                    break;

                case 1:  // Linear move
                    command.motionType = MotionType.Linear;
                    break;

                case 2:  // Clockwise arc
                    command.motionType = MotionType.ArcCW;
                    break;

                case 3:  // Counter-clockwise arc
                    command.motionType = MotionType.ArcCCW;
                    break;

                case 17: // XY plane
                    currentPlane = 17;
                    break;

                case 18: // XZ plane
                    currentPlane = 18;
                    break;

                case 19: // YZ plane
                    currentPlane = 19;
                    break;

                case 20: // Inch mode
                    metricUnits = false;
                    break;

                case 21: // Metric mode
                    metricUnits = true;
                    break;

                case 28: // Home
                    command.motionType = MotionType.Rapid;
                    command.x = 0;
                    command.y = 0;
                    command.z = 0;
                    break;

                case 90: // Absolute mode
                    absoluteMode = true;
                    break;

                case 91: // Relative mode
                    absoluteMode = false;
                    break;
            }
        }

        private void ProcessMCode(int code, GCodeCommand command)
        {
            switch (code)
            {
                case 0:  // Program stop
                case 1:  // Optional stop
                case 2:  // Program end
                case 30: // Program end and rewind
                    command.isProgramEnd = true;
                    break;

                case 3:  // Spindle on CW
                case 4:  // Spindle on CCW
                    command.spindleOn = true;
                    break;

                case 5:  // Spindle off
                    command.spindleOn = false;
                    break;

                case 6:  // Tool change
                    command.isToolChange = true;
                    break;

                case 8:  // Coolant on
                    command.coolantOn = true;
                    break;

                case 9:  // Coolant off
                    command.coolantOn = false;
                    break;
            }
        }

        private void CreateSegment(GCodeCommand command)
        {
            Vector3 startPos = currentPosition;
            Vector3 endPos = CalculateEndPosition(command);

            var segment = new ToolpathSegment
            {
                lineNumber = command.lineNumber,
                startPoint = startPos,
                endPoint = endPos,
                motionType = command.motionType,
                feedRate = command.f ?? currentFeedRate,
                spindleSpeed = currentSpindleSpeed,
                isRapid = command.motionType == MotionType.Rapid
            };

            // Handle arcs
            if (command.motionType == MotionType.ArcCW || command.motionType == MotionType.ArcCCW)
            {
                segment.arcCenter = CalculateArcCenter(startPos, endPos, command);
                segment.arcRadius = command.r ?? Vector3.Distance(startPos, segment.arcCenter);
                segment.isClockwise = command.motionType == MotionType.ArcCW;
                segment.arcPoints = GenerateArcPoints(segment, 32);
            }

            segments.Add(segment);
            OnSegmentParsed?.Invoke(segment);

            currentPosition = endPos;
        }

        private Vector3 CalculateEndPosition(GCodeCommand command)
        {
            Vector3 endPos;

            if (absoluteMode)
            {
                endPos = new Vector3(
                    command.x ?? currentPosition.x,
                    command.y ?? currentPosition.y,
                    command.z ?? currentPosition.z
                );
            }
            else
            {
                endPos = currentPosition + new Vector3(
                    command.x ?? 0,
                    command.y ?? 0,
                    command.z ?? 0
                );
            }

            return endPos;
        }

        private Vector3 CalculateArcCenter(Vector3 start, Vector3 end, GCodeCommand command)
        {
            if (command.i.HasValue || command.j.HasValue || command.k.HasValue)
            {
                // IJK format (incremental from start point)
                return start + new Vector3(
                    command.i ?? 0,
                    command.j ?? 0,
                    command.k ?? 0
                );
            }
            else if (command.r.HasValue)
            {
                // R format - calculate center from radius
                float r = command.r.Value;
                Vector3 mid = (start + end) / 2f;
                Vector3 d = end - start;
                float dist = d.magnitude / 2f;

                if (Mathf.Abs(r) < dist)
                {
                    // Invalid radius, use midpoint
                    return mid;
                }

                float h = Mathf.Sqrt(r * r - dist * dist);
                Vector3 perp = new Vector3(-d.y, d.x, 0).normalized;

                // Positive R = smaller arc, negative R = larger arc
                if ((r > 0 && command.motionType == MotionType.ArcCCW) ||
                    (r < 0 && command.motionType == MotionType.ArcCW))
                {
                    return mid + perp * h;
                }
                else
                {
                    return mid - perp * h;
                }
            }

            return (start + end) / 2f;
        }

        private Vector3[] GenerateArcPoints(ToolpathSegment segment, int numPoints)
        {
            var points = new List<Vector3>();

            Vector3 start = segment.startPoint;
            Vector3 end = segment.endPoint;
            Vector3 center = segment.arcCenter;

            // Calculate start and end angles
            float startAngle = Mathf.Atan2(start.y - center.y, start.x - center.x);
            float endAngle = Mathf.Atan2(end.y - center.y, end.x - center.x);

            // Adjust angles for direction
            if (segment.isClockwise)
            {
                if (endAngle >= startAngle) endAngle -= 2 * Mathf.PI;
            }
            else
            {
                if (endAngle <= startAngle) endAngle += 2 * Mathf.PI;
            }

            float angleStep = (endAngle - startAngle) / numPoints;
            float radius = segment.arcRadius;

            for (int i = 0; i <= numPoints; i++)
            {
                float angle = startAngle + angleStep * i;
                float x = center.x + radius * Mathf.Cos(angle);
                float y = center.y + radius * Mathf.Sin(angle);
                float z = Mathf.Lerp(start.z, end.z, (float)i / numPoints);
                points.Add(new Vector3(x, y, z));
            }

            return points.ToArray();
        }

        private float ConvertUnits(float value)
        {
            // Convert to mm if in inches
            return metricUnits ? value : value * 25.4f;
        }

        // Public accessors
        public List<ToolpathSegment> Segments => segments;
        public List<GCodeCommand> Commands => commands;
        public Vector3 CurrentPosition => currentPosition;
    }

    // =========================================================================
    // Data Classes
    // =========================================================================

    public enum MotionType
    {
        None,
        Rapid,
        Linear,
        ArcCW,
        ArcCCW
    }

    [Serializable]
    public class GCodeCommand
    {
        public int lineNumber;
        public string rawLine;
        public MotionType motionType = MotionType.None;

        // Coordinates
        public float? x, y, z;
        public float? i, j, k; // Arc center offsets
        public float? r;       // Arc radius
        public float? f;       // Feed rate
        public float? s;       // Spindle speed

        // Flags
        public bool spindleOn;
        public bool coolantOn;
        public bool isToolChange;
        public bool isProgramEnd;
    }

    [Serializable]
    public class ToolpathSegment
    {
        public int lineNumber;
        public Vector3 startPoint;
        public Vector3 endPoint;
        public MotionType motionType;
        public float feedRate;
        public float spindleSpeed;
        public bool isRapid;

        // Arc data
        public Vector3 arcCenter;
        public float arcRadius;
        public bool isClockwise;
        public Vector3[] arcPoints;

        public float Length
        {
            get
            {
                if (motionType == MotionType.ArcCW || motionType == MotionType.ArcCCW)
                {
                    // Approximate arc length
                    float totalLength = 0;
                    if (arcPoints != null && arcPoints.Length > 1)
                    {
                        for (int i = 1; i < arcPoints.Length; i++)
                        {
                            totalLength += Vector3.Distance(arcPoints[i - 1], arcPoints[i]);
                        }
                    }
                    return totalLength;
                }
                return Vector3.Distance(startPoint, endPoint);
            }
        }

        public float EstimatedTime => Length / (feedRate / 60f); // seconds
    }
}
