"""
Digital Twin Module Tests.

Tests for Phase 3 Digital Twin Research components:
- PINN (Physics-Informed Neural Networks)
- Ontology mapping
- Knowledge graphs
- Conflict resolution
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPINNModel(unittest.TestCase):
    """Tests for Physics-Informed Neural Network model."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.digital_twin.ml.pinn_model import (
            PINNConfig, PINNModel, ManufacturingPINN
        )
        self.PINNConfig = PINNConfig
        self.PINNModel = PINNModel
        self.ManufacturingPINN = ManufacturingPINN

    def test_pinn_config_defaults(self):
        """Test PINN configuration defaults."""
        config = self.PINNConfig()

        self.assertEqual(config.input_dim, 4)
        self.assertEqual(config.output_dim, 3)
        self.assertIsInstance(config.hidden_dims, list)
        self.assertGreater(len(config.hidden_dims), 0)

    def test_pinn_model_creation(self):
        """Test PINN model creation."""
        config = self.PINNConfig()
        model = self.PINNModel(config)

        self.assertIsNotNone(model)
        self.assertEqual(model.config.input_dim, 4)

    def test_pinn_forward_pass(self):
        """Test PINN forward pass."""
        config = self.PINNConfig()
        model = self.PINNModel(config)

        # Create sample input
        inputs = {
            "time": 1.0,
            "position": [0.5, 0.5, 0.1],
            "velocity": [0.0, 0.0, 0.01],
        }

        result = model.forward(inputs)

        self.assertIn("output", result)
        self.assertIn("physics_residual", result)

    def test_pinn_physics_loss(self):
        """Test physics-informed loss calculation."""
        config = self.PINNConfig()
        model = self.PINNModel(config)

        inputs = {"time": 1.0, "position": [0.5, 0.5, 0.1]}
        result = model.forward(inputs)

        physics_loss = model.physics_loss(result)

        self.assertIsInstance(physics_loss, float)
        self.assertGreaterEqual(physics_loss, 0.0)

    def test_manufacturing_pinn_thermal(self):
        """Test manufacturing PINN thermal prediction."""
        pinn = self.ManufacturingPINN()

        # Test thermal profile prediction
        result = pinn.predict_thermal_profile(
            layer=10,
            time_step=5.0,
            power=200.0,
            speed=60.0
        )

        self.assertIn("temperature", result)
        self.assertIn("gradient", result)
        self.assertIn("thermal_stress", result)

    def test_manufacturing_pinn_deformation(self):
        """Test manufacturing PINN deformation prediction."""
        pinn = self.ManufacturingPINN()

        result = pinn.predict_deformation(
            layer=15,
            temperature=220.0,
            cooling_rate=5.0
        )

        self.assertIn("warpage", result)
        self.assertIn("shrinkage", result)


