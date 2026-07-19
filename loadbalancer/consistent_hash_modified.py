"""
Task 2: Consistent Hash Map Modified
"""
import threading


class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        self.num_slots = num_slots
        self.num_virtual = num_virtual

        # slot -> hostname (None if empty)
        self.ring = [None] * num_slots

        # bookkeeping so we can remove a server later and reuse integer ids
        self.hostname_to_id = {}
        self.id_to_hostname = {}
        self.hostname_to_slots = {}  # hostname -> list of occupied slot indices
        self._next_id = 1

        self._lock = threading.Lock()

    # ---- hash functions -------------------------------------------------
    def _request_hash(self, request_id: int) -> int:
        return ((request_id * 2654435761) & 0xFFFFFFFF) % self.num_slots

    def _virtual_hash(self, i: int, j: int) -> int:
        return (((i * 1315423911) ^ (j * 2654435761)) & 0xFFFFFFFF) % self.num_slots
    # ---- internal helpers -------------------------------------------------
    def _linear_probe_empty(self, start_slot: int) -> int:
        """Find the next empty slot at or after start_slot (clockwise)."""
        for offset in range(self.num_slots):
            slot = (start_slot + offset) % self.num_slots
            if self.ring[slot] is None:
                return slot
        raise RuntimeError("Consistent hash map is full (no empty slots left)")

    def _linear_probe_occupied(self, start_slot: int) -> int:
        """Find the next occupied slot at or after start_slot (clockwise)."""
        for offset in range(self.num_slots):
            slot = (start_slot + offset) % self.num_slots
            if self.ring[slot] is not None:
                return slot
        raise RuntimeError("Consistent hash map has no servers")

    # ---- public API -------------------------------------------------------
    def add_server(self, hostname: str, server_id: int = None) -> int:
        """Places K virtual copies of `hostname` on the ring. Returns the
        integer server id used (auto-assigned if not given)."""
        with self._lock:
            if server_id is None:
                server_id = self._next_id
            self._next_id = max(self._next_id, server_id + 1)

            self.hostname_to_id[hostname] = server_id
            self.id_to_hostname[server_id] = hostname
            self.hostname_to_slots[hostname] = []

            for j in range(self.num_virtual):
                ideal_slot = self._virtual_hash(server_id, j)
                actual_slot = self._linear_probe_empty(ideal_slot)
                self.ring[actual_slot] = hostname
                self.hostname_to_slots[hostname].append(actual_slot)

            return server_id

    def remove_server(self, hostname: str):
        with self._lock:
            for slot in self.hostname_to_slots.get(hostname, []):
                self.ring[slot] = None
            self.hostname_to_slots.pop(hostname, None)
            sid = self.hostname_to_id.pop(hostname, None)
            if sid is not None:
                self.id_to_hostname.pop(sid, None)

    def get_server(self, request_id: int):
        """Returns the hostname responsible for this request, or None if
        the ring is empty."""
        with self._lock:
            if not self.hostname_to_id:
                return None
            slot = self._request_hash(request_id)
            occupied_slot = self._linear_probe_occupied(slot)
            return self.ring[occupied_slot]

    def snapshot(self):
        """Debug helper: current ring state as a list of (slot, hostname)."""
        with self._lock:
            return [(i, h) for i, h in enumerate(self.ring) if h is not None]
