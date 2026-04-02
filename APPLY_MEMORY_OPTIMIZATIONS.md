# 🚀 GUIA RÁPIDO: Aplicar Otimizações de Memória

**Problema**: Instância AWS t2.micro (1GB RAM) travando por Out of Memory
**Solução**: Configurações otimizadas já aplicadas

---

## ✅ Arquivos Modificados/Criados

### 1. Django Settings (✅ APLICADO)
- **Arquivo**: `config/settings/prod.py`
- **Mudanças**:
  - ✅ Connection pooling otimizado
  - ✅ Redis max_connections: 50 → 20
  - ✅ Session engine: database → cache
  - ✅ Celery worker concurrency: auto → 1
  - ✅ Query timeout: 30s

### 2. Gunicorn Config (📄 CRIADO)
- **Arquivo**: `gunicorn.conf.py`
- **Config**:
  - Workers: 2 (fixo, não baseado em CPU)
  - Worker class: sync (usa menos RAM)
  - Max requests: 500 (previne memory leaks)
  - Preload app: True (workers compartilham memória)

### 3. PostgreSQL Config (📄 CRIADO)
- **Arquivo**: `postgresql-low-memory.conf`
- **Config**:
  - shared_buffers: 64MB
  - effective_cache_size: 192MB
  - work_mem: 2MB
  - max_connections: 30

### 4. Redis Config (📄 CRIADO)
- **Arquivo**: `redis-low-memory.conf`
- **Config**:
  - maxmemory: 128MB
  - maxmemory-policy: allkeys-lru
  - Persistence desabilitada (cache-only)

### 5. Memory Monitor (📄 CRIADO)
- **Arquivo**: `monitor-memory.sh`
- **Features**:
  - Monitora uso de memória
  - Alerta em 80% e 90%
  - Auto-restart em crítico
  - Log de processos

---

## 📋 Passos para Aplicar (NO SERVIDOR)

### Passo 1: Gunicorn (Restart Imediato)

```bash
# Já está criado: gunicorn.conf.py
# Reiniciar serviço Django
sudo systemctl restart tickettche-backend

# Verificar se está usando 2 workers
ps aux | grep gunicorn | grep -v grep
# Deve mostrar: 1 master + 2 workers = 3 processos
```

### Passo 2: PostgreSQL (Aplicar Config)

```bash
# Copiar configuração para PostgreSQL
sudo cp postgresql-low-memory.conf /etc/postgresql/14/main/conf.d/tickettche-optimization.conf

# Ou append ao arquivo principal:
sudo cat postgresql-low-memory.conf >> /etc/postgresql/14/main/postgresql.conf

# Testar configuração
sudo -u postgres /usr/lib/postgresql/14/bin/postgres -D /var/lib/postgresql/14/main --config-file=/etc/postgresql/14/main/postgresql.conf -C shared_buffers

# Se teste OK, reiniciar PostgreSQL
sudo systemctl restart postgresql

# Verificar settings
psql -U tickettche -d tickettche -c "SHOW shared_buffers;"
psql -U tickettche -d tickettche -c "SHOW max_connections;"
```

### Passo 3: Redis (Aplicar Config)

```bash
# Backup da config atual
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup

# Aplicar mudanças
sudo bash -c 'cat redis-low-memory.conf >> /etc/redis/redis.conf'

# Ou substituir completamente:
sudo cp redis-low-memory.conf /etc/redis/redis-tickettche.conf

# Reiniciar Redis
sudo systemctl restart redis

# Verificar settings
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy

# Ver uso atual de memória
redis-cli INFO memory
```

### Passo 4: Setup Monitoramento

```bash
# Mover script para /usr/local/bin
sudo cp monitor-memory.sh /usr/local/bin/tickettche-monitor-memory
sudo chmod +x /usr/local/bin/tickettche-monitor-memory

# Testar manualmente
sudo /usr/local/bin/tickettche-monitor-memory

# Adicionar ao cron (executar a cada 5 minutos)
sudo crontab -e

# Adicionar esta linha:
*/5 * * * * /usr/local/bin/tickettche-monitor-memory

# Verificar logs
tail -f /var/log/tickettche/memory-monitor.log
```

---

## 🔍 Verificação Pós-Aplicação

