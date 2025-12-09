# docker_postgres_diagnostics_clean Recipe

**Created from:** Conversation #4
**Goal:** Docker container and PostgreSQL database diagnostics - check container health, database structure, and resource usage
**Status:** success
**Created:** 2025-12-07 17:24:35

## Overview

Complete diagnostics for Docker PostgreSQL containers. Checks container health, resource usage, network bindings, database structure, table sizes, row counts, and schema definitions. Ideal for troubleshooting thermostat monitoring systems or any PostgreSQL-in-Docker deployment.

## Prerequisites

Docker installed and running, PostgreSQL container named 'thermostat_postgres' deployed, user has docker command access (no sudo required if in docker group)

## Usage

### Basic Usage
```bash
bash docker_postgres_diagnostics_clean.sh
```

### With Output Logging
```bash
bash docker_postgres_diagnostics_clean.sh | tee docker_postgres_diagnostics_clean_output.txt
```

### With Sudo (if needed)
```bash
sudo bash docker_postgres_diagnostics_clean.sh
```

## Steps

This recipe executes 9 steps:

1. **Step 1**: `docker ps`
2. **Step 2**: `docker inspect thermostat_postgres | grep -A 10 "Mounts"`
3. **Step 3**: `docker inspect thermostat_postgres | grep -A 5 "Env"`
4. **Step 4**: `docker logs thermostat_postgres --tail 20`
5. **Step 5**: `docker stats --no-stream thermostat_postgres`
6. **Step 6**: `ss -tunlp | grep 5433`
7. **Step 7**: `ls -la /home/obd/local-server`
8. **Step 8**: `ps aux | grep -i "python.*local-server" | grep -v grep`
9. **PostgreSQL database structure investigation - list databases, tables, sizes, and schemas** (batch script)

## Success Criteria

Container status UP, port 5433 listening, database accessible, tables present and sized, memory usage <5% for idle database

## Statistics

- **Times executed:** 5
- **Last updated:** 2025-12-07 17:24:35
