NETWORK := net1

.PHONY: build up down restart logs clean test-hash

## Build both images (server must exist before the LB can spawn it)
build:
	docker build -t server:latest ./server
	docker build -t loadbalancer:latest ./loadbalancer

## Build images and start the load balancer (which spawns N=3 servers itself)
up: build
	docker compose up -d

down:
	docker compose down
	-docker rm -f $$(docker ps -aq --filter "name=Server_") 2>/dev/null || true

restart: down up

logs:
	docker compose logs -f

## Run the standalone consistent-hash unit test (no Docker required)
test-hash:
	cd loadbalancer && python3 test_consistent_hash.py

clean: down
	-docker network rm $(NETWORK)
	-docker rmi server:latest loadbalancer:latest
