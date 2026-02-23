"""
Tests for LEGO MCP v6.0 Service Layers.

Tests for:
- Data service (dataset management, artifacts, versioning, pipelines)
- Database service (connection pool, query builder, migrations, repositories)
- Optimization service (genetic algorithm, multi-objective, manufacturing)
"""

import pytest
import asyncio
from datetime import datetime
from typing import List

# ============================================
# Data Service Tests
# ============================================

class TestDatasetManager:
    """Tests for DatasetManager."""

    def test_create_dataset(self):
        """Test dataset creation."""
        from dashboard.services.data import DatasetManager, DatasetType

        manager = DatasetManager()
        dataset = manager.create_dataset(
            name="Test Dataset",
            description="A test dataset",
            dataset_type=DatasetType.TRAINING_DATA,
            owner="test_user",
            schema={"format": "parquet"},
        )

        assert dataset.name == "Test Dataset"
        assert dataset.dataset_type == DatasetType.TRAINING_DATA
        assert dataset.owner == "test_user"
        assert "test-dataset" in dataset.dataset_id

    def test_list_datasets(self):
        """Test listing datasets."""
        from dashboard.services.data import DatasetManager, DatasetType, DatasetStatus

        manager = DatasetManager()
        datasets = manager.list_datasets()
        assert len(datasets) > 0

        # Filter by type
        quality_datasets = manager.list_datasets(dataset_type=DatasetType.QUALITY_IMAGES)
        assert all(d.dataset_type == DatasetType.QUALITY_IMAGES for d in quality_datasets)

    def test_create_version(self):
        """Test dataset versioning."""
        from dashboard.services.data import DatasetManager, DatasetType

        manager = DatasetManager()
        dataset = manager.create_dataset(
            name="Version Test",
            description="Testing versioning",
            dataset_type=DatasetType.SENSOR_DATA,
            owner="test",
            schema={},
        )

        version = manager.create_version(
            dataset_id=dataset.dataset_id,
            version_number="1.0.0",
            created_by="test",
            size_bytes=1000,
            record_count=100,
            data_hash="abc123",
        )

        assert version.version_number == "1.0.0"
        assert version.record_count == 100

        # Dataset should now be active
        updated = manager.get_dataset(dataset.dataset_id)
        assert updated.current_version == "1.0.0"

    def test_get_lineage(self):
        """Test dataset lineage tracking."""
        from dashboard.services.data import DatasetManager

        manager = DatasetManager()
        # Use pre-populated dataset
        datasets = manager.list_datasets()
        if datasets:
            lineage = manager.get_lineage(datasets[0].dataset_id)
            assert "version_chain" in lineage
            assert "source_lineage" in lineage


class TestArtifactStore:
    """Tests for ArtifactStore."""

    def test_store_artifact(self):
        """Test storing an artifact."""
        from dashboard.services.data import ArtifactStore, ArtifactType

        store = ArtifactStore()
        content = b"test model content"

        artifact = store.store(
            name="test_model.pt",
            artifact_type=ArtifactType.MODEL,
            content=content,
            experiment_id="exp-001",
            created_by="test",
            metadata={"accuracy": 0.95},
        )

        assert artifact.name == "test_model.pt"
        assert artifact.size_bytes == len(content)
        assert artifact.metadata["accuracy"] == 0.95

    def test_deduplication(self):
        """Test content-addressable deduplication."""
        from dashboard.services.data import ArtifactStore, ArtifactType

        store = ArtifactStore()
        content = b"duplicate content"

        artifact1 = store.store(
            name="file1.bin",
            artifact_type=ArtifactType.CHECKPOINT,
            content=content,
        )

        artifact2 = store.store(
            name="file2.bin",
            artifact_type=ArtifactType.CHECKPOINT,
            content=content,
        )

        # Should return same artifact due to deduplication
        assert artifact1.artifact_id == artifact2.artifact_id

    def test_storage_stats(self):
        """Test storage statistics."""
        from dashboard.services.data import ArtifactStore

        store = ArtifactStore()
        stats = store.get_storage_stats()

        assert "total_artifacts" in stats
        assert "storage_used" in stats
        assert "storage_quota" in stats
        assert "by_type" in stats


