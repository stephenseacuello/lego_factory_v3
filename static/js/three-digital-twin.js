/**
 * Three.js Digital Twin Visualization
 * ====================================
 * Real-time 3D visualization of CNC machines and robot arms
 *
 * Features:
 * - STL model loading for robots (Niryo Ned2, xArm)
 * - Parametric CNC machine model
 * - Real-time kinematics animation
 * - Health overlays and interactive controls
 */

class DigitalTwinScene {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Container not found:', containerId);
            return;
        }

        // Scene configuration
        this.config = {
            backgroundColor: 0x1a202c,
            gridColor: 0x2c5282,
            ambientLight: 0x404040,
            directionalLight: 0xffffff,
            cameraFOV: 45,
            cameraNear: 0.1,
            cameraFar: 1000
        };

        // Robot state
        this.robots = {};
        this.machines = {};
        this.overlays = [];

        // Animation
        this.animationId = null;
        this.clock = new THREE.Clock();

        this.init();
    }

    init() {
        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.config.backgroundColor);

        // Create camera
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(
            this.config.cameraFOV,
            width / height,
            this.config.cameraNear,
            this.config.cameraFar
        );
        this.camera.position.set(300, 200, 300);
        this.camera.lookAt(0, 50, 0);

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        // Add orbit controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.target.set(0, 50, 0);
        this.controls.update();

        // Add lights
        this.setupLights();

        // Add ground and grid
        this.setupGround();

        // Handle resize
        window.addEventListener('resize', () => this.onResize());

        // Start render loop
        this.animate();

        console.log('Digital Twin Scene initialized');
    }

    setupLights() {
        // Ambient light
        const ambient = new THREE.AmbientLight(this.config.ambientLight, 0.6);
        this.scene.add(ambient);

        // Main directional light (sun)
        const directional = new THREE.DirectionalLight(this.config.directionalLight, 0.8);
        directional.position.set(200, 400, 200);
        directional.castShadow = true;
        directional.shadow.mapSize.width = 2048;
        directional.shadow.mapSize.height = 2048;
        directional.shadow.camera.near = 10;
        directional.shadow.camera.far = 1000;
        directional.shadow.camera.left = -500;
        directional.shadow.camera.right = 500;
        directional.shadow.camera.top = 500;
        directional.shadow.camera.bottom = -500;
        this.scene.add(directional);

        // Fill light
        const fill = new THREE.DirectionalLight(0x8888ff, 0.3);
        fill.position.set(-200, 200, -200);
        this.scene.add(fill);
    }

    setupGround() {
        // Ground plane
        const groundGeometry = new THREE.PlaneGeometry(2000, 2000);
        const groundMaterial = new THREE.MeshStandardMaterial({
            color: 0x2d3748,
            roughness: 0.9,
            metalness: 0.1
        });
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        this.scene.add(ground);

        // Grid
        const grid = new THREE.GridHelper(2000, 40, this.config.gridColor, 0x1a365d);
        grid.position.y = 0.1;
        this.scene.add(grid);
    }

    // =========================================================================
    // Robot Loading
    // =========================================================================

    async loadNiryoNed2(name, position = { x: 0, y: 0, z: 0 }) {
        const basePath = '/3d-models/robots/ned2/';

        const linkNames = [
            'base_link',
            'shoulder_link',
            'arm_link',
            'elbow_link',
            'forearm_link',
            'wrist_link',
            'hand_link'
        ];

        const robot = {
            name: name,
            type: 'niryo_ned2',
            links: [],
            joints: [0, 0, 0, 0, 0, 0],
            position: position,
            group: new THREE.Group()
        };

        robot.group.position.set(position.x, position.y, position.z);

        // Material for robot - Niryo blue/black
        const robotMaterial = new THREE.MeshStandardMaterial({
            color: 0x2c5282,
            roughness: 0.4,
            metalness: 0.6
        });

        // STL scale - Niryo models are in meters, scale to match Bantam (~300)
        const stlScale = 300;

        // Load each link - STL files from URDF
        let loadedCount = 0;
        for (let i = 0; i < linkNames.length; i++) {
            try {
                const geometry = await this.loadSTL(basePath + linkNames[i] + '.stl');
                // Use same rotation as working Bantam: -90° around X
                geometry.rotateX(-Math.PI / 2);

                const mesh = new THREE.Mesh(geometry, robotMaterial.clone());
                mesh.scale.set(stlScale, stlScale, stlScale);
                mesh.castShadow = true;
                mesh.receiveShadow = true;
                mesh.name = linkNames[i];

                const linkGroup = new THREE.Group();
                linkGroup.name = linkNames[i] + '_group';
                linkGroup.add(mesh);

                robot.links.push(linkGroup);
                loadedCount++;
            } catch (e) {
                console.warn(`Failed to load ${linkNames[i]}:`, e);
                const linkGroup = new THREE.Group();
                linkGroup.name = linkNames[i] + '_group';
                robot.links.push(linkGroup);
            }
        }

        console.log(`Loaded ${loadedCount}/${linkNames.length} Niryo Ned2 links`);

        // Build kinematic chain
        this.buildNiryoKinematicChain(robot);

        this.scene.add(robot.group);
        this.robots[name] = robot;

        console.log(`Loaded Niryo Ned2 robot: ${name}`);
        return robot;
    }

    buildNiryoKinematicChain(robot) {
        // URDF STL files are already positioned in world space relative to robot origin
        // All parts should be placed at origin - they will overlap to form the robot
        for (let i = 0; i < robot.links.length; i++) {
            const link = robot.links[i];
            link.position.set(0, 0, 0); // All at origin - STLs have correct vertex positions
            robot.group.add(link);
        }
    }

    async loadXArm(name, position = { x: 0, y: 0, z: 0 }) {
        const basePath = '/3d-models/robots/xarm/';

        const linkNames = [
            'link_base',
            'link1',
            'link2',
            'link3',
            'link4',
            'link5',
            'link6'
        ];

        const robot = {
            name: name,
            type: 'xarm',
            links: [],
            joints: [0, 0, 0, 0, 0, 0],
            position: position,
            group: new THREE.Group()
        };

        robot.group.position.set(position.x, position.y, position.z);

        // Material - silver/white for xArm
        const robotMaterial = new THREE.MeshStandardMaterial({
            color: 0xe0e0e0,
            roughness: 0.3,
            metalness: 0.7
        });

        // STL scale - xArm models are in meters, scale to match Bantam (~300)
        const stlScale = 300;

        // Load each link - STL files from URDF
        let loadedCount = 0;
        for (let i = 0; i < linkNames.length; i++) {
            try {
                const geometry = await this.loadSTL(basePath + linkNames[i] + '.stl');
                // Use same rotation as working Bantam: -90° around X
                geometry.rotateX(-Math.PI / 2);

                const mesh = new THREE.Mesh(geometry, robotMaterial.clone());
                mesh.scale.set(stlScale, stlScale, stlScale);
                mesh.castShadow = true;
                mesh.receiveShadow = true;
                mesh.name = linkNames[i];

                const linkGroup = new THREE.Group();
                linkGroup.name = linkNames[i] + '_group';
                linkGroup.add(mesh);

                robot.links.push(linkGroup);
                loadedCount++;
            } catch (e) {
                console.warn(`Failed to load ${linkNames[i]}:`, e);
                // Add empty placeholder
                const linkGroup = new THREE.Group();
                linkGroup.name = linkNames[i] + '_group';
                robot.links.push(linkGroup);
            }
        }

        console.log(`Loaded ${loadedCount}/${linkNames.length} xArm links`);

        // Build kinematic chain
        this.buildXArmKinematicChain(robot);

        this.scene.add(robot.group);
        this.robots[name] = robot;

        console.log(`Loaded xArm robot: ${name}`);
        return robot;
    }

    buildXArmKinematicChain(robot) {
        // URDF STL files are already positioned in world space relative to robot origin
        // All parts should be placed at origin - they will overlap to form the robot
        for (let i = 0; i < robot.links.length; i++) {
            const link = robot.links[i];
            link.position.set(0, 0, 0); // All at origin - STLs have correct vertex positions
            robot.group.add(link);
        }
    }

    // =========================================================================
    // CNC Machine - Bantam Explorer (STL Models)
    // =========================================================================

    async loadBantamExplorer(name, position = { x: 0, y: 0, z: 0 }) {
        const basePath = '/3d-models/bantam_explorer/';

        const machine = {
            name: name,
            type: 'bantam_explorer',
            position: position,
            state: { x: 0, y: 0, z: 0, spindle: 0 },
            group: new THREE.Group(),
            parts: {},
            config: { width: 200, depth: 150, height: 100, tableHeight: 50 }
        };

        machine.group.position.set(position.x, position.y, position.z);

        // Bantam gray material
        const machineMaterial = new THREE.MeshStandardMaterial({
            color: 0x4a5568,
            roughness: 0.6,
            metalness: 0.4
        });

        // STL scale - Bantam models are in mm, scale to scene units
        const stlScale = 0.3;

        // Load Static frame (enclosure)
        try {
            const staticGeom = await this.loadSTL(basePath + 'Bantam-Tools-Explorer-CNC-Milling-Machine-v1_Static.stl');
            staticGeom.center(); // Center geometry
            staticGeom.rotateX(-Math.PI / 2); // Rotate from Z-up to Y-up
            const staticMesh = new THREE.Mesh(staticGeom, machineMaterial.clone());
            staticMesh.scale.set(stlScale, stlScale, stlScale);
            staticMesh.castShadow = true;
            staticMesh.receiveShadow = true;
            machine.group.add(staticMesh);
            machine.parts.static = staticMesh;
            console.log('Loaded Bantam static frame');
        } catch (e) {
            console.warn('Failed to load Bantam static:', e);
        }

        // Load X-Axis (table moves left/right)
        try {
            const xGeom = await this.loadSTL(basePath + 'Bantam-Tools-Explorer-CNC-Milling-Machine-v1_X-Axis.stl');
            xGeom.center();
            xGeom.rotateX(-Math.PI / 2);
            const xGroup = new THREE.Group();
            const xMesh = new THREE.Mesh(xGeom, machineMaterial.clone());
            xMesh.scale.set(stlScale, stlScale, stlScale);
            xMesh.castShadow = true;
            xGroup.add(xMesh);
            machine.group.add(xGroup);
            machine.parts.xAxis = xGroup;
            console.log('Loaded Bantam X-axis');
        } catch (e) {
            console.warn('Failed to load Bantam X-axis:', e);
        }

        // Load Y-Axis (table moves front/back)
        try {
            const yGeom = await this.loadSTL(basePath + 'Bantam-Tools-Explorer-CNC-Milling-Machine-v1_Y-Axis.stl');
            yGeom.center();
            yGeom.rotateX(-Math.PI / 2);
            const yGroup = new THREE.Group();
            const yMesh = new THREE.Mesh(yGeom, machineMaterial.clone());
            yMesh.scale.set(stlScale, stlScale, stlScale);
            yMesh.castShadow = true;
            yGroup.add(yMesh);
            machine.group.add(yGroup);
            machine.parts.yAxis = yGroup;
            console.log('Loaded Bantam Y-axis');
        } catch (e) {
            console.warn('Failed to load Bantam Y-axis:', e);
        }

        // Load Z-Axis (spindle moves up/down)
        try {
            const zGeom = await this.loadSTL(basePath + 'Bantam-Tools-Explorer-CNC-Milling-Machine-v1_Z-Axis.stl');
            zGeom.center();
            zGeom.rotateX(-Math.PI / 2);
            const zGroup = new THREE.Group();
            const zMesh = new THREE.Mesh(zGeom, new THREE.MeshStandardMaterial({
                color: 0x2c5282,
                roughness: 0.4,
                metalness: 0.6
            }));
            zMesh.scale.set(stlScale, stlScale, stlScale);
            zMesh.castShadow = true;
            zGroup.add(zMesh);
            machine.group.add(zGroup);
            machine.parts.zAxis = zGroup;
            machine.parts.head = zGroup; // Alias for compatibility
            console.log('Loaded Bantam Z-axis');
        } catch (e) {
            console.warn('Failed to load Bantam Z-axis:', e);
        }

        // Position the machine on the ground
        machine.group.position.y = 50;

        // Add status tower light
        this.addStatusLight(machine);

        this.scene.add(machine.group);
        this.machines[name] = machine;

        console.log(`Loaded Bantam Explorer CNC: ${name}`);
        return machine;
    }

    // =========================================================================
    // CNC Machine (Parametric Fallback)
    // =========================================================================

    createCNCMachine(name, position = { x: 0, y: 0, z: 0 }, config = {}) {
        const defaults = {
            width: 400,      // X travel
            depth: 300,      // Y travel
            height: 200,     // Z travel
            tableHeight: 100,
            color: 0x4a5568
        };
        const cfg = { ...defaults, ...config };

        const machine = {
            name: name,
            type: 'cnc_mill',
            config: cfg,
            position: position,
            state: { x: 0, y: 0, z: 0, spindle: 0 },
            group: new THREE.Group(),
            parts: {}
        };

        machine.group.position.set(position.x, position.y, position.z);

        // Materials
        const frameMaterial = new THREE.MeshStandardMaterial({
            color: cfg.color,
            roughness: 0.7,
            metalness: 0.3
        });
        const tableMaterial = new THREE.MeshStandardMaterial({
            color: 0x718096,
            roughness: 0.5,
            metalness: 0.5
        });
        const spindleMaterial = new THREE.MeshStandardMaterial({
            color: 0x1a365d,
            roughness: 0.4,
            metalness: 0.6
        });

        // Base frame
        const baseGeom = new THREE.BoxGeometry(cfg.width + 100, 80, cfg.depth + 100);
        const base = new THREE.Mesh(baseGeom, frameMaterial);
        base.position.y = 40;
        base.castShadow = true;
        base.receiveShadow = true;
        machine.group.add(base);
        machine.parts.base = base;

        // Work table (moves in X/Y)
        const tableGroup = new THREE.Group();
        const tableGeom = new THREE.BoxGeometry(cfg.width - 20, 20, cfg.depth - 20);
        const table = new THREE.Mesh(tableGeom, tableMaterial);
        table.position.y = 10;
        table.castShadow = true;
        table.receiveShadow = true;
        tableGroup.add(table);
        tableGroup.position.y = cfg.tableHeight;
        machine.group.add(tableGroup);
        machine.parts.table = tableGroup;

        // Column (back)
        const columnGeom = new THREE.BoxGeometry(60, cfg.height + 150, 60);
        const column = new THREE.Mesh(columnGeom, frameMaterial);
        column.position.set(0, cfg.tableHeight + (cfg.height + 150) / 2, -cfg.depth / 2 - 30);
        column.castShadow = true;
        column.receiveShadow = true;
        machine.group.add(column);
        machine.parts.column = column;

        // Spindle head (moves in Z)
        const headGroup = new THREE.Group();
        const headGeom = new THREE.BoxGeometry(80, 100, 80);
        const head = new THREE.Mesh(headGeom, spindleMaterial);
        head.position.y = -50;
        head.castShadow = true;
        head.receiveShadow = true;
        headGroup.add(head);

        // Spindle motor
        const motorGeom = new THREE.CylinderGeometry(25, 25, 60, 16);
        const motor = new THREE.Mesh(motorGeom, spindleMaterial);
        motor.position.y = -110;
        motor.castShadow = true;
        headGroup.add(motor);
        machine.parts.motor = motor;

        // Tool holder
        const toolHolderGeom = new THREE.CylinderGeometry(15, 10, 30, 16);
        const toolHolder = new THREE.Mesh(toolHolderGeom, new THREE.MeshStandardMaterial({ color: 0xd69e2e }));
        toolHolder.position.y = -155;
        toolHolder.castShadow = true;
        headGroup.add(toolHolder);

        // End mill tool
        const toolGeom = new THREE.CylinderGeometry(5, 5, 50, 8);
        const tool = new THREE.Mesh(toolGeom, new THREE.MeshStandardMaterial({ color: 0xc53030 }));
        tool.position.y = -195;
        tool.castShadow = true;
        headGroup.add(tool);
        machine.parts.tool = tool;

        headGroup.position.set(0, cfg.tableHeight + cfg.height + 100, -cfg.depth / 2);
        machine.group.add(headGroup);
        machine.parts.head = headGroup;

        // Status tower light
        this.addStatusLight(machine);

        this.scene.add(machine.group);
        this.machines[name] = machine;

        console.log(`Created CNC machine: ${name}`);
        return machine;
    }

    addStatusLight(machine) {
        const lightGroup = new THREE.Group();

        // Pole
        const poleGeom = new THREE.CylinderGeometry(5, 5, 150, 8);
        const pole = new THREE.Mesh(poleGeom, new THREE.MeshStandardMaterial({ color: 0x2d3748 }));
        pole.position.y = 75;
        lightGroup.add(pole);

        // Light segments (red, yellow, green from top)
        const colors = [0xc53030, 0xd69e2e, 0x38a169];
        const lights = [];
        for (let i = 0; i < 3; i++) {
            const lightGeom = new THREE.CylinderGeometry(12, 12, 30, 16);
            const lightMat = new THREE.MeshStandardMaterial({
                color: colors[i],
                emissive: colors[i],
                emissiveIntensity: 0.3
            });
            const light = new THREE.Mesh(lightGeom, lightMat);
            light.position.y = 165 - i * 35;
            lightGroup.add(light);
            lights.push(light);
        }

        machine.parts.statusLights = lights;
        lightGroup.position.set(machine.config.width / 2 + 30, machine.config.tableHeight, 0);
        machine.group.add(lightGroup);
    }

    // =========================================================================
    // Animation
    // =========================================================================

    setRobotJoints(robotName, joints) {
        const robot = this.robots[robotName];
        if (!robot) return;

        robot.joints = joints;

        // Apply joint rotations based on robot type
        if (robot.type === 'niryo_ned2') {
            if (robot.links[1]) robot.links[1].rotation.y = joints[0] || 0;
            if (robot.links[2]) robot.links[2].rotation.z = joints[1] || 0;
            if (robot.links[3]) robot.links[3].rotation.z = joints[2] || 0;
            if (robot.links[4]) robot.links[4].rotation.y = joints[3] || 0;
            if (robot.links[5]) robot.links[5].rotation.z = joints[4] || 0;
            if (robot.links[6]) robot.links[6].rotation.y = joints[5] || 0;
        } else if (robot.type === 'xarm') {
            if (robot.links[1]) robot.links[1].rotation.y = joints[0] || 0;
            if (robot.links[2]) robot.links[2].rotation.z = joints[1] || 0;
            if (robot.links[3]) robot.links[3].rotation.z = joints[2] || 0;
            if (robot.links[4]) robot.links[4].rotation.y = joints[3] || 0;
            if (robot.links[5]) robot.links[5].rotation.z = joints[4] || 0;
            if (robot.links[6]) robot.links[6].rotation.y = joints[5] || 0;
        }
    }

    setMachinePosition(machineName, x, y, z, spindle = 0) {
        const machine = this.machines[machineName];
        if (!machine) return;

        machine.state = { x, y, z, spindle };

        // Handle Bantam Explorer kinematics
        if (machine.type === 'bantam_explorer') {
            if (machine.parts.xAxis) {
                machine.parts.xAxis.position.x = x * 0.5; // Scale factor
            }
            if (machine.parts.yAxis) {
                machine.parts.yAxis.position.z = y * 0.5;
            }
            if (machine.parts.zAxis) {
                machine.parts.zAxis.position.y = -z * 0.5;
            }
        } else {
            // Parametric CNC: Move table (X/Y)
            if (machine.parts.table) {
                machine.parts.table.position.x = x;
                machine.parts.table.position.z = y;
            }

            // Move head (Z)
            if (machine.parts.head) {
                machine.parts.head.position.y = machine.config.tableHeight + machine.config.height + 100 - z;
            }

            // Rotate tool based on spindle RPM
            if (machine.parts.tool && spindle > 0) {
                machine.parts.tool.rotation.y += (spindle / 60) * 0.1; // Visual rotation
            }
        }
    }

    setMachineStatus(machineName, status) {
        const machine = this.machines[machineName];
        if (!machine || !machine.parts.statusLights) return;

        const lights = machine.parts.statusLights;

        // Reset all lights
        lights.forEach(light => {
            light.material.emissiveIntensity = 0.1;
        });

        // Set active light based on status
        switch (status) {
            case 'running':
            case 'active':
                lights[2].material.emissiveIntensity = 1.0; // Green
                break;
            case 'warning':
            case 'paused':
                lights[1].material.emissiveIntensity = 1.0; // Yellow
                break;
            case 'error':
            case 'stopped':
            case 'alarm':
                lights[0].material.emissiveIntensity = 1.0; // Red
                break;
            default:
                lights[1].material.emissiveIntensity = 0.5; // Dim yellow for unknown
        }
    }

    // =========================================================================
    // Utility
    // =========================================================================

    loadSTL(url) {
        return new Promise((resolve, reject) => {
            const loader = new THREE.STLLoader();
            loader.load(
                url,
                (geometry) => {
                    geometry.computeVertexNormals();
                    resolve(geometry);
                },
                undefined,
                (error) => reject(error)
            );
        });
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        const delta = this.clock.getDelta();

        // Update controls
        if (this.controls) {
            this.controls.update();
        }

        // Render
        this.renderer.render(this.scene, this.camera);
    }

    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    // Camera presets
    setCameraView(view) {
        const views = {
            'overview': { pos: [300, 200, 300], target: [0, 50, 0] },
            'front': { pos: [0, 100, 400], target: [0, 50, 0] },
            'side': { pos: [400, 100, 0], target: [0, 50, 0] },
            'top': { pos: [0, 500, 0], target: [0, 0, 0] },
            'close-spindle': { pos: [80, 120, 80], target: [0, 80, 0] }
        };

        const v = views[view];
        if (v) {
            this.camera.position.set(...v.pos);
            this.controls.target.set(...v.target);
            this.controls.update();
        }
    }

    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        this.renderer.dispose();
        if (this.container && this.renderer.domElement) {
            this.container.removeChild(this.renderer.domElement);
        }
    }
}

// Export for use
window.DigitalTwinScene = DigitalTwinScene;
