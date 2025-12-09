#!/bin/bash
# Recipe: docker_postgres_diagnostics_clean
# Description: Complete diagnostics for Docker PostgreSQL containers. Checks container health, resource usage, network bindings, database structure, table sizes, row counts, and schema definitions. Ideal for troubleshooting thermostat monitoring systems or any PostgreSQL-in-Docker deployment.
# Created: 2025-12-07 17:24:35
# Times used: 5

# Source: Conversation #4
# Goal: Docker container and PostgreSQL database diagnostics - check container health, database structure, and resource usage
# Status: success

echo "=== docker_postgres_diagnostics_clean ==="
echo "Started: $(date)"
echo ""

echo "=== [1/9] Step 1 ==="
docker ps
echo "[STEP_1_COMPLETE]"
echo ""

echo "=== [2/9] Step 2 ==="
docker inspect thermostat_postgres | grep -A 10 "Mounts"
echo "[STEP_2_COMPLETE]"
echo ""

echo "=== [3/9] Step 3 ==="
docker inspect thermostat_postgres | grep -A 5 "Env"
echo "[STEP_3_COMPLETE]"
echo ""

echo "=== [4/9] Step 4 ==="
docker logs thermostat_postgres --tail 20
echo "[STEP_4_COMPLETE]"
echo ""

echo "=== [5/9] Step 5 ==="
docker stats --no-stream thermostat_postgres
echo "[STEP_5_COMPLETE]"
echo ""

echo "=== [6/9] Step 6 ==="
ss -tunlp | grep 5433
echo "[STEP_6_COMPLETE]"
echo ""

echo "=== [7/9] Step 7 ==="
ls -la /home/obd/local-server
echo "[STEP_7_COMPLETE]"
echo ""

echo "=== [8/9] Step 8 ==="
ps aux | grep -i "python.*local-server" | grep -v grep
echo "[STEP_8_COMPLETE]"
echo ""

echo "=== [9/9] PostgreSQL database structure investigation - list databases, tables, sizes, and schemas ==="

# Batch script embedded below:
#!/bin/bash
echo "=== [STEP 1/5] List all databases ==="
docker exec thermostat_postgres psql -U postgres -c "\l"
echo "[STEP_1_COMPLETE]"

echo "=== [STEP 2/5] List all tables in thermostat_db ==="
docker exec thermostat_postgres psql -U postgres -d thermostat_db -c "\dt"
echo "[STEP_2_COMPLETE]"

echo "=== [STEP 3/5] Get table sizes ==="
docker exec thermostat_postgres psql -U postgres -d thermostat_db -c "SELECT schemaname, relname AS table_name, pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) AS size FROM pg_stat_user_tables ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC;"
echo "[STEP_3_COMPLETE]"

echo "=== [STEP 4/5] Get row counts ==="
docker exec thermostat_postgres psql -U postgres -d thermostat_db -c "SELECT schemaname, relname AS table_name, n_live_tup AS row_count FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"
echo "[STEP_4_COMPLETE]"

echo "=== [STEP 5/5] List table columns and types ==="
docker exec thermostat_postgres psql -U postgres -d thermostat_db -c "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position LIMIT 40;"
echo "[STEP_5_COMPLETE]"
echo "[ALL_DIAGNOSTICS_COMPLETE]"


echo "[STEP_9_COMPLETE]"
echo ""

echo "[ALL_STEPS_COMPLETE]"
echo "Completed: $(date)"