### Verificar Uso de Memória

```bash
# Ver uso total
free -h

# Ver processos por memória
ps aux --sort=-%mem | head -n 15

# Esperado:
# - Total usage: 70-80% (safe range)
# - Gunicorn: ~200-300MB (2 workers)
# - PostgreSQL: ~200-250MB
# - Redis: ~100-128MB
# - OS: ~150MB
```

### Verificar Gunicorn Workers

```bash
# Ver workers ativos
ps aux | grep gunicorn

# Deve mostrar:
# - 1 master process
# - 2 worker processes
# Total: 3 processos gunicorn
```

### Verificar Logs de OOM (Out of Memory)

```bash
# Ver se houve OOM kill recentemente
dmesg | grep -i "killed process"

# Se vazio = bom (nenhum processo morto por OOM)
# Se aparecer = problema ainda não resolvido
```

### Testar Endpoints

```bash
# Testar que o backend está funcionando
curl http://localhost:8000/api/health/

# Deve retornar: {"status": "healthy"}
```

---

## 📊 Monitoramento Contínuo

### Comando para Watch em Tempo Real

```bash
# Terminal 1: Watch memory usage
watch -n 2 'free -h'

# Terminal 2: Watch top processes
watch -n 2 'ps aux --sort=-%mem | head -n 15'

# Terminal 3: Watch logs
tail -f /var/log/tickettche/memory-monitor.log
```

### Sinais de Problema

❌ **Ruim** (precisa investigar):
- Uso de memória > 90%
- Swap usage > 0%
- OOM killer ativo
- Response time > 2s
- Processos travando

✅ **Bom**:
- Uso de memória 70-80%
- Zero swap
- Response time < 500ms
- Nenhum OOM kill
- Processos rodando normal

---

## 🚨 Emergency Actions (Se Travar Novamente)

### Restart Imediato

```bash
# 1. Restart backend
sudo systemctl restart tickettche-backend

# 2. Se não resolver, restart PostgreSQL
sudo systemctl restart postgresql

# 3. Se ainda não resolver, restart Redis
sudo systemctl restart redis

# 4. Clear Redis cache (libera memória)
redis-cli FLUSHALL

# 5. Ver o que está consumindo memória
ps aux --sort=-%mem | head -n 20
```

### Investigar Queries Lentas

```bash
# Ver queries ativas no PostgreSQL
psql -U tickettche -d tickettche -c "SELECT pid, age(clock_timestamp(), query_start), query FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"

# Matar query específica (se necessário)
psql -U tickettche -d tickettche -c "SELECT pg_terminate_backend(PID);"
```

---

## 🎯 Resultado Esperado

**Antes**:
- Uso de memória: 95-100% ❌
- OOM crashes: Frequentes ❌
- Workers: 5 (muito!) ❌
- PostgreSQL shared_buffers: 128MB+ ❌

**Depois**:
- Uso de memória: 70-80% ✅
- OOM crashes: Zero ✅
- Workers: 2 (ideal) ✅
- PostgreSQL shared_buffers: 64MB ✅

**Performance**:
- Response time: < 500ms ✅
- Database queries: < 100ms ✅
- Zero service restarts ✅
- 99.9% uptime ✅

---

## 📝 Notas Importantes

1. **Django settings já aplicado** - Mudanças em `prod.py` já estão no código
2. **Gunicorn config criado** - Precisa reiniciar serviço para aplicar
3. **PostgreSQL config criado** - Precisa copiar para /etc e reiniciar
4. **Redis config criado** - Precisa copiar para /etc e reiniciar
5. **Monitor criado** - Precisa instalar no cron

**Tempo total para aplicar**: ~15 minutos

**Impacto**: Zero downtime se aplicar durante low traffic

---

## 🔄 Quando Fazer Upgrade

Considere upgrade para t3.small (2GB RAM) quando:
- [ ] Uso de memória consistentemente > 85%
- [ ] Response time > 1s regularmente
- [ ] Frequentes service restarts necessários
- [ ] Traffic crescendo > 30% ao mês
- [ ] Adicionando features pesadas

**Custo**: t3.small ~$15/mês (vs t2.micro free tier)

---

**Tudo pronto! Aplicar no servidor seguindo os passos acima.** ✅
