"""
Load testing suite using Locust.

Tests API performance under load conditions.
Run with: locust -f tests/load/locustfile.py --host=http://localhost:5000
"""

import json
import random
import string
from datetime import datetime, timedelta
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


def random_string(length=8):
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


class SCADAUser(HttpUser):
    """
    Simulates SCADA system interactions.

    These users perform high-frequency tag reads/writes typical of SCADA systems.
    """
    weight = 3
    wait_time = between(0.1, 0.5)  # Fast polling typical of SCADA

    def on_start(self):
        """Set up test data."""
        self.tag_ids = [f"tag_{i:03d}" for i in range(100)]
        self.alarm_ids = [f"alarm_{i:03d}" for i in range(20)]

    @task(10)
    def read_tag_value(self):
        """Read a single tag value."""
        tag_id = random.choice(self.tag_ids)
        with self.client.get(
            f"/api/scada/tags/{tag_id}",
            name="/api/scada/tags/[tag_id]",
            catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()  # Tag may not exist in test env

    @task(5)
    def write_tag_value(self):
        """Write a tag value."""
        tag_id = random.choice(self.tag_ids)
        payload = {
            "tag_id": tag_id,
            "value": random.uniform(0, 100),
            "quality": 192,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.client.post(
            "/api/scada/tags/write",
            json=payload,
            name="/api/scada/tags/write"
        )

    @task(3)
    def batch_write_tags(self):
        """Write multiple tag values in batch."""
        tags = random.sample(self.tag_ids, k=min(10, len(self.tag_ids)))
        payload = {
            "values": [
                {
                    "tag_id": tag_id,
                    "value": random.uniform(0, 100),
                    "quality": 192
                }
                for tag_id in tags
            ]
        }
        self.client.post(
            "/api/scada/tags/batch-write",
            json=payload,
            name="/api/scada/tags/batch-write"
        )

    @task(2)
    def get_active_alarms(self):
        """Get active alarms."""
        self.client.get("/api/scada/alarms/active")

    @task(1)
    def get_alarm_summary(self):
        """Get alarm summary."""
        self.client.get("/api/scada/alarms/summary")

    @task(1)
    def acknowledge_alarm(self):
        """Acknowledge an alarm."""
        alarm_id = random.choice(self.alarm_ids)
        payload = {
            "acknowledged_by": "test_operator",
            "notes": "Load test acknowledgment"
        }
        with self.client.post(
            f"/api/scada/alarms/{alarm_id}/acknowledge",
            json=payload,
            name="/api/scada/alarms/[alarm_id]/acknowledge",
            catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()


class HistorianUser(HttpUser):
    """
    Simulates Historian data queries.

    These users perform trend queries and data exports.
    """
    weight = 1
    wait_time = between(1, 5)

    def on_start(self):
        """Set up test data."""
        self.tag_ids = [f"tag_{i:03d}" for i in range(100)]

    @task(5)
    def query_trend_data(self):
        """Query trend data for a tag."""
        tag_id = random.choice(self.tag_ids)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        params = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "tags": tag_id
        }
        self.client.get(
            "/api/historian/trend",
            params=params,
            name="/api/historian/trend"
        )

    @task(2)
    def query_raw_data(self):
        """Query raw historian data."""
        tag_id = random.choice(self.tag_ids)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)

        params = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "tags": tag_id
        }
        self.client.get(
            "/api/historian/raw",
            params=params,
            name="/api/historian/raw"
        )

    @task(1)
    def get_historian_stats(self):
        """Get historian statistics."""
        self.client.get("/api/historian/stats")


