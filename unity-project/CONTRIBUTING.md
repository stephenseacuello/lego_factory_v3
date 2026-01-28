# Contributing to CNC SCADA Unity Digital Twin

Internal development guidelines for CNC SCADA Enterprise System developers.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Package Development](#package-development)
- [Commit Guidelines](#commit-guidelines)
- [Review Process](#review-process)

## Development Workflow

### Branch Strategy

We follow **Git Flow** with the following branches:

- `main`: Production-ready code, tagged with version numbers
- `develop`: Integration branch for features
- `feature/*`: Feature development branches
- `bugfix/*`: Bug fix branches
- `hotfix/*`: Emergency production fixes
- `release/*`: Release preparation branches

### Starting a New Feature

```bash
# Update develop branch
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/digital-twin-vrm-export

# Work on feature...

# Push feature branch
git push -u origin feature/digital-twin-vrm-export

# Create pull request to develop
```

### Creating a Release

```bash
# Create release branch
git checkout -b release/v1.1.0 develop

# Update version numbers in:
# - package.json files (all 4 packages)
# - CHANGELOG.md files
# - ARCHITECTURE.md

# Commit version bump
git commit -am "Bump version to v1.1.0"

# Merge to main
git checkout main
git merge release/v1.1.0
git tag v1.1.0

# Merge back to develop
git checkout develop
git merge release/v1.1.0

# Delete release branch
git branch -d release/v1.1.0
```

### Hotfix Process

```bash
# Create hotfix from main
git checkout -b hotfix/emergency-stop-fix main

# Fix the issue
# Update CHANGELOG.md with [1.0.1] section

# Commit
git commit -am "Fix emergency stop validation"

# Merge to main
git checkout main
git merge hotfix/emergency-stop-fix
git tag v1.0.1

# Merge to develop
git checkout develop
git merge hotfix/emergency-stop-fix

# Delete hotfix branch
git branch -d hotfix/emergency-stop-fix
```

## Code Standards

### C# Coding Conventions

Follow Unity's C# coding standards with these additions:

#### Naming Conventions

```csharp
// Public fields: PascalCase
public Transform MachineTransform;

// Private fields: camelCase with underscore
private HttpClient _httpClient;

// Constants: UPPER_SNAKE_CASE
private const float MAX_JOG_SPEED = 10000f;

// Methods: PascalCase with verb
public void UpdateMachineState() { }

// Events: OnPascalCase
public event Action<MachineState> OnStateUpdated;

// Properties: PascalCase
public bool IsConnected { get; private set; }

// Local variables: camelCase
float jogSpeed = 500f;
```

#### File Organization

```csharp
using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Brief description of class purpose
    /// </summary>
    public class ExampleComponent : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";

        #endregion

        #region Private Fields

        private HttpClient _httpClient;

        #endregion

        #region Unity Lifecycle

        void Start() { }
        void Update() { }
        void OnDestroy() { }

        #endregion

        #region Public Methods

        /// <summary>
        /// Public method with XML documentation
        /// </summary>
        public void PublicMethod() { }

        #endregion

        #region Private Methods

        private void PrivateMethod() { }

        #endregion

        #region Events

        public event Action<string> OnError;

        #endregion
    }
}
```

#### SerializeField Usage

```csharp
// ❌ Bad: Public fields expose Unity inspector AND public API
public string flaskServerUrl = "http://localhost:5000";

// ✅ Good: Private with SerializeField
[SerializeField] private string flaskServerUrl = "http://localhost:5000";

// ✅ Also good: Property with backing field
[SerializeField] private string _flaskServerUrl = "http://localhost:5000";
public string FlaskServerUrl
{
    get => _flaskServerUrl;
    set => _flaskServerUrl = value;
}
```

#### Async Patterns

Unity doesn't support async/await well, use coroutines:

```csharp
// ✅ Good: Coroutine pattern
IEnumerator FetchDataAsync()
{
    var request = new HttpRequestMessage(HttpMethod.Get, url);
    var task = httpClient.SendAsync(request);

    while (!task.IsCompleted) yield return null;

    if (task.IsFaulted || task.Result == null)
    {
        Debug.LogError("Request failed");
        yield break;
    }

    // Process result
}

// Usage
StartCoroutine(FetchDataAsync());
```

#### Error Handling

```csharp
// ✅ Good: Always handle errors
try
{
    var data = JsonConvert.DeserializeObject<MachineState>(json);
    OnStateUpdated?.Invoke(data);
}
catch (JsonException e)
{
    Debug.LogError($"[Component] JSON parse error: {e.Message}");
    OnError?.Invoke($"Invalid data format: {e.Message}");
}
```

#### Performance Best Practices

```csharp
// ❌ Bad: Allocating in Update()
void Update()
{
    var temp = new Vector3(x, y, z); // Allocates every frame
}

// ✅ Good: Reuse variables
private Vector3 _tempVector;
void Update()
{
    _tempVector.Set(x, y, z); // No allocation
}

// ❌ Bad: String concatenation in loop
for (int i = 0; i < 1000; i++)
{
    string msg = "Value: " + i;
}

// ✅ Good: StringBuilder
var sb = new StringBuilder();
for (int i = 0; i < 1000; i++)
{
    sb.Append("Value: ").Append(i);
}

// ❌ Bad: GetComponent every frame
void Update()
{
    GetComponent<Renderer>().enabled = true;
}

// ✅ Good: Cache reference
private Renderer _renderer;
void Start()
{
    _renderer = GetComponent<Renderer>();
}
void Update()
{
    _renderer.enabled = true;
}
```

## Testing Requirements

### Minimum Coverage

- **Unit Tests**: 80% code coverage minimum
- **Integration Tests**: All API endpoints
- **Performance Tests**: Critical paths (state updates, command execution)

### Unit Test Example

```csharp
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace CNCScada.DigitalTwin.Tests
{
    [TestFixture]
    public class KinematicsAnimatorTests
    {
        private GameObject _testObject;
        private KinematicsAnimator _animator;

        [SetUp]
        public void SetUp()
        {
            _testObject = new GameObject("Test");
            _animator = _testObject.AddComponent<KinematicsAnimator>();
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(_testObject);
        }

        [Test]
        public void SetTargetPosition_ValidPosition_UpdatesTarget()
        {
            // Arrange
            var expectedPosition = new Vector3(100, 50, 25);

            // Act
            _animator.SetTargetPosition(expectedPosition, Vector3.zero);

            // Assert
            Assert.AreEqual(expectedPosition, _animator.GetTargetPosition());
        }

        [Test]
        public void IsWithinLimits_PositionExceedsXLimit_ReturnsFalse()
        {
            // Arrange
            _animator.xLimits = new Vector2(0, 100);
            _animator.SetTargetPosition(new Vector3(150, 0, 0), Vector3.zero);

            // Act
            bool result = _animator.IsWithinLimits();

            // Assert
            Assert.IsFalse(result);
        }
    }
}
```

### Running Tests

```bash
# Via Unity Editor
Window > General > Test Runner > Run All

# Via Command Line
/Applications/Unity/Hub/Editor/2021.3.x/Unity.app/Contents/MacOS/Unity \
  -runTests \
  -batchmode \
  -projectPath $(pwd) \
  -testResults test-results.xml \
  -testPlatform PlayMode
```

## Documentation

### XML Documentation

All public APIs must have XML documentation:

```csharp
/// <summary>
/// Executes a jog command on the specified axis
/// </summary>
/// <param name="axis">Axis identifier (X, Y, Z, A, B, C)</param>
/// <param name="direction">Direction (-1 for negative, +1 for positive)</param>
/// <param name="speed">Jog speed in mm/min</param>
/// <exception cref="ArgumentException">Thrown when axis is invalid</exception>
/// <returns>True if command was sent successfully, false otherwise</returns>
/// <example>
/// <code>
/// jogController.JogAxis("X", 1.0f, 500f);
/// </code>
/// </example>
public bool JogAxis(string axis, float direction, float speed)
{
    // Implementation
}
```

### README Updates

When adding new features, update package README:

1. Add feature to feature list
2. Add quick start example
3. Update API reference
4. Add troubleshooting section if needed

### CHANGELOG Updates

Follow [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [1.1.0] - 2026-02-01

### Added
- VRM model export for digital twins
- Multi-machine synchronization

### Changed
- Improved toolpath rendering performance by 40%
- Updated state interpolation algorithm

### Fixed
- Fixed memory leak in SensorOverlayRenderer
- Corrected axis limit validation in KinematicsAnimator

### Deprecated
- Old binary protocol (use FlatBuffers instead)

### Removed
- Legacy JSON state format support

### Security
- Fixed XSS vulnerability in MDI console
```

## Package Development

### Creating a New Package

1. **Create Directory Structure**
   ```
   Packages/com.cnc-scada.new-feature/
   ├── Runtime/
   │   ├── Scripts/
   │   ├── CNCScada.NewFeature.asmdef
   │   └── ...
   ├── Editor/
   │   ├── Scripts/
   │   └── CNCScada.NewFeature.Editor.asmdef
   ├── Tests/
   │   ├── Runtime/
   │   └── Editor/
   ├── package.json
   ├── README.md
   ├── CHANGELOG.md
   └── LICENSE.md
   ```

2. **Create package.json**
   ```json
   {
     "name": "com.cnc-scada.new-feature",
     "version": "1.0.0",
     "displayName": "CNC SCADA New Feature",
     "description": "Brief description",
     "unity": "2021.3",
     "dependencies": {
       "com.unity.ugui": "1.0.0"
     }
   }
   ```

3. **Create Assembly Definition**
   ```json
   {
     "name": "CNCScada.NewFeature",
     "rootNamespace": "CNCScada.NewFeature",
     "references": ["CNCScada.Core"],
     "includePlatforms": [],
     "excludePlatforms": [],
     "precompiledReferences": ["Newtonsoft.Json.dll"]
   }
   ```

4. **Add to Setup Wizard**
   - Update `CNCScadaSetupWizard.cs`
   - Add new tab for package
   - Add quick start functionality

### Versioning

Follow [Semantic Versioning](https://semver.org/):

- **Major** (x.0.0): Breaking changes
- **Minor** (0.x.0): New features, backward compatible
- **Patch** (0.0.x): Bug fixes, backward compatible

### Breaking Changes

When making breaking changes:

1. Deprecate old API in minor version
2. Add warning logs
3. Document migration path
4. Remove in next major version

```csharp
[Obsolete("Use SetJogSpeed(float) instead. Will be removed in v2.0.0")]
public void SetSpeed(float speed)
{
    Debug.LogWarning("[JogController] SetSpeed is deprecated, use SetJogSpeed");
    SetJogSpeed(speed);
}

public void SetJogSpeed(float speed)
{
    // New implementation
}
```

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactor (no feature/fix)
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Build/tooling changes

**Examples**:

```
feat(digital-twin): add VRM model export

Implement VRM model export functionality for digital twins.
Supports:
- Texture atlas generation
- Joint hierarchy preservation
- Material conversion

Closes #123
```

```
fix(jog-controller): prevent negative jog speeds

Validate jog speed input to prevent negative values that
could cause unexpected behavior.

Fixes #456
```

```
perf(toolpath): optimize LOD calculation

Reduce LOD calculation overhead by 40% through:
- Caching segment distances
- Early exit for off-screen segments
- Spatial hashing for frustum culling

Benchmark results:
- Before: 15ms for 10k segments
- After: 9ms for 10k segments
```

### Commit Frequency

- Commit frequently (every logical change)
- Each commit should be buildable
- Keep commits focused (one feature/fix per commit)

## Review Process

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added to complex code
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No new warnings

## Screenshots
(if applicable)

## Related Issues
Closes #123
```

### Review Checklist

**Reviewers should verify**:

1. **Functionality**
   - Code works as intended
   - Edge cases handled
   - Error handling present

2. **Code Quality**
   - Follows coding standards
   - No code duplication
   - Appropriate abstractions
   - Performance considerations

3. **Testing**
   - Tests cover new code
   - Tests are meaningful
   - All tests pass

4. **Documentation**
   - XML docs for public APIs
   - README updated if needed
   - CHANGELOG.md updated
   - Complex logic commented

5. **Security**
   - No hardcoded secrets
   - Input validation present
   - No SQL injection risks
   - No XSS vulnerabilities

### Approval Process

- **Required Approvals**: 1 for regular changes, 2 for architectural changes
- **CI Must Pass**: All tests and linters
- **Merge Strategy**: Squash and merge for features, rebase for hotfixes

## Tools and Environment

### Required Tools

- Unity Hub (latest)
- Unity 2021.3 LTS
- Visual Studio Code or Rider
- Git 2.30+

### Recommended Extensions

**VS Code**:
- C# (Microsoft)
- Unity Code Snippets
- Unity Tools
- EditorConfig
- GitLens

**Rider**:
- Unity Support (built-in)
- .NET Core User Secrets

### Unity Packages

Auto-installed via manifest.json:
- TextMesh Pro 3.0.6+
- Unity UI (UGUI)
- Newtonsoft.Json
- Unity Test Framework

## Getting Help

### Internal Resources

- **Slack**: #cnc-scada-unity channel
- **Wiki**: https://internal.cnc-scada.com/wiki/unity
- **Architecture Docs**: See ARCHITECTURE.md in this repo

### Code Review Help

If unsure about architecture decisions:
1. Create draft PR with `[WIP]` prefix
2. Tag @unity-team for early feedback
3. Schedule architecture review meeting

## License Compliance

### Third-Party Code

When adding third-party code:

1. **Check License Compatibility**
   - Must be compatible with proprietary license
   - GPL/AGPL not allowed
   - MIT, Apache 2.0, BSD are OK

2. **Document in THIRD-PARTY-NOTICES.txt**
   ```
   Component: Example Library
   Version: 1.2.3
   License: MIT
   Source: https://github.com/example/library
   ```

3. **Include License File**
   - Copy license to `Packages/<package>/Licenses/`

### Asset Attribution

When using external 3D models, textures, audio:
1. Verify commercial use allowed
2. Document attribution in `Assets/ATTRIBUTION.md`
3. Include required notices

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-15
**Maintained By**: CNC SCADA Development Team

For questions about these guidelines, contact: devops@cnc-scada-enterprise.com
