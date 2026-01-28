using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Recipes
{
    /// <summary>
    /// Recipe and CNC program management system.
    /// Manages machining recipes, G-code programs, tool lists, and setup sheets.
    /// Supports versioning, approval workflows, and program transfer.
    /// </summary>
    public class RecipeManager : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private string programsPath = "Programs";
        [SerializeField] private string backendUrl = "http://localhost:5001/api/recipes";
        [SerializeField] private bool syncWithBackend = true;

        [Header("Recipes")]
        [SerializeField] private List<MachiningRecipe> recipes = new List<MachiningRecipe>();

        [Header("Programs")]
        [SerializeField] private List<CNCProgram> programs = new List<CNCProgram>();

        [Header("Active Selection")]
        [SerializeField] private string activeRecipeId;
        [SerializeField] private string activeProgramId;

        [Header("Statistics")]
        [SerializeField] private int totalRecipes;
        [SerializeField] private int totalPrograms;
        [SerializeField] private int approvedRecipes;

        // Lookups
        private Dictionary<string, MachiningRecipe> recipeLookup = new Dictionary<string, MachiningRecipe>();
        private Dictionary<string, CNCProgram> programLookup = new Dictionary<string, CNCProgram>();

        // Events
        public event Action<MachiningRecipe> OnRecipeCreated;
        public event Action<MachiningRecipe> OnRecipeUpdated;
        public event Action<MachiningRecipe> OnRecipeApproved;
        public event Action<MachiningRecipe> OnRecipeActivated;
        public event Action<CNCProgram> OnProgramLoaded;
        public event Action<CNCProgram> OnProgramTransferred;

        // Singleton
        public static RecipeManager Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            // Ensure programs directory exists
            string fullPath = Path.Combine(Application.persistentDataPath, programsPath);
            if (!Directory.Exists(fullPath))
            {
                Directory.CreateDirectory(fullPath);
            }

            InitializeDemoRecipes();
        }

        private void InitializeDemoRecipes()
        {
            // Create demo machining recipes
            CreateRecipe(new MachiningRecipe
            {
                recipeId = "RCP_BRACKET_001",
                recipeName = "Mounting Bracket - Standard",
                partNumber = "BRACKET-001",
                revision = "A",
                material = "Aluminum 6061-T6",
                estimatedCycleTime = 15f,
                status = RecipeStatus.Approved,
                approvedBy = "Quality Manager",
                approvedDate = DateTime.Now.AddDays(-30),
                machineType = "Bantam CNC",
                description = "Standard mounting bracket for controller enclosure",
                setupInstructions = "1. Install 1/4\" end mill in spindle\n2. Set work offset to corner\n3. Verify stock dimensions",
                toolList = new List<RecipeTool>
                {
                    new RecipeTool { toolNumber = 1, toolName = "1/4\" End Mill", diameter = 6.35f, flutes = 4, operation = "Facing, Profiling" },
                    new RecipeTool { toolNumber = 2, toolName = "1/8\" End Mill", diameter = 3.175f, flutes = 2, operation = "Pocketing" },
                    new RecipeTool { toolNumber = 3, toolName = "#21 Drill", diameter = 4.04f, flutes = 2, operation = "Drilling" }
                },
                operations = new List<MachiningOperation>
                {
                    new MachiningOperation { operationNumber = 10, operationName = "Face Top", toolNumber = 1, spindleSpeed = 6000, feedRate = 500, depthOfCut = 0.5f },
                    new MachiningOperation { operationNumber = 20, operationName = "Profile Outside", toolNumber = 1, spindleSpeed = 8000, feedRate = 400, depthOfCut = 2.0f },
                    new MachiningOperation { operationNumber = 30, operationName = "Pocket Center", toolNumber = 2, spindleSpeed = 10000, feedRate = 300, depthOfCut = 1.0f },
                    new MachiningOperation { operationNumber = 40, operationName = "Drill Holes", toolNumber = 3, spindleSpeed = 4000, feedRate = 150, depthOfCut = 12.0f }
                },
                programFile = "bracket_001.nc"
            });

            CreateRecipe(new MachiningRecipe
            {
                recipeId = "RCP_SHAFT_002",
                recipeName = "Drive Shaft - Rev B",
                partNumber = "SHAFT-002",
                revision = "B",
                material = "Brass C360",
                estimatedCycleTime = 25f,
                status = RecipeStatus.Approved,
                approvedBy = "Process Engineer",
                approvedDate = DateTime.Now.AddDays(-15),
                machineType = "Bantam CNC",
                description = "Precision drive shaft for motor coupling",
                toolList = new List<RecipeTool>
                {
                    new RecipeTool { toolNumber = 1, toolName = "1/2\" Face Mill", diameter = 12.7f, flutes = 4, operation = "Facing" },
                    new RecipeTool { toolNumber = 2, toolName = "1/4\" End Mill", diameter = 6.35f, flutes = 4, operation = "Profiling" },
                    new RecipeTool { toolNumber = 3, toolName = "Center Drill", diameter = 3.0f, flutes = 2, operation = "Center Drilling" }
                },
                programFile = "shaft_002.nc"
            });

            CreateRecipe(new MachiningRecipe
            {
                recipeId = "RCP_PLATE_003",
                recipeName = "Base Plate - Simple",
                partNumber = "PLATE-003",
                revision = "A",
                material = "Aluminum 6061-T6",
                estimatedCycleTime = 8f,
                status = RecipeStatus.Draft,
                machineType = "Bantam CNC",
                description = "Simple base plate with mounting holes",
                programFile = "plate_003.nc"
            });

            // Create demo programs
            CreateProgram(new CNCProgram
            {
                programId = "PRG_BRACKET_001",
                programName = "bracket_001.nc",
                recipeId = "RCP_BRACKET_001",
                version = "1.0",
                gcode = GenerateDemoBracketGCode(),
                fileSize = 2048,
                lineCount = 150,
                status = ProgramStatus.Verified
            });

            CreateProgram(new CNCProgram
            {
                programId = "PRG_SHAFT_002",
                programName = "shaft_002.nc",
                recipeId = "RCP_SHAFT_002",
                version = "2.1",
                gcode = GenerateDemoShaftGCode(),
                fileSize = 3500,
                lineCount = 220,
                status = ProgramStatus.Verified
            });

            UpdateStatistics();
        }

        private string GenerateDemoBracketGCode()
        {
            return @"(Mounting Bracket - Standard)
(Part Number: BRACKET-001 Rev A)
(Material: Aluminum 6061-T6)
(Generated: " + DateTime.Now.ToString("yyyy-MM-dd") + @")

G21 (Metric)
G90 (Absolute)
G17 (XY Plane)

(Tool 1 - 1/4 End Mill)
T1 M6
S6000 M3
G43 H1 Z50

(Op 10 - Face Top)
G0 X0 Y0
G0 Z5
G1 Z-0.5 F500
G1 X50 F500
G1 Y50
G1 X0
G1 Y0
G0 Z50

(Op 20 - Profile Outside)
S8000
G0 X-5 Y-5
G0 Z2
G1 Z-2 F400
G1 X55
G1 Y55
G1 X-5
G1 Y-5
G0 Z50

(Tool 2 - 1/8 End Mill)
T2 M6
S10000 M3
G43 H2 Z50

(Op 30 - Pocket Center)
G0 X15 Y15
G0 Z2
G1 Z-5 F300
G1 X35
G1 Y35
G1 X15
G1 Y15
G0 Z50

(Tool 3 - Drill)
T3 M6
S4000 M3
G43 H3 Z50

(Op 40 - Drill Holes)
G0 X10 Y10
G0 Z2
G1 Z-12 F150
G0 Z2
G0 X40 Y10
G1 Z-12 F150
G0 Z2
G0 X40 Y40
G1 Z-12 F150
G0 Z2
G0 X10 Y40
G1 Z-12 F150
G0 Z50

M5
M30
";
        }

        private string GenerateDemoShaftGCode()
        {
            return @"(Drive Shaft - Rev B)
(Part Number: SHAFT-002 Rev B)
(Material: Brass C360)

G21 G90 G17
T1 M6
S5000 M3
G43 H1 Z50

G0 X0 Y0
G0 Z5
G1 Z0 F200
G1 X25 F400
G0 Z50

M5
M30
";
        }

        // =========================================================================
        // Recipe Management
        // =========================================================================

        /// <summary>
        /// Create a new machining recipe
        /// </summary>
        public MachiningRecipe CreateRecipe(MachiningRecipe recipe)
        {
            if (string.IsNullOrEmpty(recipe.recipeId))
            {
                recipe.recipeId = $"RCP_{DateTime.Now.Ticks}";
            }

            recipe.createdDate = DateTime.Now;
            recipe.modifiedDate = DateTime.Now;

            if (recipe.status == RecipeStatus.None)
            {
                recipe.status = RecipeStatus.Draft;
            }

            recipes.Add(recipe);
            recipeLookup[recipe.recipeId] = recipe;

            UpdateStatistics();
            OnRecipeCreated?.Invoke(recipe);

            Debug.Log($"[RecipeManager] Created recipe: {recipe.recipeName}");

            return recipe;
        }

        /// <summary>
        /// Update an existing recipe
        /// </summary>
        public bool UpdateRecipe(MachiningRecipe recipe)
        {
            if (!recipeLookup.ContainsKey(recipe.recipeId))
            {
                return false;
            }

            recipe.modifiedDate = DateTime.Now;

            // If recipe was approved and is being modified, reset to draft
            if (recipe.status == RecipeStatus.Approved)
            {
                recipe.status = RecipeStatus.PendingApproval;
            }

            recipeLookup[recipe.recipeId] = recipe;

            int index = recipes.FindIndex(r => r.recipeId == recipe.recipeId);
            if (index >= 0)
            {
                recipes[index] = recipe;
            }

            OnRecipeUpdated?.Invoke(recipe);

            Debug.Log($"[RecipeManager] Updated recipe: {recipe.recipeName}");

            return true;
        }

        /// <summary>
        /// Submit recipe for approval
        /// </summary>
        public void SubmitForApproval(string recipeId)
        {
            if (recipeLookup.TryGetValue(recipeId, out var recipe))
            {
                recipe.status = RecipeStatus.PendingApproval;
                recipe.modifiedDate = DateTime.Now;

                OnRecipeUpdated?.Invoke(recipe);

                Debug.Log($"[RecipeManager] Recipe submitted for approval: {recipe.recipeName}");
            }
        }

        /// <summary>
        /// Approve a recipe
        /// </summary>
        public void ApproveRecipe(string recipeId, string approvedBy)
        {
            if (recipeLookup.TryGetValue(recipeId, out var recipe))
            {
                recipe.status = RecipeStatus.Approved;
                recipe.approvedBy = approvedBy;
                recipe.approvedDate = DateTime.Now;
                recipe.modifiedDate = DateTime.Now;

                UpdateStatistics();
                OnRecipeApproved?.Invoke(recipe);

                Debug.Log($"[RecipeManager] Recipe approved: {recipe.recipeName} by {approvedBy}");
            }
        }

        /// <summary>
        /// Reject a recipe
        /// </summary>
        public void RejectRecipe(string recipeId, string reason)
        {
            if (recipeLookup.TryGetValue(recipeId, out var recipe))
            {
                recipe.status = RecipeStatus.Rejected;
                recipe.rejectionReason = reason;
                recipe.modifiedDate = DateTime.Now;

                OnRecipeUpdated?.Invoke(recipe);

                Debug.Log($"[RecipeManager] Recipe rejected: {recipe.recipeName} - {reason}");
            }
        }

        /// <summary>
        /// Set the active recipe for production
        /// </summary>
        public void ActivateRecipe(string recipeId)
        {
            if (recipeLookup.TryGetValue(recipeId, out var recipe))
            {
                if (recipe.status != RecipeStatus.Approved)
                {
                    Debug.LogWarning($"[RecipeManager] Cannot activate unapproved recipe: {recipe.recipeName}");
                    return;
                }

                activeRecipeId = recipeId;
                OnRecipeActivated?.Invoke(recipe);

                // Load associated program
                if (!string.IsNullOrEmpty(recipe.programFile))
                {
                    var program = programs.Find(p => p.programName == recipe.programFile);
                    if (program != null)
                    {
                        ActivateProgram(program.programId);
                    }
                }

                Debug.Log($"[RecipeManager] Activated recipe: {recipe.recipeName}");
            }
        }

        // =========================================================================
        // Program Management
        // =========================================================================

        /// <summary>
        /// Create a new CNC program
        /// </summary>
        public CNCProgram CreateProgram(CNCProgram program)
        {
            if (string.IsNullOrEmpty(program.programId))
            {
                program.programId = $"PRG_{DateTime.Now.Ticks}";
            }

            program.createdDate = DateTime.Now;
            program.modifiedDate = DateTime.Now;

            if (program.status == ProgramStatus.None)
            {
                program.status = ProgramStatus.Draft;
            }

            // Calculate line count if not set
            if (program.lineCount == 0 && !string.IsNullOrEmpty(program.gcode))
            {
                program.lineCount = program.gcode.Split('\n').Length;
            }

            programs.Add(program);
            programLookup[program.programId] = program;

            UpdateStatistics();

            Debug.Log($"[RecipeManager] Created program: {program.programName}");

            return program;
        }

        /// <summary>
        /// Load a program from file
        /// </summary>
        public CNCProgram LoadProgramFromFile(string filePath)
        {
            if (!File.Exists(filePath))
            {
                Debug.LogError($"[RecipeManager] Program file not found: {filePath}");
                return null;
            }

            string gcode = File.ReadAllText(filePath);
            string fileName = Path.GetFileName(filePath);

            var program = new CNCProgram
            {
                programName = fileName,
                gcode = gcode,
                fileSize = new FileInfo(filePath).Length,
                lineCount = gcode.Split('\n').Length,
                status = ProgramStatus.Draft
            };

            CreateProgram(program);
            OnProgramLoaded?.Invoke(program);

            return program;
        }

        /// <summary>
        /// Save program to file
        /// </summary>
        public void SaveProgramToFile(string programId, string filePath = null)
        {
            if (!programLookup.TryGetValue(programId, out var program))
            {
                return;
            }

            if (string.IsNullOrEmpty(filePath))
            {
                filePath = Path.Combine(Application.persistentDataPath, programsPath, program.programName);
            }

            File.WriteAllText(filePath, program.gcode);
            program.modifiedDate = DateTime.Now;

            Debug.Log($"[RecipeManager] Saved program: {filePath}");
        }

        /// <summary>
        /// Set the active program
        /// </summary>
        public void ActivateProgram(string programId)
        {
            if (programLookup.TryGetValue(programId, out var program))
            {
                activeProgramId = programId;

                // Load into toolpath visualizer if available
                var toolpathVisualizer = FindObjectOfType<CNCScada.Toolpath.ToolpathVisualizer>();
                if (toolpathVisualizer != null && !string.IsNullOrEmpty(program.gcode))
                {
                    toolpathVisualizer.LoadGCode(program.gcode);
                }

                Debug.Log($"[RecipeManager] Activated program: {program.programName}");
            }
        }

        /// <summary>
        /// Transfer program to machine
        /// </summary>
        public IEnumerator TransferProgramToMachine(string programId, string machineId)
        {
            if (!programLookup.TryGetValue(programId, out var program))
            {
                yield break;
            }

            Debug.Log($"[RecipeManager] Transferring program {program.programName} to {machineId}...");

            // Simulate transfer delay
            yield return new WaitForSeconds(1f);

            program.lastTransferDate = DateTime.Now;
            program.lastTransferMachine = machineId;

            OnProgramTransferred?.Invoke(program);

            var notificationService = FindObjectOfType<CNCScada.Notifications.NotificationService>();
            notificationService?.Notify(
                "Program Transferred",
                $"{program.programName} transferred to {machineId}",
                CNCScada.Notifications.NotificationType.Success
            );

            Debug.Log($"[RecipeManager] Program transferred successfully");
        }

        /// <summary>
        /// Verify program (syntax check)
        /// </summary>
        public bool VerifyProgram(string programId)
        {
            if (!programLookup.TryGetValue(programId, out var program))
            {
                return false;
            }

            // Basic G-code verification
            var errors = new List<string>();
            string[] lines = program.gcode.Split('\n');

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i].Trim();

                if (string.IsNullOrEmpty(line) || line.StartsWith("(") || line.StartsWith(";"))
                {
                    continue;
                }

                // Check for valid G/M codes
                if (!IsValidGCodeLine(line))
                {
                    errors.Add($"Line {i + 1}: Invalid syntax");
                }
            }

            if (errors.Count == 0)
            {
                program.status = ProgramStatus.Verified;
                program.verificationDate = DateTime.Now;
                Debug.Log($"[RecipeManager] Program verified: {program.programName}");
                return true;
            }
            else
            {
                program.status = ProgramStatus.Error;
                Debug.LogWarning($"[RecipeManager] Program verification failed: {errors.Count} errors");
                return false;
            }
        }

        private bool IsValidGCodeLine(string line)
        {
            // Basic validation - check for G, M, X, Y, Z, F, S codes
            string upper = line.ToUpper();
            return upper.StartsWith("G") || upper.StartsWith("M") ||
                   upper.StartsWith("T") || upper.StartsWith("S") ||
                   upper.StartsWith("F") || upper.StartsWith("X") ||
                   upper.StartsWith("Y") || upper.StartsWith("Z") ||
                   upper.StartsWith("N") || upper.StartsWith("%");
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        public MachiningRecipe GetRecipe(string recipeId)
        {
            return recipeLookup.TryGetValue(recipeId, out var recipe) ? recipe : null;
        }

        public CNCProgram GetProgram(string programId)
        {
            return programLookup.TryGetValue(programId, out var program) ? program : null;
        }

        public List<MachiningRecipe> GetAllRecipes() => new List<MachiningRecipe>(recipes);
        public List<CNCProgram> GetAllPrograms() => new List<CNCProgram>(programs);

        public List<MachiningRecipe> GetRecipesByStatus(RecipeStatus status)
        {
            return recipes.Where(r => r.status == status).ToList();
        }

        public List<MachiningRecipe> GetRecipesForPart(string partNumber)
        {
            return recipes.Where(r => r.partNumber == partNumber).ToList();
        }

        public MachiningRecipe GetActiveRecipe()
        {
            return string.IsNullOrEmpty(activeRecipeId) ? null : GetRecipe(activeRecipeId);
        }

        public CNCProgram GetActiveProgram()
        {
            return string.IsNullOrEmpty(activeProgramId) ? null : GetProgram(activeProgramId);
        }

        private void UpdateStatistics()
        {
            totalRecipes = recipes.Count;
            totalPrograms = programs.Count;
            approvedRecipes = recipes.Count(r => r.status == RecipeStatus.Approved);
        }

        // Properties
        public int TotalRecipes => totalRecipes;
        public int TotalPrograms => totalPrograms;
        public int ApprovedRecipes => approvedRecipes;
        public string ActiveRecipeId => activeRecipeId;
        public string ActiveProgramId => activeProgramId;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum RecipeStatus
    {
        None,
        Draft,
        PendingApproval,
        Approved,
        Rejected,
        Obsolete
    }

    public enum ProgramStatus
    {
        None,
        Draft,
        Verified,
        Error,
        Obsolete
    }

    [Serializable]
    public class MachiningRecipe
    {
        public string recipeId;
        public string recipeName;
        public string partNumber;
        public string revision;
        public string material;
        public float estimatedCycleTime;
        public RecipeStatus status;
        public string machineType;
        public string description;
        public string setupInstructions;
        public List<RecipeTool> toolList;
        public List<MachiningOperation> operations;
        public string programFile;
        public string approvedBy;
        public DateTime approvedDate;
        public string rejectionReason;
        public DateTime createdDate;
        public DateTime modifiedDate;
        public string createdBy;
        public Dictionary<string, string> customParameters;
    }

    [Serializable]
    public class RecipeTool
    {
        public int toolNumber;
        public string toolName;
        public float diameter;
        public int flutes;
        public string material;
        public string coating;
        public string operation;
        public float stickout;
        public string holderType;
    }

    [Serializable]
    public class MachiningOperation
    {
        public int operationNumber;
        public string operationName;
        public int toolNumber;
        public float spindleSpeed;
        public float feedRate;
        public float depthOfCut;
        public float stepover;
        public string strategy;
        public string notes;
    }

    [Serializable]
    public class CNCProgram
    {
        public string programId;
        public string programName;
        public string recipeId;
        public string version;
        public string gcode;
        public long fileSize;
        public int lineCount;
        public ProgramStatus status;
        public DateTime createdDate;
        public DateTime modifiedDate;
        public DateTime verificationDate;
        public DateTime lastTransferDate;
        public string lastTransferMachine;
        public string checksum;
    }
}
