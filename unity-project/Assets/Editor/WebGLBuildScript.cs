using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace CNCScada.Editor
{
    /// <summary>
    /// Build script for creating WebGL builds of the CNC SCADA Digital Twin.
    /// Creates optimized builds for embedding in the Flask web dashboard.
    /// </summary>
    public class WebGLBuildScript
    {
        // Build output path relative to Unity project
        private const string WebGLOutputPath = "../ui/static/unity-webgl";

        // Full build output path relative to Flask project
        private const string FlaskWebGLPath = "ui/static/unity-webgl";

        [MenuItem("CNC SCADA/Build WebGL", false, 100)]
        public static void BuildWebGL()
        {
            string outputPath = Path.Combine(Application.dataPath, "..", WebGLOutputPath);
            outputPath = Path.GetFullPath(outputPath);

            Debug.Log($"Building WebGL to: {outputPath}");

            // Ensure output directory exists
            if (Directory.Exists(outputPath))
            {
                // Clean old build
                Directory.Delete(outputPath, true);
            }
            Directory.CreateDirectory(outputPath);

            // Configure build settings
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = true;
            PlayerSettings.WebGL.template = "APPLICATION:Default";
            PlayerSettings.WebGL.memorySize = 256;
            PlayerSettings.WebGL.linkerTarget = WebGLLinkerTarget.Wasm;

            // Get scenes to build
            string[] scenes = GetBuildScenes();

            // Build options
            BuildPlayerOptions buildOptions = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = outputPath,
                target = BuildTarget.WebGL,
                options = BuildOptions.None
            };

            // Perform build
            BuildReport report = BuildPipeline.BuildPlayer(buildOptions);
            BuildSummary summary = report.summary;

            if (summary.result == BuildResult.Succeeded)
            {
                Debug.Log($"WebGL build succeeded: {summary.totalSize / 1024 / 1024:F2} MB");
                Debug.Log($"Output: {outputPath}");
                Debug.Log("The build is ready to be served from Flask at /static/unity-webgl/");

                // Open output folder
                EditorUtility.RevealInFinder(outputPath);
            }
            else
            {
                Debug.LogError($"WebGL build failed with {summary.totalErrors} errors");
            }
        }

        [MenuItem("CNC SCADA/Build WebGL (Development)", false, 101)]
        public static void BuildWebGLDevelopment()
        {
            string outputPath = Path.Combine(Application.dataPath, "..", WebGLOutputPath + "-dev");
            outputPath = Path.GetFullPath(outputPath);

            Debug.Log($"Building WebGL (Development) to: {outputPath}");

            if (Directory.Exists(outputPath))
            {
                Directory.Delete(outputPath, true);
            }
            Directory.CreateDirectory(outputPath);

            // Development settings
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
            PlayerSettings.WebGL.decompressionFallback = false;
            PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.FullWithStacktrace;

            string[] scenes = GetBuildScenes();

            BuildPlayerOptions buildOptions = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = outputPath,
                target = BuildTarget.WebGL,
                options = BuildOptions.Development | BuildOptions.AllowDebugging
            };

            BuildReport report = BuildPipeline.BuildPlayer(buildOptions);
            BuildSummary summary = report.summary;

            if (summary.result == BuildResult.Succeeded)
            {
                Debug.Log($"WebGL development build succeeded: {summary.totalSize / 1024 / 1024:F2} MB");
            }
            else
            {
                Debug.LogError($"WebGL build failed with {summary.totalErrors} errors");
            }
        }

        [MenuItem("CNC SCADA/Configure WebGL Settings", false, 200)]
        public static void ConfigureWebGLSettings()
        {
            // Product settings
            PlayerSettings.productName = "CNC Digital Twin";
            PlayerSettings.companyName = "CNC-SCADA";
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.WebGL, "com.cncscada.digitaltwin");

            // WebGL specific settings
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = true;
            PlayerSettings.WebGL.memorySize = 256;
            PlayerSettings.WebGL.linkerTarget = WebGLLinkerTarget.Wasm;
            PlayerSettings.WebGL.threadsSupport = false; // Safari compatibility
            PlayerSettings.WebGL.dataCaching = true;

            // Quality settings for WebGL
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.gpuSkinning = true;

            // Scripting backend
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.WebGL, ScriptingImplementation.IL2CPP);
            PlayerSettings.SetApiCompatibilityLevel(BuildTargetGroup.WebGL, ApiCompatibilityLevel.NET_Standard_2_0);

            // Define symbols
            PlayerSettings.SetScriptingDefineSymbolsForGroup(
                BuildTargetGroup.WebGL,
                "UNITY_ROBOTICS_ROS_TCP_CONNECTOR"
            );

            Debug.Log("WebGL settings configured for CNC SCADA Digital Twin");
        }

        private static string[] GetBuildScenes()
        {
            // Get all enabled scenes from build settings
            var scenes = new System.Collections.Generic.List<string>();

            foreach (var scene in EditorBuildSettings.scenes)
            {
                if (scene.enabled)
                {
                    scenes.Add(scene.path);
                }
            }

            // If no scenes configured, try to find the main scene
            if (scenes.Count == 0)
            {
                string mainScene = "Assets/Scenes/DigitalTwin.unity";
                if (File.Exists(Path.Combine(Application.dataPath, "..", mainScene)))
                {
                    scenes.Add(mainScene);
                }
                else
                {
                    mainScene = "Assets/Scenes/SampleScene.unity";
                    if (File.Exists(Path.Combine(Application.dataPath, "..", mainScene)))
                    {
                        scenes.Add(mainScene);
                    }
                }
            }

            return scenes.ToArray();
        }
    }

    /// <summary>
    /// Custom WebGL template for embedding in Flask dashboard
    /// </summary>
    public class WebGLTemplateCreator
    {
        [MenuItem("CNC SCADA/Create WebGL Template", false, 201)]
        public static void CreateWebGLTemplate()
        {
            string templatePath = Path.Combine(Application.dataPath, "WebGLTemplates", "CNCScada");

            if (!Directory.Exists(templatePath))
            {
                Directory.CreateDirectory(templatePath);
            }

            // Create index.html template
            string indexHtml = @"<!DOCTYPE html>
<html lang=""en-us"">
<head>
    <meta charset=""utf-8"">
    <meta http-equiv=""Content-Type"" content=""text/html; charset=utf-8"">
    <meta name=""viewport"" content=""width=device-width, initial-scale=1.0"">
    <title>{{{ PRODUCT_NAME }}}</title>
    <style>
        * { margin: 0; padding: 0; }
        html, body { width: 100%; height: 100%; overflow: hidden; background: #1a1a2e; }
        #unity-container {
            width: 100%;
            height: 100%;
        }
        #unity-canvas {
            width: 100%;
            height: 100%;
            background: #1a1a2e;
        }
        #unity-loading-bar {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 300px;
        }
        #unity-progress-bar-empty {
            width: 100%;
            height: 18px;
            background: #333;
            border-radius: 9px;
        }
        #unity-progress-bar-full {
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 9px;
            transition: width 0.1s;
        }
        #unity-loading-text {
            color: #888;
            text-align: center;
            margin-top: 10px;
            font-family: sans-serif;
        }
        .unity-mobile-warning {
            position: absolute;
            left: 50%;
            top: 5%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            padding: 10px 20px;
            border-radius: 5px;
            color: white;
            font-family: sans-serif;
        }
    </style>
