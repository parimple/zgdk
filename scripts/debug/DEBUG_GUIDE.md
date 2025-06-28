# Debug Scripts Guide

## Overview
Debug scripts help diagnose issues with the zaGadka Discord Bot in development and production environments.

## Debug Scripts

### 🐛 debug_interface.py
**Purpose**: Interactive debugging interface for real-time bot inspection
**Usage**:
```bash
python debug_interface.py
```
**Features**:
- Live bot state inspection
- Command execution tracking
- Database query monitoring
- Service health checks

### 🐛 debug_step_by_step.py
**Purpose**: Step-by-step execution debugger for complex workflows
**Usage**:
```bash
python debug_step_by_step.py <workflow_name>
```
**Workflows**:
- premium_purchase
- bump_notification
- role_assignment
- team_creation

### 🐛 debug_stub.py
**Purpose**: Minimal stub for testing debug infrastructure
**Usage**:
```bash
python debug_stub.py
```
**Use Cases**:
- Verify debug hooks are working
- Test logging configuration
- Check debug permissions

### 🐛 debug_test.py
**Purpose**: Test suite for debugging functionality
**Usage**:
```bash
python debug_test.py
```

## Debug Modes

### 1. Interactive Mode
```python
# Start interactive session
python debug_interface.py
> inspect bot.guilds
> check service IActivityTrackingService
> trace command ranking
```

### 2. Logging Mode
```python
# Enable verbose logging
DEBUG=true python debug_interface.py
```

### 3. Breakpoint Mode
```python
# Set breakpoints in code
import pdb; pdb.set_trace()
```

## Common Debug Scenarios

### Checking Service Status
```python
# In debug interface
> services
> check service IPremiumService
> check service IRoleService
```

### Tracing Command Execution
```python
# Trace specific command
> trace command shop
> trace command ranking @user
```

### Database Inspection
```python
# Check database state
> db tables
> db query "SELECT * FROM members WHERE id = 123"
```

### Memory Analysis
```python
# Check memory usage
> memory
> memory services
> memory cogs
```

## Debug Output

Debug information is saved to:
- `/logs/debug/` - Debug session logs
- `/logs/trace/` - Command execution traces
- `/logs/error/` - Error diagnostics

## Safety Notes

⚠️ **Warning**: Debug scripts can access sensitive data
- Never run in production without authorization
- Remove debug code before deployment
- Sanitize debug output before sharing

## Advanced Debugging

### Remote Debugging
```bash
# Connect to remote bot
python debug_interface.py --remote host:port
```

### Performance Profiling
```bash
# Profile bot performance
python debug_interface.py --profile
```

### Memory Leak Detection
```bash
# Monitor memory over time
python debug_interface.py --monitor-memory
```