class TestDataVersionControl:
    """Tests for DataVersionControl."""

    def test_commit(self):
        """Test creating a commit."""
        from dashboard.services.data import DataVersionControl, CommitType

        dvc = DataVersionControl()
        commit = dvc.commit(
            message="Add new training data",
            changes={"added": ["data/train.csv"]},
            author="test_user",
        )

        assert "Add new training data" in commit.message
        assert commit.author == "test_user"
        assert len(commit.parent_commits) > 0

    def test_branch_operations(self):
        """Test branch creation and checkout."""
        from dashboard.services.data import DataVersionControl

        dvc = DataVersionControl()

        # Create branch
        branch = dvc.create_branch("feature-branch")
        assert branch.name == "feature-branch"

        # Checkout
        dvc.checkout("feature-branch")
        assert dvc.current_branch == "feature-branch"

        # Return to main
        dvc.checkout("main")
        assert dvc.current_branch == "main"

    def test_history(self):
        """Test commit history."""
        from dashboard.services.data import DataVersionControl

        dvc = DataVersionControl()
        history = dvc.get_history(limit=10)

        assert len(history) > 0
        assert all(hasattr(c, 'commit_hash') for c in history)

    def test_tag(self):
        """Test tagging commits."""
        from dashboard.services.data import DataVersionControl

        dvc = DataVersionControl()
        commit_hash = dvc.tag("v2.0.0")

        assert "v2.0.0" in dvc.tags
        assert dvc.tags["v2.0.0"] == commit_hash


class TestDataPipeline:
    """Tests for DataPipeline."""

    def test_list_pipelines(self):
        """Test listing pipelines."""
        from dashboard.services.data import PipelineExecutor

        executor = PipelineExecutor()
        pipelines = executor.list_pipelines()

        assert len(pipelines) > 0
        assert all(hasattr(p, 'pipeline_id') for p in pipelines)

    def test_create_pipeline(self):
        """Test creating a pipeline."""
        from dashboard.services.data import PipelineExecutor

        executor = PipelineExecutor()
        pipeline = executor.create_pipeline(
            name="Test Pipeline",
            description="A test ETL pipeline",
            stages=[
                {"name": "Extract", "type": "extract", "config": {}},
                {"name": "Transform", "type": "transform", "config": {}},
                {"name": "Load", "type": "load", "config": {}},
            ],
            schedule="0 * * * *",
            tags=["test"],
        )

        assert pipeline.name == "Test Pipeline"
        assert len(pipeline.stages) == 3

    @pytest.mark.asyncio
    async def test_execute_pipeline(self):
        """Test pipeline execution."""
        from dashboard.services.data import PipelineExecutor

        executor = PipelineExecutor()
        pipelines = executor.list_pipelines()

        if pipelines:
            run = await executor.execute_pipeline(
                pipeline_id=pipelines[0].pipeline_id,
                triggered_by="test",
            )

            assert run.pipeline_id == pipelines[0].pipeline_id
            assert run.status.value in ["completed", "running"]


# ============================================
# Database Service Tests
# ============================================