</head>
<body>
    <div id=""unity-container"">
        <canvas id=""unity-canvas"" tabindex=""-1""></canvas>
        <div id=""unity-loading-bar"">
            <div id=""unity-progress-bar-empty"">
                <div id=""unity-progress-bar-full""></div>
            </div>
            <p id=""unity-loading-text"">Loading Digital Twin...</p>
        </div>
    </div>
    <script>
        var container = document.getElementById('unity-container');
        var canvas = document.getElementById('unity-canvas');
        var loadingBar = document.getElementById('unity-loading-bar');
        var progressBarFull = document.getElementById('unity-progress-bar-full');
        var loadingText = document.getElementById('unity-loading-text');

        // Configuration passed from Flask
        var unityConfig = window.unityConfig || {};
        var serverUrl = unityConfig.serverUrl || window.location.origin;
        var machineId = unityConfig.machineId || 'default';

        var buildUrl = 'Build';
        var loaderUrl = buildUrl + '/{{{ LOADER_FILENAME }}}';
        var config = {
            dataUrl: buildUrl + '/{{{ DATA_FILENAME }}}',
            frameworkUrl: buildUrl + '/{{{ FRAMEWORK_FILENAME }}}',
#if USE_WASM
            codeUrl: buildUrl + '/{{{ CODE_FILENAME }}}',
#endif
#if MEMORY_FILENAME
            memoryUrl: buildUrl + '/{{{ MEMORY_FILENAME }}}',
#endif
#if SYMBOLS_FILENAME
            symbolsUrl: buildUrl + '/{{{ SYMBOLS_FILENAME }}}',
#endif
            streamingAssetsUrl: 'StreamingAssets',
            companyName: '{{{ COMPANY_NAME }}}',
            productName: '{{{ PRODUCT_NAME }}}',
            productVersion: '{{{ PRODUCT_VERSION }}}',
        };

        var script = document.createElement('script');
        script.src = loaderUrl;
        script.onload = function() {
            createUnityInstance(canvas, config, function(progress) {
                progressBarFull.style.width = 100 * progress + '%';
                if (progress > 0.9) {
                    loadingText.textContent = 'Initializing...';
                }
            }).then(function(unityInstance) {
                loadingBar.style.display = 'none';

                // Pass configuration to Unity
                unityInstance.SendMessage('FlaskSocketIOClient', 'SetServerUrl', serverUrl);
                unityInstance.SendMessage('DigitalTwinController', 'SetMachineId', machineId);

                // Expose Unity instance globally for Flask integration
                window.unityInstance = unityInstance;

            }).catch(function(message) {
                alert('Error loading Digital Twin: ' + message);
            });
        };
        document.body.appendChild(script);
    </script>
</body>
</html>";

            File.WriteAllText(Path.Combine(templatePath, "index.html"), indexHtml);

            // Create thumbnail
            Debug.Log($"WebGL template created at: {templatePath}");
            Debug.Log("You may need to restart Unity to see the template in Player Settings.");

            AssetDatabase.Refresh();
        }
    }
}
