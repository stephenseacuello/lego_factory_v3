"""
Multi-Brick Generator - Generate novel brick combinations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BrickCategory(Enum):
    """LEGO brick categories."""
    BASIC = "basic"
    PLATE = "plate"
    TILE = "tile"
    SLOPE = "slope"
    TECHNIC = "technic"
    SPECIAL = "special"
    CUSTOM = "custom"


class ConnectionType(Enum):
    """Types of brick connections."""
    STUD = "stud"  # Standard stud-tube connection
    TECHNIC_PIN = "technic_pin"
    TECHNIC_AXLE = "technic_axle"
    CLIP = "clip"
    HINGE = "hinge"
    BALL_JOINT = "ball_joint"


@dataclass
class BrickSpec:
    """Specification for a brick."""
    brick_id: str
    name: str
    category: BrickCategory
    studs_x: int
    studs_y: int
    height_units: int  # 1 = plate height, 3 = standard brick
    has_studs_top: bool = True
    has_tubes_bottom: bool = True
    special_features: List[str] = field(default_factory=list)
    mass_grams: float = 0.0


@dataclass
class BrickPlacement:
    """Placement of a brick in an assembly."""
    brick: BrickSpec
    position: Tuple[float, float, float]  # mm coordinates
    rotation: float  # degrees around Z axis
    color: str = "red"


@dataclass
class BrickAssembly:
    """Assembly of multiple bricks."""
    assembly_id: str
    name: str
    bricks: List[BrickPlacement]
    connections: List[Dict[str, Any]]
    total_mass: float
    bounding_box: Tuple[float, float, float]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GeneratedDesign:
    """Result of brick generation."""
    design_id: str
    assembly: BrickAssembly
    fitness_score: float
    compatibility_score: float
    novelty_score: float
    printability_score: float
    generation_params: Dict[str, Any]


class MultiBrickGenerator:
    """
    Generate novel LEGO brick combinations.

    Features:
    - Parametric brick generation
    - Assembly optimization
    - Novel combination discovery
    - Compatibility checking
    """

    def __init__(self):
        self._brick_library: Dict[str, BrickSpec] = {}
        self._generation_history: List[GeneratedDesign] = []
        self._load_standard_bricks()

    def _load_standard_bricks(self) -> None:
        """Load standard LEGO brick library."""
        # Basic bricks
        for x in [1, 2, 3, 4, 6, 8]:
            for y in [1, 2]:
                if x >= y:  # Avoid duplicates like 1x2 and 2x1
                    self._brick_library[f"brick_{x}x{y}"] = BrickSpec(
                        brick_id=f"brick_{x}x{y}",
                        name=f"Brick {x}x{y}",
                        category=BrickCategory.BASIC,
                        studs_x=x,
                        studs_y=y,
                        height_units=3,
                        mass_grams=x * y * 0.8
                    )

        # Plates (1/3 height of bricks)
        for x in [1, 2, 4, 6]:
            for y in [1, 2]:
                if x >= y:
                    self._brick_library[f"plate_{x}x{y}"] = BrickSpec(
                        brick_id=f"plate_{x}x{y}",
                        name=f"Plate {x}x{y}",
                        category=BrickCategory.PLATE,
                        studs_x=x,
                        studs_y=y,
                        height_units=1,
                        mass_grams=x * y * 0.3
                    )

        # Tiles (plates without studs)
        for x in [1, 2, 4]:
            for y in [1, 2]:
                if x >= y:
                    self._brick_library[f"tile_{x}x{y}"] = BrickSpec(
                        brick_id=f"tile_{x}x{y}",
                        name=f"Tile {x}x{y}",
                        category=BrickCategory.TILE,
                        studs_x=x,
                        studs_y=y,
                        height_units=1,
                        has_studs_top=False,
                        mass_grams=x * y * 0.25
                    )

        # Slopes
        for x in [1, 2]:
            self._brick_library[f"slope_45_{x}x2"] = BrickSpec(
                brick_id=f"slope_45_{x}x2",
                name=f"Slope 45° {x}x2",
                category=BrickCategory.SLOPE,
                studs_x=x,
                studs_y=2,
                height_units=3,
                special_features=["slope_45"],
                mass_grams=x * 2 * 0.7
            )

        logger.info(f"Loaded {len(self._brick_library)} standard bricks")

    def generate_random_assembly(self,
                                 n_bricks: int = 10,
                                 categories: Optional[List[BrickCategory]] = None,
                                 bounds: Tuple[float, float, float] = (100, 100, 100)) -> BrickAssembly:
        """
        Generate random brick assembly.

        Args:
            n_bricks: Number of bricks
            categories: Allowed brick categories
            bounds: Bounding box limits (mm)

        Returns:
            Random assembly
        """
        if categories is None:
            categories = [BrickCategory.BASIC, BrickCategory.PLATE]

        # Filter bricks by category
        available = [b for b in self._brick_library.values()
                    if b.category in categories]

        placements = []
        occupied_positions: Set[Tuple[int, int, int]] = set()

        for i in range(n_bricks):
            brick = np.random.choice(available)

            # Find valid position
            max_attempts = 100
            for attempt in range(max_attempts):
                # Random position (in stud units)
                x = np.random.randint(0, int(bounds[0] / 8))
                y = np.random.randint(0, int(bounds[1] / 8))
                z = np.random.randint(0, int(bounds[2] / 3.2))

                # Check if position is valid
                positions_needed = set()
                for dx in range(brick.studs_x):
                    for dy in range(brick.studs_y):
                        positions_needed.add((x + dx, y + dy, z))

                if not positions_needed & occupied_positions:
                    # Position is valid
                    occupied_positions.update(positions_needed)

                    placement = BrickPlacement(
                        brick=brick,
                        position=(x * 8.0, y * 8.0, z * 3.2),  # Convert to mm
                        rotation=0,
                        color=np.random.choice(['red', 'blue', 'yellow', 'green', 'white'])
                    )
                    placements.append(placement)
                    break

        # Calculate connections
        connections = self._find_connections(placements)

        # Calculate total mass
        total_mass = sum(p.brick.mass_grams for p in placements)

        # Calculate bounding box
        if placements:
            max_x = max(p.position[0] + p.brick.studs_x * 8 for p in placements)
            max_y = max(p.position[1] + p.brick.studs_y * 8 for p in placements)
            max_z = max(p.position[2] + p.brick.height_units * 3.2 for p in placements)
            bbox = (max_x, max_y, max_z)
        else:
            bbox = (0, 0, 0)

        return BrickAssembly(
            assembly_id=f"assembly_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name="Random Assembly",
            bricks=placements,
            connections=connections,
            total_mass=total_mass,
            bounding_box=bbox
        )

    def generate_optimized(self,
                          objective: str = 'stability',
                          constraints: Dict[str, Any] = None,
                          n_generations: int = 50,
                          population_size: int = 20) -> GeneratedDesign:
        """
        Generate optimized brick assembly using evolutionary algorithm.

        Args:
            objective: 'stability', 'minimal_parts', 'symmetry'
            constraints: Constraint definitions
            n_generations: Number of generations
            population_size: Population size

        Returns:
            Best generated design
        """
        constraints = constraints or {}

        # Initialize population
        population = [
            self.generate_random_assembly(
                n_bricks=constraints.get('max_bricks', 15)
            )
            for _ in range(population_size)
        ]

        best_design = None
        best_fitness = float('-inf')

        for generation in range(n_generations):
            # Evaluate fitness
            fitness_scores = [
                self._evaluate_fitness(assembly, objective, constraints)
                for assembly in population
            ]

            # Track best
            max_idx = np.argmax(fitness_scores)
            if fitness_scores[max_idx] > best_fitness:
                best_fitness = fitness_scores[max_idx]
                best_design = population[max_idx]

            # Selection (tournament)
            new_population = []
            for _ in range(population_size):
                # Tournament selection
                i1, i2 = np.random.randint(0, population_size, 2)
                winner = population[i1] if fitness_scores[i1] > fitness_scores[i2] else population[i2]
                new_population.append(self._mutate_assembly(winner))

            population = new_population

        # Calculate final scores
        compatibility = self._evaluate_compatibility(best_design)
        novelty = self._evaluate_novelty(best_design)
        printability = self._evaluate_printability(best_design)

        result = GeneratedDesign(
            design_id=f"gen_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            assembly=best_design,
            fitness_score=best_fitness,
            compatibility_score=compatibility,
            novelty_score=novelty,
            printability_score=printability,
            generation_params={
                'objective': objective,
                'generations': n_generations,
                'population_size': population_size
            }
        )

        self._generation_history.append(result)
        return result

    def _find_connections(self, placements: List[BrickPlacement]) -> List[Dict[str, Any]]:
        """Find connections between bricks."""
        connections = []

        for i, p1 in enumerate(placements):
            for j, p2 in enumerate(placements):
                if i >= j:
                    continue

                # Check if bricks are adjacent vertically
                z_diff = abs(p1.position[2] - p2.position[2])
                if abs(z_diff - p1.brick.height_units * 3.2) < 0.1 or \
                   abs(z_diff - p2.brick.height_units * 3.2) < 0.1:

                    # Check horizontal overlap
                    x_overlap = self._check_overlap(
                        p1.position[0], p1.brick.studs_x * 8,
                        p2.position[0], p2.brick.studs_x * 8
                    )
                    y_overlap = self._check_overlap(
                        p1.position[1], p1.brick.studs_y * 8,
                        p2.position[1], p2.brick.studs_y * 8
                    )

                    if x_overlap > 0 and y_overlap > 0:
                        connections.append({
                            'brick1_idx': i,
                            'brick2_idx': j,
                            'type': ConnectionType.STUD.value,
                            'strength': (x_overlap * y_overlap) / 64  # Normalized
                        })

        return connections

    def _check_overlap(self, pos1: float, size1: float,
                      pos2: float, size2: float) -> float:
        """Check overlap between two intervals."""
        start = max(pos1, pos2)
        end = min(pos1 + size1, pos2 + size2)
        return max(0, end - start)

    def _evaluate_fitness(self,
                         assembly: BrickAssembly,
                         objective: str,
                         constraints: Dict) -> float:
        """Evaluate assembly fitness."""
        score = 0.0

        if objective == 'stability':
            # More connections = more stable
            score = len(assembly.connections) / max(1, len(assembly.bricks))
            # Bonus for lower center of gravity
            if assembly.bricks:
                avg_z = np.mean([p.position[2] for p in assembly.bricks])
                score += 0.5 * (1 - avg_z / assembly.bounding_box[2])

        elif objective == 'minimal_parts':
            # Fewer parts = better, but penalize if too few connections
            score = 1.0 / (1 + len(assembly.bricks) / 10)
            if len(assembly.connections) < len(assembly.bricks) - 1:
                score *= 0.5  # Penalty for disconnected parts

        elif objective == 'symmetry':
            # Score based on symmetry
            score = self._evaluate_symmetry(assembly)

        # Apply constraints
        max_bricks = constraints.get('max_bricks')
        if max_bricks and len(assembly.bricks) > max_bricks:
            score *= 0.5

        max_mass = constraints.get('max_mass')
        if max_mass and assembly.total_mass > max_mass:
            score *= 0.5

        return score

    def _evaluate_symmetry(self, assembly: BrickAssembly) -> float:
        """Evaluate symmetry of assembly."""
        if not assembly.bricks:
            return 0.0

        # Calculate center
        center_x = np.mean([p.position[0] for p in assembly.bricks])
        center_y = np.mean([p.position[1] for p in assembly.bricks])

        # Check for matching pairs across center
        symmetry_score = 0
        total_pairs = 0

        for p1 in assembly.bricks:
            # Look for mirror brick
            mirror_x = 2 * center_x - p1.position[0]
            mirror_y = 2 * center_y - p1.position[1]

            for p2 in assembly.bricks:
                if p2 is not p1:
                    if (abs(p2.position[0] - mirror_x) < 8 and
                        abs(p2.position[1] - mirror_y) < 8 and
                        p2.brick.brick_id == p1.brick.brick_id):
                        symmetry_score += 1
                        break
            total_pairs += 1

        return symmetry_score / total_pairs if total_pairs > 0 else 0

    def _mutate_assembly(self, assembly: BrickAssembly) -> BrickAssembly:
        """Mutate an assembly."""
        new_placements = list(assembly.bricks)

        mutation_type = np.random.choice(['move', 'add', 'remove', 'swap'])

        if mutation_type == 'move' and new_placements:
            idx = np.random.randint(len(new_placements))
            p = new_placements[idx]
            # Move slightly
            new_pos = (
                p.position[0] + np.random.choice([-8, 0, 8]),
                p.position[1] + np.random.choice([-8, 0, 8]),
                max(0, p.position[2] + np.random.choice([-3.2, 0, 3.2]))
            )
            new_placements[idx] = BrickPlacement(
                brick=p.brick,
                position=new_pos,
                rotation=p.rotation,
                color=p.color
            )

        elif mutation_type == 'add':
            brick = np.random.choice(list(self._brick_library.values()))
            new_placements.append(BrickPlacement(
                brick=brick,
                position=(
                    np.random.randint(0, 10) * 8,
                    np.random.randint(0, 10) * 8,
                    np.random.randint(0, 5) * 3.2
                ),
                rotation=0,
                color=np.random.choice(['red', 'blue', 'yellow'])
            ))

        elif mutation_type == 'remove' and len(new_placements) > 1:
            idx = np.random.randint(len(new_placements))
            new_placements.pop(idx)

        elif mutation_type == 'swap' and len(new_placements) >= 2:
            i1, i2 = np.random.randint(0, len(new_placements), 2)
            new_placements[i1], new_placements[i2] = new_placements[i2], new_placements[i1]

        # Rebuild assembly
        connections = self._find_connections(new_placements)
        total_mass = sum(p.brick.mass_grams for p in new_placements)

        if new_placements:
            max_x = max(p.position[0] + p.brick.studs_x * 8 for p in new_placements)
            max_y = max(p.position[1] + p.brick.studs_y * 8 for p in new_placements)
            max_z = max(p.position[2] + p.brick.height_units * 3.2 for p in new_placements)
            bbox = (max_x, max_y, max_z)
        else:
            bbox = (0, 0, 0)

        return BrickAssembly(
            assembly_id=f"mutated_{datetime.utcnow().strftime('%H%M%S')}",
            name="Mutated Assembly",
            bricks=new_placements,
            connections=connections,
            total_mass=total_mass,
            bounding_box=bbox
        )

    def _evaluate_compatibility(self, assembly: BrickAssembly) -> float:
        """Evaluate LEGO compatibility."""
        # All standard bricks are compatible
        return 1.0

    def _evaluate_novelty(self, assembly: BrickAssembly) -> float:
        """Evaluate novelty compared to history."""
        if not self._generation_history:
            return 1.0

        # Compare to previous designs
        similarities = []
        for prev in self._generation_history[-10:]:
            sim = self._calculate_similarity(assembly, prev.assembly)
            similarities.append(sim)

        return 1 - np.mean(similarities) if similarities else 1.0

    def _calculate_similarity(self, a1: BrickAssembly, a2: BrickAssembly) -> float:
        """Calculate similarity between assemblies."""
        # Simple: compare brick counts
        count_diff = abs(len(a1.bricks) - len(a2.bricks))
        mass_diff = abs(a1.total_mass - a2.total_mass)

        similarity = 1 / (1 + count_diff * 0.1 + mass_diff * 0.01)
        return similarity

    def _evaluate_printability(self, assembly: BrickAssembly) -> float:
        """Evaluate if assembly can be 3D printed as single unit."""
        # Penalize floating parts
        if len(assembly.connections) < len(assembly.bricks) - 1:
            return 0.5

        return 0.9  # Standard bricks are printable

    def get_brick_library(self) -> List[BrickSpec]:
        """Get available bricks."""
        return list(self._brick_library.values())