class TestOntologyMapper(unittest.TestCase):
    """Tests for ontology mapping functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.digital_twin.ontology.ontology_mapper import (
            OntologyMapper, ManufacturingOntology
        )
        self.OntologyMapper = OntologyMapper
        self.ManufacturingOntology = ManufacturingOntology

    def test_ontology_creation(self):
        """Test ontology mapper creation."""
        mapper = self.OntologyMapper()

        self.assertIsNotNone(mapper)
        self.assertIsInstance(mapper.namespaces, dict)

    def test_add_concept(self):
        """Test adding concept to ontology."""
        mapper = self.OntologyMapper()

        result = mapper.add_concept(
            uri="http://example.org/Machine",
            label="Machine",
            definition="Manufacturing machine asset"
        )

        self.assertTrue(result["success"])
        self.assertIn("Machine", mapper.concepts)

    def test_add_relationship(self):
        """Test adding relationship between concepts."""
        mapper = self.OntologyMapper()

        # Add concepts first
        mapper.add_concept("http://example.org/Machine", "Machine", "")
        mapper.add_concept("http://example.org/Part", "Part", "")

        result = mapper.add_relationship(
            subject="Machine",
            predicate="produces",
            obj="Part"
        )

        self.assertTrue(result["success"])

    def test_manufacturing_ontology(self):
        """Test manufacturing ontology with standard concepts."""
        ontology = self.ManufacturingOntology()

        # Check for ISO 23247 concepts
        concepts = ontology.get_concepts()

        self.assertIn("DigitalTwin", concepts)
        self.assertIn("PhysicalAsset", concepts)
        self.assertIn("ManufacturingProcess", concepts)

    def test_sparql_query(self):
        """Test SPARQL query execution."""
        ontology = self.ManufacturingOntology()

        query = "SELECT ?s WHERE { ?s rdf:type :Machine }"
        result = ontology.query(query)

        self.assertIsInstance(result, dict)
        self.assertIn("results", result)


class TestKnowledgeGraph(unittest.TestCase):
    """Tests for knowledge graph functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.digital_twin.ontology.knowledge_graph import (
            KnowledgeGraph, ManufacturingKnowledgeGraph
        )
        self.KnowledgeGraph = KnowledgeGraph
        self.ManufacturingKnowledgeGraph = ManufacturingKnowledgeGraph

    def test_graph_creation(self):
        """Test knowledge graph creation."""
        graph = self.KnowledgeGraph()

        self.assertIsNotNone(graph)
        self.assertEqual(graph.node_count(), 0)

    def test_add_node(self):
        """Test adding node to graph."""
        graph = self.KnowledgeGraph()

        result = graph.add_node(
            node_id="machine_001",
            node_type="Machine",
            properties={"name": "Printer 1", "status": "active"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(graph.node_count(), 1)

    def test_add_edge(self):
        """Test adding edge between nodes."""
        graph = self.KnowledgeGraph()

        graph.add_node("machine_001", "Machine", {})
        graph.add_node("part_001", "Part", {})

        result = graph.add_edge(
            source="machine_001",
            target="part_001",
            relationship="produces"
        )

        self.assertTrue(result["success"])
        self.assertEqual(graph.edge_count(), 1)

    def test_find_path(self):
        """Test finding path between nodes."""
        graph = self.KnowledgeGraph()

        # Create chain: machine -> process -> part
        graph.add_node("machine", "Machine", {})
        graph.add_node("process", "Process", {})
        graph.add_node("part", "Part", {})

        graph.add_edge("machine", "process", "executes")
        graph.add_edge("process", "part", "produces")

        path = graph.find_path("machine", "part")

        self.assertIsNotNone(path)
        self.assertEqual(len(path), 3)

    def test_manufacturing_knowledge_graph(self):
        """Test manufacturing knowledge graph with assets."""
        mkg = self.ManufacturingKnowledgeGraph()

        # Register asset
        result = mkg.register_asset(
            asset_id="printer_001",
            asset_type="3DPrinter",
            properties={
                "make": "Prusa",
                "model": "MK4",
                "location": "Lab A"
            }
        )

        self.assertTrue(result["success"])

        # Query asset
        asset = mkg.get_asset("printer_001")
        self.assertEqual(asset["properties"]["make"], "Prusa")


class TestConflictResolver(unittest.TestCase):
    """Tests for CRDT-based conflict resolution."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.digital_twin.sync.conflict_resolver import (
            ConflictResolver, CRDTType, VectorClock
        )
        self.ConflictResolver = ConflictResolver
        self.CRDTType = CRDTType
        self.VectorClock = VectorClock

    def test_vector_clock_creation(self):
        """Test vector clock creation."""
        clock = self.VectorClock()

        self.assertEqual(clock.get_time("node1"), 0)

    def test_vector_clock_increment(self):
        """Test vector clock increment."""
        clock = self.VectorClock()

        clock.increment("node1")
        clock.increment("node1")

        self.assertEqual(clock.get_time("node1"), 2)

    def test_vector_clock_comparison(self):
        """Test vector clock comparison."""
        clock1 = self.VectorClock()
        clock2 = self.VectorClock()

        clock1.increment("node1")
        clock2.increment("node1")
        clock2.increment("node1")

        self.assertTrue(clock1 < clock2)

    def test_lww_register(self):
        """Test Last-Writer-Wins register."""
        resolver = self.ConflictResolver()

        result1 = resolver.update(
            key="sensor_value",
            value=100.0,
            timestamp=datetime.now() - timedelta(seconds=10),
            source="sensor_1"
        )

        result2 = resolver.update(
            key="sensor_value",
            value=105.0,
            timestamp=datetime.now(),
            source="sensor_2"
        )

        current = resolver.get("sensor_value")

        self.assertEqual(current, 105.0)  # Later timestamp wins

    def test_g_counter(self):
        """Test Grow-only counter CRDT."""
        resolver = self.ConflictResolver(self.CRDTType.G_COUNTER)

        resolver.increment("count", "node1", 5)
        resolver.increment("count", "node2", 3)

        total = resolver.get("count")

        self.assertEqual(total, 8)

    def test_conflict_detection(self):
        """Test concurrent update conflict detection."""
        resolver = self.ConflictResolver()

        # Simulate concurrent updates
        same_time = datetime.now()

        resolver.update("value", 10, same_time, "node1")
        result = resolver.update("value", 20, same_time, "node2")

        self.assertTrue(result.get("conflict_detected", False))


class TestStateEventSourcing(unittest.TestCase):
    """Tests for event sourcing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.digital_twin.sync.event_sourcing import (
            Event, EventStore, EventSourcedAggregate
        )
        self.Event = Event
        self.EventStore = EventStore
        self.EventSourcedAggregate = EventSourcedAggregate

    def test_event_creation(self):
        """Test event creation."""
        event = self.Event(
            event_type="MachineStarted",
            aggregate_id="machine_001",
            data={"operator": "John", "program": "part_123"}
        )

        self.assertIsNotNone(event.event_id)
        self.assertIsNotNone(event.timestamp)

    def test_event_store_append(self):
        """Test appending events to store."""
        store = self.EventStore()

        event = self.Event(
            event_type="PartCreated",
            aggregate_id="part_001",
            data={"type": "bracket", "material": "PLA"}
        )

        result = store.append(event)

        self.assertTrue(result["success"])
        self.assertEqual(store.event_count(), 1)

    def test_event_store_replay(self):
        """Test event replay for aggregate reconstruction."""
        store = self.EventStore()

        # Add events
        events = [
            self.Event("PartCreated", "part_001", {"type": "bracket"}),
            self.Event("PartUpdated", "part_001", {"status": "printing"}),
            self.Event("PartCompleted", "part_001", {"quality": "pass"}),
        ]

        for event in events:
            store.append(event)

        # Replay
        replayed = store.get_events("part_001")

        self.assertEqual(len(replayed), 3)
        self.assertEqual(replayed[-1].event_type, "PartCompleted")

    def test_event_sourced_aggregate(self):
        """Test event-sourced aggregate pattern."""

        class PartAggregate(self.EventSourcedAggregate):
            def __init__(self):
                super().__init__()
                self.status = "created"
                self.quality = None

            def apply_PartCreated(self, event):
                self.status = "created"

            def apply_PartCompleted(self, event):
                self.status = "completed"
                self.quality = event.data.get("quality")

        aggregate = PartAggregate()

        events = [
            self.Event("PartCreated", "part_001", {}),
            self.Event("PartCompleted", "part_001", {"quality": "A"}),
        ]

        for event in events:
            aggregate.apply(event)

        self.assertEqual(aggregate.status, "completed")
        self.assertEqual(aggregate.quality, "A")


if __name__ == "__main__":
    unittest.main()
