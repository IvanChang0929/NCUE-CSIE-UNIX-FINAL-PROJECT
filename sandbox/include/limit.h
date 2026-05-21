#ifndef LIMIT_H
#define LIMIT_H

#include <sys/resource.h>

void setup_resource_limits();
void setup_cgroup(pid_t pid);
void print_resource_usage(void);
void print_sandbox_result(int status);

#endif