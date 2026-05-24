#ifndef LIMIT_H
#define LIMIT_H

#include <sys/resource.h>
#include <sys/types.h>

void setup_resource_limits();
void setup_cgroup(pid_t pid, const char *job_id);
long read_cgroup_memory_current_kb(const char *job_id);
void print_resource_usage(void);
void print_sandbox_result(int status);

#endif