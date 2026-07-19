"""
Standalone sanity test for ConsistentHashMap.
Run with: python test_consistent_hash.py or make test-hash
"""
import random
import collections
from consistent_hash import ConsistentHashMap


def test_basic_distribution():
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    for name in ["Server1", "Server2", "Server3"]:
        chm.add_server(name)

    counts = collections.Counter()
    for _ in range(10000):
        rid = random.randint(100000, 999999)
        server = chm.get_server(rid)
        counts[server] += 1

    print("Distribution across 3 servers (10,000 requests):")
    for server, count in counts.items():
        print(f"  {server}: {count}")
    print()


def test_failure_rebalance():
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    for name in ["Server1", "Server2", "Server3", "Server4"]:
        chm.add_server(name)

    print("Before failure:")
    counts_before = collections.Counter()
    for _ in range(10000):
        counts_before[chm.get_server(random.randint(100000, 999999))] += 1
    print(dict(counts_before))

    chm.remove_server("Server1")

    print("After removing Server1:")
    counts_after = collections.Counter()
    for _ in range(10000):
        counts_after[chm.get_server(random.randint(100000, 999999))] += 1
    print(dict(counts_after))
    print()


if __name__ == "__main__":
    test_basic_distribution()
    test_failure_rebalance()