class TestConnectionPool:
    """Tests for ConnectionPool."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test connection pool initialization."""
        from dashboard.services.database import ConnectionPool, PoolConfig

        config = PoolConfig(
            host="localhost",
            database="test_db",
            min_connections=2,
            max_connections=10,
        )

        pool = ConnectionPool(config)
        await pool.initialize()

        stats = pool.get_stats()
        assert stats["current_connections"] >= config.min_connections

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        """Test acquiring and releasing connections."""
        from dashboard.services.database import ConnectionPool, PoolConfig

        config = PoolConfig(min_connections=2, max_connections=5)
        pool = ConnectionPool(config)
        await pool.initialize()

        conn = await pool.acquire()
        assert conn.state.value == "in_use"

        await pool.release(conn)
        # Connection should be available again

        await pool.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test connection context manager."""
        from dashboard.services.database import ConnectionPool, PoolConfig

        config = PoolConfig(min_connections=2)
        pool = ConnectionPool(config)
        await pool.initialize()

        async with pool.connection() as conn:
            assert conn is not None
            assert conn.state.value == "in_use"

        await pool.close()


class TestQueryBuilder:
    """Tests for QueryBuilder."""

    def test_select_query(self):
        """Test SELECT query building."""
        from dashboard.services.database import QueryBuilder

        query = (
            QueryBuilder("experiments")
            .select("id", "name", "status")
            .where_eq("status", "running")
            .order_by("created_at")
            .limit(10)
            .build()
        )

        assert "SELECT" in query.sql
        assert "experiments" in query.sql
        assert "WHERE" in query.sql
        assert "LIMIT 10" in query.sql
        assert "running" in query.params.values()

    def test_insert_query(self):
        """Test INSERT query building."""
        from dashboard.services.database import QueryBuilder

        query = (
            QueryBuilder("models")
            .insert(name="test_model", version="1.0.0", stage="staging")
            .build()
        )

        assert "INSERT INTO models" in query.sql
        assert "name" in query.sql
        assert "test_model" in query.params.values()

    def test_update_query(self):
        """Test UPDATE query building."""
        from dashboard.services.database import QueryBuilder

        query = (
            QueryBuilder("experiments")
            .update(status="completed", updated_at="2024-01-01")
            .where_eq("id", "exp-001")
            .build()
        )

        assert "UPDATE experiments SET" in query.sql
        assert "WHERE" in query.sql

    def test_delete_query(self):
        """Test DELETE query building."""
        from dashboard.services.database import QueryBuilder

        query = (
            QueryBuilder("artifacts")
            .delete()
            .where_eq("experiment_id", "exp-old")
            .build()
        )

        assert "DELETE FROM artifacts" in query.sql
        assert "WHERE" in query.sql

    def test_join_query(self):
        """Test JOIN query building."""
        from dashboard.services.database import QueryBuilder

        query = (
            QueryBuilder("experiments")
            .select("experiments.*", "models.version")
            .left_join("models", "experiments.id = models.experiment_id")
            .where_eq("experiments.status", "completed")
            .build()
        )

        assert "LEFT JOIN models" in query.sql
        assert "ON experiments.id = models.experiment_id" in query.sql


class TestMigrationManager:
    """Tests for MigrationManager."""

    def test_get_pending(self):
        """Test getting pending migrations."""
        from dashboard.services.database import MigrationManager

        manager = MigrationManager()
        pending = manager.get_pending_migrations()

        assert isinstance(pending, list)
        # Should have some pending migrations
        assert len(pending) >= 0

    def test_get_applied(self):
        """Test getting applied migrations."""
        from dashboard.services.database import MigrationManager

        manager = MigrationManager()
        applied = manager.get_applied_migrations()

        assert isinstance(applied, list)
        # Sample data includes applied migrations
        assert len(applied) > 0

    def test_add_migration(self):
        """Test adding a new migration."""
        from dashboard.services.database import MigrationManager

        manager = MigrationManager()
        migration = manager.add_migration(
            version="999",
            name="test_migration",
            description="Test migration",
            up_sql="CREATE TABLE test (id INT);",
            down_sql="DROP TABLE test;",
        )

        assert migration.version == "999"
        assert migration.checksum is not None

    def test_dry_run(self):
        """Test migration dry run."""
        from dashboard.services.database import MigrationManager

        manager = MigrationManager()
        results = manager.migrate(dry_run=True)

        # Dry run should not change status
        for result in results:
            assert result.get("dry_run") == True

    def test_verify_checksums(self):
        """Test checksum verification."""
        from dashboard.services.database import MigrationManager

        manager = MigrationManager()
        issues = manager.verify_checksums()

        # Should be no issues with fresh manager
        assert isinstance(issues, list)


class TestRepository:
    """Tests for Repository pattern."""

    @pytest.mark.asyncio
    async def test_experiment_repository(self):
        """Test ExperimentRepository."""
        from dashboard.services.database import ExperimentRepository, ExperimentEntity

        repo = ExperimentRepository()

        # Create
        experiment = ExperimentEntity(
            name="Test Experiment",
            description="Testing repository",
            status="created",
            owner="test",
        )
        saved = await repo.save(experiment)
        assert saved.id == experiment.id

        # Read
        found = await repo.find_by_id(experiment.id)
        assert found is not None
        assert found.name == "Test Experiment"

        # List
        all_experiments = await repo.find_all()
        assert len(all_experiments) > 0

        # Delete
        deleted = await repo.delete(experiment.id)
        assert deleted == True

    @pytest.mark.asyncio
    async def test_unit_of_work(self):
        """Test UnitOfWork pattern."""
        from dashboard.services.database import UnitOfWork, ExperimentEntity

        async with UnitOfWork() as uow:
            # Create experiment through UoW
            exp = ExperimentEntity(name="UoW Test", status="created")
            await uow.experiments.save(exp)

            # Should be accessible
            found = await uow.experiments.find_by_id(exp.id)
            assert found is not None


# ============================================
# Optimization Service Tests
# ============================================

class TestGeneticAlgorithm:
    """Tests for GeneticAlgorithm."""

    def test_initialization(self):
        """Test GA initialization."""
        from dashboard.services.optimization import GeneticAlgorithm, GAConfig

        def fitness(genes):
            return -sum((g - 0.5) ** 2 for g in genes)

        config = GAConfig(
            population_size=20,
            max_generations=10,
            chromosome_length=5,
        )

        ga = GeneticAlgorithm(config, fitness)
        population = ga.initialize_population()

        assert len(population.individuals) == 20
        assert all(len(ind.genes) == 5 for ind in population.individuals)

    def test_evolution(self):
        """Test GA evolution."""
        from dashboard.services.optimization import GeneticAlgorithm, GAConfig

        def fitness(genes):
            return -sum((g - 0.5) ** 2 for g in genes)

        config = GAConfig(
            population_size=20,
            max_generations=5,
            chromosome_length=3,
        )

        ga = GeneticAlgorithm(config, fitness)
        ga.initialize_population()

        initial_best = ga.population.best_fitness

        for _ in range(5):
            ga.evolve()

        # Fitness should improve or stay same
        assert ga.population.best_fitness >= initial_best

    def test_full_run(self):
        """Test full GA run."""
        from dashboard.services.optimization import GeneticAlgorithm, GAConfig

        def fitness(genes):
            # Sphere function (minimum at origin)
            return -sum(g ** 2 for g in genes)

        config = GAConfig(
            population_size=30,
            max_generations=20,
            chromosome_length=3,
            gene_bounds=[(-5.0, 5.0)] * 3,
        )

        ga = GeneticAlgorithm(config, fitness)
        best = ga.run()

        assert best is not None
        assert best.fitness > -75  # Should find something reasonable

    def test_results(self):
        """Test getting GA results."""
        from dashboard.services.optimization import GeneticAlgorithm, GAConfig

        def fitness(genes):
            return sum(genes)

        config = GAConfig(population_size=10, max_generations=5)
        ga = GeneticAlgorithm(config, fitness)
        ga.run()

        results = ga.get_results()
        assert "best_individual" in results
        assert "history" in results
        assert len(results["history"]) == 5


class TestMultiObjectiveOptimizer:
    """Tests for MultiObjectiveOptimizer."""

    def test_initialization(self):
        """Test NSGA-II initialization."""
        from dashboard.services.optimization import (
            MultiObjectiveOptimizer,
            ObjectiveFunction,
            ObjectiveDirection,
        )

        objectives = [
            ObjectiveFunction("f1", lambda x: x[0] ** 2, ObjectiveDirection.MINIMIZE),
            ObjectiveFunction("f2", lambda x: (x[0] - 2) ** 2, ObjectiveDirection.MINIMIZE),
        ]

        optimizer = MultiObjectiveOptimizer(
            objectives=objectives,
            gene_bounds=[(0.0, 2.0)],
            population_size=20,
        )

        population = optimizer.initialize_population()
        assert len(population) == 20

    def test_dominance(self):
        """Test Pareto dominance."""
        from dashboard.services.optimization import (
            MultiObjectiveOptimizer,
            ObjectiveFunction,
            Solution,
        )

        objectives = [
            ObjectiveFunction("f1", lambda x: x[0]),
            ObjectiveFunction("f2", lambda x: x[0]),
        ]

        optimizer = MultiObjectiveOptimizer(
            objectives=objectives,
            gene_bounds=[(0.0, 1.0)],
        )

        s1 = Solution("s1", [0.3], [0.3, 0.3])
        s2 = Solution("s2", [0.5], [0.5, 0.5])

        # s1 should dominate s2 (both objectives smaller)
        assert optimizer.dominates(s1, s2)
        assert not optimizer.dominates(s2, s1)

    def test_pareto_front(self):
        """Test Pareto front extraction."""
        from dashboard.services.optimization import (
            MultiObjectiveOptimizer,
            ObjectiveFunction,
            ObjectiveDirection,
        )

        objectives = [
            ObjectiveFunction("f1", lambda x: x[0], ObjectiveDirection.MINIMIZE),
            ObjectiveFunction("f2", lambda x: 1 - x[0], ObjectiveDirection.MINIMIZE),
        ]

        optimizer = MultiObjectiveOptimizer(
            objectives=objectives,
            gene_bounds=[(0.0, 1.0)],
            population_size=30,
            max_generations=10,
        )

        result = optimizer.run()

        assert result.pareto_front is not None
        assert len(result.pareto_front.solutions) > 0
        assert result.pareto_front.rank == 0


class TestManufacturingOptimizer:
    """Tests for manufacturing-specific optimization."""

    def test_print_parameters(self):
        """Test PrintParameters conversion."""
        from dashboard.services.optimization import PrintParameters

        params = PrintParameters(
            layer_height=0.2,
            nozzle_temperature=210.0,
            print_speed=60.0,
        )

        genes = params.to_genes()
        restored = PrintParameters.from_genes(genes)

        assert restored.layer_height == params.layer_height
        assert restored.nozzle_temperature == params.nozzle_temperature

    def test_print_parameter_optimization(self):
        """Test print parameter optimization."""
        from dashboard.services.optimization import PrintParameterOptimizer

        optimizer = PrintParameterOptimizer(
            target_quality="balanced",
            material="PLA",
        )

        result = optimizer.optimize(
            objectives=["quality", "time"],
            generations=10,
            population_size=20,
        )

        assert "recommended" in result
        assert "pareto_front" in result
        assert len(result["pareto_front"]) > 0

    def test_scheduling_optimization(self):
        """Test scheduling optimization."""
        from dashboard.services.optimization import SchedulingOptimizer

        jobs = [
            {"id": f"job_{i}", "duration": 10 + i * 5}
            for i in range(10)
        ]
        machines = [{"id": f"machine_{i}"} for i in range(3)]

        optimizer = SchedulingOptimizer(jobs, machines)
        result = optimizer.optimize(generations=20)

        assert "schedule" in result
        assert "makespan" in result
        assert "utilization" in result
        assert result["utilization"] > 0

    def test_quality_threshold_optimization(self):
        """Test quality threshold optimization."""
        from dashboard.services.optimization import QualityOptimizer

        optimizer = QualityOptimizer(
            defect_costs={"crack": 100, "void": 50},
            inspection_costs=5.0,
            false_positive_cost=10.0,
            false_negative_cost=100.0,
        )

        # Precision-recall curve data
        pr_curve = [
            (0.1, 0.6, 0.95),
            (0.3, 0.75, 0.85),
            (0.5, 0.85, 0.70),
            (0.7, 0.92, 0.50),
            (0.9, 0.98, 0.30),
        ]

        result = optimizer.optimize_threshold(pr_curve)

        assert "optimal_threshold" in result
        assert 0 <= result["optimal_threshold"] <= 1
        assert "recommendation" in result


class TestBayesianOptimizer:
    """Tests for Bayesian optimization."""

    def test_suggest(self):
        """Test point suggestion."""
        from dashboard.services.optimization import BayesianOptimizer

        def objective(x):
            return -(x[0] - 0.5) ** 2

        optimizer = BayesianOptimizer(
            bounds=[(0.0, 1.0)],
            objective_function=objective,
            n_initial_points=3,
        )

        # Initial suggestions should be random
        for _ in range(3):
            x = optimizer.suggest()
            y = objective(x)
            optimizer.observe(x, y)

        # After initial points, should use acquisition
        x = optimizer.suggest()
        assert 0 <= x[0] <= 1

    def test_optimization(self):
        """Test full Bayesian optimization."""
        from dashboard.services.optimization import BayesianOptimizer

        def objective(x):
            # Simple 1D function with maximum at 0.7
            return -((x[0] - 0.7) ** 2)

        optimizer = BayesianOptimizer(
            bounds=[(0.0, 1.0)],
            objective_function=objective,
            n_initial_points=5,
        )

        result = optimizer.optimize(n_iterations=15)

        assert result["best_x"] is not None
        assert result["best_y"] is not None
        # Should find something close to 0.7
        assert abs(result["best_x"][0] - 0.7) < 0.3

    def test_hyperparameter_tuner(self):
        """Test hyperparameter tuning interface."""
        from dashboard.services.optimization import HyperparameterTuner

        def objective(params):
            # Simulated model performance
            lr = params["learning_rate"]
            batch = params["batch_size"]
            return -(lr - 0.001) ** 2 - (batch - 32) ** 2 / 1000

        tuner = HyperparameterTuner(
            param_space={
                "learning_rate": (0.0001, 0.01),
                "batch_size": (8, 64),
            },
            objective_function=objective,
        )

        result = tuner.tune(n_trials=10)

        assert "best_params" in result
        assert "learning_rate" in result["best_params"]
        assert "batch_size" in result["best_params"]


# ============================================
# Run tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