class QMSUser(HttpUser):
    """
    Simulates QMS interactions.

    These users create NCRs, CAPAs, and manage quality workflows.
    """
    weight = 1
    wait_time = between(2, 10)

    def on_start(self):
        """Set up test data."""
        self.ncr_ids = []
        self.capa_ids = []
        self.severities = ['critical', 'major', 'minor']
        self.dispositions = ['rework', 'scrap', 'use_as_is', 'return_to_vendor']

    @task(3)
    def list_ncrs(self):
        """List NCRs with filters."""
        params = {
            "status": random.choice(["draft", "open", "closed"]),
            "page": 1,
            "per_page": 20
        }
        self.client.get("/api/qms/ncrs", params=params)

    @task(2)
    def create_ncr(self):
        """Create a new NCR."""
        payload = {
            "title": f"Load Test NCR - {random_string()}",
            "description": "NCR created during load testing",
            "detected_by": "load_test_user",
            "severity": random.choice(self.severities),
            "category": "dimensional",
            "product_id": f"PART-{random_string(4)}",
            "lot_number": f"LOT-{random_string(6)}"
        }
        with self.client.post(
            "/api/qms/ncrs",
            json=payload,
            name="/api/qms/ncrs [POST]",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                data = response.json()
                if 'ncr_number' in data:
                    self.ncr_ids.append(data['ncr_number'])

    @task(1)
    def get_ncr_details(self):
        """Get NCR details."""
        if self.ncr_ids:
            ncr_id = random.choice(self.ncr_ids)
            self.client.get(
                f"/api/qms/ncrs/{ncr_id}",
                name="/api/qms/ncrs/[ncr_id]"
            )

    @task(1)
    def get_ncr_metrics(self):
        """Get NCR metrics."""
        params = {"days": random.choice([7, 30, 90])}
        self.client.get("/api/qms/ncrs/metrics", params=params)

    @task(1)
    def list_capas(self):
        """List CAPAs."""
        params = {
            "status": random.choice(["draft", "open", "closed"]),
            "page": 1,
            "per_page": 20
        }
        self.client.get("/api/qms/capas", params=params)


class MLInferenceUser(HttpUser):
    """
    Simulates ML inference requests.

    These users submit sensor data for anomaly detection.
    """
    weight = 1
    wait_time = between(1, 3)

    @task(5)
    def run_inference(self):
        """Run ML inference on sensor data."""
        # Generate random sensor data
        sensor_data = [
            [random.gauss(50, 10) for _ in range(10)]
            for _ in range(256)
        ]
        payload = {
            "sensor_data": sensor_data,
            "tag_id": f"sensor_group_{random.randint(1, 10):03d}"
        }
        self.client.post(
            "/api/ml/inference/predict",
            json=payload,
            name="/api/ml/inference/predict"
        )

    @task(2)
    def get_inference_stats(self):
        """Get inference statistics."""
        self.client.get("/api/ml/inference/stats")

    @task(1)
    def compare_fingerprints(self):
        """Compare two fingerprints."""
        fp1 = [random.gauss(0, 1) for _ in range(128)]
        fp2 = [random.gauss(0, 1) for _ in range(128)]
        payload = {
            "fingerprint1": fp1,
            "fingerprint2": fp2
        }
        self.client.post(
            "/api/ml/inference/compare",
            json=payload,
            name="/api/ml/inference/compare"
        )


class RoboticsUser(HttpUser):
    """
    Simulates ROS2 robotics interactions.

    These users interact with the robot control APIs.
    """
    weight = 1
    wait_time = between(1, 5)

    def on_start(self):
        """Set up test data."""
        self.robot_ids = ["xarm_001", "xarm_002", "ur5_001"]

    @task(5)
    def get_robot_state(self):
        """Get robot state."""
        robot_id = random.choice(self.robot_ids)
        self.client.get(
            f"/api/robotics/robots/{robot_id}/state",
            name="/api/robotics/robots/[robot_id]/state"
        )

    @task(2)
    def get_all_robots(self):
        """Get all robots status."""
        self.client.get("/api/robotics/robots")

    @task(1)
    def send_move_command(self):
        """Send a move command (simulation mode)."""
        robot_id = random.choice(self.robot_ids)
        payload = {
            "x": random.uniform(0.1, 0.5),
            "y": random.uniform(-0.3, 0.3),
            "z": random.uniform(0.1, 0.4),
            "speed": 0.1,
            "simulation": True
        }
        with self.client.post(
            f"/api/robotics/robots/{robot_id}/move",
            json=payload,
            name="/api/robotics/robots/[robot_id]/move",
            catch_response=True
        ) as response:
            if response.status_code in [404, 503]:
                response.success()  # Robot may not be connected


class HealthCheckUser(HttpUser):
    """
    Simulates monitoring system health checks.
    """
    weight = 1
    wait_time = between(5, 15)

    @task(5)
    def health_check(self):
        """Check application health."""
        self.client.get("/health")

    @task(2)
    def metrics_endpoint(self):
        """Fetch Prometheus metrics."""
        self.client.get("/metrics")


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    if isinstance(environment.runner, MasterRunner):
        print("Load test starting on master node")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("\n=== Load Test Complete ===")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"Requests/sec: {environment.stats.total.total_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Called on each request for custom logging."""
    if exception:
        print(f"Request failed: {name} - {exception}")
