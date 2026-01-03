import threading
import time
import unittest
import tempfile
import shutil
import socket
from pathlib import Path

from gate.broker import LockBrokerServer
from gate.config import BrokerConfig
from gate.client import LockBrokerClient, BrokerEndpoint

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class TestBrokerFairness(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.port = get_free_port()
        self.config = BrokerConfig(
            state_dir=self.tmp_dir,
            host="127.0.0.1",
            port=self.port,
            lease_ms=2000,
            acquire_timeout_ms=5000,
            max_hold_ms=10000
        )
        self.server = LockBrokerServer(self.config)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.5)
        
        self.endpoint = BrokerEndpoint(host="127.0.0.1", port=self.port)
        self.client = LockBrokerClient(self.endpoint, timeout_seconds=10)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_fifo_fairness(self):
        """Verify FIFO ordering: Writer A -> Writer B -> Reader C."""
        path = "fifo_test"
        
        # 1. A acquires Write
        res_a = self.client.acquire(path, "write", "owner_A", timeout_ms=1000, lease_ms=10000)
        self.assertEqual(res_a["status"], "granted")
        lock_id_a = res_a["lock"]["lock_id"]

        # 2. B requests Write (should block)
        events = []
        
        def run_b():
            # B attempts to acquire
            events.append("B_start")
            res_b = self.client.acquire(path, "write", "owner_B", timeout_ms=5000, lease_ms=10000)
            events.append("B_acquired")
            # B holds for a bit then releases
            time.sleep(0.5)
            self.client.release(res_b["lock"]["lock_id"], "owner_B")
            events.append("B_released")

        th_b = threading.Thread(target=run_b)
        th_b.start()
        time.sleep(0.2) # Ensure B is queued

        # 3. C requests Read (should block behind B)
        def run_c():
            events.append("C_start")
            res_c = self.client.acquire(path, "read", "owner_C", timeout_ms=5000, lease_ms=10000)
            events.append("C_acquired")
            self.client.release(res_c["lock"]["lock_id"], "owner_C")
            events.append("C_released")

        th_c = threading.Thread(target=run_c)
        th_c.start()
        time.sleep(0.2) # Ensure C is queued

        # Verify B and C haven't acquired yet
        self.assertNotIn("B_acquired", events)
        self.assertNotIn("C_acquired", events)

        # 4. Release A -> B should get it
        self.client.release(lock_id_a, "owner_A")
        
        th_b.join()
        
        # 5. After B finishes, C should get it
        th_c.join()
        
        expected_order = [
            "B_start", 
            "C_start", 
            "B_acquired", 
            "B_released", 
            "C_acquired", 
            "C_released"
        ]
        
        # Filter strictly for the order of acquisition/release that matters
        filtered_events = [e for e in events if e in expected_order]
        self.assertEqual(filtered_events, expected_order)

    def test_crash_recovery(self):
        """Verify that a lock is forcibly taken if the owner stops heartbeating."""
        path = "crash_test"
        lease_ms = 1000
        
        # 1. A acquires Write with short lease
        res_a = self.client.acquire(path, "write", "owner_A", timeout_ms=1000, lease_ms=lease_ms)
        self.assertEqual(res_a["status"], "granted")
        
        # 2. B attempts to acquire (should block initially)
        start_time = time.monotonic()
        
        # B waits slightly longer than lease
        res_b = self.client.acquire(path, "write", "owner_B", timeout_ms=3000, lease_ms=5000)
        
        duration = time.monotonic() - start_time
        self.assertEqual(res_b["status"], "granted")
        
        # It should have waited at least the lease time (approx)
        # We give some buffer for processing time.
        self.assertGreaterEqual(duration, 0.9) 

    def test_persistence(self):
        """Verify that locks persist across broker restarts (using shared DB)."""
        path = "persist_test"
        
        # 1. Acquire lock on Server A
        res = self.client.acquire(path, "write", "owner_P", timeout_ms=1000, lease_ms=10000)
        self.assertEqual(res["status"], "granted")
        lock_id = res["lock"]["lock_id"]
        
        # 2. Start Server B on a different port but same state_dir (same DB)
        port_b = get_free_port()
        config_b = BrokerConfig(
            state_dir=self.tmp_dir, 
            host="127.0.0.1",
            port=port_b,
            lease_ms=2000
        )
        server_b = LockBrokerServer(config_b)
        th_b = threading.Thread(target=server_b.serve_forever, daemon=True)
        th_b.start()
        time.sleep(0.5)
        
        # 3. Verify status via Server B
        client_b = LockBrokerClient(BrokerEndpoint("127.0.0.1", port_b), timeout_seconds=5)
        status = client_b.status(path)
        
        self.assertEqual(len(status["locks"]), 1)
        self.assertEqual(status["locks"][0]["owner"], "owner_P")
        self.assertEqual(status["locks"][0]["lock_id"], lock_id)

if __name__ == "__main__":
    unittest.main()
