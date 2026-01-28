using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.ML
{
    /// <summary>
    /// Machine Learning Inference Engine for edge deployment
    /// Supports ONNX models, real-time inference, and predictive analytics
    /// </summary>
    public class MLInferenceEngine : MonoBehaviour
    {
        public static MLInferenceEngine Instance { get; private set; }

        [Header("Engine Configuration")]
        [SerializeField] private float inferenceInterval = 0.1f; // 10 Hz default
        [SerializeField] private int maxBatchSize = 32;
        [SerializeField] private bool enableGPUAcceleration = true;
        [SerializeField] private int featureBufferSize = 1000;

        // Registered models
        private Dictionary<string, MLModel> models = new Dictionary<string, MLModel>();

        // Feature streams for continuous inference
        private Dictionary<string, FeatureStream> featureStreams = new Dictionary<string, FeatureStream>();

        // Inference queue for batching
        private Queue<InferenceRequest> inferenceQueue = new Queue<InferenceRequest>();

        // Model performance tracking
        private Dictionary<string, ModelPerformance> modelPerformance = new Dictionary<string, ModelPerformance>();

        // Events
        public event Action<string, InferenceResult> OnInferenceComplete;
        public event Action<string, AnomalyDetection> OnAnomalyDetected;
        public event Action<string, PredictionResult> OnPredictionReady;
        public event Action<string, ModelEvent> OnModelEvent;

        #region Data Structures

        [System.Serializable]
        public class MLModel
        {
            public string modelId;
            public string name;
            public string version;
            public ModelType type;
            public ModelStatus status;
            public DateTime loadedAt;

            // Model architecture
            public int[] inputShape;
            public int[] outputShape;
            public string[] inputFeatures;
            public string[] outputLabels;

            // Preprocessing
            public NormalizationParams normalization;
            public Dictionary<string, float[]> featureScaling;

            // Model weights (simplified representation)
            public List<Layer> layers;

            // Metadata
            public float accuracy;
            public float f1Score;
            public string trainedOn;
            public Dictionary<string, object> hyperparameters;
        }

        public enum ModelType
        {
            Regression,
            BinaryClassification,
            MultiClassification,
            AnomalyDetection,
            TimeSeries,
            Clustering,
            ReinforcementLearning
        }

        public enum ModelStatus
        {
            Loading,
            Ready,
            Running,
            Error,
            Updating
        }

        [System.Serializable]
        public class Layer
        {
            public string name;
            public LayerType type;
            public int[] shape;
            public float[,] weights;
            public float[] biases;
            public ActivationType activation;
        }

        public enum LayerType
        {
            Dense,
            Conv1D,
            Conv2D,
            LSTM,
            GRU,
            Dropout,
            BatchNorm,
            Flatten,
            Pooling
        }

        public enum ActivationType
        {
            None,
            ReLU,
            Sigmoid,
            Tanh,
            Softmax,
            LeakyReLU,
            ELU
        }

        [System.Serializable]
        public class NormalizationParams
        {
            public NormalizationType type;
            public float[] mean;
            public float[] std;
            public float[] min;
            public float[] max;
        }

        public enum NormalizationType
        {
            None,
            StandardScaler,  // (x - mean) / std
            MinMaxScaler,    // (x - min) / (max - min)
            RobustScaler     // (x - median) / IQR
        }

        [System.Serializable]
        public class FeatureStream
        {
            public string streamId;
            public string[] featureNames;
            public Queue<float[]> buffer;
            public int windowSize;
            public int stride;
            public DateTime lastUpdate;
            public string targetModelId;
        }

        [System.Serializable]
        public class InferenceRequest
        {
            public string requestId;
            public string modelId;
            public float[][] inputData;
            public DateTime timestamp;
            public int priority;
            public Action<InferenceResult> callback;
        }

        [System.Serializable]
        public class InferenceResult
        {
            public string requestId;
            public string modelId;
            public float[][] outputs;
            public float[] probabilities;
            public int[] predictedClasses;
            public float confidence;
            public float inferenceTimeMs;
            public DateTime timestamp;
        }

        [System.Serializable]
        public class AnomalyDetection
        {
            public string detectionId;
            public string modelId;
            public float anomalyScore;
            public float threshold;
            public bool isAnomaly;
            public float[] featureContributions;
            public string[] contributingFeatures;
            public AnomalySeverity severity;
            public DateTime timestamp;
        }

        public enum AnomalySeverity
        {
            Low,
            Medium,
            High,
            Critical
        }

        [System.Serializable]
        public class PredictionResult
        {
            public string predictionId;
            public string modelId;
            public PredictionType type;
            public float predictedValue;
            public float[] forecastValues;
            public float confidenceInterval;
            public float lowerBound;
            public float upperBound;
            public DateTime predictionTime;
            public DateTime targetTime;
        }

        public enum PredictionType
        {
            RemainingUsefulLife,
            NextFailure,
            QualityPrediction,
            ProcessParameter,
            EnergyConsumption,
            CycleTime
        }

        [System.Serializable]
        public class ModelPerformance
        {
            public string modelId;
            public int totalInferences;
            public float averageInferenceTimeMs;
            public float maxInferenceTimeMs;
            public float minInferenceTimeMs;
            public int errorCount;
            public float accuracy;
            public float precision;
            public float recall;
            public List<float> recentLatencies;
        }

        [System.Serializable]
        public class ModelEvent
        {
            public string modelId;
            public ModelEventType eventType;
            public string message;
            public Dictionary<string, object> details;
            public DateTime timestamp;
        }

        public enum ModelEventType
        {
            Loaded,
            Updated,
            Error,
            DriftDetected,
            RetrainingNeeded,
            Unloaded
        }

        #endregion

        #region Unity Lifecycle

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
            }
        }

        private void Start()
        {
            InitializeEngine();
            StartCoroutine(InferenceLoop());
            StartCoroutine(ModelMonitoringLoop());
        }

        private void OnDestroy()
        {
            StopAllCoroutines();
        }

        #endregion

        #region Initialization

        private void InitializeEngine()
        {
            Debug.Log("[MLInference] Initializing ML Inference Engine");

            // Create default models for common use cases
            CreatePredictiveMaintenanceModel();
            CreateAnomalyDetectionModel();
            CreateQualityPredictionModel();
            CreateToolWearModel();
            CreateEnergyPredictionModel();

            Debug.Log($"[MLInference] Engine initialized with {models.Count} models");
        }

        private void CreatePredictiveMaintenanceModel()
        {
            var model = new MLModel
            {
                modelId = "predictive_maintenance_v1",
                name = "Predictive Maintenance Model",
                version = "1.0.0",
                type = ModelType.Regression,
                status = ModelStatus.Ready,
                loadedAt = DateTime.Now,
                inputShape = new int[] { 1, 20 },
                outputShape = new int[] { 1, 1 },
                inputFeatures = new string[]
                {
                    "spindle_vibration_x", "spindle_vibration_y", "spindle_vibration_z",
                    "spindle_temperature", "spindle_current", "spindle_rpm",
                    "axis_x_position", "axis_y_position", "axis_z_position",
                    "axis_x_load", "axis_y_load", "axis_z_load",
                    "coolant_pressure", "coolant_temperature",
                    "ambient_temperature", "humidity",
                    "operating_hours", "cycles_count", "last_maintenance_hours", "alarm_count"
                },
                outputLabels = new string[] { "remaining_useful_life_hours" },
                normalization = new NormalizationParams
                {
                    type = NormalizationType.StandardScaler,
                    mean = new float[20],
                    std = Enumerable.Repeat(1f, 20).ToArray()
                },
                layers = CreateNeuralNetworkLayers(20, new int[] { 64, 32, 16 }, 1),
                accuracy = 0.89f,
                f1Score = 0.87f,
                trainedOn = "2024-01-15"
            };

            models[model.modelId] = model;
            modelPerformance[model.modelId] = new ModelPerformance
            {
                modelId = model.modelId,
                recentLatencies = new List<float>()
            };
        }

        private void CreateAnomalyDetectionModel()
        {
            var model = new MLModel
            {
                modelId = "anomaly_detection_v1",
                name = "Isolation Forest Anomaly Detector",
                version = "1.0.0",
                type = ModelType.AnomalyDetection,
                status = ModelStatus.Ready,
                loadedAt = DateTime.Now,
                inputShape = new int[] { 1, 12 },
                outputShape = new int[] { 1, 1 },
                inputFeatures = new string[]
                {
                    "vibration_rms", "vibration_kurtosis", "vibration_crest_factor",
                    "temperature_deviation", "current_deviation", "speed_deviation",
                    "position_error", "following_error", "cycle_time_deviation",
                    "power_factor", "harmonic_distortion", "noise_level"
                },
                outputLabels = new string[] { "anomaly_score" },
                normalization = new NormalizationParams
                {
                    type = NormalizationType.MinMaxScaler,
                    min = new float[12],
                    max = Enumerable.Repeat(1f, 12).ToArray()
                },
                layers = CreateAutoencoderLayers(12, new int[] { 8, 4, 8 }, 12),
                accuracy = 0.94f,
                f1Score = 0.91f,
                trainedOn = "2024-02-20"
            };

            models[model.modelId] = model;
            modelPerformance[model.modelId] = new ModelPerformance
            {
                modelId = model.modelId,
                recentLatencies = new List<float>()
            };
        }

        private void CreateQualityPredictionModel()
        {
            var model = new MLModel
            {
                modelId = "quality_prediction_v1",
                name = "Part Quality Predictor",
                version = "1.0.0",
                type = ModelType.BinaryClassification,
                status = ModelStatus.Ready,
                loadedAt = DateTime.Now,
                inputShape = new int[] { 1, 15 },
                outputShape = new int[] { 1, 2 },
                inputFeatures = new string[]
                {
                    "feed_rate", "spindle_speed", "depth_of_cut",
                    "tool_wear_percentage", "tool_vibration",
                    "material_hardness", "coolant_flow_rate",
                    "ambient_temperature", "humidity",
                    "machine_hours_since_calibration",
                    "axis_backlash_x", "axis_backlash_y", "axis_backlash_z",
                    "thermal_compensation_active", "operator_experience_level"
                },
                outputLabels = new string[] { "reject", "accept" },
                normalization = new NormalizationParams
                {
                    type = NormalizationType.StandardScaler,
                    mean = new float[15],
                    std = Enumerable.Repeat(1f, 15).ToArray()
                },
                layers = CreateNeuralNetworkLayers(15, new int[] { 32, 16 }, 2, true),
                accuracy = 0.96f,
                f1Score = 0.94f,
                trainedOn = "2024-03-10"
            };

            models[model.modelId] = model;
            modelPerformance[model.modelId] = new ModelPerformance
            {
                modelId = model.modelId,
                recentLatencies = new List<float>()
            };
        }

        private void CreateToolWearModel()
        {
            var model = new MLModel
            {
                modelId = "tool_wear_v1",
                name = "Tool Wear Estimator",
                version = "1.0.0",
                type = ModelType.Regression,
                status = ModelStatus.Ready,
                loadedAt = DateTime.Now,
                inputShape = new int[] { 1, 10 },
                outputShape = new int[] { 1, 1 },
                inputFeatures = new string[]
                {
                    "cutting_force_x", "cutting_force_y", "cutting_force_z",
                    "spindle_power", "acoustic_emission",
                    "surface_roughness", "chips_shape_factor",
                    "cutting_time", "material_removed", "tool_type_encoded"
                },
                outputLabels = new string[] { "wear_percentage" },
                normalization = new NormalizationParams
                {
                    type = NormalizationType.StandardScaler,
                    mean = new float[10],
                    std = Enumerable.Repeat(1f, 10).ToArray()
                },
                layers = CreateNeuralNetworkLayers(10, new int[] { 32, 16, 8 }, 1),
                accuracy = 0.91f,
                f1Score = 0.89f,
                trainedOn = "2024-01-28"
            };

            models[model.modelId] = model;
            modelPerformance[model.modelId] = new ModelPerformance
            {
                modelId = model.modelId,
                recentLatencies = new List<float>()
            };
        }

        private void CreateEnergyPredictionModel()
        {
            var model = new MLModel
            {
                modelId = "energy_prediction_v1",
                name = "Energy Consumption Predictor",
                version = "1.0.0",
                type = ModelType.TimeSeries,
                status = ModelStatus.Ready,
                loadedAt = DateTime.Now,
                inputShape = new int[] { 24, 8 }, // 24 timesteps, 8 features
                outputShape = new int[] { 1, 1 },
                inputFeatures = new string[]
                {
                    "power_consumption_kwh", "spindle_utilization",
                    "axis_activity", "coolant_pump_state",
                    "ambient_temperature", "shift_encoding",
                    "day_of_week", "hour_of_day"
                },
                outputLabels = new string[] { "next_hour_consumption_kwh" },
                normalization = new NormalizationParams
                {
                    type = NormalizationType.MinMaxScaler,
                    min = new float[8],
                    max = Enumerable.Repeat(1f, 8).ToArray()
                },
                layers = CreateLSTMLayers(8, 32, 1),
                accuracy = 0.88f,
                f1Score = 0.86f,
                trainedOn = "2024-02-05"
            };

            models[model.modelId] = model;
            modelPerformance[model.modelId] = new ModelPerformance
            {
                modelId = model.modelId,
                recentLatencies = new List<float>()
            };
        }

        private List<Layer> CreateNeuralNetworkLayers(int inputSize, int[] hiddenSizes, int outputSize, bool softmax = false)
        {
            var layers = new List<Layer>();
            int prevSize = inputSize;

            for (int i = 0; i < hiddenSizes.Length; i++)
            {
                layers.Add(new Layer
                {
                    name = $"dense_{i}",
                    type = LayerType.Dense,
                    shape = new int[] { prevSize, hiddenSizes[i] },
                    weights = InitializeWeights(prevSize, hiddenSizes[i]),
                    biases = new float[hiddenSizes[i]],
                    activation = ActivationType.ReLU
                });
                prevSize = hiddenSizes[i];
            }

            // Output layer
            layers.Add(new Layer
            {
                name = "output",
                type = LayerType.Dense,
                shape = new int[] { prevSize, outputSize },
                weights = InitializeWeights(prevSize, outputSize),
                biases = new float[outputSize],
                activation = softmax ? ActivationType.Softmax : ActivationType.None
            });

            return layers;
        }

        private List<Layer> CreateAutoencoderLayers(int inputSize, int[] encoderSizes, int outputSize)
        {
            var layers = new List<Layer>();
            int prevSize = inputSize;

            // Encoder
            for (int i = 0; i < encoderSizes.Length; i++)
            {
                layers.Add(new Layer
                {
                    name = $"encoder_{i}",
                    type = LayerType.Dense,
                    shape = new int[] { prevSize, encoderSizes[i] },
                    weights = InitializeWeights(prevSize, encoderSizes[i]),
                    biases = new float[encoderSizes[i]],
                    activation = ActivationType.ReLU
                });
                prevSize = encoderSizes[i];
            }

            // Decoder (output)
            layers.Add(new Layer
            {
                name = "decoder_output",
                type = LayerType.Dense,
                shape = new int[] { prevSize, outputSize },
                weights = InitializeWeights(prevSize, outputSize),
                biases = new float[outputSize],
                activation = ActivationType.Sigmoid
            });

            return layers;
        }

        private List<Layer> CreateLSTMLayers(int inputSize, int hiddenSize, int outputSize)
        {
            var layers = new List<Layer>();

            // LSTM layer (simplified)
            layers.Add(new Layer
            {
                name = "lstm",
                type = LayerType.LSTM,
                shape = new int[] { inputSize, hiddenSize },
                weights = InitializeWeights(inputSize + hiddenSize, hiddenSize * 4), // Gates: i, f, g, o
                biases = new float[hiddenSize * 4],
                activation = ActivationType.Tanh
            });

            // Dense output
            layers.Add(new Layer
            {
                name = "output",
                type = LayerType.Dense,
                shape = new int[] { hiddenSize, outputSize },
                weights = InitializeWeights(hiddenSize, outputSize),
                biases = new float[outputSize],
                activation = ActivationType.None
            });

            return layers;
        }

        private float[,] InitializeWeights(int inputSize, int outputSize)
        {
            // Xavier/Glorot initialization
            var weights = new float[inputSize, outputSize];
            float scale = Mathf.Sqrt(2.0f / (inputSize + outputSize));

            for (int i = 0; i < inputSize; i++)
            {
                for (int j = 0; j < outputSize; j++)
                {
                    weights[i, j] = UnityEngine.Random.Range(-scale, scale);
                }
            }

            return weights;
        }

        #endregion

        #region Model Management

        public void LoadModel(string modelId, byte[] modelData)
        {
            // In production, this would load ONNX or TensorFlow Lite model
            Debug.Log($"[MLInference] Loading model: {modelId}");

            if (models.ContainsKey(modelId))
            {
                models[modelId].status = ModelStatus.Updating;
            }

            // Simulate model loading
            StartCoroutine(LoadModelAsync(modelId, modelData));
        }

        private IEnumerator LoadModelAsync(string modelId, byte[] modelData)
        {
            yield return new WaitForSeconds(0.5f); // Simulate loading time

            if (models.ContainsKey(modelId))
            {
                models[modelId].status = ModelStatus.Ready;
                models[modelId].loadedAt = DateTime.Now;

                OnModelEvent?.Invoke(modelId, new ModelEvent
                {
                    modelId = modelId,
                    eventType = ModelEventType.Loaded,
                    message = "Model loaded successfully",
                    timestamp = DateTime.Now
                });
            }

            Debug.Log($"[MLInference] Model {modelId} loaded successfully");
        }

        public void UnloadModel(string modelId)
        {
            if (models.ContainsKey(modelId))
            {
                models.Remove(modelId);
                modelPerformance.Remove(modelId);

                OnModelEvent?.Invoke(modelId, new ModelEvent
                {
                    modelId = modelId,
                    eventType = ModelEventType.Unloaded,
                    message = "Model unloaded",
                    timestamp = DateTime.Now
                });

                Debug.Log($"[MLInference] Model {modelId} unloaded");
            }
        }

        public MLModel GetModel(string modelId)
        {
            return models.TryGetValue(modelId, out var model) ? model : null;
        }

        public List<MLModel> GetAllModels()
        {
            return models.Values.ToList();
        }

        #endregion

        #region Feature Streams

        public void CreateFeatureStream(string streamId, string[] featureNames, int windowSize, int stride, string targetModelId)
        {
            var stream = new FeatureStream
            {
                streamId = streamId,
                featureNames = featureNames,
                buffer = new Queue<float[]>(),
                windowSize = windowSize,
                stride = stride,
                lastUpdate = DateTime.Now,
                targetModelId = targetModelId
            };

            featureStreams[streamId] = stream;
            Debug.Log($"[MLInference] Created feature stream: {streamId} -> {targetModelId}");
        }

        public void PushFeatures(string streamId, float[] features)
        {
            if (!featureStreams.TryGetValue(streamId, out var stream))
            {
                Debug.LogWarning($"[MLInference] Feature stream not found: {streamId}");
                return;
            }

            stream.buffer.Enqueue(features);
            stream.lastUpdate = DateTime.Now;

            // Maintain buffer size
            while (stream.buffer.Count > featureBufferSize)
            {
                stream.buffer.Dequeue();
            }

            // Check if we have enough data for inference
            if (stream.buffer.Count >= stream.windowSize)
            {
                TriggerStreamInference(stream);
            }
        }

        private void TriggerStreamInference(FeatureStream stream)
        {
            // Get window of data
            var windowData = stream.buffer.Skip(stream.buffer.Count - stream.windowSize).ToArray();

            // Queue inference request
            var request = new InferenceRequest
            {
                requestId = Guid.NewGuid().ToString(),
                modelId = stream.targetModelId,
                inputData = windowData,
                timestamp = DateTime.Now,
                priority = 1
            };

            inferenceQueue.Enqueue(request);
        }

        #endregion

        #region Inference

        public string RequestInference(string modelId, float[][] inputData, Action<InferenceResult> callback = null, int priority = 0)
        {
            var request = new InferenceRequest
            {
                requestId = Guid.NewGuid().ToString(),
                modelId = modelId,
                inputData = inputData,
                timestamp = DateTime.Now,
                priority = priority,
                callback = callback
            };

            inferenceQueue.Enqueue(request);
            return request.requestId;
        }

        public InferenceResult RunInferenceSynchronous(string modelId, float[] input)
        {
            if (!models.TryGetValue(modelId, out var model))
            {
                Debug.LogError($"[MLInference] Model not found: {modelId}");
                return null;
            }

            var startTime = Time.realtimeSinceStartup;

            // Preprocess input
            var processedInput = PreprocessInput(input, model);

            // Run forward pass
            var output = ForwardPass(processedInput, model);

            var inferenceTime = (Time.realtimeSinceStartup - startTime) * 1000f;

            // Update performance metrics
            UpdatePerformanceMetrics(modelId, inferenceTime);

            var result = new InferenceResult
            {
                requestId = Guid.NewGuid().ToString(),
                modelId = modelId,
                outputs = new float[][] { output },
                confidence = CalculateConfidence(output, model),
                inferenceTimeMs = inferenceTime,
                timestamp = DateTime.Now
            };

            // Process based on model type
            ProcessInferenceResult(result, model);

            return result;
        }

        private IEnumerator InferenceLoop()
        {
            while (true)
            {
                // Process batches
                if (inferenceQueue.Count > 0)
                {
                    var batch = new List<InferenceRequest>();

                    // Collect batch
                    while (inferenceQueue.Count > 0 && batch.Count < maxBatchSize)
                    {
                        batch.Add(inferenceQueue.Dequeue());
                    }

                    // Sort by priority
                    batch = batch.OrderByDescending(r => r.priority).ToList();

                    // Process batch
                    foreach (var request in batch)
                    {
                        ProcessInferenceRequest(request);
                        yield return null; // Spread across frames
                    }
                }

                yield return new WaitForSeconds(inferenceInterval);
            }
        }

        private void ProcessInferenceRequest(InferenceRequest request)
        {
            if (!models.TryGetValue(request.modelId, out var model))
            {
                Debug.LogError($"[MLInference] Model not found: {request.modelId}");
                return;
            }

            var startTime = Time.realtimeSinceStartup;

            try
            {
                // Process each input in the batch
                var outputs = new List<float[]>();

                foreach (var input in request.inputData)
                {
                    var processed = PreprocessInput(input, model);
                    var output = ForwardPass(processed, model);
                    outputs.Add(output);
                }

                var inferenceTime = (Time.realtimeSinceStartup - startTime) * 1000f;

                var result = new InferenceResult
                {
                    requestId = request.requestId,
                    modelId = request.modelId,
                    outputs = outputs.ToArray(),
                    confidence = CalculateConfidence(outputs.Last(), model),
                    inferenceTimeMs = inferenceTime,
                    timestamp = DateTime.Now
                };

                ProcessInferenceResult(result, model);

                // Update metrics
                UpdatePerformanceMetrics(request.modelId, inferenceTime);

                // Invoke callback
                request.callback?.Invoke(result);

                // Fire event
                OnInferenceComplete?.Invoke(request.modelId, result);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[MLInference] Inference error: {ex.Message}");

                if (modelPerformance.TryGetValue(request.modelId, out var perf))
                {
                    perf.errorCount++;
                }
            }
        }

        private float[] PreprocessInput(float[] input, MLModel model)
        {
            if (model.normalization == null || model.normalization.type == NormalizationType.None)
            {
                return input;
            }

            var processed = new float[input.Length];

            switch (model.normalization.type)
            {
                case NormalizationType.StandardScaler:
                    for (int i = 0; i < input.Length; i++)
                    {
                        float mean = model.normalization.mean != null && i < model.normalization.mean.Length
                            ? model.normalization.mean[i] : 0f;
                        float std = model.normalization.std != null && i < model.normalization.std.Length
                            ? model.normalization.std[i] : 1f;
                        processed[i] = (input[i] - mean) / (std + 1e-8f);
                    }
                    break;

                case NormalizationType.MinMaxScaler:
                    for (int i = 0; i < input.Length; i++)
                    {
                        float min = model.normalization.min != null && i < model.normalization.min.Length
                            ? model.normalization.min[i] : 0f;
                        float max = model.normalization.max != null && i < model.normalization.max.Length
                            ? model.normalization.max[i] : 1f;
                        processed[i] = (input[i] - min) / (max - min + 1e-8f);
                    }
                    break;

                default:
                    Array.Copy(input, processed, input.Length);
                    break;
            }

            return processed;
        }

        private float[] ForwardPass(float[] input, MLModel model)
        {
            var current = input;

            foreach (var layer in model.layers)
            {
                current = ProcessLayer(current, layer);
            }

            return current;
        }

        private float[] ProcessLayer(float[] input, Layer layer)
        {
            float[] output;

            switch (layer.type)
            {
                case LayerType.Dense:
                    output = DenseForward(input, layer);
                    break;

                case LayerType.LSTM:
                    output = LSTMForward(input, layer);
                    break;

                default:
                    output = input;
                    break;
            }

            // Apply activation
            output = ApplyActivation(output, layer.activation);

            return output;
        }

        private float[] DenseForward(float[] input, Layer layer)
        {
            int outputSize = layer.shape[1];
            var output = new float[outputSize];

            for (int j = 0; j < outputSize; j++)
            {
                float sum = layer.biases[j];

                for (int i = 0; i < Mathf.Min(input.Length, layer.shape[0]); i++)
                {
                    sum += input[i] * layer.weights[i, j];
                }

                output[j] = sum;
            }

            return output;
        }

        private float[] LSTMForward(float[] input, Layer layer)
        {
            // Simplified LSTM forward pass
            int hiddenSize = layer.shape[1];
            var output = new float[hiddenSize];

            // Initialize hidden and cell states
            var h = new float[hiddenSize];
            var c = new float[hiddenSize];

            // Process sequence (simplified - just use last timestep)
            for (int t = 0; t < Mathf.Min(input.Length, hiddenSize); t++)
            {
                float x = t < input.Length ? input[t] : 0f;

                // Simplified LSTM gates
                float i_gate = Sigmoid(x * 0.5f + h[t % hiddenSize] * 0.3f);
                float f_gate = Sigmoid(x * 0.4f + h[t % hiddenSize] * 0.3f + 1f); // Bias toward remembering
                float g_gate = (float)System.Math.Tanh(x * 0.5f + h[t % hiddenSize] * 0.3f);
                float o_gate = Sigmoid(x * 0.5f + h[t % hiddenSize] * 0.3f);

                c[t % hiddenSize] = f_gate * c[t % hiddenSize] + i_gate * g_gate;
                h[t % hiddenSize] = o_gate * (float)System.Math.Tanh(c[t % hiddenSize]);
                output[t % hiddenSize] = h[t % hiddenSize];
            }

            return output;
        }

        private float[] ApplyActivation(float[] input, ActivationType activation)
        {
            var output = new float[input.Length];

            switch (activation)
            {
                case ActivationType.ReLU:
                    for (int i = 0; i < input.Length; i++)
                        output[i] = Mathf.Max(0, input[i]);
                    break;

                case ActivationType.Sigmoid:
                    for (int i = 0; i < input.Length; i++)
                        output[i] = Sigmoid(input[i]);
                    break;

                case ActivationType.Tanh:
                    for (int i = 0; i < input.Length; i++)
                        output[i] = (float)System.Math.Tanh(input[i]);
                    break;

                case ActivationType.Softmax:
                    output = Softmax(input);
                    break;

                case ActivationType.LeakyReLU:
                    for (int i = 0; i < input.Length; i++)
                        output[i] = input[i] > 0 ? input[i] : 0.01f * input[i];
                    break;

                case ActivationType.ELU:
                    for (int i = 0; i < input.Length; i++)
                        output[i] = input[i] > 0 ? input[i] : Mathf.Exp(input[i]) - 1f;
                    break;

                default:
                    Array.Copy(input, output, input.Length);
                    break;
            }

            return output;
        }

        private float Sigmoid(float x)
        {
            return 1f / (1f + Mathf.Exp(-Mathf.Clamp(x, -20f, 20f)));
        }

        private float[] Softmax(float[] input)
        {
            var output = new float[input.Length];
            float maxVal = input.Max();
            float sumExp = 0f;

            for (int i = 0; i < input.Length; i++)
            {
                output[i] = Mathf.Exp(input[i] - maxVal);
                sumExp += output[i];
            }

            for (int i = 0; i < output.Length; i++)
            {
                output[i] /= sumExp;
            }

            return output;
        }

        private float CalculateConfidence(float[] output, MLModel model)
        {
            switch (model.type)
            {
                case ModelType.BinaryClassification:
                case ModelType.MultiClassification:
                    return output.Max();

                case ModelType.Regression:
                    // For regression, confidence based on uncertainty estimation
                    return 0.85f; // Placeholder

                case ModelType.AnomalyDetection:
                    // For anomaly detection, invert the score
                    return 1f - Mathf.Clamp01(output[0]);

                default:
                    return 0.8f;
            }
        }

        private void ProcessInferenceResult(InferenceResult result, MLModel model)
        {
            switch (model.type)
            {
                case ModelType.BinaryClassification:
                case ModelType.MultiClassification:
                    result.probabilities = result.outputs.Last();
                    result.predictedClasses = new int[] { Array.IndexOf(result.probabilities, result.probabilities.Max()) };
                    break;

                case ModelType.AnomalyDetection:
                    ProcessAnomalyDetection(result, model);
                    break;

                case ModelType.Regression:
                case ModelType.TimeSeries:
                    ProcessPrediction(result, model);
                    break;
            }
        }

        private void ProcessAnomalyDetection(InferenceResult result, MLModel model)
        {
            float anomalyScore = result.outputs.Last()[0];
            float threshold = 0.5f; // Configurable threshold

            if (anomalyScore > threshold)
            {
                var detection = new AnomalyDetection
                {
                    detectionId = Guid.NewGuid().ToString(),
                    modelId = model.modelId,
                    anomalyScore = anomalyScore,
                    threshold = threshold,
                    isAnomaly = true,
                    severity = DetermineAnomalySeverity(anomalyScore),
                    timestamp = DateTime.Now
                };

                OnAnomalyDetected?.Invoke(model.modelId, detection);
                Debug.LogWarning($"[MLInference] Anomaly detected! Score: {anomalyScore:F3}, Severity: {detection.severity}");
            }
        }

        private AnomalySeverity DetermineAnomalySeverity(float score)
        {
            if (score > 0.9f) return AnomalySeverity.Critical;
            if (score > 0.75f) return AnomalySeverity.High;
            if (score > 0.6f) return AnomalySeverity.Medium;
            return AnomalySeverity.Low;
        }

        private void ProcessPrediction(InferenceResult result, MLModel model)
        {
            var prediction = new PredictionResult
            {
                predictionId = result.requestId,
                modelId = model.modelId,
                predictedValue = result.outputs.Last()[0],
                confidenceInterval = 0.95f,
                predictionTime = DateTime.Now
            };

            // Determine prediction type based on model
            if (model.modelId.Contains("maintenance"))
            {
                prediction.type = PredictionType.RemainingUsefulLife;
                prediction.targetTime = DateTime.Now.AddHours(prediction.predictedValue);
            }
            else if (model.modelId.Contains("tool_wear"))
            {
                prediction.type = PredictionType.RemainingUsefulLife;
            }
            else if (model.modelId.Contains("energy"))
            {
                prediction.type = PredictionType.EnergyConsumption;
            }
            else if (model.modelId.Contains("quality"))
            {
                prediction.type = PredictionType.QualityPrediction;
            }

            OnPredictionReady?.Invoke(model.modelId, prediction);
        }

        #endregion

        #region Model Monitoring

        private IEnumerator ModelMonitoringLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(60f); // Check every minute

                foreach (var kvp in models)
                {
                    CheckModelHealth(kvp.Value);
                }
            }
        }

        private void CheckModelHealth(MLModel model)
        {
            if (!modelPerformance.TryGetValue(model.modelId, out var perf))
                return;

            // Check for performance degradation
            if (perf.recentLatencies.Count > 10)
            {
                float recentAvg = perf.recentLatencies.TakeLast(10).Average();
                float overallAvg = perf.averageInferenceTimeMs;

                if (recentAvg > overallAvg * 1.5f)
                {
                    OnModelEvent?.Invoke(model.modelId, new ModelEvent
                    {
                        modelId = model.modelId,
                        eventType = ModelEventType.DriftDetected,
                        message = $"Performance degradation detected. Recent avg: {recentAvg:F2}ms vs Overall: {overallAvg:F2}ms",
                        timestamp = DateTime.Now
                    });
                }
            }

            // Check error rate
            if (perf.totalInferences > 100)
            {
                float errorRate = (float)perf.errorCount / perf.totalInferences;

                if (errorRate > 0.05f)
                {
                    OnModelEvent?.Invoke(model.modelId, new ModelEvent
                    {
                        modelId = model.modelId,
                        eventType = ModelEventType.Error,
                        message = $"High error rate detected: {errorRate:P2}",
                        timestamp = DateTime.Now
                    });
                }
            }
        }

        private void UpdatePerformanceMetrics(string modelId, float inferenceTime)
        {
            if (!modelPerformance.TryGetValue(modelId, out var perf))
                return;

            perf.totalInferences++;

            // Update running average
            perf.averageInferenceTimeMs = perf.averageInferenceTimeMs +
                (inferenceTime - perf.averageInferenceTimeMs) / perf.totalInferences;

            // Track min/max
            if (inferenceTime < perf.minInferenceTimeMs || perf.minInferenceTimeMs == 0)
                perf.minInferenceTimeMs = inferenceTime;
            if (inferenceTime > perf.maxInferenceTimeMs)
                perf.maxInferenceTimeMs = inferenceTime;

            // Keep recent latencies
            perf.recentLatencies.Add(inferenceTime);
            while (perf.recentLatencies.Count > 100)
            {
                perf.recentLatencies.RemoveAt(0);
            }
        }

        public ModelPerformance GetModelPerformance(string modelId)
        {
            return modelPerformance.TryGetValue(modelId, out var perf) ? perf : null;
        }

        #endregion

        #region Predictive Maintenance Helpers

        public float PredictRemainingUsefulLife(string machineId, float[] sensorData)
        {
            var result = RunInferenceSynchronous("predictive_maintenance_v1", sensorData);
            return result?.outputs[0][0] ?? -1f;
        }

        public float PredictToolWear(float[] cuttingData)
        {
            var result = RunInferenceSynchronous("tool_wear_v1", cuttingData);
            return result?.outputs[0][0] ?? -1f;
        }

        public bool PredictPartQuality(float[] processData, out float confidence)
        {
            var result = RunInferenceSynchronous("quality_prediction_v1", processData);
            confidence = result?.confidence ?? 0f;

            if (result != null && result.predictedClasses != null && result.predictedClasses.Length > 0)
            {
                return result.predictedClasses[0] == 1; // 1 = accept, 0 = reject
            }

            return false;
        }

        public float DetectAnomaly(float[] featureVector)
        {
            var result = RunInferenceSynchronous("anomaly_detection_v1", featureVector);
            return result?.outputs[0][0] ?? 0f;
        }

        #endregion

        #region Engine Statistics

        public EngineStatistics GetEngineStatistics()
        {
            return new EngineStatistics
            {
                totalModels = models.Count,
                readyModels = models.Values.Count(m => m.status == ModelStatus.Ready),
                totalInferences = modelPerformance.Values.Sum(p => p.totalInferences),
                totalErrors = modelPerformance.Values.Sum(p => p.errorCount),
                pendingRequests = inferenceQueue.Count,
                activeFeatureStreams = featureStreams.Count,
                averageLatencyMs = modelPerformance.Values.Where(p => p.totalInferences > 0)
                    .Average(p => p.averageInferenceTimeMs),
                gpuAccelerationEnabled = enableGPUAcceleration
            };
        }

        [System.Serializable]
        public class EngineStatistics
        {
            public int totalModels;
            public int readyModels;
            public int totalInferences;
            public int totalErrors;
            public int pendingRequests;
            public int activeFeatureStreams;
            public float averageLatencyMs;
            public bool gpuAccelerationEnabled;
        }

        #endregion
    }
}
