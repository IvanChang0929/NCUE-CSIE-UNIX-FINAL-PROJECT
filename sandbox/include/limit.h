#ifndef LIMIT_H
#define LIMIT_H

#include <sys/resource.h>
#include <sys/types.h>

void setup_resource_limits(long memory_mb, int timeout_sec);
void setup_cgroup(pid_t pid, const char *job_id, double cpu_core, long memory_mb);
long read_cgroup_memory_current_kb(const char *job_id);
long read_cgroup_cpu_usage_usec(const char *job_id);
void print_resource_usage(void);
void print_sandbox_result(int status);

#endif